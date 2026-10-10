"""Правила грейда, согласованные с постановщиками: повышение — только отдельным тестом, шаг вниз после неудачи не
расходует попытку и не блокирует повтор, неподтверждённый грейд виден работодателю ниже подтверждённых."""
from tests.conftest import login
from tests.test_api_flow import API, answer_all, register_candidate


def _survey(client, h, grade="middle"):
    r = client.post(f"{API}/candidate/survey", headers=h, json={"direction": "development", "specialization": "backend", "primary_lang": "python",
                                                               "stack": ["Python", "PostgreSQL"], "experience_years": 3,
                                                               "declared_grade": grade, "work_formats": ["remote"]})
    assert r.status_code == 200


def _start(client, h, grade):
    r = client.post(f"{API}/candidate/assessment/attempts", headers=h, json={"target_grade": grade})
    assert r.status_code in (200, 201), r.text
    return r.json()["attempt_id"]


def test_upgrade_requires_separate_test(client):
    h = register_candidate(client, "upgrade@test.ru")
    _survey(client, h, "middle")
    first = _start(client, h, "middle")
    res = answer_all(client, h, first, correct=True)
    assert res["passed"] and res["upgrade_grade"] == "senior"
    me = client.get(f"{API}/candidate/me", headers=h).json()
    assert me["grade"] == "middle"  # автоповышения нет
    r = client.post(f"{API}/candidate/assessment/attempts/{first}/upgrade", headers=h)
    assert r.status_code == 201 and r.json()["target_grade"] == "senior"
    assert client.get(f"{API}/candidate/me", headers=h).json()["grade"] == "middle"  # до прохождения теста грейд прежний
    # предложение используется один раз
    assert client.post(f"{API}/candidate/assessment/attempts/{first}/upgrade", headers=h).status_code == 409
    res2 = answer_all(client, h, r.json()["attempt_id"], correct=False)
    assert not res2["passed"]
    me = client.get(f"{API}/candidate/me", headers=h).json()
    assert me["grade"] == "middle"  # неудача на повышении грейд не понижает
    el = client.get(f"{API}/candidate/assessment/eligibility", headers=h).json()
    assert el["attempts_30d"] == 1 and not el["grades"]["senior"]["allowed"]  # тест на повышение вне лимита, дальше — обычные правила


def test_step_down_after_failure_is_free_and_does_not_lock(client):
    h = register_candidate(client, "stepdown@test.ru")
    _survey(client, h, "senior")
    res = answer_all(client, h, _start(client, h, "senior"), correct=False)
    assert not res["passed"]
    el = client.get(f"{API}/candidate/assessment/eligibility", headers=h).json()
    assert el["grades"]["middle"]["allowed"] and el["grades"]["middle"]["mode"] == "step_down"
    assert not el["grades"]["senior"]["allowed"]  # повтор того же уровня — после паузы
    res = answer_all(client, h, _start(client, h, "middle"), correct=True)
    assert res["passed"]
    me = client.get(f"{API}/candidate/me", headers=h).json()
    assert me["grade"] == "middle" and not me["grade_locked_until"]  # шаг вниз не запускает 90-дневную блокировку
    el = client.get(f"{API}/candidate/assessment/eligibility", headers=h).json()
    assert el["attempts_30d"] == 1  # шаг вниз попытку не расходует
    assert el["grades"]["senior"]["available_at"] and not el["locked_until"]  # повтор Senior — через обычные 14 дней


def test_unconfirmed_grade_is_shown_below_confirmed(client):
    h = register_candidate(client, "unconfirmed@test.ru")
    _survey(client, h, "middle")
    me = client.get(f"{API}/candidate/me", headers=h).json()
    he = login(client, "employer@draft.demo")
    found = client.get(f"{API}/employer/candidates", headers=he, params={"specialization": "backend", "grades": ["middle"], "limit": 100,
                                                                         "sort": "strength"}).json()
    assert found["unconfirmed"] >= 1
    statuses = [c["grade_status"] for c in found["items"]]
    assert statuses == sorted(statuses)  # "confirmed" < "unconfirmed": неподтверждённые — в конце
    only = client.get(f"{API}/employer/candidates", headers=he, params={"specialization": "backend", "confirmed_only": True}).json()
    assert only["unconfirmed"] == 0
    need = client.post(f"{API}/employer/needs", headers=he, json={"title": "Python", "specialization": "backend", "grades": ["middle"],
                                                                  "must_skills": ["Python"], "salary_from": 150000, "salary_to": 400000,
                                                                  "work_formats": ["remote"]}).json()
    sl = client.get(f"{API}/employer/needs/{need['id']}/shortlist", headers=he, params={"limit": 100}).json()
    order = [c["match"]["grade_status"] for c in sl["items"]]
    assert order == sorted(order)
    card = client.get(f"{API}/employer/candidates/{me['id']}", headers=he).json()
    assert card["grade_status"] == "unconfirmed" and "не подтверждён" in card["category"]


def test_expert_mode_separates_grades_on_demo_accounts(client):
    """Режим эксперта: автопрохождение синтетическим профилем заданного уровня — сильный проходит, слабый нет."""
    h = {"Authorization": f"Bearer {client.post(f'{API}/auth/login', json={'email': 'expert1@draft.demo', 'password': 'Demo2026!'}).json()['access_token']}"}
    assert client.get(f"{API}/candidate/me", headers=h).json()["expert_mode"]
    _survey(client, h, "middle")
    strong = client.post(f"{API}/candidate/assessment/attempts/{_start(client, h, 'middle')}/expert/simulate", headers=h,
                         json={"theta": 1.8, "seed": 1}).json()
    assert strong["finished"] and strong["result"]["passed"]
    h2 = {"Authorization": f"Bearer {client.post(f'{API}/auth/login', json={'email': 'expert2@draft.demo', 'password': 'Demo2026!'}).json()['access_token']}"}
    _survey(client, h2, "middle")
    weak = client.post(f"{API}/candidate/assessment/attempts/{_start(client, h2, 'middle')}/expert/simulate", headers=h2,
                       json={"theta": -1.6, "seed": 1}).json()
    assert not weak["result"]["passed"]
    # обычному кандидату режим недоступен
    hc = register_candidate(client, "notexpert@test.ru")
    _survey(client, hc, "junior")
    a = _start(client, hc, "junior")
    assert client.post(f"{API}/candidate/assessment/attempts/{a}/expert/simulate", headers=hc, json={"theta": 1}).status_code == 403


def _answer_all_with_events(client, h, attempt_id, events):
    from app.core.db import SessionLocal
    from app.models import TestItem
    item = client.get(f"{API}/candidate/assessment/attempts/{attempt_id}", headers=h).json()["item"]
    n = 0
    while True:
        n += 1
        with SessionLocal() as db:
            key = db.get(TestItem, item["item_id"]).answer_key
        resp = key["correct"][0] if key["kind"] == "single" else key["correct"] if key["kind"] == "multi" else (
            key["value"][0] if isinstance(key["value"], list) else key["value"])
        r = client.post(f"{API}/candidate/assessment/attempts/{attempt_id}/answer", headers=h,
                        json={"item_id": item["item_id"], "response": resp, "time_ms": 20000, "events": events}).json()
        if r["finished"]:
            return r["result"], n
        item = r["item"]


def test_suspicious_pass_requires_confirmation_form(client):
    h = register_candidate(client, "confirm@test.ru")
    _survey(client, h, "middle")
    res, _ = _answer_all_with_events(client, h, _start(client, h, "middle"), {"blur": 1, "paste": 1})  # вставки и уходы со вкладки
    assert not res["passed"] and res["decision"] == "needs_confirmation"
    assert client.get(f"{API}/candidate/me", headers=h).json()["grade"] is None  # грейд не присвоен
    el = client.get(f"{API}/candidate/assessment/eligibility", headers=h).json()
    assert el["confirmation"]["grade"] == "middle" and el["grades"]["middle"]["mode"] == "confirm" and el["attempts_30d"] == 1
    a = _start(client, h, "middle")
    item = client.get(f"{API}/candidate/assessment/attempts/{a}", headers=h).json()["item"]
    from app.core.db import SessionLocal
    from app.models import TestItem
    with SessionLocal() as db:
        it = db.get(TestItem, item["item_id"])
        from app.testing.bank import REGISTRY
        assert it.time_limit_s < REGISTRY[it.template_id].time_limit  # строже таймер
    res, n = _answer_all_with_events(client, h, a, {})
    assert res["passed"] and res["decision"] == "confirmed" and 6 <= n <= 10
    assert client.get(f"{API}/candidate/me", headers=h).json()["grade"] == "middle"


def test_server_never_reissues_a_seen_variant():
    """Если вариант уже кто-то видел (хеш есть в БД), сервер генерирует другой."""
    from app.testing.bank import REGISTRY, GenCtx, render
    from app.testing.service import fresh_variant

    t = REGISTRY["sql.left_join"]
    ctx = GenCtx(lang="python", spec="backend")
    first = render(t, 12345, ctx)[2]

    class SeenDB:  # имитация БД: «уже выдан» только первый вариант
        def scalar(self, stmt):
            return 1 if first in str(stmt.compile(compile_kwargs={"literal_binds": True})) else None

    seed, _, _, h = fresh_variant(SeenDB(), t, ctx, 12345)
    assert h != first and seed != 12345
