#!/usr/bin/env python3
"""Secret-leak guard — CI fails the build on detected credential-like
content. Scans every git-tracked file (never node_modules/.next/.git
internals — git ls-files already excludes those). Stdlib only.

Usage: python3 scripts/secret_scan.py   (exits 1 and prints matches on
a real hit — never prints the full secret value, only file:line.)
"""
from __future__ import annotations

import re
import subprocess
import sys

# (name, compiled pattern) — real credential SHAPES, not just var names,
# to avoid flagging this file itself or docs that mention key names.
PATTERNS = [
    ("Anthropic API key", re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}")),
    ("OpenAI API key", re.compile(r"sk-(proj-)?[a-zA-Z0-9_-]{20,}")),
    ("AWS access key ID", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Generic private key block", re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("Vercel token", re.compile(r"\bvercel_[A-Za-z0-9]{20,}")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
]

# Files that legitimately document key *names*/*shapes* in prose or
# regexes (this scanner and its own tests) — never real key material.
EXEMPT_PATHS = {"scripts/secret_scan.py", "backend/tests/test_secret_scan.py"}


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
    return [f for f in out.stdout.splitlines() if f]


def scan() -> list[str]:
    findings = []
    for path in tracked_files():
        if path in EXEMPT_PATHS:
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                for lineno, line in enumerate(fh, start=1):
                    for name, pattern in PATTERNS:
                        if pattern.search(line):
                            findings.append(f"{path}:{lineno}: possible {name}")
        except (IsADirectoryError, PermissionError):
            continue
    return findings


def main() -> int:
    findings = scan()
    if findings:
        print("Secret scan FAILED — credential-like content found:")
        for f in findings:
            print(f"  {f}")
        return 1
    print("Secret scan OK — no credential-like content found in tracked files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
