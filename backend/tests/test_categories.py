"""Несколько категорий у одного кандидата (по письменным ответам организаторов — «будет плюсом»): у каждой свой грейд,
подтверждаемый только тестом; работодатель находит кандидата во всех категориях."""
from tests.conftest import login
from tests.test_api_flow import API, answer_all, register_candidate
from tests.test_grade_rules import _start, _survey


def test_additional_category_lifecycle(client):
    h = register_candidate(client, "twocats@test.ru")
    _survey(client, h, "middle")
    res = answer_all(client, h, _start(client, h, "middle"), correct=True)
    assert res["passed"]

    r = client.post(f"{API}/candidate/categories", headers=h, json={"specialization": "devops", "declared_grade": "junior"})
    assert r.status_code == 201, r.text
    items = {c["specialization"]: c for c in r.json()["items"]}
    assert items["backend"]["main"] and items["backend"]["confirmed"]
    assert not items["devops"]["main"] and not items["devops"]["confirmed"] and items["devops"]["declared_grade"] == "junior"
    # повтор и основная специализация — отказ; опрос не может «перепрыгнуть» на дополнительную
    assert client.post(f"{API}/candidate/categories", headers=h, json={"specialization": "devops", "declared_grade": "middle"}).status_code == 409
    assert client.post(f"{API}/candidate/categories", headers=h, json={"specialization": "backend", "declared_grade": "middle"}).status_code == 409
    r = client.post(f"{API}/candidate/survey", headers=h, json={"direction": "infra", "specialization": "devops", "experience_years": 2,
                                                               "declared_grade": "junior"})
    assert r.status_code == 409

    me = client.get(f"{API}/candidate/me", headers=h).json()
    he = login(client, "employer@draft.demo")
    # работодатель находит кандидата по дополнительной категории — со статусом «не подтверждён»
    found = client.get(f"{API}/employer/candidates", headers=he, params={"specialization": "devops", "grades": ["junior"], "limit": 100}).json()
    card = next(c for c in found["items"] if c["id"] == me["id"])
    assert card["specialization"] == "devops" and card["grade_status"] == "unconfirmed" and card["matched_additional"]
    assert any("дополнительная категория" in w for w in card["why"])
    # и по основной — как раньше
    found = client.get(f"{API}/employer/candidates", headers=he, params={"specialization": "backend", "grades": ["middle"], "limit": 100}).json()
    card = next(c for c in found["items"] if c["id"] == me["id"])
    assert card["specialization"] == "backend" and card["grade_status"] == "confirmed"
    assert {c["specialization"] for c in card["categories"]} == {"backend", "devops"}
    # подборка по потребности DevOps объясняет, по какой категории кандидат найден
    need = client.post(f"{API}/employer/needs", headers=he, json={"title": "DevOps", "specialization": "devops", "grades": ["junior"],
                                                                  "must_skills": ["Docker"], "salary_from": 100000, "salary_to": 400000,
                                                                  "work_formats": ["remote"]}).json()
    sl = client.get(f"{API}/employer/needs/{need['id']}/shortlist", headers=he, params={"limit": 100}).json()
    hit = next((c for c in sl["items"] if c["id"] == me["id"]), None)
    assert hit and hit["match"]["category"]["specialization"] == "devops" and hit["match"]["category"]["additional"]

    # сделать DevOps основной: категории меняются местами, подтверждённый backend сохраняется в дополнительной
    r = client.post(f"{API}/candidate/categories/devops/main", headers=h)
    assert r.status_code == 200, r.text
    items = {c["specialization"]: c for c in r.json()["items"]}
    assert items["devops"]["main"] and not items["devops"]["confirmed"]
    assert not items["backend"]["main"] and items["backend"]["confirmed"] and items["backend"]["grade"] == "middle"
    el = r.json()["eligibility"]
    assert el["grades"]["junior"]["allowed"]  # паузы и блокировки — свои у каждой категории
    res = answer_all(client, h, _start(client, h, "junior"), correct=True)
    assert res["passed"] and res["specialization"] == "devops"
    items = {c["specialization"]: c for c in client.get(f"{API}/candidate/categories", headers=h).json()["items"]}
    assert items["devops"]["confirmed"] and items["devops"]["grade"] == "junior" and items["backend"]["grade"] == "middle"

    # вернуть backend основной и удалить DevOps
    assert client.post(f"{API}/candidate/categories/backend/main", headers=h).status_code == 200
    me = client.get(f"{API}/candidate/me", headers=h).json()
    assert me["specialization"] == "backend" and me["grade"] == "middle"
    assert client.delete(f"{API}/candidate/categories/devops", headers=h).status_code == 200
    assert [c["specialization"] for c in client.get(f"{API}/candidate/categories", headers=h).json()["items"]] == ["backend"]


def test_category_limit(client):
    h = register_candidate(client, "manycats@test.ru")
    _survey(client, h, "junior")
    for spec in ("qa", "devops"):
        assert client.post(f"{API}/candidate/categories", headers=h, json={"specialization": spec, "declared_grade": "junior"}).status_code == 201
    r = client.post(f"{API}/candidate/categories", headers=h, json={"specialization": "ml", "declared_grade": "junior"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "too_many_categories"
