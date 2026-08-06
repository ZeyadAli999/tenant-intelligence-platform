"""Portable archive hygiene tests."""

import zipfile
from pathlib import PurePosixPath

from scripts.package_project import create_portable_zip


def test_portable_zip_has_safe_posix_paths(tmp_path) -> None:
    root = tmp_path / "project"
    (root / "api").mkdir(parents=True)
    (root / "app").mkdir()
    (root / "migrations").mkdir()
    (root / "migrations/versions").mkdir()
    (root / "services/documents").mkdir(parents=True)
    (root / "workers").mkdir()
    (root / "frontend/app/login").mkdir(parents=True)
    (root / "frontend/app/(authenticated)/databases").mkdir(parents=True)
    (root / "frontend/app/api/backend/[...path]").mkdir(parents=True)
    (root / "frontend/components/databases").mkdir(parents=True)
    (root / "frontend/lib").mkdir(parents=True)
    (root / "frontend/tests").mkdir(parents=True)
    (root / "frontend/node_modules/pkg").mkdir(parents=True)
    (root / "frontend/.next/cache").mkdir(parents=True)
    (root / "outputs").mkdir()
    (root / "work").mkdir()
    for name in (
        "api/router.py",
        "app/main.py",
        "migrations/env.py",
        "migrations/versions/20260803_0006_document_rag_hybrid.py",
        "services/documents/retrieval.py",
        "workers/document_tasks.py",
        "frontend/package.json",
        "frontend/package-lock.json",
        "frontend/app/login/page.tsx",
        "frontend/app/(authenticated)/databases/page.tsx",
        "frontend/app/api/backend/[...path]/route.ts",
        "frontend/components/databases/database-workspace.tsx",
        "frontend/components/databases/database-list-view.tsx",
        "frontend/components/databases/database-detail-view.tsx",
        "frontend/components/databases/database-modal.tsx",
        "frontend/components/databases/connection-list-table.tsx",
        "frontend/components/databases/schema-table-explorer.tsx",
        "frontend/lib/database-api.ts",
        "frontend/lib/database-contracts.ts",
        "frontend/tests/database-phase5d.test.ts",
        "frontend/tests/database-ui.test.tsx",
        "README.md",
        "SECURITY.md",
        ".env.example",
    ):
        path = root / name
        path.write_text("safe", encoding="utf-8")
    (root / ".env").write_text("SECRET=unsafe", encoding="utf-8")
    (root / "frontend/.env.local").write_text("SECRET=unsafe", encoding="utf-8")
    (root / "frontend/node_modules/pkg/index.js").write_text("unsafe", encoding="utf-8")
    (root / "frontend/.next/cache/item").write_text("unsafe", encoding="utf-8")
    (root / "frontend/tsconfig.tsbuildinfo").write_text("unsafe", encoding="utf-8")
    (root / "work/temporary.log").write_text("unsafe", encoding="utf-8")
    (root / "outputs/nested.zip").write_bytes(b"unsafe")
    output = tmp_path / "portable.zip"
    create_portable_zip(root, output)
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert names == sorted(names)
        assert all("\\" not in name for name in names)
        assert all(not PurePosixPath(name).is_absolute() for name in names)
        assert all(".." not in PurePosixPath(name).parts for name in names)
        assert len(names) == len({name.casefold() for name in names})
        assert ".env" not in names
        assert all(not name.startswith(("work/", "outputs/")) for name in names)
        assert all("node_modules" not in name and ".next" not in name for name in names)
        assert "frontend/.env.local" not in names
        assert "frontend/tsconfig.tsbuildinfo" not in names
