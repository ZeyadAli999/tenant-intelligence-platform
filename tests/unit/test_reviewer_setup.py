"""Static and deterministic safety unit tests for reviewer onboarding scripts."""

import base64
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PS_SCRIPT = ROOT_DIR / "scripts" / "reviewer-setup.ps1"
SH_SCRIPT = ROOT_DIR / "scripts" / "reviewer-setup.sh"


def test_reviewer_setup_scripts_exist():
    """Verify that both Windows PowerShell and Unix Bash setup scripts exist."""
    assert PS_SCRIPT.is_file(), f"PowerShell setup script missing at {PS_SCRIPT}"
    assert SH_SCRIPT.is_file(), f"Bash setup script missing at {SH_SCRIPT}"


def test_scripts_do_not_contain_destructive_docker_commands():
    """Ensure setup scripts never invoke destructive Docker commands."""
    forbidden = [
        "down -v",
        "volume prune",
        "system prune",
        "container prune",
        "docker rm",
    ]

    ps_content = PS_SCRIPT.read_text(encoding="utf-8").lower()
    sh_content = SH_SCRIPT.read_text(encoding="utf-8").lower()

    for cmd in forbidden:
        assert cmd not in ps_content, (
            f"Forbidden command '{cmd}' found in PowerShell setup script"
        )
        assert cmd not in sh_content, (
            f"Forbidden command '{cmd}' found in Bash setup script"
        )


def test_scripts_reference_canonical_urls_and_ports():
    """Verify scripts reference canonical port 3000 and 8000, not temporary developer ports."""
    ps_content = PS_SCRIPT.read_text(encoding="utf-8")
    sh_content = SH_SCRIPT.read_text(encoding="utf-8")

    # Check for canonical frontend URL
    assert "http://localhost:3000" in ps_content
    assert "http://localhost:3000" in sh_content

    # Check for canonical backend readiness URL
    assert "http://localhost:8000/api/health/ready" in ps_content
    assert "http://localhost:8000/api/health/ready" in sh_content

    # Ensure no temporary developer ports (e.g. 3001, 8001, 5433) are hardcoded in canonical scripts
    forbidden_ports = [":3001", ":8001", ":5433", ":9002"]
    for port in forbidden_ports:
        assert port not in ps_content, (
            f"Temporary port {port} found in PowerShell setup script"
        )
        assert port not in sh_content, (
            f"Temporary port {port} found in Bash setup script"
        )


def test_scripts_do_not_log_secrets():
    """Verify setup scripts do not write or echo secrets to terminal output."""
    ps_content = PS_SCRIPT.read_text(encoding="utf-8")
    sh_content = SH_SCRIPT.read_text(encoding="utf-8")

    # Check that passwords and secret values are not echoed or printed
    assert "Write-Host $AdminPassword" not in ps_content
    assert "Write-Host $GroqApiKey" not in ps_content
    assert "Write-Host $jwtSecret" not in ps_content
    assert "echo $ADMIN_PASSWORD" not in sh_content
    assert "echo $GROQ_API_KEY" not in sh_content


def test_docker_exec_password_passed_by_variable_name_only():
    """Verify docker compose exec references -e BOOTSTRAP_ADMIN_PASSWORD by variable name without a literal."""
    ps_content = PS_SCRIPT.read_text(encoding="utf-8")
    sh_content = SH_SCRIPT.read_text(encoding="utf-8")

    # Verify presence of inherited environment variable flag
    assert "-e BOOTSTRAP_ADMIN_PASSWORD" in ps_content
    assert "-e BOOTSTRAP_ADMIN_PASSWORD" in sh_content

    # Ensure no literal variable assignment occurs inside the docker compose command string
    assert "-e BOOTSTRAP_ADMIN_PASSWORD=" not in ps_content
    assert "-e BOOTSTRAP_ADMIN_PASSWORD=" not in sh_content



def test_scripts_do_not_contain_developer_specific_paths():
    """Verify setup scripts do not hardcode local developer folder paths."""
    ps_content = PS_SCRIPT.read_text(encoding="utf-8").lower()
    sh_content = SH_SCRIPT.read_text(encoding="utf-8").lower()

    dev_paths = ["c:\\users\\zezos", "/home/zezos", "/users/zezos"]
    for dev_path in dev_paths:
        assert dev_path not in ps_content, (
            f"Developer path '{dev_path}' found in PowerShell script"
        )
        assert dev_path not in sh_content, (
            f"Developer path '{dev_path}' found in Bash script"
        )


def test_base64url_key_generation_format():
    """Verify the 32-byte base64url key format expected by backend Settings validator."""
    # Generate 32 bytes and base64url encode without padding
    raw = b"12345678901234567890123456789012"  # 32 bytes
    encoded = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    # Decoding with padding restoration
    padding = "=" * (-len(encoded) % 4)
    decoded = base64.b64decode(encoded + padding, altchars=b"-_", validate=True)
    assert len(decoded) == 32


def test_scripts_contain_instructor_evaluation_defaults():
    """Verify setup scripts default to Instructor Evaluation tenant and email credentials."""
    ps_content = PS_SCRIPT.read_text(encoding="utf-8")
    sh_content = SH_SCRIPT.read_text(encoding="utf-8")

    assert "instructor-review" in ps_content
    assert "instructor-review" in sh_content
    assert "instructor@demo.example" in ps_content
    assert "instructor@demo.example" in sh_content
    assert "Instructor Evaluation" in ps_content
    assert "Instructor Evaluation" in sh_content
    assert "Instructor Reviewer" in ps_content
    assert "Instructor Reviewer" in sh_content


def test_powershell_root_resolution_uses_psscriptroot():
    """Verify scripts/reviewer-setup.ps1 uses $PSScriptRoot and not $MyInvocation.MyCommand.Definition."""
    ps_content = PS_SCRIPT.read_text(encoding="utf-8")

    assert "$PSScriptRoot" in ps_content
    assert "$MyInvocation.MyCommand.Definition" not in ps_content
    assert "tenant-intelligence-copilot" not in ps_content.lower()


def test_readme_public_naming_and_instructor_content():
    """Verify README.md is sanitized of internal names and contains required instructor details."""
    readme_path = ROOT_DIR / "README.md"
    readme_content = readme_path.read_text(encoding="utf-8")
    readme_lower = readme_content.lower()

    # Sanitization checks
    assert "copilot" not in readme_lower
    assert "codex" not in readme_lower
    assert "antigravity" not in readme_lower

    # Required instructions and placeholders
    assert "cd <path-to-downloaded-repository>" in readme_content
    assert "00 — INSTRUCTOR ACCESS & LOGIN CREDENTIALS" in readme_content
    assert "Option 1:" in readme_content
    assert "Option 2:" in readme_content
    assert r".\scripts\reviewer-setup.ps1" in readme_content
    assert "instructor-review" in readme_content
    assert "instructor@demo.example" in readme_content
