# CR-046 Phase 2: OOS / Walk-Forward Validation Plan

Date: 2026-04-01
Status: **APPROVED (A Decision)**
Prerequisite: Phase 1 PASS (pure-causal SMC validated, 0 signal divergence)
Canonical SMC: **Version B (pure-causal) ONLY**

---

## 1. SMC Version Policy

| Version | Role | Usage |
|---------|------|-------|
| **Version B (pure-causal)** | **Canonical evaluation path** | All Phase 2 judgments, OOS metrics, final verdict |
| Version A (delay-compensated) | Comparative reference only | Divergence monitoring, regression check. **NOT for operational judgment** |

| Property | Version A | Version B |
|----------|-----------|-----------|
| Performance | Identical (0 divergence on current dataset) | Identical |
| Structural safety | Low (future bars in classification) | **High (past-only)** |
| Live trading equivalence | Uncertain | **Guaranteed** |

> **Why B is canonical**: Even though Version A produced identical signals on this dataset,
> structural safety matters independently of current performance. Parameter changes, asset
> changes, or timeframe changes could reactivate the future-data dependency in Version A.

---

## 2. Phase 2 Tests

### 2.1 Temporal OOS Split

```
Train: Oct 2025 - Jan 2026 (4 months, ~2880 bars)
Test:  Feb 2026 - Apr 2026 (2 months, ~1440 bars)

Selection + weights from train period only.
Strategy D composition evaluated on test period.
```

| Metric | Pass Criteria |
|--------|---------------|
| OOS Sharpe | > 0.5 |
| OOS Return | > 0% |
| OOS PF | > 1.0 |

### 2.2 Walk-Forward (3 windows)

```
Window 1: Train Oct-Dec 2025, Test Jan 2026
Window 2: Train Nov 2025-Jan 2026, Test Feb 2026
Window 3: Train Dec 2025-Feb 2026, Test Mar 2026
```

| Metric | Pass Criteria |
|--------|---------------|
| Mean OOS Sharpe | > 0.3 |
| OOS Sharpe std | < 2.0 (stability) |

### 2.3 Purged Cross-Validation (5-fold)

```
5-fold purged CV with 48h (48 bars) embargo between folds.
In each fold: compute Strategy D metrics.
```

| Metric | Pass Criteria |
|--------|---------------|
| Mean CV Sharpe | > 0.3 |
| CV Sharpe variance | Document (no hard threshold) |

### 2.4 Selection Stability

```
In each fold: re-rank all 6 indicators by Sharpe.
Check if Top 3 remains {SMC, WaveTrend, Supertrend}.
```

| Metric | Pass Criteria |
|--------|---------------|
| Top 3 stable | >= 3/5 folds |

---

## 3. Acceptance Criteria (Phase 2)

| AC | Check | Threshold | SMC Version |
|----|-------|-----------|-------------|
| AC-3 | OOS Sharpe (temporal) | > 0.5 | **Version B** |
| AC-4 | Walk-forward mean Sharpe | > 0.3 | **Version B** |
| AC-5 | Selection stability | >= 3/5 folds | **Version B** |

---

## 4. Prohibited Actions

| Prohibition | Compliance |
|-------------|------------|
| Use Version A for operational judgment | FORBIDDEN |
| Lower min_trades threshold | FORBIDDEN |
| Modify Strategy D parameters mid-test | FORBIDDEN |
| Cherry-pick favorable OOS windows | FORBIDDEN |
| Skip purged CV embargo | FORBIDDEN |

---

## 5. Deliverables

| # | Deliverable | Format |
|---|-------------|--------|
| 1 | OOS temporal split results | Table: Sharpe, Return, PF, WinR, MDD |
| 2 | Walk-forward 3-window results | Table per window + mean |
| 3 | Purged CV results | Table: fold metrics + mean/std |
| 4 | Selection stability matrix | 5x6 indicator rank matrix |
| 5 | Version A vs B comparison (all tests) | Side-by-side for reference |
| 6 | Phase 2 verdict | PASS / FAIL / CONDITIONAL with evidence |

---

## Signature

```
CR-046 Phase 2 Plan
Canonical SMC: Version B (pure-causal)
Version A: comparative reference only
Approved by: A (Decision Authority)
Date: 2026-04-01
```
