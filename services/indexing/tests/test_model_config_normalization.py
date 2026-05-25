from __future__ import annotations

from indexing_service.config import normalize_chat_model, normalize_embedding_model


def test_normalize_chat_model_for_deepseek() -> None:
    assert normalize_chat_model("chat", base_url="https://api.deepseek.com") == "deepseek-chat"


def test_normalize_embedding_model_for_siliconflow() -> None:
    assert normalize_embedding_model("bge-m3", base_url="https://api.siliconflow.cn/v1") == "BAAI/bge-m3"
