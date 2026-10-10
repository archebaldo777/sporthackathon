"""Проверка разбора резюме и категоризации по стеку и специализации на размеченном вручную наборе.

Набор (app/validation/data/resumes_labeled.json) написан независимо от генератора синтетических данных: разные стили
(hh.ru, LinkedIn, свободный текст), русский и английский, сленг («реакт», «k8s», «постгрес»), разные форматы контактов
и дат. Для каждого резюме размечены ФИО, контакты, город, специализация, стаж и навыки онтологии платформы.

Метрики: точность по полям; для навыков — micro-precision / recall / F1 (на уровне отдельных навыков);
стаж считается верным при ошибке не больше 0.5 года.
Запуск: python -m app.validation.resume_eval
"""
from __future__ import annotations

import json
import re
import statistics
from datetime import date
from pathlib import Path

from app.nlp.resume_parser import parse_resume

DATA = Path(__file__).resolve().parent / "data" / "resumes_labeled.json"
HOLDOUT = Path(__file__).resolve().parent / "data" / "resumes_labeled_test.json"
FIELDS = ["name", "email", "phone", "telegram", "github", "city", "specialization", "experience_years"]


def _norm(v) -> str | None:
    return None if v in (None, "") else str(v).strip().lower().replace("ё", "е")


def _pred(p: dict) -> dict:
    val = lambda k: p[k]["value"]  # noqa: E731
    phone = val("phone")
    return {
        "name": val("full_name"),
        "email": val("email"),
        "phone": re.sub(r"\D", "", phone)[-10:] if phone else None,
        "telegram": (val("telegram") or "").lstrip("@") or None,
        "github": (val("github") or "").rstrip("/").split("/")[-1] or None,
        "city": val("city"),
        "specialization": val("specialization"),
        "experience_years": val("experience_years"),
        "skills": val("skills") or [],
    }


def evaluate(path: Path = DATA) -> dict:
    data = json.loads(path.read_text())
    today = date.fromisoformat(data["reference_date"])
    correct = {f: 0 for f in FIELDS}
    tp = fp = fn = 0
    exp_err = []
    rows = []
    for it in data["items"]:
        g, p = it["gold"], _pred(parse_resume(it["text"], today))
        ok = {}
        for f in FIELDS:
            if f == "experience_years":
                gv, pv = g[f], p[f]
                ok[f] = (gv is None and not pv) or (gv is not None and pv is not None and abs(gv - pv) <= 0.5)
                if gv is not None and pv is not None:
                    exp_err.append(abs(gv - pv))
            else:
                ok[f] = _norm(g[f]) == _norm(p[f])
            correct[f] += ok[f]
        gs, ps = set(g["skills"]), set(p["skills"])
        tp += len(gs & ps)
        fp += len(ps - gs)
        fn += len(gs - ps)
        rows.append({"id": it["id"], "errors": [f for f in FIELDS if not ok[f]], "missed_skills": sorted(gs - ps),
                     "extra_skills": sorted(ps - gs), "pred_spec": p["specialization"], "gold_spec": g["specialization"]})
    n = len(data["items"])
    prec, rec = tp / max(1, tp + fp), tp / max(1, tp + fn)
    return {
        "resumes": n,
        "skills_labeled": tp + fn,
        "field_accuracy": {f: round(correct[f] / n, 3) for f in FIELDS},
        "skills": {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(2 * prec * rec / max(1e-9, prec + rec), 3)},
        "experience_mae": round(statistics.mean(exp_err), 2) if exp_err else None,
        "per_resume": rows,
    }


def evaluate_all() -> dict:
    """Основной набор (по нему дорабатывался парсер) и отложенный; для отложенного — также замер до правок."""
    dev, test = evaluate(DATA), evaluate(HOLDOUT)
    strip = lambda r: {k: v for k, v in r.items() if k != "per_resume"} | {  # noqa: E731
        "errors": [x for x in r["per_resume"] if x["errors"] or x["missed_skills"] or x["extra_skills"]]}
    return {"dev": strip(dev), "holdout": strip(test), "holdout_first_run": json.loads(HOLDOUT.read_text()).get("first_run")}


if __name__ == "__main__":
    r = evaluate()
    print(json.dumps({k: v for k, v in r.items() if k != "per_resume"}, ensure_ascii=False, indent=1))
    for row in r["per_resume"]:
        if row["errors"] or row["missed_skills"] or row["extra_skills"]:
            print(row["id"], "ошибки:", row["errors"], "| пропущено:", row["missed_skills"], "| лишнее:", row["extra_skills"],
                  f"| спец. {row['pred_spec']} vs {row['gold_spec']}" if "specialization" in row["errors"] else "")
