"""Приглашения — «обратная» механика выхода на контакт.

Работодатель находит кандидата в категории/подборке и отправляет приглашение с описанием, вилкой (обязательно)
и способом связи. Кандидат видит условия ДО начала общения; контакты кандидата раскрываются работодателю
только после принятия. Статусы: sent → viewed → accepted | declined | expired | withdrawn; после принятия —
этапы воронки работодателя: contact → interview → offer → hired | closed (видны обеим сторонам).
"""
from __future__ import annotations

import secrets
from collections import Counter
from datetime import timedelta

from fastapi import BackgroundTasks
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog.data import DECLINE_REASONS, category_label, grade_name
from app.core.db import utcnow
from app.core.errors import AppError
from app.matching.scoring import NeedView
from app.matching.service import _pending, _task_skills, best_score, category_of, need_view
from app.models import CandidateProfile, Company, HiringNeed, Invitation, Message, ShortlistEntry, User, Vacancy
from app.services import webhooks
from app.services.common import audit, notify
from app.services.trust import daily_limit, refresh_trust, risk_flags

STAGES = ["contact", "interview", "offer", "hired", "closed"]
STAGE_NAMES = {"contact": "Знакомство", "interview": "Интервью", "offer": "Оффер", "hired": "Выход на работу", "closed": "Закрыто"}
STATUS_NAMES = {"sent": "Отправлено", "viewed": "Просмотрено", "accepted": "Принято", "declined": "Отклонено", "expired": "Истекло",
                "withdrawn": "Отозвано"}


def expire_overdue(db: Session) -> None:
    now = utcnow()
    for inv in db.scalars(select(Invitation).where(Invitation.status.in_(["sent", "viewed"]), Invitation.expires_at < now)).all():
        inv.status = "expired"
    db.flush()


def _explain(db: Session, cand: CandidateProfile, need: HiringNeed | None, vacancy: Vacancy | None, salary_from: int, salary_to: int,
             work_format: str | None) -> dict | None:
    if need:
        e = db.scalar(select(ShortlistEntry).where(ShortlistEntry.need_id == need.id, ShortlistEntry.candidate_id == cand.user_id))
        if e:
            return e.explanation
        nv = need_view(need)
    elif vacancy:
        nv = need_view(vacancy)
    else:
        nv = NeedView(spec=cand.specialization, grades=[cand.grade or cand.declared_grade], salary_from=salary_from, salary_to=salary_to,
                      work_formats=[work_format] if work_format else [])
    return best_score(cand, nv, _task_skills(db, [cand.user_id]), _pending(db))


def send(db: Session, bg: BackgroundTasks | None, company: Company, candidate_ids: list[int], data: dict) -> list[Invitation]:
    expire_overdue(db)
    refresh_trust(db, company)
    since = utcnow() - timedelta(days=1)
    sent_today = db.scalar(select(func.count()).select_from(Invitation).where(Invitation.employer_id == company.user_id,
                                                                             Invitation.created_at >= since)) or 0
    limit = daily_limit(company.trust_score)
    if sent_today + len(candidate_ids) > limit:
        raise AppError(429, "invite_limit", f"Лимит приглашений в сутки для вашего уровня доверия — {limit}. Заполните профиль компании, "
                                            "чтобы повысить доверие.", {"limit": limit, "sent_today": sent_today})
    if data["salary_from"] > data["salary_to"]:
        raise AppError(400, "invalid_salary", "Нижняя граница вилки больше верхней")
    need = db.get(HiringNeed, data["need_id"]) if data.get("need_id") else None
    if need and need.employer_id != company.user_id:
        raise AppError(404, "not_found", "Потребность не найдена")
    vacancy = db.get(Vacancy, data["vacancy_id"]) if data.get("vacancy_id") else None
    if vacancy and vacancy.employer_id != company.user_id:
        raise AppError(404, "not_found", "Вакансия не найдена")
    flags = risk_flags(f"{data['title']} {data['description']} {data['contact_method']}", data["salary_from"], data["salary_to"],
                       need.specialization if need else (vacancy.specialization if vacancy else None),
                       need.grades if need else ([vacancy.grade] if vacancy else None))
    if any(f["code"] in ("payment_request", "pii_request", "scheme") for f in flags):
        raise AppError(422, "risky_content", "Приглашение содержит признаки мошенничества и не может быть отправлено", flags)
    batch = secrets.token_hex(6) if len(candidate_ids) > 1 else None
    out = []
    for cid in dict.fromkeys(candidate_ids):
        cand = db.get(CandidateProfile, cid)
        if not cand or not cand.visible or not (cand.grade or cand.declared_grade) or cand.search_status == "not_looking":
            if len(candidate_ids) == 1:
                raise AppError(404, "candidate_unavailable", "Кандидат недоступен для приглашений")
            continue
        active = db.scalar(select(Invitation).where(Invitation.employer_id == company.user_id, Invitation.candidate_id == cid,
                                                    Invitation.status.in_(["sent", "viewed"])))
        if active:
            if len(candidate_ids) == 1:
                raise AppError(409, "already_invited", "У кандидата уже есть ваше активное приглашение")
            continue
        expl = _explain(db, cand, need, vacancy, data["salary_from"], data["salary_to"], data.get("work_format"))
        inv = Invitation(
            employer_id=company.user_id, candidate_id=cid, need_id=need.id if need else None, vacancy_id=vacancy.id if vacancy else None,
            batch_id=batch, title=data["title"], description=data["description"], salary_from=data["salary_from"], salary_to=data["salary_to"],
            work_format=data.get("work_format"), city=data.get("city"), contact_method=data["contact_method"], status="sent",
            match_score=expl["score"] if expl else None, explanation=expl, risk_flags=flags,
            expires_at=utcnow() + timedelta(days=int(data.get("expires_in_days") or 10)),
        )
        db.add(inv)
        db.flush()
        if need:
            e = db.scalar(select(ShortlistEntry).where(ShortlistEntry.need_id == need.id, ShortlistEntry.candidate_id == cid))
            if e and e.mark == "new":
                e.mark = "starred"
        user = db.get(User, cid)
        notify(db, cid, "invitation", f"Приглашение от «{company.name}»",
               f"{data['title']} · {data['salary_from']:,}–{data['salary_to']:,} ₽ gross".replace(",", " "), f"/c/invitations/{inv.id}",
               email_to=user.email if user and not cand.is_synthetic else None)
        out.append(inv)
    db.commit()
    return out


def mark_viewed(db: Session, inv: Invitation) -> None:
    if inv.status == "sent":
        inv.status = "viewed"
        inv.viewed_at = utcnow()
        db.commit()


def accept(db: Session, bg: BackgroundTasks | None, cand: CandidateProfile, inv: Invitation, message: str | None) -> Invitation:
    expire_overdue(db)
    if inv.status not in ("sent", "viewed"):
        raise AppError(409, "invalid_status", f"Приглашение в статусе «{STATUS_NAMES[inv.status]}» нельзя принять")
    inv.status, inv.stage, inv.responded_at = "accepted", "contact", utcnow()
    inv.viewed_at = inv.viewed_at or inv.responded_at
    inv.candidate_message = message
    audit(db, cand.user_id, "contacts_revealed", "invitation", inv.id, employer_id=inv.employer_id)
    emp_user = db.get(User, inv.employer_id)
    notify(db, inv.employer_id, "invitation_accepted", f"{cand.full_name or 'Кандидат ' + cand.public_code} принял(а) приглашение",
           f"«{inv.title}». Контакты кандидата открыты.", f"/e/invitations/{inv.id}", email_to=emp_user.email if emp_user else None)
    db.commit()
    webhooks.emit(bg, inv.employer_id, "invitation.accepted", ats_candidate_payload(db, inv))
    return inv


def decline(db: Session, bg: BackgroundTasks | None, cand: CandidateProfile, inv: Invitation, reason: str, comment: str | None) -> Invitation:
    expire_overdue(db)
    if inv.status not in ("sent", "viewed"):
        raise AppError(409, "invalid_status", "Приглашение уже обработано")
    if reason not in DECLINE_REASONS:
        raise AppError(400, "invalid_reason", "Укажите причину отказа")
    inv.status, inv.decline_reason, inv.decline_comment, inv.responded_at = "declined", reason, comment, utcnow()
    inv.viewed_at = inv.viewed_at or inv.responded_at
    notify(db, inv.employer_id, "invitation_declined", f"Кандидат {cand.public_code} отклонил приглашение",
           f"Причина: {DECLINE_REASONS[reason]}", f"/e/invitations/{inv.id}")
    db.commit()
    webhooks.emit(bg, inv.employer_id, "invitation.declined", {"invitation_id": inv.id, "candidate_code": cand.public_code,
                                                               "reason": reason, "reason_text": DECLINE_REASONS[reason]})
    return inv


def withdraw(db: Session, company: Company, inv: Invitation) -> Invitation:
    if inv.status not in ("sent", "viewed"):
        raise AppError(409, "invalid_status", "Отозвать можно только неотвеченное приглашение")
    inv.status = "withdrawn"
    notify(db, inv.candidate_id, "invitation_withdrawn", f"«{company.name}» отозвала приглашение", inv.title, f"/c/invitations/{inv.id}")
    db.commit()
    return inv


def set_stage(db: Session, company: Company, inv: Invitation, stage: str) -> Invitation:
    if inv.status != "accepted":
        raise AppError(409, "invalid_status", "Этапы доступны после принятия приглашения")
    if stage not in STAGES:
        raise AppError(400, "invalid_stage", "Неизвестный этап")
    inv.stage = stage
    notify(db, inv.candidate_id, "invitation_stage", f"«{company.name}»: этап «{STAGE_NAMES[stage]}»", inv.title, f"/c/invitations/{inv.id}")
    db.commit()
    return inv


# ---------------------------------------------------------------- контакты и переписка после принятия
MESSAGE_MAX_LEN = 2000
MESSAGES_PER_HOUR = 30


def contacts_open(inv: Invitation) -> bool:
    """Контакты кандидата открыты пригласившему работодателю: приглашение принято и кандидат не закрыл доступ."""
    return inv.status == "accepted" and inv.contacts_revoked_at is None


def set_contacts_access(db: Session, cand: CandidateProfile, inv: Invitation, revoked: bool) -> Invitation:
    """Кандидат закрывает (или снова открывает) работодателю доступ к своим контактам. Переписка на платформе остаётся."""
    if inv.status != "accepted":
        raise AppError(409, "invalid_status", "Доступ к контактам управляется только по принятому приглашению")
    if revoked and inv.contacts_revoked_at is None:
        inv.contacts_revoked_at = utcnow()
        audit(db, cand.user_id, "contacts_revoked", "invitation", inv.id, employer_id=inv.employer_id)
        notify(db, inv.employer_id, "contacts_revoked", f"Кандидат {cand.public_code} закрыл доступ к контактам",
               f"«{inv.title}». Связаться можно через переписку на платформе.", f"/e/invitations/{inv.id}")
    elif not revoked and inv.contacts_revoked_at is not None:
        inv.contacts_revoked_at = None
        audit(db, cand.user_id, "contacts_revealed", "invitation", inv.id, employer_id=inv.employer_id)
        notify(db, inv.employer_id, "contacts_restored", f"Кандидат {cand.public_code} снова открыл контакты", f"«{inv.title}»",
               f"/e/invitations/{inv.id}")
    db.commit()
    return inv


def messages(db: Session, inv: Invitation, viewer_role: str) -> list[dict]:
    """Переписка по приглашению; входящие сообщения отмечаются прочитанными."""
    rows = db.scalars(select(Message).where(Message.invitation_id == inv.id).order_by(Message.created_at, Message.id)).all()
    now = utcnow()
    for m in rows:
        if m.sender_role != viewer_role and m.read_at is None:
            m.read_at = now
    db.commit()
    return [{"id": m.id, "from": m.sender_role, "mine": m.sender_role == viewer_role, "text": m.text,
             "created_at": m.created_at.isoformat(), "read": m.read_at is not None} for m in rows]


def post_message(db: Session, inv: Invitation, sender_id: int, sender_role: str, text: str) -> dict:
    if inv.status != "accepted":
        raise AppError(409, "invalid_status", "Переписка открывается после того, как кандидат принял приглашение")
    text = (text or "").strip()
    if not text:
        raise AppError(400, "empty_message", "Пустое сообщение")
    if len(text) > MESSAGE_MAX_LEN:
        raise AppError(400, "message_too_long", f"Сообщение длиннее {MESSAGE_MAX_LEN} символов")
    hour_ago = utcnow() - timedelta(hours=1)
    sent = db.scalar(select(func.count()).select_from(Message).where(Message.invitation_id == inv.id, Message.sender_id == sender_id,
                                                                     Message.created_at >= hour_ago)) or 0
    if sent >= MESSAGES_PER_HOUR:
        raise AppError(429, "too_many_messages", "Слишком много сообщений за час — попробуйте позже")
    m = Message(invitation_id=inv.id, sender_id=sender_id, sender_role=sender_role, text=text)
    db.add(m)
    if sender_role == "employer":
        notify(db, inv.candidate_id, "message", f"«{inv.company.name}»: новое сообщение", text[:140], f"/c/invitations/{inv.id}")
    else:
        cand = db.get(CandidateProfile, inv.candidate_id)
        notify(db, inv.employer_id, "message", f"Кандидат {cand.public_code if cand else ''}: новое сообщение", text[:140],
               f"/e/invitations/{inv.id}")
    db.commit()
    return {"id": m.id, "from": sender_role, "mine": True, "text": m.text, "created_at": m.created_at.isoformat(), "read": False}


def unread_counts(db: Session, inv_ids: list[int], viewer_role: str) -> dict[int, int]:
    if not inv_ids:
        return {}
    rows = db.execute(select(Message.invitation_id, func.count()).where(Message.invitation_id.in_(inv_ids), Message.sender_role != viewer_role,
                                                                       Message.read_at.is_(None)).group_by(Message.invitation_id)).all()
    return {i: n for i, n in rows}


def ats_candidate_payload(db: Session, inv: Invitation) -> dict:
    cand = db.get(CandidateProfile, inv.candidate_id)
    user = db.get(User, inv.candidate_id)
    return {
        "invitation_id": inv.id, "title": inv.title, "salary": {"from": inv.salary_from, "to": inv.salary_to, "currency": "RUB"},
        "candidate": {
            "code": cand.public_code, "full_name": cand.full_name, "email": user.email if user else None, "phone": cand.phone,
            "telegram": cand.telegram, "category": category_of(cand), "specialization": cand.specialization,
            "grade": cand.grade, "verified_skills": sorted({v["skill"] for v in cand.verified_skills or []}), "skills": cand.skills,
            "fsp": {"fsp_id": cand.fsp_id, "achievements": len(cand.achievements), "score": cand.fsp_score},
        },
    }


def invitation_view(inv: Invitation, for_role: str, cand: CandidateProfile | None = None) -> dict:
    comp = inv.company
    d = {
        "id": inv.id, "title": inv.title, "description": inv.description, "salary_from": inv.salary_from, "salary_to": inv.salary_to,
        "work_format": inv.work_format, "city": inv.city, "status": inv.status, "status_name": STATUS_NAMES.get(inv.status, inv.status),
        "stage": inv.stage, "stage_name": STAGE_NAMES.get(inv.stage) if inv.stage else None, "created_at": inv.created_at.isoformat(),
        "viewed_at": inv.viewed_at.isoformat() if inv.viewed_at else None,
        "responded_at": inv.responded_at.isoformat() if inv.responded_at else None, "expires_at": inv.expires_at.isoformat(),
        "decline_reason": inv.decline_reason, "decline_reason_name": DECLINE_REASONS.get(inv.decline_reason) if inv.decline_reason else None,
        "decline_comment": inv.decline_comment, "candidate_message": inv.candidate_message, "vacancy_id": inv.vacancy_id, "need_id": inv.need_id,
        "risk_flags": inv.risk_flags or [],
        "contacts_revoked_at": inv.contacts_revoked_at.isoformat() if inv.contacts_revoked_at else None,
        "contacts_open": contacts_open(inv), "chat_available": inv.status == "accepted",
        "company": {"id": comp.user_id, "name": comp.name, "industry": comp.industry, "city": comp.city, "website": comp.website,
                    "trust_score": comp.trust_score, "description": comp.description, "accent": comp.accent},
    }
    # способ связи с работодателем виден кандидату сразу — это часть условий приглашения
    d["contact_method"] = inv.contact_method
    if for_role == "employer":
        d["match_score"] = inv.match_score
        d["explanation"] = inv.explanation
        if cand:
            d["candidate"] = {"id": cand.user_id, "code": cand.public_code, "category": category_of(cand),
                              "grade": grade_name(cand.grade or cand.declared_grade), "grade_status": "confirmed" if cand.grade else "unconfirmed",
                              "headline": cand.headline}
    else:
        if inv.explanation:
            # кандидату показываем, почему его выбрали (без внутренних весов)
            d["why_you"] = (inv.explanation.get("reasons") or [])[:4]
    return d


def employer_analytics(db: Session, company: Company) -> dict:
    invs = db.scalars(select(Invitation).where(Invitation.employer_id == company.user_id)).all()
    by_status = Counter(i.status for i in invs)
    answered = by_status["accepted"] + by_status["declined"]
    reasons = Counter(i.decline_reason for i in invs if i.status == "declined")
    times = sorted(((i.responded_at - i.created_at).total_seconds() / 3600) for i in invs if i.responded_at)
    stages = Counter(i.stage for i in invs if i.status == "accepted")
    return {
        "total": len(invs),
        "by_status": dict(by_status),
        "acceptance_rate": round(by_status["accepted"] / answered, 3) if answered else None,
        "view_rate": round(sum(1 for i in invs if i.viewed_at) / len(invs), 3) if invs else None,
        "decline_reasons": [{"code": k, "name": DECLINE_REASONS.get(k, k), "count": v} for k, v in reasons.most_common()],
        "median_response_hours": round(times[len(times) // 2], 1) if times else None,
        "pipeline": {s: stages.get(s, 0) for s in STAGES},
    }
