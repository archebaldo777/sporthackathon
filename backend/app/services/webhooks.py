"""Исходящие вебхуки для интеграции с ATS работодателя (Huntflow, Potok, E-Staff и др.).

Каждое событие подписывается HMAC-SHA256 секретом вебхука (заголовок X-Draft-Signature), доставка — с повторами.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time

import httpx
from fastapi import BackgroundTasks
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Webhook, WebhookDelivery

EVENTS = {
    "invitation.accepted": "Кандидат принял приглашение (контакты раскрыты)",
    "invitation.declined": "Кандидат отклонил приглашение",
    "invitation.stage_changed": "Этап найма изменён на платформе (знакомство, интервью, оффер, выход)",
    "application.created": "Новый отклик на вакансию",
    "application.status_changed": "Статус отклика изменён на платформе",
    "task.submitted": "Кандидат прислал решение задачи",
}


def _deliver(webhook_id: int, event: str, payload: dict) -> None:
    db = SessionLocal()
    try:
        wh = db.get(Webhook, webhook_id)
        if not wh or not wh.active:
            return
        body = json.dumps({"event": event, "sent_at": int(time.time()), "data": payload}, ensure_ascii=False, default=str)
        sig = hmac.new(wh.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        d = WebhookDelivery(webhook_id=wh.id, event=event, payload=payload, attempts=0)
        db.add(d)
        for attempt in range(3):
            d.attempts = attempt + 1
            try:
                r = httpx.post(wh.url, content=body, timeout=3, headers={"Content-Type": "application/json", "X-Draft-Event": event,
                                                                           "X-Draft-Signature": f"sha256={sig}"})
                d.status_code, d.ok = r.status_code, 200 <= r.status_code < 300
                if d.ok:
                    break
            except httpx.HTTPError as exc:
                d.error = str(exc)[:480]
            time.sleep(0.3 * (2**attempt))
        db.commit()
    finally:
        db.close()


def emit(bg: BackgroundTasks | None, employer_id: int, event: str, payload: dict) -> None:
    db = SessionLocal()
    try:
        hooks = db.scalars(select(Webhook).where(Webhook.employer_id == employer_id, Webhook.active.is_(True))).all()
        targets = [h.id for h in hooks if event in (h.events or [])]
    finally:
        db.close()
    for hid in targets:
        if bg is not None:
            bg.add_task(_deliver, hid, event, payload)
        else:
            _deliver(hid, event, payload)
