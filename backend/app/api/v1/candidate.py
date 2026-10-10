"""Личный кабинет кандидата: профиль и резюме, опрос, категория, приглашения, отклики, задачи, настройки (152-ФЗ)."""
from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog.data import GRADES, SPECIALIZATIONS, category_label, grade_name
from app.catalog.skills import normalize_list
from app.core.db import get_db, utcnow
from app.core.deps import current_candidate
from app.core.errors import COMMON_ERRORS, AppError, err
from app.fsp import client as fsp
from app.fsp.scoring import fsp_score
from app.matching.service import best_score, candidate_card, fsp_summary, need_view, _task_skills
from app.matching.strength import completeness, refresh_strength, strength_parts
from app.models import (
    Application,
    CandidateProfile,
    Consent,
    GradeChange,
    Invitation,
    Report,
    SurveyResponse,
    TaskAssignment,
    TestAttempt,
    User,
    Vacancy,
)
from app.nlp.resume_parser import parse_resume, pdf_to_text
from app.schemas import AcceptIn, ApplyIn, CategoryIn, ConsentIn, ContactsAccessIn, DeclineIn, MessageIn, PrivacyIn, ProfileIn, ReportIn, SurveyIn, TaskSubmitIn
from app.services import categories as cat_svc
from app.services import demo
from app.services import invitations as inv_svc
from app.services import tasks as task_svc
from app.services import webhooks
from app.services.common import CONSENT_KINDS, audit, current_consents, notify, record_consent
from app.services.pdf import build_profile_pdf
from app.services.trust import refresh_trust
from app.testing.service import eligibility, expert_mode, expire_stale

router = APIRouter(prefix="/candidate", tags=["Кандидат"], responses=COMMON_ERRORS)


def own_profile(db: Session, c: CandidateProfile) -> dict:
    card = candidate_card(c, reveal=True, full=True)
    pending = db.scalar(select(func.count()).select_from(Invitation).where(Invitation.candidate_id == c.user_id,
                                                                          Invitation.status.in_(["sent", "viewed"]))) or 0
    steps = [
        {"key": "survey", "title": "Опрос: направление, специализация, грейд", "done": c.survey_completed_at is not None},
        {"key": "test", "title": "Тест на заявленный грейд", "done": c.grade is not None},
        {"key": "profile", "title": "Профиль и резюме", "done": bool(c.full_name and c.skills)},
        {"key": "publish", "title": "Публикация профиля для работодателей", "done": bool(c.visible)},
        {"key": "fsp", "title": "Связь с ФСП ID (по желанию)", "done": bool(c.fsp_id), "optional": True},
    ]
    card.update({
        "email": c.user.email if c.user else None,
        "privacy": c.privacy,
        "visible": c.visible,
        "direction": c.direction,
        "primary_lang": c.primary_lang,
        "framework": c.framework,
        "declared_grade": c.declared_grade,
        "grade_name": grade_name(c.grade),
        "grade_locked_until": _active_lock(c),
        "theta_se": c.theta_se,
        "survey_completed_at": c.survey_completed_at.isoformat() if c.survey_completed_at else None,
        "resume_filename": c.resume_filename,
        "completeness": round(completeness(c), 2),
        "pending_invitations": pending,
        "onboarding": steps,
        "fsp": fsp_summary(c),
        "last_attempt_id": c.last_attempt_id,
        "expert_mode": expert_mode(c.user.email if c.user else None),
        "demo_shared": demo.shared_demo(c.user.email if c.user else None),
        "demo_resettable": demo.resettable(c.user.email if c.user else None),
    })
    return card


def _active_lock(c: CandidateProfile) -> str | None:
    """Дата окончания фиксации грейда — только если период ещё не истёк."""
    lock, now = c.grade_locked_until, utcnow()
    if lock and (lock if lock.tzinfo else lock.replace(tzinfo=now.tzinfo)) > now:
        return lock.isoformat()
    return None

@router.get("/me", summary="Профиль кандидата с категорией, статусом и шагами онбординга")
def me(c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    expire_stale(db, c)
    return own_profile(db, c)


@router.put("/profile", summary="Сохранить профиль/резюме (ручное заполнение или подтверждение распознанного PDF)")
def update_profile(body: ProfileIn, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    if "skills" in data:
        data["skills"] = normalize_list(data["skills"]) or [s for s in data["skills"] if s][:40]
    if "experience" in data:
        data["experience"] = [e for e in data["experience"] if any(e.values())]
    if data.get("salary_from") and data.get("salary_to") and data["salary_from"] > data["salary_to"]:
        raise AppError(400, "invalid_salary", "Нижняя граница ожиданий больше верхней")
    for k, v in data.items():
        setattr(c, k, v)
    c.updated_at = utcnow()
    refresh_strength(c)
    db.commit()
    return own_profile(db, c)


@router.post("/resume/parse", summary="Загрузка PDF-резюме с автораспознаванием полей",
             responses={**err(400, "Файл не является PDF или не содержит текста"), **err(413, "Файл слишком большой")})
async def parse_resume_pdf(file: UploadFile = File(...), c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise AppError(413, "too_large", "Максимальный размер файла — 5 МБ")
    if not data.startswith(b"%PDF"):
        raise AppError(400, "not_pdf", "Загрузите файл в формате PDF")
    try:
        text = pdf_to_text(data)
    except Exception:  # noqa: BLE001
        raise AppError(400, "pdf_error", "Не удалось прочитать PDF")
    if len(text.strip()) < 40:
        raise AppError(400, "no_text", "В PDF не найден текст (возможно, это скан). Заполните профиль вручную")
    c.resume_text, c.resume_filename = text[:50000], (file.filename or "resume.pdf")[:200]
    db.commit()
    return {"fields": parse_resume(text), "text_preview": text[:1500]}


@router.post("/resume/parse-text", summary="Распознавание резюме из текста (вставка из буфера)")
def parse_resume_text(body: dict, c: CandidateProfile = Depends(current_candidate)):
    text = str(body.get("text") or "")
    if len(text.strip()) < 40:
        raise AppError(400, "no_text", "Слишком короткий текст")
    return {"fields": parse_resume(text), "text_preview": text[:1500]}


@router.get("/profile/pdf", summary="Стандартизированный PDF-профиль с QR-кодом проверки", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}}})
def profile_pdf(c: CandidateProfile = Depends(current_candidate)):
    pdf = build_profile_pdf(c)
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="draft-profile-{c.public_code}.pdf"'})


# ---------------------------------------------------------------- опрос и категория
@router.post("/survey", summary="Опрос по отрасли и специализации (обязательный шаг перед тестом)",
             responses=err(409, "Смена специализации заблокирована до окончания периода"))
def submit_survey(body: SurveyIn, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    spec = SPECIALIZATIONS[body.specialization]
    if body.direction != spec["direction"]:
        raise AppError(400, "invalid_direction", "Специализация не относится к выбранному направлению")
    now = utcnow()
    lock = c.grade_locked_until
    if c.grade and c.specialization and c.specialization != body.specialization and lock and (lock if lock.tzinfo else lock.replace(tzinfo=now.tzinfo)) > now:
        raise AppError(409, "spec_locked", "Сменить специализацию можно после окончания периода фиксации грейда",
                       {"available_at": lock.isoformat()})
    if any(x.specialization == body.specialization for x in c.extra_categories):
        raise AppError(409, "category_exists", "Эта специализация уже добавлена как дополнительная категория — сделайте её основной")
    lang = body.primary_lang if body.primary_lang in spec["langs"] else spec["langs"][0]
    if c.specialization and c.specialization != body.specialization and c.grade:
        db.add(GradeChange(candidate_id=c.user_id, specialization=c.specialization, from_grade=c.grade, to_grade="none",
                           reason="specialization_change", created_at=now))
        c.grade, c.theta, c.theta_se, c.topic_scores, c.verified_skills = None, None, None, {}, []
    c.direction, c.specialization, c.primary_lang = body.direction, body.specialization, lang
    c.framework = body.framework if body.specialization == "frontend" else None
    c.declared_grade, c.experience_years, c.team_role = body.declared_grade, body.experience_years, body.team_role
    if body.domains:
        c.domains = body.domains
    if body.work_formats:
        c.work_formats = body.work_formats
    stack = normalize_list(body.stack)
    if stack:
        c.skills = list(dict.fromkeys((c.skills or []) + stack))
    c.survey_completed_at = now
    db.add(SurveyResponse(candidate_id=c.user_id, answers=body.model_dump(), created_at=now))
    c.fsp_score = fsp_score(c.achievements, spec=c.specialization)  # актуальность дисциплин ФСП зависит от специализации
    refresh_strength(c)
    db.commit()
    return {"status": "ok", "eligibility": eligibility(db, c), "profile": own_profile(db, c)}


# ---------------------------------------------------------------- несколько категорий
@router.get("/categories", summary="Мои категории: основная и дополнительные")
def categories(c: CandidateProfile = Depends(current_candidate)):
    return {"items": cat_svc.all_categories(c), "max_extra": cat_svc.MAX_EXTRA}


@router.post("/categories", status_code=201, summary="Добавить дополнительную категорию (грейд заявленный — подтверждается тестом)",
             responses=err(409, "Специализация уже есть, лимит категорий или не пройден опрос"))
def add_category(body: CategoryIn, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    cat_svc.add_category(db, c, body.specialization, body.declared_grade, body.primary_lang, body.framework)
    db.commit()
    return {"items": cat_svc.all_categories(c), "max_extra": cat_svc.MAX_EXTRA}


@router.post("/categories/{spec}/main", summary="Сделать дополнительную категорию основной — чтобы пройти по ней тест",
             responses={**err(404, "Нет такой категории"), **err(409, "Есть незавершённый тест")})
def make_main_category(spec: str, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    cat_svc.make_main(db, c, spec)
    db.commit()
    return {"items": cat_svc.all_categories(c), "eligibility": eligibility(db, c), "profile": own_profile(db, c)}


@router.delete("/categories/{spec}", summary="Удалить дополнительную категорию", responses=err(404, "Нет такой категории"))
def remove_category(spec: str, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    cat_svc.remove_category(db, c, spec)
    db.commit()
    return {"items": cat_svc.all_categories(c), "max_extra": cat_svc.MAX_EXTRA}


@router.get("/history", summary="История опросов, попыток тестирования и изменений грейда")
def history(c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    surveys = db.scalars(select(SurveyResponse).where(SurveyResponse.candidate_id == c.user_id).order_by(SurveyResponse.created_at.desc())).all()
    attempts = db.scalars(select(TestAttempt).where(TestAttempt.candidate_id == c.user_id).order_by(TestAttempt.started_at.desc())).all()
    changes = db.scalars(select(GradeChange).where(GradeChange.candidate_id == c.user_id).order_by(GradeChange.created_at.desc())).all()
    return {
        "surveys": [{"id": s.id, "created_at": s.created_at.isoformat(), "answers": s.answers} for s in surveys],
        "attempts": [{"id": a.id, "specialization": a.specialization, "target_grade": a.target_grade, "status": a.status, "passed": a.passed,
                      "theta": a.theta, "se": a.se, "items": a.items_count, "upgrade_grade": a.upgrade_grade,
                      "upgrade_accepted": a.upgrade_accepted, "started_at": a.started_at.isoformat(),
                      "finished_at": a.finished_at.isoformat() if a.finished_at else None} for a in attempts],
        "grade_changes": [{"from": g.from_grade, "to": g.to_grade, "reason": g.reason, "specialization": g.specialization,
                           "created_at": g.created_at.isoformat()} for g in changes],
    }


# ---------------------------------------------------------------- приглашения
@router.get("/insights", summary="Зарплатный радар и путь роста по данным категории (обезличенно)")
def insights(c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    from app.services.insights import candidate_insights

    return candidate_insights(db, c)


@router.get("/invitations", summary="Входящие приглашения от работодателей (только свои)")
def my_invitations(status: str | None = None, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    inv_svc.expire_overdue(db)
    db.commit()
    q = select(Invitation).where(Invitation.candidate_id == c.user_id)
    if status:
        q = q.where(Invitation.status == status)
    rows = db.scalars(q.order_by(Invitation.created_at.desc())).all()
    unread = inv_svc.unread_counts(db, [i.id for i in rows], "candidate")
    return {"items": [inv_svc.invitation_view(i, "candidate") | {"unread_messages": unread.get(i.id, 0)} for i in rows]}


def _own_inv(db: Session, c: CandidateProfile, inv_id: int) -> Invitation:
    inv = db.get(Invitation, inv_id)
    if not inv or inv.candidate_id != c.user_id:
        raise AppError(404, "not_found", "Приглашение не найдено")
    return inv


@router.get("/invitations/{inv_id}", summary="Приглашение (при открытии отмечается как просмотренное)")
def get_invitation(inv_id: int, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    inv = _own_inv(db, c, inv_id)
    inv_svc.mark_viewed(db, inv)
    return inv_svc.invitation_view(inv, "candidate")


@router.post("/invitations/{inv_id}/accept", summary="Принять приглашение — контакты раскрываются работодателю")
def accept_invitation(inv_id: int, body: AcceptIn, bg: BackgroundTasks, c: CandidateProfile = Depends(current_candidate),
                      db: Session = Depends(get_db)):
    return inv_svc.invitation_view(inv_svc.accept(db, bg, c, _own_inv(db, c, inv_id), body.message), "candidate")


@router.post("/invitations/{inv_id}/decline", summary="Отклонить приглашение с причиной (обратная связь работодателю)")
def decline_invitation(inv_id: int, body: DeclineIn, bg: BackgroundTasks, c: CandidateProfile = Depends(current_candidate),
                       db: Session = Depends(get_db)):
    return inv_svc.invitation_view(inv_svc.decline(db, bg, c, _own_inv(db, c, inv_id), body.reason, body.comment), "candidate")


@router.post("/invitations/{inv_id}/contacts", summary="Закрыть или снова открыть работодателю доступ к своим контактам",
             description="После принятия приглашения кандидат может отозвать доступ: контакты скрываются из кабинета и API работодателя "
                         "(включая ATS-выгрузку), переписка на платформе остаётся. Действие записывается в журнал аудита.",
             responses=err(409, "Приглашение не принято"))
def contacts_access(inv_id: int, body: ContactsAccessIn, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    return inv_svc.invitation_view(inv_svc.set_contacts_access(db, c, _own_inv(db, c, inv_id), body.revoked), "candidate")


@router.get("/invitations/{inv_id}/messages", summary="Переписка с работодателем по принятому приглашению")
def inv_messages(inv_id: int, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    inv = _own_inv(db, c, inv_id)
    return {"items": inv_svc.messages(db, inv, "candidate"), "available": inv.status == "accepted"}


@router.post("/invitations/{inv_id}/messages", status_code=201, summary="Написать работодателю (после принятия приглашения)",
             responses={**err(409, "Приглашение не принято"), **err(429, "Слишком много сообщений")})
def inv_post_message(inv_id: int, body: MessageIn, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    return inv_svc.post_message(db, _own_inv(db, c, inv_id), c.user_id, "candidate", body.text)


@router.post("/invitations/{inv_id}/report", status_code=201, summary="Пожаловаться на приглашение (антифрод)")
def report_invitation(inv_id: int, body: ReportIn, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    inv = _own_inv(db, c, inv_id)
    db.add(Report(reporter_id=c.user_id, employer_id=inv.employer_id, target_type="invitation", target_id=inv.id, reason=body.reason,
                  comment=body.comment))
    db.flush()
    refresh_trust(db, inv.company)
    db.commit()
    return {"status": "received"}


# ---------------------------------------------------------------- отклики
@router.post("/applications", status_code=201, summary="Откликнуться на вакансию (контакты раскрываются работодателю)",
             responses={**err(409, "Уже откликались"), **err(404, "Вакансия не найдена")})
def apply(body: ApplyIn, bg: BackgroundTasks, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    v = db.get(Vacancy, body.vacancy_id)
    if not v or v.status != "published":
        raise AppError(404, "not_found", "Вакансия не найдена или закрыта")
    if not c.grade:
        raise AppError(409, "grade_required", "Чтобы откликаться, подтвердите грейд тестом — работодатель увидит вашу категорию")
    if db.scalar(select(Application).where(Application.vacancy_id == v.id, Application.candidate_id == c.user_id)):
        raise AppError(409, "already_applied", "Вы уже откликались на эту вакансию")
    res = best_score(c, need_view(v, include_adjacent=True), _task_skills(db, [c.user_id])) or {}
    a = Application(vacancy_id=v.id, candidate_id=c.user_id, cover_letter=body.cover_letter, status="sent", match_score=res.get("score"),
                    explanation=res or None)
    db.add(a)
    db.flush()
    audit(db, c.user_id, "contacts_revealed", "application", a.id, employer_id=v.employer_id)
    notify(db, v.employer_id, "application", f"Новый отклик на «{v.title}»", f"Кандидат {c.public_code}, {category_label(c.specialization, c.grade)}",
           f"/e/vacancies/{v.id}")
    db.commit()
    webhooks.emit(bg, v.employer_id, "application.created", {"application_id": a.id, "vacancy_id": v.id, "candidate_code": c.public_code})
    return {"id": a.id, "status": a.status, "match_score": a.match_score}


@router.get("/applications", summary="Мои отклики и их статусы")
def my_applications(c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    rows = db.scalars(select(Application).where(Application.candidate_id == c.user_id).order_by(Application.created_at.desc())).all()
    names = {"sent": "Отправлен", "viewed": "Просмотрен", "interview": "Приглашение на интервью", "offer": "Оффер", "rejected": "Отказ",
             "withdrawn": "Отозван"}
    return {"items": [{"id": a.id, "status": a.status, "status_name": names.get(a.status, a.status), "match_score": a.match_score,
                       "created_at": a.created_at.isoformat(), "updated_at": a.updated_at.isoformat(), "employer_comment": a.employer_comment,
                       "vacancy": {"id": a.vacancy.id, "title": a.vacancy.title, "company": a.vacancy.company.name,
                                   "salary_from": a.vacancy.salary_from, "salary_to": a.vacancy.salary_to, "status": a.vacancy.status}}
                      for a in rows]}


@router.delete("/applications/{app_id}", summary="Отозвать отклик")
def withdraw_application(app_id: int, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    a = db.get(Application, app_id)
    if not a or a.candidate_id != c.user_id:
        raise AppError(404, "not_found", "Отклик не найден")
    a.status = "withdrawn"
    db.commit()
    return {"status": "withdrawn"}


# ---------------------------------------------------------------- регулярные задачи
def _assignment_view(a: TaskAssignment, show_rubric: bool = False) -> dict:
    t = a.task
    return {"id": a.id, "status": a.status, "assigned_at": a.assigned_at.isoformat(), "due_at": a.due_at.isoformat(),
            "answer": a.answer, "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None, "score": a.score,
            "feedback": a.feedback, "auto_score": a.auto_score,
            "task": {"id": t.id, "title": t.title, "description": t.description, "kind": t.kind, "est_minutes": t.est_minutes,
                     "skills": t.skills, "company": t.company.name}}


@router.get("/tasks", summary="Текущая регулярная задача и история")
def my_tasks(c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    task_svc.assign_if_due(db, c)
    rows = db.scalars(select(TaskAssignment).where(TaskAssignment.candidate_id == c.user_id).order_by(TaskAssignment.assigned_at.desc())).all()
    db.commit()
    current = next((a for a in rows if a.status == "assigned"), None)
    return {"current": _assignment_view(current) if current else None, "history": [_assignment_view(a) for a in rows if a.status != "assigned"],
            "tasks_done": c.tasks_done, "task_score": c.task_score, "available": c.grade is not None}


@router.post("/tasks/request", summary="Получить новую задачу сейчас (если нет активной)")
def request_task(c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    if not c.grade:
        raise AppError(409, "grade_required", "Регулярные задачи доступны после присвоения категории")
    a = task_svc.assign_if_due(db, c, force=True)
    if not a:
        raise AppError(404, "no_tasks", "Сейчас нет новых задач для вашей категории — загляните позже")
    return _assignment_view(a)


@router.post("/tasks/{assignment_id}/submit", summary="Отправить решение или подход к решению")
def submit_task(assignment_id: int, body: TaskSubmitIn, bg: BackgroundTasks, c: CandidateProfile = Depends(current_candidate),
                db: Session = Depends(get_db)):
    a = db.get(TaskAssignment, assignment_id)
    if not a:
        raise AppError(404, "not_found", "Задача не найдена")
    return _assignment_view(task_svc.submit(db, bg, c, a, body.answer))


@router.post("/tasks/{assignment_id}/skip", summary="Пропустить задачу")
def skip_task(assignment_id: int, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    a = db.get(TaskAssignment, assignment_id)
    if not a:
        raise AppError(404, "not_found", "Задача не найдена")
    task_svc.skip(db, c, a)
    return {"status": "skipped"}


# ---------------------------------------------------------------- настройки, 152-ФЗ, ФСП
@router.put("/settings/privacy", summary="Настройки приватности и видимости профиля",
            responses=err(409, "Нет согласия на публикацию профиля"))
def privacy(body: PrivacyIn, request: Request, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    vis = data.pop("visible", None)
    c.privacy = {**(c.privacy or {}), **data}
    if vis is not None:
        if vis and not current_consents(db, c.user_id).get("profile_publication"):
            record_consent(db, c.user_id, "profile_publication", True, request.client.host if request.client else None,
                           request.headers.get("user-agent"))
        c.visible = vis
        if not vis:
            record_consent(db, c.user_id, "profile_publication", False, request.client.host if request.client else None,
                           request.headers.get("user-agent"))
    db.commit()
    return {"privacy": c.privacy, "visible": c.visible}


@router.get("/consents", summary="Текущие согласия и журнал изменений")
def consents(c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    log = db.scalars(select(Consent).where(Consent.user_id == c.user_id).order_by(Consent.created_at.desc())).all()
    # согласие законного представителя фиксируется при регистрации 15–17-летнего и не переключается в настройках
    kinds = {k: v for k, v in CONSENT_KINDS.items() if k != "guardian_consent"}
    return {"current": current_consents(db, c.user_id), "kinds": kinds, "all_kinds": CONSENT_KINDS, "age_group": c.age_group,
            "log": [{"kind": x.kind, "granted": x.granted, "version": x.version, "created_at": x.created_at.isoformat()} for x in log]}


@router.post("/consents", summary="Дать или отозвать согласие")
def set_consent(body: ConsentIn, request: Request, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    if body.kind == "pd_processing" and not body.granted:
        raise AppError(409, "pd_required", "Без согласия на обработку данных сервис недоступен — для отзыва удалите аккаунт")
    record_consent(db, c.user_id, body.kind, body.granted, request.client.host if request.client else None, request.headers.get("user-agent"))
    if body.kind == "profile_publication":
        c.visible = body.granted
    if body.kind == "fsp_data" and not body.granted:
        _unlink(db, c)
    db.commit()
    return {"current": current_consents(db, c.user_id), "visible": c.visible}


@router.post("/fsp/sync", summary="Обновить достижения из реестра ФСП (сервисный токен реестра)", responses=err(503, "Реестр недоступен"))
def fsp_sync(c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    if not c.fsp_id:
        raise AppError(409, "not_linked", "Профиль не связан с ФСП ID")
    try:
        n = fsp.apply_results(db, c, fsp.fetch_results(fsp.service_token(), c.fsp_id))
    except AppError:
        raise
    except Exception:  # noqa: BLE001
        raise AppError(503, "fsp_unavailable", "Реестр ФСП недоступен, попробуйте позже")
    db.commit()
    return {"achievements": n, "fsp": fsp_summary(c)}


def _unlink(db: Session, c: CandidateProfile) -> None:
    u = db.get(User, c.user_id)
    u.fsp_sub = None
    c.fsp_id, c.fsp_linked_at, c.fsp_profile, c.fsp_score = None, None, None, 0.0
    for a in list(c.achievements):
        c.achievements.remove(a)
    refresh_strength(c)


@router.delete("/fsp", summary="Отвязать ФСП ID и удалить полученные достижения")
def fsp_unlink(request: Request, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    demo.guard_shared(c.user.email if c.user else None, "отвязка ФСП ID")
    _unlink(db, c)
    record_consent(db, c.user_id, "fsp_data", False, request.client.host if request.client else None, request.headers.get("user-agent"))
    db.commit()
    return {"status": "unlinked"}


@router.get("/export", summary="Выгрузка всех персональных данных (право субъекта ПДн, 152-ФЗ ст. 14)")
def export(c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    audit(db, c.user_id, "data_export", "candidate", c.user_id)
    db.commit()
    data = {"profile": own_profile(db, c), "history": history(c, db), "invitations": my_invitations(None, c, db),
            "applications": my_applications(c, db), "consents": consents(c, db)}
    return Response(json.dumps(data, ensure_ascii=False, indent=2, default=str), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="draft-data-{c.public_code}.json"'})


@router.delete("/account", status_code=204, summary="Удалить аккаунт и все персональные данные",
               responses=err(403, "Общий демо-аккаунт на демо-стенде (код demo_account_protected)"))
def delete_account(c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    demo.guard_shared(c.user.email if c.user else None, "удаление аккаунта")
    u = db.get(User, c.user_id)
    audit(db, None, "account_deleted", "user", u.id)
    db.delete(u)
    db.commit()


@router.post("/demo/reset", summary="Демо-стенд: начать путь заново (только newbie и expert1–5)",
             description="Удаляет профиль, опрос, попытки теста, категории, приглашения и отклики демо-аккаунта и создаёт пустой "
                         "профиль — чтобы следующий эксперт жюри прошёл путь кандидата с нуля.",
             responses=err(403, "Недоступно для этого аккаунта или вне демо-режима"))
def demo_reset(c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    demo.reset_candidate(db, c)
    return {"status": "reset"}
