"""Custom exceptions + global handler (Architecture §2.9, Refactore task 2.4).

Rule: NEVER leak a raw stack trace to the frontend. Every unhandled error
becomes a stable JSON envelope; the technical detail goes to the log with
the request id.
"""
from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AppException(Exception):
    """Base for all business exceptions — carries an HTTP status + message."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    message: str = "Yêu cầu không hợp lệ."

    def __init__(self, message: str | None = None):
        if message:
            self.message = message
        super().__init__(self.message)


class UnauthorizedException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    message = "Phiên đăng nhập không hợp lệ hoặc đã hết hạn."


class ForbiddenException(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    message = "Bạn không có quyền thực hiện thao tác này."


class NotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    message = "Không tìm thấy tài nguyên yêu cầu."


class ConflictException(AppException):
    status_code = status.HTTP_409_CONFLICT
    message = "Dữ liệu bị trùng lặp hoặc xung đột."


class QuotaExceededException(AppException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    message = "Đã vượt hạn mức tài nguyên của Workspace."


class FrozenResourceException(AppException):
    """Mutation attempted on an immutable snapshot (DATASET_VERSIONS frozen)."""

    status_code = status.HTTP_409_CONFLICT
    message = "Phiên bản đã đóng băng (frozen) — không thể chỉnh sửa."


def _error_body(message: str) -> dict:
    return {"error": True, "message": message}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the global exception handlers to a FastAPI app (v2 stack)."""

    @app.exception_handler(AppException)
    async def _app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code, content=_error_body(exc.message)
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception):
        # Details go to the log (with request id) — never to the client.
        from app.core.logging import get_logger

        get_logger("core.exceptions").exception(
            "unhandled error on {} {}", request.method, request.url.path
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                "Hệ thống đang gián đoạn, vui lòng thử lại sau ít phút."
            ),
        )
