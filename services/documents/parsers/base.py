"""Normalized parser contracts."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ParsedElement:
    text: str
    page_number: int | None = None
    section_title: str | None = None
    sheet_name: str | None = None
    row_start: int | None = None
    row_end: int | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedDocument:
    elements: tuple[ParsedElement, ...]
    page_count: int | None = None


class DocumentParser(Protocol):
    def parse(self, path: Path) -> ParsedDocument: ...
