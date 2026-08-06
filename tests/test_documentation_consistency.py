"""Prevent Phase 3C documentation from regressing to obsolete scope claims."""

from pathlib import Path


def test_phase3c_documentation_has_no_obsolete_scope_claims() -> None:
    readme = Path("README.md").read_text(encoding="utf-8").casefold()
    security = Path("SECURITY.md").read_text(encoding="utf-8").casefold()
    obsolete = (
        "natural-language sql generation, llms",
        "conversations, chat, redis",
        "future database agent",
    )
    assert "phase 3c" in readme
    assert all(claim not in readme for claim in obsolete)
    assert "phase 4" in security.splitlines()[0]


def test_phase3c_groq_only_runtime_documentation_and_source_contract() -> None:
    readme = Path("README.md").read_text(encoding="utf-8").casefold()
    security = Path("SECURITY.md").read_text(encoding="utf-8").casefold()
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for root in ("app", "api", "services")
        for path in Path(root).rglob("*.py")
    ).casefold()
    assert "groq cloud is the only real application provider" in readme
    assert "no provider switch" in readme
    assert "explicit automated-test dependency injection" in security
    for obsolete in (
        "openai_api_key",
        "smoke_openai_phase3c",
        "services.llm.openai_provider",
    ):
        assert obsolete not in readme
        assert obsolete not in source
    assert "`llm_provider`" not in readme


def test_phase4_documentation_has_no_obsolete_document_scope_claims() -> None:
    readme = Path("README.md").read_text(encoding="utf-8").casefold()
    security = Path("SECURITY.md").read_text(encoding="utf-8").casefold()
    assert "phase 4 document infrastructure and apis" in readme
    assert "phase 4 file, retrieval, and evidence boundary" in security
    for obsolete in (
        "document rag, and hybrid answers\nare not implemented",
        "redis, background workers, qdrant, and minio are also not used",
        "document and hybrid retrieval are outside phase 3c",
        "document/hybrid execution are deliberately rejected",
    ):
        assert obsolete not in readme
        assert obsolete not in security
