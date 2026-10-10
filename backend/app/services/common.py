"""Общие сервисы: почта, уведомления, аудит, согласия (152-ФЗ)."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from email.utils import make_msgid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AuditLog, Consent, Notification

log = logging.getLogger("draft")

CONSENT_VERSION = "1.0"
CONSENT_KINDS = {
    "pd_processing": "Согласие на обработку персональных данных (152-ФЗ)",
    "profile_publication": "Согласие на публикацию профиля для работодателей платформы",
    "fsp_data": "Согласие на получение данных о достижениях из реестра ФСП",
    "marketing": "Согласие на получение новостей платформы",
    "guardian_consent": "Согласие законного представителя на обработку персональных данных несовершеннолетнего (15–17 лет)",
}


def send_email(to: str, subject: str, text: str, html: str | None = None) -> bool:
    """Отправка письма через SMTP (в docker-compose — Mailpit). Ошибка доставки не ломает бизнес-операцию."""
    msg = EmailMessage()
    msg["From"] = settings.mail_from
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain="draft.local")
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as s:
            if settings.smtp_tls:
                s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("SMTP недоступен (%s). Письмо для %s: %s\n%s", exc, to, subject, text)
        return False


def email_layout(title: str, body_html: str, cta: tuple[str, str] | None = None) -> str:
    button = (
        f'<p style="margin:28px 0"><a href="{cta[1]}" style="background:#402FFF;color:#fff;padding:12px 22px;border-radius:8px;'
        f'text-decoration:none;font-weight:600">{cta[0]}</a></p>' if cta else ""
    )
    # фирменный стиль ФСП: графитовая шапка #1B1C21, «ДРАФТ_» с красным курсором, акцент #402FFF
    return (
        '<div style="font-family:Inter,Arial,sans-serif;max-width:560px;margin:0 auto;color:#1b1c21">'
        '<div style="background:#1b1c21;color:#ededed;padding:18px 24px;border-radius:10px 10px 0 0;'
        'font-family:\'JetBrains Mono\',Consolas,monospace;font-weight:700;font-size:18px;letter-spacing:2px">'
        'ДРАФТ<span style="color:#ec1d35">_</span>'
        '<span style="font-weight:400;font-size:11px;letter-spacing:1.5px;color:#9b9c9e;margin-left:12px">ПРОЕКТ ФСП · ИТ-НАЙМ</span></div>'
        '<div style="height:4px;background:linear-gradient(90deg,#402fff 0 70%,#ec1d35 70% 100%)"></div>'
        f'<div style="padding:8px 24px 24px"><h1 style="font-size:22px;margin:24px 0 12px">{title}</h1>{body_html}{button}'
        '<p style="color:#62636b;font-size:12px;margin-top:32px">Платформа ИТ-найма с верифицированным профилем участника '
        'Федерации спортивного программирования России.</p></div></div>'
    )


def notify(db: Session, user_id: int, kind: str, title: str, body: str | None = None, link: str | None = None,
           email_to: str | None = None) -> Notification:
    n = Notification(user_id=user_id, kind=kind, title=title, body=body, link=link)
    db.add(n)
    if email_to:
        url = f"{settings.public_url}{link}" if link else settings.public_url
        send_email(email_to, title, f"{body or ''}\n\n{url}", email_layout(title, f"<p>{body or ''}</p>", ("Открыть", url)))
    return n


def audit(db: Session, actor_id: int | None, action: str, target_type: str | None = None, target_id: int | None = None,
          **meta) -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, target_type=target_type, target_id=target_id, meta=meta or None))


def record_consent(db: Session, user_id: int, kind: str, granted: bool, ip: str | None = None, ua: str | None = None) -> Consent:
    c = Consent(user_id=user_id, kind=kind, version=CONSENT_VERSION, granted=granted, ip=ip, user_agent=(ua or "")[:250])
    db.add(c)
    return c


def current_consents(db: Session, user_id: int) -> dict[str, bool]:
    rows = db.query(Consent).filter(Consent.user_id == user_id).order_by(Consent.created_at.asc(), Consent.id.asc()).all()
    state = {k: False for k in CONSENT_KINDS}
    for r in rows:
        state[r.kind] = r.granted
    return state
