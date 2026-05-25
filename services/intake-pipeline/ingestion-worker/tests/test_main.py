from fastapi.testclient import TestClient

from ingestion_worker.agent_reviewer import AgentReviewUnavailableError
from ingestion_worker import main


client = TestClient(main.app)


def test_convert_returns_503_when_reviewer_is_unavailable(monkeypatch):
    class _FailingPipeline:
        def run(self, *, collection_id, source_files):
            raise AgentReviewUnavailableError(
                "LLM connection failed: unable to connect to the DeepSeek endpoint at https://api.deepseek.com/chat/completions."
            )

    monkeypatch.setattr(main, "_pipeline", None)
    monkeypatch.setattr(main, "get_pipeline", lambda: _FailingPipeline())

    response = client.post(
        "/internal/ingestion/convert",
        json={
            "collection_id": "col-1",
            "source_file_path": "E:/tmp/example.md",
        },
    )

    assert response.status_code == 503
    detail = response.json()["detail"].lower()
    assert "llm connection failed" in detail
    assert "unable to connect" in detail
