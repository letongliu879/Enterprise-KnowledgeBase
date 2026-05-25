"""Tests for MarkItDown converter.

Tests use mock MarkItDown since the real package may have extra dependencies
(libreoffice, etc.) that aren't available in every environment.
"""

from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile

from reality_rag_contracts import (
    ConversionRequest,
    ConversionResult,
    ConversionStatus,
)


def make_request(path: str, collection_id: str = "col-1") -> ConversionRequest:
    return ConversionRequest(source_file_path=path, collection_id=collection_id)


class TestSupportedExtensions:
    def test_returns_non_empty_list(self):
        from ingestion_worker.converters.markitdown_converter import MarkItDownConverter
        converter = MarkItDownConverter()
        exts = converter.supported_extensions()
        assert len(exts) > 0
        assert ".txt" in exts
        assert ".md" in exts
        assert ".pdf" in exts
        assert ".docx" in exts

    def test_all_extensions_lowercase(self):
        from ingestion_worker.converters.markitdown_converter import MarkItDownConverter
        converter = MarkItDownConverter()
        for ext in converter.supported_extensions():
            assert ext == ext.lower()


class TestUnsupportedExtension:
    def test_returns_unsupported_for_unknown_extension(self):
        from ingestion_worker.converters.markitdown_converter import MarkItDownConverter
        converter = MarkItDownConverter()
        result = converter.convert(make_request("/fake/file.xyz"))
        assert result.conversion_status == ConversionStatus.UNSUPPORTED
        assert "xyz" in result.error_message
        assert result.canonical_md == ""

    def test_returns_unsupported_for_no_extension(self):
        from ingestion_worker.converters.markitdown_converter import MarkItDownConverter
        converter = MarkItDownConverter()
        result = converter.convert(make_request("/fake/nofile"))
        assert result.conversion_status == ConversionStatus.UNSUPPORTED


class TestMarkItDownSuccess:
    def test_converts_txt_file_successfully(self):
        from ingestion_worker.converters.markitdown_converter import MarkItDownConverter

        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("Hello world")
            tmp_path = f.name

        try:
            converter = MarkItDownConverter()
            with patch.object(converter._markitdown, "convert") as mock_convert:
                mock_result = MagicMock()
                mock_result.text_content = "# Hello world\n\nConverted content."
                mock_convert.return_value = mock_result

                result = converter.convert(make_request(tmp_path))
                assert result.conversion_status == ConversionStatus.SUCCESS
                assert "Hello world" in result.canonical_md
                assert result.error_message == ""
                assert result.metadata["converter"] == "markitdown"
                assert result.metadata["extension"] == ".txt"
        finally:
            Path(tmp_path).unlink()

    def test_converts_md_file_successfully(self):
        from ingestion_worker.converters.markitdown_converter import MarkItDownConverter

        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("# Already markdown")
            tmp_path = f.name

        try:
            converter = MarkItDownConverter()
            with patch.object(converter._markitdown, "convert") as mock_convert:
                mock_result = MagicMock()
                mock_result.text_content = "# Already markdown"
                mock_convert.return_value = mock_result

                result = converter.convert(make_request(tmp_path))
                assert result.conversion_status == ConversionStatus.SUCCESS
        finally:
            Path(tmp_path).unlink()


class TestMarkItDownFailure:
    def test_returns_failed_on_exception(self):
        from ingestion_worker.converters.markitdown_converter import MarkItDownConverter

        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("test")
            tmp_path = f.name

        try:
            converter = MarkItDownConverter()
            with patch.object(converter._markitdown, "convert") as mock_convert:
                mock_convert.side_effect = RuntimeError("Conversion exploded")

                result = converter.convert(make_request(tmp_path))
                assert result.conversion_status == ConversionStatus.FAILED
                assert "Conversion exploded" in result.error_message
        finally:
            Path(tmp_path).unlink()

    def test_returns_failed_for_missing_file(self):
        from ingestion_worker.converters.markitdown_converter import MarkItDownConverter
        converter = MarkItDownConverter()
        result = converter.convert(make_request("/nonexistent/file.txt"))
        assert result.conversion_status == ConversionStatus.FAILED
        assert "File not found" in result.error_message


class TestJSONSerialization:
    def test_result_is_json_serializable(self):
        from ingestion_worker.converters.markitdown_converter import MarkItDownConverter

        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("test")
            tmp_path = f.name

        try:
            converter = MarkItDownConverter()
            with patch.object(converter._markitdown, "convert") as mock_convert:
                mock_result = MagicMock()
                mock_result.text_content = "converted"
                mock_convert.return_value = mock_result

                result = converter.convert(make_request(tmp_path))
                json_str = result.model_dump_json()
                assert "converted" in json_str
                assert "success" in json_str
        finally:
            Path(tmp_path).unlink()

    def test_failed_result_is_json_serializable(self):
        from ingestion_worker.converters.markitdown_converter import MarkItDownConverter
        converter = MarkItDownConverter()
        result = converter.convert(make_request("/nonexistent/file.txt"))
        json_str = result.model_dump_json()
        assert "FAILED" in json_str or "failed" in json_str


class TestNoUnwantedImports:
    def test_no_contextweaver_import(self):
        """Verify markitdown_converter does not import contextweaver."""
        import importlib
        mod = importlib.import_module(
            "ingestion_worker.converters.markitdown_converter"
        )
        source = mod.__file__
        if source:
            with open(source) as f:
                content = f.read()
            assert "contextweaver" not in content.lower()

    def test_no_legacy_write(self):
        """Verify markitdown_converter does not reference legacy path."""
        import importlib
        mod = importlib.import_module(
            "ingestion_worker.converters.markitdown_converter"
        )
        source = mod.__file__
        if source:
            with open(source) as f:
                content = f.read()
            assert "legacy" not in content.lower()
