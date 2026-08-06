"""Create and verify a deterministic, portable project ZIP."""

import argparse
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

EXCLUDED_DIRS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".next",
    ".auth",
    "__pycache__",
    "coverage",
    "accessibility-reports",
    "auth-state",
    "htmlcov",
    "node_modules",
    "outputs",
    "playwright-report",
    "secrets",
    "tmp",
    "test-results",
    "visual-test-output",
    "work",
}
EXCLUDED_NAMES = {".env", ".env.local", ".coverage", "state.json", "demo_policy.txt"}
EXCLUDED_SUFFIXES = {
    ".db",
    ".log",
    ".key",
    ".pem",
    ".pyc",
    ".sqlite",
    ".sqlite3",
    ".tsbuildinfo",
    ".zip",
}
FIXED_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


def project_files(root: Path) -> list[tuple[PurePosixPath, Path]]:
    files: list[tuple[PurePosixPath, Path]] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if not path.is_file() or path.name in EXCLUDED_NAMES:
            continue
        if path.suffix.casefold() in EXCLUDED_SUFFIXES:
            continue
        archive_path = PurePosixPath(*relative.parts)
        validate_archive_name(str(archive_path))
        files.append((archive_path, path))
    files.sort(key=lambda item: str(item[0]))
    normalized = [str(item[0]).casefold() for item in files]
    if len(normalized) != len(set(normalized)):
        raise ValueError("Duplicate normalized archive paths")
    return files


def validate_archive_name(name: str) -> None:
    if "\\" in name:
        raise ValueError("ZIP entry contains a backslash")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("ZIP entry is absolute or traverses directories")
    if path.parts and ":" in path.parts[0]:
        raise ValueError("ZIP entry contains a drive-letter path")


def create_portable_zip(root: Path, output: Path) -> Path:
    root = root.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = project_files(root)
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for archive_path, source in files:
            info = zipfile.ZipInfo(str(archive_path), FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())
    verify_portable_zip(output)
    return output


def verify_portable_zip(archive_path: Path) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        for name in names:
            validate_archive_name(name)
        normalized = [str(PurePosixPath(name)).casefold() for name in names]
        if len(normalized) != len(set(normalized)):
            raise ValueError("ZIP contains duplicate normalized paths")
        required = {
            "api/router.py",
            "app/main.py",
            "migrations/env.py",
            "migrations/versions/20260803_0006_document_rag_hybrid.py",
            "services/documents/retrieval.py",
            "workers/document_tasks.py",
            "frontend/package.json",
            "frontend/package-lock.json",
            "frontend/app/login/page.tsx",
            "README.md",
        }
        if not required.issubset(names):
            raise ValueError("ZIP is missing the expected project tree")
        with tempfile.TemporaryDirectory(prefix="phase4-zip-check-") as directory:
            archive.extractall(directory)
            extracted = Path(directory)
            if not all((extracted / path).is_file() for path in required):
                raise ValueError("Portable ZIP extraction verification failed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = create_portable_zip(arguments.root, arguments.output)
    print(f"Portable archive created: {result.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
