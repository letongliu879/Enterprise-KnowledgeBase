from __future__ import annotations

from pathlib import Path

from ragflow_runtime.deepdoc.parser import HtmlParser, JsonParser, TxtParser


class AssetReader:
    def __init__(self) -> None:
        self._html_parser = HtmlParser()
        self._txt_parser = TxtParser()
        self._json_parser = JsonParser()

    def read(self, asset_ref: str) -> str:
        path = self._resolve_path(asset_ref)
        if path is None or not path.exists():
            return ""

        suffix = path.suffix.lower()
        if suffix in {".html", ".htm"}:
            return self._join_sections(self._html_parser(str(path), binary=path.read_bytes()))
        if suffix in {".txt", ".text", ".log"}:
            sections = self._txt_parser(str(path), binary=path.read_bytes())
            return self._join_sections(section[0] for section in sections if section and section[0].strip())
        if suffix in {".json", ".jsonl"}:
            return self._join_sections(self._json_parser(path.read_bytes()))

        # Keep markdown on the raw path for now so downstream chunkers preserve
        # original source lines until the full DeepDoc markdown path is wired
        # into the current ChunkRecord pipeline.
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _resolve_path(asset_ref: str) -> Path | None:
        if asset_ref.startswith("file://"):
            return Path(asset_ref.removeprefix("file://"))
        return Path(asset_ref)

    @staticmethod
    def _join_sections(sections) -> str:
        normalized = [str(section).strip() for section in sections if str(section).strip()]
        return "\n\n".join(normalized)
