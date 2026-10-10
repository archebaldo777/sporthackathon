"""Сервис тестирования: попытки, выдача заданий, проверка ответов, присвоение грейда, ограничения по частоте."""
from __future__ import annotations

import hashlib
import random
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog.data import COMPETENCIES, GRADE_ORDER, GRADES, SPECIALIZATIONS, competency_skills, grade_name
from app.core.config import settings
from app.core.db import utcnow
from app.core.errors import AppError
from app.models import CandidateProfile, GradeChange, ItemStat, TestAttempt, TestItem
from app.services.common import notify
from app.testing.bank import REGISTRY, GenCtx, check_answer, render
from app.testing.blueprint import base_blueprint
from app.testing.cat import Answered, CatConfig, CatState, finalize, select_next, should_stop

ATTEMPT_MINUTES = 90  # до 22 заданий; типичная попытка — 13–16 заданий
TIME_GRACE_S = 20
UPGRADE_WINDOW_DAYS = 14


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


CONFIRM_WINDOW_DAYS = 7
CONFIRM_TIME_FACTOR = 0.7  # контрольная форма: строже таймер на задание


def cat_config(mode: str = "regular") -> CatConfig:
    if mode == "confirm":
        # короткая контрольная форма из свежих вариантов у порога грейда
        return CatConfig(min_items=6, max_items=10, coverage_items=6, decision_confidence=settings.test_decision_confidence)
    return CatConfig(min_items=settings.test_min_items, max_items=settings.test_max_items, coverage_items=settings.test_coverage_items,
                     decision_confidence=settings.test_decision_confidence)


def candidate_ctx(cand: CandidateProfile) -> GenCtx:
    spec = cand.specialization or "backend"
    lang = cand.primary_lang if cand.primary_lang in SPECIALIZATIONS[spec]["langs"] else SPECIALIZATIONS[spec]["langs"][0]
    fw = cand.framework or ("react" if spec == "frontend" else None)
    return GenCtx(lang=lang, framework=fw, spec=spec)


# ---------------------------------------------------------------- правила допуска к тесту
# Режимы попытки (attempt.blueprint["mode"]):
#   regular   — обычный тест на выбранный грейд, расходует попытку из лимита за 30 дней;
#   step_down — тест на уровень ниже после неудачи без подтверждённого грейда: попытку не расходует,
#               а подтверждённый так грейд не запускает 90-дневную блокировку смены грейда;
#   upgrade   — отдельный тест на грейд выше по предложению системы после уверенного прохождения:
#               доступен сразу, без ожидания блокировки и вне лимита. Повышение без теста не выполняется.
#   confirm   — контрольная форма: попытка прошла порог, но сработали сигналы нечестности (аномальный паттерн
#               ответов, уходы со вкладки, вставки, сверхбыстрые ответы). Грейд не присваивается, пока кандидат не
#               подтвердит его короткой формой (6–10 свежих заданий, строже таймер); доступна сразу, вне лимита.
def upgrade_offer(db: Session, cand: CandidateProfile, now: datetime | None = None) -> TestAttempt | None:
    """Последняя попытка, по которой кандидату предложен тест на грейд выше и предложение ещё действует."""
    now = now or utcnow()
    if not cand.grade:
        return None
    a = db.scalar(select(TestAttempt).where(TestAttempt.candidate_id == cand.user_id, TestAttempt.status == "completed",
                                            TestAttempt.specialization == cand.specialization,
                                            TestAttempt.passed.is_(True), TestAttempt.is_synthetic.is_(False))
                  .order_by(TestAttempt.finished_at.desc()).limit(1))
    if (not a or not a.upgrade_grade or a.upgrade_accepted or a.target_grade != cand.grade
            or (now - _aware(a.finished_at)).days > UPGRADE_WINDOW_DAYS):
        return None
    return a


def _mode(a: TestAttempt) -> str:
    return (a.blueprint or {}).get("mode", "regular")


def pending_confirmation(db: Session, cand: CandidateProfile, now: datetime | None = None) -> TestAttempt | None:
    """Попытка, ожидающая контрольной формы (последняя завершённая, не старше CONFIRM_WINDOW_DAYS)."""
    now = now or utcnow()
    a = db.scalar(select(TestAttempt).where(TestAttempt.candidate_id == cand.user_id, TestAttempt.status == "completed",
                                            TestAttempt.specialization == cand.specialization, TestAttempt.is_synthetic.is_(False))
                  .order_by(TestAttempt.finished_at.desc()).limit(1))
    if a and a.decision == "needs_confirmation" and (now - _aware(a.finished_at)).days <= CONFIRM_WINDOW_DAYS:
        return a
    return None


def eligibility(db: Session, cand: CandidateProfile, now: datetime | None = None) -> dict:
    now = now or utcnow()
    res: dict = {"grades": {}, "in_progress_attempt_id": None, "locked_until": None, "attempts_30d": 0, "upgrade_offer": None,
                 "attempts_limit": settings.max_attempts_per_30_days, "survey_required": cand.specialization is None}
    if cand.specialization is None:
        for g in GRADE_ORDER:
            res["grades"][g] = {"allowed": False, "reason": "Сначала пройдите опрос по направлению и специализации"}
        return res
    ip = db.scalar(select(TestAttempt).where(TestAttempt.candidate_id == cand.user_id, TestAttempt.status == "in_progress"))
    if ip and _aware(ip.deadline_at) > now:
        res["in_progress_attempt_id"] = ip.id
    recent = db.scalars(
        select(TestAttempt).where(TestAttempt.candidate_id == cand.user_id, TestAttempt.started_at >= now - timedelta(days=30),
                                  TestAttempt.is_synthetic.is_(False))
    ).all()
    # шаг вниз после неудачи и тест на повышение по предложению системы попытку не расходуют
    res["attempts_30d"] = sum(1 for a in recent if _mode(a) == "regular")
    confirm = pending_confirmation(db, cand, now)
    res["confirmation"] = ({"grade": confirm.target_grade, "attempt_id": confirm.id,
                            "until": (_aware(confirm.finished_at) + timedelta(days=CONFIRM_WINDOW_DAYS)).isoformat()} if confirm else None)
    lock = _aware(cand.grade_locked_until)
    if cand.grade and lock and lock > now:
        res["locked_until"] = lock.isoformat()
    offer = upgrade_offer(db, cand, now)
    if offer:
        res["upgrade_offer"] = {"grade": offer.upgrade_grade, "attempt_id": offer.id,
                                "until": (_aware(offer.finished_at) + timedelta(days=UPGRADE_WINDOW_DAYS)).isoformat()}
    last_fail: dict[str, datetime] = {}
    for a in recent:  # паузы после неудачи — в своей специализации (у кандидата может быть несколько категорий)
        if a.status == "completed" and a.passed is False and a.decision != "needs_confirmation" and a.specialization == cand.specialization:
            last_fail[a.target_grade] = max(last_fail.get(a.target_grade, _aware(a.finished_at)), _aware(a.finished_at))
    for g in GRADE_ORDER:
        allowed, reason, available_at, mode = True, None, None, "regular"
        step_down = not cand.grade and any(GRADE_ORDER.index(f) > GRADE_ORDER.index(g) for f in last_fail)
        if step_down:
            mode = "step_down"
        if res["in_progress_attempt_id"]:
            allowed, reason = False, "Есть незавершённая попытка — продолжите её"
        elif confirm and g == confirm.target_grade:
            mode = "confirm"  # контрольная форма: сразу и вне лимита
        elif offer and g == offer.upgrade_grade:
            mode = "upgrade"  # отдельный тест на повышение: сразу, без ожидания блокировки и вне лимита
        elif len([a for a in recent if _mode(a) == "regular"]) >= settings.max_attempts_per_30_days and not step_down:
            allowed, reason = False, f"Не более {settings.max_attempts_per_30_days} попыток за 30 дней"
        elif cand.grade:
            if g == cand.grade:
                allowed, reason = False, "Этот грейд уже подтверждён"
            elif lock and lock > now:
                allowed, reason, available_at = False, "Смена грейда возможна не чаще одного раза в 90 дней", lock.isoformat()
            elif abs(GRADE_ORDER.index(g) - GRADE_ORDER.index(cand.grade)) > 1:
                allowed, reason = False, "Грейд меняется на одну ступень за раз"
        if allowed and mode != "confirm" and g in last_fail:
            # пересдача того же уровня — после паузы (и по предложению о повышении тоже); уровень ниже доступен сразу
            until = last_fail[g] + timedelta(days=settings.retake_same_grade_cooldown_days)
            if until > now:
                allowed, reason, available_at = False, "Повторная попытка на этот грейд — после паузы", until.isoformat()
        if allowed and mode != "confirm" and not cand.grade:
            # без подтверждённого грейда: после неудачи на уровне f уровни ниже f доступны сразу, f и выше — после паузы
            blocking = [last_fail[f] for f in last_fail if GRADE_ORDER.index(f) <= GRADE_ORDER.index(g)]
            if blocking:
                until = max(blocking) + timedelta(days=settings.retake_same_grade_cooldown_days)
                if until > now:
                    allowed, reason, available_at = False, "После неудачи сразу доступен тест на уровень ниже, этот — после паузы", until.isoformat()
        res["grades"][g] = {"allowed": allowed, "reason": reason, "available_at": available_at, "mode": mode}
    return res


# ---------------------------------------------------------------- калибровка и экспозиция
def bank_overrides(db: Session) -> tuple[dict[str, tuple[float, float]], dict[str, float], set[str]]:
    rows = db.scalars(select(ItemStat)).all()
    total = db.scalar(select(func.count(TestAttempt.id))) or 0
    overrides = {r.template_id: (r.a, r.b) for r in rows if r.a is not None and r.b is not None}
    exposure = {r.template_id: r.administered / max(60, total) for r in rows}
    retired = {r.template_id for r in rows if r.retired}
    return overrides, exposure, retired


def _state(attempt: TestAttempt, ctx: GenCtx, seen_before: set[str] | None = None) -> CatState:
    st = CatState(spec=attempt.specialization, ctx=ctx, target_grade=attempt.target_grade, blueprint=attempt.blueprint["weights"],
                  seen_before=seen_before or set())
    for it in attempt.items:
        st.used.add(it.template_id)
        if it.is_correct is not None:
            st.answered.append(Answered(it.template_id, it.competency, it.a, it.b, it.c, bool(it.is_correct)))
    return st


def _variant_seed(attempt: TestAttempt, position: int) -> int:
    return int(hashlib.sha256(f"{attempt.seed}:{attempt.id}:{position}".encode()).hexdigest()[:8], 16) % (2**31 - 1)


FRESH_TRIES = 25


def fresh_variant(db: Session, t, ctx: GenCtx, seed: int):
    """Вариант, который ещё не видел ни один кандидат: если такой текст уже выдавался (совпал хеш), генерируем заново.
    Заученные ответы из чужих попыток поэтому бесполезны. Для семейств с малым числом вариантов после FRESH_TRIES
    попыток выдаётся последний сгенерированный (такие семейства и так ограничены контролем экспозиции)."""
    for k in range(FRESH_TRIES):
        s = seed if k == 0 else int(hashlib.sha256(f"{seed}:{k}".encode()).hexdigest()[:8], 16) % (2**31 - 1)
        payload, key, vhash = render(t, s, ctx)
        if not db.scalar(select(TestItem.id).where(TestItem.variant_hash == vhash).limit(1)):
            break
    return s, payload, key, vhash


def _issue_next(db: Session, attempt: TestAttempt, st: CatState) -> TestItem | None:
    overrides, exposure, retired = bank_overrides(db)
    rng = random.Random(attempt.seed * 1009 + len(attempt.items))
    t = select_next(st, rng, overrides=overrides, exposure=exposure, retired=retired, cut_window=cat_config().cut_window)
    if t is None:
        return None
    a, b = overrides.get(t.id, (t.a, t.b))
    vseed, payload, key, vhash = fresh_variant(db, t, st.ctx, _variant_seed(attempt, len(attempt.items) + 1))
    item = TestItem(
        attempt_id=attempt.id, position=len(attempt.items) + 1, template_id=t.id, competency=t.competency, level=t.level, kind=payload["kind"],
        a=a, b=b, c=t.c, variant_seed=vseed, variant_hash=vhash, payload=payload, answer_key=key,
        time_limit_s=int(t.time_limit * CONFIRM_TIME_FACTOR) if _mode(attempt) == "confirm" else t.time_limit,
        presented_at=utcnow(),
    )
    attempt.items.append(item)
    db.flush()
    return item


def start_attempt(db: Session, cand: CandidateProfile, target_grade: str) -> TestAttempt:
    if target_grade not in GRADES:
        raise AppError(400, "invalid_grade", "Неизвестный грейд")
    el = eligibility(db, cand)
    if el["in_progress_attempt_id"]:
        return db.get(TestAttempt, el["in_progress_attempt_id"])
    g = el["grades"][target_grade]
    if not g["allowed"]:
        raise AppError(409, "not_eligible", g["reason"] or "Тест сейчас недоступен", {"available_at": g.get("available_at")})
    ctx = candidate_ctx(cand)
    now = utcnow()
    attempt = TestAttempt(
        candidate_id=cand.user_id, specialization=cand.specialization, lang=ctx.lang, target_grade=target_grade,
        seed=random.SystemRandom().randint(1, 2**31 - 1),
        blueprint={"weights": base_blueprint(cand.specialization), "lang": ctx.lang, "framework": ctx.framework, "mode": g["mode"],
                   **({"confirms": el["confirmation"]["attempt_id"]} if g["mode"] == "confirm" else {})},
        started_at=now, deadline_at=now + timedelta(minutes=ATTEMPT_MINUTES),
    )
    if g["mode"] == "upgrade":
        upgrade_offer(db, cand, now).upgrade_accepted = True  # предложение используется один раз
    db.add(attempt)
    db.flush()
    seen = _seen_before(db, cand.user_id)
    _issue_next(db, attempt, _state(attempt, ctx, seen))
    db.commit()
    return attempt


def _seen_before(db: Session, candidate_id: int) -> set[str]:
    rows = db.execute(
        select(TestItem.template_id).join(TestAttempt, TestAttempt.id == TestItem.attempt_id).where(TestAttempt.candidate_id == candidate_id)
    ).all()
    return {r[0] for r in rows}


def current_item(attempt: TestAttempt) -> TestItem | None:
    for it in attempt.items:
        if it.is_correct is None:
            return it
    return None


def item_view(attempt: TestAttempt, item: TestItem, cfg: CatConfig | None = None) -> dict:
    cfg = cfg or cat_config()
    elapsed = (utcnow() - _aware(item.presented_at)).total_seconds()
    return {
        "attempt_id": attempt.id,
        "item_id": item.id,
        "position": item.position,
        "min_items": cfg.min_items,
        "max_items": cfg.max_items,
        "competency": COMPETENCIES.get(item.competency, {}).get("name", item.competency),
        "time_limit_s": item.time_limit_s,
        "time_left_s": max(0, int(item.time_limit_s - elapsed)),
        "attempt_deadline": _aware(attempt.deadline_at).isoformat(),
        **item.payload,
    }


def submit_answer(db: Session, cand: CandidateProfile, attempt: TestAttempt, item_id: int, response, time_ms: int | None,
                  events: dict | None) -> dict:
    if attempt.candidate_id != cand.user_id:
        raise AppError(404, "not_found", "Попытка не найдена")
    if attempt.status != "in_progress":
        raise AppError(409, "attempt_closed", "Попытка уже завершена")
    item = current_item(attempt)
    if not item or item.id != item_id:
        raise AppError(409, "stale_item", "Это задание уже не актуально — обновите страницу")
    now = utcnow()
    server_ms = int((now - _aware(item.presented_at)).total_seconds() * 1000)
    timed_out = server_ms > (item.time_limit_s + TIME_GRACE_S) * 1000
    item.response = {"value": response, "timed_out": timed_out}
    item.is_correct = (not timed_out) and check_answer(item.answer_key, response)
    item.answered_at = now
    item.time_spent_ms = server_ms
    item.events = events or {}
    if not (attempt.blueprint or {}).get("expert"):
        _update_stats(db, item)  # ответы режима эксперта не участвуют в калибровке банка
    ctx = candidate_ctx(cand)
    st = _state(attempt, ctx, _seen_before(db, cand.user_id))
    deadline_passed = _aware(attempt.deadline_at) < now
    if deadline_passed or should_stop(st, cat_config(_mode(attempt))) or _issue_next(db, attempt, st) is None:
        finish_attempt(db, cand, attempt)
        db.commit()
        return {"finished": True, "result": attempt_result(attempt)}
    db.commit()
    return {"finished": False, "item": item_view(attempt, current_item(attempt))}


# ---------------------------------------------------------------- режим эксперта (только демо-стенд)
# Жюри проверяет воспроизводимость и разделяющую силу теста на своих синтетических профилях. Чтобы пройти тест
# «за кандидата заданного уровня» за минуту, демо-аккаунты экспертов могут отвечать кнопками «верно / неверно» или
# запустить автопрохождение по модели IRT. Ключи ответов при этом не покидают сервер; такие ответы не участвуют
# в калибровке банка. Вне демо-режима и для обычных аккаунтов функции недоступны.
EXPERT_EMAIL = re.compile(r"^(expert\d+|newbie)@draft\.demo$")


def expert_mode(email: str | None) -> bool:
    return settings.demo_mode and bool(EXPERT_EMAIL.match(email or ""))


def _key_response(key: dict, correct: bool):
    if key["kind"] == "single":
        return key["correct"][0] if correct else next(i for i in range(12) if i not in key["correct"])
    if key["kind"] == "multi":
        return key["correct"] if correct else key["correct"][:-1] or [next(i for i in range(12) if i not in key["correct"])]
    v = key["value"][0] if isinstance(key["value"], list) else key["value"]
    if correct:
        return v
    try:
        return str(float(v) + 1 + abs(float(key.get("tolerance") or 0)) * 10)
    except (TypeError, ValueError):
        return "—"


def expert_answer(db: Session, cand: CandidateProfile, attempt: TestAttempt, item_id: int, correct: bool) -> dict:
    item = current_item(attempt)
    if not item or item.id != item_id:
        raise AppError(409, "stale_item", "Это задание уже не актуально — обновите страницу")
    attempt.blueprint = {**(attempt.blueprint or {}), "expert": True}
    return submit_answer(db, cand, attempt, item_id, _key_response(item.answer_key, correct), None, {"expert": True})


def expert_simulate(db: Session, cand: CandidateProfile, attempt: TestAttempt, theta: float, seed: int | None = None) -> dict:
    """Ответить на оставшиеся задания как кандидат с уровнем θ: P(верно) по модели 3PL с параметрами каждого задания."""
    from app.testing.irt import p_correct

    rng = random.Random(seed)
    while True:
        item = current_item(attempt)
        if attempt.status != "in_progress" or item is None:
            return {"finished": True, "result": attempt_result(attempt)}
        res = expert_answer(db, cand, attempt, item.id, rng.random() < float(p_correct(theta, item.a, item.b, item.c)))
        if res["finished"]:
            return res


def _update_stats(db: Session, item: TestItem) -> None:
    stat = db.get(ItemStat, item.template_id)
    if not stat:
        stat = ItemStat(template_id=item.template_id, administered=0, correct=0, recent=[])
        db.add(stat)
    stat.administered = (stat.administered or 0) + 1
    stat.correct = (stat.correct or 0) + (1 if item.is_correct else 0)


def _flags(attempt: TestAttempt, lz: float | None) -> dict:
    focus = sum(int((it.events or {}).get("blur", 0)) for it in attempt.items)
    pastes = sum(int((it.events or {}).get("paste", 0)) for it in attempt.items)
    fast = sum(1 for it in attempt.items if it.is_correct and it.level >= 3 and it.kind == "input" and (it.time_spent_ms or 10**6) < 8000)
    reasons = []
    if lz is not None and lz < -2.0:
        reasons.append("Аномальный паттерн ответов (person-fit lz < −2)")
    if focus >= 4:
        reasons.append("Частые уходы со вкладки теста")
    if pastes >= 2:
        reasons.append("Вставка ответов из буфера обмена")
    if fast >= 2:
        reasons.append("Слишком быстрые верные ответы на сложные задания")
    return {"person_fit_lz": None if lz is None else round(lz, 2), "focus_lost": focus, "pastes": pastes, "fast_correct": fast,
            "suspicious": len(reasons) >= 2 or (lz is not None and lz < -2.5), "reasons": reasons}


def verified_skills(topic_scores: dict, cand: CandidateProfile, grade: str | None) -> list[dict]:
    cut = GRADES[grade]["cut"] if grade else GRADES["intern"]["cut"]
    ctx = candidate_ctx(cand)
    out = []
    for comp, ts in topic_scores.items():
        if ts["n"] >= 2 and ts["theta"] >= cut - 0.3:
            for skill in competency_skills(comp, ctx.lang, cand.specialization, ctx.framework):
                out.append({"skill": skill, "competency": comp, "score": ts["score"], "theta": ts["theta"]})
    return out


def finish_attempt(db: Session, cand: CandidateProfile, attempt: TestAttempt, now: datetime | None = None, notify_user: bool = True) -> None:
    now = now or utcnow()
    st = _state(attempt, candidate_ctx(cand))
    # незавершённые задания считаются неотвеченными и удаляются
    for it in list(attempt.items):
        if it.is_correct is None:
            attempt.items.remove(it)
    res = finalize(st)
    attempt.status = "completed"
    attempt.finished_at = now
    attempt.theta, attempt.se, attempt.p_target = round(res.theta, 4), round(res.se, 4), round(res.p_target, 4)
    attempt.passed = res.passed
    attempt.decision = "confirmed" if res.passed else "failed"
    attempt.upgrade_grade = res.upgrade_grade
    attempt.suggested_grade = res.suggested_grade
    attempt.topic_scores = res.topic_scores
    attempt.items_count = len(st.answered)
    attempt.flags = {**_flags(attempt, res.person_fit), "probs": {k: round(v, 3) for k, v in res.probs.items()}}
    attempt.trajectory = _trajectory(st)
    mode = _mode(attempt)

    if res.passed and attempt.flags["suspicious"] and mode != "confirm" and not (attempt.blueprint or {}).get("expert"):
        # порог пройден, но есть сигналы нечестности: грейд не присваивается до контрольной формы, профиль не меняется
        attempt.passed, attempt.decision, attempt.upgrade_grade = False, "needs_confirmation", None
        cand.last_activity_at = now
        if notify_user and not attempt.is_synthetic:
            notify(db, cand.user_id, "assessment", f"Подтвердите грейд {grade_name(attempt.target_grade)} контрольной формой",
                   f"Результат выше порога, но система зафиксировала сигналы, при которых грейд подтверждается короткой формой "
                   f"(6–10 новых заданий). Доступна сразу, не расходует попытку, действует {CONFIRM_WINDOW_DAYS} дней.",
                   f"/c/assessment/result/{attempt.id}")
        return

    prev = cand.grade
    cand.theta, cand.theta_se = attempt.theta, attempt.se
    cand.topic_scores = res.topic_scores
    cand.last_attempt_id = attempt.id
    cand.last_activity_at = now
    target = attempt.target_grade
    if res.passed:
        if prev != target:
            cand.grade = target
            # грейд, подтверждённый шагом вниз после неудачи, не блокирует смену: повтор неудавшегося уровня —
            # через обычную паузу на пересдачу (14 дней), а не через 90 дней
            base_mode = mode
            if mode == "confirm":  # контрольная форма наследует режим исходной попытки (шаг вниз не блокирует смену)
                orig = db.get(TestAttempt, (attempt.blueprint or {}).get("confirms") or 0)
                base_mode = _mode(orig) if orig else "regular"
            cand.grade_locked_until = None if base_mode == "step_down" else now + timedelta(days=settings.grade_change_cooldown_days)
            reason = "initial" if prev is None else ("retest_up" if GRADE_ORDER.index(target) > GRADE_ORDER.index(prev) else "retest_down")
            db.add(GradeChange(candidate_id=cand.user_id, specialization=attempt.specialization, from_grade=prev, to_grade=target,
                               reason=reason, attempt_id=attempt.id, created_at=now))
        cand.grade_confirmed_at = now
    cand.verified_skills = verified_skills(res.topic_scores, cand, cand.grade)
    from app.matching.strength import refresh_strength  # локальный импорт: избегаем цикла

    refresh_strength(cand, now)
    if notify_user and not attempt.is_synthetic:
        if res.passed:
            title = f"Грейд {grade_name(target)} подтверждён"
            body = f"Вы в категории «{SPECIALIZATIONS[attempt.specialization]['short']} · {grade_name(cand.grade)}». Работодатели уже видят ваш профиль."
            if res.upgrade_grade:
                body += (f" Вы уверенно справились — можно сразу, без ожидания, пройти отдельный тест "
                         f"на {grade_name(res.upgrade_grade)} (предложение действует {UPGRADE_WINDOW_DAYS} дней).")
        else:
            title = f"Грейд {grade_name(target)} пока не подтверждён"
            body = "Грейд не понижается принудительно: вы можете пройти тест на уровень ниже или повторить попытку позже."
        notify(db, cand.user_id, "assessment", title, body, f"/c/assessment/result/{attempt.id}")


def _trajectory(st: CatState) -> list[dict]:
    from app.testing import irt

    out = []
    mu, sd = st.prior
    for i in range(1, len(st.answered) + 1):
        part = st.answered[:i]
        th, se, _ = irt.eap([(x.params, x.correct) for x in part], mu, sd)
        x = part[-1]
        out.append({"n": i, "theta": round(th, 3), "se": round(se, 3), "b": round(x.b, 2), "correct": x.correct, "competency": x.competency})
    return out


def start_upgrade(db: Session, cand: CandidateProfile, attempt: TestAttempt) -> TestAttempt:
    """Начать отдельный тест на грейд выше по предложению из результата попытки (повышение без теста не выполняется)."""
    offer = upgrade_offer(db, cand)
    if attempt.candidate_id != cand.user_id or not attempt.upgrade_grade:
        raise AppError(409, "no_upgrade", "Повышение по этой попытке недоступно")
    if not offer or offer.id != attempt.id:
        raise AppError(409, "upgrade_expired", "Предложение о тесте на грейд выше больше не действует")
    return start_attempt(db, cand, attempt.upgrade_grade)


def abandon(db: Session, cand: CandidateProfile, attempt: TestAttempt) -> None:
    if attempt.candidate_id != cand.user_id or attempt.status != "in_progress":
        raise AppError(409, "attempt_closed", "Попытка уже завершена")
    finish_attempt(db, cand, attempt)
    db.commit()


def attempt_result(attempt: TestAttempt) -> dict:
    return {
        "attempt_id": attempt.id,
        "status": attempt.status,
        "specialization": attempt.specialization,
        "target_grade": attempt.target_grade,
        "passed": attempt.passed,
        "decision": attempt.decision,
        "theta": attempt.theta,
        "se": attempt.se,
        "p_target": attempt.p_target,
        "upgrade_grade": None if attempt.upgrade_accepted else attempt.upgrade_grade,
        "upgrade_accepted": attempt.upgrade_accepted,
        "suggested_grade": attempt.suggested_grade,
        "topic_scores": attempt.topic_scores,
        "items_count": attempt.items_count,
        "probs": (attempt.flags or {}).get("probs"),
        "trajectory": attempt.trajectory,
        "started_at": _aware(attempt.started_at).isoformat() if attempt.started_at else None,
        "finished_at": _aware(attempt.finished_at).isoformat() if attempt.finished_at else None,
        "items": [
            {"position": it.position, "competency": COMPETENCIES.get(it.competency, {}).get("name", it.competency), "level": it.level,
             "correct": it.is_correct, "time_spent_s": round((it.time_spent_ms or 0) / 1000)}
            for it in attempt.items
        ],
    }


def resolve_attempt(db: Session, attempt_id: int) -> TestAttempt:
    a = db.get(TestAttempt, attempt_id)
    if not a:
        raise AppError(404, "not_found", "Попытка не найдена")
    return a


def expire_stale(db: Session, cand: CandidateProfile) -> None:
    """Попытки с истёкшим дедлайном закрываются при следующем обращении кандидата."""
    for a in db.scalars(select(TestAttempt).where(TestAttempt.candidate_id == cand.user_id, TestAttempt.status == "in_progress")).all():
        if _aware(a.deadline_at) < utcnow():
            finish_attempt(db, cand, a)
    db.commit()
