"""Личный кабинет работодателя: компания, потребности и подборки, банк кандидатов, приглашения, вакансии,
регулярные задачи, интеграции с ATS."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.catalog.data import GRADE_ORDER, category_label
from app.catalog.skills import normalize_list
from app.core.db import get_db, utcnow
from app.core.deps import current_company
from app.core.errors import COMMON_ERRORS, AppError, err
from app.core.security import sha256
from app.matching import service as match
from app.matching.scoring import score
from app.models import (
    ApiKey,
    Application,
    CandidateProfile,
    Company,
    EmployerTask,
    HiringNeed,
    Invitation,
    ShortlistEntry,
    TaskAssignment,
    Vacancy,
    Webhook,
    WebhookDelivery,
)
from app.nlp.need_parser import parse_need
from app.schemas import (
    ApiKeyIn,
    ApplicationStatusIn,
    CompanyIn,
    InviteIn,
    MarkIn,
    MessageIn,
    NeedIn,
    ParseTextIn,
    ReviewIn,
    StageIn,
    TaskIn,
    VacancyIn,
    WebhookIn,
)
from app.services import invitations as inv_svc
from app.services import tasks as task_svc
from app.services import webhooks
from app.services.common import audit, notify
from app.services.trust import daily_limit, refresh_trust, risk_flags, tier
from app.services.webhooks import EVENTS
from app.testing.bank import GenCtx
from app.testing.blueprint import blueprint_view, sample_items, vacancy_blueprint

router = APIRouter(prefix="/employer", tags=["Работодатель"], responses=COMMON_ERRORS)


# ---------------------------------------------------------------- компания
def company_view(db: Session, c: Company) -> dict:
    refresh_trust(db, c)
    since = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today = db.scalar(select(func.count()).select_from(Invitation).where(Invitation.employer_id == c.user_id,
                                                                             Invitation.created_at >= since)) or 0
    return {"id": c.user_id, "name": c.name, "description": c.description, "industry": c.industry, "website": c.website, "size": c.size,
            "city": c.city, "contact_name": c.contact_name, "contact_email": c.contact_email, "contact_phone": c.contact_phone,
            "telegram": c.telegram, "inn": c.inn, "accent": c.accent, "trust_score": c.trust_score, "trust_factors": c.trust_factors,
            "trust_tier": tier(c.trust_score), "daily_invite_limit": daily_limit(c.trust_score), "invites_today": sent_today}


@router.get("/company", summary="Профиль компании и индекс доверия")
def get_company(c: Company = Depends(current_company), db: Session = Depends(get_db)):
    v = company_view(db, c)
    db.commit()
    return v


@router.put("/company", summary="Обновить профиль компании")
def put_company(body: CompanyIn, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    v = company_view(db, c)
    db.commit()
    return v


@router.get("/dashboard", summary="Сводка: потребности, приглашения, отклики, задачи")
def dashboard(c: Company = Depends(current_company), db: Session = Depends(get_db)):
    inv_svc.expire_overdue(db)
    needs = db.scalars(select(HiringNeed).where(HiringNeed.employer_id == c.user_id, HiringNeed.status == "active")).all()
    apps = db.scalar(select(func.count()).select_from(Application).join(Vacancy).where(Vacancy.employer_id == c.user_id,
                                                                                      Application.status == "sent")) or 0
    subs = db.scalar(select(func.count()).select_from(TaskAssignment).join(EmployerTask).where(EmployerTask.employer_id == c.user_id,
                                                                                              TaskAssignment.status == "submitted")) or 0
    recent = db.scalars(select(Invitation).where(Invitation.employer_id == c.user_id).order_by(Invitation.updated_at.desc()).limit(6)).all()
    cands = {x.user_id: x for x in db.scalars(select(CandidateProfile).where(CandidateProfile.user_id.in_([i.candidate_id for i in recent]))).all()}
    db.commit()
    return {"company": company_view(db, c), "needs": len(needs), "new_applications": apps, "submissions_to_review": subs,
            "analytics": inv_svc.employer_analytics(db, c),
            "recent_invitations": [inv_svc.invitation_view(i, "employer", cands.get(i.candidate_id)) for i in recent]}


# ---------------------------------------------------------------- потребности и подборки
def need_out(db: Session, n: HiringNeed) -> dict:
    counts = dict(db.execute(select(ShortlistEntry.mark, func.count()).where(ShortlistEntry.need_id == n.id).group_by(ShortlistEntry.mark)).all())
    invited = db.scalar(select(func.count()).select_from(Invitation).where(Invitation.need_id == n.id)) or 0
    return {"id": n.id, "title": n.title, "description": n.description, "specialization": n.specialization, "grades": n.grades,
            "must_skills": n.must_skills, "nice_skills": n.nice_skills, "work_formats": n.work_formats, "city": n.city,
            "salary_from": n.salary_from, "salary_to": n.salary_to, "fsp_weight": n.fsp_weight, "domains": n.domains, "status": n.status,
            "created_at": n.created_at.isoformat(), "last_run_at": n.last_run_at.isoformat() if n.last_run_at else None,
            "shortlist": {"total": sum(counts.values()), "starred": counts.get("starred", 0), "hidden": counts.get("hidden", 0)},
            "invited": invited, "market": match.market_hint(n.specialization, n.grades, n.salary_from, n.salary_to),
            "categories": [category_label(n.specialization, g) for g in n.grades]}


def _need(db: Session, c: Company, need_id: int) -> HiringNeed:
    n = db.get(HiringNeed, need_id)
    if not n or n.employer_id != c.user_id:
        raise AppError(404, "not_found", "Потребность не найдена")
    return n


@router.post("/needs/parse", summary="Разбор текстового описания потребности (NLP): специализация, грейд, стек, вилка, формат")
def parse(body: ParseTextIn, c: Company = Depends(current_company)):
    res = parse_need(body.text)
    if res["salary_from"] and res["salary_to"]:
        res["market"] = match.market_hint(res["specialization"], res["grades"], res["salary_from"], res["salary_to"])
    return res


@router.get("/needs", summary="Мои потребности")
def list_needs(c: Company = Depends(current_company), db: Session = Depends(get_db)):
    rows = db.scalars(select(HiringNeed).where(HiringNeed.employer_id == c.user_id, HiringNeed.status != "archived")
                      .order_by(HiringNeed.created_at.desc())).all()
    return {"items": [need_out(db, n) for n in rows]}


@router.post("/needs", status_code=201, summary="Описать потребность — система сформирует подборку кандидатов")
def create_need(body: NeedIn, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    data = body.model_dump()
    data["must_skills"] = normalize_list(data["must_skills"])
    data["nice_skills"] = [s for s in normalize_list(data["nice_skills"]) if s not in data["must_skills"]]
    data["grades"] = sorted(set(data["grades"]), key=GRADE_ORDER.index)
    n = HiringNeed(employer_id=c.user_id, **data)
    db.add(n)
    db.flush()
    res = match.run_need(db, n)
    return {**need_out(db, n), "run": res}


@router.get("/needs/{need_id}", summary="Потребность и рекомендованные категории")
def get_need(need_id: int, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    n = _need(db, c, need_id)
    ranked = match.rank(db, match.need_view(n))
    return {**need_out(db, n), "recommended_categories": match.recommend_categories(match.need_view(n), ranked, [])}


@router.put("/needs/{need_id}", summary="Изменить потребность (подборка пересчитывается, пометки сохраняются)")
def update_need(need_id: int, body: NeedIn, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    n = _need(db, c, need_id)
    data = body.model_dump()
    data["must_skills"] = normalize_list(data["must_skills"])
    data["nice_skills"] = [s for s in normalize_list(data["nice_skills"]) if s not in data["must_skills"]]
    for k, v in data.items():
        setattr(n, k, v)
    res = match.run_need(db, n)
    return {**need_out(db, n), "run": res}


@router.delete("/needs/{need_id}", summary="Архивировать потребность")
def archive_need(need_id: int, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    n = _need(db, c, need_id)
    n.status = "archived"
    db.commit()
    return {"status": "archived"}


@router.post("/needs/{need_id}/run", summary="Обновить подборку (новые кандидаты, свежие результаты)")
def rerun(need_id: int, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    n = _need(db, c, need_id)
    return match.run_need(db, n)


@router.get("/needs/{need_id}/shortlist", summary="Подборка с уточняющими фильтрами (без потери исходной подборки)")
def shortlist(
    need_id: int,
    grades: list[str] = Query(default=[]),
    skills: list[str] = Query(default=[], description="Все перечисленные навыки должны быть подтверждены или заявлены"),
    verified_only: bool = Query(False, description="Учитывать только подтверждённые навыки"),
    fsp_only: bool = False,
    formats: list[str] = Query(default=[]),
    relation: str | None = Query(None, description="target | adjacent_grade | related_spec"),
    min_score: float = 0,
    within_budget: bool = False,
    mark: str | None = Query(None, description="starred | hidden | new"),
    include_hidden: bool = False,
    c: Company = Depends(current_company),
    db: Session = Depends(get_db),
):
    n = _need(db, c, need_id)
    if not n.last_run_at:
        match.run_need(db, n)
    entries = db.scalars(select(ShortlistEntry).where(ShortlistEntry.need_id == n.id).order_by(ShortlistEntry.rank)).all()
    cands = {x.user_id: x for x in db.scalars(select(CandidateProfile).options(selectinload(CandidateProfile.achievements),
                                                                              selectinload(CandidateProfile.user))
                                              .where(CandidateProfile.user_id.in_([e.candidate_id for e in entries]))).all()}
    invites = {i.candidate_id: i for i in db.scalars(select(Invitation).where(Invitation.employer_id == c.user_id,
                                                                             Invitation.candidate_id.in_(list(cands)))).all()}
    base_total = len([e for e in entries if e.mark != "hidden"])
    revealed = match.revealed_ids(db, c.user_id)
    out = []
    for e in entries:
        cand = cands.get(e.candidate_id)
        if not cand:
            continue
        ex = e.explanation or {}
        if e.mark == "hidden" and not include_hidden and mark != "hidden":
            continue
        if mark and e.mark != mark:
            continue
        if grades and cand.grade not in grades:
            continue
        if fsp_only and not (cand.fsp_score or 0) > 0:
            continue
        if formats and not set(formats) & set(cand.work_formats or []):
            continue
        if relation and ex.get("relation") != relation:
            continue
        if e.score < min_score:
            continue
        if within_budget and cand.salary_from and cand.salary_from > n.salary_to:
            continue
        if skills:
            sd = ex.get("skills", {})
            ok = True
            for s in skills:
                ev = (sd.get(s) or {}).get("evidence")
                if ev is None:
                    ver = {v["skill"] for v in cand.verified_skills or []}
                    ev = "test" if s in ver else ("declared" if s in (cand.skills or []) else "none")
                if ev in ("none", "related") or (verified_only and ev == "declared"):
                    ok = False
            if not ok:
                continue
        card = match.candidate_card(cand, cand.user_id in revealed, explanation=ex)
        card.update({"rank": e.rank, "score": e.score, "mark": e.mark, "note": e.note, "first_seen_at": e.first_seen_at.isoformat()})
        inv = invites.get(cand.user_id)
        card["invitation"] = {"id": inv.id, "status": inv.status, "status_name": inv_svc.STATUS_NAMES[inv.status]} if inv else None
        out.append(card)
    return {"need": need_out(db, n), "base_total": base_total, "filtered_total": len(out), "items": out}


@router.get("/needs/{need_id}/compare", summary="Сравнить 2–3 кандидатов по потребности: компоненты оценки и «почему A выше B»",
            responses=err(400, "Нужно от 2 до 3 кандидатов"))
def compare(need_id: int, ids: list[int] = Query(..., description="2–3 id кандидатов"), c: Company = Depends(current_company),
            db: Session = Depends(get_db)):
    if not 2 <= len(set(ids)) <= 3:
        raise AppError(400, "compare_size", "Для сравнения выберите от 2 до 3 кандидатов")
    return match.compare(db, _need(db, c, need_id), c.user_id, list(dict.fromkeys(ids)))


@router.put("/needs/{need_id}/shortlist/{candidate_id}", summary="Пометить кандидата в подборке (избранное/скрыть/заметка)")
def mark_entry(need_id: int, candidate_id: int, body: MarkIn, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    n = _need(db, c, need_id)
    e = db.scalar(select(ShortlistEntry).where(ShortlistEntry.need_id == n.id, ShortlistEntry.candidate_id == candidate_id))
    if not e:
        raise AppError(404, "not_found", "Кандидат не входит в подборку")
    e.mark = body.mark
    if body.note is not None:
        e.note = body.note
    db.commit()
    return {"mark": e.mark, "note": e.note}


@router.get("/needs/{need_id}/test-plan", summary="Как система тестирует кандидатов под эту потребность: план и примеры заданий")
def need_test_plan(need_id: int, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    n = _need(db, c, need_id)
    return _test_plan(n.specialization, n.must_skills + n.nice_skills, n.grades[0])


def _test_plan(spec: str, skills: list[str], grade: str) -> dict:
    vb = vacancy_blueprint(spec, skills)
    ctx = GenCtx(lang=vb["lang"], framework=vb["framework"], spec=spec)
    return {**vb, "plan": blueprint_view(vb["weights"], ctx, spec, grade),
            "samples": sample_items(spec, ctx, vb["weights"], grade, n=4),
            "note": "Каждому кандидату задания генерируются заново: другие данные и формулировки, та же трудность. "
                    "Ответ вычисляется генератором, поэтому утечка конкретного варианта не помогает следующему кандидату."}


# ---------------------------------------------------------------- банк кандидатов
@router.get("/categories", summary="Карта категорий: специализации × грейды, объём, доля ФСП, медианные ожидания")
def categories(c: Company = Depends(current_company), db: Session = Depends(get_db)):
    return match.category_map(db)


@router.get("/candidates", summary="Поиск по банку кандидатов с фильтрами")
def search(
    specialization: str | None = None,
    grades: list[str] = Query(default=[]),
    skills: list[str] = Query(default=[]),
    verified_only: bool = False,
    fsp_only: bool = False,
    formats: list[str] = Query(default=[]),
    city: str | None = None,
    salary_max: int | None = None,
    q: str | None = None,
    sort: str = Query("strength", description="strength | fresh | salary | theta"),
    limit: int = Query(30, le=100),
    offset: int = 0,
    confirmed_only: bool = Query(False, description="Только с грейдом, подтверждённым тестом. По умолчанию кандидаты с неподтверждённым "
                                                     "грейдом тоже показываются — со статусом и ниже подтверждённых"),
    c: Company = Depends(current_company),
    db: Session = Depends(get_db),
):
    return match.search(db, c.user_id, specialization, grades, normalize_list(skills) or skills, verified_only, fsp_only, formats, city,
                        salary_max, q, sort, limit, offset, confirmed_only)


@router.get("/candidates/{candidate_id}", summary="Профиль кандидата (контакты — только после принятия приглашения/отклика)")
def candidate(candidate_id: int, need_id: int | None = None, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    cand = db.get(CandidateProfile, candidate_id)
    if not cand or not (cand.grade or cand.declared_grade) or not (cand.visible or match.contact_revealed(db, c.user_id, candidate_id)):
        raise AppError(404, "not_found", "Кандидат не найден или скрыл профиль")
    reveal = match.contact_revealed(db, c.user_id, candidate_id)
    expl = None
    if need_id:
        n = _need(db, c, need_id)
        e = db.scalar(select(ShortlistEntry).where(ShortlistEntry.need_id == n.id, ShortlistEntry.candidate_id == candidate_id))
        expl = e.explanation if e else match.best_score(cand, match.need_view(n), match._task_skills(db, [cand.user_id]))
    card = match.candidate_card(cand, reveal, explanation=expl, full=True)
    invs = db.scalars(select(Invitation).where(Invitation.employer_id == c.user_id, Invitation.candidate_id == candidate_id)
                      .order_by(Invitation.created_at.desc())).all()
    card["invitations"] = [inv_svc.invitation_view(i, "employer") for i in invs]
    tasks = db.scalars(select(TaskAssignment).where(TaskAssignment.candidate_id == candidate_id, TaskAssignment.status == "reviewed")
                       .order_by(TaskAssignment.reviewed_at.desc()).limit(5)).all()
    if (cand.privacy or {}).get("show_tasks", True):
        card["task_results"] = [{"title": t.task.title, "company": t.task.company.name, "score": t.score, "date": t.reviewed_at.isoformat()}
                                for t in tasks]
    audit(db, c.user_id, "candidate_viewed", "candidate", candidate_id)
    db.commit()
    return card


# ---------------------------------------------------------------- приглашения
def _inv(db: Session, c: Company, inv_id: int) -> Invitation:
    i = db.get(Invitation, inv_id)
    if not i or i.employer_id != c.user_id:
        raise AppError(404, "not_found", "Приглашение не найдено")
    return i


@router.post("/invitations", status_code=201, summary="Пригласить кандидата(ов): описание, вилка (обязательно), способ связи",
             responses={**err(409, "Уже есть активное приглашение"), **err(429, "Превышен суточный лимит"), **err(422, "Признаки мошенничества")})
def invite(body: InviteIn, bg: BackgroundTasks, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    invs = inv_svc.send(db, bg, c, body.candidate_ids, body.model_dump())
    return {"sent": len(invs), "items": [inv_svc.invitation_view(i, "employer") for i in invs]}


@router.get("/invitations", summary="Мои приглашения и их статусы")
def list_invitations(status: str | None = None, need_id: int | None = None, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    inv_svc.expire_overdue(db)
    db.commit()
    q = select(Invitation).where(Invitation.employer_id == c.user_id)
    if status:
        q = q.where(Invitation.status == status)
    if need_id:
        q = q.where(Invitation.need_id == need_id)
    rows = db.scalars(q.order_by(Invitation.created_at.desc())).all()
    cands = {x.user_id: x for x in db.scalars(select(CandidateProfile).where(CandidateProfile.user_id.in_([i.candidate_id for i in rows]))).all()}
    items = []
    unread = inv_svc.unread_counts(db, [i.id for i in rows], "employer")
    for i in rows:
        v = inv_svc.invitation_view(i, "employer", cands.get(i.candidate_id))
        v["unread_messages"] = unread.get(i.id, 0)
        if inv_svc.contacts_open(i) and cands.get(i.candidate_id):
            cand = cands[i.candidate_id]
            v["contacts"] = {"full_name": cand.full_name, "email": cand.user.email if cand.user else None, "phone": cand.phone,
                             "telegram": cand.telegram}
        items.append(v)
    return {"items": items, "analytics": inv_svc.employer_analytics(db, c)}


@router.get("/invitations/{inv_id}", summary="Приглашение")
def get_inv(inv_id: int, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    i = _inv(db, c, inv_id)
    cand = db.get(CandidateProfile, i.candidate_id)
    v = inv_svc.invitation_view(i, "employer", cand)
    if inv_svc.contacts_open(i):
        v["contacts"] = {"full_name": cand.full_name, "email": cand.user.email if cand.user else None, "phone": cand.phone,
                         "telegram": cand.telegram, "github": cand.github}
    return v


@router.get("/invitations/{inv_id}/messages", summary="Переписка с кандидатом по принятому приглашению")
def inv_messages(inv_id: int, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    i = _inv(db, c, inv_id)
    return {"items": inv_svc.messages(db, i, "employer"), "available": i.status == "accepted"}


@router.post("/invitations/{inv_id}/messages", status_code=201, summary="Написать кандидату (после принятия приглашения)",
             responses={**err(409, "Приглашение не принято"), **err(429, "Слишком много сообщений")})
def inv_post_message(inv_id: int, body: MessageIn, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    return inv_svc.post_message(db, _inv(db, c, inv_id), c.user_id, "employer", body.text)


@router.post("/invitations/{inv_id}/withdraw", summary="Отозвать неотвеченное приглашение")
def withdraw(inv_id: int, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    return inv_svc.invitation_view(inv_svc.withdraw(db, c, _inv(db, c, inv_id)), "employer")


@router.put("/invitations/{inv_id}/stage", summary="Этап после принятия: знакомство → интервью → оффер → выход")
def stage(inv_id: int, body: StageIn, bg: BackgroundTasks, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    i = inv_svc.set_stage(db, c, _inv(db, c, inv_id), body.stage)
    webhooks.emit(bg, c.user_id, "invitation.stage_changed", {"invitation_id": i.id, "stage": i.stage})  # ATS узнаёт об этапе
    return inv_svc.invitation_view(i, "employer")


@router.get("/analytics", summary="Аналитика приглашений: конверсия, причины отказов, воронка")
def analytics(c: Company = Depends(current_company), db: Session = Depends(get_db)):
    return inv_svc.employer_analytics(db, c)


# ---------------------------------------------------------------- вакансии и отклики
def vacancy_out(db: Session, v: Vacancy) -> dict:
    counts = dict(db.execute(select(Application.status, func.count()).where(Application.vacancy_id == v.id).group_by(Application.status)).all())
    return {"id": v.id, "title": v.title, "description": v.description, "specialization": v.specialization, "grade": v.grade,
            "category": category_label(v.specialization, v.grade), "must_skills": v.must_skills, "nice_skills": v.nice_skills,
            "work_formats": v.work_formats, "city": v.city, "salary_from": v.salary_from, "salary_to": v.salary_to, "status": v.status,
            "risk_flags": v.risk_flags, "views": v.views, "created_at": v.created_at.isoformat(), "updated_at": v.updated_at.isoformat(),
            "applications": {"total": sum(counts.values()), **counts},
            "market": match.market_hint(v.specialization, [v.grade], v.salary_from, v.salary_to)}


def _vac(db: Session, c: Company, vid: int) -> Vacancy:
    v = db.get(Vacancy, vid)
    if not v or v.employer_id != c.user_id:
        raise AppError(404, "not_found", "Вакансия не найдена")
    return v


@router.get("/vacancies", summary="Мои вакансии")
def my_vacancies(c: Company = Depends(current_company), db: Session = Depends(get_db)):
    rows = db.scalars(select(Vacancy).where(Vacancy.employer_id == c.user_id).order_by(Vacancy.created_at.desc())).all()
    return {"items": [vacancy_out(db, v) for v in rows]}


def _vacancy_data(body: VacancyIn) -> dict:
    data = body.model_dump()
    data["must_skills"] = normalize_list(data["must_skills"])
    data["nice_skills"] = [s for s in normalize_list(data["nice_skills"]) if s not in data["must_skills"]]
    data["risk_flags"] = risk_flags(f"{data['title']} {data['description']}", data["salary_from"], data["salary_to"], data["specialization"],
                                    [data["grade"]])
    if any(f["code"] in ("payment_request", "pii_request", "scheme") for f in data["risk_flags"]):
        raise AppError(422, "risky_content", "Вакансия содержит признаки мошенничества и не может быть опубликована", data["risk_flags"])
    return data


@router.post("/vacancies", status_code=201, summary="Опубликовать вакансию (зарплатная вилка обязательна)")
def create_vacancy(body: VacancyIn, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    v = Vacancy(employer_id=c.user_id, **_vacancy_data(body))
    db.add(v)
    db.commit()
    return vacancy_out(db, v)


@router.get("/vacancies/{vid}", summary="Вакансия")
def get_vacancy(vid: int, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    return vacancy_out(db, _vac(db, c, vid))


@router.put("/vacancies/{vid}", summary="Редактировать вакансию")
def update_vacancy(vid: int, body: VacancyIn, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    v = _vac(db, c, vid)
    for k, val in _vacancy_data(body).items():
        setattr(v, k, val)
    db.commit()
    return vacancy_out(db, v)


@router.get("/vacancies/{vid}/applications", summary="Отклики на вакансию (контакты откликнувшихся раскрыты)")
def vacancy_applications(vid: int, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    v = _vac(db, c, vid)
    rows = db.scalars(select(Application).where(Application.vacancy_id == v.id, Application.status != "withdrawn")
                      .order_by(Application.match_score.desc().nulls_last())).all()
    out = []
    for a in rows:
        cand = db.get(CandidateProfile, a.candidate_id)
        card = match.candidate_card(cand, reveal=True, explanation=a.explanation)
        card.update({"application_id": a.id, "status": a.status, "cover_letter": a.cover_letter, "applied_at": a.created_at.isoformat(),
                     "match_score": a.match_score, "employer_comment": a.employer_comment})
        out.append(card)
    return {"vacancy": vacancy_out(db, v), "items": out}


APPLICATION_STATUS_NAMES = {"viewed": "просмотрен", "interview": "приглашение на интервью", "offer": "оффер", "rejected": "отказ"}


def set_application_status(db: Session, c: Company, app_id: int, status: str, comment: str | None = None) -> Application:
    """Статус отклика — из кабинета работодателя или из его ATS; кандидат получает уведомление."""
    a = db.get(Application, app_id)
    if not a or a.vacancy.employer_id != c.user_id:
        raise AppError(404, "not_found", "Отклик не найден")
    if status not in APPLICATION_STATUS_NAMES:
        raise AppError(400, "invalid_status", "Неизвестный статус отклика")
    a.status = status
    if comment is not None:
        a.employer_comment = comment
    if status == "viewed" and not a.viewed_at:
        a.viewed_at = utcnow()
    notify(db, a.candidate_id, "application_status", f"Отклик на «{a.vacancy.title}»: {APPLICATION_STATUS_NAMES[status]}", comment, "/c/applications")
    db.commit()
    return a


@router.put("/applications/{app_id}", summary="Статус отклика: просмотрен, интервью, оффер, отказ")
def application_status(app_id: int, body: ApplicationStatusIn, bg: BackgroundTasks, c: Company = Depends(current_company),
                       db: Session = Depends(get_db)):
    a = set_application_status(db, c, app_id, body.status, body.comment)
    webhooks.emit(bg, c.user_id, "application.status_changed", {"application_id": a.id, "vacancy_id": a.vacancy_id,
                                                                "external_id": a.vacancy.external_id, "status": a.status})
    return {"id": a.id, "status": a.status}


@router.get("/vacancies/{vid}/recommended", summary="Рекомендованные кандидаты под вакансию (пригласить напрямую)")
def vacancy_recommended(vid: int, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    v = _vac(db, c, vid)
    ranked = match.rank(db, match.need_view(v))[:20]
    revealed = match.revealed_ids(db, c.user_id)
    return {"items": [{**match.candidate_card(cand, cand.user_id in revealed, explanation=r), "score": r["score"]}
                      for cand, r in ranked]}


@router.get("/vacancies/{vid}/test-plan", summary="План тестирования кандидатов под вакансию и примеры сгенерированных заданий")
def vacancy_test_plan(vid: int, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    v = _vac(db, c, vid)
    return _test_plan(v.specialization, v.must_skills + v.nice_skills, v.grade)


# ---------------------------------------------------------------- регулярные задачи
def task_out(db: Session, t: EmployerTask) -> dict:
    counts = dict(db.execute(select(TaskAssignment.status, func.count()).where(TaskAssignment.task_id == t.id)
                             .group_by(TaskAssignment.status)).all())
    return {"id": t.id, "title": t.title, "description": t.description, "specialization": t.specialization, "grades": t.grades,
            "kind": t.kind, "est_minutes": t.est_minutes, "key_points": t.key_points, "skills": t.skills, "active": t.active,
            "created_at": t.created_at.isoformat(), "stats": counts}


@router.get("/tasks", summary="Мои задачи для регулярных заданий")
def tasks(c: Company = Depends(current_company), db: Session = Depends(get_db)):
    rows = db.scalars(select(EmployerTask).where(EmployerTask.employer_id == c.user_id).order_by(EmployerTask.created_at.desc())).all()
    return {"items": [task_out(db, t) for t in rows]}


@router.post("/tasks", status_code=201, summary="Создать короткую задачу (система будет предлагать её кандидатам категории)")
def create_task(body: TaskIn, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    data = body.model_dump()
    data["skills"] = normalize_list(data["skills"])
    t = EmployerTask(employer_id=c.user_id, **data)
    db.add(t)
    db.commit()
    return task_out(db, t)


def _task(db: Session, c: Company, tid: int) -> EmployerTask:
    t = db.get(EmployerTask, tid)
    if not t or t.employer_id != c.user_id:
        raise AppError(404, "not_found", "Задача не найдена")
    return t


@router.put("/tasks/{tid}", summary="Изменить задачу")
def update_task(tid: int, body: TaskIn, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    t = _task(db, c, tid)
    for k, v in body.model_dump().items():
        setattr(t, k, v)
    db.commit()
    return task_out(db, t)


@router.get("/tasks/{tid}", summary="Задача и решения кандидатов")
def task_detail(tid: int, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    t = _task(db, c, tid)
    rows = db.scalars(select(TaskAssignment).where(TaskAssignment.task_id == t.id, TaskAssignment.status.in_(["submitted", "reviewed"]))
                      .order_by(TaskAssignment.submitted_at.desc())).all()
    subs = []
    for a in rows:
        cand = db.get(CandidateProfile, a.candidate_id)
        subs.append({"id": a.id, "status": a.status, "answer": a.answer, "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
                     "auto_score": a.auto_score, "auto_details": a.auto_details, "score": a.score, "feedback": a.feedback,
                     "candidate": {"id": cand.user_id, "code": cand.public_code, "name": match.display_name(cand, match.contact_revealed(db, c.user_id, cand.user_id)),
                                   "category": match.category_of(cand)}})
    return {**task_out(db, t), "submissions": subs}


@router.post("/tasks/{tid}/submissions/{aid}/review", summary="Оценить решение (1–5) — влияет на актуальность профиля кандидата")
def review(tid: int, aid: int, body: ReviewIn, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    t = _task(db, c, tid)
    a = db.get(TaskAssignment, aid)
    if not a:
        raise AppError(404, "not_found", "Решение не найдено")
    a = task_svc.review(db, t, a, body.score, body.feedback)
    return {"id": a.id, "status": a.status, "score": a.score}


# ---------------------------------------------------------------- интеграции (ATS)
@router.get("/integrations", summary="API-ключи и вебхуки для интеграции с ATS")
def integrations(c: Company = Depends(current_company), db: Session = Depends(get_db)):
    keys = db.scalars(select(ApiKey).where(ApiKey.employer_id == c.user_id, ApiKey.revoked_at.is_(None))).all()
    hooks = db.scalars(select(Webhook).where(Webhook.employer_id == c.user_id)).all()
    dels = db.scalars(select(WebhookDelivery).join(Webhook).where(Webhook.employer_id == c.user_id)
                      .order_by(WebhookDelivery.created_at.desc()).limit(20)).all()
    return {
        "api_keys": [{"id": k.id, "name": k.name, "prefix": k.prefix, "created_at": k.created_at.isoformat(),
                      "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None} for k in keys],
        "webhooks": [{"id": h.id, "url": h.url, "events": h.events, "active": h.active, "secret_hint": h.secret[:4] + "…"} for h in hooks],
        "deliveries": [{"id": d.id, "event": d.event, "ok": d.ok, "status_code": d.status_code, "attempts": d.attempts, "error": d.error,
                        "created_at": d.created_at.isoformat()} for d in dels],
        "events": EVENTS,
    }


@router.post("/api-keys", status_code=201, summary="Создать API-ключ (показывается один раз)")
def create_key(body: ApiKeyIn, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    raw = "drk_" + secrets.token_urlsafe(32)
    k = ApiKey(employer_id=c.user_id, name=body.name, prefix=raw[:12], key_hash=sha256(raw))
    db.add(k)
    db.commit()
    return {"id": k.id, "name": k.name, "key": raw, "prefix": k.prefix}


@router.delete("/api-keys/{kid}", summary="Отозвать API-ключ")
def revoke_key(kid: int, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    k = db.get(ApiKey, kid)
    if not k or k.employer_id != c.user_id:
        raise AppError(404, "not_found", "Ключ не найден")
    k.revoked_at = utcnow()
    db.commit()
    return {"status": "revoked"}


@router.post("/webhooks", status_code=201, summary="Подписать URL на события (подпись HMAC-SHA256)")
def create_webhook(body: WebhookIn, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    bad = [e for e in body.events if e not in EVENTS]
    if bad:
        raise AppError(400, "invalid_events", "Неизвестные события", bad)
    secret = secrets.token_hex(24)
    h = Webhook(employer_id=c.user_id, url=body.url, secret=secret, events=body.events)
    db.add(h)
    db.commit()
    return {"id": h.id, "url": h.url, "events": h.events, "secret": secret}


@router.delete("/webhooks/{hid}", summary="Удалить вебхук")
def delete_webhook(hid: int, c: Company = Depends(current_company), db: Session = Depends(get_db)):
    h = db.get(Webhook, hid)
    if not h or h.employer_id != c.user_id:
        raise AppError(404, "not_found", "Вебхук не найден")
    db.delete(h)
    db.commit()
    return {"status": "deleted"}
