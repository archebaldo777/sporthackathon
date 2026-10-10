"""После принятия приглашения: переписка на платформе и отзыв кандидатом доступа к контактам."""
from tests.conftest import login
from tests.test_api_flow import API, register_candidate
from tests.test_grade_rules import _survey


def _accepted_invitation(client, email):
    h = register_candidate(client, email)
    _survey(client, h, "junior")
    client.put(f"{API}/candidate/profile", headers=h, json={"full_name": "Чат Тестов", "phone": "+79990002233"})
    me = client.get(f"{API}/candidate/me", headers=h).json()
    he = login(client, "employer@draft.demo")
    inv = client.post(f"{API}/employer/invitations", headers=he, json={
        "candidate_ids": [me["id"]], "title": "Junior Python", "description": "Команда внутренних сервисов, Python и PostgreSQL.",
        "salary_from": 120000, "salary_to": 160000, "work_format": "remote", "contact_method": "hr@technovector.demo"})
    assert inv.status_code == 201, inv.text  # грейд не подтверждён, но пригласить можно
    inv_id = inv.json()["items"][0]["id"]
    return h, he, me, inv_id


def test_chat_after_acceptance(client):
    h, he, me, inv_id = _accepted_invitation(client, "chat@test.ru")
    # до принятия переписки нет — условия сначала, общение потом
    assert client.post(f"{API}/employer/invitations/{inv_id}/messages", headers=he, json={"text": "Привет"}).status_code == 409
    client.post(f"{API}/candidate/invitations/{inv_id}/accept", headers=h, json={})
    assert client.post(f"{API}/employer/invitations/{inv_id}/messages", headers=he, json={"text": "Удобно созвониться в четверг?"}).status_code == 201
    lst = client.get(f"{API}/candidate/invitations", headers=h).json()["items"]
    assert next(i for i in lst if i["id"] == inv_id)["unread_messages"] == 1
    thread = client.get(f"{API}/candidate/invitations/{inv_id}/messages", headers=h).json()
    assert thread["available"] and thread["items"][0]["text"].startswith("Удобно") and not thread["items"][0]["mine"]
    assert client.post(f"{API}/candidate/invitations/{inv_id}/messages", headers=h, json={"text": "Да, после 15:00"}).status_code == 201
    lst = client.get(f"{API}/candidate/invitations", headers=h).json()["items"]
    assert next(i for i in lst if i["id"] == inv_id)["unread_messages"] == 0
    emp = client.get(f"{API}/employer/invitations/{inv_id}/messages", headers=he).json()["items"]
    assert [m["from"] for m in emp] == ["employer", "candidate"] and emp[0]["read"]
    assert client.post(f"{API}/candidate/invitations/{inv_id}/messages", headers=h, json={"text": " "}).status_code in (400, 422)


def test_candidate_revokes_contacts(client):
    h, he, me, inv_id = _accepted_invitation(client, "revoke@test.ru")
    client.post(f"{API}/candidate/invitations/{inv_id}/accept", headers=h, json={})
    assert client.get(f"{API}/employer/invitations/{inv_id}", headers=he).json()["contacts"]["phone"] == "+79990002233"
    r = client.post(f"{API}/candidate/invitations/{inv_id}/contacts", headers=h, json={"revoked": True}).json()
    assert r["contacts_revoked_at"] and not r["contacts_open"]
    v = client.get(f"{API}/employer/invitations/{inv_id}", headers=he).json()
    assert "contacts" not in v and not v["contacts_open"]
    card = client.get(f"{API}/employer/candidates/{me['id']}", headers=he).json()
    assert not card["contacts_revealed"] and "contacts" not in card
    # переписка остаётся
    assert client.post(f"{API}/employer/invitations/{inv_id}/messages", headers=he, json={"text": "Поняли, пишем здесь"}).status_code == 201
    client.post(f"{API}/candidate/invitations/{inv_id}/contacts", headers=h, json={"revoked": False})
    assert client.get(f"{API}/employer/invitations/{inv_id}", headers=he).json()["contacts"]["phone"] == "+79990002233"


def test_minor_registration_requires_guardian_consent(client):
    base = {"email": "minor@test.ru", "password": "Secret123", "role": "candidate", "consent_pd": True, "consent_publication": True, "age_group": "minor"}
    assert client.post(f"{API}/auth/register", json=base).status_code == 422  # без согласия законного представителя нельзя
    assert client.post(f"{API}/auth/register", json={**base, "guardian_consent": True}).status_code == 201
    from tests.conftest import last_code
    tok = client.post(f"{API}/auth/verify-email", json={"email": "minor@test.ru", "code": last_code("minor@test.ru")}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    cons = client.get(f"{API}/candidate/consents", headers=h).json()
    assert cons["current"]["guardian_consent"] and "guardian_consent" not in cons["kinds"] and cons["age_group"] == "minor"
    _survey(client, h, "intern")
    me = client.get(f"{API}/candidate/me", headers=h).json()
    he = login(client, "employer@draft.demo")
    assert client.get(f"{API}/employer/candidates/{me['id']}", headers=he).json()["age_group"] == "minor"


def test_compare_candidates_explains_order(client):
    he = login(client, "employer@draft.demo")
    sl = client.get(f"{API}/employer/needs/1/shortlist", headers=he).json()["items"]
    ids = [sl[0]["id"], sl[5]["id"], sl[9]["id"]]
    r = client.get(f"{API}/employer/needs/1/compare", headers=he, params=[("ids", i) for i in ids]).json()
    scores = [x["match"]["score"] for x in r["items"]]
    assert scores == sorted(scores, reverse=True) and len(r["pairs"]) == 2
    p = r["pairs"][0]
    assert p["score_gap"] >= 0 and (p["a_better"] or p["b_modifiers"])  # разница объяснена компонентами или модификаторами
    assert all("contacts" not in x for x in r["items"] if not x["contacts_revealed"])
    assert client.get(f"{API}/employer/needs/1/compare", headers=he, params=[("ids", ids[0])]).status_code == 400


def test_candidate_insights_respect_anonymity(client):
    from app.services.insights import _company_median, _quartiles

    assert _quartiles([100000.0] * 4) is None  # меньше 5 значений — распределение скрыто
    assert _company_median([(1, 200000.0), (1, 210000.0), (2, 220000.0)]) is None  # меньше 3 компаний — вилка скрыта
    hc = login(client, "candidate@draft.demo")
    r = client.get(f"{API}/candidate/insights", headers=hc).json()
    assert r["available"] and r["now"]["market_median"] and r["steps"]
    q = r["now"]["expectations"]
    assert q is None or (q["n"] >= 5 and q["p25"] <= q["p50"] <= q["p75"] and q["p50"] % 1000 == 0)
    newbie = login(client, "newbie@draft.demo")
    assert client.get(f"{API}/candidate/insights", headers=newbie).json()["available"] is False


def test_candidate_contacts_encrypted_at_rest(client):
    from sqlalchemy import text

    from app.core.db import SessionLocal
    from app.models import CandidateProfile, User

    h = register_candidate(client, "crypto@test.ru")
    client.put(f"{API}/candidate/profile", headers=h, json={"full_name": "Шифр Тестов", "phone": "+79991112233", "telegram": "@cipher"})
    with SessionLocal() as db:
        uid = db.query(User).filter(User.email == "crypto@test.ru").one().id
        raw = db.execute(text("select full_name, phone, telegram from candidate_profiles where user_id = :u"), {"u": uid}).one()
        assert all(v.startswith("enc:v1:") and "7999" not in v for v in raw)  # в БД — только шифртекст
        c = db.get(CandidateProfile, uid)
        assert (c.full_name, c.phone, c.telegram) == ("Шифр Тестов", "+79991112233", "@cipher")
