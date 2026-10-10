"""Оценка механики подбора на ВНЕШНЕМ размеченном наборе пар «вакансия — кандидат» (например, на наборе жюри).

Формат входа — JSON (UTF-8), пример: docs/examples/eval_pairs_example.json
{
  "vacancies":  [{"id": "v1", "text": "свободный текст вакансии",
                  // необязательные поля, имеют приоритет над разобранными из текста:
                  "specialization": "backend", "grades": ["middle"], "must_skills": ["Python"], "nice_skills": [],
                  "salary_from": 200000, "salary_to": 280000, "work_formats": ["remote"], "city": "Москва"}],
  "candidates": [{"id": "c1", "resume_text": "текст резюме",
                  "specialization": "backend", "grade": "middle", "skills": ["Python", "SQL"],
                  "salary_from": 220000, "salary_to": 260000, "work_formats": ["remote"], "city": "Казань",
                  "search_status": "active",
                  // результат адаптивного теста платформы, если кандидат его прошёл:
                  "test": {"grade": "middle", "theta": 0.62, "verified_skills": ["Python", "SQL"]},
                  // достижения ФСП, если есть:
                  "fsp": [{"discipline": "product", "level": "national", "place": 2, "participants": 120, "date": "2025-11-20"}]}],
  "labels":     [{"vacancy": "v1", "candidate": "c1", "relevance": 2}]      // 0..3 или 0/1
}
Специализация и грейд принимают коды (backend, middle) и обычные названия («Бэкенд», «мидл», «Senior»).
Кандидат без теста ранжируется по заявленной категории, без истории ФСП — с fsp_score = 0 (не исключается).

Два протокола:
  • pool  — система ищет по всем кандидатам набора, неразмеченные пары считаются нерелевантными
            (так подборка работает в продукте);
  • pairs — для каждой вакансии ранжируются только размеченные для неё кандидаты (классический протокол «пар»).
Метрики: Precision@10 (доля релевантных в топ-10; при меньшем числе кандидатов — в топ-k), nDCG@10, MRR, Recall@30.
Релевантным считается rel ≥ 2 для шкалы 0–3 и rel ≥ 1 для бинарной разметки (меняется параметром threshold).
Сравнение: наш ранжировщик против «классической площадки» — фильтр по заявленным специализации и грейду
и сортировка по текстовой близости резюме (TF-IDF).

Запуск:  python -m app.validation.external_eval data.json [--out report.json] [--threshold 2]
         python -m app.validation.external_eval --example docs/examples/eval_pairs_example.json   # собрать пример
Тот же расчёт доступен в интерфейсе (страница «Валидация») и в API: POST /api/v1/validation/external-eval.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.catalog.data import FSP_DISCIPLINES, FSP_LEVELS, GRADE_ORDER, SPECIALIZATIONS
from app.catalog.skills import normalize_list
from app.fsp.scoring import fsp_score, is_prize, result_title, result_weight
from app.matching.scoring import Achievement, CandView, NeedView, score
from app.matching.service import RELATION_ORDER
from app.matching.text import TfIdf
from app.nlp.need_parser import parse_need
from app.nlp.resume_parser import classify_specialization, parse_resume

K = 10
LIMITS = {"vacancies": 300, "candidates": 3000, "labels": 100_000}
GRADE_ALIASES = {
    "intern": "intern", "стажёр": "intern", "стажер": "intern", "trainee": "intern", "стажировка": "intern",
    "junior": "junior", "джун": "junior", "джуниор": "junior", "младший": "junior", "jun": "junior",
    "middle": "middle", "мидл": "middle", "middle+": "middle", "mid": "middle",
    "senior": "senior", "сеньор": "senior", "синьор": "senior", "старший": "senior", "ведущий": "senior", "lead": "senior", "тимлид": "senior",
}
FORMAT_ALIASES = {"office": "office", "офис": "office", "hybrid": "hybrid", "гибрид": "hybrid", "remote": "remote", "удалённо": "remote",
                  "удаленно": "remote", "удалёнка": "remote", "удаленка": "remote"}


class EvalError(ValueError):
    """Ошибка формата входного набора — текст понятен пользователю."""


# ---------------------------------------------------------------- нормализация полей
def norm_grade(v) -> str | None:
    if not v:
        return None
    return GRADE_ALIASES.get(str(v).strip().lower())


def norm_spec(v) -> str | None:
    if not v:
        return None
    s = str(v).strip().lower()
    for code, info in SPECIALIZATIONS.items():
        if s in (code, info["short"].lower(), info["name"].lower()):
            return code
    best, conf, _ = classify_specialization([], s)
    return best if conf > 0 else None


def norm_formats(v) -> list[str]:
    return sorted({FORMAT_ALIASES[x.strip().lower()] for x in (v or []) if isinstance(x, str) and x.strip().lower() in FORMAT_ALIASES})


def _int(v) -> int | None:
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _date(v) -> date:
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        try:
            return date(int(v), 6, 1)
        except (TypeError, ValueError):
            return date.today()


def build_need(raw: dict) -> NeedView:
    text = str(raw.get("text") or raw.get("description") or "")
    p = parse_need(text) if text.strip() else {}
    spec = norm_spec(raw.get("specialization")) or p.get("specialization")
    if not spec:
        raise EvalError(f"Вакансия {raw.get('id')!r}: не удалось определить специализацию — укажите поле specialization или текст")
    grades = [g for g in (norm_grade(x) for x in (raw.get("grades") or ([raw["grade"]] if raw.get("grade") else []))) if g]
    grades = sorted(set(grades or p.get("grades") or ["middle"]), key=GRADE_ORDER.index)
    must = normalize_list(raw["must_skills"]) if raw.get("must_skills") is not None else p.get("must_skills", [])
    nice = normalize_list(raw["nice_skills"]) if raw.get("nice_skills") is not None else p.get("nice_skills", [])
    return NeedView(spec=spec, grades=grades, must_skills=must, nice_skills=[s for s in nice if s not in must],
                    salary_from=_int(raw.get("salary_from")) or p.get("salary_from") or 0,
                    salary_to=_int(raw.get("salary_to")) or p.get("salary_to") or 0,
                    work_formats=norm_formats(raw.get("work_formats")) or p.get("work_formats", []),
                    city=raw.get("city") or p.get("city"), fsp_weight=float(raw.get("fsp_weight", 0.5)),
                    domains=p.get("domains", []), description=text or " ".join(must + nice))


def build_candidate(idx: int, raw: dict, today: date) -> tuple[CandView, str | None, str]:
    """Возвращает (представление для ранжирования, заявленный грейд, текст резюме для текстовой близости)."""
    text = str(raw.get("resume_text") or raw.get("text") or "")
    p = parse_resume(text) if text.strip() else {}
    val = lambda k: (p.get(k) or {}).get("value")  # noqa: E731
    skills = normalize_list(raw["skills"]) if raw.get("skills") else (val("skills") or [])
    spec = norm_spec(raw.get("specialization")) or val("specialization")
    declared = norm_grade(raw.get("grade")) or val("declared_grade")
    test = raw.get("test") or {}
    tested_grade = norm_grade(test.get("grade"))
    verified = normalize_list(test.get("verified_skills") or []) if tested_grade else []
    achievements, fsp_items = [], []
    for a in raw.get("fsp") or []:
        disc = a.get("discipline") if a.get("discipline") in FSP_DISCIPLINES else "product"
        lvl = a.get("level") if a.get("level") in FSP_LEVELS else "regional"
        d = _date(a.get("date") or a.get("year"))
        place = _int(a.get("place"))
        fsp_items.append(SimpleNamespace(level=lvl, discipline=disc, place=place, participants=_int(a.get("participants")),
                                         percentile=a.get("percentile"), event_date=d))
        achievements.append(Achievement(str(a.get("event") or a.get("event_name") or "Соревнование ФСП"), disc, lvl, place,
                                        result_title(place, a.get("percentile")), d.year, normalize_list(a.get("stack") or []),
                                        weight=result_weight(place, _int(a.get("participants")), a.get("percentile"), d, today),
                                        prize=is_prize(place, _int(a.get("participants")), a.get("percentile"))))
    langs = [s for s in skills if s in (SPECIALIZATIONS.get(spec or "", {}).get("langs") or [])]
    view = CandView(
        id=idx, spec=spec, grade=tested_grade or declared, theta=test.get("theta") if tested_grade else None,
        lang=test.get("lang") or (langs[0] if langs else None), framework=test.get("framework"),
        topic_scores=test.get("topic_scores") or {}, verified_skills=verified, declared_skills=skills,
        fsp_score=fsp_score(fsp_items, today, spec) if fsp_items else 0.0, achievements=achievements,
        salary_from=_int(raw.get("salary_from")), salary_to=_int(raw.get("salary_to")),
        work_formats=norm_formats(raw.get("work_formats")), city=raw.get("city") or val("city"), relocation=bool(raw.get("relocation")),
        domains=val("domains") or [], search_status=raw.get("search_status") or "active",
        text=text or " ".join(skills),
    )
    return view, declared, view.text


# ---------------------------------------------------------------- метрики
def _metrics(ranked: list[str], rel: dict[str, int], thr: int, pool_size: int) -> dict:
    rels = [rel.get(i, 0) for i in ranked]
    k = max(1, min(K, pool_size))
    gains = [2 ** r - 1 for r in rels[:K]]
    ideal = sorted((2 ** r - 1 for r in rel.values()), reverse=True)[:K]
    dcg = sum(g / math.log2(i + 2) for i, g in enumerate(gains))
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    relevant_total = sum(1 for v in rel.values() if v >= thr)
    first = next((i for i, r in enumerate(rels) if r >= thr), None)
    return {
        "p@10": sum(1 for r in rels[:k] if r >= thr) / k,
        "ndcg@10": dcg / idcg if idcg > 0 else 0.0,
        "mrr": 1 / (first + 1) if first is not None else 0.0,
        "recall@30": sum(1 for r in rels[:30] if r >= thr) / relevant_total if relevant_total else 0.0,
    }


def _mean(rows: list[dict]) -> dict:
    return {k: round(statistics.mean(r[k] for r in rows), 3) for k in rows[0]} if rows else {}


# ---------------------------------------------------------------- оценка
def evaluate_external(data: dict, threshold: int | None = None, now: datetime | None = None) -> dict:
    if not isinstance(data, dict):
        raise EvalError("Ожидается JSON-объект с ключами vacancies, candidates, labels")
    vac_raw, cand_raw, lab_raw = data.get("vacancies") or [], data.get("candidates") or [], data.get("labels") or []
    for key, items in (("vacancies", vac_raw), ("candidates", cand_raw), ("labels", lab_raw)):
        if not isinstance(items, list) or not items:
            raise EvalError(f"Поле {key} должно быть непустым списком")
        if len(items) > LIMITS[key]:
            raise EvalError(f"Слишком большой набор: {key} — не более {LIMITS[key]}")
    now = now or datetime.now(timezone.utc)
    today = now.date()

    vac_ids = [str(v.get("id")) for v in vac_raw]
    cand_ids = [str(c.get("id")) for c in cand_raw]
    if len(set(vac_ids)) != len(vac_ids) or len(set(cand_ids)) != len(cand_ids):
        raise EvalError("Идентификаторы вакансий и кандидатов должны быть уникальными")
    needs = {vid: build_need(v) for vid, v in zip(vac_ids, vac_raw)}
    views, declared, texts = {}, {}, {}
    for i, (cid, c) in enumerate(zip(cand_ids, cand_raw)):
        views[cid], declared[cid], texts[cid] = build_candidate(i, c, today)

    labels: dict[str, dict[str, int]] = {vid: {} for vid in vac_ids}
    for lb in lab_raw:
        v, c = str(lb.get("vacancy")), str(lb.get("candidate"))
        if v not in labels or c not in views:
            raise EvalError(f"Разметка ссылается на неизвестную пару: вакансия {v!r}, кандидат {c!r}")
        try:
            labels[v][c] = max(0, min(3, int(lb.get("relevance", 0))))
        except (TypeError, ValueError):
            raise EvalError(f"Некорректная оценка релевантности у пары {v!r}–{c!r}") from None
    binary = all(x in (0, 1) for d in labels.values() for x in d.values())
    thr = threshold if threshold is not None else (1 if binary else 2)

    tfidf = TfIdf(dict(enumerate(texts[c] for c in cand_ids)))
    pos = {c: i for i, c in enumerate(cand_ids)}

    def ours(nv: NeedView, pool: list[str]) -> list[tuple[str, dict]]:
        sims = tfidf.query(nv.description + " " + " ".join(nv.must_skills + nv.nice_skills))
        out = [(c, r) for c in pool if (r := score(views[c], nv, sims.get(pos[c], 0.0), now))]
        out.sort(key=lambda x: (RELATION_ORDER[x[1]["relation"]], -x[1]["score"]))
        return out

    def keyword(nv: NeedView, pool: list[str]) -> list[str]:
        sims = tfidf.query(nv.description + " " + " ".join(nv.must_skills + nv.nice_skills))
        ok = [c for c in pool if views[c].spec == nv.spec and (declared[c] or views[c].grade) in nv.grades]
        return sorted(ok, key=lambda c: -sims.get(pos[c], 0.0))

    protocols: dict[str, dict[str, list[dict]]] = {"pool": {}, "pairs": {}}
    ceiling: dict[str, list[float]] = {"pool": [], "pairs": []}  # максимально достижимый P@10 при данной разметке
    per_vacancy = []
    for vid in vac_ids:
        rel, nv = labels[vid], needs[vid]
        if not any(x >= thr for x in rel.values()):
            continue  # без единого релевантного кандидата вакансия ничего не говорит о качестве ранжирования
        row = {"vacancy": vid, "parsed": {"specialization": nv.spec, "grades": nv.grades, "must_skills": nv.must_skills,
                                          "salary": [nv.salary_from, nv.salary_to]},
               "labeled": len(rel), "relevant": sum(1 for x in rel.values() if x >= thr)}
        for proto, pool in (("pool", cand_ids), ("pairs", list(rel))):
            ranked = ours(nv, pool)
            ids = [c for c, _ in ranked]
            m_ours, m_kw = _metrics(ids, rel, thr, len(pool)), _metrics(keyword(nv, pool), rel, thr, len(pool))
            ceiling[proto].append(min(row["relevant"], max(1, min(K, len(pool)))) / max(1, min(K, len(pool))))
            protocols[proto].setdefault("ours", []).append(m_ours)
            protocols[proto].setdefault("keyword_baseline", []).append(m_kw)
            row[proto] = {"ours": {k: round(v, 3) for k, v in m_ours.items()}, "keyword_baseline": {k: round(v, 3) for k, v in m_kw.items()}}
            if proto == "pool":
                row["top"] = [{"candidate": c, "score": r["score"], "relation": r["relation"], "label": rel.get(c),
                               "reasons": r["reasons"][:3]} for c, r in ranked[:K]]
        per_vacancy.append(row)
    if not per_vacancy:
        raise EvalError("Ни у одной вакансии нет релевантных кандидатов в разметке — считать нечего")

    summary = {proto: {name: _mean(ms) for name, ms in methods.items()} for proto, methods in protocols.items()}
    for proto in summary:
        summary[proto]["ideal"] = {"p@10": round(statistics.mean(ceiling[proto]), 3), "ndcg@10": 1.0, "mrr": 1.0, "recall@30": 1.0}
    wins = sum(1 for r in per_vacancy if r["pool"]["ours"]["ndcg@10"] > r["pool"]["keyword_baseline"]["ndcg@10"])
    ties = sum(1 for r in per_vacancy if r["pool"]["ours"]["ndcg@10"] == r["pool"]["keyword_baseline"]["ndcg@10"])
    n_labels = sum(len(d) for d in labels.values())
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "vacancies": len(vac_ids), "vacancies_evaluated": len(per_vacancy), "candidates": len(cand_ids), "labels": n_labels,
        "scale": "binary" if binary else "graded_0_3", "threshold": thr,
        "base_rate": round(sum(1 for d in labels.values() for x in d.values() if x >= thr) / max(1, n_labels), 3),
        "candidates_with_test": sum(1 for c in cand_raw if norm_grade((c.get("test") or {}).get("grade"))),
        "candidates_with_fsp": sum(1 for v in views.values() if v.fsp_score > 0),
        "candidates_uncategorized": sum(1 for v in views.values() if not v.spec or not v.grade),
        "summary": summary,
        "ours_beats_keyword": {"wins": wins, "ties": ties, "losses": len(per_vacancy) - wins - ties},
        "per_vacancy": per_vacancy,
    }


# ---------------------------------------------------------------- пример набора из синтетической популяции
def build_example(db, n_vacancies: int = 48, n_candidates: int = 800, seed: int = 5) -> dict:
    """Пример набора в формате входа: тексты резюме — из профилей синтетических кандидатов,
    разметка — по их скрытой истине (как в основной процедуре валидации, см. matching_eval.relevance)."""
    import random

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models import CandidateProfile
    from app.validation.matching_eval import make_needs, relevance

    rng = random.Random(seed)
    pool = list(db.scalars(select(CandidateProfile).options(selectinload(CandidateProfile.achievements))
                           .where(CandidateProfile.is_synthetic.is_(True), CandidateProfile.synthetic_truth.is_not(None))
                           .order_by(CandidateProfile.user_id)).all())
    specs = list(SPECIALIZATIONS)
    pool = [c for c in pool if c.specialization in specs and c.visible and c.search_status != "not_looking"]
    cands = rng.sample(pool, min(n_candidates, len(pool)))
    needs = [n for n in make_needs(seed) if n.spec in specs]
    needs = rng.sample(needs, min(n_vacancies, len(needs)))
    out: dict = {"vacancies": [], "candidates": [], "labels": []}
    fmt = {"office": "офис", "hybrid": "гибрид", "remote": "удалённо"}
    for i, n in enumerate(needs, 1):
        grades = " / ".join(g.capitalize() for g in n.grades)
        text = (f"{SPECIALIZATIONS[n.spec]['name']} ({grades}). Обязательно: {', '.join(n.must_skills)}. "
                f"Будет плюсом: {', '.join(n.nice_skills) or '—'}.\n\nЗарплата {n.salary_from // 1000}–{n.salary_to // 1000} тыс. ₽"
                + (f", формат: {', '.join(fmt[f] for f in n.work_formats)}." if n.work_formats else "."))
        out["vacancies"].append({"id": f"v{i}", "text": text})
    for j, c in enumerate(cands, 1):
        exp = "\n".join(f"{e.get('title', '')}. {e.get('description', '')}" for e in (c.experience or []))
        resume = "\n".join(filter(None, [c.headline, f"Навыки: {', '.join(c.skills or [])}", c.about, exp]))
        item = {"id": f"c{j}", "resume_text": resume, "grade": c.declared_grade, "salary_from": c.salary_from, "salary_to": c.salary_to,
                "work_formats": c.work_formats or [], "city": c.city, "search_status": c.search_status}
        if c.grade and rng.random() < 0.75:
            item["test"] = {"grade": c.grade, "theta": round(c.theta or 0, 2), "verified_skills": [v["skill"] for v in (c.verified_skills or [])]}
        if c.achievements:
            item["fsp"] = [{"event": a.event_name, "discipline": a.discipline, "level": a.level, "place": a.place, "participants": a.participants,
                            "percentile": a.percentile, "date": a.event_date.isoformat(), "stack": a.stack or []} for a in c.achievements]
        out["candidates"].append(item)
        for i, n in enumerate(needs, 1):
            r = relevance(n, c)
            if r > 0 or rng.random() < 0.15:  # все релевантные пары и часть нерелевантных — как в реальной разметке
                out["labels"].append({"vacancy": f"v{i}", "candidate": f"c{j}", "relevance": r})
    return out


def export_example(path: str) -> dict:
    from app.core.db import SessionLocal

    with SessionLocal() as db:
        out = build_example(db)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return out


def _print(r: dict) -> None:
    print(f"Вакансий: {r['vacancies']} (оценено {r['vacancies_evaluated']}), кандидатов: {r['candidates']}, пар в разметке: {r['labels']}, "
          f"шкала: {r['scale']}, порог релевантности: {r['threshold']}, доля релевантных пар: {r['base_rate']:.0%}")
    print(f"С тестом платформы: {r['candidates_with_test']}, с достижениями ФСП: {r['candidates_with_fsp']}, "
          f"без категории (не попадут в подборку): {r['candidates_uncategorized']}")
    names = {"ours": "Драфт", "keyword_baseline": "Поиск по резюме", "ideal": "Идеал (потолок)"}
    for proto, title in (("pool", "по всей базе"), ("pairs", "только размеченные пары")):
        print(f"\nПротокол «{title}»:   P@10   nDCG@10   MRR   R@30")
        for m, v in r["summary"][proto].items():
            print(f"  {names[m]:<18} {v['p@10']:.3f}   {v['ndcg@10']:.3f}   {v['mrr']:.3f}  {v['recall@30']:.3f}")
    w = r["ours_beats_keyword"]
    print(f"\nnDCG@10 лучше базовой линии: {w['wins']} из {r['vacancies_evaluated']} вакансий (равно: {w['ties']})")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Оценка подбора на размеченном наборе пар «вакансия — кандидат»")
    ap.add_argument("path", nargs="?", help="JSON с vacancies, candidates, labels")
    ap.add_argument("--out", help="куда сохранить полный отчёт (JSON)")
    ap.add_argument("--threshold", type=int, help="минимальная оценка релевантной пары (по умолчанию 2 для 0–3, 1 для 0/1)")
    ap.add_argument("--example", help="собрать пример набора из синтетической популяции в указанный файл")
    a = ap.parse_args(argv)
    if a.example:
        ex = export_example(a.example)
        print(f"Пример сохранён: {a.example} ({len(ex['vacancies'])} вакансий, {len(ex['candidates'])} кандидатов, {len(ex['labels'])} пар)")
        if not a.path:
            a.path = a.example
    if not a.path:
        ap.error("укажите путь к набору")
    with open(a.path, encoding="utf-8") as f:
        data = json.load(f)
    try:
        r = evaluate_external(data, a.threshold)
    except EvalError as e:
        sys.exit(f"Ошибка набора: {e}")
    _print(r)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=1)
        print(f"Полный отчёт: {a.out}")


if __name__ == "__main__":
    main()
