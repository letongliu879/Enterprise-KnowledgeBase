from __future__ import annotations

from pydantic import BaseModel


class ParseHints(BaseModel):
    content_class_hint: str | None = None
    scanned_pdf: bool = False
    table_heavy: bool = False
    presentation_like: bool = False
    reason: str = ""


class ParseHintDetector:
    def detect(self, *, filename: str, mime_type: str, binary: bytes) -> ParseHints:
        suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        sample = binary[:32768]
        text_sample = sample.decode("utf-8", errors="ignore")

        if suffix == "pdf":
            if self._looks_scanned_pdf(sample):
                return ParseHints(content_class_hint="scanned_pdf", scanned_pdf=True, reason="pdf:image_only_or_low_text")
            if self._looks_table_heavy(text_sample):
                return ParseHints(content_class_hint="table", table_heavy=True, reason="pdf:table_markers")

        if suffix in {"ppt", "pptx"}:
            return ParseHints(content_class_hint="presentation", presentation_like=True, reason="suffix:presentation")

        if suffix in {"xlsx", "xls", "csv"}:
            return ParseHints(content_class_hint="table", table_heavy=True, reason="suffix:table")

        if "resume" in filename.lower():
            return ParseHints(content_class_hint="resume", reason="filename:resume")

        if self._looks_qa_text(text_sample):
            return ParseHints(content_class_hint="qa", reason="text:qa_pattern")

        return ParseHints()

    @staticmethod
    def _looks_scanned_pdf(sample: bytes) -> bool:
        if b"/Font" in sample or b"/Text" in sample:
            return False
        image_markers = sample.count(b"/Image")
        return image_markers >= 1

    @staticmethod
    def _looks_table_heavy(text_sample: str) -> bool:
        comma_lines = sum(1 for line in text_sample.splitlines() if line.count(",") >= 3)
        pipe_lines = sum(1 for line in text_sample.splitlines() if line.count("|") >= 3)
        tab_lines = sum(1 for line in text_sample.splitlines() if line.count("\t") >= 3)
        return (comma_lines + pipe_lines + tab_lines) >= 2

    @staticmethod
    def _looks_qa_text(text_sample: str) -> bool:
        lowered = text_sample.lower()
        markers = ["q:", "a:", "question:", "answer:", "faq"]
        return sum(marker in lowered for marker in markers) >= 2
