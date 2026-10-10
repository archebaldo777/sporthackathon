"""Регулярные короткие задачи от работодателей.

Раз в N дней (по умолчанию 7) система назначает кандидату задачу работодателя его категории: решить её или
предложить подход. Ответ получает автоматическую предварительную оценку по скрытой рубрике (ключевые пункты)
и финальную оценку работодателя 1–5. Решение, почти совпадающее с чужим ответом на ту же задачу, помечается для
работодателя (проверка на списывание). Результат обновляет «актуальность» профиля и служит свежим сигналом
для работодателей; автор сильного решения — естественный кандидат для приглашения.
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import BackgroundTasks
from rapidfuzz import fuzz
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import utcnow
from app.core.errors import AppError
from app.matching.strength import refresh_strength
from app.models import CandidateProfile, EmployerTask, HiringNeed, TaskAssignment
from app.services import webhooks
from app.services.common import notify

PRIOR_MEAN, PRIOR_WEIGHT = 3.0, 2.0
COPY_SIMILARITY = 90  # token_set_ratio: перестановка слов и мелкие правки не скрывают совпадение
COPY_MIN_LEN = 80  # короткие ответы похожи естественно — не сравниваем


def similar_answers(db: Session, a: TaskAssignment) -> list[dict]:
    """Ранее отправленные решения той же задачи, почти совпадающие с этим (возможное списывание)."""
    if len(a.answer or "") < COPY_MIN_LEN:
        return []
    out = []
    for other in db.scalars(select(TaskAssignment).where(TaskAssignment.task_id == a.task_id, TaskAssignment.id != a.id,
                                                         TaskAssignment.answer.is_not(None))).all():
        if len(other.answer) < COPY_MIN_LEN:
            continue
        sim = fuzz.token_set_ratio(a.answer.lower(), other.answer.lower())
        if sim >= COPY_SIMILARITY:
            code = db.get(CandidateProfile, other.candidate_id).public_code
            out.append({"assignment_id": other.id, "candidate_code": code, "similarity": round(sim)})
    return sorted(out, key=lambda x: -x["similarity"])[:5]


def _aware(dt):
    from datetime import timezone

    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def expire(db: Session, cand_id: int) -> None:
    now = utcnow()
    for a in db.scalars(select(TaskAssignment).where(TaskAssignment.candidate_id == cand_id, TaskAssignment.status == "assigned")).all():
        if _aware(a.due_at) < now:
            a.status = "expired"
    db.flush()


def active_assignment(db: Session, cand_id: int) -> TaskAssignment | None:
    return db.scalar(select(TaskAssignment).where(TaskAssignment.candidate_id == cand_id, TaskAssignment.status == "assigned"))


def pick_task(db: Session, cand: CandidateProfile) -> EmployerTask | None:
    done = {r[0] for r in db.execute(select(TaskAssignment.task_id).where(TaskAssignment.candidate_id == cand.user_id)).all()}
    tasks = [t for t in db.scalars(select(EmployerTask).where(EmployerTask.active.is_(True), EmployerTask.specialization == cand.specialization)).all()
             if t.id not in done and (not t.grades or cand.grade in t.grades)]
    if not tasks:
        return None
    hiring = {r[0] for r in db.execute(select(HiringNeed.employer_id).where(HiringNeed.specialization == cand.specialization,
                                                                           HiringNeed.status == "active")).all()}
    load = dict(db.execute(select(TaskAssignment.task_id, func.count()).group_by(TaskAssignment.task_id)).all())
    # приоритет: компании, которые сейчас ищут людей этой категории; затем — наименее загруженные задачи
    tasks.sort(key=lambda t: (t.employer_id not in hiring, load.get(t.id, 0), t.id))
    return tasks[0]


def assign_if_due(db: Session, cand: CandidateProfile, force: bool = False) -> TaskAssignment | None:
    if not cand.grade or not cand.specialization:
        return None
    expire(db, cand.user_id)
    cur = active_assignment(db, cand.user_id)
    if cur:
        return cur
    last = db.scalar(select(func.max(TaskAssignment.assigned_at)).where(TaskAssignment.candidate_id == cand.user_id))
    if not force and last and utcnow() - _aware(last) < timedelta(days=settings.task_assign_interval_days):
        return None
    task = pick_task(db, cand)
    if not task:
        return None
    a = TaskAssignment(task_id=task.id, candidate_id=cand.user_id, status="assigned", assigned_at=utcnow(),
                       due_at=utcnow() + timedelta(days=settings.task_due_days))
    db.add(a)
    db.flush()
    notify(db, cand.user_id, "task", "Новая задача от работодателя", f"«{task.title}» от {task.company.name}. Срок — {settings.task_due_days} дней.",
           "/c/tasks")
    db.commit()
    return a


def auto_score(task: EmployerTask, answer: str) -> tuple[float, dict]:
    """Предварительная оценка: какая доля ключевых пунктов рубрики раскрыта в ответе (нечёткое сравнение)."""
    points = task.key_points or []
    if not points:
        return (0.5 if len(answer.strip()) > 200 else 0.25), {"covered": [], "missing": [], "note": "Рубрика не задана"}
    low = answer.lower()
    covered, missing = [], []
    for p in points:
        stems = [w[:6] for w in p.lower().split() if len(w) > 3] or [p.lower()]
        hit = all(st in low for st in stems) or fuzz.partial_ratio(p.lower(), low) >= 82
        (covered if hit else missing).append(p)
    length_ok = len(answer.strip()) >= 120
    score = len(covered) / len(points) * (1.0 if length_ok else 0.7)
    return round(score, 3), {"covered": covered, "missing": missing, "length_ok": length_ok}


def submit(db: Session, bg: BackgroundTasks | None, cand: CandidateProfile, a: TaskAssignment, answer: str) -> TaskAssignment:
    if a.candidate_id != cand.user_id:
        raise AppError(404, "not_found", "Задача не найдена")
    expire(db, cand.user_id)
    if a.status != "assigned":
        raise AppError(409, "invalid_status", "Задача уже закрыта")
    if len(answer.strip()) < 30:
        raise AppError(400, "too_short", "Опишите решение или подход подробнее (не менее 30 символов)")
    a.answer, a.submitted_at, a.status = answer.strip(), utcnow(), "submitted"
    a.auto_score, details = auto_score(a.task, a.answer)
    a.auto_details = {**details, "similar": similar_answers(db, a)}
    cand.last_activity_at = utcnow()
    refresh_strength(cand)
    notify(db, a.task.employer_id, "task_submitted", "Новое решение задачи", f"«{a.task.title}» — кандидат {cand.public_code}", f"/e/tasks/{a.task_id}")
    db.commit()
    webhooks.emit(bg, a.task.employer_id, "task.submitted", {"task_id": a.task_id, "assignment_id": a.id, "candidate_code": cand.public_code})
    return a


def skip(db: Session, cand: CandidateProfile, a: TaskAssignment) -> None:
    if a.candidate_id != cand.user_id or a.status != "assigned":
        raise AppError(409, "invalid_status", "Задача уже закрыта")
    a.status = "skipped"
    db.commit()


def review(db: Session, task: EmployerTask, a: TaskAssignment, score: int, feedback: str | None) -> TaskAssignment:
    if a.task_id != task.id:
        raise AppError(404, "not_found", "Решение не найдено")
    if a.status not in ("submitted", "reviewed"):
        raise AppError(409, "invalid_status", "Решение ещё не отправлено")
    if not 1 <= score <= 5:
        raise AppError(400, "invalid_score", "Оценка от 1 до 5")
    a.score, a.feedback, a.reviewed_at, a.status = score, feedback, utcnow(), "reviewed"
    cand = db.get(CandidateProfile, a.candidate_id)
    recompute_task_score(db, cand)
    notify(db, cand.user_id, "task_reviewed", f"Работодатель оценил решение: {score}/5", f"«{task.title}»", "/c/tasks")
    db.commit()
    return a


def recompute_task_score(db: Session, cand: CandidateProfile) -> None:
    scores = [r[0] for r in db.execute(select(TaskAssignment.score).where(TaskAssignment.candidate_id == cand.user_id,
                                                                          TaskAssignment.status == "reviewed")).all()]
    cand.tasks_done = len(scores)
    # байесовское среднее: одна случайная «пятёрка» не перевешивает
    cand.task_score = round((PRIOR_MEAN * PRIOR_WEIGHT + sum(scores)) / (PRIOR_WEIGHT + len(scores)), 2) if scores else None
    cand.last_activity_at = utcnow()
    refresh_strength(cand)
