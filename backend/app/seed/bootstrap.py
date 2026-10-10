"""Инициализация БД и генерация синтетических данных.

Синтетический кандидат имеет скрытую «истину» (synthetic_truth): истинную способность θ, истинный грейд и
реальный набор навыков. Наблюдаемые данные шумные, как в жизни: заявленный грейд бывает завышен, в резюме
встречается «набивка» ключевыми словами. Тест кандидата моделируется реальным CAT-движком платформы по его
истинной θ — так категория в базе получается тем же путём, что и у живых пользователей.
Эта «истина» используется только процедурой валидации и не отдаётся через API.
"""
from __future__ import annotations

import json
import logging
import math
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func, select

from app.catalog.data import CITIES, DECLINE_REASONS, DOMAINS, GRADE_ORDER, GRADES, MARKET_SALARY, SOFT_SKILLS, SPECIALIZATIONS
from app.core.config import settings
from app.core.db import Base, SessionLocal, engine, utcnow
from app.core.security import hash_password
from app.fsp.client import apply_results
from app.matching.service import recompute_percentiles, run_need
from app.matching.scoring import RELATED_SPECS
from app.matching.strength import refresh_strength
from app.models import (
    Application,
    CandidateCategory,
    CandidateProfile,
    Company,
    Consent,
    EmployerTask,
    GradeChange,
    HiringNeed,
    Invitation,
    ItemStat,
    Message,
    SurveyResponse,
    TaskAssignment,
    TestAttempt,
    TestItem,
    User,
    Vacancy,
)
from app.seed import content
from app.services.tasks import auto_score, recompute_task_score
from app.services.trust import refresh_trust
from app.testing.bank import GenCtx
from app.testing.cat import grade_from_theta, simulate
from app.testing.service import cat_config
from app.testing.service import verified_skills

log = logging.getLogger("draft.seed")
DEMO_PASSWORD = "Demo2026!"
LANG_WEIGHTS = {
    "backend": {"python": 0.35, "java": 0.2, "go": 0.15, "javascript": 0.15, "csharp": 0.07, "kotlin": 0.04, "php": 0.04},
    "mobile": {"kotlin": 0.45, "swift": 0.35, "dart": 0.2},
    "qa": {"python": 0.6, "java": 0.25, "javascript": 0.15},
}
SPEC_WEIGHTS = {"backend": 0.27, "frontend": 0.15, "mobile": 0.1, "ml": 0.11, "data_analyst": 0.1, "devops": 0.1, "qa": 0.1, "infosec": 0.07}
GRADE_WEIGHTS = {"intern": 0.12, "junior": 0.28, "middle": 0.35, "senior": 0.25}
STACK_LANG = {
    "backend": [("Python", "python"), ("Go", "go"), ("Java", "java"), ("Node.js", "javascript"), ("TypeScript", "javascript")],
    "mobile": [("Kotlin", "kotlin"), ("Swift", "swift"), ("Flutter", "dart"), ("Dart", "dart")],
    "qa": [("Python", "python"), ("Pytest", "python")],
}


# Столбцы, добавленные после первого выпуска: create_all не меняет существующие таблицы, поэтому добавляем их явно
# (идемпотентно), чтобы обновление стенда не требовало пересоздания базы.
LATE_COLUMNS = [("invitations", "contacts_revoked_at", "TIMESTAMP"),
                ("candidate_profiles", "age_group", "VARCHAR(16) NOT NULL DEFAULT 'adult'"),
                ("vacancies", "external_id", "VARCHAR(64)")]


LATE_INDEXES = ["CREATE INDEX IF NOT EXISTS ix_test_items_variant_hash ON test_items (variant_hash)",
                "CREATE INDEX IF NOT EXISTS ix_vacancies_external_id ON vacancies (external_id)"]
# зашифрованные поля длиннее исходных: в PostgreSQL расширяем тип (в SQLite длина не проверяется)
LATE_PG_DDL = [f"ALTER TABLE candidate_profiles ALTER COLUMN {c} TYPE TEXT" for c in ("full_name", "phone", "telegram")]


def _add_missing_columns(engine) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    with engine.begin() as conn:
        for table, column, ddl in LATE_COLUMNS:
            if column not in {c["name"] for c in insp.get_columns(table)}:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
        for ddl in LATE_INDEXES:
            conn.execute(text(ddl))
        if engine.dialect.name == "postgresql":
            for ddl in LATE_PG_DDL:
                conn.execute(text(ddl))


def bootstrap() -> None:
    """Создание схемы и однократное заполнение БД. Advisory-lock PostgreSQL исключает гонку,
    если стартуют несколько воркеров или процесс перезапускается во время заполнения."""
    from sqlalchemy import text

    pg = engine.dialect.name == "postgresql"
    with engine.connect() as lock_conn:
        if pg:
            lock_conn.execute(text("SELECT pg_advisory_lock(20261005)"))
        try:
            Base.metadata.create_all(engine)
            _add_missing_columns(engine)
            if not settings.seed_on_start:
                return
            with SessionLocal() as db:
                if db.scalar(select(func.count()).select_from(User)):
                    return
                log.info("Пустая БД — генерирую синтетические данные…")
                seed(db)
                log.info("Синтетические данные готовы")
        finally:
            if pg:
                lock_conn.execute(text("SELECT pg_advisory_unlock(20261005)"))


def inn10(rng: random.Random) -> str:
    while True:
        d = [rng.randint(0, 9) for _ in range(9)]
        d[0] = rng.randint(1, 9)
        c = sum(k * x for k, x in zip([2, 4, 10, 3, 5, 9, 4, 6, 8], d)) % 11 % 10
        return "".join(map(str, d + [c]))


def translit(s: str) -> str:
    table = str.maketrans({"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i", "й": "y",
                           "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
                           "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya"})
    return s.lower().translate(table)


def wchoice(rng: random.Random, weights: dict):
    return rng.choices(list(weights), list(weights.values()))[0]


def load_registry() -> dict:
    p = Path(settings.fsp_seed_registry_path)
    if not p.exists():
        log.warning("Реестр ФСП %s не найден — кандидаты будут без достижений", p)
        return {"athletes": [], "events": [], "results": []}
    return json.loads(p.read_text())


def seed(db) -> None:
    rng = random.Random(42)
    now = utcnow()
    pw = hash_password(DEMO_PASSWORD)
    reg = load_registry()
    events = {e["event_id"]: e for e in reg["events"]}
    results = defaultdict(list)
    for r in reg["results"]:
        results[r["fsp_id"]].append({**r, "event": events[r["event_id"]]})

    # ------------------------------------------------------------ администратор и компании
    admin = User(email="admin@draft.demo", password_hash=pw, role="admin", email_verified=True, created_at=now - timedelta(days=200))
    db.add(admin)
    companies: list[Company] = []
    for i, co in enumerate(content.COMPANIES):
        email = "employer@draft.demo" if i == 0 else f"hr@{co['key']}.demo"
        u = User(email=email, password_hash=pw, role="employer", email_verified=True, created_at=now - timedelta(days=rng.randint(40, 300)))
        db.add(u)
        db.flush()
        c = Company(user_id=u.id, name=co["name"], description=co["description"], industry=co["industry"], website=f"https://{co['key']}.demo",
                    size=co["size"], city=co["city"], contact_name=rng.choice(["Ольга Смирнова", "Ирина Павлова", "Денис Орлов", "Мария Козлова"]),
                    contact_email=f"hr@{co['key']}.demo" if i else "employer@technovector.demo", telegram=f"@{co['key']}_hr",
                    inn=inn10(rng), accent=co["accent"], is_synthetic=i != 0, created_at=u.created_at)
        if i == 0:
            c.website = "https://technovector.demo"
        db.add(c)
        companies.append(c)
    db.flush()

    # ------------------------------------------------------------ кандидаты
    athletes = [a for a in reg["athletes"] if a.get("_seed_linked")]
    cfg = cat_config()
    cands: list[CandidateProfile] = []
    item_rows: list[TestItem] = []
    stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    used_codes = set()
    n_total = settings.seed_candidates
    athlete_iter = iter(athletes)
    fsp_share = min(0.9, len(athletes) / max(1, n_total))  # доля кандидатов с историей ФСП (≈36% при 720)
    for i in range(n_total):
        athlete = next(athlete_iter, None) if rng.random() < fsp_share else None
        if athlete:
            spec = athlete["_spec"]
            theta = max(-2.3, min(2.6, 0.75 * athlete["_latent"] + rng.gauss(0, 0.45)))
            name, city = athlete["full_name"], athlete["city"]
        else:
            spec = wchoice(rng, SPEC_WEIGHTS)
            g = wchoice(rng, GRADE_WEIGHTS)
            lo = GRADES[g]["cut"]
            hi = GRADES[GRADE_ORDER[GRADE_ORDER.index(g) + 1]]["cut"] if g != "senior" else 2.4
            theta = rng.uniform(lo - (0.3 if g == "intern" else 0), hi)
            female = rng.random() < 0.3
            name = f"{rng.choice(_FIRST_F if female else _FIRST_M)} {rng.choice(_LAST)}{'а' if female else ''}"
            city = rng.choices(CITIES, [35, 15] + [3] * (len(CITIES) - 2))[0]
        true_grade = grade_from_theta(theta) or "intern"
        lang = wchoice(rng, LANG_WEIGHTS[spec]) if spec in LANG_WEIGHTS else SPECIALIZATIONS[spec]["langs"][0]
        framework = wchoice(rng, {"react": 0.65, "vue": 0.25, "angular": 0.1}) if spec == "frontend" else None
        fsp_stack: list[str] = []
        if athlete:  # язык и навыки участника согласованы со стеком, на котором он выступал на соревнованиях ФСП
            for r in results[athlete["fsp_id"]]:
                fsp_stack += [x for x in r.get("stack", []) if x not in fsp_stack]
            lang = next((code for skill, code in STACK_LANG.get(spec, []) if skill in fsp_stack), lang)
            if spec == "frontend":
                framework = next((code for skill, code in [("React", "react"), ("Vue", "vue")] if skill in fsp_stack), framework)
        stack_key = (spec, framework if spec == "frontend" else lang)
        pool = content.TRACK_STACK.get(stack_key) or content.TRACK_STACK[(spec, SPECIALIZATIONS[spec]["langs"][0])]
        true_skills = list(dict.fromkeys(pool[:2] + rng.sample(pool[2:], min(len(pool) - 2, rng.randint(2, 5)))))
        true_skills += [x for x in fsp_stack if x not in true_skills and x != "Алгоритмы"]
        stuffer = rng.random() < 0.2
        declared_skills = [s for s in true_skills if rng.random() > 0.1]
        if stuffer:
            other = [s for (sp, _), st in content.TRACK_STACK.items() for s in st if s not in true_skills]
            declared_skills += rng.sample(other, 5)
            declared_skills = list(dict.fromkeys(declared_skills))
        gi = GRADE_ORDER.index(true_grade)
        r = rng.random()
        declared = GRADE_ORDER[min(3, gi + 1)] if r < 0.25 else (GRADE_ORDER[max(0, gi - 1)] if r < 0.33 else true_grade)
        years = {"intern": rng.uniform(0, 1), "junior": rng.uniform(0.8, 2.5), "middle": rng.uniform(2, 5.5), "senior": rng.uniform(4.5, 12)}[true_grade]
        if declared != true_grade and rng.random() < 0.5:
            years += 1.5 if GRADE_ORDER.index(declared) > gi else -0.5
        years = round(max(0, years) * 2) / 2
        u = User(email=f"cand{i:04d}@synthetic.draft", password_hash=None, role="candidate", email_verified=True,
                 created_at=now - timedelta(days=rng.randint(20, 400)))
        db.add(u)
        db.flush()
        code = None
        while not code or code in used_codes:
            code = "K-" + "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(5))
        used_codes.add(code)
        sal_med = MARKET_SALARY[spec][true_grade]
        salary = None if rng.random() < 0.08 else int(round(sal_med * math.exp(rng.gauss(0, 0.16)) * (0.9 + 0.3 * rng.random()), -4))
        c = CandidateProfile(
            user_id=u.id, public_code=code, full_name=name, headline=f"{content.TITLES[spec]}" + (f" · {pool[0]}" if pool else ""),
            phone=f"+79{rng.randint(10, 99)}{rng.randint(1000000, 9999999)}", telegram=f"@{translit(name.split()[0])}_{rng.randint(10, 999)}",
            github=f"https://github.com/{translit(name.split()[-1])}{rng.randint(1, 99)}" if rng.random() < 0.5 else None,
            city=city, relocation=rng.random() < 0.25, about=rng.choice(content.ABOUT), experience_years=years,
            work_formats=rng.choice([["remote"], ["hybrid"], ["office"], ["remote", "hybrid"], ["office", "hybrid"], ["remote", "hybrid", "office"]]),
            salary_from=salary, salary_to=int(salary * 1.2) if salary else None,
            search_status=rng.choices(["active", "open", "not_looking"], [0.4, 0.5, 0.1])[0], skills=declared_skills,
            roles=[spec], soft_skills=rng.sample(SOFT_SKILLS, rng.randint(2, 4)),
            domains=rng.sample(list(DOMAINS), rng.randint(0, 2)), experience=_experience(rng, spec, years, now),
            education=[{"place": rng.choice(content.UNIVERSITIES), "degree": rng.choice(["Бакалавр", "Магистр", "Специалист"]),
                        "year": now.year - int(years) - rng.randint(0, 2)}],
            direction=SPECIALIZATIONS[spec]["direction"], specialization=spec, primary_lang=lang, framework=framework, declared_grade=declared,
            team_role=("teamlead" if rng.random() < 0.3 else "techlead") if true_grade == "senior" and rng.random() < 0.4 else
            ("mentor" if rng.random() < 0.2 else "developer"),
            survey_completed_at=u.created_at + timedelta(days=1), visible=rng.random() < 0.95,
            privacy={"hide_name": rng.random() < 0.7, "hide_current_company": True, "show_salary": rng.random() < 0.9, "show_fsp": True,
                     "show_tasks": True},
            is_synthetic=True,
            synthetic_truth={"theta": round(theta, 3), "grade": true_grade, "skills": true_skills, "stuffer": stuffer, "spec": spec,
                             "fsp_athlete": athlete["fsp_id"] if athlete else None},
            created_at=u.created_at,
        )
        db.add(c)
        db.add(SurveyResponse(candidate_id=u.id, answers={"specialization": spec, "primary_lang": lang, "declared_grade": declared,
                                                          "experience_years": years}, created_at=c.survey_completed_at))
        db.add(Consent(user_id=u.id, kind="pd_processing", version="1.0", granted=True, created_at=u.created_at))
        db.add(Consent(user_id=u.id, kind="profile_publication", version="1.0", granted=c.visible, created_at=u.created_at))
        db.flush()
        # ---- тестирование тем же CAT-движком по истинной θ
        ctx = GenCtx(lang=lang, framework=framework, spec=spec)
        target = declared
        tested_at = now - timedelta(days=rng.randint(3, 160))
        final = None
        for attempt_no in range(2):
            res, st = simulate(theta, spec, ctx, target, SPECIALIZATIONS[spec]["blueprint"], random.Random(rng.randint(1, 10**9)), cfg)
            a = TestAttempt(candidate_id=u.id, specialization=spec, lang=lang, target_grade=target, status="completed", seed=rng.randint(1, 10**9),
                            blueprint={"weights": SPECIALIZATIONS[spec]["blueprint"], "lang": lang, "framework": framework},
                            started_at=tested_at, finished_at=tested_at + timedelta(minutes=rng.randint(18, 40)),
                            deadline_at=tested_at + timedelta(minutes=75), theta=round(res.theta, 4), se=round(res.se, 4),
                            p_target=round(res.p_target, 4), passed=res.passed, decision="confirmed" if res.passed else "failed",
                            upgrade_grade=res.upgrade_grade, suggested_grade=res.suggested_grade, topic_scores=res.topic_scores,
                            items_count=len(st.answered), flags={"probs": {k: round(v, 3) for k, v in res.probs.items()}}, is_synthetic=True)
            db.add(a)
            db.flush()
            for pos, x in enumerate(st.answered, start=1):
                item_rows.append(TestItem(attempt_id=a.id, position=pos, template_id=x.template_id, competency=x.competency, level=0, kind="synthetic",
                                          a=x.a, b=x.b, c=x.c, variant_seed=0, variant_hash="", payload={}, answer_key={},
                                          is_correct=x.correct, time_limit_s=0, presented_at=tested_at, answered_at=tested_at))
                stats[x.template_id][0] += 1
                stats[x.template_id][1] += int(x.correct)
            if res.passed:
                final = (a, res, target)
                break
            if not res.suggested_grade:
                break
            target = res.suggested_grade
            tested_at += timedelta(hours=rng.randint(1, 30))
        if final:
            a, res, g = final
            c.grade, c.theta, c.theta_se, c.topic_scores = g, a.theta, a.se, res.topic_scores
            c.grade_confirmed_at, c.grade_locked_until, c.last_attempt_id = a.finished_at, a.finished_at + timedelta(days=90), a.id
            db.add(GradeChange(candidate_id=u.id, specialization=spec, from_grade=None, to_grade=g, reason="initial", attempt_id=a.id,
                               created_at=a.finished_at))
            if res.upgrade_grade and rng.random() < 0.5:
                c.grade = res.upgrade_grade
                a.upgrade_accepted = True
                db.add(GradeChange(candidate_id=u.id, specialization=spec, from_grade=g, to_grade=res.upgrade_grade, reason="upgrade",
                                   attempt_id=a.id, created_at=a.finished_at))
            c.verified_skills = verified_skills(res.topic_scores, c, c.grade)
        else:
            c.theta, c.theta_se, c.topic_scores = a.theta, a.se, res.topic_scores
        c.last_activity_at = (c.grade_confirmed_at or tested_at) + timedelta(days=rng.randint(0, 20))
        if c.last_activity_at > now:
            c.last_activity_at = now - timedelta(days=1)
        if athlete:
            c.fsp_id, c.fsp_linked_at = athlete["fsp_id"], u.created_at + timedelta(days=2)
            u.fsp_sub = athlete["sub"]
            db.add(Consent(user_id=u.id, kind="fsp_data", version="1.0", granted=True, created_at=c.fsp_linked_at))
            apply_results(db, c, {"athlete": {k: v for k, v in athlete.items() if not k.startswith("_")}, "results": results[athlete["fsp_id"]]},
                          now)
        refresh_strength(c, now)
        cands.append(c)
    db.add_all(item_rows)
    for tid, (n, k) in stats.items():
        db.add(ItemStat(template_id=tid, administered=n, correct=k, recent=[]))
    db.flush()
    log.info("Кандидаты: %d, попыток тестирования с заданиями: %d", len(cands), len(item_rows))
    _extra_categories(cands, cfg, now)

    # ------------------------------------------------------------ задачи работодателей
    by_industry = defaultdict(list)
    for co in companies:
        by_industry[co.industry].append(co)
    tasks: list[EmployerTask] = []
    k = 0
    for spec, items in content.TASKS.items():
        for title, kind, desc, points, skills in items:
            co = companies[k % len(companies)]
            k += 1
            t = EmployerTask(employer_id=co.user_id, title=title, description=desc, specialization=spec, grades=["junior", "middle", "senior"],
                             kind=kind, est_minutes=rng.choice([20, 30, 45]), key_points=points, skills=skills, created_at=now - timedelta(days=60))
            db.add(t)
            tasks.append(t)
    db.flush()
    tasks_by_spec = defaultdict(list)
    for t in tasks:
        tasks_by_spec[t.specialization].append(t)
    for c in cands:
        if not c.grade or rng.random() > 0.35:
            continue
        truth = c.synthetic_truth
        for t in rng.sample(tasks_by_spec[c.specialization], min(len(tasks_by_spec[c.specialization]), rng.randint(1, 2))):
            when = now - timedelta(days=rng.randint(2, 50))
            quality = truth["theta"] - GRADES[c.grade]["center"] + rng.gauss(0, 0.7)
            sc = max(1, min(5, round(3.3 + 1.1 * quality)))
            covered = t.key_points[: max(1, min(len(t.key_points), sc - 1))]
            answer = "Предлагаю такой подход: " + "; ".join(f"учесть {p}" for p in covered) + ". Далее — мониторинг и проверка на нагрузке."
            a = TaskAssignment(task_id=t.id, candidate_id=c.user_id, status="reviewed", assigned_at=when, due_at=when + timedelta(days=7),
                               answer=answer, submitted_at=when + timedelta(days=1), score=sc, feedback=rng.choice(
                                   ["Хорошо структурировано", "Не хватило деталей по отказоустойчивости", "Отличное решение!", "Есть спорные места"]),
                               reviewed_at=when + timedelta(days=2))
            a.task = t
            a.auto_score, a.auto_details = auto_score(t, answer)
            db.add(a)
        db.flush()
        recompute_task_score(db, c)
        c.last_activity_at = max(c.last_activity_at, now - timedelta(days=rng.randint(1, 30)))
        refresh_strength(c, now)

    # ------------------------------------------------------------ вакансии
    vacancies: list[Vacancy] = []
    for spec, items in content.VACANCIES.items():
        for title, must, nice, desc in items:
            for gi, grade in enumerate(rng.sample(["junior", "middle", "middle", "senior"], 2)):
                co = rng.choice(companies[1:]) if (len(vacancies) % 4) else companies[0]
                med = MARKET_SALARY[spec][grade]
                lo = int(round(med * rng.uniform(0.85, 1.0), -4))
                v = Vacancy(employer_id=co.user_id, title=f"{title}" + ("" if grade == "middle" else f" ({GRADES[grade]['name']})"),
                            description=f"{desc}\n\nКомпания: {co.name}. Мы предлагаем: официальное оформление, ДМС, бюджет на обучение и конференции.",
                            specialization=spec, grade=grade, must_skills=must, nice_skills=nice,
                            work_formats=rng.choice([["remote"], ["hybrid"], ["office", "hybrid"], ["remote", "hybrid"]]), city=co.city,
                            salary_from=lo, salary_to=int(round(lo * rng.uniform(1.2, 1.4), -4)), status="published", risk_flags=[],
                            created_at=now - timedelta(days=rng.randint(1, 40)))
                db.add(v)
                vacancies.append(v)
    db.flush()

    # ------------------------------------------------------------ потребности и подборки
    graded = [c for c in cands if c.grade]
    for c in companies:
        refresh_trust(db, c)
    needs_spec = [
        (companies[0], "Backend-разработчик в команду биллинга", "backend", ["middle"], ["Python", "PostgreSQL", "Docker"], ["Kafka", "Redis"],
         220000, 300000, ["hybrid", "remote"], 0.6, ["fintech", "it_services"],
         "Команда биллинга B2B-платформы: расчёт тарифов, интеграции с платёжными системами, высокая нагрузка. Асинхронный Python, события в Kafka."),
        (companies[0], "Senior Frontend (React) в дизайн-систему", "frontend", ["senior"], ["React", "TypeScript"], ["Next.js", "CSS"],
         330000, 430000, ["remote", "hybrid"], 0.4, [], "Развитие дизайн-системы и личного кабинета: компоненты, доступность, производительность."),
        (companies[0], "Стажёр / Junior аналитик данных", "data_analyst", ["intern", "junior"], ["SQL", "Python"], ["A/B-тестирование"],
         60000, 110000, ["office", "hybrid"], 0.7, [], "Помощь продуктовой команде: отчёты, SQL-выгрузки, анализ экспериментов. Наставник с первого дня."),
        (companies[1], "Go-разработчик платёжного ядра", "backend", ["middle", "senior"], ["Go", "PostgreSQL", "Kafka"], ["Kubernetes"],
         280000, 420000, ["remote", "hybrid"], 0.5, ["fintech"], "Платёжное ядро банка: идемпотентность, распределённые транзакции."),
        (companies[6], "Аналитик SOC", "infosec", ["junior", "middle"], ["SIEM", "Анализ инцидентов"], ["Python"], 120000, 220000,
         ["office", "hybrid"], 0.8, ["security"], "Круглосуточный мониторинг и расследование инцидентов."),
        (companies[13], "ML-инженер (NLP)", "ml", ["middle", "senior"], ["Python", "Машинное обучение", "PyTorch"], ["NLP"], 300000, 450000,
         ["remote"], 0.6, [], "LLM-ассистенты для промышленности: дообучение, оценка качества, инференс."),
        (companies[2], "Android-разработчик", "mobile", ["middle"], ["Kotlin", "Android SDK"], ["Jetpack Compose"], 220000, 300000,
         ["hybrid"], 0.5, ["ecommerce"], "Мобильное приложение маркетплейса."),
    ]
    needs = []
    for co, title, spec, grades, must, nice, sf, st_, fmts, fw, doms, desc in needs_spec:
        n = HiringNeed(employer_id=co.user_id, title=title, description=desc, specialization=spec, grades=grades, must_skills=must,
                       nice_skills=nice, work_formats=fmts, city=co.city, salary_from=sf, salary_to=st_, fsp_weight=fw, domains=doms,
                       created_at=now - timedelta(days=rng.randint(2, 15)))
        db.add(n)
        needs.append(n)
    db.commit()
    for n in needs:
        run_need(db, n, now)

    # ------------------------------------------------------------ приглашения (история для аналитики)
    statuses = ["sent", "viewed", "accepted", "declined"]
    for n in needs:
        co = db.get(Company, n.employer_id)
        from app.models import ShortlistEntry

        top = db.scalars(select(ShortlistEntry).where(ShortlistEntry.need_id == n.id).order_by(ShortlistEntry.rank).limit(8)).all()
        take = top[:3] if n.employer_id == companies[0].user_id else top[:7]
        for e in take:
            st = rng.choices(statuses, [0.25, 0.2, 0.35, 0.2])[0]
            created = now - timedelta(days=rng.randint(1, 18), hours=rng.randint(0, 20))
            inv = Invitation(employer_id=co.user_id, candidate_id=e.candidate_id, need_id=n.id, title=n.title,
                             description=f"{n.description} Предлагаем {n.salary_from // 1000}–{n.salary_to // 1000} тыс. ₽, гибкий график и сильную команду.",
                             salary_from=n.salary_from, salary_to=n.salary_to, work_format=n.work_formats[0] if n.work_formats else None,
                             city=n.city, contact_method=f"{co.contact_name}, {co.contact_email}, Telegram {co.telegram}", status=st,
                             match_score=e.score, explanation=e.explanation, risk_flags=[], created_at=created,
                             expires_at=created + timedelta(days=10))
            if st in ("viewed", "accepted", "declined"):
                inv.viewed_at = created + timedelta(hours=rng.randint(1, 30))
            if st in ("accepted", "declined"):
                inv.responded_at = inv.viewed_at + timedelta(hours=rng.randint(1, 48))
            if st == "accepted":
                inv.stage = rng.choice(["contact", "interview", "interview", "offer"])
                inv.candidate_message = "Здравствуйте! Интересно, давайте созвонимся."
            if st == "declined":
                inv.decline_reason = rng.choices(list(DECLINE_REASONS), [0.4, 0.15, 0.15, 0.05, 0.15, 0.05, 0.05])[0]
            if inv.expires_at < now and st in ("sent", "viewed"):
                inv.status = "expired"
            db.add(inv)
            e.mark = "starred"

    # ------------------------------------------------------------ отклики
    vac_by_spec = defaultdict(list)
    for v in vacancies:
        vac_by_spec[v.specialization].append(v)
    for c in graded:
        if rng.random() > 0.22 or not c.visible:
            continue
        for v in rng.sample(vac_by_spec[c.specialization], min(len(vac_by_spec[c.specialization]), rng.randint(1, 2))):
            db.add(Application(vacancy_id=v.id, candidate_id=c.user_id, cover_letter="Здравствуйте! Мой опыт и подтверждённый грейд соответствуют вакансии.",
                               status=rng.choices(["sent", "viewed", "interview", "rejected"], [0.5, 0.25, 0.15, 0.1])[0],
                               created_at=now - timedelta(days=rng.randint(0, 20))))
    db.flush()

    _demo_accounts(db, rng, pw, cands, companies, tasks_by_spec, vacancies, now)
    for c in companies:
        refresh_trust(db, c)
    db.commit()
    recompute_percentiles(db)
    for n in needs:
        run_need(db, n, now)
    db.commit()


def _experience(rng: random.Random, spec: str, years: float, now) -> list[dict]:
    out, left, end_year = [], years, now.year
    while left > 0.4 and len(out) < 3:
        dur = min(left, rng.uniform(1, 3.5))
        start_year = int(end_year - dur)
        out.append({"company": rng.choice(content.PAST_COMPANIES), "title": content.TITLES[spec], "start": str(start_year),
                    "end": None if not out else str(end_year),
                    "description": "Разработка и поддержка сервисов, участие в код-ревью и планировании."})
        left -= dur
        end_year = start_year
    return out


def _extra_categories(cands: list[CandidateProfile], cfg, now) -> None:
    """Часть кандидатов работает и в смежной специализации: дополнительная категория с заявленным грейдом, у части —
    подтверждённым тем же CAT-движком. Отдельный генератор случайных чисел: основная выборка (и валидация) не меняется."""
    xrng = random.Random(4242)
    n = 0
    for c in cands:
        if not c.grade or not c.visible or xrng.random() > 0.12:
            continue
        spec2 = xrng.choice(RELATED_SPECS[c.specialization])
        info = SPECIALIZATIONS[spec2]
        theta2 = c.synthetic_truth["theta"] - xrng.uniform(0.3, 1.1)  # во второй специализации обычно слабее
        declared2 = grade_from_theta(theta2 + xrng.gauss(0, 0.3)) or "intern"
        row = CandidateCategory(direction=info["direction"], specialization=spec2, primary_lang=info["langs"][0],
                                framework="react" if spec2 == "frontend" else None, declared_grade=declared2, topic_scores={}, verified_skills=[],
                                created_at=now - timedelta(days=xrng.randint(5, 90)))
        if xrng.random() < 0.6:
            res, _ = simulate(theta2, spec2, GenCtx(lang=row.primary_lang, framework=row.framework, spec=spec2), declared2, info["blueprint"],
                              random.Random(xrng.randint(1, 10**9)), cfg)
            if res.passed:
                row.grade, row.theta, row.theta_se, row.topic_scores = declared2, round(res.theta, 4), round(res.se, 4), res.topic_scores
                row.grade_confirmed_at = now - timedelta(days=xrng.randint(2, 60))
                row.grade_locked_until = row.grade_confirmed_at + timedelta(days=90)
                row.verified_skills = verified_skills(res.topic_scores, row, declared2)
        c.extra_categories.append(row)
        n += 1
    log.info("Дополнительные категории: %d", n)


def _demo_accounts(db, rng, pw, cands, companies, tasks_by_spec, vacancies, now) -> None:
    """Демо-аккаунты для жюри: кандидат с историей ФСП, кандидат без ФСП, новый кандидат, работодатель, админ."""
    # 1) backend middle (Python) с достижениями ФСП
    pick = next((c for c in cands if c.specialization == "backend" and c.primary_lang == "python" and c.grade == "middle" and c.fsp_score > 0.3),
                None) or next(c for c in cands if c.grade and c.fsp_score > 0)
    _make_demo(db, pick, "candidate@draft.demo", pw)
    pick.full_name = pick.full_name or "Демо Кандидат"
    pick.headline = "Backend-разработчик · Python, PostgreSQL"
    pick.search_status, pick.visible = "active", True
    pick.privacy = {**pick.privacy, "hide_name": True}
    if not any(x.specialization == "devops" for x in pick.extra_categories):
        pick.extra_categories.append(CandidateCategory(direction="infra", specialization="devops", primary_lang="python", declared_grade="junior",
                                                       topic_scores={}, verified_skills=[], created_at=now - timedelta(days=12)))
    # приглашения: два новых и одно принятое
    others = [c for c in companies[1:6]]
    for i, co in enumerate(others[:3]):
        st = ["sent", "sent", "accepted"][i]
        created = now - timedelta(days=i + 1, hours=3)
        inv = Invitation(employer_id=co.user_id, candidate_id=pick.user_id,
                         title=["Python-разработчик в команду платежей", "Backend-разработчик (FastAPI)", "Разработчик интеграций"][i],
                         description=["Ищем инженера в команду платёжных сервисов: асинхронный Python, PostgreSQL, Kafka. Вас выбрали по подтверждённому грейду и результатам ФСП.",
                                      "Сервисы аналитики для 3 млн пользователей. Нужен опыт с FastAPI и PostgreSQL, остальное подскажем.",
                                      "Интеграции с партнёрами и внутренние API. Команда из 5 человек, гибридный формат."][i],
                         salary_from=[240000, 230000, 210000][i], salary_to=[310000, 290000, 270000][i], work_format=["hybrid", "remote", "hybrid"][i],
                         city=co.city, contact_method=f"{co.contact_name}, {co.contact_email}", status=st, risk_flags=[], created_at=created,
                         expires_at=created + timedelta(days=10), match_score=78.0 - i * 4,
                         explanation={"reasons": [f"Категория Backend · Middle подтверждена адаптивным тестом",
                                                  "Подтверждены тестом: Python, SQL", "Достижения ФСП в продуктовом программировании"]})
        if st == "accepted":
            inv.viewed_at = inv.responded_at = created + timedelta(hours=5)
            inv.stage, inv.candidate_message = "interview", "Добрый день! Готов к созвону на этой неделе."
        db.add(inv)
        if st == "accepted":
            # короткая переписка на платформе после принятия — без обмена контактами
            db.flush()
            for k, (role, text) in enumerate([("employer", "Спасибо, что откликнулись! Удобно созвониться в четверг в 16:00?"),
                                              ("candidate", "Да, четверг подходит. Пришлите, пожалуйста, ссылку на встречу.")]):
                db.add(Message(invitation_id=inv.id, sender_role=role, text=text, created_at=created + timedelta(hours=6 + k),
                               sender_id=co.user_id if role == "employer" else pick.user_id, read_at=created + timedelta(hours=7 + k)))
    t = next(iter(tasks_by_spec["backend"]), None)
    if t and not db.scalar(select(TaskAssignment).where(TaskAssignment.task_id == t.id, TaskAssignment.candidate_id == pick.user_id)):
        db.add(TaskAssignment(task_id=t.id, candidate_id=pick.user_id, status="assigned", assigned_at=now - timedelta(days=1),
                              due_at=now + timedelta(days=6)))
    # 2) frontend junior без истории ФСП
    p2 = next((c for c in cands if c.specialization == "frontend" and c.grade == "junior" and not c.fsp_id and c.framework == "react"), None) or \
        next(c for c in cands if c.grade and not c.fsp_id)
    _make_demo(db, p2, "candidate2@draft.demo", pw)
    p2.search_status, p2.visible = "open", True
    # 3) новый кандидат — пройти путь с нуля
    # новые кандидаты для самостоятельного прохождения: newbie и пять аккаунтов экспертов жюри (режим эксперта)
    for i, email in enumerate(["newbie@draft.demo"] + [f"expert{k}@draft.demo" for k in range(1, 6)]):
        u = User(email=email, password_hash=pw, role="candidate", email_verified=True, created_at=now)
        db.add(u)
        db.flush()
        db.add(CandidateProfile(user_id=u.id, public_code=f"K-NEW{i + 1:02d}", visible=True))
        db.add(Consent(user_id=u.id, kind="pd_processing", version="1.0", granted=True))
        db.add(Consent(user_id=u.id, kind="profile_publication", version="1.0", granted=True))
    db.flush()


def _make_demo(db, c: CandidateProfile, email: str, pw: str) -> None:
    u = db.get(User, c.user_id)
    u.email, u.password_hash = email, pw
    c.is_synthetic = False  # демо-аккаунт получает реальные уведомления и не участвует в валидации


_FIRST_M = ["Александр", "Дмитрий", "Максим", "Сергей", "Андрей", "Алексей", "Артём", "Илья", "Кирилл", "Михаил", "Никита", "Матвей",
            "Роман", "Егор", "Арсений", "Иван", "Денис", "Евгений", "Даниил", "Тимофей", "Владислав", "Игорь", "Павел", "Руслан", "Марк"]
_FIRST_F = ["Анна", "Мария", "Елена", "Дарья", "Алина", "Ирина", "Екатерина", "Арина", "Полина", "Ольга", "Юлия", "Татьяна", "Наталья",
            "Виктория", "Елизавета", "Анастасия", "Валерия", "Ксения", "София", "Вероника"]
_LAST = ["Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев", "Петров", "Соколов", "Михайлов", "Новиков", "Фёдоров", "Морозов", "Волков",
         "Алексеев", "Лебедев", "Семёнов", "Егоров", "Павлов", "Козлов", "Степанов", "Николаев", "Орлов", "Андреев", "Макаров", "Никитин",
         "Захаров", "Зайцев", "Соловьёв", "Борисов", "Яковлев", "Григорьев", "Романов", "Воробьёв", "Сергеев", "Кузьмин", "Фролов",
         "Тихонов", "Лазарев", "Медведев", "Ершов", "Никифоров", "Субботин", "Шестаков", "Голубев", "Виноградов", "Богданов"]
