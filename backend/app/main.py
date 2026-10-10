"""Точка входа FastAPI-приложения «Драфт».

Слои: api (HTTP, схемы, RBAC) → services/testing/matching/nlp/fsp (бизнес-логика) → models (хранилище, PostgreSQL).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import assessment, auth, candidate, employer, public
from app.core.config import settings
from app.core.errors import install_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("draft")

TAGS = [
    {"name": "Аутентификация", "description": "Регистрация по e-mail с подтверждением, JWT (RS256, Keycloak-совместимые claims), вход через ФСП ID (OIDC)."},
    {"name": "Кандидат", "description": "Профиль и резюме, опрос, категория, приглашения, отклики, регулярные задачи, приватность и согласия (152-ФЗ)."},
    {"name": "Тестирование", "description": "Адаптивное тестирование на грейд: параметрические задания, IRT, ограничения по частоте смены грейда."},
    {"name": "Работодатель", "description": "Потребности и подборки с объяснимостью, банк кандидатов, приглашения, вакансии, задачи, интеграции."},
    {"name": "Вакансии", "description": "Классический сценарий: опубликованные вакансии и самостоятельный отклик кандидата."},
    {"name": "Механика тестирования", "description": "Прозрачность механики: обзор банка, генерация вариантов, симуляция CAT."},
    {"name": "Валидация", "description": "Результаты собственной процедуры валидации тестирования и подбора."},
    {"name": "ATS-интеграция", "description": "API для ATS работодателя по ключу X-API-Key."},
]


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return resp


@asynccontextmanager
async def lifespan(_: FastAPI):
    from app.seed.bootstrap import bootstrap

    bootstrap()
    yield


app = FastAPI(
    title="Драфт — API платформы ИТ-найма с верифицированным профилем участника ФСП",
    version="1.0.0",
    description=(
        "Обратная механика подбора: кандидаты распределяются по категориям (специализация × грейд) по результатам опроса "
        "и адаптивного тестирования, работодатель находит категорию и сам приглашает конкретного кандидата с вилкой зарплаты.\n\n"
        "Все ошибки возвращаются в формате `{\"error\": {\"code\", \"message\", \"details\"}}`."
    ),
    openapi_tags=TAGS,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
app.add_middleware(SecurityHeaders)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
install_handlers(app)

for r in (auth.router, candidate.router, assessment.router, employer.router, public.router, public.ats, public.admin):
    app.include_router(r, prefix="/api/v1")


@app.get("/api/health", tags=["Справочники и публичные данные"], summary="Проверка работоспособности")
def health():
    return {"status": "ok", "version": app.version}
