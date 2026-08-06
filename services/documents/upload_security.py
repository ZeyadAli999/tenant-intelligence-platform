"""Streaming upload validation with bounded archive inspection."""

import hashlib
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import aiofiles
from fastapi import UploadFile

from app.config import Settings

SUPPORTED = {".pdf", ".docx", ".xlsx", ".csv", ".txt"}
MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv",
    ".txt": "text/plain",
}


class FileValidationError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ValidatedUpload:
    path: Path
    display_name: str
    extension: str
    detected_mime_type: str
    size: int
    checksum: str


def sanitize_display_name(filename: str | None) -> tuple[str, str]:
    raw = (filename or "").strip()
    if (
        not raw
        or "/" in raw
        or "\\" in raw
        or ":" in raw
        or raw != Path(raw).name
        or ".." in PurePosixPath(raw.replace("\\", "/")).parts
    ):
        raise FileValidationError("UNSUPPORTED_FILE_TYPE")
    cleaned = re.sub(r"[^A-Za-z0-9._ ()\-\u0080-\uffff]", "_", raw)[:255]
    extension = Path(cleaned).suffix.casefold()
    if extension not in SUPPORTED:
        raise FileValidationError("UNSUPPORTED_FILE_TYPE")
    return cleaned, extension


async def stream_and_validate(
    upload: UploadFile, settings: Settings
) -> ValidatedUpload:
    name, extension = sanitize_display_name(upload.filename)
    digest = hashlib.sha256()
    size = 0
    descriptor, temporary_name = tempfile.mkstemp(prefix="document-", suffix=extension)
    os.close(descriptor)
    path = Path(temporary_name)
    try:
        async with aiofiles.open(path, "wb") as temporary:
            while data := await upload.read(1024 * 1024):
                size += len(data)
                if size > settings.document_max_file_bytes:
                    raise FileValidationError("FILE_TOO_LARGE")
                digest.update(data)
                await temporary.write(data)
        if size == 0:
            raise FileValidationError("EMPTY_FILE")
        detected = detect_type(path, extension)
        inspect_container(path, extension)
        return ValidatedUpload(
            path, name, extension, detected, size, digest.hexdigest()
        )
    except Exception:
        path.unlink(missing_ok=True)
        raise


def detect_type(path: Path, extension: str) -> str:
    with path.open("rb") as stream:
        prefix = stream.read(16)
    if extension == ".pdf" and not prefix.startswith(b"%PDF-"):
        raise FileValidationError("MIME_MISMATCH")
    if extension in (".docx", ".xlsx") and not prefix.startswith(b"PK\x03\x04"):
        raise FileValidationError("MIME_MISMATCH")
    if extension in (".csv", ".txt") and b"\x00" in prefix:
        raise FileValidationError("MIME_MISMATCH")
    return MIME_BY_EXTENSION[extension]


def inspect_container(path: Path, extension: str) -> None:
    if extension not in (".docx", ".xlsx"):
        return
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > 5000:
                raise FileValidationError("ARCHIVE_LIMIT_EXCEEDED")
            expanded = 0
            for info in infos:
                normalized = PurePosixPath(info.filename.replace("\\", "/"))
                if normalized.is_absolute() or ".." in normalized.parts:
                    raise FileValidationError("ARCHIVE_LIMIT_EXCEEDED")
                expanded += info.file_size
                if expanded > 200_000_000:
                    raise FileValidationError("ARCHIVE_LIMIT_EXCEEDED")
                if info.compress_size and info.file_size / info.compress_size > 100:
                    raise FileValidationError("ARCHIVE_LIMIT_EXCEEDED")
                lower = info.filename.casefold()
                if lower.endswith(("vbaproject.bin", ".exe", ".js", ".vbs")):
                    raise FileValidationError("UNSUPPORTED_FILE_TYPE")
            names = {item.filename for item in infos}
            required = (
                "word/document.xml" if extension == ".docx" else "xl/workbook.xml"
            )
            if required not in names or "[Content_Types].xml" not in names:
                raise FileValidationError("MIME_MISMATCH")
    except zipfile.BadZipFile as exc:
        raise FileValidationError("MIME_MISMATCH") from exc
