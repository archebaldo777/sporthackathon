"""Интеграция с ATS по определению организаторов: синхронизация вакансий, откликов и статусов через API — без ручного
дублирования в двух системах."""
from tests.conftest import login
from tests.test_api_flow import API, answer_all, register_candidate
from tests.test_grade_rules import _start, _survey


def test_ats_sync_vacancies_applications_statuses(client):
    he = login(client, "employer@draft.demo")
    key = client.post(f"{API}/employer/api-keys", headers=he, json={"name": "Huntflow"}).json()["key"]
    ats = {"X-API-Key": key}
    assert client.get(f"{API}/ats/v1/vacancies", headers={"X-API-Key": "drk_wrong_key_123"}).status_code == 401

    # вакансия из ATS: специализацию, грейд и навыки распознаёт разбор текста
    body = {"title": "Python-разработчик (Middle)", "salary_from": 220000, "salary_to": 290000,
            "description": "Сервис платежей. Обязательно: Python, FastAPI, PostgreSQL. Будет плюсом: Kafka. Удалённо."}
    r = client.put(f"{API}/ats/v1/vacancies/HF-1042", headers=ats, json=body)
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["created"] and v["external_id"] == "HF-1042" and v["specialization"] == "backend" and v["grade"] == "middle"
    assert {"Python", "PostgreSQL"} <= set(v["must_skills"]) and "specialization" in v["recognized"]
    # повторная синхронизация обновляет ту же вакансию, а не создаёт копию
    r = client.put(f"{API}/ats/v1/vacancies/HF-1042", headers=ats, json={**body, "salary_to": 310000})
    assert not r.json()["created"] and r.json()["id"] == v["id"] and r.json()["salary_to"] == 310000
    assert sum(1 for x in client.get(f"{API}/ats/v1/vacancies", headers=ats).json()["items"] if x["external_id"] == "HF-1042") == 1
    # без распознаваемой специализации — понятная ошибка, а не угаданная категория
    r = client.put(f"{API}/ats/v1/vacancies/HF-1043", headers=ats, json={**body, "title": "Специалист",
                                                                         "description": "Ищем человека в дружную команду, подробности на интервью"})
    assert r.status_code == 422

    # отклик кандидата приходит в ATS с контактами; статус из ATS видит кандидат
    h = register_candidate(client, "atsapply@test.ru")
    _survey(client, h, "middle")
    assert answer_all(client, h, _start(client, h, "middle"), correct=True)["passed"]
    app_id = client.post(f"{API}/candidate/applications", headers=h, json={"vacancy_id": v["id"]}).json()["id"]
    apps = client.get(f"{API}/ats/v1/applications", headers=ats).json()["items"]
    a = next(x for x in apps if x["application_id"] == app_id)
    assert a["external_id"] == "HF-1042" and a["candidate"]["email"] == "atsapply@test.ru"
    r = client.put(f"{API}/ats/v1/applications/{app_id}/status", headers=ats, params={"status": "interview"})
    assert r.status_code == 200 and r.json()["status"] == "interview"
    mine = client.get(f"{API}/candidate/applications", headers=h).json()
    items = mine["items"] if isinstance(mine, dict) else mine
    assert next(x for x in items if x["id"] == app_id)["status"] == "interview"
    assert client.put(f"{API}/ats/v1/applications/{app_id}/status", headers=ats, params={"status": "hired!"}).status_code == 400
