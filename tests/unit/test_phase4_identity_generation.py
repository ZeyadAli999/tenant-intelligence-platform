"""Regression coverage for valid disposable Phase 4 identity generation."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from pydantic import EmailStr, TypeAdapter

from scripts import phase4_live_stages as live
from scripts.disposable_identity import disposable_email
from scripts.phase4_safe_inspect import SMOKE_CODE

EMAIL = TypeAdapter(EmailStr)


def valid(value: str) -> str:
    return EMAIL.validate_python(value)


def test_every_generated_identity_shape_is_emailstr_compatible() -> None:
    for prefix in ("admin", "admin-other", "user", "eval"):
        address = disposable_email(prefix, "012345abcdef")
        assert valid(address) == address
        assert address.endswith("@example.com")


def test_create_identities_bootstraps_both_valid_admin_emails(
    monkeypatch, tmp_path
) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(live.secrets, "token_hex", lambda _: "012345abcdef")
    monkeypatch.setattr(live.secrets, "token_urlsafe", lambda _: "temporary-password")

    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(live.subprocess, "run", run)
    state: dict[str, object] = {}
    live.create_identities(tmp_path, state, "document")
    assert len(commands) == 2
    emails = [command[command.index("--admin-email") + 1] for command in commands]
    assert emails == [
        "admin-012345abcdef@example.com",
        "admin-other-012345abcdef@example.com",
    ]
    assert all(valid(email) == email for email in emails)


def test_authenticate_creates_normal_user_with_valid_email(
    monkeypatch, tmp_path
) -> None:
    created: list[str] = []
    monkeypatch.setattr(live.secrets, "token_hex", lambda _: "01234567")
    monkeypatch.setattr(live.secrets, "token_urlsafe", lambda _: "temporary-password")

    def request(state, method, path, **kwargs):
        if path == "/users":
            created.append(str(kwargs["json"]["email"]))
            return {"id": "normal-user"}
        if path == "/auth/me":
            tenant = "other" if kwargs.get("token") == "second-token" else "primary"
            return {"tenant": {"id": tenant}}
        if kwargs.get("json", {}).get("tenant_code", "").startswith("p4-other-"):
            return {"access_token": "second-token"}
        return {"access_token": "primary-token"}

    monkeypatch.setattr(live, "request", request)
    state: dict[str, object] = {
        "tenant_code": "p4-012345abcdef",
        "email": "admin-012345abcdef@example.com",
        "password": "temporary-password",
        "second_tenant_code": "p4-other-012345abcdef",
        "second_tenant_email": "admin-other-012345abcdef@example.com",
        "second_tenant_password": "temporary-password",
    }
    live.authenticate(tmp_path, state, "document")
    assert created == ["user-01234567@example.com"]
    assert valid(created[0]) == created[0]
    assert (
        json.loads((tmp_path / "state.json").read_text())["normal_email"] == created[0]
    )


def test_evaluator_identity_email_is_valid() -> None:
    address = disposable_email("eval", uuid4().hex)
    assert valid(address) == address


def test_reserved_invalid_domain_is_absent_from_executable_scripts() -> None:
    forbidden = "example" + ".invalid"
    project = Path(__file__).resolve().parents[2]
    hits = [
        path
        for path in (project / "scripts").rglob("*.py")
        if forbidden in path.read_text(encoding="utf-8")
    ]
    assert hits == []


def test_cleanup_tenant_naming_safeguards_are_unchanged() -> None:
    assert SMOKE_CODE.fullmatch("p4-012345abcdef")
    assert SMOKE_CODE.fullmatch("p4-other-012345abcdef")
    assert SMOKE_CODE.fullmatch("demo") is None
