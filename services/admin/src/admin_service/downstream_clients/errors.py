"""Downstream client error types."""

from dataclasses import dataclass


@dataclass
class DownstreamError(Exception):
    code: str
    message: str
    status_code: int = 500

    @classmethod
    def not_implemented(cls, message: str) -> "DownstreamError":
        return cls("DOWNSTREAM_NOT_IMPLEMENTED", message, 501)

    @classmethod
    def unavailable(cls, message: str) -> "DownstreamError":
        return cls("DOWNSTREAM_UNAVAILABLE", message, 503)

    @classmethod
    def conflict(cls, message: str) -> "DownstreamError":
        return cls("CONFLICT", message, 409)
