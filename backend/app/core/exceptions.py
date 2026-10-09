"""自定义异常与全局异常处理器

统一错误响应格式：
    {"code": str, "message": str, "detail": Optional[Any]}
"""
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    """应用层异常基类"""

    def __init__(self, code: str, message: str, status_code: int = 400, detail: Any = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


class NotFoundError(AppException):
    def __init__(self, message: str = "资源不存在", detail: Any = None):
        super().__init__("NOT_FOUND", message, 404, detail)


class AuthError(AppException):
    def __init__(self, message: str = "认证失败", detail: Any = None):
        super().__init__("AUTH_ERROR", message, 401, detail)


class PermissionError(AppException):
    def __init__(self, message: str = "无访问权限", detail: Any = None):
        super().__init__("PERMISSION_DENIED", message, 403, detail)


class ValidationError(AppException):
    def __init__(self, message: str = "参数校验失败", detail: Any = None):
        super().__init__("VALIDATION_ERROR", message, 422, detail)


def _error_body(code: str, message: str, detail: Optional[Any] = None) -> dict:
    body = {"code": code, "message": message}
    if detail is not None:
        body["detail"] = detail
    return body


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器"""

    @app.exception_handler(AppException)
    async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, exc.detail),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_error_body("INTERNAL_ERROR", "服务器内部错误", str(exc)),
        )
