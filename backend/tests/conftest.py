"""Тестовое окружение: отдельная БД draft_test, небольшой синтетический набор, перехват писем."""
import os
import re

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://localhost/draft_test")
os.environ["SEED_CANDIDATES"] = "160"
os.environ["SMTP_PORT"] = "1"  # письма не отправляются, а перехватываются фикстурой
os.environ["JWT_PRIVATE_KEY_PATH"] = os.path.join(os.path.dirname(__file__), ".jwt_test.pem")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, engine  # noqa: E402
import app.models  # noqa: E402,F401

MAILBOX: list[dict] = []


@pytest.fixture(scope="session")
def client():
    Base.metadata.drop_all(engine)
    from app.api.v1 import auth as auth_api

    def fake_send(to, subject, text, html=None):
        MAILBOX.append({"to": to, "subject": subject, "text": text})
        return True

    auth_api.send_email = fake_send
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    """Лимит входа (20 в минуту с адреса) — защита стенда; тесты изолируем, чтобы порядок их запуска не влиял на результат."""
    from app.core.deps import auth_limiter

    auth_limiter.hits.clear()
    yield


def last_code(email: str) -> str:
    msg = next(m for m in reversed(MAILBOX) if m["to"] == email)
    return re.search(r"(\d{6})", msg["text"]).group(1)


def login(client, email, password="Demo2026!") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
