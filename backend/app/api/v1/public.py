"""Публичные и вспомогательные эндпоинты: справочник, вакансии, уведомления, проверка PDF-профиля,
демонстрация механик (генерация вариантов, симуляция CAT), результаты валидации, ATS API, администрирование."""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Body, Depends, Header, Query
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog.data import COMPETENCIES, GRADE_ORDER, GRADES, SPECIALIZATIONS, category_label, public_catalog
from app.core.config import settings
from app.core.db import get_db, utcnow
from app.core.deps import RateLimiter, bearer, get_current_user, require_role
from app.core.errors import COMMON_ERRORS, AppError, err
from app.core.security import decode_access_token, sha256
from app.matching import service as match
from app.models import (
    ApiKey,
    Application,
    CandidateProfile,
    Company,
    EmployerTask,
    Invitation,
    ItemStat,
    Notification,
    Report,
    TestAttempt,
    User,
    Vacancy,
)
from app.schemas import AtsVacancyIn, VacancyIn
from app.services import invitations as inv_svc
from app.services.pdf import parse_verify_token
from app.testing import irt
from app.testing.bank import REGISTRY, GenCtx, render
from app.validation.external_eval import EvalError, build_example, evaluate_external
from app.testing.cat import information_curve, simulate
from app.testing.service import cat_config

router = APIRouter(tags=["Справочники и публичные данные"])
VALIDATION_PATH = Path(__file__).resolve().parents[3] / "validation_results" / "report.json"


@router.get("/catalog", summary="Справочник: направления, специализации, грейды, навыки, дисциплины ФСП")
def catalog():
    return public_catalog()


@router.get("/public/stats", summary="Статистика платформы для главной страницы")
def stats(db: Session = Depends(get_db)):
    cands = db.scalar(select(func.count()).select_from(CandidateProfile).where(CandidateProfile.grade.is_not(None))) or 0
    fsp = db.scalar(select(func.count()).select_from(CandidateProfile).where(CandidateProfile.fsp_score > 0)) or 0
    comps = db.scalar(select(func.count()).select_from(Company)) or 0
    invs = db.scalar(select(func.count()).select_from(Invitation)) or 0
    acc = db.scalar(select(func.count()).select_from(Invitation).where(Invitation.status == "accepted")) or 0
    return {"candidates_verified": cands, "with_fsp": fsp, "companies": comps, "invitations": invs, "accepted": acc,
            "templates": len(REGISTRY), "specializations": len(SPECIALIZATIONS), "demo_mode": settings.demo_mode,
            "demo_mailbox_url": settings.demo_mailbox_url if settings.demo_mode else None,
            "fsp_login_url": f"{settings.fsp_issuer_public}" if settings.demo_mode else None}


@router.get("/public/verify/{token}", summary="Проверка подлинности PDF-профиля по QR-коду", responses=err(404, "Недействительный код"))
def verify(token: str, db: Session = Depends(get_db)):
    parsed = parse_verify_token(token)
    if not parsed:
        raise AppError(404, "invalid_token", "Код проверки недействителен")
    uid, ts = parsed
    c = db.get(CandidateProfile, uid)
    if not c:
        raise AppError(404, "not_found", "Профиль удалён")
    name = c.full_name or ""
    parts = name.split()
    masked = f"{parts[0]} {parts[1][0]}." if len(parts) >= 2 else (name or c.public_code)
    return {"valid": True, "issued_at": datetime.fromtimestamp(ts, timezone.utc).isoformat(), "code": c.public_code, "name": masked,
            "category": category_label(c.specialization, c.grade), "grade_confirmed_at": c.grade_confirmed_at.isoformat() if c.grade_confirmed_at else None,
            "fsp_linked": bool(c.fsp_id), "fsp_achievements": len(c.achievements), "verified_skills": sorted({v["skill"] for v in c.verified_skills or []})}


# ---------------------------------------------------------------- вакансии (кандидатский сценарий отклика)
def _optional_candidate(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> CandidateProfile | None:
    if not creds:
        return None
    try:
        claims = decode_access_token(creds.credentials)
    except Exception:  # noqa: BLE001
        return None
    return db.get(CandidateProfile, int(claims["sub"])) if "candidate" in claims.get("realm_access", {}).get("roles", []) else None


def vacancy_public(v: Vacancy) -> dict:
    co = v.company
    return {"id": v.id, "title": v.title, "description": v.description, "specialization": v.specialization, "grade": v.grade,
            "category": category_label(v.specialization, v.grade), "must_skills": v.must_skills, "nice_skills": v.nice_skills,
            "work_formats": v.work_formats, "city": v.city, "salary_from": v.salary_from, "salary_to": v.salary_to,
            "created_at": v.created_at.isoformat(), "risk_flags": v.risk_flags,
            "company": {"id": co.user_id, "name": co.name, "industry": co.industry, "city": co.city, "trust_score": co.trust_score, "accent": co.accent}}


@router.get("/vacancies", tags=["Вакансии"], summary="Опубликованные вакансии; для кандидата — с оценкой соответствия")
def vacancies(specialization: str | None = None, grade: str | None = None, format: str | None = None, salary_min: int | None = None,
              q: str | None = None, mine: bool = Query(False, description="Только подходящие моей категории"), limit: int = Query(50, le=100),
              offset: int = 0, cand: CandidateProfile | None = Depends(_optional_candidate), db: Session = Depends(get_db)):
    stmt = select(Vacancy).where(Vacancy.status == "published")
    if specialization:
        stmt = stmt.where(Vacancy.specialization == specialization)
    if grade:
        stmt = stmt.where(Vacancy.grade == grade)
    if salary_min:
        stmt = stmt.where(Vacancy.salary_to >= salary_min)
    if mine and cand and cand.specialization:
        stmt = stmt.where(Vacancy.specialization == cand.specialization)
    rows = db.scalars(stmt.order_by(Vacancy.created_at.desc())).all()
    if format:
        rows = [v for v in rows if format in (v.work_formats or [])]
    if q:
        ql = q.lower()
        rows = [v for v in rows if ql in v.title.lower() or ql in v.description.lower() or any(ql in s.lower() for s in v.must_skills or [])]
    applied = set()
    ts = None
    if cand:
        applied = {a.vacancy_id for a in db.scalars(select(Application).where(Application.candidate_id == cand.user_id)).all()}
        if cand.grade:
            ts = match._task_skills(db, [cand.user_id])
    view = ts is not None
    items = []
    for v in rows:
        d = vacancy_public(v)
        if view:
            r = match.best_score(cand, match.need_view(v, include_adjacent=True), ts)  # лучшая из категорий кандидата
            d["match"] = {"score": r["score"], "fit": r["fit"], "reasons": r["reasons"][:3], "warnings": r["warnings"][:2]} if r else None
        d["applied"] = v.id in applied
        items.append(d)
    if view:
        items.sort(key=lambda d: -(d.get("match") or {}).get("score", 0))
    return {"total": len(items), "items": items[offset: offset + limit]}


@router.get("/vacancies/{vid}", tags=["Вакансии"], summary="Вакансия", responses=err(404, "Не найдена"))
def vacancy(vid: int, cand: CandidateProfile | None = Depends(_optional_candidate), db: Session = Depends(get_db)):
    v = db.get(Vacancy, vid)
    if not v or v.status != "published":
        raise AppError(404, "not_found", "Вакансия не найдена")
    v.views = (v.views or 0) + 1
    db.commit()
    d = vacancy_public(v)
    d["company"]["description"] = v.company.description
    if cand and cand.grade:
        d["match"] = match.best_score(cand, match.need_view(v, include_adjacent=True), match._task_skills(db, [cand.user_id]))
        d["applied"] = bool(db.scalar(select(Application).where(Application.vacancy_id == v.id, Application.candidate_id == cand.user_id)))
    return d


# ---------------------------------------------------------------- уведомления
@router.get("/notifications", tags=["Уведомления"], summary="Мои уведомления", responses=COMMON_ERRORS)
def notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(40)).all()
    unread = db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))) or 0
    return {"unread": unread, "items": [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link,
                                         "read": n.read_at is not None, "created_at": n.created_at.isoformat()} for n in rows]}


@router.post("/notifications/read-all", tags=["Уведомления"], summary="Отметить все как прочитанные", responses=COMMON_ERRORS)
def read_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for n in db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))).all():
        n.read_at = utcnow()
    db.commit()
    return {"status": "ok"}


# ---------------------------------------------------------------- механика тестирования (для демонстрации)
@router.get("/mechanics/bank", tags=["Механика тестирования"], summary="Обзор банка шаблонов-генераторов")
def bank_overview(db: Session = Depends(get_db)):
    stats = {s.template_id: s for s in db.scalars(select(ItemStat)).all()}
    by_spec = {}
    for spec, info in SPECIALIZATIONS.items():
        comps = {}
        for comp in info["blueprint"]:
            ts = [t for t in REGISTRY.values() if t.competency == comp and spec in t.specs]
            comps[comp] = {"name": COMPETENCIES[comp]["name"], "families": len(ts), "levels": sorted({t.level for t in ts})}
        by_spec[spec] = {"name": info["name"], "blueprint": info["blueprint"], "competencies": comps}
    items = [{"id": t.id, "title": t.title, "competency": t.competency, "competency_name": COMPETENCIES[t.competency]["name"],
              "specs": t.specs, "langs": t.langs, "level": t.level, "kind": t.kind, "method": t.method, "a": round(t.a, 2), "b": round(t.b, 2),
              "c": t.c, "administered": stats[t.id].administered if t.id in stats else 0,
              "p_value": round(stats[t.id].correct / stats[t.id].administered, 3) if t.id in stats and stats[t.id].administered else None,
              "drift": stats[t.id].drift_flag if t.id in stats else False}
             for t in REGISTRY.values()]
    return {"total": len(REGISTRY), "by_spec": by_spec, "items": items,
            "methods": {"parametric": sum(1 for t in REGISTRY.values() if t.method == "parametric"),
                        "pool": sum(1 for t in REGISTRY.values() if t.method == "pool")}}


@router.get("/mechanics/preview", tags=["Механика тестирования"], summary="Сгенерировать несколько вариантов одного шаблона (без ключей)")
def preview(template_id: str, lang: str | None = None, framework: str | None = None, n: int = Query(2, ge=1, le=4)):
    t = REGISTRY.get(template_id)
    if not t:
        raise AppError(404, "not_found", "Шаблон не найден")
    lang = lang or (t.langs[0] if t.langs else None)
    ctx = GenCtx(lang=lang, framework=framework or (t.frameworks[0] if t.frameworks else "react"), spec=t.specs[0])
    variants = []
    rng = random.Random()
    for _ in range(n):
        payload, key, h = render(t, rng.randint(1, 10**9), ctx)
        variants.append({"payload": payload, "variant_hash": h})
    return {"template": {"id": t.id, "title": t.title, "competency": COMPETENCIES[t.competency]["name"], "level": t.level, "a": t.a, "b": t.b,
                         "c": t.c, "method": t.method}, "variants": variants, "information_curve": information_curve(t)}


@router.get("/mechanics/simulate", tags=["Механика тестирования"], summary="Симуляция адаптивного теста для «виртуального кандидата»")
def simulate_cat(theta: float = Query(0.5, ge=-3, le=3), specialization: str = "backend", target_grade: str = "middle", seed: int | None = None):
    if specialization not in SPECIALIZATIONS or target_grade not in GRADES:
        raise AppError(400, "invalid", "Неизвестная специализация или грейд")
    info = SPECIALIZATIONS[specialization]
    rng = random.Random(seed)
    ctx = GenCtx(lang=info["langs"][0], framework="react", spec=specialization)
    res, st = simulate(theta, specialization, ctx, target_grade, info["blueprint"], rng, cat_config())
    mu, sd = st.prior
    traj = []
    for i in range(1, len(st.answered) + 1):
        th, se, _ = irt.eap([(x.params, x.correct) for x in st.answered[:i]], mu, sd)
        x = st.answered[i - 1]
        traj.append({"n": i, "theta": round(th, 3), "se": round(se, 3), "template": x.template_id, "title": REGISTRY[x.template_id].title,
                     "competency": COMPETENCIES[x.competency]["name"], "b": round(x.b, 2), "correct": x.correct})
    return {"true_theta": theta, "theta": round(res.theta, 3), "se": round(res.se, 3), "passed": res.passed, "upgrade": res.upgrade_grade,
            "suggested": res.suggested_grade, "probs": {k: round(v, 3) for k, v in res.probs.items()}, "trajectory": traj,
            "cuts": {g: GRADES[g]["cut"] for g in GRADE_ORDER}, "topic_scores": res.topic_scores}


@router.get("/validation/report", tags=["Валидация"], summary="Результаты процедуры валидации тестирования и подбора")
def validation_report():
    if not VALIDATION_PATH.exists():
        raise AppError(404, "not_ready", "Отчёт ещё не сформирован: запустите python -m app.validation.run_all")
    return json.loads(VALIDATION_PATH.read_text())


eval_limiter = RateLimiter(limit=12, window_s=60)
_example_cache: dict = {}


@router.post("/validation/external-eval", tags=["Валидация"], dependencies=[Depends(eval_limiter)],
             summary="Оценка подбора на своём размеченном наборе пар «вакансия — кандидат»",
             description="Принимает вакансии (текст и/или поля), кандидатов (текст резюме и/или поля, результаты теста, достижения ФСП) "
                         "и разметку релевантности пар (0–3 или 0/1). Возвращает Precision@10, nDCG@10, MRR, Recall@30 механики подбора "
                         "и базовой линии «поиск по резюме» в двух протоколах: по всей базе и только по размеченным парам. "
                         "Формат: docs/examples/eval_pairs_example.json или GET /validation/external-eval/example.",
             responses={**err(400, "Некорректный формат набора (код invalid_dataset)"), **err(429, "Слишком много запросов")})
def external_eval(data: dict = Body(..., description="Объект с полями vacancies, candidates, labels"),
                  threshold: int | None = Query(None, ge=1, le=3, description="Минимальная оценка релевантной пары")):
    try:
        return evaluate_external(data, threshold)
    except EvalError as e:
        raise AppError(400, "invalid_dataset", str(e)) from None


@router.get("/validation/external-eval/example", tags=["Валидация"],
            summary="Пример размеченного набора пар в формате проверки (из синтетической популяции, разметка по скрытой истине)")
def external_eval_example(db: Session = Depends(get_db)):
    if "data" not in _example_cache:
        _example_cache["data"] = build_example(db)
    return _example_cache["data"]


# ---------------------------------------------------------------- ATS API (по API-ключу)
ats = APIRouter(prefix="/ats/v1", tags=["ATS-интеграция"])


def ats_company(x_api_key: str = Header(..., alias="X-API-Key"), db: Session = Depends(get_db)) -> Company:
    k = db.scalar(select(ApiKey).where(ApiKey.prefix == x_api_key[:12], ApiKey.revoked_at.is_(None)))
    if not k or k.key_hash != sha256(x_api_key):
        raise AppError(401, "invalid_api_key", "Недействительный API-ключ")
    k.last_used_at = utcnow()
    db.commit()
    return db.get(Company, k.employer_id)


@ats.get("/candidates", summary="Кандидаты, принявшие приглашения (с контактами) — для импорта в ATS", responses=err(401, "Неверный ключ"))
def ats_candidates(c: Company = Depends(ats_company), db: Session = Depends(get_db)):
    invs = db.scalars(select(Invitation).where(Invitation.employer_id == c.user_id, Invitation.status == "accepted",
                                               Invitation.contacts_revoked_at.is_(None))).all()
    return {"items": [inv_svc.ats_candidate_payload(db, i) | {"stage": i.stage} for i in invs]}


# Синхронизация с ATS (по определению организаторов): вакансии, отклики и статусы — без ручного дублирования.
@ats.get("/vacancies", summary="Вакансии компании на платформе (с идентификаторами ATS)", responses=err(401, "Неверный ключ"))
def ats_vacancies(c: Company = Depends(ats_company), db: Session = Depends(get_db)):
    from app.api.v1.employer import vacancy_out

    rows = db.scalars(select(Vacancy).where(Vacancy.employer_id == c.user_id).order_by(Vacancy.created_at.desc())).all()
    return {"items": [vacancy_out(db, v) | {"external_id": v.external_id} for v in rows]}


@ats.put("/vacancies/{external_id}", summary="Создать или обновить вакансию из ATS (специализацию, грейд и навыки распознает разбор текста)",
         responses={**err(401, "Неверный ключ"), **err(422, "Не удалось определить специализацию или грейд / признаки мошенничества")})
def ats_vacancy_upsert(external_id: str, body: AtsVacancyIn, c: Company = Depends(ats_company), db: Session = Depends(get_db)):
    from app.api.v1.employer import _vacancy_data, vacancy_out
    from app.nlp.need_parser import parse_need

    if len(external_id) > 64:
        raise AppError(422, "invalid_external_id", "Идентификатор ATS длиннее 64 символов")
    parsed = parse_need(f"{body.title}\n{body.description}")
    data = body.model_dump()
    filled = []
    if parsed.get("specialization_confidence", 0) < 0.5:
        parsed["specialization"] = None  # не угадываем специализацию по слабым признакам
    for k in ("specialization", "must_skills", "nice_skills", "work_formats"):
        if not data[k] and parsed.get(k):
            data[k], _ = parsed[k], filled.append(k)
    if not data["grade"] and parsed.get("grades"):
        data["grade"], _ = parsed["grades"][0], filled.append("grade")
    if not data["specialization"] or not data["grade"]:
        raise AppError(422, "unrecognized", "Не удалось определить специализацию или грейд — передайте их явно",
                       {"specialization": data["specialization"], "grade": data["grade"]})
    clean = _vacancy_data(VacancyIn(**{k: v for k, v in data.items() if v is not None}))
    v = db.scalar(select(Vacancy).where(Vacancy.employer_id == c.user_id, Vacancy.external_id == external_id))
    created = v is None
    if created:
        v = Vacancy(employer_id=c.user_id, external_id=external_id, **clean)
        db.add(v)
    else:
        for k, val in clean.items():
            setattr(v, k, val)
    db.commit()
    return vacancy_out(db, v) | {"external_id": v.external_id, "created": created, "recognized": filled}


@ats.get("/applications", summary="Отклики на вакансии компании (с контактами откликнувшихся) — для импорта в ATS",
         responses=err(401, "Неверный ключ"))
def ats_applications(since: datetime | None = Query(None, description="Только отклики, созданные после этого момента (ISO 8601)"),
                     c: Company = Depends(ats_company), db: Session = Depends(get_db)):
    q = (select(Application).join(Vacancy, Vacancy.id == Application.vacancy_id)
         .where(Vacancy.employer_id == c.user_id, Application.status != "withdrawn").order_by(Application.created_at))
    if since:
        q = q.where(Application.created_at > since)
    out = []
    for a in db.scalars(q).all():
        cand = db.get(CandidateProfile, a.candidate_id)
        user = db.get(User, a.candidate_id)
        out.append({"application_id": a.id, "vacancy_id": a.vacancy_id, "external_id": a.vacancy.external_id, "status": a.status,
                    "created_at": a.created_at.isoformat(), "match_score": a.match_score, "cover_letter": a.cover_letter,
                    "candidate": {"code": cand.public_code, "full_name": cand.full_name, "email": user.email if user else None,
                                  "phone": cand.phone, "telegram": cand.telegram, "category": match.category_of(cand),
                                  "verified_skills": sorted(set(match.all_verified(cand)))}})
    return {"items": out}


@ats.put("/applications/{app_id}/status", summary="Синхронизация статуса отклика из ATS (просмотрен, интервью, оффер, отказ)",
         responses={**err(401, "Неверный ключ"), **err(404, "Отклик не найден")})
def ats_application_status(app_id: int, status: str = Query(...), c: Company = Depends(ats_company), db: Session = Depends(get_db)):
    from app.api.v1.employer import set_application_status

    a = set_application_status(db, c, app_id, status)
    return {"id": a.id, "status": a.status}


@ats.put("/invitations/{inv_id}/stage", summary="Синхронизация этапа воронки из ATS", responses=err(401, "Неверный ключ"))
def ats_stage(inv_id: int, stage: str = Query(...), c: Company = Depends(ats_company), db: Session = Depends(get_db)):
    i = db.get(Invitation, inv_id)
    if not i or i.employer_id != c.user_id:
        raise AppError(404, "not_found", "Приглашение не найдено")
    inv_svc.set_stage(db, c, i, stage)
    return {"id": i.id, "stage": i.stage}


# ---------------------------------------------------------------- администрирование
admin = APIRouter(prefix="/admin", tags=["Администрирование"], responses=COMMON_ERRORS)


@admin.get("/overview", summary="Сводка платформы и очереди модерации")
def admin_overview(user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    reports = db.scalars(select(Report).where(Report.status == "open").order_by(Report.created_at.desc()).limit(50)).all()
    flagged = db.scalars(select(TestAttempt).where(TestAttempt.status == "completed", TestAttempt.is_synthetic.is_(False))
                         .order_by(TestAttempt.finished_at.desc()).limit(200)).all()
    return {
        "users": dict(db.execute(select(User.role, func.count()).group_by(User.role)).all()),
        "attempts": db.scalar(select(func.count()).select_from(TestAttempt)),
        "reports": [{"id": r.id, "employer_id": r.employer_id, "reason": r.reason, "comment": r.comment, "created_at": r.created_at.isoformat()}
                    for r in reports],
        "suspicious_attempts": [{"id": a.id, "candidate_id": a.candidate_id, "flags": a.flags} for a in flagged if (a.flags or {}).get("suspicious")],
    }


@admin.post("/recalibrate", summary="Онлайн-калибровка трудности шаблонов и детекция дрейфа (признак утечки)")
def recalibrate(user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    from app.validation.calibration import recalibrate_from_db

    return recalibrate_from_db(db)
