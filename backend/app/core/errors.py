"""Единый формат ошибок API: {"error": {"code", "message", "details"}}."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details: Any = None):
        self.status, self.code, self.message, self.details = status, code, message, details


def not_found(what: str = "Объект") -> AppError:
    return AppError(404, "not_found", f"{what} не найден")


def forbidden(msg: str = "Недостаточно прав") -> AppError:
    return AppError(403, "forbidden", msg)


def bad_request(code: str, msg: str, details: Any = None) -> AppError:
    return AppError(400, code, msg, details)


def conflict(code: str, msg: str, details: Any = None) -> AppError:
    return AppError(409, code, msg, details)


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


def err(status: int, description: str) -> dict:
    return {status: {"model": ErrorResponse, "description": description}}


COMMON_ERRORS = {**err(401, "Не аутентифицирован"), **err(403, "Недостаточно прав"), **err(422, "Ошибка валидации")}


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}})

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": "Проверьте корректность данных", "details": details}})

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = {401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed", 429: "rate_limited"}.get(exc.status_code, "http_error")
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": code, "message": str(exc.detail), "details": None}},
                            headers=getattr(exc, "headers", None))
