#!/usr/bin/env python3
"""
Constitution Document Verification Script
Checks 25 documents in docs/aos-constitution/ for structural integrity.
Exit code 0 only when BLOCKER=0 and MAJOR=0.
"""
import os
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "docs" / "aos-constitution"

REQUIRED_FIELDS = [
    "document_id", "title", "level", "authority_mode",
    "parent", "version", "last_updated",
    "defines", "may_reference", "may_not_define",
]

LEVEL_AUTHORITY_MAP = {
    "L1": ["CONSTITUTIONAL"],
    "L2": ["POLICY"],
    "L3": ["SPRINT", "OPERATIONAL"],
    "L4": ["CONDITIONAL"],
    "L5": ["APPEND_ONLY"],
}

NO_CODE_BLOCK_FILES = ["constitution.md", "invariant-lens-spec.md", "external-api-governance.md"]

INVARIANT_LENS_REQUIRED = [
    "sprints/sprint-3a.md", "sprints/sprint-3b1.md", "sprints/sprint-3b2.md",
    "sprints/sprint-5.md", "sprints/sprint-6-gate.md", "sprints/sprint-6.md",
    "operator-runbook.md",
]

SPRINT_KEYWORDS = {
    "sprints/sprint-3a.md": ["UncertaintyContext", "dominant scenario", "Constitutional Judge"],
    "sprints/sprint-3b1.md": ["UncertaintyContext", "Invariant Lens"],
    "sprints/sprint-5.md": ["U3", "Counterfactual", "LOCKDOWN"],
}

ALLOWED_EXTRA_FIELDS = {
    "constitution.md": ["authority_delegates"],
    "invariant-lens-spec.md": ["authority_scope"],
}
# All cond-*.md files get unlock_reason_class
COND_EXTRA_FIELD = "unlock_reason_class"

MAX_TOTAL_LINES = 2387

LINE_LIMITS = {
    "constitution.md": 200,
    "sprint-plan.md": 150,
    "external-api-governance.md": 400,
    "invariant-lens-spec.md": 300,
    "rsg-spec.md": 100,
    "changelog.md": 120,
    "operator-runbook.md": 120,
    "sprints/sprint-1.md": 130,
    "sprints/sprint-2.md": 130,
    "sprints/sprint-3a.md": 200,
    "sprints/sprint-3b1.md": 200,
    "sprints/sprint-3b2.md": 130,
    "sprints/sprint-4a.md": 110,
    "sprints/sprint-4b.md": 110,
    "sprints/sprint-5.md": 200,
    "sprints/sprint-6-gate.md": 80,
    "sprints/sprint-6.md": 80,
    "sprints/sprint-7a.md": 60,
}
# Each cond-*.md: 25 lines max
COND_LINE_LIMIT = 25


def parse_frontmatter(filepath):
    """Parse YAML frontmatter from a markdown file. Returns dict or None."""
    text = filepath.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None, text
    raw = match.group(1)
    fm = {}
    for line in raw.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip()
    return fm, text


def collect_files():
    """Collect all .md files under BASE."""
    files = []
    for root, _, names in os.walk(BASE):
        for name in names:
            if name.endswith(".md"):
                full = Path(root) / name
                rel = full.relative_to(BASE).as_posix()
                files.append((rel, full))
    return sorted(files)


def main():
    blockers = []
    majors = []

    files = collect_files()
    rel_names = [r for r, _ in files]

    # Check 1: File count = 26
    if len(files) != 26:
        blockers.append(f"[1] File count = {len(files)}, expected 26. Files: {rel_names}")

    # Parse all frontmatter
    parsed = {}
    for rel, full in files:
        fm, text = parse_frontmatter(full)
        line_count = len(text.split("\n"))
        parsed[rel] = {"fm": fm, "text": text, "lines": line_count, "path": full}

    # Check 2: document_id count = 25, no duplicates
    doc_ids = []
    for rel, info in parsed.items():
        if info["fm"] and "document_id" in info["fm"]:
            doc_ids.append(info["fm"]["document_id"])
    unique_ids = set(doc_ids)
    if len(doc_ids) != 26:
        blockers.append(f"[2] document_id count = {len(doc_ids)}, expected 26")
    if len(unique_ids) != len(doc_ids):
        dupes = [d for d in doc_ids if doc_ids.count(d) > 1]
        blockers.append(f"[2] Duplicate document_ids: {set(dupes)}")

    # Check 3: authority_mode ↔ level mapping
    for rel, info in parsed.items():
        fm = info["fm"]
        if not fm:
            blockers.append(f"[3] {rel}: No frontmatter found")
            continue
        level = fm.get("level", "")
        mode = fm.get("authority_mode", "")
        allowed = LEVEL_AUTHORITY_MAP.get(level, [])
        if mode not in allowed:
            blockers.append(f"[3] {rel}: level={level} but authority_mode={mode}, expected one of {allowed}")

    # Check 4: Code block prohibition
    for fname in NO_CODE_BLOCK_FILES:
        if fname in parsed:
            count = parsed[fname]["text"].count("```")
            if count > 0:
                blockers.append(f"[4] {fname}: {count} code block markers found (must be 0)")

    # Check 5: Invariant Lens subsection
    for rel in INVARIANT_LENS_REQUIRED:
        if rel in parsed:
            if "### Invariant Lens" not in parsed[rel]["text"]:
                majors.append(f"[5] {rel}: Missing '### Invariant Lens' subsection")
        else:
            majors.append(f"[5] {rel}: File not found")

    # Check 6: Sprint mapping keywords
    for rel, keywords in SPRINT_KEYWORDS.items():
        if rel in parsed:
            for kw in keywords:
                if kw not in parsed[rel]["text"]:
                    majors.append(f"[6] {rel}: Missing keyword '{kw}'")
        else:
            majors.append(f"[6] {rel}: File not found")

    # Check 7: Line counts
    total_lines = sum(info["lines"] for info in parsed.values())
    if total_lines >= MAX_TOTAL_LINES:
        blockers.append(f"[7] Total lines = {total_lines}, must be < {MAX_TOTAL_LINES}")

    for rel, limit in LINE_LIMITS.items():
        if rel in parsed and parsed[rel]["lines"] > limit:
            blockers.append(f"[7] {rel}: {parsed[rel]['lines']} lines, limit {limit}")

    for rel in rel_names:
        if rel.startswith("conditional-designs/cond-"):
            if rel in parsed and parsed[rel]["lines"] > COND_LINE_LIMIT:
                blockers.append(f"[7] {rel}: {parsed[rel]['lines']} lines, limit {COND_LINE_LIMIT}")

    # Check 8: L4 lock structure
    for rel in rel_names:
        if rel.startswith("conditional-designs/cond-"):
            if rel in parsed:
                text = parsed[rel]["text"]
                if "lock_declaration" not in text.lower():
                    majors.append(f"[8] {rel}: Missing lock_declaration")
                fm = parsed[rel]["fm"]
                if not fm or "unlock_reason_class" not in fm:
                    majors.append(f"[8] {rel}: Missing unlock_reason_class in frontmatter")

    # Check 9: Frontmatter completeness (10 required fields)
    for rel, info in parsed.items():
        fm = info["fm"]
        if not fm:
            blockers.append(f"[9] {rel}: No frontmatter")
            continue
        for field in REQUIRED_FIELDS:
            if field not in fm:
                blockers.append(f"[9] {rel}: Missing required field '{field}'")

    # Check 9a: Document-specific extra fields
    if "constitution.md" in parsed:
        fm = parsed["constitution.md"]["fm"]
        if fm and "authority_delegates" not in fm:
            blockers.append("[9a] constitution.md: Missing authority_delegates")

    for rel in rel_names:
        if rel.startswith("conditional-designs/cond-"):
            fm = parsed[rel]["fm"] if rel in parsed else None
            if fm and "unlock_reason_class" not in fm:
                blockers.append(f"[9a] {rel}: Missing unlock_reason_class")

    if "invariant-lens-spec.md" in parsed:
        fm = parsed["invariant-lens-spec.md"]["fm"]
        if fm and "authority_scope" not in fm:
            blockers.append("[9a] invariant-lens-spec.md: Missing authority_scope")

    # Check 9b: Disallowed extra fields
    for rel, info in parsed.items():
        fm = info["fm"]
        if not fm:
            continue
        extra = set(fm.keys()) - set(REQUIRED_FIELDS)
        allowed_extra = set()
        if rel in ALLOWED_EXTRA_FIELDS:
            allowed_extra = set(ALLOWED_EXTRA_FIELDS[rel])
        if rel.startswith("conditional-designs/cond-"):
            allowed_extra.add(COND_EXTRA_FIELD)
        disallowed = extra - allowed_extra
        if disallowed:
            blockers.append(f"[9b] {rel}: Disallowed extra fields: {disallowed}")

    # Check 10: DOC-L2-INVARIANT-LENS specifics
    if "invariant-lens-spec.md" in parsed:
        fm = parsed["invariant-lens-spec.md"]["fm"]
        if fm:
            if fm.get("authority_mode") != "POLICY":
                blockers.append(f"[10] invariant-lens-spec.md: authority_mode={fm.get('authority_mode')}, expected POLICY")
            if fm.get("authority_scope") != "policy_rules_only":
                blockers.append(f"[10] invariant-lens-spec.md: authority_scope={fm.get('authority_scope')}, expected policy_rules_only")
        code_blocks = parsed["invariant-lens-spec.md"]["text"].count("```")
        if code_blocks > 0:
            blockers.append(f"[10] invariant-lens-spec.md: {code_blocks} code block markers (must be 0)")

    # Report
    print("=" * 60)
    print("Constitution Verification Report")
    print("=" * 60)
    print(f"Files found: {len(files)}")
    print(f"Unique document_ids: {len(unique_ids)}")
    print(f"Total lines: {total_lines}")
    print()

    for rel, info in sorted(parsed.items()):
        print(f"  {rel}: {info['lines']} lines")
    print()

    if blockers:
        print(f"BLOCKER ({len(blockers)}):")
        for b in blockers:
            print(f"  {b}")
        print()

    if majors:
        print(f"MAJOR ({len(majors)}):")
        for m in majors:
            print(f"  {m}")
        print()

    if not blockers and not majors:
        print("RESULT: PASS - BLOCKER 0, MAJOR 0")
    else:
        print(f"RESULT: FAIL - BLOCKER {len(blockers)}, MAJOR {len(majors)}")

    sys.exit(0 if (not blockers and not majors) else 1)


if __name__ == "__main__":
    main()
