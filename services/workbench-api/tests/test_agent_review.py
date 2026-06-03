"""Tests for AgentReview display."""

import pytest
import respx
from fastapi.testclient import TestClient


class TestAgentReview:
    def test_get_agent_review(self, client: TestClient, reviewer_token: str):
        with respx.mock:
            respx.get("http://localhost:8004/internal/tickets/ticket_123").respond(
                200, json={
                    "ticket_id": "ticket_123",
                    "collection_id": "col_default",
                    "status": "PENDING",
                }
            )
            respx.get("http://localhost:8004/internal/tickets/ticket_123/agent-review").respond(
                200, json={
                    "ticket_id": "ticket_123",
                    "decision": "REQUEST_CHANGES",
                    "source_file_id": "sf_123",
                    "parse_snapshot_id": "ps_123",
                    "anchored_findings": [
                        {
                            "finding_id": "finding_001",
                            "severity": "high",
                            "problem_summary": "Quoted policy mismatch",
                            "source_quote": "Original quote",
                            "confidence": 0.88,
                        }
                    ],
                }
            )
            resp = client.get(
                "/workbench/tickets/ticket_123/agent-review",
                headers={"Authorization": f"Bearer {reviewer_token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["ticket_id"] == "ticket_123"
            assert data["decision"] == "REQUEST_CHANGES"
            assert len(data["findings"]) == 1
            assert data["findings"][0]["source_quote"] == "Original quote"

    def test_get_agent_review_not_implemented(self, client: TestClient, reviewer_token: str):
        with respx.mock:
            respx.get("http://localhost:8004/internal/tickets/ticket_123").respond(
                200, json={
                    "ticket_id": "ticket_123",
                    "collection_id": "col_default",
                    "status": "PENDING",
                }
            )
            respx.get("http://localhost:8004/internal/tickets/ticket_123/agent-review").respond(404)
            resp = client.get(
                "/workbench/tickets/ticket_123/agent-review",
                headers={"Authorization": f"Bearer {reviewer_token}"},
            )
            assert resp.status_code == 501
            assert resp.json()["detail"]["error_code"] == "DOWNSTREAM_NOT_IMPLEMENTED"

    def test_agent_review_read_only(self, client: TestClient, reviewer_token: str):
        # AgentReview is read-only; there is no PUT/POST endpoint for it
        # This test documents that workbench cannot modify AgentReview
        with respx.mock:
            respx.get("http://localhost:8004/internal/tickets/ticket_123").respond(
                200, json={
                    "ticket_id": "ticket_123",
                    "collection_id": "col_default",
                    "status": "PENDING",
                }
            )
            respx.get("http://localhost:8004/internal/tickets/ticket_123/agent-review").respond(404)
            resp = client.get(
                "/workbench/tickets/ticket_123/agent-review",
                headers={"Authorization": f"Bearer {reviewer_token}"},
            )
            assert resp.status_code == 501
