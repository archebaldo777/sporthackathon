"""Оценка достижений ФСП для ранжирования внутри категории (на грейд не влияет).

Все соревнования и дисциплины ФСП равноценны: уровень соревнования («чемпионат России» или хакатон) вес не меняет,
рейтинга дисциплин нет — так рекомендовали постановщики задачи. Учитываются результативность, число соревнований и
актуальность дисциплины для специализации (идея организаторов: результат специалиста по ИБ на соревновании по ИБ
релевантнее, чем по робототехнике):

  вклад результата = фактор результата (победитель 1.0, призёр 0.85/0.75, финалист топ-10% 0.55 … участник 0.2) × давность
                     × актуальность (профильная дисциплина 1.0, смежная 0.8, непрофильная 0.6 — catalog.DISCIPLINE_FIT)
  Σ = Σ(вклады призовых и финальных результатов) + min(Σ(вклады участий без результата), PARTICIPATION_CAP)
  fsp_score = 1 − exp(−Σ / SCALE)

В профиле актуальность считается к специализации кандидата, в подборке — к специализации и навыкам запроса работодателя.

Ограничение участий (PARTICIPATION_CAP) не даёт «набить» профиль онлайн-явками: сколько угодно участий без результата
весят меньше одного призового места. Давность: половина веса за 2 года (свежий результат котируется сильнее).
Отсутствие истории ФСП даёт fsp_score = 0 и не исключает кандидата из выдачи.
"""
from __future__ import annotations

import math
from datetime import date

from app.catalog.data import DISCIPLINE_FIT, discipline_fit

PARTICIPATION_FACTOR = 0.3  # результат ниже этого порога — участие без призового/финального результата
PARTICIPATION_CAP = 0.6
SCALE = 2.0
HALF_LIFE_YEARS = 2.0


def place_factor(place: int | None, participants: int | None, percentile: float | None) -> float:
    if place == 1:
        return 1.0
    if place == 2:
        return 0.85
    if place == 3:
        return 0.75
    pct = percentile
    if pct is None and place and participants:
        pct = 1 - (place - 1) / max(1, participants)
    if pct is None:
        return 0.2
    if pct >= 0.9:
        return 0.55
    if pct >= 0.75:
        return 0.4
    if pct >= 0.5:
        return 0.28
    return 0.18


def recency(event_date: date, today: date | None = None) -> float:
    years = max(0.0, ((today or date.today()) - event_date).days / 365.25)
    return 0.5 ** (years / HALF_LIFE_YEARS)


def result_weight(place: int | None, participants: int | None, percentile: float | None, event_date: date,
                  today: date | None = None) -> float:
    return place_factor(place, participants, percentile) * recency(event_date, today)


def is_prize(place: int | None, participants: int | None, percentile: float | None) -> bool:
    """Призовой или финальный результат (а не участие без результата)."""
    return place_factor(place, participants, percentile) >= PARTICIPATION_FACTOR


def aggregate(contributions: list[tuple[float, bool]]) -> float:
    """contributions — (вклад результата, призовой ли). Участия без результата ограничены потолком."""
    prize = sum(w for w, p in contributions if p)
    participation = sum(w for w, p in contributions if not p)
    return round(1 - math.exp(-(prize + min(participation, PARTICIPATION_CAP)) / SCALE), 4)


def fsp_score(achievements: list, today: date | None = None, spec: str | None = None) -> float:
    """Сила достижений ФСП; со spec — с учётом актуальности дисциплин для этой специализации."""
    return aggregate([
        (result_weight(a.place, a.participants, a.percentile, a.event_date, today)
         * DISCIPLINE_FIT[discipline_fit(a.discipline, spec)], is_prize(a.place, a.participants, a.percentile))
        for a in achievements
    ])


def result_title(place: int | None, percentile: float | None) -> str:
    if place == 1:
        return "Победитель"
    if place in (2, 3):
        return "Призёр"
    if percentile is not None and percentile >= 0.9:
        return "Финалист (топ-10%)"
    return "Участник"
