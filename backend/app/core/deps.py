"""Зависимости FastAPI: текущий пользователь, проверка ролей (RBAC), ограничение частоты запросов."""
from __future__ import annotations

import time
from collections import defaultdict, deque

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.models import CandidateProfile, Company, User

bearer = HTTPBearer(auto_error=False, description="JWT access-токен (RS256), полученный через /api/v1/auth/login")


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not creds:
        raise AppError(401, "unauthorized", "Требуется авторизация")
    try:
        claims = decode_access_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise AppError(401, "token_expired", "Срок действия токена истёк")
    except jwt.PyJWTError:
        raise AppError(401, "invalid_token", "Недействительный токен")
    user = db.get(User, int(claims["sub"]))
    if not user or not user.is_active:
        raise AppError(401, "unauthorized", "Пользователь не найден или заблокирован")
    return user


def require_verified(user: User = Depends(get_current_user)) -> User:
    if not user.email_verified:
        raise AppError(403, "email_not_verified", "Подтвердите адрес электронной почты")
    return user


def require_role(*roles: str):
    def dep(user: User = Depends(require_verified)) -> User:
        if user.role not in roles:
            raise AppError(403, "forbidden", "Раздел недоступен для вашей роли")
        return user

    return dep


def current_candidate(user: User = Depends(require_role("candidate")), db: Session = Depends(get_db)) -> CandidateProfile:
    cand = db.get(CandidateProfile, user.id)
    if not cand:
        raise AppError(404, "not_found", "Профиль кандидата не найден")
    return cand


def current_company(user: User = Depends(require_role("employer")), db: Session = Depends(get_db)) -> Company:
    comp = db.get(Company, user.id)
    if not comp:
        raise AppError(404, "not_found", "Профиль компании не найден")
    return comp


class RateLimiter:
    """Простой in-memory лимитер (скользящее окно) для чувствительных эндпоинтов: вход, регистрация, повторная отправка кода."""

    def __init__(self, limit: int, window_s: int):
        self.limit, self.window = limit, window_s
        self.hits: dict[str, deque] = defaultdict(deque)

    def __call__(self, request: Request) -> None:
        key = f"{request.url.path}:{request.client.host if request.client else 'local'}"
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            raise AppError(429, "rate_limited", "Слишком много запросов, попробуйте позже")
        q.append(now)


auth_limiter = RateLimiter(limit=20, window_s=60)
