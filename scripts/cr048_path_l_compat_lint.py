"""CR-048 RI-2B-2c Path L SQLite compatibility lint gate.

Purpose
-------
Scan `app/` Python sources for SQL syntax patterns that break on SQLite
(aiosqlite driver, SQLite 3.35+) but are accepted by PostgreSQL. The gate
exists to prevent regression after the Option A2 remediation in
`app/services/shadow_write_service.py` line ~568, where a raw
`text("SELECT ... FOR UPDATE")` was replaced by a dialect-aware ORM
`select(...).with_for_update()` construct.

Scope
-----
- Files scanned: `app/**/*.py`
- Lines skipped:
    * pure comment lines and inline comment tails after `#`
    * docstring line ranges (detected via AST)
- Files known-excluded (see KNOWN_EXCLUSIONS below):
    * `app/models/paper_session.py` — pre-existing JSONB usage, outside
      the CR-048 RI-2B-2c Session 2 Option A2 remediation scope
- Patterns enforced: see FORBIDDEN_PATTERNS below (word-boundary guarded)
- Exit code: 0 = clean, 1 = at least one new violation

Scope boundaries (governance lock)
----------------------------------
- Does NOT modify any application source file
- Does NOT touch `tests/`, `alembic/`, or any other directory
- Does NOT enforce ILIKE, `::` cast, or raw `text(` detection
  (too broad — those require hand review, not automated gating)
- Does NOT attempt to fix files in the known-exclusions list
  (that work belongs to a future remediation session, not Session 2)

Usage
-----
    python scripts/cr048_path_l_compat_lint.py

Exit codes
----------
    0  clean — zero violations outside the known-exclusions list
    1  failed — at least one forbidden pattern found in a non-excluded file
    2  internal error (app/ not found, etc.)
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

# ── Forbidden Postgres-only SQL patterns (break on SQLite) ────────

FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    (r"\bFOR\s+UPDATE\b", "FOR UPDATE (use ORM .with_for_update() instead)"),
    (r"\bFOR\s+SHARE\b", "FOR SHARE (Postgres-only lock modifier)"),
    (r"\bDISTINCT\s+ON\b", "DISTINCT ON (Postgres-only select modifier)"),
    (r"\bLATERAL\b", "LATERAL join (Postgres-only)"),
    (r"\bNULLS\s+(?:FIRST|LAST)\b", "NULLS FIRST/LAST sort order (Postgres-only)"),
    (r"\bGENERATED\s+ALWAYS\b", "GENERATED ALWAYS column (Postgres-only DDL)"),
    (r"\bjsonb\b", "jsonb type (Postgres-only)"),
    (r"\bJSONB\b", "JSONB type (Postgres-only)"),
    (r"\bunnest\s*\(", "unnest() function (Postgres-only)"),
    (r"ARRAY\s*\[", "ARRAY[...] literal (Postgres-only)"),
]

# ── Known-exclusions (pre-existing Path L incompatibilities) ──────
#
# Each entry below is a file whose known Postgres-only usage is
# documented but NOT in scope for the current Session 2 Option A2
# remediation. Removing an entry here is a separate CR/session decision.

KNOWN_EXCLUSIONS: dict[str, str] = {
    "app/models/paper_session.py": (
        "pre-existing JSONB column type usage; out of scope for "
        "CR-048 RI-2B-2c Session 2 (Option A2 targets shadow_write_service "
        "line 568 only). Separate Path L compatibility session required."
    ),
}


def _strip_inline_comment(line: str) -> str:
    """Remove a Python-style trailing `# comment`.

    Deliberately simple: splits on the first `#` and returns the prefix.
    Does not parse string literals — but the forbidden SQL patterns
    above live inside Python string literals, which would still appear
    in the prefix if present in real code.
    """
    if "#" not in line:
        return line
    return line.split("#", 1)[0]


def _collect_docstring_lines(tree: ast.AST) -> set[int]:
    """Return the set of 1-based line numbers that are inside a docstring.

    A docstring is defined as the first statement of a Module,
    FunctionDef, AsyncFunctionDef, or ClassDef node when that first
    statement is an Expr whose value is a string Constant.
    """
    doc_lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node,
            (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if not isinstance(first, ast.Expr):
            continue
        if not isinstance(first.value, ast.Constant):
            continue
        if not isinstance(first.value.value, str):
            continue
        start = first.lineno
        end = getattr(first, "end_lineno", start) or start
        for ln in range(start, end + 1):
            doc_lines.add(ln)
    return doc_lines


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Return list of (line_no, raw_line, pattern_description) violations."""
    violations: list[tuple[int, str, str]] = []
    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return violations

    # Detect docstring line ranges to skip via AST.
    try:
        tree = ast.parse(content, filename=str(path))
        docstring_lines = _collect_docstring_lines(tree)
    except SyntaxError:
        docstring_lines = set()

    for lineno, line in enumerate(content.splitlines(), start=1):
        if lineno in docstring_lines:
            continue
        code_part = _strip_inline_comment(line)
        if not code_part.strip():
            continue
        for pattern, description in FORBIDDEN_PATTERNS:
            if re.search(pattern, code_part):
                violations.append((lineno, line.rstrip(), description))
                break  # one violation per line is enough signal
    return violations


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    app_dir = repo_root / "app"

    if not app_dir.exists():
        print(
            f"[cr048-path-l-compat-lint] ERROR: {app_dir} not found",
            file=sys.stderr,
        )
        return 2

    enforced_violations = 0
    excluded_violation_count = 0
    files_scanned = 0
    files_excluded = 0

    for py_file in sorted(app_dir.rglob("*.py")):
        rel = py_file.relative_to(repo_root).as_posix()
        violations = scan_file(py_file)
        if rel in KNOWN_EXCLUSIONS:
            files_excluded += 1
            excluded_violation_count += len(violations)
            continue
        files_scanned += 1
        if violations:
            for lineno, line, description in violations:
                print(f"{rel}:{lineno}: {description}")
                print(f"    {line}")
            enforced_violations += len(violations)

    print()
    print(
        f"[cr048-path-l-compat-lint] scanned {files_scanned} file(s) "
        f"in app/ (excluded {files_excluded})"
    )
    if excluded_violation_count:
        print(
            f"[cr048-path-l-compat-lint] {excluded_violation_count} "
            f"pre-existing violation(s) in known-exclusions list (not enforced)"
        )
        for rel, reason in KNOWN_EXCLUSIONS.items():
            print(f"    - {rel}: {reason}")
    if enforced_violations:
        print(f"[cr048-path-l-compat-lint] FAIL: {enforced_violations} violation(s)")
        return 1
    print("[cr048-path-l-compat-lint] PASS: 0 enforced violations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
