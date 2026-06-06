"""Unit tests for ekb_svc_utils.py."""

from __future__ import annotations

import pytest

from ekb_svc_utils import _convert_to_jdbc_url


class TestConvertToJdbcUrl:
    def test_strips_user_pass(self) -> None:
        url = "postgresql://rag_flow:infini_rag_flow@127.0.0.1:5432/rag_flow"
        assert _convert_to_jdbc_url(url) == "jdbc:postgresql://127.0.0.1:5432/rag_flow"

    def test_already_jdbc_unchanged(self) -> None:
        url = "jdbc:postgresql://host:5432/db"
        assert _convert_to_jdbc_url(url) == url

    def test_non_postgresql_unchanged(self) -> None:
        url = "sqlite:///tmp.db"
        assert _convert_to_jdbc_url(url) == url

    def test_no_auth_preserved(self) -> None:
        url = "postgresql://host:5432/db"
        assert _convert_to_jdbc_url(url) == "jdbc:postgresql://host:5432/db"

    def test_special_chars_in_password(self) -> None:
        """Passwords with URL-escaped chars should be stripped cleanly."""
        url = "postgresql://user:p%40ss@host:5432/db"
        assert _convert_to_jdbc_url(url) == "jdbc:postgresql://host:5432/db"

    def test_ipv6_host(self) -> None:
        """IPv6 addresses in brackets should be preserved."""
        url = "postgresql://user:pass@[::1]:5432/db"
        assert _convert_to_jdbc_url(url) == "jdbc:postgresql://[::1]:5432/db"
