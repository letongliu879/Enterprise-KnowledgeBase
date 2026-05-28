from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParserProfile:
    profile_id: str
    parser_id: str
    parser_backend: str
    default_parser_config: dict[str, object] = field(default_factory=dict)
    embedding_text_policy: str = "display_text"
    chunk_profile_id: str = ""
    description: str = ""


# Static registry of first-class parser profiles.
# In future versions these may be loaded from database or admin-managed templates.
_PARSER_PROFILES: dict[str, ParserProfile] = {
    "naive": ParserProfile(
        profile_id="naive",
        parser_id="naive",
        parser_backend="ragflow_app",
        embedding_text_policy="display_text",
        chunk_profile_id="naive",
        description="General text parser with token chunking",
    ),
    "presentation": ParserProfile(
        profile_id="presentation",
        parser_id="presentation",
        parser_backend="ragflow_app",
        embedding_text_policy="display_text",
        chunk_profile_id="presentation",
        description="Slide-level semantic chunking for presentations",
    ),
    "table": ParserProfile(
        profile_id="table",
        parser_id="table",
        parser_backend="ragflow_app",
        embedding_text_policy="display_text",
        chunk_profile_id="table",
        description="Table-aware parser with metadata aggregation",
    ),
    "paper": ParserProfile(
        profile_id="paper",
        parser_id="paper",
        parser_backend="ragflow_app",
        embedding_text_policy="display_text_with_authors",
        chunk_profile_id="paper",
        description="Academic paper parser with author/keyword semantics",
    ),
    "qa": ParserProfile(
        profile_id="qa",
        parser_id="qa",
        parser_backend="ragflow_app",
        embedding_text_policy="question_kwd",
        chunk_profile_id="qa",
        description="Q&A structured parser with question embedding",
    ),
    "picture": ParserProfile(
        profile_id="picture",
        parser_id="picture",
        parser_backend="ragflow_app",
        embedding_text_policy="display_text",
        chunk_profile_id="picture",
        description="Image parser with OCR and caption extraction",
    ),
    "audio": ParserProfile(
        profile_id="audio",
        parser_id="audio",
        parser_backend="ragflow_app",
        embedding_text_policy="display_text",
        chunk_profile_id="audio",
        description="Audio parser with transcription chunking",
    ),
    "email": ParserProfile(
        profile_id="email",
        parser_id="email",
        parser_backend="ragflow_app",
        embedding_text_policy="display_text",
        chunk_profile_id="email",
        description="Email parser with header and body separation",
    ),
    "manual": ParserProfile(
        profile_id="manual",
        parser_id="manual",
        parser_backend="ragflow_app",
        embedding_text_policy="display_text_with_section_path",
        chunk_profile_id="manual",
        description="Manual/book parser with hierarchical section paths",
    ),
    "resume": ParserProfile(
        profile_id="resume",
        parser_id="resume",
        parser_backend="ragflow_app",
        embedding_text_policy="display_text",
        chunk_profile_id="resume",
        description="Resume parser with structured field extraction",
    ),
}


def get_parser_profile(profile_id: str) -> ParserProfile | None:
    return _PARSER_PROFILES.get(profile_id)


def list_parser_profile_ids() -> list[str]:
    return list(_PARSER_PROFILES.keys())
