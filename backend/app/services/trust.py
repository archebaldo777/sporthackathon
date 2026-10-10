"""Антифрод: индекс доверия работодателю и автоматические флаги риска вакансий/приглашений.

MVP-реализация (за рамками обязательного объёма ТЗ):
  * проверка контрольной суммы ИНН, совпадение домена корпоративной почты и сайта, полнота профиля;
  * поведенческие сигналы: доля принятых приглашений, жалобы кандидатов;
  * текстовые и ценовые флаги риска (предоплата, «серые» схемы, нереалистичная вилка);
  * лимит приглашений в сутки зависит от уровня доверия — массовая рассылка без репутации невозможна.
Полная концепция (ЕГРЮЛ/ФНС, ЕСИА для юрлиц, модерация, ML-детектор аномалий) — в docs/.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog.data import MARKET_SALARY
from app.core.config import settings
from app.models import Company, Invitation, Report, User, Vacancy

RISK_PATTERNS = [
    (r"предоплат|оплат\w* обучени|платн\w* стажировк|вступительн\w* взнос", "payment_request", "Требование оплаты от кандидата"),
    (r"криптовалют|инвестиц\w* в проект|пассивн\w* доход|финансов\w* пирамид", "scheme", "Признаки финансовой схемы"),
    (r"паспортн\w* данн|снилс|данн\w* карт|cvv|номер карт", "pii_request", "Запрос персональных или платёжных данных"),
    (r"без опыта.{0,40}(от|до)\s*\d{3}\s*(000|тыс)|заработок от \d+ в день", "too_good", "Нереалистично высокий доход без требований"),
    (r"только (в|через) (whatsapp|ватсап)|пишите в личку", "off_platform", "Перевод общения в сторонние каналы"),
]


def inn_valid(inn: str | None) -> bool:
    if not inn or not inn.isdigit() or len(inn) not in (10, 12):
        return False
    d = [int(x) for x in inn]

    def ctrl(coefs, digits):
        return sum(c * x for c, x in zip(coefs, digits)) % 11 % 10

    if len(inn) == 10:
        return ctrl([2, 4, 10, 3, 5, 9, 4, 6, 8], d) == d[9]
    return (ctrl([7, 2, 4, 10, 3, 5, 9, 4, 6, 8], d) == d[10]
            and ctrl([3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8], d) == d[11])


def _domain(url_or_email: str | None) -> str | None:
    if not url_or_email:
        return None
    if "@" in url_or_email:
        return url_or_email.split("@", 1)[1].lower()
    host = urlparse(url_or_email if "://" in url_or_email else f"https://{url_or_email}").hostname
    return host.lower().removeprefix("www.") if host else None


FREE_MAIL = {"gmail.com", "mail.ru", "yandex.ru", "ya.ru", "bk.ru", "inbox.ru", "list.ru", "outlook.com", "icloud.com", "rambler.ru"}


def risk_flags(text: str, salary_from: int | None, salary_to: int | None, spec: str | None, grades: list[str] | None) -> list[dict]:
    flags = []
    low = (text or "").lower()
    for pat, code, msg in RISK_PATTERNS:
        if re.search(pat, low):
            flags.append({"code": code, "message": msg})
    if salary_from and salary_to and spec in MARKET_SALARY and grades:
        med = max(MARKET_SALARY[spec].get(g, 0) for g in grades)
        if med and salary_to > 3 * med:
            flags.append({"code": "salary_unrealistic", "message": "Вилка более чем втрое выше рыночной медианы"})
        if med and salary_to < 0.35 * med:
            flags.append({"code": "salary_low", "message": "Вилка значительно ниже рынка"})
    if len((text or "").strip()) < 40:
        flags.append({"code": "too_short", "message": "Слишком короткое описание предложения"})
    return flags


def compute_trust(db: Session, company: Company) -> tuple[int, list[dict]]:
    factors: list[dict] = []
    score = 40
    user = db.get(User, company.user_id)
    site, mail = _domain(company.website), _domain(company.contact_email or (user.email if user else None))
    if site and mail and (mail == site or mail.endswith("." + site)) and mail not in FREE_MAIL:
        score += 15
        factors.append({"label": "Корпоративная почта совпадает с доменом сайта", "delta": 15})
    elif mail in FREE_MAIL:
        factors.append({"label": "Используется публичный почтовый сервис", "delta": 0})
    if inn_valid(company.inn):
        score += 10
        factors.append({"label": "ИНН указан и прошёл проверку контрольной суммы", "delta": 10})
    filled = sum(bool(x) for x in [company.description, company.website, company.industry, company.size, company.city])
    if filled >= 4:
        score += 10
        factors.append({"label": "Профиль компании заполнен", "delta": 10})
    created = company.created_at if company.created_at.tzinfo else company.created_at.replace(tzinfo=timezone.utc)
    age_bonus = min(10, (datetime.now(timezone.utc) - created).days // 9)
    if age_bonus:
        score += age_bonus
        factors.append({"label": "Возраст аккаунта", "delta": age_bonus})
    total = db.scalar(select(func.count()).select_from(Invitation).where(Invitation.employer_id == company.user_id,
                                                                        Invitation.status.in_(["accepted", "declined"]))) or 0
    acc = db.scalar(select(func.count()).select_from(Invitation).where(Invitation.employer_id == company.user_id,
                                                                      Invitation.status == "accepted")) or 0
    if total >= 5:
        rate = acc / total
        delta = 10 if rate >= 0.3 else (4 if rate >= 0.15 else -5)
        score += delta
        factors.append({"label": f"Доля принятых приглашений {round(rate * 100)}%", "delta": delta})
    reports = db.scalar(select(func.count()).select_from(Report).where(Report.employer_id == company.user_id, Report.status == "open")) or 0
    if reports:
        delta = -min(45, 15 * reports)
        score += delta
        factors.append({"label": f"Жалобы кандидатов: {reports}", "delta": delta})
    flagged = db.scalar(select(func.count()).select_from(Vacancy).where(Vacancy.employer_id == company.user_id,
                                                                       func.jsonb_array_length(Vacancy.risk_flags) > 0)) if db.bind.dialect.name == "postgresql" else 0
    if flagged:
        score -= 10
        factors.append({"label": "Есть вакансии с признаками риска", "delta": -10})
    return max(0, min(100, score)), factors


def tier(score: int) -> str:
    return "high" if score >= 70 else ("mid" if score >= 45 else "low")


def daily_limit(score: int) -> int:
    return {"low": settings.invitations_daily_limit_low, "mid": settings.invitations_daily_limit_mid,
            "high": settings.invitations_daily_limit_high}[tier(score)]


def refresh_trust(db: Session, company: Company) -> int:
    company.trust_score, company.trust_factors = compute_trust(db, company)
    return company.trust_score
