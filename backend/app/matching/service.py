"""Сервис подбора: формирование подборки по потребности, рекомендации категорий, поиск по банку кандидатов,
карточки кандидатов с учётом приватности и правил раскрытия контактов."""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.catalog.data import (
    DISCIPLINE_FIT_NAMES,
    DOMAINS,
    FSP_DISCIPLINES,
    FSP_LEVELS,
    GRADE_ORDER,
    GRADES,
    MARKET_SALARY,
    SPECIALIZATIONS,
    WORK_FORMATS,
    category_label,
    discipline_fit,
    grade_name,
)
from app.core.cache import TTLCache
from app.core.db import utcnow
from app.fsp.scoring import fsp_score, is_prize, result_weight
from app.matching.scoring import RELATED_SPECS, Achievement, CandView, NeedView, score
from app.matching.strength import strength_for, strength_parts
from app.matching.text import TfIdf
from app.services.categories import all_categories
from app.models import Application, CandidateCategory, CandidateProfile, EmployerTask, HiringNeed, Invitation, ShortlistEntry, TaskAssignment, Vacancy

SHORTLIST_SIZE = 60
_cards = TTLCache(maxsize=4096, ttl=120)
_queries = TTLCache(maxsize=512, ttl=60)


def pool_version(db: Session) -> tuple:
    """Версия банка кандидатов: меняется при любом изменении профиля — ключ кэша поиска и карты категорий."""
    return tuple(db.execute(select(func.max(CandidateProfile.updated_at), func.count()).select_from(CandidateProfile)).one())
RELATION_ORDER = {"target": 0, "adjacent_grade": 1, "related_spec": 2}


# ---------------------------------------------------------------- построение представлений
def _task_skills(db: Session, ids: list[int] | None = None) -> dict[int, list[str]]:
    q = (select(TaskAssignment.candidate_id, EmployerTask.skills)
         .join(EmployerTask, EmployerTask.id == TaskAssignment.task_id)
         .where(TaskAssignment.status == "reviewed", TaskAssignment.score >= 4))
    if ids is not None:
        q = q.where(TaskAssignment.candidate_id.in_(ids))
    out: dict[int, list[str]] = defaultdict(list)
    for cid, skills in db.execute(q).all():
        for s in skills or []:
            if s not in out[cid]:
                out[cid].append(s)
    return out


def _pending(db: Session) -> dict[int, int]:
    rows = db.execute(select(Invitation.candidate_id, func.count()).where(Invitation.status.in_(["sent", "viewed"]))
                      .group_by(Invitation.candidate_id)).all()
    return {cid: n for cid, n in rows}


def cand_text(c: CandidateProfile) -> str:
    exp = " ".join(f"{e.get('title', '')} {e.get('description', '')}" for e in (c.experience or []))
    return " ".join(filter(None, [c.headline, c.about, exp, " ".join(c.skills or [])]))


def all_verified(c: CandidateProfile) -> list[str]:
    """Навыки, подтверждённые тестом в любой из категорий кандидата (подтверждённый навык — факт о человеке, а не о категории)."""
    out = [v["skill"] for v in (c.verified_skills or [])]
    for x in c.extra_categories:
        out += [v["skill"] for v in (x.verified_skills or []) if v["skill"] not in out]
    return list(dict.fromkeys(out))


def to_view(c: CandidateProfile, task_skills: dict[int, list[str]] | None = None, pending: dict[int, int] | None = None,
            cat: CandidateCategory | None = None) -> CandView:
    """Представление кандидата для формулы подбора; cat — дополнительная категория (иначе основная из профиля)."""
    today = date.today()
    src = cat or c
    fsp = c.fsp_score or 0.0
    strength, percentile = c.strength or 0.0, c.category_percentile
    if cat is not None:
        fsp = fsp_score(c.achievements, today, cat.specialization)
        strength, percentile = strength_for(c, cat.theta, cat.grade, fsp), None
    return CandView(
        id=c.user_id, spec=src.specialization, grade=src.grade or src.declared_grade, theta=src.theta, grade_confirmed=src.grade is not None,
        lang=src.primary_lang, framework=src.framework,
        topic_scores={**(c.topic_scores or {}), **(cat.topic_scores or {})} if cat is not None else (c.topic_scores or {}),
        verified_skills=all_verified(c), declared_skills=list(c.skills or []),
        task_skills=(task_skills or {}).get(c.user_id, []), fsp_score=fsp,
        achievements=[Achievement(a.event_name, a.discipline, a.level, a.place, a.result_title, a.event_date.year, a.stack or [],
                                  weight=result_weight(a.place, a.participants, a.percentile, a.event_date, today),
                                  prize=is_prize(a.place, a.participants, a.percentile))
                      for a in c.achievements],
        salary_from=c.salary_from, salary_to=c.salary_to, work_formats=c.work_formats or [], city=c.city, relocation=c.relocation,
        domains=c.domains or [], search_status=c.search_status, tasks_done=c.tasks_done or 0, task_score=c.task_score,
        last_activity_at=c.last_activity_at, strength=strength, category_percentile=percentile,
        pending_invites=(pending or {}).get(c.user_id, 0), text=cand_text(c),
    )


def category_sources(c: CandidateProfile, specs: list[str] | None = None) -> list[CandidateCategory | None]:
    """Категории кандидата, участвующие в выдаче: None — основная (из профиля), иначе дополнительная."""
    out: list[CandidateCategory | None] = []
    if c.specialization and (c.grade or c.declared_grade) and (specs is None or c.specialization in specs):
        out.append(None)
    out += [x for x in c.extra_categories if specs is None or x.specialization in specs]
    return out


def category_info(c: CandidateProfile, cat: CandidateCategory | None) -> dict:
    """Категория, по которой кандидат попал в выдачу (для объяснения и карточки)."""
    src = cat or c
    grade = src.grade or src.declared_grade
    return {"specialization": src.specialization, "grade": grade, "confirmed": src.grade is not None, "additional": cat is not None,
            "label": category_label(src.specialization, grade), "theta": src.theta}


def _order_key(res: dict, strength: float = 0.0) -> tuple:
    # подтверждённые — раньше неподтверждённых, затем целевая категория, смежные; внутри — по оценке
    return (res["grade_status"] != "confirmed", RELATION_ORDER[res["relation"]], -res["score"], -strength)


def best_score(c: CandidateProfile, nv: NeedView, task_skills: dict[int, list[str]] | None = None, pending: dict[int, int] | None = None,
               sim: float = 0.0, now: datetime | None = None, with_parts: bool = False) -> dict | None:
    """Оценка кандидата по потребности в лучшей из его категорий (основной или дополнительной)."""
    best = None
    for cat in category_sources(c):
        v = to_view(c, task_skills, pending, cat)
        r = score(v, nv, sim, now, with_parts=with_parts)
        if r and (best is None or _order_key(r, v.strength) < _order_key(best[0], best[1])):
            r["category"] = category_info(c, cat)
            best = (r, v.strength)
    return best[0] if best else None


def need_view(n: HiringNeed | Vacancy, include_adjacent: bool = True) -> NeedView:
    grades = n.grades if isinstance(n, HiringNeed) else [n.grade]
    return NeedView(spec=n.specialization, grades=list(grades), must_skills=list(n.must_skills or []), nice_skills=list(n.nice_skills or []),
                    salary_from=n.salary_from, salary_to=n.salary_to, work_formats=list(n.work_formats or []), city=n.city,
                    fsp_weight=getattr(n, "fsp_weight", 0.5), domains=list(getattr(n, "domains", []) or []),
                    description=f"{n.title}\n{n.description or ''}", include_adjacent=include_adjacent)


def has_category():
    """Кандидат участвует в выдаче: грейд подтверждён тестом или заявлен в опросе (тогда — со статусом «не подтверждён»).
    Неподтверждённых не скрываем — по рекомендации постановщиков они показываются ниже подтверждённых."""
    return CandidateProfile.grade.is_not(None) | CandidateProfile.declared_grade.is_not(None)


def visible_pool(db: Session, specs: list[str]) -> list[CandidateProfile]:
    """Опубликованные профили, у которых основная или дополнительная категория — в одной из специализаций."""
    extra = select(CandidateCategory.user_id).where(CandidateCategory.specialization.in_(specs))
    q = (select(CandidateProfile).options(selectinload(CandidateProfile.achievements), selectinload(CandidateProfile.extra_categories))
         .where(CandidateProfile.visible.is_(True), CandidateProfile.search_status != "not_looking",
                (has_category() & CandidateProfile.specialization.in_(specs)) | CandidateProfile.user_id.in_(extra)))
    return list(db.scalars(q).all())


# ---------------------------------------------------------------- ранжирование
def rank(db: Session, nv: NeedView, now: datetime | None = None, pool: list[CandidateProfile] | None = None) -> list[tuple[CandidateProfile, dict]]:
    now = now or utcnow()
    specs = [nv.spec] + (RELATED_SPECS.get(nv.spec, []) if nv.include_adjacent else [])
    pool = pool if pool is not None else visible_pool(db, specs)
    ts, pend = _task_skills(db, [c.user_id for c in pool]), _pending(db)
    tfidf = TfIdf({c.user_id: cand_text(c) for c in pool})
    sims = tfidf.query(nv.description + " " + " ".join(nv.must_skills + nv.nice_skills))
    out = []
    for c in pool:
        # у кандидата с несколькими категориями в выдачу идёт лучшая из подходящих запросу
        best = None
        for cat in category_sources(c, specs):
            v = to_view(c, ts, pend, cat)
            res = score(v, nv, sims.get(c.user_id, 0.0), now)
            if res and (best is None or _order_key(res, v.strength) < best[0]):
                res["category"] = category_info(c, cat)
                best = (_order_key(res, v.strength), res)
        if best:
            out.append((c, best[1], best[0]))
    # выдача строится по категориям: сначала целевая категория запроса, затем смежные (каждая группа — по score);
    # кандидаты с неподтверждённым грейдом — после всех подтверждённых
    out.sort(key=lambda p: p[2])
    return [(c, r) for c, r, _ in out]


def recommend_categories(nv: NeedView, ranked: list[tuple[CandidateProfile, dict]], pool_all: list[CandidateProfile]) -> list[dict]:
    """Рекомендованные категории: целевые и смежные, с объёмом, долей ФСП и соответствием зарплатной вилке."""
    groups: dict[tuple[str, str], list] = defaultdict(list)
    unconfirmed: dict[tuple[str, str], int] = defaultdict(int)
    for c, r in ranked:
        cat = r["category"]
        if cat["confirmed"]:
            groups[(cat["specialization"], cat["grade"])].append((c, r))
        else:
            unconfirmed[(cat["specialization"], cat["grade"])] += 1
    out = []
    for (spec, grade), items in groups.items():
        rel = items[0][1]["relation"]
        sal = [c.salary_from for c, _ in items if c.salary_from]
        fits = [c for c, _ in items if c.salary_from is None or c.salary_from <= nv.salary_to]
        top = sorted((r["score"] for _, r in items), reverse=True)[:10]
        median = int(statistics.median(sal)) if sal else None
        note = {"target": "Основная категория вашего запроса", "adjacent_grade": "Смежный грейд", "related_spec": "Смежная специализация"}[rel]
        if median and median > nv.salary_to:
            note += f" · медианные ожидания {median // 1000} тыс. ₽ выше вашей вилки"
        out.append({
            "specialization": spec, "grade": grade, "label": category_label(spec, grade), "relation": rel,
            "count": len(items), "with_fsp": sum(1 for c, _ in items if c.achievements),
            "salary_fit_share": round(len(fits) / len(items), 2), "median_salary": median,
            "avg_top_score": round(sum(top) / len(top), 1) if top else 0, "note": note,
            "unconfirmed": unconfirmed.get((spec, grade), 0),
        })
    order = {"target": 0, "adjacent_grade": 1, "related_spec": 2}
    out.sort(key=lambda x: (order[x["relation"]], -x["avg_top_score"]))
    return out


def run_need(db: Session, need: HiringNeed, now: datetime | None = None) -> dict:
    """Пересчитать подборку по потребности. Пометки работодателя (избранное/скрытые) сохраняются."""
    now = now or utcnow()
    nv = need_view(need)
    ranked = rank(db, nv, now)
    existing = {e.candidate_id: e for e in db.scalars(select(ShortlistEntry).where(ShortlistEntry.need_id == need.id)).all()}
    keep_ids = set()
    for i, (c, r) in enumerate(ranked[:SHORTLIST_SIZE], start=1):
        e = existing.get(c.user_id)
        if e:
            e.score, e.rank, e.explanation = r["score"], i, r
        else:
            db.add(ShortlistEntry(need_id=need.id, candidate_id=c.user_id, score=r["score"], rank=i, explanation=r, first_seen_at=now))
        keep_ids.add(c.user_id)
    pos = {c.user_id: (i, r) for i, (c, r) in enumerate(ranked, start=1)}
    for cid, e in existing.items():
        if cid in keep_ids:
            continue
        if e.mark in ("starred", "hidden") and cid in pos:
            e.rank, e.score, e.explanation = pos[cid][0], pos[cid][1]["score"], pos[cid][1]
        elif e.mark == "starred":
            e.rank = 9999  # кандидат выпал из категории (например, скрыл профиль), но остаётся в избранном
        else:
            db.delete(e)
    need.last_run_at = now
    db.commit()
    return {"total_matched": len(ranked), "categories": recommend_categories(nv, ranked, [])}


# ---------------------------------------------------------------- карточки и приватность
def revealed_ids(db: Session, employer_id: int) -> set[int]:
    """Кандидаты, чьи контакты открыты работодателю (принятое приглашение или отклик) — одним запросом на страницу."""
    inv = db.execute(select(Invitation.candidate_id).where(Invitation.employer_id == employer_id, Invitation.status == "accepted",
                                                           Invitation.contacts_revoked_at.is_(None))).scalars()
    app_ = db.execute(select(Application.candidate_id).join(Vacancy, Vacancy.id == Application.vacancy_id)
                      .where(Vacancy.employer_id == employer_id, Application.status != "withdrawn")).scalars()
    return set(inv) | set(app_)


def contact_revealed(db: Session, employer_id: int, candidate_id: int) -> bool:
    inv = db.scalar(select(func.count()).select_from(Invitation).where(
        Invitation.employer_id == employer_id, Invitation.candidate_id == candidate_id, Invitation.status == "accepted",
        Invitation.contacts_revoked_at.is_(None)))
    if inv:
        return True
    app_ = db.scalar(select(func.count()).select_from(Application).join(Vacancy, Vacancy.id == Application.vacancy_id).where(
        Vacancy.employer_id == employer_id, Application.candidate_id == candidate_id, Application.status != "withdrawn"))
    return bool(app_)


def fsp_summary(c: CandidateProfile) -> dict:
    ach = c.achievements
    if not c.fsp_id and not ach:
        return {"linked": False, "count": 0, "items": [], "score": 0.0,
                "note": "Кандидат пока не участвовал в соревнованиях ФСП или не связал ФСП ID — это не влияет на категорию"}
    items = [{
        "event": a.event_name, "discipline": FSP_DISCIPLINES.get(a.discipline, {}).get("name", a.discipline),
        "discipline_code": a.discipline, "level": FSP_LEVELS.get(a.level, {}).get("name", a.level), "level_code": a.level,
        "date": a.event_date.isoformat(), "place": a.place, "participants": a.participants, "result": a.result_title,
        "team": a.team_name, "role": a.team_role, "stack": a.stack, "percentile": a.percentile, "verified": a.verified,
        "fit": discipline_fit(a.discipline, c.specialization), "fit_name": DISCIPLINE_FIT_NAMES[discipline_fit(a.discipline, c.specialization)],
    } for a in ach]
    return {"linked": bool(c.fsp_id), "fsp_id": c.fsp_id if c.fsp_id else None, "count": len(ach), "items": items,
            "score": c.fsp_score, "profile": c.fsp_profile,
            "best": items[0] if items else None,
            "note": None if ach else "ФСП ID связан, но результатов соревнований пока нет"}


def category_of(c: CandidateProfile) -> str | None:
    """Категория для работодателя: подтверждённая тестом или заявленная — с пометкой «не подтверждён»."""
    if c.grade:
        return category_label(c.specialization, c.grade)
    if c.declared_grade and c.specialization:
        return f"{category_label(c.specialization, c.declared_grade)} · не подтверждён"
    return None


def display_name(c: CandidateProfile, reveal: bool) -> str:
    if reveal or not (c.privacy or {}).get("hide_name", True):
        return c.full_name or f"Кандидат {c.public_code}"
    return f"Кандидат {c.public_code}"


def candidate_card(c: CandidateProfile, reveal: bool = False, explanation: dict | None = None, now: datetime | None = None,
                   full: bool = False, category: dict | None = None) -> dict:
    """Карточка кандидата для работодателя. Базовая часть кэшируется по (кандидат, время изменения профиля, раскрытие).
    category — категория, по которой кандидат найден (если дополнительная, карточка показывает её)."""
    if now is None and not full:
        card = dict(_cards.get_or_set((c.user_id, c.updated_at, reveal), lambda: _candidate_card(c, reveal)))
        if explanation:
            card["match"] = explanation
    else:
        card = _candidate_card(c, reveal, explanation, now, full)
    return _show_category(card, category or (explanation or {}).get("category"))


def _show_category(card: dict, cat: dict | None) -> dict:
    if cat and cat.get("additional"):
        card.update({"specialization": cat["specialization"], "grade": cat["grade"] if cat["confirmed"] else None,
                     "declared_grade": cat["grade"], "grade_status": "confirmed" if cat["confirmed"] else "unconfirmed",
                     "category": cat["label"] if cat["confirmed"] else f"{cat['label']} · не подтверждён", "theta": cat.get("theta"),
                     "category_percentile": None, "matched_additional": True})
    return card


def _candidate_card(c: CandidateProfile, reveal: bool = False, explanation: dict | None = None, now: datetime | None = None,
                    full: bool = False) -> dict:
    priv = c.privacy or {}
    now = now or utcnow()
    last = c.last_activity_at
    if last and not last.tzinfo:
        last = last.replace(tzinfo=timezone.utc)
    card = {
        "id": c.user_id,
        "code": c.public_code,
        "name": display_name(c, reveal),
        "headline": c.headline,
        "specialization": c.specialization,
        "grade": c.grade,
        "grade_status": "confirmed" if c.grade else "unconfirmed",
        "declared_grade": c.declared_grade,
        "category": category_of(c),
        "lang": c.primary_lang,
        "theta": c.theta,
        "category_percentile": c.category_percentile,
        "strength": c.strength,
        "strength_parts": strength_parts(c, now),
        "grade_confirmed_at": c.grade_confirmed_at.isoformat() if c.grade_confirmed_at else None,
        "verified_skills": sorted(set(all_verified(c))),
        "categories": all_categories(c),
        "skills": c.skills or [],
        "experience_years": c.experience_years,
        "city": c.city,
        "relocation": c.relocation,
        "work_formats": c.work_formats or [],
        "domains": c.domains or [],
        "search_status": c.search_status,
        "age_group": c.age_group or "adult",
        "salary_from": c.salary_from if priv.get("show_salary", True) else None,
        "salary_to": c.salary_to if priv.get("show_salary", True) else None,
        "fsp": fsp_summary(c) if priv.get("show_fsp", True) else {"linked": False, "hidden": True, "count": 0, "items": []},
        "tasks": {"done": c.tasks_done or 0, "avg_score": c.task_score} if priv.get("show_tasks", True) else None,
        "last_activity_at": last.isoformat() if last else None,
        "contacts_revealed": reveal,
    }
    if full:
        card.update({
            "about": c.about,
            "topic_scores": c.topic_scores or {},
            "soft_skills": c.soft_skills or [],
            "roles": c.roles or [],
            "team_role": c.team_role,
            "education": c.education or [],
            "experience": [
                {k: v for k, v in e.items() if not (k == "company" and priv.get("hide_current_company", True) and not reveal and i == 0)}
                for i, e in enumerate(c.experience or [])
            ],
        })
    if reveal:
        card["contacts"] = {"email": c.user.email if c.user else None, "phone": c.phone, "telegram": c.telegram, "github": c.github,
                            "full_name": c.full_name}
    if explanation:
        card["match"] = explanation
    return card


# ---------------------------------------------------------------- поиск по банку
def search(db: Session, employer_id: int, spec: str | None = None, grades: list[str] | None = None, skills: list[str] | None = None,
           verified_only: bool = False, fsp_only: bool = False, formats: list[str] | None = None, city: str | None = None,
           salary_max: int | None = None, q: str | None = None, sort: str = "strength", limit: int = 30, offset: int = 0,
           confirmed_only: bool = False) -> dict:
    key = ("search", pool_version(db), spec, tuple(grades or ()), tuple(skills or ()), verified_only, fsp_only, tuple(formats or ()),
           city, salary_max, q, sort, confirmed_only)
    ordered, unconfirmed_total = _queries.get_or_set(key, lambda: _search_ids(db, spec, grades, skills, verified_only, fsp_only, formats,
                                                                              city, salary_max, q, sort, confirmed_only))
    total = len(ordered)
    page_ids = ordered[offset: offset + limit]
    # связанные данные подгружаем только для страницы выдачи
    loaded = {c.user_id: c for c in db.scalars(select(CandidateProfile).options(selectinload(CandidateProfile.achievements),
                                                                                selectinload(CandidateProfile.user),
                                                                                selectinload(CandidateProfile.extra_categories))
                                               .where(CandidateProfile.user_id.in_([i for i, _ in page_ids]))).all()}
    revealed = revealed_ids(db, employer_id)
    items = []
    for cid, cat_spec in page_ids:
        c = loaded[cid]
        cat = next((x for x in c.extra_categories if x.specialization == cat_spec), None) if cat_spec else None
        card = candidate_card(c, c.user_id in revealed, category=category_info(c, cat))
        card["why"] = _why_in_category(c, cat)
        items.append(card)
    return {"total": total, "unconfirmed": unconfirmed_total, "items": items}


def _search_ids(db: Session, spec, grades, skills, verified_only, fsp_only, formats, city, salary_max, q, sort,
                confirmed_only) -> tuple[list[tuple[int, str | None]], int]:
    """Упорядоченные (кандидат, дополнительная категория или None). С фильтром по специализации кандидат находится
    и по дополнительной категории — тогда грейд, подтверждённость и сила берутся из неё."""
    stmt = (select(CandidateProfile).options(selectinload(CandidateProfile.extra_categories))
            .where(CandidateProfile.visible.is_(True), CandidateProfile.search_status != "not_looking"))
    if spec:
        stmt = stmt.where((CandidateProfile.specialization == spec)
                          | CandidateProfile.user_id.in_(select(CandidateCategory.user_id).where(CandidateCategory.specialization == spec)))
    if city:
        stmt = stmt.where(CandidateProfile.city == city)
    if salary_max:
        stmt = stmt.where((CandidateProfile.salary_from.is_(None)) | (CandidateProfile.salary_from <= salary_max))
    if fsp_only:
        stmt = stmt.where(CandidateProfile.fsp_score > 0)
    entries = []  # (профиль, категория-источник, подтверждён, грейд, сила, θ)
    for c in db.scalars(stmt).all():
        # первая подходящая под фильтры категория кандидата: основная, затем дополнительные
        for cat in category_sources(c, [spec] if spec else None):
            src = cat or c
            grade = src.grade or src.declared_grade
            if (confirmed_only and not src.grade) or (grades and grade not in grades):
                continue
            strength = c.strength or 0.0
            if cat is not None:
                strength = strength_for(c, cat.theta, cat.grade, fsp_score(c.achievements, None, cat.specialization))
            entries.append((c, cat, src.grade is not None, strength, src.theta))
            break
    if formats:
        entries = [e for e in entries if set(formats) & set(e[0].work_formats or [])]
    if skills:
        def has(c, s):
            ver = set(all_verified(c))
            return s in ver if verified_only else (s in ver or s in (c.skills or []))
        entries = [e for e in entries if all(has(e[0], s) for s in skills)]
    if q:
        ql = q.lower()
        entries = [e for e in entries if ql in (e[0].headline or "").lower() or any(ql in s.lower() for s in (e[0].skills or []))
                   or ql in (e[0].about or "").lower()]
    key = {
        "strength": lambda e: -e[3],
        "fresh": lambda e: -(e[0].last_activity_at.timestamp() if e[0].last_activity_at else 0),
        "salary": lambda e: (e[0].salary_from or 10**9),
        "theta": lambda e: -(e[4] if e[4] is not None else -9),
    }.get(sort, lambda e: -e[3])
    entries.sort(key=lambda e: (not e[2], key(e)))  # неподтверждённые — после подтверждённых
    unconfirmed_total = sum(1 for e in entries if not e[2])
    return [(e[0].user_id, e[1].specialization if e[1] is not None else None) for e in entries], unconfirmed_total


def _why_in_category(c: CandidateProfile, cat: CandidateCategory | None = None) -> list[str]:
    src = cat or c
    extra = " (дополнительная категория кандидата)" if cat is not None else ""
    if not src.grade:
        out = [f"Грейд {grade_name(src.declared_grade)} заявлен{extra}, тестом пока не подтверждён — показан ниже подтверждённых"]
        if c.achievements:
            a = c.achievements[0]
            out.append(f"ФСП: {a.result_title}, {a.event_name} ({a.event_date.year})")
        return out
    out = [f"Категория {category_label(src.specialization, src.grade)}{extra} присвоена по результату адаптивного теста"]
    if cat is None and c.category_percentile is not None:
        out.append(f"Сила профиля выше, чем у {int(c.category_percentile)}% кандидатов категории")
    if c.achievements:
        a = c.achievements[0]
        out.append(f"ФСП: {a.result_title}, {a.event_name} ({a.event_date.year})")
    if c.tasks_done:
        out.append(f"Регулярные задачи: {c.tasks_done}, средняя оценка {c.task_score or 0:.1f}")
    return out


def category_map(db: Session) -> dict:
    return _queries.get_or_set(("categories", pool_version(db)), lambda: _category_map(db))


def _category_map(db: Session) -> dict:
    rows = db.execute(select(CandidateProfile.specialization, CandidateProfile.grade, CandidateProfile.salary_from, CandidateProfile.fsp_score,
                             CandidateProfile.search_status)
                      .where(CandidateProfile.visible.is_(True), CandidateProfile.grade.is_not(None),
                             CandidateProfile.search_status != "not_looking")).all()
    cells: dict[tuple[str, str], list] = defaultdict(list)
    for r in rows:
        cells[(r.specialization, r.grade)].append(r)
    unconf = defaultdict(int, db.execute(select(CandidateProfile.specialization + ":" + CandidateProfile.declared_grade, func.count())
                                         .where(CandidateProfile.visible.is_(True), CandidateProfile.grade.is_(None),
                                                CandidateProfile.declared_grade.is_not(None), CandidateProfile.specialization.is_not(None),
                                                CandidateProfile.search_status != "not_looking")
                                         .group_by(CandidateProfile.specialization, CandidateProfile.declared_grade)).all())
    # дополнительные категории кандидатов учитываются в своих ячейках
    extra = db.execute(select(CandidateCategory.specialization, CandidateCategory.grade, CandidateCategory.declared_grade,
                              CandidateProfile.salary_from, CandidateProfile.fsp_score, CandidateProfile.search_status)
                       .join(CandidateProfile, CandidateProfile.user_id == CandidateCategory.user_id)
                       .where(CandidateProfile.visible.is_(True), CandidateProfile.search_status != "not_looking")).all()
    for r in extra:
        if r.grade:
            cells[(r.specialization, r.grade)].append(r)
        elif r.declared_grade:
            unconf[f"{r.specialization}:{r.declared_grade}"] += 1
    out = []
    for spec, info in SPECIALIZATIONS.items():
        row = {"specialization": spec, "name": info["name"], "short": info["short"], "direction": info["direction"], "cells": []}
        for g in GRADE_ORDER:
            items = cells.get((spec, g), [])
            sal = [c.salary_from for c in items if c.salary_from]
            row["cells"].append({
                "grade": g, "grade_name": grade_name(g), "count": len(items), "with_fsp": sum(1 for c in items if (c.fsp_score or 0) > 0),
                "active": sum(1 for c in items if c.search_status == "active"),
                "median_salary": int(statistics.median(sal)) if sal else None, "market_salary": MARKET_SALARY[spec][g],
                "unconfirmed": unconf.get(f"{spec}:{g}", 0),
            })
        out.append(row)
    return {"rows": out, "total": len(rows), "additional": sum(1 for r in extra if r.grade)}


def recompute_percentiles(db: Session) -> None:
    """Перцентиль силы профиля внутри категории (для объяснимости «выше, чем у N% категории»)."""
    rows = db.scalars(select(CandidateProfile).where(CandidateProfile.grade.is_not(None))).all()
    groups: dict[tuple, list[CandidateProfile]] = defaultdict(list)
    for c in rows:
        groups[(c.specialization, c.grade)].append(c)
    for items in groups.values():
        items.sort(key=lambda c: c.strength or 0)
        n = len(items)
        for i, c in enumerate(items):
            c.category_percentile = round(100 * i / max(1, n - 1), 1) if n > 1 else 50.0
    db.commit()


def market_hint(spec: str, grades: list[str], salary_from: int, salary_to: int) -> dict:
    med = [MARKET_SALARY[spec][g] for g in grades if g in MARKET_SALARY.get(spec, {})]
    if not med:
        return {}
    m = int(statistics.mean(med))
    status = "ok"
    if salary_to < 0.8 * m:
        status = "low"
    elif salary_from > 1.6 * m:
        status = "high"
    return {"market_median": m, "status": status,
            "message": {"ok": "Вилка соответствует рынку", "low": "Вилка заметно ниже рынка — вероятность принятия приглашений снизится",
                        "high": "Вилка значительно выше рынка — проверьте корректность"}[status]}


# ---------------------------------------------------------------- сравнение кандидатов
COMP_NAMES = {"L": "Подтверждённый уровень", "S": "Навыки", "F": "Достижения ФСП", "A": "Актуальность", "C": "Условия", "D": "Контекст"}


def _modifier_notes(mods: dict, p: dict) -> list[str]:
    out = []
    if mods["over_budget"]:
        out.append(f"ожидания выше бюджета (оценка ×{p['salary_mult']:.2f})")
    if mods["format_mismatch"]:
        out.append(f"формат работы не совпадает (×{p['format_mult']:.2f})")
    if mods["must_cov"] is not None and mods["must_cov"] < 1:
        out.append(f"покрыто {round(100 * mods['must_cov'])}% обязательных навыков (×{p['gate_floor'] + (1 - p['gate_floor']) * mods['must_cov']:.2f})")
    if mods["relation"] == "adjacent_grade":
        out.append(f"смежный грейд (×{p['adjacent_mult']:.2f})")
    elif mods["relation"] == "related_spec":
        out.append(f"смежная специализация (×{p['related_mult']:.2f})")
    if not mods["grade_confirmed"]:
        out.append("грейд не подтверждён тестом (×0.60)")
    return out


def compare(db: Session, need: HiringNeed, employer_id: int, ids: list[int], now: datetime | None = None) -> dict:
    """Сравнение 2–3 кандидатов по одной потребности: те же компоненты формулы и «почему A выше B»."""
    from app.matching.scoring import PARAMS

    now = now or utcnow()
    nv = need_view(need)
    cands = {c.user_id: c for c in db.scalars(select(CandidateProfile).options(selectinload(CandidateProfile.achievements),
                                                                              selectinload(CandidateProfile.user),
                                                                              selectinload(CandidateProfile.extra_categories))
                                              .where(CandidateProfile.user_id.in_(ids))).all()}
    ts, pend = _task_skills(db, list(cands)), _pending(db)
    tfidf = TfIdf({cid: cand_text(c) for cid, c in cands.items()})
    sims = tfidf.query(nv.description + " " + " ".join(nv.must_skills + nv.nice_skills))
    revealed = revealed_ids(db, employer_id)
    rows = []
    for cid in ids:
        c = cands.get(cid)
        if not c or not (c.visible or cid in revealed):
            continue
        r = best_score(c, nv, ts, pend, sims.get(cid, 0.0), now, with_parts=True)
        if not r:
            continue
        parts = r.pop("_parts")
        rows.append({"card": candidate_card(c, cid in revealed, explanation=r), "parts": parts})
    rows.sort(key=lambda x: -x["card"]["match"]["score"])
    pairs = []
    for a, b in zip(rows, rows[1:]):
        ca = {x["key"]: x for x in a["card"]["match"]["components"]}
        cb = {x["key"]: x for x in b["card"]["match"]["components"]}
        diffs = sorted(((k, round(ca[k]["contribution"] - cb[k]["contribution"], 1)) for k in ca), key=lambda x: -abs(x[1]))
        pairs.append({
            "a": a["card"]["id"], "b": b["card"]["id"], "a_name": a["card"]["name"], "b_name": b["card"]["name"],
            "score_gap": round(a["card"]["match"]["score"] - b["card"]["match"]["score"], 1),
            "a_better": [{"key": k, "name": COMP_NAMES[k], "points": d} for k, d in diffs if d >= 0.5],
            "b_better": [{"key": k, "name": COMP_NAMES[k], "points": -d} for k, d in diffs if d <= -0.5],
            "a_modifiers": _modifier_notes(a["parts"]["mods"], PARAMS), "b_modifiers": _modifier_notes(b["parts"]["mods"], PARAMS),
        })
    skills = list(dict.fromkeys(nv.must_skills + nv.nice_skills))
    return {"need": {"id": need.id, "title": need.title, "salary_from": need.salary_from, "salary_to": need.salary_to,
                     "must_skills": nv.must_skills, "nice_skills": nv.nice_skills},
            "items": [x["card"] for x in rows], "skills": skills, "pairs": pairs}
