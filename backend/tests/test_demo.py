"""Демо-стенд для жюри: общие демо-аккаунты защищены от необратимых действий, «чистые» аккаунты можно начать заново."""
from app.core.config import settings
from tests.conftest import login
from tests.test_api_flow import API, answer_all, register_candidate
from tests.test_grade_rules import _start, _survey


def test_shared_demo_account_cannot_be_deleted_or_unlinked(client):
    h = login(client, "candidate@draft.demo")
    me = client.get(f"{API}/candidate/me", headers=h).json()
    assert me["demo_shared"] and not me["demo_resettable"] and me["fsp"]["linked"]

    r = client.delete(f"{API}/candidate/account", headers=h)
    assert r.status_code == 403 and r.json()["error"]["code"] == "demo_account_protected"
    r = client.delete(f"{API}/candidate/fsp", headers=h)
    assert r.status_code == 403 and r.json()["error"]["code"] == "demo_account_protected"

    # аккаунт и достижения на месте, вход работает
    me = client.get(f"{API}/candidate/me", headers=login(client, "candidate@draft.demo")).json()
    assert me["fsp"]["linked"] and me["grade"]
    # начать заново можно только «чистым» аккаунтам
    assert client.post(f"{API}/candidate/demo/reset", headers=h).status_code == 403


def test_own_account_can_still_be_deleted(client):
    h = register_candidate(client, "delete-me@test.ru")
    assert client.get(f"{API}/candidate/me", headers=h).json()["demo_shared"] is False
    assert client.delete(f"{API}/candidate/account", headers=h).status_code == 204
    r = client.post(f"{API}/auth/login", json={"email": "delete-me@test.ru", "password": "Secret123"})
    assert r.status_code == 401


def test_expert_account_starts_over(client):
    h = login(client, "expert5@draft.demo")
    before = client.get(f"{API}/candidate/me", headers=h).json()
    assert before["demo_resettable"] and before["grade"] is None

    _survey(client, h, "middle")
    answer_all(client, h, _start(client, h, "middle"), correct=True)
    used = client.get(f"{API}/candidate/me", headers=h).json()
    assert used["grade"] and used["survey_completed_at"] and used["grade_locked_until"]

    r = client.post(f"{API}/candidate/demo/reset", headers=h)
    assert r.status_code == 200, r.text
    fresh = client.get(f"{API}/candidate/me", headers=h).json()  # тот же токен: пользователь не пересоздаётся
    assert fresh["code"] == before["code"]
    assert fresh["grade"] is None and fresh["survey_completed_at"] is None and fresh["grade_locked_until"] is None
    assert fresh["last_attempt_id"] is None and fresh["visible"]
    assert client.get(f"{API}/candidate/history", headers=h).json()["attempts"] == []
    consents = client.get(f"{API}/candidate/consents", headers=h).json()["current"]
    assert consents["pd_processing"] and consents["profile_publication"]

    # путь проходится заново: опрос и тест доступны сразу
    _survey(client, h, "junior")
    assert _start(client, h, "junior")


def test_demo_protections_off_outside_demo_mode(client, monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", False)
    h = login(client, "candidate@draft.demo")
    me = client.get(f"{API}/candidate/me", headers=h).json()
    assert not me["demo_shared"] and not me["demo_resettable"]
    assert client.post(f"{API}/candidate/demo/reset", headers=login(client, "expert4@draft.demo")).status_code == 403
