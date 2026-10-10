"""Несколько категорий у одного кандидата.

Основная категория хранится в профиле (по ней проходит тест), дополнительные — в CandidateCategory. Сделать
дополнительную основной = поменять поля категорий местами: у каждой категории сохраняются свой грейд, результат теста,
блокировка смены грейда и подтверждённые навыки. Грейд в любой категории присваивается только тестом.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog.data import GRADES, SPECIALIZATIONS, category_label
from app.core.db import utcnow
from app.core.errors import AppError
from app.fsp.scoring import fsp_score
from app.matching.strength import refresh_strength
from app.models import CandidateCategory, CandidateProfile, GradeChange, TestAttempt
from app.models.candidate import CATEGORY_FIELDS

MAX_EXTRA = 2  # основная + до двух дополнительных


def _aware(dt: datetime | None) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=utcnow().tzinfo)


def category_view(src, main: bool) -> dict:
    """Описание категории для кабинета кандидата и карточки работодателя (src — профиль или CandidateCategory)."""
    grade = src.grade or src.declared_grade
    return {
        "specialization": src.specialization, "grade": src.grade, "declared_grade": src.declared_grade,
        "label": category_label(src.specialization, grade), "confirmed": src.grade is not None, "main": main,
        "lang": src.primary_lang, "framework": src.framework,
        "grade_confirmed_at": _aware(src.grade_confirmed_at).isoformat() if src.grade_confirmed_at else None,
        "locked_until": _aware(src.grade_locked_until).isoformat() if src.grade_locked_until else None,
    }


def all_categories(c: CandidateProfile) -> list[dict]:
    out = [category_view(c, True)] if c.specialization and (c.grade or c.declared_grade) else []
    return out + [category_view(x, False) for x in c.extra_categories]


def add_category(db: Session, c: CandidateProfile, spec: str, declared_grade: str, lang: str | None = None,
                 framework: str | None = None) -> CandidateCategory:
    if spec not in SPECIALIZATIONS:
        raise AppError(400, "invalid_specialization", "Неизвестная специализация")
    if declared_grade not in GRADES:
        raise AppError(400, "invalid_grade", "Неизвестный грейд")
    if not c.specialization:
        raise AppError(409, "survey_required", "Сначала пройдите опрос по основной специализации")
    if spec == c.specialization or any(x.specialization == spec for x in c.extra_categories):
        raise AppError(409, "category_exists", "Эта специализация уже есть в ваших категориях")
    if len(c.extra_categories) >= MAX_EXTRA:
        raise AppError(409, "too_many_categories", f"Можно добавить не больше {MAX_EXTRA} дополнительных категорий")
    info = SPECIALIZATIONS[spec]
    row = CandidateCategory(
        direction=info["direction"], specialization=spec, declared_grade=declared_grade,
        primary_lang=lang if lang in info["langs"] else info["langs"][0],
        framework=framework if spec == "frontend" else None, topic_scores={}, verified_skills=[],
    )
    c.extra_categories.append(row)
    c.updated_at = utcnow()  # версия банка кандидатов — сбрасывает кэш поиска и карты категорий
    db.flush()
    return row


def remove_category(db: Session, c: CandidateProfile, spec: str) -> None:
    row = next((x for x in c.extra_categories if x.specialization == spec), None)
    if not row:
        raise AppError(404, "not_found", "Дополнительная категория не найдена")
    if row.grade:
        db.add(GradeChange(candidate_id=c.user_id, specialization=spec, from_grade=row.grade, to_grade="none",
                           reason="category_removed", created_at=utcnow()))
    c.extra_categories.remove(row)
    c.updated_at = utcnow()
    db.flush()


def make_main(db: Session, c: CandidateProfile, spec: str) -> None:
    """Сделать дополнительную категорию основной (например, чтобы пройти по ней тест): поля категорий меняются местами."""
    row = next((x for x in c.extra_categories if x.specialization == spec), None)
    if not row:
        raise AppError(404, "not_found", "Дополнительная категория не найдена")
    from app.testing.service import expire_stale  # локальный импорт: сервис тестирования импортирует модели профиля

    expire_stale(db, c)
    if db.scalar(select(TestAttempt.id).where(TestAttempt.candidate_id == c.user_id, TestAttempt.status == "in_progress").limit(1)):
        raise AppError(409, "attempt_in_progress", "Сначала завершите начатый тест")
    for f in CATEGORY_FIELDS:
        main_value, extra_value = getattr(c, f), getattr(row, f)
        setattr(c, f, extra_value)
        setattr(row, f, main_value)
    c.topic_scores, c.verified_skills = c.topic_scores or {}, c.verified_skills or []
    c.fsp_score = fsp_score(c.achievements, spec=c.specialization)  # актуальность дисциплин ФСП — к новой основной
    c.updated_at = utcnow()
    refresh_strength(c)
    db.flush()
