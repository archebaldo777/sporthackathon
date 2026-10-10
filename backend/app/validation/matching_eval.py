"""Валидация механики подбора на тестовом наборе пар «потребность — кандидат».

Эталонная разметка строится по СКРЫТОЙ истине синтетических кандидатов (истинный грейд и истинные навыки),
недоступной ни одному ранжировщику. Ранжировщики видят только наблюдаемые данные (резюме, заявленный грейд,
результаты теста, ФСП, задачи). Поэтому сравнение честно отвечает на вопрос: помогает ли верифицированный
профиль находить действительно подходящих людей лучше, чем самоописанное резюме.

Релевантность (0–3):
  0 — другая специализация, грейд дальше чем на ступень, кандидат не ищет работу, нет ни одного обязательного навыка;
  1 — соседний грейд или слабое покрытие обязательных навыков;
  2 — целевой грейд и приемлемые навыки;
  3 — целевой грейд и ≥ 2/3 обязательных навыков реально есть;
  −1 за зарплатные ожидания выше вилки более чем на 10% и за несовместимый формат работы.
Метрики: Precision@10 (rel ≥ 2), nDCG@10 (gain = 2^rel − 1), MRR, Recall@30, доля нерелевантных (rel = 0) в топ-10.
"""
from __future__ import annotations

import math
import random
import statistics
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.catalog.data import GRADE_ORDER, GRADES, MARKET_SALARY, SPECIALIZATIONS
from app.matching.scoring import EXPERT_PARAMS, PARAMS, NeedView, score, weights
from app.matching.service import RELATION_ORDER, _pending, _task_skills, cand_text, to_view
from app.matching.text import TfIdf
from app.models import CandidateProfile
from app.seed.content import TRACK_STACK

K = 10


def make_needs(seed: int = 77) -> list[NeedView]:
    rng = random.Random(seed)
    needs = []
    for spec, info in SPECIALIZATIONS.items():
        tracks = [k for k in TRACK_STACK if k[0] == spec]
        for grade in GRADE_ORDER:
            for _ in range(2 if grade in ("junior", "middle") else 1):
                track = rng.choice(tracks)
                pool = TRACK_STACK[track]
                must = [pool[0]] + rng.sample(pool[1:], 2)
                rest = [s for s in pool if s not in must]
                nice = rng.sample(rest, min(2, len(rest)))
                grades = [grade] if rng.random() < 0.75 or grade == "senior" else [grade, GRADE_ORDER[GRADE_ORDER.index(grade) + 1]]
                med = MARKET_SALARY[spec][grade]
                lo = int(med * rng.uniform(0.85, 1.0))
                needs.append(NeedView(spec=spec, grades=grades, must_skills=must, nice_skills=nice, salary_from=lo,
                                      salary_to=int(lo * rng.uniform(1.2, 1.4)),
                                      work_formats=rng.choice([[], ["remote"], ["hybrid"], ["office", "hybrid"], ["remote", "hybrid"]]),
                                      fsp_weight=0.5, description=f"{info['name']}: {', '.join(must + nice)}"))
    return needs


def relevance(n: NeedView, c: CandidateProfile) -> int:
    t = c.synthetic_truth or {}
    if t.get("spec") != n.spec or c.search_status == "not_looking" or not c.visible:
        return 0
    tg = GRADE_ORDER.index(t["grade"])
    dist = min(abs(tg - GRADE_ORDER.index(g)) for g in n.grades)
    if dist >= 2:
        return 0
    cov = len(set(n.must_skills) & set(t["skills"])) / len(n.must_skills) if n.must_skills else 1.0
    if cov == 0:
        return 0
    within_budget = not (c.salary_from and n.salary_to and c.salary_from > n.salary_to * 1.1)
    above = tg > max(GRADE_ORDER.index(g) for g in n.grades)
    if dist == 1 and above and within_budget and cov >= 0.34:
        rel = 2  # «сильнее запроса» и укладывается в бюджет — работодателю подходит
    elif dist == 1 or cov < 0.34:
        rel = 1
    else:
        rel = 2
        # «сильный» кандидат категории: реально владеет большинством обязательных навыков и находится в верхней половине грейда
        lo = GRADES[t["grade"]]["cut"]
        hi = GRADES[GRADE_ORDER[tg + 1]]["cut"] if tg + 1 < len(GRADE_ORDER) else lo + 1.4
        if cov >= 0.66 and t["theta"] >= (lo + hi) / 2:
            rel = 3
    if c.salary_from and n.salary_to and c.salary_from > n.salary_to * 1.1:
        rel -= 1
    if n.work_formats and c.work_formats and not set(n.work_formats) & set(c.work_formats):
        rel -= 1
    return max(0, rel)


def ndcg(rels: list[int], ideal: list[int], k: int = K) -> float:
    dcg = sum((2**r - 1) / math.log2(i + 2) for i, r in enumerate(rels[:k]))
    idcg = sum((2**r - 1) / math.log2(i + 2) for i, r in enumerate(sorted(ideal, reverse=True)[:k]))
    return dcg / idcg if idcg > 0 else 0.0


def metrics(ranked_ids: list[int], rel: dict[int, int]) -> dict:
    rels = [rel.get(i, 0) for i in ranked_ids]
    relevant_total = sum(1 for v in rel.values() if v >= 2)
    first = next((i for i, r in enumerate(rels) if r >= 2), None)
    return {
        "p@5": sum(1 for r in rels[:5] if r >= 2) / 5,
        "p@10": sum(1 for r in rels[:K] if r >= 2) / K,
        "ndcg@10": ndcg(rels, list(rel.values())),
        "mrr": 1 / (first + 1) if first is not None else 0.0,
        "recall@30": (sum(1 for r in rels[:30] if r >= 2) / relevant_total) if relevant_total else 0.0,
        "noise@10": (sum(1 for r in rels[:K] if r == 0) / min(K, len(rels))) if rels else 0.0,
    }


def load_pool(db: Session):
    pool = list(db.scalars(select(CandidateProfile).options(selectinload(CandidateProfile.achievements))
                           .where(CandidateProfile.is_synthetic.is_(True), CandidateProfile.synthetic_truth.is_not(None))).all())
    # как в продакшене: в выдачу попадают только опубликованные профили кандидатов, которые рассматривают предложения
    pool = [c for c in pool if c.visible and c.search_status != "not_looking"]
    ts, pend = _task_skills(db), _pending(db)
    views = {c.user_id: to_view(c, ts, pend) for c in pool}
    by_id = {c.user_id: c for c in pool}
    resume = TfIdf({c.user_id: cand_text(c) for c in pool})
    return pool, views, by_id, resume


def evaluate(db: Session, now: datetime | None = None, need_seeds: tuple[int, ...] = (77, 78, 79, 80, 81)) -> dict:
    now = now or datetime.now(timezone.utc)
    pool, views, by_id, resume = load_pool(db)
    needs = [nv for sd in need_seeds for nv in make_needs(sd)]

    def ours(nv: NeedView, view_fn=lambda v: v, need_fn=lambda n: n, params=None):
        nv2 = need_fn(nv)
        sims = resume.query(nv2.description + " " + " ".join(nv2.must_skills + nv2.nice_skills))
        out = []
        for cid, v in views.items():
            vv = view_fn(v)
            r = score(vv, nv2, sims.get(cid, 0.0), now, params=params)
            if r:
                out.append((cid, r["score"], (by_id[cid].strength or 0), RELATION_ORDER[r["relation"]], r["grade_status"] != "confirmed"))
        out.sort(key=lambda x: (x[4], x[3], -x[1], -x[2]))  # как в продакшене (service.rank)
        return [x[0] for x in out]

    def keyword_baseline(nv: NeedView):
        # «классическая площадка»: фильтр по заявленным специализации и грейду, ранжирование по совпадению слов в резюме
        sims = resume.query(nv.description + " " + " ".join(nv.must_skills + nv.nice_skills))
        cands = [c for c in pool if c.specialization == nv.spec and c.declared_grade in nv.grades and c.visible
                 and c.search_status != "not_looking"]
        cands.sort(key=lambda c: -sims.get(c.user_id, 0.0))
        return [c.user_id for c in cands]

    def self_declared(v):
        # та же формула, но без верифицированного слоя: грейд — заявленный, тестовых доказательств нет
        c = by_id[v.id]
        return replace(v, grade=c.declared_grade, theta=None, topic_scores={}, verified_skills=[], category_percentile=None)

    def no_fsp(v):
        return replace(v, fsp_score=0.0, achievements=[])

    rankers = {
        "keyword_resume_baseline": keyword_baseline,
        "self_declared_category": lambda nv: ours(nv, view_fn=self_declared),
        "ours_full": lambda nv: ours(nv),
        "ours_expert_weights": lambda nv: ours(nv, params=EXPERT_PARAMS),
        "ours_without_fsp": lambda nv: ours(nv, view_fn=no_fsp, need_fn=lambda n: replace(n, fsp_weight=0.0)),
        "ours_without_adjacent": lambda nv: ours(nv, need_fn=lambda n: replace(n, include_adjacent=False)),
    }
    results: dict[str, list[dict]] = defaultdict(list)
    by_set: dict[str, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
    per_need = []
    set_of = {id(nv): i // (len(needs) // len(need_seeds)) for i, nv in enumerate(needs)}
    for nv in needs:
        rel = {c.user_id: relevance(nv, c) for c in pool}
        if sum(1 for v in rel.values() if v >= 2) < 3:
            continue
        row = {"need": f"{SPECIALIZATIONS[nv.spec]['short']} · {'/'.join(nv.grades)} · {', '.join(nv.must_skills)}",
               "relevant": sum(1 for v in rel.values() if v >= 2)}
        for name, fn in rankers.items():
            m = metrics(fn(nv), rel)
            results[name].append(m)
            by_set[name][set_of[id(nv)]].append(m)
            row[name] = round(m["ndcg@10"], 3)
        per_need.append(row)
    summary = {name: {k: round(statistics.mean(m[k] for m in ms), 3) for k in ms[0]} for name, ms in results.items()}
    # устойчивость: разброс nDCG@10 между независимыми наборами потребностей
    spread = {name: {"ndcg@10_sd": round(statistics.pstdev([statistics.mean(m["ndcg@10"] for m in v) for v in sets.values()]), 3),
                     "p@10_sd": round(statistics.pstdev([statistics.mean(m["p@10"] for m in v) for v in sets.values()]), 3)}
              for name, sets in by_set.items()}
    wins = sum(1 for a, b in zip(results["ours_full"], results["keyword_resume_baseline"]) if a["ndcg@10"] > b["ndcg@10"])
    # FSP: доля кандидатов с подтверждёнными достижениями в топ-10 при равной релевантности
    fsp_top = []
    for nv in needs[:20]:
        ids = rankers["ours_full"](nv)[:K]
        fsp_top.append(sum(1 for i in ids if views[i].fsp_score > 0) / K)
    base_share = sum(1 for v in views.values() if v.fsp_score > 0) / len(views)
    # стабильность выдачи к шуму в резюме: перестановка порядка навыков/набивка не должны менять топ
    return {
        "needs_evaluated": len(per_need),
        "pool_size": len(pool),
        "summary": summary,
        "spread_between_need_sets": spread,
        "need_sets": len(need_seeds),
        "ours_beats_keyword_share": round(wins / max(1, len(results["ours_full"])), 3),
        "per_need": per_need,
        "fsp_share_top10": round(statistics.mean(fsp_top), 3),
        "fsp_share_pool": round(base_share, 3),
        "weights_default": {k: round(v, 3) for k, v in weights(0.5).items()},
        "params": PARAMS,
        "params_tuned": PARAMS != EXPERT_PARAMS,
    }
