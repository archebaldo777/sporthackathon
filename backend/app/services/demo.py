"""Демо-стенд для жюри: общие демо-аккаунты и «чистые» аккаунты для самостоятельного прохождения.

Демо-аккаунтами (*@draft.demo) одновременно пользуются несколько экспертов. Необратимые действия — удаление аккаунта и
отвязка ФСП ID — у них отключены: один эксперт не должен сломать сценарий остальным (проверить удаление можно на своём
аккаунте). Аккаунты для прохождения пути с нуля (newbie, expert1–5) после использования можно начать заново: профиль,
опрос, попытки теста, категории, приглашения и отклики удаляются каскадом и создаётся пустой профиль. Вне демо-режима
ничего из этого не действует.
"""
from __future__ import annotations

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.models import CandidateProfile, Consent, Notification, User
from app.services.common import audit, record_consent
from app.testing.service import expert_mode

DEMO_DOMAIN = "@draft.demo"


def shared_demo(email: str | None) -> bool:
    return settings.demo_mode and (email or "").lower().endswith(DEMO_DOMAIN)


def guard_shared(email: str | None, action: str) -> None:
    """403 для необратимого действия над общим демо-аккаунтом."""
    if shared_demo(email):
        raise AppError(403, "demo_account_protected",
                       f"Это общий демо-аккаунт для жюри: {action} отключено, чтобы не сломать сценарий другим экспертам. "
                       "Проверьте на своём аккаунте — зарегистрируйтесь, письмо с кодом придёт в демо-почту.")


def resettable(email: str | None) -> bool:
    return expert_mode(email)


def reset_candidate(db: Session, c: CandidateProfile) -> None:
    """Вернуть аккаунт newbie / expertN к состоянию «только что создан» (как при первичной генерации данных)."""
    email = c.user.email if c.user else None
    if not resettable(email):
        raise AppError(403, "demo_reset_unavailable", "Начать заново можно только демо-аккаунтам newbie и expert1–5 на демо-стенде")
    uid, code = c.user_id, c.public_code
    # профиль и всё, что на него ссылается (опрос, попытки, категории, приглашения, отклики, задачи, достижения ФСП),
    # удаляется каскадом в БД; уведомления и согласия — по пользователю
    db.execute(delete(CandidateProfile).where(CandidateProfile.user_id == uid))
    db.execute(delete(Notification).where(Notification.user_id == uid))
    db.execute(delete(Consent).where(Consent.user_id == uid))
    db.execute(update(User).where(User.id == uid).values(fsp_sub=None))
    db.flush()
    db.expunge_all()  # в сессии остался удалённый профиль с тем же ключом
    db.add(CandidateProfile(user_id=uid, public_code=code, visible=True))
    for kind in ("pd_processing", "profile_publication"):
        record_consent(db, uid, kind, True)
    audit(db, uid, "demo_account_reset", "user", uid)
    db.commit()
