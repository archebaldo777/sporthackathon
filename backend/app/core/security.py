"""Безопасность: хеширование паролей (Argon2id), JWT RS256 с Keycloak-совместимыми claims, refresh-токены.

Структура access-токена повторяет Keycloak (iss, sub, aud, azp, realm_access.roles, email_verified,
preferred_username), а публичный ключ публикуется в формате JWKS. Поэтому переход на ФСП ID (Keycloak)
сводится к смене issuer/JWKS URL — бизнес-код читает те же claims.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import settings

_ph = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)  # параметры по рекомендации OWASP


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return _ph.verify(hashed, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def random_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def random_code(digits: int = 6) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(digits))


def sign(value: str) -> str:
    """HMAC-подпись (PDF-профили, webhooks)."""
    return hmac.new(settings.secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()


# ---------------------------------------------------------------- ключи RS256
@lru_cache
def _private_key():
    path = Path(settings.jwt_private_key_path)
    if path.exists():
        return serialization.load_pem_private_key(path.read_bytes(), password=None)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return key


def _b64u(n: int) -> str:
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


@lru_cache
def key_id() -> str:
    pub = _private_key().public_key().public_numbers()
    return sha256(f"{pub.n}:{pub.e}")[:16]


def jwks() -> dict:
    pub = _private_key().public_key().public_numbers()
    return {"keys": [{"kty": "RSA", "use": "sig", "alg": "RS256", "kid": key_id(), "n": _b64u(pub.n), "e": _b64u(pub.e)}]}


def create_access_token(user_id: int, email: str, role: str, email_verified: bool, fsp_linked: bool = False) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    ttl = settings.access_token_ttl_min * 60
    payload = {
        "iss": settings.jwt_issuer,
        "sub": str(user_id),
        "aud": settings.jwt_audience,
        "azp": settings.jwt_audience,
        "typ": "Bearer",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
        "jti": str(uuid.uuid4()),
        "email": email,
        "email_verified": email_verified,
        "preferred_username": email,
        "realm_access": {"roles": [role]},
        "fsp_linked": fsp_linked,
    }
    token = jwt.encode(payload, _private_key(), algorithm="RS256", headers={"kid": key_id()})
    return token, ttl


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, _private_key().public_key(), algorithms=["RS256"], audience=settings.jwt_audience, issuer=settings.jwt_issuer)
