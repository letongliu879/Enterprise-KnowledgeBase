from __future__ import annotations

from dataclasses import dataclass

from indexing_service.parse_detection import ParseHintDetector, ParseHints
from indexing_service.ragflow_strategy import get_ragflow_parser


class DocumentFamily:
    LAYOUT_DOCUMENT = "layout_document"
    TABLE_DOCUMENT = "table_document"
    PRESENTATION_DOCUMENT = "presentation_document"
    IMAGE_DOCUMENT = "image_document"
    TEXT_DOCUMENT = "text_document"
    SPECIALIZED_DOCUMENT = "specialized_document"


@dataclass(frozen=True)
class ParsePolicy:
    document_family: str
    parser_id: str
    parser_backend: str
    parser_config: dict[str, object]
    effective_profile_id: str
    chunk_profile_id: str
    decision_reason: str
    warnings: list[str]


class ParsePolicyResolver:
    def __init__(self, detector: ParseHintDetector | None = None) -> None:
        self._detector = detector or ParseHintDetector()

    def resolve(
        self,
        *,
        filename: str,
        mime_type: str,
        binary: bytes,
        collection_default_parser_id: str | None,
        collection_parser_config: dict[str, object],
        requested_parser_id: str | None,
        requested_parser_config: dict[str, object] | None,
    ) -> ParsePolicy:
        hints = self._detector.detect(
            filename=filename,
            mime_type=mime_type,
            binary=binary,
        )
        upstream_parser_id = get_ragflow_parser(
            filename=filename,
            collection_default_parser_id=collection_default_parser_id or "naive",
        )

        warnings: list[str] = []
        if hints.reason:
            warnings.append(hints.reason)

        # Manual override takes precedence over upstream default
        if requested_parser_id:
            parser_id = requested_parser_id
            warnings.append(f"manual_parser_override_accepted:{requested_parser_id}")
            decision_reason = f"manual_override:{requested_parser_id};upstream_fallback:{upstream_parser_id}"
        else:
            parser_id = upstream_parser_id
            decision_reason = f"upstream:file_service.get_parser:{parser_id}"

        if requested_parser_config:
            warnings.append("manual_parser_config_override_ignored")

        parser_config = dict(collection_parser_config)
        document_family = self._document_family_from_parser(parser_id, hints)
        effective_profile_id = self._effective_profile_id(parser_id, document_family)
        chunk_profile_id = self._chunk_profile_id(parser_id, document_family)

        return ParsePolicy(
            document_family=document_family,
            parser_id=parser_id,
            parser_backend="ragflow_app",
            parser_config=parser_config,
            effective_profile_id=effective_profile_id,
            chunk_profile_id=chunk_profile_id,
            decision_reason=decision_reason,
            warnings=warnings,
        )

    @staticmethod
    def _document_family_from_parser(parser_id: str, hints: ParseHints) -> str:
        pid = parser_id.lower()
        if pid in {"presentation"}:
            return DocumentFamily.PRESENTATION_DOCUMENT
        if pid in {"table"}:
            return DocumentFamily.TABLE_DOCUMENT
        if pid in {"picture", "image"}:
            return DocumentFamily.IMAGE_DOCUMENT
        if pid in {"qa", "resume", "email", "paper", "laws", "book", "manual"}:
            return DocumentFamily.SPECIALIZED_DOCUMENT
        if hints.scanned_pdf or pid in {"ocr", "layout"}:
            return DocumentFamily.LAYOUT_DOCUMENT
        return DocumentFamily.TEXT_DOCUMENT

    @staticmethod
    def _effective_profile_id(parser_id: str, document_family: str) -> str:
        return f"{document_family}:{parser_id}"

    @staticmethod
    def _chunk_profile_id(parser_id: str, document_family: str) -> str:
        # Thin mapping: parser_id directly drives chunk semantics in first version.
        # Future: chunk profiles may diverge from parser_id (e.g., same parser, different chunk size).
        return parser_id
