"""SOL S-1 V-3R2 Shadow Drift Verification Run Script (IMPL-2 fork).

Purpose
-------
This file is a V-3R2 runner fork of `scripts/sol_s1_v3_shadow_run.py`. It
exists solely to enforce the RULE-EXEC-3 triple-lock pre-flight guard
required by the SEALED execution-mode protocol and the SEALED v3r2 run-GO
receipt. It is NOT a new shadow simulation, NOT a new verification strategy,
and NOT a rewrite of the V-3R1 runner.

The original frozen V-3R1 runner MUST remain byte-identical on disk:

    original_path   = scripts/sol_s1_v3_shadow_run.py
    original_sha256 = 94110d249fb8d6b371dbcfa1b922b45018eb567ac23c9d0afa82e184163c3f4a

This fork does NOT mutate the original, does NOT shadow its exports, and
does NOT duplicate its simulation logic. On guard pass, this fork delegates
to the frozen runner's `main()` via in-process Python module import — NOT
via subprocess, NOT via shell wrapper, NOT via file copy.

Authority Chain (SEALED, read-only at runtime)
----------------------------------------------
1. docs/operations/evidence/sol_s1_v3_execution_mode_protocol.md
     - Slot 1 RULE-OBS-1           (execution_mode declaration mandate)
     - Slot 2 RULE-STATE-2         (run GO issuance precondition)
     - Slot 3 RULE-EXEC-3          (dual env var / triple-lock mandate)
     - Slot 4 RULE-CONSTITUTIONAL-4 (runner authority boundary)
2. docs/operations/evidence/sol_s1_v3r2_run_go_receipt.md
     - Triple-lock precondition for `legal_run`
     - Companion to the SEALED v3r1 run GO receipt (v3r1 unchanged)
3. docs/operations/evidence/sol_s1_v3_design_addendum_runner_authority.md
     - Runner scope: transparent relay only; no interpretation of authority

Triple-Lock (RULE-EXEC-3)
-------------------------
Lock 1:  `--run` must be present in argv.
Lock 2:  env SOL_S1_V3_RUN_AUTHORIZED must equal "v3_run_go_granted".
Lock 3:  env SOL_S1_V3_EXECUTION_MODE must be either "realtime_shadow"
         or "historical_replay". Empty, missing, or "ambiguous" is rejected.

All three locks are AND-combined. Any single failure aborts with a
lock-specific non-zero exit code BEFORE any shadow simulation logic runs
and BEFORE the frozen runner is imported.

Authority Boundary (RULE-CONSTITUTIONAL-4)
------------------------------------------
This runner is a transparent relay. It does NOT:
  - grant V-4 unlock,
  - release Chain A binding,
  - close or DEFER-release the parent chain,
  - issue run authorization,
  - set, export, or mutate any environment variable,
  - interpret or re-derive governance state.

Constraints Enforced by This Fork
---------------------------------
  - The original `sol_s1_v3_shadow_run.py` MUST remain unchanged.
  - No test writing, no test execution, no run authorization grant.
  - Triple-lock failure paths print diagnostics and return non-zero codes
    that distinguish which lock failed.
  - Triple-lock pass paths delegate to the frozen runner's own `main()`
    via in-process import. The frozen runner's OWN single-env guard still
    runs on Lock 2's value, providing redundant (but not conflicting)
    defense-in-depth.
  - This file imports the frozen runner lazily (inside the pass path) so
    that merely importing this fork module does NOT unconditionally pull
    in the frozen runner.

Fork Provenance
---------------
    chain_id                : grp_chain_impl_2_runner_script_fork_chain
    created_under           : raw explicit single next GO
    seal_operation_on_target: none (target body unchanged, pre=post sha256)
    max_new_files           : 1 (this file)
    existing_file_mutation  : 0
    auto_advance            : forbidden
"""

from __future__ import annotations

import os
import sys
from typing import Final, Mapping

# ---------------------------------------------------------------------------
# Authority Source References (string constants only — no runtime file I/O)
# ---------------------------------------------------------------------------

AUTHORITY_SOURCE_EXECUTION_MODE_PROTOCOL: Final[str] = (
    "docs/operations/evidence/sol_s1_v3_execution_mode_protocol.md"
)
AUTHORITY_SOURCE_V3R2_RUN_GO_RECEIPT: Final[str] = (
    "docs/operations/evidence/sol_s1_v3r2_run_go_receipt.md"
)
AUTHORITY_SOURCE_DESIGN_ADDENDUM_RUNNER: Final[str] = (
    "docs/operations/evidence/sol_s1_v3_design_addendum_runner_authority.md"
)

# ---------------------------------------------------------------------------
# Fork Provenance (audit trail constants)
# ---------------------------------------------------------------------------

FORK_OF_ORIGINAL_PATH: Final[str] = "scripts/sol_s1_v3_shadow_run.py"
FORK_OF_ORIGINAL_SHA256: Final[str] = (
    "94110d249fb8d6b371dbcfa1b922b45018eb567ac23c9d0afa82e184163c3f4a"
)
FORK_CHAIN_ID: Final[str] = "grp_chain_impl_2_runner_script_fork_chain"
FORK_DESIGN_VERSION_LABEL: Final[str] = "V-3R2"

# ---------------------------------------------------------------------------
# Triple-Lock Constants (RULE-EXEC-3, Slot 3 of execution-mode protocol)
# ---------------------------------------------------------------------------

CLI_RUN_FLAG: Final[str] = "--run"

RUN_AUTHORIZATION_ENV_KEY: Final[str] = "SOL_S1_V3_RUN_AUTHORIZED"
RUN_AUTHORIZATION_EXPECTED: Final[str] = "v3_run_go_granted"

EXECUTION_MODE_ENV_KEY: Final[str] = "SOL_S1_V3_EXECUTION_MODE"
EXECUTION_MODE_VALUE_REALTIME_SHADOW: Final[str] = "realtime_shadow"
EXECUTION_MODE_VALUE_HISTORICAL_REPLAY: Final[str] = "historical_replay"
EXECUTION_MODE_ALLOWED_VALUES: Final[frozenset[str]] = frozenset(
    {
        EXECUTION_MODE_VALUE_REALTIME_SHADOW,
        EXECUTION_MODE_VALUE_HISTORICAL_REPLAY,
    }
)

# ---------------------------------------------------------------------------
# Exit Codes (lock-specific, audit-friendly)
# ---------------------------------------------------------------------------

EXIT_OK: Final[int] = 0
EXIT_LOCK_1_FAILED: Final[int] = 11  # CLI --run flag missing
EXIT_LOCK_2_FAILED: Final[int] = 12  # RUN_AUTHORIZED missing / wrong value
EXIT_LOCK_3_FAILED: Final[int] = 13  # EXECUTION_MODE missing / invalid
EXIT_DELEGATION_IMPORT_FAILED: Final[int] = 14  # frozen runner import failed


# ---------------------------------------------------------------------------
# Pre-Flight Triple-Lock Guard
# ---------------------------------------------------------------------------


def triple_lock_pre_flight_guard(
    argv: list[str],
    env: Mapping[str, str],
) -> int:
    """Bounded Slot 3 (RULE-EXEC-3) triple-lock pre-flight guard.

    Pure inspection. This function:
      - does NOT mutate argv,
      - does NOT mutate the environment,
      - does NOT grant any authorization,
      - does NOT import the frozen runner,
      - does NOT execute any simulation logic,
      - does NOT perform file I/O.

    Returns EXIT_OK (0) iff all three locks pass. Otherwise returns a
    lock-specific non-zero exit code and prints a diagnostic describing
    which lock failed and what the expected value is.

    Accepting argv and env as parameters (rather than reading sys.argv /
    os.environ directly inside) keeps this function pure and inspectable
    by future validation chains without running a live shadow simulation.
    """
    # --- Lock 1: CLI --run flag must be present ---
    if CLI_RUN_FLAG not in argv:
        print(
            f"[V-3R2][LOCK-1][ABORT] CLI flag '{CLI_RUN_FLAG}' is required.",
            flush=True,
        )
        print(
            f"[V-3R2][LOCK-1][ABORT] authority: {AUTHORITY_SOURCE_EXECUTION_MODE_PROTOCOL}",
            flush=True,
        )
        return EXIT_LOCK_1_FAILED

    # --- Lock 2: SOL_S1_V3_RUN_AUTHORIZED env var ---
    run_authorized_value = env.get(RUN_AUTHORIZATION_ENV_KEY, "")
    if run_authorized_value != RUN_AUTHORIZATION_EXPECTED:
        print(
            f"[V-3R2][LOCK-2][ABORT] env var {RUN_AUTHORIZATION_ENV_KEY} "
            f"is not set to the expected value.",
            flush=True,
        )
        print(
            f"[V-3R2][LOCK-2][ABORT] expected: '{RUN_AUTHORIZATION_EXPECTED}'",
            flush=True,
        )
        print(
            f"[V-3R2][LOCK-2][ABORT] this fork does NOT set, export, or grant "
            f"{RUN_AUTHORIZATION_ENV_KEY} itself.",
            flush=True,
        )
        print(
            f"[V-3R2][LOCK-2][ABORT] authority: {AUTHORITY_SOURCE_V3R2_RUN_GO_RECEIPT}",
            flush=True,
        )
        return EXIT_LOCK_2_FAILED

    # --- Lock 3: SOL_S1_V3_EXECUTION_MODE env var (new Slot 3 requirement) ---
    declared_mode_raw = env.get(EXECUTION_MODE_ENV_KEY, "")
    declared_mode = declared_mode_raw.strip()
    if declared_mode not in EXECUTION_MODE_ALLOWED_VALUES:
        print(
            f"[V-3R2][LOCK-3][ABORT] env var {EXECUTION_MODE_ENV_KEY} is "
            f"missing or has an invalid value.",
            flush=True,
        )
        print(
            f"[V-3R2][LOCK-3][ABORT] received: '{declared_mode}'",
            flush=True,
        )
        print(
            f"[V-3R2][LOCK-3][ABORT] allowed: {sorted(EXECUTION_MODE_ALLOWED_VALUES)}",
            flush=True,
        )
        print(
            f"[V-3R2][LOCK-3][ABORT] RULE-EXEC-3 requires an explicit "
            f"declared execution_mode BEFORE any shadow run is permitted. "
            f"'ambiguous' is NOT accepted as a declaration.",
            flush=True,
        )
        print(
            f"[V-3R2][LOCK-3][ABORT] authority: {AUTHORITY_SOURCE_EXECUTION_MODE_PROTOCOL}",
            flush=True,
        )
        return EXIT_LOCK_3_FAILED

    # --- All three locks passed ---
    print(
        f"[V-3R2][LOCK-OK] triple-lock pre-flight guard PASSED "
        f"({CLI_RUN_FLAG}=present, "
        f"{RUN_AUTHORIZATION_ENV_KEY}=<set>, "
        f"{EXECUTION_MODE_ENV_KEY}='{declared_mode}').",
        flush=True,
    )
    print(
        f"[V-3R2][LOCK-OK] authority chain: "
        f"{AUTHORITY_SOURCE_EXECUTION_MODE_PROTOCOL} + "
        f"{AUTHORITY_SOURCE_V3R2_RUN_GO_RECEIPT}",
        flush=True,
    )
    return EXIT_OK


# ---------------------------------------------------------------------------
# Fork Entry Point
# ---------------------------------------------------------------------------


def main() -> int:
    """V-3R2 fork entry point: triple-lock → delegate to frozen V-3R1 main.

    Step 1: Run the Slot 3 triple-lock pre-flight guard against the current
            sys.argv and os.environ.
    Step 2: If any lock fails, return the lock-specific exit code. The
            frozen runner is NOT imported or invoked in this path.
    Step 3: If all three locks pass, import the frozen V-3R1 runner module
            in-process (NOT subprocess) and delegate to its `main()`.

    Note: After this fork's Lock 2 passes, the frozen runner's OWN internal
    single-env guard (at the `RUN_AUTHORIZED` check inside `main_async`)
    also runs. Both guards consult the same env var for the same expected
    value, so the frozen runner's internal guard is redundant-but-not-
    conflicting in this code path. That redundancy is intentional: it
    matches the 'additive, body-unchanged' discipline of the external-
    bounded seal of the v3r2 run-GO receipt.
    """
    guard_result = triple_lock_pre_flight_guard(sys.argv, os.environ)
    if guard_result != EXIT_OK:
        return guard_result

    # --- Delegation to frozen V-3R1 runner (in-process, not subprocess) ---
    try:
        # Lazy import: only performed after all three locks pass, so that
        # merely importing this fork module (for e.g. future pure guard
        # inspection) does NOT unconditionally pull in the frozen runner.
        fork_dir = os.path.dirname(os.path.abspath(__file__))
        if fork_dir not in sys.path:
            sys.path.insert(0, fork_dir)
        import sol_s1_v3_shadow_run as v3r1_frozen  # type: ignore
    except Exception as exc:
        print(
            f"[V-3R2][DELEGATION][ABORT] unable to import frozen V-3R1 "
            f"runner from '{FORK_OF_ORIGINAL_PATH}': {exc!r}",
            flush=True,
        )
        return EXIT_DELEGATION_IMPORT_FAILED

    print(
        f"[V-3R2][DELEGATION] triple-lock passed — delegating to frozen "
        f"V-3R1 runner main() in-process.",
        flush=True,
    )
    print(
        f"[V-3R2][DELEGATION] frozen_sha256={FORK_OF_ORIGINAL_SHA256}",
        flush=True,
    )
    return v3r1_frozen.main()


if __name__ == "__main__":
    sys.exit(main())
