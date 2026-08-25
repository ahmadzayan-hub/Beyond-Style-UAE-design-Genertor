"""Secret-leak guard tests: the repo scanner catches real-shaped
credentials, and a Next.js production build never bakes ANTHROPIC_API_KEY
/ OPENAI_API_KEY values into client-side bundle output — the concrete
"ANTHROPIC_API_KEY and OPENAI_API_KEY strings cannot appear in built
frontend output" requirement."""
from __future__ import annotations

import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_secret_scan_catches_a_real_shaped_key(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import secret_scan

    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=fake_repo, check=True)
    (fake_repo / "leaky.py").write_text('KEY = "sk-ant-abcdefghijklmnopqrstuvwxyz0123456789"\n')
    subprocess.run(["git", "add", "-A"], cwd=fake_repo, check=True)

    monkeypatch.chdir(fake_repo)
    findings = secret_scan.scan()
    assert any("Anthropic API key" in f for f in findings)


def test_secret_scan_ignores_clean_files(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import secret_scan

    fake_repo = tmp_path / "repo2"
    fake_repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=fake_repo, check=True)
    (fake_repo / "clean.py").write_text('ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")\n')
    subprocess.run(["git", "add", "-A"], cwd=fake_repo, check=True)

    monkeypatch.chdir(fake_repo)
    findings = secret_scan.scan()
    assert findings == []


def test_current_repo_passes_secret_scan():
    """The actual repository, right now, has no credential-like content
    in any git-tracked file."""
    result = subprocess.run(
        [sys.executable, "scripts/secret_scan.py"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_frontend_build_never_contains_secret_key_material():
    """Builds the Next.js app WITHOUT any ANTHROPIC_API_KEY/OPENAI_API_KEY
    env var set (there is none in this environment) and asserts those
    literal names/values never appear in .next output — this app has no
    Next.js API routes that would need server-side secrets, so nothing
    should ever reference them client-side in the first place. Skipped
    when frontend deps aren't installed (e.g. a backend-only CI job) —
    the equivalent grep runs as its own step in the frontend CI job,
    which always has Node set up. See .github/workflows/ci.yml."""
    frontend_dir = REPO_ROOT / "frontend"
    if not (frontend_dir / "node_modules").is_dir():
        import pytest

        pytest.skip("frontend/node_modules not installed in this job — see the frontend CI job's own check")
    result = subprocess.run(
        ["npm", "run", "build"], cwd=frontend_dir, capture_output=True, text=True, timeout=300
    )
    assert result.returncode == 0, result.stdout + result.stderr

    hits = subprocess.run(
        ["grep", "-rl", "-e", "ANTHROPIC_API_KEY", "-e", "OPENAI_API_KEY", str(frontend_dir / ".next")],
        capture_output=True, text=True,
    )
    assert hits.stdout.strip() == "", f"secret key name leaked into build output: {hits.stdout}"
