"""Bounded CSV parser retaining row ranges."""

import csv
from pathlib import Path

from charset_normalizer import from_bytes

from app.config import Settings
from services.documents.parsers.base import ParsedDocument, ParsedElement
from services.documents.upload_security import FileValidationError


class CSVParser:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def parse(self, path: Path) -> ParsedDocument:
        try:
            match = from_bytes(path.read_bytes()).best()
            if match is None:
                raise FileValidationError("PARSING_FAILED")
            rows = list(csv.reader(str(match).splitlines()))
            if (
                len(rows) > self.settings.document_max_spreadsheet_rows
                or sum(map(len, rows)) > self.settings.document_max_spreadsheet_cells
            ):
                raise FileValidationError("CONTENT_LIMIT_EXCEEDED")
            elements = tuple(
                ParsedElement(
                    "\n".join(
                        " | ".join(cell for cell in row)
                        for row in rows[start : start + 50]
                    ),
                    row_start=start + 1,
                    row_end=min(start + 50, len(rows)),
                )
                for start in range(0, len(rows), 50)
            )
            return ParsedDocument(elements)
        except FileValidationError:
            raise
        except Exception as exc:
            raise FileValidationError("PARSING_FAILED") from exc
