"""Deterministic, metadata-preserving token-window chunker."""

import hashlib
import re
from dataclasses import dataclass

from app.config import Settings
from services.documents.parsers.base import ParsedDocument
from services.documents.upload_security import FileValidationError

TOKEN = re.compile(r"\S+")


@dataclass(frozen=True)
class ChunkDraft:
    index: int
    content: str
    content_hash: str
    token_count: int
    page_number: int | None
    section_title: str | None
    sheet_name: str | None
    row_start: int | None
    row_end: int | None
    metadata: dict[str, object]


def chunk_document(
    document: ParsedDocument, settings: Settings
) -> tuple[ChunkDraft, ...]:
    target = settings.document_chunk_target_tokens
    overlap = min(settings.document_chunk_overlap_tokens, target - 1)
    result: list[ChunkDraft] = []
    for element in document.elements:
        tokens = TOKEN.findall(element.text)
        start = 0
        while start < len(tokens):
            window = tokens[start : start + target]
            content = " ".join(window).strip()
            if content:
                result.append(
                    ChunkDraft(
                        len(result),
                        content,
                        hashlib.sha256(content.encode()).hexdigest(),
                        len(window),
                        element.page_number,
                        element.section_title,
                        element.sheet_name,
                        element.row_start,
                        element.row_end,
                        dict(element.metadata),
                    )
                )
            if len(result) > settings.document_max_chunks_per_file:
                raise FileValidationError("CONTENT_LIMIT_EXCEEDED")
            if start + target >= len(tokens):
                break
            start += target - overlap
    if not result:
        raise FileValidationError("PARSING_FAILED")
    return tuple(result)
