"""Explicit parser registry; unsupported formats never silently fall back."""

from app.config import Settings
from services.documents.parsers.base import DocumentParser
from services.documents.parsers.csv import CSVParser
from services.documents.parsers.docx import DOCXParser
from services.documents.parsers.pdf import PDFParser
from services.documents.parsers.text import TextParser
from services.documents.parsers.xlsx import XLSXParser
from services.documents.upload_security import FileValidationError


class ParserRegistry:
    def __init__(self, settings: Settings) -> None:
        self.parsers: dict[str, DocumentParser] = {
            ".pdf": PDFParser(settings),
            ".docx": DOCXParser(),
            ".xlsx": XLSXParser(settings),
            ".csv": CSVParser(settings),
            ".txt": TextParser(),
        }

    def resolve(self, extension: str) -> DocumentParser:
        try:
            return self.parsers[extension.casefold()]
        except KeyError as exc:
            raise FileValidationError("UNSUPPORTED_FILE_TYPE") from exc
