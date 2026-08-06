"""Bounded plain-text parser with safe encoding detection."""

from pathlib import Path

from charset_normalizer import from_bytes

from services.documents.parsers.base import ParsedDocument, ParsedElement
from services.documents.upload_security import FileValidationError


class TextParser:
    def parse(self, path: Path) -> ParsedDocument:
        match = from_bytes(path.read_bytes()).best()
        if match is None:
            raise FileValidationError("PARSING_FAILED")
        text = str(match).strip()
        if not text:
            raise FileValidationError("PARSING_FAILED")
        return ParsedDocument((ParsedElement(text),))
