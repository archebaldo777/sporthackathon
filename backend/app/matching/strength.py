"""Сила подтверждённого профиля — ранжирование кандидатов внутри категории (специализация × грейд).

strength = 100 · (0.55·T + 0.20·F + 0.15·A + 0.10·P)
  T — положение θ внутри полосы грейда (результат адаптивного теста),
  F — сила достижений ФСП (0, если истории ФСП нет — профиль не штрафуется, а не получает бонус),
  A — актуальность: свежесть активности и оценки регулярных задач,
  P — полнота профиля.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from app.catalog.data import GRADE_ORDER, GRADES
from app.models import CandidateProfile

W_TEST, W_FSP, W_ACTIVITY, W_PROFILE = 0.55, 0.20, 0.15, 0.10


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def band_position(theta: float | None, grade: str | None) -> float:
    """0 — у нижнего порога грейда, 1 — у порога следующего грейда."""
    if theta is None or grade is None:
        return 0.0
    lo = GRADES[grade]["cut"]
    idx = GRADE_ORDER.index(grade)
    hi = GRADES[GRADE_ORDER[idx + 1]]["cut"] if idx + 1 < len(GRADE_ORDER) else lo + 1.5
    return max(0.0, min(1.0, (theta - lo) / (hi - lo)))


def activity_score(cand: CandidateProfile, now: datetime) -> float:
    last = _aware(cand.last_activity_at)
    fresh = math.exp(-((now - last).days if last else 365) / 60.0)
    task = ((cand.task_score or 0) - 1) / 4 if cand.tasks_done else 0.0
    volume = min(1.0, (cand.tasks_done or 0) / 4)
    return round(0.55 * fresh + 0.3 * task + 0.15 * volume, 4)


def completeness(cand: CandidateProfile) -> float:
    checks = [bool(cand.full_name), bool(cand.headline), bool(cand.skills), bool(cand.experience), bool(cand.about),
              cand.salary_from is not None, bool(cand.work_formats), bool(cand.city), bool(cand.soft_skills), bool(cand.education)]
    return sum(checks) / len(checks)


def strength_parts(cand: CandidateProfile, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    return {
        "test": round(band_position(cand.theta, cand.grade), 4),
        "fsp": round(cand.fsp_score or 0.0, 4),
        "activity": activity_score(cand, now),
        "profile": round(completeness(cand), 4),
    }


def strength_for(cand: CandidateProfile, theta: float | None, grade: str | None, fsp: float, now: datetime | None = None) -> float:
    """Сила профиля в дополнительной категории: свой результат теста и актуальность ФСП, общие активность и полнота."""
    p = strength_parts(cand, now)
    return round(100 * (W_TEST * band_position(theta, grade) + W_FSP * fsp + W_ACTIVITY * p["activity"] + W_PROFILE * p["profile"]), 2)


def refresh_strength(cand: CandidateProfile, now: datetime | None = None) -> float:
    p = strength_parts(cand, now)
    cand.strength = round(100 * (W_TEST * p["test"] + W_FSP * p["fsp"] + W_ACTIVITY * p["activity"] + W_PROFILE * p["profile"]), 2)
    return cand.strength
