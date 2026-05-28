"""Unified error codes for admin service."""

from fastapi import HTTPException


class AdminErrorCode:
    DOWNSTREAM_NOT_IMPLEMENTED = "DOWNSTREAM_NOT_IMPLEMENTED"
    DOWNSTREAM_UNAVAILABLE = "DOWNSTREAM_UNAVAILABLE"
    CONFLICT = "CONFLICT"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"


def downstream_not_implemented(detail: str) -> HTTPException:
    return HTTPException(status_code=501, detail={
        "error_code": AdminErrorCode.DOWNSTREAM_NOT_IMPLEMENTED,
        "message": detail,
    })


def downstream_unavailable(detail: str) -> HTTPException:
    return HTTPException(status_code=503, detail={
        "error_code": AdminErrorCode.DOWNSTREAM_UNAVAILABLE,
        "message": detail,
    })


def conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=409, detail={
        "error_code": AdminErrorCode.CONFLICT,
        "message": detail,
    })


def unauthorized(detail: str = "Authentication required") -> HTTPException:
    return HTTPException(status_code=401, detail={
        "error_code": AdminErrorCode.UNAUTHORIZED,
        "message": detail,
    })


def forbidden(detail: str = "Permission denied") -> HTTPException:
    return HTTPException(status_code=403, detail={
        "error_code": AdminErrorCode.FORBIDDEN,
        "message": detail,
    })


def not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=404, detail={
        "error_code": AdminErrorCode.NOT_FOUND,
        "message": detail,
    })
