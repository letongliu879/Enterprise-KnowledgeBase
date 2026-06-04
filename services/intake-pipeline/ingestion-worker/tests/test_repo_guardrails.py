"""Repository-level guardrails for intake-pipeline test harnesses."""

from __future__ import annotations

from inspect import signature
from pathlib import Path


_SERVICE_ROOT = Path(__file__).resolve().parents[2]


def test_no_bare_testclient_return_or_lifespan_monkeypatch_in_tests():
    violations: list[str] = []
    for path in _SERVICE_ROOT.rglob("tests/test_*.py"):
        if path.name == "test_repo_guardrails.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "return TestClient(" in text:
            violations.append(f"{path}: bare return TestClient(")
        if "app.router.lifespan_context =" in text:
            violations.append(f"{path}: lifespan monkeypatch in test")

    assert not violations, "Phase S guardrail violations:\n" + "\n".join(violations)


def test_background_worker_app_factories_support_disabling_pollers():
    from agent_review_worker.main import create_app as create_review_app
    from conversion_worker.main import create_app as create_conversion_app
    from publishing_worker.main import create_app as create_publishing_app

    factories = {
        "agent_review_worker": create_review_app,
        "conversion_worker": create_conversion_app,
        "publishing_worker": create_publishing_app,
    }

    for name, factory in factories.items():
        params = signature(factory).parameters
        assert "start_background_poller" in params, f"{name} must expose start_background_poller"
        assert params["start_background_poller"].default is True, (
            f"{name} start_background_poller should default to True"
        )
        app = factory(start_background_poller=False)
        assert app.title, f"{name} create_app() should return a configured FastAPI app"
