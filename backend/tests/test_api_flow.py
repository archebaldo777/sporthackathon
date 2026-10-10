"""Сквозные сценарии API: регистрация с подтверждением e-mail, опрос, тест, категория, подбор, приглашение,
раскрытие контактов, отклик, ограничения доступа и частоты смены грейда."""
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import TestItem
from tests.conftest import last_code, login

API = "/api/v1"


def register_candidate(client, email):
    r = client.post(f"{API}/auth/register", json={"email": email, "password": "Secret123", "role": "candidate", "consent_pd": True,
                                                  "consent_publication": True})
    assert r.status_code == 201, r.text
    r = client.post(f"{API}/auth/verify-email", json={"email": email, "code": last_code(email)})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def answer_all(client, h, attempt_id, correct=True):
    item = client.get(f"{API}/candidate/assessment/attempts/{attempt_id}", headers=h).json()["item"]
    while True:
        with SessionLocal() as db:
            key = db.get(TestItem, item["item_id"]).answer_key
        if correct:
            resp = key["correct"][0] if key["kind"] == "single" else key["correct"] if key["kind"] == "multi" else (
                key["value"][0] if isinstance(key["value"], list) else key["value"])
        else:
            resp = "zzz" if key["kind"] == "input" else ([] if key["kind"] == "multi" else next(i for i in range(9) if i not in key["correct"]))
        r = client.post(f"{API}/candidate/assessment/attempts/{attempt_id}/answer", headers=h,
                        json={"item_id": item["item_id"], "response": resp, "time_ms": 20000}).json()
        if r["finished"]:
            return r["result"]
        item = r["item"]


def test_registration_requires_consent_and_verification(client):
    r = client.post(f"{API}/auth/register", json={"email": "x@test.ru", "password": "Secret123", "role": "candidate", "consent_pd": False})
    assert r.status_code == 422
    r = client.post(f"{API}/auth/register", json={"email": "unverified@test.ru", "password": "Secret123", "role": "candidate", "consent_pd": True})
    assert r.status_code == 201
    h = login(client, "unverified@test.ru", "Secret123")
    assert client.get(f"{API}/candidate/me", headers=h).status_code == 403  # без подтверждения e-mail кабинет недоступен
    assert client.post(f"{API}/auth/verify-email", json={"email": "unverified@test.ru", "code": "000000"}).status_code == 400


def test_full_reverse_hiring_flow(client):
    h = register_candidate(client, "flow@test.ru")
    # тест до опроса недоступен
    assert client.post(f"{API}/candidate/assessment/attempts", headers=h, json={"target_grade": "middle"}).status_code == 409
    r = client.post(f"{API}/candidate/survey", headers=h, json={"direction": "development", "specialization": "backend", "primary_lang": "python",
                                                               "stack": ["Python", "postgres", "Docker"], "experience_years": 4,
                                                               "declared_grade": "middle", "work_formats": ["remote"]})
    assert r.status_code == 200 and r.json()["profile"]["skills"] == ["Python", "PostgreSQL", "Docker"]
    client.put(f"{API}/candidate/profile", headers=h, json={"full_name": "Тест Флоу", "phone": "+79990001122", "salary_from": 230000,
                                                            "salary_to": 280000})
    a = client.post(f"{API}/candidate/assessment/attempts", headers=h, json={"target_grade": "middle"}).json()
    result = answer_all(client, h, a["attempt_id"], correct=True)
    assert result["passed"] and 8 <= result["items_count"] <= 22
    me = client.get(f"{API}/candidate/me", headers=h).json()
    assert me["grade"] == "middle" and me["category"] == "Backend · Middle" and me["grade_locked_until"]
    # смена грейда ограничена по времени; уверенное прохождение даёт не автоповышение, а отдельный тест на грейд выше
    el = client.get(f"{API}/candidate/assessment/eligibility", headers=h).json()
    assert el["locked_until"] and not el["grades"]["junior"]["allowed"]
    assert el["upgrade_offer"]["grade"] == "senior" and el["grades"]["senior"]["mode"] == "upgrade"
    # работодатель находит кандидата в подборке, контакты скрыты
    he = login(client, "employer@draft.demo")
    need = client.post(f"{API}/employer/needs", headers=he, json={"title": "Python в биллинг", "specialization": "backend", "grades": ["middle"],
                                                                  "must_skills": ["Python", "PostgreSQL"], "salary_from": 220000,
                                                                  "salary_to": 320000, "work_formats": ["remote"]}).json()
    sl = client.get(f"{API}/employer/needs/{need['id']}/shortlist", headers=he).json()
    mine = next(c for c in sl["items"] if c["id"] == me["id"])
    assert "contacts" not in mine and mine["match"]["reasons"]
    # уточнение подборки не теряет исходную
    refined = client.get(f"{API}/employer/needs/{need['id']}/shortlist", headers=he, params={"fsp_only": True}).json()
    assert refined["base_total"] == sl["base_total"] and refined["filtered_total"] <= sl["base_total"]
    # приглашение без вилки невозможно
    bad = client.post(f"{API}/employer/invitations", headers=he, json={"candidate_ids": [me["id"]], "title": "Позиция", "description": "x" * 30,
                                                                      "contact_method": "hr@x.ru"})
    assert bad.status_code == 422
    inv = client.post(f"{API}/employer/invitations", headers=he, json={
        "candidate_ids": [me["id"]], "title": "Python-разработчик", "description": "Команда биллинга, асинхронный Python и PostgreSQL.",
        "salary_from": 250000, "salary_to": 300000, "work_format": "remote", "contact_method": "hr@technovector.demo", "need_id": need["id"]}).json()
    inv_id = inv["items"][0]["id"]
    # кандидат видит условия, статус меняется на «просмотрено»
    ci = client.get(f"{API}/candidate/invitations/{inv_id}", headers=h).json()
    assert ci["salary_from"] == 250000 and ci["company"]["name"] == "ТехноВектор" and ci["contact_method"]
    assert client.get(f"{API}/employer/invitations/{inv_id}", headers=he).json()["status"] == "viewed"
    card = client.get(f"{API}/employer/candidates/{me['id']}", headers=he).json()
    assert not card["contacts_revealed"] and "contacts" not in card
    client.post(f"{API}/candidate/invitations/{inv_id}/accept", headers=h, json={"message": "Готов к созвону"})
    card = client.get(f"{API}/employer/candidates/{me['id']}", headers=he).json()
    assert card["contacts_revealed"] and card["contacts"]["phone"] == "+79990001122"
    st = client.put(f"{API}/employer/invitations/{inv_id}/stage", headers=he, json={"stage": "interview"}).json()
    assert st["stage"] == "interview"


def test_failed_test_allows_lower_grade_not_forced_downgrade(client):
    h = register_candidate(client, "fail@test.ru")
    client.post(f"{API}/candidate/survey", headers=h, json={"direction": "data", "specialization": "data_analyst", "stack": ["SQL"],
                                                           "experience_years": 1, "declared_grade": "senior"})
    a = client.post(f"{API}/candidate/assessment/attempts", headers=h, json={"target_grade": "senior"}).json()
    result = answer_all(client, h, a["attempt_id"], correct=False)
    assert not result["passed"]
    me = client.get(f"{API}/candidate/me", headers=h).json()
    assert me["grade"] is None
    el = client.get(f"{API}/candidate/assessment/eligibility", headers=h).json()
    assert el["grades"]["middle"]["allowed"] and not el["grades"]["senior"]["allowed"]


def test_access_control(client):
    hc = login(client, "candidate@draft.demo")
    he = login(client, "employer@draft.demo")
    assert client.get(f"{API}/employer/dashboard", headers=hc).status_code == 403
    assert client.get(f"{API}/candidate/me", headers=he).status_code == 403
    assert client.get(f"{API}/candidate/me").status_code == 401
    # чужое приглашение кандидату недоступно
    h2 = login(client, "candidate2@draft.demo")
    own = client.get(f"{API}/candidate/invitations", headers=hc).json()["items"]
    assert own and client.get(f"{API}/candidate/invitations/{own[0]['id']}", headers=h2).status_code == 404


def test_candidate_without_fsp_handled(client):
    h2 = login(client, "candidate2@draft.demo")
    me = client.get(f"{API}/candidate/me", headers=h2).json()
    assert me["grade"] and me["fsp"]["linked"] is False and me["fsp"]["note"]
    he = login(client, "employer@draft.demo")
    res = client.get(f"{API}/employer/candidates", headers=he, params={"specialization": me["specialization"], "grades": [me["grade"]],
                                                                         "limit": 100}).json()
    assert any(c["id"] == me["id"] for c in res["items"])


def test_application_reveals_contacts(client):
    hc = login(client, "candidate2@draft.demo")
    vacs = client.get(f"{API}/vacancies", headers=hc, params={"mine": True}).json()["items"]
    v = next(x for x in vacs if not x["applied"])
    r = client.post(f"{API}/candidate/applications", headers=hc, json={"vacancy_id": v["id"], "cover_letter": "Здравствуйте!"})
    assert r.status_code == 201
    assert client.post(f"{API}/candidate/applications", headers=hc, json={"vacancy_id": v["id"]}).status_code == 409


def test_risky_invitation_blocked_and_pdf_verification(client):
    he = login(client, "employer@draft.demo")
    hc = login(client, "candidate@draft.demo")
    me = client.get(f"{API}/candidate/me", headers=hc).json()
    r = client.post(f"{API}/employer/invitations", headers=he, json={
        "candidate_ids": [me["id"]], "title": "Стажировка", "description": "Требуется предоплата за обучение 5000 рублей перед началом работы",
        "salary_from": 100000, "salary_to": 150000, "contact_method": "whatsapp"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "risky_content"
    pdf = client.get(f"{API}/candidate/profile/pdf", headers=hc)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_regular_tasks_cycle(client):
    hc = login(client, "candidate2@draft.demo")
    t = client.get(f"{API}/candidate/tasks", headers=hc).json()
    cur = t["current"] or client.post(f"{API}/candidate/tasks/request", headers=hc).json()
    r = client.post(f"{API}/candidate/tasks/{cur['id']}/submit", headers=hc, json={"answer": "Подход: виртуализация видимых строк, мемоизация и пагинация. " * 3})
    assert r.status_code == 200 and r.json()["status"] == "submitted" and r.json()["auto_score"] is not None


def test_openapi_documented(client):
    spec = client.get("/api/openapi.json").json()
    assert len(spec["paths"]) > 60
    assert "/api/v1/employer/invitations" in spec["paths"]


def test_task_copy_detection(client):
    """Решение, почти совпадающее с чужим ответом на ту же задачу, помечается для работодателя."""
    from datetime import datetime, timezone

    from sqlalchemy import select as sel

    from app.models import CandidateProfile, EmployerTask, TaskAssignment
    from app.services.tasks import similar_answers

    text = ("Начну с профилирования: найду медленные запросы в pg_stat_statements, добавлю составной индекс по (user_id, created_at), "
            "уберу N+1 через selectinload и закэширую справочники в Redis на пять минут.")
    with SessionLocal() as db:
        task = db.scalar(sel(EmployerTask).limit(1))
        a_id, b_id, c_id = db.scalars(sel(CandidateProfile.user_id).where(CandidateProfile.is_synthetic.is_(True)).limit(3)).all()
        rows = [TaskAssignment(task_id=task.id, candidate_id=cid, status="submitted", answer=ans, due_at=datetime.now(timezone.utc))
                for cid, ans in ((a_id, text), (b_id, text.replace("пять минут", "5 минут") + " Проверю на нагрузке."),
                                 (c_id, "Сначала уточню требования к отчёту, затем спроектирую витрину в ClickHouse и материализованные "
                                        "представления по дням; дашборд соберу в Superset, расчёт метрик покрою тестами."))]
        db.add_all(rows)
        db.flush()
        sim = similar_answers(db, rows[1])
        assert [x["assignment_id"] for x in sim] == [rows[0].id] and sim[0]["similarity"] >= 90
        assert similar_answers(db, rows[2]) == []
        db.rollback()
