"""Protect public project documentation without coupling it to old README layout."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SECURITY = ROOT / "SECURITY.md"
ARCHIVED = ROOT / "docs/reference/full-technical-reference-2026.md"


def test_public_readme_explains_current_scope() -> None:
    readme = README.read_text(encoding="utf-8").casefold()
    for expected in (
        "text-to-sql", "sqlglot", "document rag", "multi-tenant",
        "permissions", "read-only", "groq api key", "known limitations",
    ):
        assert expected in readme, f"Missing project scope detail: {expected}"
    for obsolete in (
        "natural-language sql generation, llms",
        "future database agent",
        "document rag, and hybrid answers\nare not implemented",
        "document/hybrid execution are deliberately rejected",
    ):
        assert obsolete not in readme


def test_security_boundaries_and_provider_configuration_documented() -> None:
    readme = README.read_text(encoding="utf-8").casefold()
    security = SECURITY.read_text(encoding="utf-8").casefold()
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for folder in ("app", "api", "services")
        for path in (ROOT / folder).rglob("*.py")
    ).casefold()
    assert "not an llm prompt" in readme
    assert "server-resolved tenant identity" in readme
    assert "groq_api_key" in security
    assert "no provider switch" in security
    assert "explicit automated-test dependency injection" in security
    for obsolete in (
        "openai_api_key", "smoke_openai_phase3c", "services.llm.openai_provider",
    ):
        assert obsolete not in readme
        assert obsolete not in source
    assert "llm_provider" not in readme


def test_original_instructor_reference_is_preserved() -> None:
    readme = README.read_text(encoding="utf-8")
    original = ARCHIVED.read_text(encoding="utf-8")
    assert "docs/reference/full-technical-reference-2026.md" in readme
    for expected in (
        "00 — INSTRUCTOR ACCESS & LOGIN CREDENTIALS",
        "Option 1:", "Option 2:",
        "instructor-review", "instructor@demo.example",
        "Phase 3C database chat",
        "Phase 4 document infrastructure and APIs",
    ):
        assert expected in original
