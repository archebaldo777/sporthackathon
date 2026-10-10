"""Подстройка весов формулы подбора на ОТДЕЛЬНЫХ наборах потребностей (не тех, на которых публикуются метрики).

Компоненты оценки (L, S, F, A, C, D) и модификаторы (бюджет, формат, гейт обязательных навыков, смежная категория)
считаются один раз для каждой пары «потребность — кандидат»; затем перебираются веса и множители:
случайный поиск вокруг экспертных значений + покоординатное уточнение в продуктовых рамках весов (WEIGHT_BOUNDS).
Цель — среднее nDCG@10, P@5 и P@10 на наборах подстройки.
Результат пишется в app/matching/tuned_params.json; итоговые метрики считаются в matching_eval на независимых наборах.

Запуск: python -m app.validation.tune_matching [--samples 250]
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from datetime import datetime, timezone
from pathlib import Path

from app.core.db import SessionLocal
from app.matching.scoring import EXPERT_PARAMS, combine, score
from app.matching.service import RELATION_ORDER
from app.validation.matching_eval import K, load_pool, make_needs, metrics, relevance

TUNING_SEEDS = (201, 202, 203)  # не пересекаются с наборами отчёта (77–81)
OUT = Path(__file__).resolve().parents[1] / "matching" / "tuned_params.json"
WEIGHT_KEYS = ["L", "S", "F_max", "A", "C", "D"]
# Продуктовые рамки весов (доли после нормировки). Без них поиск «подгоняет» формулу под синтетику: вес текста резюме
# растёт, а веса подтверждённых навыков и ФСП падают до нуля — это противоречит ТЗ (выдача по подтверждённому профилю,
# ФСП поднимает кандидата внутри категории). Рамки задают смысл, поиск — баланс внутри них.
WEIGHT_BOUNDS = {"L": (0.20, 0.40), "S": (0.20, 0.40), "F_max": (0.10, 0.25), "A": (0.04, 0.12), "C": (0.08, 0.22), "D": (0.02, 0.12)}
MULT_RANGES = {"salary_mult": (0.5, 1.0), "format_mult": (0.5, 1.0), "gate_floor": (0.1, 0.9), "adjacent_mult": (0.6, 1.0),
               "related_mult": (0.5, 1.0)}


def precompute(db, seeds=TUNING_SEEDS):
    pool, views, by_id, resume = load_pool(db)
    now = datetime.now(timezone.utc)
    cases = []
    for nv in [n for sd in seeds for n in make_needs(sd)]:
        rel = {c.user_id: relevance(nv, c) for c in pool}
        if sum(1 for v in rel.values() if v >= 2) < 3:
            continue
        sims = resume.query(nv.description + " " + " ".join(nv.must_skills + nv.nice_skills))
        rows = []
        for cid, v in views.items():
            r = score(v, nv, sims.get(cid, 0.0), now, with_parts=True)
            if r:
                rows.append((cid, RELATION_ORDER[r["relation"]], r["_parts"], by_id[cid].strength or 0))
        cases.append((rel, rows))
    return cases


def objective(cases, p) -> dict:
    ms = []
    for rel, rows in cases:
        ranked = sorted(rows, key=lambda x: (not x[2]["mods"]["grade_confirmed"], x[1],
                                             -combine(x[2]["comps"], x[2]["mods"], x[2]["fsp_weight"], p), -x[3]))
        ms.append(metrics([x[0] for x in ranked], rel))
    out = {k: statistics.mean(m[k] for m in ms) for k in ("ndcg@10", "p@10", "p@5", "mrr")}
    # цель — поровну качество порядка (nDCG@10) и доля подходящих в первых 5 и 10: работодатель смотрит верх выдачи
    out["goal"] = (out["ndcg@10"] + out["p@5"] + out["p@10"]) / 3
    return out


def feasible(p: dict) -> bool:
    s = sum(p[k] for k in WEIGHT_KEYS)
    return all(lo <= p[k] / s <= hi for k, (lo, hi) in WEIGHT_BOUNDS.items())


def sample(rng: random.Random, base: dict, scale: float) -> dict:
    p = dict(base)
    for k in WEIGHT_KEYS:
        p[k] = max(0.005, base[k] * rng.lognormvariate(0, scale))
    for k, (lo, hi) in MULT_RANGES.items():
        p[k] = min(hi, max(lo, base[k] + rng.gauss(0, scale * (hi - lo) / 2)))
    return p


def tune(samples: int = 800, seed: int = 7) -> dict:
    rng = random.Random(seed)
    with SessionLocal() as db:
        cases = precompute(db)
    expert = objective(cases, EXPERT_PARAMS)
    best, best_val = dict(EXPERT_PARAMS), expert["goal"]
    for i in range(samples):
        cand = sample(rng, best, 0.6 if i < samples // 2 else 0.25)
        if not feasible(cand):
            continue
        val = objective(cases, cand)["goal"]
        if val > best_val + 1e-4:
            best, best_val = cand, val
    # покоординатное уточнение
    for _ in range(2):
        for k in WEIGHT_KEYS + list(MULT_RANGES):
            for f in (0.8, 0.9, 1.1, 1.25):
                cand = dict(best)
                cand[k] = best[k] * f
                if k in MULT_RANGES:
                    cand[k] = min(MULT_RANGES[k][1], max(MULT_RANGES[k][0], cand[k]))
                if not feasible(cand):
                    continue
                val = objective(cases, cand)["goal"]
                if val > best_val + 1e-4:
                    best, best_val = cand, val
    s = sum(best[k] for k in WEIGHT_KEYS)
    best = {k: round(v / s if k in WEIGHT_KEYS else v, 3) for k, v in best.items()}  # веса — в долях
    tuned = objective(cases, best)
    return {"params": best, "bounds": WEIGHT_BOUNDS, "tuning_needs": len(cases), "tuning_seeds": list(TUNING_SEEDS),
            "tuning_metrics": {"expert": {k: round(v, 3) for k, v in expert.items()}, "tuned": {k: round(v, 3) for k, v in tuned.items()}}}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--samples", type=int, default=800)
    a = ap.parse_args()
    res = tune(a.samples)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
