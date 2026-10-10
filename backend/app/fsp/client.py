"""Интеграция с ФСП ID (OIDC, Keycloak) и реестром достижений ФСП.

Поток связывания профиля (Authorization Code + PKCE):
  1. /auth/fsp/authorize → платформа сохраняет state + code_verifier и возвращает URL авторизации ФСП ID;
  2. пользователь входит в ФСП ID и даёт согласие на scope fsp_achievements;
  3. /auth/fsp/callback → обмен code на токены (client_secret + PKCE), проверка подписи id_token по JWKS, nonce, aud, iss;
  4. по access_token запрашиваются результаты из реестра и сохраняются как верифицированные достижения.
Настоящий Keycloak подключается сменой FSP_OIDC_* переменных: используются стандартные discovery-эндпоинты.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import date, datetime, timezone
from functools import lru_cache
from urllib.parse import urlencode

import httpx
import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.fsp.scoring import fsp_score
from app.models import CandidateProfile, FspAchievement, OidcState

SCOPE = "openid profile email fsp_achievements"


def redirect_uri() -> str:
    return f"{settings.public_url}/auth/fsp/callback"


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def _internal(url: str) -> str:
    """Discovery отдаёт публичные адреса; backend внутри docker-сети обращается по внутреннему адресу."""
    return url.replace(settings.fsp_oidc_public_base, settings.fsp_oidc_internal_base)


@lru_cache(maxsize=1)
def discovery() -> dict:
    url = f"{settings.fsp_issuer_internal}/.well-known/openid-configuration"
    r = httpx.get(url, timeout=5)
    r.raise_for_status()
    return r.json()


def begin(db: Session, intent: str, user_id: int | None = None, role: str | None = None) -> str:
    try:
        conf = discovery()
    except httpx.HTTPError:
        discovery.cache_clear()
        raise AppError(503, "fsp_unavailable", "ФСП ID временно недоступен, попробуйте позже")
    state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(16)
    verifier, challenge = pkce_pair()
    db.add(OidcState(state=state, code_verifier=verifier, nonce=nonce, intent=intent, user_id=user_id, role=role))
    db.commit()
    params = {"client_id": settings.fsp_client_id, "redirect_uri": redirect_uri(), "response_type": "code", "scope": SCOPE,
              "state": state, "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256"}
    return f"{conf['authorization_endpoint']}?{urlencode(params)}"


def complete(db: Session, code: str, state: str) -> tuple[OidcState, dict, dict]:
    st = db.get(OidcState, state)
    if not st:
        raise AppError(400, "invalid_state", "Сессия авторизации ФСП ID устарела, повторите попытку")
    created = st.created_at if st.created_at.tzinfo else st.created_at.replace(tzinfo=timezone.utc)
    if (datetime.now(timezone.utc) - created).total_seconds() > 600:
        db.delete(st)
        db.commit()
        raise AppError(400, "invalid_state", "Сессия авторизации ФСП ID истекла")
    conf = discovery()
    try:
        r = httpx.post(_internal(conf["token_endpoint"]), timeout=8, data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri(), "client_id": settings.fsp_client_id,
            "client_secret": settings.fsp_client_secret, "code_verifier": st.code_verifier})
    except httpx.HTTPError:
        raise AppError(503, "fsp_unavailable", "ФСП ID недоступен")
    if r.status_code != 200:
        raise AppError(400, "fsp_token_error", "ФСП ID отклонил обмен кода", r.json() if r.headers.get("content-type", "").startswith("application/json") else None)
    tokens = r.json()
    claims = verify_id_token(tokens["id_token"], st.nonce)
    db.delete(st)
    db.commit()
    return st, tokens, claims


def verify_id_token(id_token: str, nonce: str) -> dict:
    conf = discovery()
    jwks = httpx.get(_internal(conf["jwks_uri"]), timeout=5).json()
    header = jwt.get_unverified_header(id_token)
    key = next((k for k in jwks["keys"] if k.get("kid") == header.get("kid")), None)
    if not key:
        raise AppError(400, "fsp_token_error", "Неизвестный ключ подписи ФСП ID")
    pub = jwt.algorithms.RSAAlgorithm.from_jwk(key)
    claims = jwt.decode(id_token, pub, algorithms=["RS256"], audience=settings.fsp_client_id, issuer=conf["issuer"])
    if claims.get("nonce") != nonce:
        raise AppError(400, "fsp_token_error", "Неверный nonce")
    return claims


def fetch_results(access_token: str, fsp_id: str) -> dict:
    r = httpx.get(f"{settings.fsp_registry_api}/athletes/{fsp_id}/results", headers={"Authorization": f"Bearer {access_token}"}, timeout=8)
    if r.status_code == 404:
        return {"athlete": None, "results": []}
    r.raise_for_status()
    return r.json()


def service_token() -> str:
    conf = discovery()
    r = httpx.post(_internal(conf["token_endpoint"]), timeout=8, data={"grant_type": "client_credentials", "client_id": settings.fsp_client_id,
                                                                      "client_secret": settings.fsp_client_secret})
    r.raise_for_status()
    return r.json()["access_token"]


def apply_results(db: Session, cand: CandidateProfile, payload: dict, now: datetime | None = None) -> int:
    """Заменяет достижения кандидата данными реестра. Пустая история — корректный и ожидаемый случай."""
    from app.fsp.scoring import result_title

    now = now or datetime.now(timezone.utc)
    for a in list(cand.achievements):
        cand.achievements.remove(a)
    athlete = payload.get("athlete") or {}
    cand.fsp_profile = {k: athlete.get(k) for k in ("full_name", "region", "sport_rank", "rating", "club") if athlete}
    for r in payload.get("results", []):
        ev = r["event"]
        cand.achievements.append(FspAchievement(
            result_id=r["result_id"], event_id=ev["event_id"], event_name=ev["name"], discipline=ev["discipline"], level=ev["level"],
            event_date=date.fromisoformat(ev["start_date"]), place=r.get("place"), participants=r.get("units_total"),
            result_title=result_title(r.get("place"), r.get("percentile")), team_name=r.get("team_name"), team_role=r.get("team_role"),
            stack=r.get("stack") or [], percentile=r.get("percentile"), diploma_url=r.get("diploma_url"), signature=r.get("signature"),
            verified=True,
        ))
    db.flush()
    cand.fsp_score = fsp_score(cand.achievements, spec=cand.specialization)  # с учётом актуальности дисциплин
    cand.fsp_synced_at = now
    from app.matching.strength import refresh_strength

    refresh_strength(cand, now)
    return len(cand.achievements)
