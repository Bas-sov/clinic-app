import logging
import re

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 400

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class BadRequestError(AppError):
    status_code = 400


class UnauthorizedError(AppError):
    status_code = 401


class ForbiddenError(AppError):
    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class TooManyRequestsError(AppError):
    status_code = 429


def _error_body(code: str, message: str, **extra: object) -> dict:
    return {"detail": {"code": code, "message": message, **extra}}


_CYRILLIC = re.compile(r"[а-яё]", re.IGNORECASE)


def _translate(error: dict) -> str:
    kind = error["type"]
    ctx = error.get("ctx") or {}
    match kind:
        case "missing":
            return "Обязательное поле"
        case "string_too_long":
            return f"Не длиннее {ctx['max_length']} символов"
        case "string_too_short":
            return "Поле не может быть пустым" if ctx.get("min_length") == 1 else f"Не короче {ctx['min_length']} символов"
        case "string_pattern_mismatch":
            return "Неверный формат"
        case "date_parsing" | "date_from_datetime_parsing" | "date_type":
            return "Неверный формат даты"
        case "time_parsing" | "time_type":
            return "Неверный формат времени"
        case "int_parsing" | "int_type" | "decimal_parsing" | "float_parsing":
            return "Должно быть числом"
        case "greater_than" | "greater_than_equal" | "less_than" | "less_than_equal":
            return "Значение вне допустимого диапазона"
        case "enum" | "literal_error":
            return "Недопустимое значение"
        case "value_error":
            # Свои валидаторы пишем по-русски — их текст отдаём как есть.
            text = str(ctx.get("error", ""))
            return text if _CYRILLIC.search(text) else "Неверное значение"
    return "Неверное значение"


def _field_name(loc: tuple) -> str:
    parts = loc[1:] if loc and loc[0] in ("body", "query", "path", "header") else loc
    return ".".join(str(p) for p in parts)


async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=_error_body(exc.code, exc.message))


async def _validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    fields = [{"field": _field_name(e["loc"]), "message": _translate(e)} for e in exc.errors()]
    return JSONResponse(
        status_code=422,
        content=_error_body("validation_error", "Проверьте введённые данные", fields=fields),
    )


_HTTP_MESSAGES = {
    404: ("not_found", "Ресурс не найден"),
    405: ("method_not_allowed", "Метод не поддерживается"),
}


async def _http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code, message = _HTTP_MESSAGES.get(exc.status_code, ("http_error", "Ошибка запроса"))
    return JSONResponse(status_code=exc.status_code, content=_error_body(code, message))


async def _unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Необработанная ошибка: %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=_error_body("internal_error", "Внутренняя ошибка сервера"),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(Exception, _unexpected_error_handler)
