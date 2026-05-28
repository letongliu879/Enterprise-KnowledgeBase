"""Unified error codes for workbench service."""

from fastapi import HTTPException


class WorkbenchErrorCode:
    DOWNSTREAM_NOT_IMPLEMENTED = "DOWNSTREAM_NOT_IMPLEMENTED"
    DOWNSTREAM_UNAVAILABLE = "DOWNSTREAM_UNAVAILABLE"
    CONFLICT = "CONFLICT"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    BAD_REQUEST = "BAD_REQUEST"


def downstream_not_implemented(detail: str) -> HTTPException:
    return HTTPException(status_code=501, detail={
        "error_code": WorkbenchErrorCode.DOWNSTREAM_NOT_IMPLEMENTED,
        "message": detail,
    })


def downstream_unavailable(detail: str) -> HTTPException:
    return HTTPException(status_code=503, detail={
        "error_code": WorkbenchErrorCode.DOWNSTREAM_UNAVAILABLE,
        "message": detail,
    })


def conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=409, detail={
        "error_code": WorkbenchErrorCode.CONFLICT,
        "message": detail,
    })


def unauthorized(detail: str = "Authentication required") -> HTTPException:
    return HTTPException(status_code=401, detail={
        "error_code": WorkbenchErrorCode.UNAUTHORIZED,
        "message": detail,
    })


def forbidden(detail: str = "Permission denied") -> HTTPException:
    return HTTPException(status_code=403, detail={
        "error_code": WorkbenchErrorCode.FORBIDDEN,
        "message": detail,
    })


def not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=404, detail={
        "error_code": WorkbenchErrorCode.NOT_FOUND,
        "message": detail,
    })


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail={
        "error_code": WorkbenchErrorCode.BAD_REQUEST,
        "message": detail,
    })
