"""Abstract base class for file converters."""

from abc import ABC, abstractmethod

from reality_rag_contracts import ConversionRequest, ConversionResult


class BaseConverter(ABC):
    """Converter interface. Each converter handles a set of file extensions."""

    @abstractmethod
    def convert(self, request: ConversionRequest) -> ConversionResult:
        """Convert a source file to canonical markdown."""

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return the list of file extensions this converter can handle."""
