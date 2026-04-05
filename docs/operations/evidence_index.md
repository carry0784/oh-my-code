# Evidence Directory Index

**Created**: 2026-04-05
**Source session**: AELP v1 / Plan B / Item Q-1
**Parent plan**: `autonomous_execution_loop_plan.md` → `continuous_progress_plan_v1.md`
**Status**: INDEX — this document is a navigation map, not a content modification.
**Purpose**: Provide a grouped index of every file under `docs/operations/evidence/` so that operators can locate a specific receipt, seal, or report in seconds instead of scrolling a flat 243-entry directory.

---

## 1. Scope boundary

### 1.1 What this document IS
- A categorized index of existing evidence files
- A cross-reference between change requests (CRs), phases, and artifacts
- A navigational aid for future sessions

### 1.2 What this document is NOT
- **NOT** a modification of any evidence file content
- **NOT** a reorganization of the directory structure
- **NOT** a deletion / rename / move of any artifact
- **NOT** a seal, judgment, or approval in itself

> Evidence files under `docs/operations/evidence/` are immutable once sealed. This index only references them; it never rewrites them.

---

## 2. Counting summary

| Group | Files | Note |
|---|:---:|---|
| CR-048 (LLM runtime integration) | 66 | largest cluster, multi-stage |
| CR-046 (canonical core: SMC+WaveTrend) | 34 | Phase 1–5a |
| C-04 (Genesis Baseline) | 30 | Phase 1–10, sealed |
| Shadow (7-day / v2 observation) | 16 | includes daily checklists |
| M2 (mainnet micro-live) | 9 | baseline + repeat packages |
| CR-039 (collection stability prereq) | 8 | monitor logs + reports |
| Sprint contracts (ops tools) | 6 | 2026-03-30 batch |
| Guarded release / Mode 1 / Phase H | ~12 | operational receipts |
| Other CRs (030/034–038, 045, 047, 049, 048a) | ~12 | small clusters |
| Baselines / seals / misc | ~50 | includes exception_register, receipt_naming_convention, etc. |
| **TOTAL** | **243** | as of 2026-04-05 |

---

## 3. CR-048 — LLM runtime integration (66 files)

### 3.1 Runtime integration scope review
- `cr048_runtime_integration_scope_review_package.md`
- `cr048_staged_l3_expansion_proposal.md`

### 3.2 Stage 1 (L3 — strategy registry)
- `cr048_stage1_l3_scope_request.md`
- `cr048_stage1_l3_completion_evidence.md`

### 3.3 Stage 2 (L3 — runtime loader)
- `cr048_stage2_l3_scope_request.md`
- `cr048_stage2a_l3_scope_request.md`
- `cr048_stage2a_l3_completion_evidence.md`
- `cr048_stage2b_l3_scope_request.md`
- `cr048_stage2b_l3_completion_evidence.md`
- `cr048_stage2a_2b_boundary_delta.md`
- `cr048_stage2b_review_package.md`
- `cr048_stage2b_to_stage3_runtime_delta.md`

### 3.4 Stage 3 (L3 — boundary contracts)
- `cr048_stage3_l3_scope_request.md`
- `cr048_stage3a_l3_completion_evidence.md`
- `cr048_stage3b_boundary_contract_spec.md`
- `cr048_stage3b_boundary_inventory.md`
- `cr048_stage3b_dataprovider_capability_matrix.md`
- `cr048_stage3b_design_review_package.md`
- `cr048_stage3b_failure_mode_matrix.md`
- `cr048_stage3b_purity_guard_spec.md`
- `cr048_stage3b_test_plan.md`
- `cr048_stage3b1_l3_completion_evidence.md`
- `cr048_stage3b2_l3_completion_evidence.md`
- `cr048_stage3b2_fixture_strategy.md`
- `cr048_stage3b2_screening_input_transform_spec.md`
- `cr048_stage3b2_stub_contract.md`
- `cr048_stage3b2_stub_scope_review.md`
- `cr048_stage3b2_symbol_namespace_contract.md`
- `cr048_stage3b2_test_plan.md`

### 3.5 Stage 4 (L3 — pipeline composition)
- `cr048_stage4_scope_review_package.md`
- `cr048_stage4a_fail_closed_matrix.md`
- `cr048_stage4a_l3_completion_evidence.md`
- `cr048_stage4a_pipeline_composition_scope_spec.md`
- `cr048_stage4a_pipeline_contract.md`
- `cr048_stage4a_reuse_map.md`
- `cr048_stage4a_test_plan.md`
- `cr048_stage4b_l3_completion_evidence.md`
- `cr048_stage4b_scope_review_package.md`

### 3.6 RI-1 (shadow observation)
- `cr048_ri1_shadow_design_contract_package.md`
- `cr048_ri1_shadow_observation_evidence_package.md`
- `cr048_ri1_completion_evidence.md`
- `cr048_ri1a_threshold_alignment_remeasurement_package.md`
- `ri1_shadow_observation_results.json`
- `ri1a_threshold_alignment_results.json`

### 3.7 RI-2 (readthrough + observation)
- `cr048_ri2_reentry_review_package.md`
- `cr048_ri2a_scope_review_package.md`
- `cr048_ri2a1_readthrough_design_contract_package.md`
- `cr048_ri2a1_implementation_completion_report.md`
- `cr048_ri2a1_completion_evidence.md`
- `cr048_ri2a2_scope_review_package.md`
- `cr048_ri2a2a_observation_log_design_contract_package.md`
- `cr048_ri2a2a_implementation_completion_report.md`
- `cr048_ri2a2a_completion_evidence.md`
- `cr048_ri2a2b_scope_review_package.md`
- `cr048_ri2a2b_design_contract_package.md`
- `cr048_ri2a2b_activation_manifest.md`
- `cr048_ri2a2b_completion_evidence.md`
- `cr048_ri2b_scope_review_package.md`
- `cr048_ri2b1_design_contract_package.md`
- `cr048_ri2b1_completion_evidence.md`
- `cr048_ri2b2_scope_review_package.md`
- `cr048_ri2b2a_design_contract_package.md`
- `cr048_ri2b2a_completion_evidence.md`
- `cr048_ri2b2b_scope_review_package.md`
- `cr048_ri2b2b_scope_review_acceptance_receipt.md`
- `cr048_ri2b2b_implementation_go_receipt.md` ← **current governance chain head (A signed 2026-04-04)**

### 3.8 Misc CR-048
- `cr048_ops_verification_report.md`
- `cr048_limited_l3_model_skeleton_evidence.md`
- `cr048a_sealed_pass.md`

---

## 4. CR-046 — Canonical core (SMC pure-causal + WaveTrend) (34 files)

### 4.1 Design + canonical definition
- `cr046_canonical_core_definition.md`
- `cr046_smc_pure_causal_design.md`
- `cr046_overlay_challenger_rules.md`

### 4.2 Phase 1 — repaint audit
- `cr046_phase1_repaint_audit.md` (PASS)

### 4.3 Phase 2 — OOS / WF / CV
- `cr046_phase2_plan.md`
- `cr046_phase2_report.md`
- `cr046_phase2_results.json`

### 4.4 Phase 3 — multi-asset
- `cr046_phase3_report.md`
- `cr046_phase3_results.json`

### 4.5 Phase 4 — execution realism
- `cr046_phase4_report.md`
- `cr046_phase4_results.json`
- `cr046_phase4_pass_seal.md` (SEALED 8/8)

### 4.6 Phase 5 — deployment readiness + Phase 5a preflight
- `cr046_phase5_deployment_readiness.md`
- `cr046_deployment_readiness_table.md`
- `cr046_three_tier_judgment.md` (SOL GO / BTC guarded / ETH excluded)
- `cr046_sol_paper_rollout_plan.md` (APPROVED 2026-04-01, A)
- `cr046_sol_stage_a_review.md`
- `cr046_btc_latency_guard_checklist.md`
- `cr046_phase5a_preflight.md` ← **new (B-5, 2026-04-05, this AELP cycle)**

### 4.7 Track B (ETH research)
- `cr046_track_b_eth_research_plan.md`
- `cr046_track_b_failure_analysis.md`
- `cr046_track_b_report.md`
- `cr046_track_b_results.json`
- `cr046_track_b_sealed.md`

### 4.8 Track C (regime filter v1, FAIL)
- `cr046_track_c_regime_filter_plan.md`
- `cr046_track_c_report.md`
- `cr046_track_c_results.json`

### 4.9 Track C-v2 (realized vol etc., FAIL)
- `cr046_track_c_v2_research_plan.md`
- `cr046_track_c_v2_failure_analysis.md`
- `cr046_track_c_v2_report.md`
- `cr046_track_c_v2_results.json`
- `cr046_track_c_v2_sealed.md`

### 4.10 Misc CR-046
- `cr046_strategy_d_validation_package.md`
- `cr046_testnet_recovery_log.md`

---

## 5. C-04 Genesis Baseline (30 files)

- `c04_genesis_baseline_2026-03-26.md`
- `c04_final_completion_freeze_2026-03-26.md`
- `c04_operational_visibility_baseline_2026-03-26.md`
- `c04_phase1_approval_2026-03-26.md`
- `c04_phase1_testcode_receipt_2026-03-26.md`
- `c04_phase2_review_2026-03-26.md`
- `c04_phase3_implementation_start_approval_2026-03-26.md`
- `c04_phase3_review_2026-03-26.md`
- `c04_phase4_activation_approval_2026-03-26.md`
- `c04_phase4_activation_scope_review_2026-03-26.md`
- `c04_phase4_activation_completion_review_2026-03-26.md`
- `c04_phase5_execution_approval_2026-03-26.md`
- `c04_phase5_execution_scope_review_2026-03-26.md`
- `c04_phase5_execution_completion_review_2026-03-26.md`
- `c04_phase6_approval_2026-03-26.md`
- `c04_phase6_scope_review_2026-03-26.md`
- `c04_phase6_completion_review_2026-03-26.md`
- `c04_phase7_approval_2026-03-26.md`
- `c04_phase7_scope_review_2026-03-26.md`
- `c04_phase7_completion_review_2026-03-26.md`
- `c04_phase8_approval_2026-03-26.md`
- `c04_phase8_scope_review_2026-03-26.md`
- `c04_phase8_completion_review_2026-03-26.md`
- `c04_phase9_approval_2026-03-26.md`
- `c04_phase9_scope_review_2026-03-26.md`
- `c04_phase9_completion_review_2026-03-26.md`
- `c04_phase9plus_expansion_review_2026-03-26.md`
- `c04_phase10_consolidated_2026-03-26.md`
- `c04_step4_ui_binding_freeze_2026-03-26.md`
- `c04_step6_history_freeze_2026-03-26.md`

> C-04 sealed via `c04_final_completion_freeze_2026-03-26.md`. Do not modify any file in this group.

---

## 6. Shadow observation (16 files)

### 6.1 7-day v1
- `shadow_day0_baseline.md`
- `shadow_day0_baseline_v2.md`
- `shadow_daily_checklist.md`
- `shadow_day02_checklist.md`
- `shadow_day03_checklist.md`
- `shadow_day04_checklist.md`
- `shadow_day05_checklist.md`
- `shadow_day06_checklist.md`
- `shadow_day07_checklist.md`
- `shadow_run_template.md`
- `shadow_7day_final_verdict.md`
- `shadow_logs/` (subdirectory)

### 6.2 v2 observation
- `shadow_v2_day01_checklist.md`
- `shadow_v2_day02_checklist.md`
- `shadow_v2_day03_checklist.md`
- `shadow_v2_7day_summary.md`

---

## 7. M2 Mainnet micro-live (9 files)

- `m2_1_5_dryrun_passthrough.md`
- `m2_1_live_read_execution.md`
- `m2_2_baseline_card.md`
- `m2_2_baseline_diff_checklist.md`
- `m2_2_execution_preparation.md`
- `m2_2_post_run_review.md`
- `m2_2_repeat_readiness_card.md`
- `m2_2_repeat_review_package.md`
- `m2_2_review_package.md`

> M2-2 first mainnet micro-live FILLED, CR-033~037 SEALED (per memory: `project_m2_2_baseline.md`).

---

## 8. CR-039 (collection stability prereq) (8 files)

- `cr039_prerequisites.md`
- `cr039_prereq_a_collection_stability.md`
- `cr039_prereq_a_collection_stability_v2.md`
- `cr039_price_source_transition_note.md`
- `cr039_collection_monitor_results.json`
- `cr039_collection_monitor_24h_results.json`
- `cr039_collection_monitor_mainnet_readonly_results.json`
- `cr039_monitor_24h_stdout.log`

---

## 9. Sprint contracts (2026-03-30 batch) (6 files)

- `sprint_contract_board_obs_upgrade_2026-03-30.md`
- `sprint_contract_cleanup_policy_2026-03-30.md`
- `sprint_contract_cleanup_sim_2026-03-30.md`
- `sprint_contract_decision_board_visual_2026-03-30.md`
- `sprint_contract_operator_decision_2026-03-30.md`
- `sprint_contract_orphan_policy_2026-03-30.md`

---

## 10. Guarded release / Mode 1 / Phase H / Baselines (~50 files)

### 10.1 Guarded release
- `guarded_release_receipt_2026-04-03.md`
- `guarded_release_exit_evaluation_2026-04-04.md`
- `guarded_release_l2_exception_note_2026-04-04.md`
- `l2_opening_review_2026-04-04.md`

### 10.2 Baseline hold
- `baseline_card_2026-03-30.md`
- `baseline_hold_release_evaluation_2026-04-03.md`
- `baseline_hold_strengthening_completion_2026-04-03.md`

### 10.3 Mode 1 / Mode 2 / Pilot
- `mode1_sustained_review_2026-05-14.md`
- `mode2_transition_readiness_assessment.md`
- `phase_h_pilot_closure_2026-05-08.md`
- `controlled_expansion_p1_closure_2026-05-08.md`
- `classification_calibration_recheck_2026-05-14.md`
- `multi_operator_onboarding_2026-05-08.md`
- `warm_start_verification_2026-05-08.md`
- `runner_artifact_normalization_2026-05-08.md`

### 10.4 Seals (2026-03-30)
- `agent_boundary_seal_2026-03-30.md`
- `execution_boundary_seal_2026-03-30.md`
- `execution_boundary_replication_report_2026-03-30.md`
- `four_tier_seal_completion_report_2026-03-30.md`
- `okx_removal_seal_2026-03-30.md`
- `order_executor_design_2026-03-30.md`
- `skill_loop_boundary_seal_2026-03-30.md`
- `skill_loop_seal_receipt_2026-03-30.md`
- `submit_boundary_seal_2026-03-30.md`

### 10.5 Phase seals (2026-03-31)
- `phase_a_seal_2026-03-31.md`
- `phase_c_interim_seal_2026-03-31.md`
- `phase_f_validation_report_2026-03-31.md`

---

## 11. Controlled restart / runtime consistency (2026-03-25 batch)

- `controlled_restart_execution_2026-03-25.md`
- `controlled_restart_review_2026-03-25.md`
- `runtime_consistency_audit_2026-03-25.md`
- `s03_stabilization_2026-03-25.md`
- `z02_daily_2026-03-25.md`
- `z02_runtime_2026-03-25.md`
- `tab3_smoke_2026-03-25.md`
- `tab3_safe_cards_receipt_2026-03-26.md`
- `b14a_receipt_2026-03-25.md`
- `b14b_receipt_2026-03-25.md`
- `b16_receipt_2026-03-25.md`
- `b17_receipt_2026-03-25.md`
- `b18_receipt_2026-03-25.md`
- `b19_receipt_2026-03-25.md`
- `b20_receipt_2026-03-25.md`
- `b21_receipt_2026-03-25.md`
- `b22_receipt_2026-03-26.md`
- `ki1_b15_receipt_2026-03-25.md`
- `ki2_receipt_2026-03-25.md`

---

## 12. Other CRs (small clusters)

| CR | Files |
|---|---|
| CR-030 | `cr030_orphan_aggregation_design_review.md` |
| CR-034 | `cr034_dashboard_db_timeout_investigation.md` |
| CR-035 | `cr035_phase_b_prevention.md`, `cr035_v2_timeout_investigation.md` |
| CR-036 | `cr036_execution_path_contract_fix.md` |
| CR-037 | `cr037_params_keyword_contract_fix.md` |
| CR-038 | `cr038_phase1_checkpoint.md` |
| CR-045 | `cr045_shadow_redesign_package.md` |
| CR-047 | `cr047_1h_cg2b_reverification_package.md`, `cr047_7day_summary.md`, `cr047_pass_seal.md` |
| CR-049 | `cr049_phase3_design_card.md`, `cr049_sealed_pass.md` |

---

## 13. Conventions, registers, and reference docs

| File | Role |
|---|---|
| `receipt_naming_convention.md` | Canonical receipt naming rules (3-pattern) |
| `exception_register.md` | Active exception registry |
| `EX-002_runtime_strategy_loader_casing.md` | Specific exception detail |
| `operator_authorization_checklist.md` | Operator authorization flow |
| `operational_readiness_review.md` | Operational readiness snapshot |
| `go_hold_transition_criteria.md` | GO ↔ HOLD transition rule |
| `r04_decision_memo.md` | Decision memo R-04 |
| `obs_restart_stability_check.md` | Observation restart stability check |
| `killswitch_rehearsal_evidence.md` | Kill-switch drill evidence |
| `indicator_backtest_results.json` | Indicator backtest data |
| `cg2a_pass_seal.md` | CG-2A sealed pass marker |
| `test_orderdep_001.md` | Order dependency test |

---

## 14. How to use this index

1. **Search by CR number** → jump to the matching section
2. **Search by artifact type** (receipt / scope review / completion evidence / seal) → use section sub-headers
3. **Search by date** → dated files have `_YYYY-MM-DD` suffix; grep the filename list
4. **Cross-reference** with `CLAUDE.md` §CR-046 for the current operational state
5. **For the live governance chain head**, always check `cr048_ri2b2b_implementation_go_receipt.md` first

---

## 15. What this PR does / does not do

### Does ✅
- Enumerate 243 evidence files in grouped form
- Provide section-level navigation for CR-048, CR-046, C-04, shadow, M2, CR-039, sprint contracts, and seals
- Reference the latest governance chain head
- Tag the newly added `cr046_phase5a_preflight.md` from the same AELP cycle

### Does NOT ❌
- Modify any evidence file
- Rename, move, or delete any artifact
- Create new seals or receipts
- Alter directory structure
- Touch any source code

---

## 16. References

| 문서 | 역할 |
|---|---|
| `docs/operations/autonomous_execution_loop_plan.md` | AELP parent (Plan B scope) |
| `docs/operations/continuous_progress_plan_v1.md` | v1 plan defining Track B quality items |
| `docs/operations/evidence/receipt_naming_convention.md` | Canonical naming spec |
| `CLAUDE.md` §CR-046 | Current operational state |

---

## Footer

```
Evidence Directory Index
Plan ref         : AELP v1 / Plan B / Item Q-1
Created          : 2026-04-05
Files indexed    : 243
Groups           : 14 (CR-048, CR-046, C-04, Shadow, M2, CR-039, Sprint,
                       Guarded release, Other CRs, Controlled restart batch,
                       Conventions, Misc, Seals 2026-03-30, Seals 2026-03-31)
Content changes  : 0 (index only, no artifact modified)
Track A impact   : none
```
