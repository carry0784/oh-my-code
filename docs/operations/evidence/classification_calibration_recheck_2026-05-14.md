# CR-025: Classification Calibration Recheck Pack

Date: 2026-05-14
Status: **PASS — CALIBRATION DEBT RESOLVED**
Author: B (Implementer)
CR-ID: CR-025
Category: L1 (operational governance, no code change)
Purpose: Resolve calibration debt from CR-022 (criterion #8: 3/5 → target 4/5+)

---

## 1. Background

CR-022 multi-operator onboarding (2026-05-08) identified a classification
consistency gap: A and B matched on 3/5 samples (60%), below the 90%
target. A issued CONDITIONAL PASS with the following conditions:

1. Canonical classifications fixed in multi_operator_readiness_pack.md
2. Next bi-weekly calibration must re-run 5-sample test
3. Boundary rules established (default-to-C for validation surface,
   default-to-L3 for board fields)

This document executes condition #2.

---

## 2. Calibration Protocol

1. B prepares 5 new hypothetical change descriptions (below)
2. A and B independently classify each: **Level (L1/L2/L3)** + **Category (A/B/C/D)**
3. Compare results
4. Target: >= 4/5 (80%) match on Level AND Category

### Scoring Rules

- **Match**: Level AND Category both agree
- **Partial**: Level agrees, Category differs by 1 step (A↔B or B↔C)
- **Mismatch**: Level disagrees OR Category differs by 2+ steps

### Decision Matrix

| Score | Outcome |
|-------|---------|
| 5/5 | FULL PASS — upgrade to unconditional 8/8 |
| 4/5 | PASS — upgrade to unconditional 8/8 |
| 3/5 | EXTEND — add boundary rules, schedule re-run |
| <= 2/5 | FAIL — systematic training needed |

---

## 3. Calibration Samples

### Sample 1

**Description**: Add a `last_checked_at` timestamp field to the
sustained_operation_log.md template for daily checks.

**Affected files**: docs/operations/sustained_operation_log.md
**Affected OC rules**: None

| Classifier | Level | Category | Reasoning |
|------------|-------|----------|-----------|
| B | L1 | A | Documentation template change, no code, no observation layer |
| A | L1 | A | 문서 템플릿 보강이며 런타임/계약/검증 표면 영향 없음 |

---

### Sample 2

**Description**: Refine the red line #1 grep pattern to exclude
comment lines containing "NEVER True", eliminating FP-001.

**Affected files**: scripts/verify_constitution.py (grep pattern)
**Affected OC rules**: Red line verification procedure

| Classifier | Level | Category | Reasoning |
|------------|-------|----------|-----------|
| B | L2 | C | Touches validation surface (grep pattern for red line check). Boundary rule: default to Category C. |
| A | L2 | C | Red line 검증 표면 변경이므로 default-to-C 적용 |

---

### Sample 3

**Description**: Add a new `observation_version` string field to
the four-tier board schema with default value "1.0".

**Affected files**: app/schemas/four_tier_board_schema.py
**Affected OC rules**: Board sealed at 24 fields

| Classifier | Level | Category | Reasoning |
|------------|-------|----------|-----------|
| B | L3 | D | Board field addition. Boundary rule: default to L3. Board sealed at 24 fields = constitutional protection. |
| A | L3 | C | Board field 추가는 default-to-L3; observation/API surface 변경이므로 C (D 영역 아님) |

---

### Sample 4

**Description**: Add a pytest marker `@pytest.mark.governance` to
all 312 governance tests to enable selective test runs.

**Affected files**: tests/test_agent_governance.py, tests/test_ops_checks.py,
tests/test_market_feed.py, tests/test_dashboard.py
**Affected OC rules**: None (test organization, no assertion changes)

| Classifier | Level | Category | Reasoning |
|------------|-------|----------|-----------|
| B | L1 | B | Test organization only. No assertion relaxation. No observation layer change. Self-review sufficient. |
| A | L1 | B | 테스트 조직/운영 분류 보강이며 assertion/런타임 의미 변화 없음 |

---

### Sample 5

**Description**: Change the Celery beat schedule for `expire_signals`
from every 60 seconds to every 120 seconds to reduce testnet API load.

**Affected files**: workers/celery_app.py (beat_schedule)
**Affected OC rules**: None directly, but affects worker behavior

| Classifier | Level | Category | Reasoning |
|------------|-------|----------|-----------|
| B | L2 | B | Code change to worker configuration. Does not touch sealed observation layer. Does not add/remove board fields. Runtime behavior change but read-only path only. Requires 832/0/0 regression. |
| A | L2 | B | 운영 설정 변경이지만 sealed layer/action boundary 직접 접촉 아님 |

---

## 4. Calibration Results

Completed 2026-05-14. A submitted independent classification.

### Comparison

| # | B Level | B Cat | A Level | A Cat | Match? | Resolution |
|---|---------|-------|---------|-------|--------|------------|
| 1 | L1 | A | L1 | A | **MATCH** | — |
| 2 | L2 | C | L2 | C | **MATCH** | — |
| 3 | L3 | D | L3 | C | PARTIAL | Level match. Cat: B=D (constitutional), A=C (observation contract, not safety invariant). A's reasoning accepted — board field addition is L3 but not D unless it touches action_allowed/prediction/execution. New boundary rule added. |
| 4 | L1 | B | L1 | B | **MATCH** | — |
| 5 | L2 | B | L2 | B | **MATCH** | — |

### Score

- Matches: 4/5
- Partials: 1/5 (Level match, Category 1-step difference)
- Mismatches: 0/5

### Verdict

**PASS (4/5 match ≥ 4/5 threshold)**

Calibration debt from CR-022 is resolved. Pilot criterion #8
upgrades from CONDITIONAL PASS to unconditional **PASS**.

### #3 Resolution — New Boundary Rule

A's L3/C classification for board field addition is accepted:

- **L3** is correct: board field addition violates sealed field count
- **C** is correct: board field addition changes observation contract/API
  surface but does NOT modify safety invariants (action_allowed,
  prediction, execution/write paths). Category D is reserved for
  changes to safety invariants and constitutional red lines.

**New boundary rule**: Board field addition/removal → L3/C (not L3/D)
unless the field directly controls a safety invariant or red line.

---

## 5. Post-Calibration Actions

### If PASS (4/5+)

1. Update phase_h_pilot_closure_2026-05-08.md:
   - Criterion #8: CONDITIONAL PASS → **PASS**
   - Summary: "7/8 PASS + 1 CONDITIONAL PASS" → **"8/8 PASS"**
2. Update multi_operator_readiness_pack.md:
   - Classification consistency: "CONDITIONAL PASS" → **"PASS"**
3. Update mode1_sustained_review_2026-05-14.md:
   - Outstanding items: remove calibration debt line
4. Close CR-025 in intake registry

### If EXTEND (3/5)

1. Analyze mismatch patterns
2. Add new boundary rules
3. Schedule third calibration round (5 new samples)
4. CR-025 remains open

---

## 6. Boundary Rules Reference (Current)

| Rule | Source |
|------|--------|
| Validation surface changes → default to Category C | CR-022 (2026-05-08) |
| Board field addition/removal → default to L3 | CR-022 (2026-05-08) |
| Documentation-only → L1 / Category A | post_pilot_change_control.md |
| Test additions (no relaxation) → L1 / Category A or B | post_pilot_change_control.md |

### New Boundary Rules (CR-025, 2026-05-14)

| Rule | Source |
|------|--------|
| Board field addition/removal → L3/C (not L3/D) unless field controls safety invariant or red line | CR-025 #3 resolution |
