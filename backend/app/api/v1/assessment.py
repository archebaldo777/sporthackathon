"""Тестирование кандидата: допуск, адаптивная попытка, ответы, результат, повышение грейда."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import current_candidate
from app.core.errors import COMMON_ERRORS, AppError, err
from app.models import CandidateProfile
from app.schemas import AnswerIn, ExpertAnswerIn, ExpertSimulateIn, StartAttemptIn
from app.testing import service as svc
from app.testing.blueprint import blueprint_view

router = APIRouter(prefix="/candidate/assessment", tags=["Тестирование"], responses=COMMON_ERRORS)


@router.get("/eligibility", summary="На какие грейды можно пройти тест сейчас (с учётом ограничений по частоте)")
def get_eligibility(c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    svc.expire_stale(db, c)
    res = svc.eligibility(db, c)
    if c.specialization:
        ctx = svc.candidate_ctx(c)
        from app.testing.blueprint import base_blueprint

        res["plan"] = blueprint_view(base_blueprint(c.specialization), ctx, c.specialization, c.declared_grade or "middle",
                                     svc.cat_config().max_items)
        res["config"] = {"min_items": svc.cat_config().min_items, "max_items": svc.cat_config().max_items, "minutes": svc.ATTEMPT_MINUTES}
    res["current_grade"] = c.grade
    res["declared_grade"] = c.declared_grade
    return res


@router.post("/attempts", status_code=201, summary="Начать тест на выбранный грейд (возвращает первое задание)",
             responses={**err(409, "Тест на этот грейд сейчас недоступен")})
def start(body: StartAttemptIn, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    a = svc.start_attempt(db, c, body.target_grade)
    item = svc.current_item(a)
    return {"attempt_id": a.id, "item": svc.item_view(a, item) if item else None}


def _own(db: Session, c: CandidateProfile, attempt_id: int):
    a = svc.resolve_attempt(db, attempt_id)
    if a.candidate_id != c.user_id:
        raise AppError(404, "not_found", "Попытка не найдена")
    return a


@router.get("/attempts/{attempt_id}", summary="Состояние попытки: текущее задание или итог")
def get_attempt(attempt_id: int, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    a = _own(db, c, attempt_id)
    if a.status == "in_progress":
        item = svc.current_item(a)
        if item:
            return {"finished": False, "item": svc.item_view(a, item)}
    return {"finished": True, "result": svc.attempt_result(a)}


@router.post("/attempts/{attempt_id}/answer", summary="Ответ на текущее задание; возвращает следующее задание или итог",
             responses={**err(409, "Задание неактуально или попытка завершена")})
def answer(attempt_id: int, body: AnswerIn, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    a = _own(db, c, attempt_id)
    return svc.submit_answer(db, c, a, body.item_id, body.response, body.time_ms, body.events)


@router.post("/attempts/{attempt_id}/expert/answer", include_in_schema=True,
             summary="Режим эксперта (демо): ответить на текущее задание верно или неверно",
             description="Только на демо-стенде и только для аккаунтов expertN@draft.demo и newbie@draft.demo. Ключ ответа не передаётся клиенту.",
             responses=err(403, "Режим эксперта недоступен"))
def expert_answer(attempt_id: int, body: ExpertAnswerIn, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    _expert_only(c)
    return svc.expert_answer(db, c, _own(db, c, attempt_id), body.item_id, body.correct)


@router.post("/attempts/{attempt_id}/expert/simulate",
             summary="Режим эксперта (демо): пройти оставшиеся задания как кандидат уровня θ (модель IRT 3PL)",
             description="Для проверки разделяющей силы и воспроизводимости: θ ≈ −1.5 стажёр, −0.5 junior, 0.5 middle, 1.5 senior.",
             responses=err(403, "Режим эксперта недоступен"))
def expert_simulate(attempt_id: int, body: ExpertSimulateIn, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    _expert_only(c)
    return svc.expert_simulate(db, c, _own(db, c, attempt_id), body.theta, body.seed)


def _expert_only(c: CandidateProfile) -> None:
    if not svc.expert_mode(c.user.email if c.user else None):
        raise AppError(403, "expert_mode_disabled", "Режим эксперта доступен только демо-аккаунтам экспертов на демо-стенде")


@router.post("/attempts/{attempt_id}/finish", summary="Досрочно завершить попытку (оставшиеся задания не засчитываются)")
def finish(attempt_id: int, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    a = _own(db, c, attempt_id)
    svc.abandon(db, c, a)
    return {"finished": True, "result": svc.attempt_result(a)}


@router.post("/attempts/{attempt_id}/upgrade", status_code=201,
             summary="Начать отдельный тест на грейд выше по предложению из результата (без ожидания 90 дней, вне лимита попыток)",
             description="После уверенного прохождения система предлагает тест на следующий грейд. Повышение без теста не выполняется: "
                         "грейд меняется, только если пройден этот отдельный тест. Предложение действует 14 дней и используется один раз.",
             responses=err(409, "Предложение недоступно или истекло"))
def upgrade(attempt_id: int, c: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    a = _own(db, c, attempt_id)
    new = svc.start_upgrade(db, c, a)
    return {"attempt_id": new.id, "target_grade": new.target_grade}
