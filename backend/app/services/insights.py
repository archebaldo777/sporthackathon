"""Зарплатный радар и путь роста кандидата — по данным платформы его категории.

Обезличенность: распределение ожиданий показывается при ≥ MIN_VALUES значений, вилки вакансий и приглашений — только если
в группе ≥ MIN_COMPANIES разных компаний (по медиане нельзя восстановить вилку одной компании или зарплату одного человека);
значения округляются до тысячи. Все суммы — gross, в месяц.
"""
from __future__ import annotations

import statistics
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog.data import COMPETENCIES, GRADE_ORDER, MARKET_SALARY, SPECIALIZATIONS, grade_name
from app.models import CandidateProfile, HiringNeed, Invitation, Vacancy

MIN_VALUES = 5
MIN_COMPANIES = 3
GAP_SKILLS = 6


def _k(v: float | None) -> int | None:
    return None if v is None else int(round(v / 1000.0) * 1000)


def _quartiles(values: list[float]) -> dict | None:
    if len(values) < MIN_VALUES:
        return None
    q = statistics.quantiles(sorted(values), n=4)
    return {"p25": _k(q[0]), "p50": _k(q[1]), "p75": _k(q[2]), "n": len(values)}


def _company_median(pairs: list[tuple[int, float]]) -> dict | None:
    """pairs — (компания, середина вилки). Медиана только при достаточном числе компаний."""
    companies = {c for c, _ in pairs}
    if len(companies) < MIN_COMPANIES:
        return None
    return {"median": _k(statistics.median(v for _, v in pairs)), "n": len(pairs), "companies": len(companies)}


def salary_radar(db: Session, spec: str, grade: str, exclude_id: int | None = None) -> dict:
    grade_of = func.coalesce(CandidateProfile.grade, CandidateProfile.declared_grade)
    exp = [float(v) for v in db.scalars(select(CandidateProfile.salary_from).where(
        CandidateProfile.specialization == spec, grade_of == grade, CandidateProfile.salary_from.is_not(None),
        CandidateProfile.user_id != (exclude_id or 0))).all()]
    vac = [(e, (a + b) / 2) for e, a, b in db.execute(select(Vacancy.employer_id, Vacancy.salary_from, Vacancy.salary_to).where(
        Vacancy.specialization == spec, Vacancy.grade == grade, Vacancy.status == "published")).all()]
    offers = [(e, (a + b) / 2) for e, a, b in db.execute(
        select(Invitation.employer_id, Invitation.salary_from, Invitation.salary_to)
        .join(CandidateProfile, CandidateProfile.user_id == Invitation.candidate_id)
        .where(CandidateProfile.specialization == spec, grade_of == grade)).all()]
    return {"specialization": spec, "grade": grade, "market_median": MARKET_SALARY.get(spec, {}).get(grade),
            "expectations": _quartiles(exp), "vacancies": _company_median(vac), "offers": _company_median(offers)}


def _position(own: int | None, ref: int | None) -> str | None:
    if not own or not ref:
        return None
    if own < 0.9 * ref:
        return "below"
    if own > 1.1 * ref:
        return "above"
    return "in"


def candidate_insights(db: Session, cand: CandidateProfile) -> dict:
    spec, grade = cand.specialization, cand.grade or cand.declared_grade
    if not spec or not grade:
        return {"available": False, "reason": "Пройдите опрос и выберите грейд — радар строится по вашей категории"}
    now_radar = salary_radar(db, spec, grade, cand.user_id)
    idx = GRADE_ORDER.index(grade)
    nxt = GRADE_ORDER[idx + 1] if idx + 1 < len(GRADE_ORDER) else None
    next_radar = salary_radar(db, spec, nxt, cand.user_id) if nxt else None
    ref = (now_radar["offers"] or now_radar["vacancies"] or {}).get("median") or now_radar["market_median"]

    # спрос на навыки: вакансии и потребности следующего грейда (для senior — своего)
    target = nxt or grade
    postings: list[list[str]] = []
    for must, nice in db.execute(select(Vacancy.must_skills, Vacancy.nice_skills).where(
            Vacancy.specialization == spec, Vacancy.grade == target, Vacancy.status == "published")).all():
        postings.append(list(dict.fromkeys((must or []) + (nice or []))))
    for must, nice, grades in db.execute(select(HiringNeed.must_skills, HiringNeed.nice_skills, HiringNeed.grades).where(
            HiringNeed.specialization == spec, HiringNeed.status == "active")).all():
        if target in (grades or []):
            postings.append(list(dict.fromkeys((must or []) + (nice or []))))
    demand = Counter(s for p in postings for s in p)
    have_verified = {v["skill"] for v in (cand.verified_skills or [])}
    have = have_verified | set(cand.skills or [])
    gaps = [{"skill": s, "share": round(n / len(postings), 2)} for s, n in demand.most_common() if s not in have][:GAP_SKILLS]
    strengths = [{"skill": s, "share": round(n / len(postings), 2), "verified": s in have_verified}
                 for s, n in demand.most_common() if s in have][:GAP_SKILLS]

    topics = cand.topic_scores or {}
    weakest = min(topics.items(), key=lambda kv: kv[1].get("score", 1))[0] if topics else None
    steps = []
    if not cand.grade:
        steps.append(f"Подтвердите грейд {grade_name(grade)} тестом — без этого вы показываетесь ниже подтверждённых кандидатов")
    elif nxt:
        steps.append(f"Когда будете готовы — тест на {grade_name(nxt)}: смена грейда раз в 90 дней, после уверенного результата — сразу")
    if gaps:
        steps.append(f"Чаще всего на уровне {grade_name(target)} просят: " + ", ".join(g["skill"] for g in gaps[:3]))
    if weakest:
        steps.append(f"Самая слабая тема теста — «{topics[weakest].get('name') or COMPETENCIES.get(weakest, {}).get('name', weakest)}»: "
                     "её задания стоит повторить перед следующей попыткой")
    if not cand.fsp_id:
        steps.append("Свяжите ФСП ID: подтверждённые результаты соревнований поднимают вас внутри категории")
    elif not any(a.place and a.place <= 3 for a in cand.achievements):
        steps.append("Призовое место на соревновании ФСП весит больше любого числа участий — выберите ближайший турнир по своей дисциплине")
    return {
        "available": True,
        "category": f"{SPECIALIZATIONS[spec]['short']} · {grade_name(grade)}",
        "grade_confirmed": cand.grade is not None,
        "own_expectation": cand.salary_from,
        "position": _position(cand.salary_from, ref),
        "reference_median": ref,
        "now": now_radar,
        "next_grade": nxt,
        "next": next_radar,
        "demand": {"grade": target, "postings": len(postings), "gaps": gaps, "strengths": strengths},
        "weakest_topic": weakest and {"code": weakest, "name": topics[weakest].get("name"), "score": topics[weakest].get("score")},
        "steps": steps,
        "privacy": {"min_values": MIN_VALUES, "min_companies": MIN_COMPANIES},
    }
