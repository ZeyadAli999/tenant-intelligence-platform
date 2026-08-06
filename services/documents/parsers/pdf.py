"""Bounded text-only PDF parser; OCR is deliberately disabled."""

from pathlib import Path

import pymupdf

from app.config import Settings
from services.documents.parsers.base import ParsedDocument, ParsedElement
from services.documents.upload_security import FileValidationError


class PDFParser:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def parse(self, path: Path) -> ParsedDocument:
        try:
            document = pymupdf.open(path)
            if document.needs_pass:
                raise FileValidationError("ENCRYPTED_DOCUMENT")
            if document.page_count > self.settings.document_max_pages:
                raise FileValidationError("CONTENT_LIMIT_EXCEEDED")
            elements = tuple(
                ParsedElement(text=page.get_text("text").strip(), page_number=index + 1)
                for index, page in enumerate(document)
                if page.get_text("text").strip()
            )
            return ParsedDocument(elements, document.page_count)
        except FileValidationError:
            raise
        except Exception as exc:
            raise FileValidationError("PARSING_FAILED") from exc
