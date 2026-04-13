"""Bounded unit tests for the V-3R2 runner fork triple-lock pre-flight guard.

Purpose
-------
Verify the *pure* `triple_lock_pre_flight_guard(argv, env)` function of
`scripts/sol_s1_v3r2_shadow_run.py` using only synthetic argv/env inputs.

Chain provenance
----------------
    chain_id          : grp_chain_impl_3_test_writing_chain
    target_under_test : pure triple_lock_pre_flight_guard(argv, env)
    allowed_scope     : guard behavior + module constants only
    forbidden_scope   : shadow simulation execution, frozen runner import at
                        test time, os.environ / sys.argv mutation, env
                        activation, run authorization grant, execution mode
                        activation, VAL-1 / GOV / Ratification auto-open

Discipline
----------
- Tests pass synthetic `argv` and `env` dicts directly into the guard.
- Tests NEVER mutate `os.environ` or `sys.argv`.
- Tests NEVER import `sol_s1_v3_shadow_run` (the frozen V-3R1 runner).
- Tests NEVER call the fork's `main()` (which would trigger the frozen
  runner import on the guard-pass path).
- Tests load the fork module via `importlib.util.spec_from_file_location`,
  which executes the fork's module body only. The fork's module body
  contains constants and function definitions — it does NOT import the
  frozen runner (that import is lazy inside `main()`).

Scope boundary statement
------------------------
This test file is CREATED under the IMPL-3 bounded chain. It is NOT
EXECUTED by IMPL-3. IMPL-3 forbids pytest/unittest execution. Any test
runner invocation (e.g. `pytest tests/scripts/...`) is a SEPARATE chain
(e.g. VAL-1) and is outside the scope of IMPL-3.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from types import ModuleType


# ---------------------------------------------------------------------------
# Fork module loader — bounded, does NOT import the frozen V-3R1 runner
# ---------------------------------------------------------------------------


REPO_ROOT = Path(__file__).resolve().parents[2]
FORK_PATH = REPO_ROOT / "scripts" / "sol_s1_v3r2_shadow_run.py"
FROZEN_PATH = REPO_ROOT / "scripts" / "sol_s1_v3_shadow_run.py"

EXPECTED_FROZEN_SHA256 = (
    "94110d249fb8d6b371dbcfa1b922b45018eb567ac23c9d0afa82e184163c3f4a"
)


def _load_fork_module() -> ModuleType:
    """Load the V-3R2 fork module via importlib.

    Executes the fork's module body only (constants + function definitions).
    Does NOT trigger the fork's `main()` — the fork's import of the frozen
    V-3R1 runner is lazy, inside `main()`, after all three locks pass.
    Therefore, loading the fork module here does NOT import the frozen
    runner and does NOT place `sol_s1_v3_shadow_run` in `sys.modules`.

    Uses a test-private module name to avoid conflicts with any other test
    that may independently load the fork.
    """
    spec = importlib.util.spec_from_file_location(
        "sol_s1_v3r2_shadow_run_testsubject", str(FORK_PATH)
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to build module spec for {FORK_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Loaded once at test-module import time. Test-support operation only.
_FORK = _load_fork_module()


# ---------------------------------------------------------------------------
# Lock 1 — CLI --run flag
# ---------------------------------------------------------------------------


class TestLock1CliRunFlag(unittest.TestCase):
    """Lock 1: CLI `--run` flag must be present in argv."""

    def test_empty_argv_rejected(self) -> None:
        result = _FORK.triple_lock_pre_flight_guard([], {})
        self.assertEqual(result, _FORK.EXIT_LOCK_1_FAILED)

    def test_argv_without_run_flag_rejected(self) -> None:
        result = _FORK.triple_lock_pre_flight_guard(
            ["prog", "--other"], {}
        )
        self.assertEqual(result, _FORK.EXIT_LOCK_1_FAILED)

    def test_run_flag_alone_then_lock2_fires(self) -> None:
        # With --run present but no env vars, Lock 1 passes and Lock 2 fires.
        result = _FORK.triple_lock_pre_flight_guard(["prog", "--run"], {})
        self.assertEqual(result, _FORK.EXIT_LOCK_2_FAILED)

    def test_run_flag_constant_literal(self) -> None:
        self.assertEqual(_FORK.CLI_RUN_FLAG, "--run")


# ---------------------------------------------------------------------------
# Lock 2 — SOL_S1_V3_RUN_AUTHORIZED env var
# ---------------------------------------------------------------------------


class TestLock2RunAuthorizedEnvVar(unittest.TestCase):
    """Lock 2: env `SOL_S1_V3_RUN_AUTHORIZED` must equal `v3_run_go_granted`."""

    def test_missing_env_rejected(self) -> None:
        result = _FORK.triple_lock_pre_flight_guard(["prog", "--run"], {})
        self.assertEqual(result, _FORK.EXIT_LOCK_2_FAILED)

    def test_empty_env_rejected(self) -> None:
        result = _FORK.triple_lock_pre_flight_guard(
            ["prog", "--run"],
            {"SOL_S1_V3_RUN_AUTHORIZED": ""},
        )
        self.assertEqual(result, _FORK.EXIT_LOCK_2_FAILED)

    def test_wrong_value_rejected(self) -> None:
        result = _FORK.triple_lock_pre_flight_guard(
            ["prog", "--run"],
            {"SOL_S1_V3_RUN_AUTHORIZED": "some_other_value"},
        )
        self.assertEqual(result, _FORK.EXIT_LOCK_2_FAILED)

    def test_case_sensitive_rejected(self) -> None:
        # "V3_RUN_GO_GRANTED" uppercase must NOT be accepted.
        result = _FORK.triple_lock_pre_flight_guard(
            ["prog", "--run"],
            {"SOL_S1_V3_RUN_AUTHORIZED": "V3_RUN_GO_GRANTED"},
        )
        self.assertEqual(result, _FORK.EXIT_LOCK_2_FAILED)

    def test_correct_value_then_lock3_fires(self) -> None:
        result = _FORK.triple_lock_pre_flight_guard(
            ["prog", "--run"],
            {"SOL_S1_V3_RUN_AUTHORIZED": "v3_run_go_granted"},
        )
        self.assertEqual(result, _FORK.EXIT_LOCK_3_FAILED)

    def test_env_key_constant(self) -> None:
        self.assertEqual(
            _FORK.RUN_AUTHORIZATION_ENV_KEY, "SOL_S1_V3_RUN_AUTHORIZED"
        )

    def test_expected_value_constant(self) -> None:
        self.assertEqual(
            _FORK.RUN_AUTHORIZATION_EXPECTED, "v3_run_go_granted"
        )


# ---------------------------------------------------------------------------
# Lock 3 — SOL_S1_V3_EXECUTION_MODE env var
# ---------------------------------------------------------------------------


class TestLock3ExecutionModeEnvVar(unittest.TestCase):
    """Lock 3: env `SOL_S1_V3_EXECUTION_MODE` must be a valid declared value.

    Valid = {"realtime_shadow", "historical_replay"}.
    Missing, empty, whitespace-only, "ambiguous", and any other string must
    be rejected with EXIT_LOCK_3_FAILED.
    """

    _base_env = {
        "SOL_S1_V3_RUN_AUTHORIZED": "v3_run_go_granted",
    }

    def _env(self, mode_value):
        env = dict(self._base_env)
        if mode_value is not None:
            env["SOL_S1_V3_EXECUTION_MODE"] = mode_value
        return env

    def test_missing_rejected(self) -> None:
        result = _FORK.triple_lock_pre_flight_guard(
            ["prog", "--run"], self._env(None)
        )
        self.assertEqual(result, _FORK.EXIT_LOCK_3_FAILED)

    def test_empty_rejected(self) -> None:
        result = _FORK.triple_lock_pre_flight_guard(
            ["prog", "--run"], self._env("")
        )
        self.assertEqual(result, _FORK.EXIT_LOCK_3_FAILED)

    def test_whitespace_only_rejected(self) -> None:
        result = _FORK.triple_lock_pre_flight_guard(
            ["prog", "--run"], self._env("   ")
        )
        self.assertEqual(result, _FORK.EXIT_LOCK_3_FAILED)

    def test_ambiguous_rejected(self) -> None:
        # 'ambiguous' is an internal classification label, NOT a valid
        # declared execution_mode. Slot 3 explicitly rejects it.
        result = _FORK.triple_lock_pre_flight_guard(
            ["prog", "--run"], self._env("ambiguous")
        )
        self.assertEqual(result, _FORK.EXIT_LOCK_3_FAILED)

    def test_arbitrary_string_rejected(self) -> None:
        result = _FORK.triple_lock_pre_flight_guard(
            ["prog", "--run"], self._env("FAKE_VALUE")
        )
        self.assertEqual(result, _FORK.EXIT_LOCK_3_FAILED)

    def test_case_sensitive_rejected(self) -> None:
        # Upper-case variant must NOT be accepted.
        result = _FORK.triple_lock_pre_flight_guard(
            ["prog", "--run"], self._env("REALTIME_SHADOW")
        )
        self.assertEqual(result, _FORK.EXIT_LOCK_3_FAILED)

    def test_realtime_shadow_accepted(self) -> None:
        result = _FORK.triple_lock_pre_flight_guard(
            ["prog", "--run"], self._env("realtime_shadow")
        )
        self.assertEqual(result, _FORK.EXIT_OK)

    def test_historical_replay_accepted(self) -> None:
        result = _FORK.triple_lock_pre_flight_guard(
            ["prog", "--run"], self._env("historical_replay")
        )
        self.assertEqual(result, _FORK.EXIT_OK)

    def test_surrounding_whitespace_stripped_accepted(self) -> None:
        # The guard strips the value. Leading/trailing whitespace around a
        # valid value should still pass.
        result = _FORK.triple_lock_pre_flight_guard(
            ["prog", "--run"], self._env("  realtime_shadow  ")
        )
        self.assertEqual(result, _FORK.EXIT_OK)

    def test_env_key_constant(self) -> None:
        self.assertEqual(
            _FORK.EXECUTION_MODE_ENV_KEY, "SOL_S1_V3_EXECUTION_MODE"
        )

    def test_allowed_values_frozenset(self) -> None:
        self.assertEqual(
            _FORK.EXECUTION_MODE_ALLOWED_VALUES,
            frozenset({"realtime_shadow", "historical_replay"}),
        )
        self.assertIsInstance(
            _FORK.EXECUTION_MODE_ALLOWED_VALUES, frozenset
        )

    def test_realtime_shadow_value_constant(self) -> None:
        self.assertEqual(
            _FORK.EXECUTION_MODE_VALUE_REALTIME_SHADOW, "realtime_shadow"
        )

    def test_historical_replay_value_constant(self) -> None:
        self.assertEqual(
            _FORK.EXECUTION_MODE_VALUE_HISTORICAL_REPLAY, "historical_replay"
        )


# ---------------------------------------------------------------------------
# AND combination — any single failure blocks
# ---------------------------------------------------------------------------


class TestTripleLockAndCombination(unittest.TestCase):
    """Any one of the three locks failing must block the guard."""

    _good_argv = ["prog", "--run"]
    _good_env = {
        "SOL_S1_V3_RUN_AUTHORIZED": "v3_run_go_granted",
        "SOL_S1_V3_EXECUTION_MODE": "historical_replay",
    }

    def test_all_three_locks_satisfied(self) -> None:
        result = _FORK.triple_lock_pre_flight_guard(
            self._good_argv, self._good_env
        )
        self.assertEqual(result, _FORK.EXIT_OK)

    def test_lock1_failure_alone(self) -> None:
        # --run missing, env fully valid — should still fail on Lock 1.
        result = _FORK.triple_lock_pre_flight_guard(
            ["prog"], self._good_env
        )
        self.assertEqual(result, _FORK.EXIT_LOCK_1_FAILED)

    def test_lock2_failure_alone(self) -> None:
        env = dict(self._good_env)
        env.pop("SOL_S1_V3_RUN_AUTHORIZED")
        result = _FORK.triple_lock_pre_flight_guard(self._good_argv, env)
        self.assertEqual(result, _FORK.EXIT_LOCK_2_FAILED)

    def test_lock3_failure_alone(self) -> None:
        env = dict(self._good_env)
        env.pop("SOL_S1_V3_EXECUTION_MODE")
        result = _FORK.triple_lock_pre_flight_guard(self._good_argv, env)
        self.assertEqual(result, _FORK.EXIT_LOCK_3_FAILED)

    def test_short_circuit_lock1_reported_first(self) -> None:
        # If --run is missing, guard reports LOCK-1 regardless of env state.
        result = _FORK.triple_lock_pre_flight_guard(["prog"], {})
        self.assertEqual(result, _FORK.EXIT_LOCK_1_FAILED)

    def test_short_circuit_lock2_reported_before_lock3(self) -> None:
        # Even with a valid mode env, if RUN_AUTHORIZED is missing,
        # LOCK-2 fires first (Lock 2 evaluated before Lock 3).
        result = _FORK.triple_lock_pre_flight_guard(
            ["prog", "--run"],
            {"SOL_S1_V3_EXECUTION_MODE": "historical_replay"},
        )
        self.assertEqual(result, _FORK.EXIT_LOCK_2_FAILED)


# ---------------------------------------------------------------------------
# Exit code mapping
# ---------------------------------------------------------------------------


class TestExitCodeConstants(unittest.TestCase):
    """Exit codes must be distinct, stable, and audit-friendly."""

    def test_exit_ok(self) -> None:
        self.assertEqual(_FORK.EXIT_OK, 0)

    def test_exit_lock_1_failed(self) -> None:
        self.assertEqual(_FORK.EXIT_LOCK_1_FAILED, 11)

    def test_exit_lock_2_failed(self) -> None:
        self.assertEqual(_FORK.EXIT_LOCK_2_FAILED, 12)

    def test_exit_lock_3_failed(self) -> None:
        self.assertEqual(_FORK.EXIT_LOCK_3_FAILED, 13)

    def test_exit_delegation_import_failed(self) -> None:
        self.assertEqual(_FORK.EXIT_DELEGATION_IMPORT_FAILED, 14)

    def test_all_exit_codes_distinct(self) -> None:
        codes = {
            _FORK.EXIT_OK,
            _FORK.EXIT_LOCK_1_FAILED,
            _FORK.EXIT_LOCK_2_FAILED,
            _FORK.EXIT_LOCK_3_FAILED,
            _FORK.EXIT_DELEGATION_IMPORT_FAILED,
        }
        self.assertEqual(len(codes), 5)

    def test_failure_codes_are_nonzero(self) -> None:
        for code in (
            _FORK.EXIT_LOCK_1_FAILED,
            _FORK.EXIT_LOCK_2_FAILED,
            _FORK.EXIT_LOCK_3_FAILED,
            _FORK.EXIT_DELEGATION_IMPORT_FAILED,
        ):
            self.assertNotEqual(code, 0)


# ---------------------------------------------------------------------------
# Authority source constants
# ---------------------------------------------------------------------------


class TestAuthorityConstants(unittest.TestCase):
    """Authority source constants must point to the expected SEALED docs."""

    def test_execution_mode_protocol_path(self) -> None:
        self.assertEqual(
            _FORK.AUTHORITY_SOURCE_EXECUTION_MODE_PROTOCOL,
            "docs/operations/evidence/sol_s1_v3_execution_mode_protocol.md",
        )

    def test_v3r2_run_go_receipt_path(self) -> None:
        self.assertEqual(
            _FORK.AUTHORITY_SOURCE_V3R2_RUN_GO_RECEIPT,
            "docs/operations/evidence/sol_s1_v3r2_run_go_receipt.md",
        )

    def test_design_addendum_runner_path(self) -> None:
        self.assertEqual(
            _FORK.AUTHORITY_SOURCE_DESIGN_ADDENDUM_RUNNER,
            "docs/operations/evidence/sol_s1_v3_design_addendum_runner_authority.md",
        )

    def test_all_authority_sources_are_strings(self) -> None:
        for attr_name in (
            "AUTHORITY_SOURCE_EXECUTION_MODE_PROTOCOL",
            "AUTHORITY_SOURCE_V3R2_RUN_GO_RECEIPT",
            "AUTHORITY_SOURCE_DESIGN_ADDENDUM_RUNNER",
        ):
            self.assertIsInstance(getattr(_FORK, attr_name), str)

    def test_all_authority_sources_distinct(self) -> None:
        paths = {
            _FORK.AUTHORITY_SOURCE_EXECUTION_MODE_PROTOCOL,
            _FORK.AUTHORITY_SOURCE_V3R2_RUN_GO_RECEIPT,
            _FORK.AUTHORITY_SOURCE_DESIGN_ADDENDUM_RUNNER,
        }
        self.assertEqual(len(paths), 3)


# ---------------------------------------------------------------------------
# Frozen sha256 constant equality
# ---------------------------------------------------------------------------


class TestFrozenSha256ConstantEquality(unittest.TestCase):
    """`FORK_OF_ORIGINAL_SHA256` must equal the actual frozen runner sha256.

    Computes the sha256 of the frozen runner file at test time (read-only
    file I/O; no import, no execution) and asserts it matches the constant
    baked into the fork and the literal expected value.
    """

    def test_constant_matches_expected_literal(self) -> None:
        self.assertEqual(
            _FORK.FORK_OF_ORIGINAL_SHA256, EXPECTED_FROZEN_SHA256
        )

    def test_constant_matches_file_on_disk(self) -> None:
        self.assertTrue(
            FROZEN_PATH.is_file(),
            f"frozen runner missing at {FROZEN_PATH}",
        )
        computed = hashlib.sha256(FROZEN_PATH.read_bytes()).hexdigest()
        self.assertEqual(computed, EXPECTED_FROZEN_SHA256)
        self.assertEqual(computed, _FORK.FORK_OF_ORIGINAL_SHA256)

    def test_constant_is_64_hex_chars(self) -> None:
        self.assertEqual(len(_FORK.FORK_OF_ORIGINAL_SHA256), 64)
        int(_FORK.FORK_OF_ORIGINAL_SHA256, 16)  # must parse as hex


# ---------------------------------------------------------------------------
# Fork provenance constants
# ---------------------------------------------------------------------------


class TestForkProvenanceConstants(unittest.TestCase):
    """Fork provenance constants form the fork's audit trail."""

    def test_fork_of_original_path(self) -> None:
        self.assertEqual(
            _FORK.FORK_OF_ORIGINAL_PATH, "scripts/sol_s1_v3_shadow_run.py"
        )

    def test_fork_chain_id(self) -> None:
        self.assertEqual(
            _FORK.FORK_CHAIN_ID,
            "grp_chain_impl_2_runner_script_fork_chain",
        )

    def test_fork_design_version_label(self) -> None:
        self.assertEqual(_FORK.FORK_DESIGN_VERSION_LABEL, "V-3R2")


# ---------------------------------------------------------------------------
# Guard purity / isolation invariants
# ---------------------------------------------------------------------------


class TestGuardIsolationInvariants(unittest.TestCase):
    """The guard must be pure: no arg/env mutation, no global state reach."""

    def test_guard_does_not_mutate_env_arg(self) -> None:
        env = {
            "SOL_S1_V3_RUN_AUTHORIZED": "v3_run_go_granted",
            "SOL_S1_V3_EXECUTION_MODE": "historical_replay",
        }
        env_snapshot = dict(env)
        _FORK.triple_lock_pre_flight_guard(["prog", "--run"], env)
        self.assertEqual(env, env_snapshot)

    def test_guard_does_not_mutate_argv_arg(self) -> None:
        argv = ["prog", "--run"]
        argv_snapshot = list(argv)
        _FORK.triple_lock_pre_flight_guard(
            argv,
            {
                "SOL_S1_V3_RUN_AUTHORIZED": "v3_run_go_granted",
                "SOL_S1_V3_EXECUTION_MODE": "historical_replay",
            },
        )
        self.assertEqual(argv, argv_snapshot)

    def test_guard_does_not_touch_os_environ(self) -> None:
        # Read-only snapshot check; os.environ is not mutated by the guard.
        snapshot = dict(os.environ)
        _FORK.triple_lock_pre_flight_guard(["prog", "--run"], {})
        self.assertEqual(dict(os.environ), snapshot)

    def test_guard_does_not_touch_sys_argv(self) -> None:
        snapshot = list(sys.argv)
        _FORK.triple_lock_pre_flight_guard(["prog", "--run"], {})
        self.assertEqual(list(sys.argv), snapshot)

    def test_guard_is_deterministic_on_repeated_calls(self) -> None:
        good_argv = ["prog", "--run"]
        good_env = {
            "SOL_S1_V3_RUN_AUTHORIZED": "v3_run_go_granted",
            "SOL_S1_V3_EXECUTION_MODE": "realtime_shadow",
        }
        results = [
            _FORK.triple_lock_pre_flight_guard(good_argv, good_env)
            for _ in range(5)
        ]
        self.assertEqual(results, [_FORK.EXIT_OK] * 5)


# ---------------------------------------------------------------------------
# Frozen runner NOT imported at fork-module load time
# ---------------------------------------------------------------------------


class TestFrozenRunnerNotImportedAtModuleLoad(unittest.TestCase):
    """Loading the fork must NOT pull in the frozen V-3R1 runner."""

    def test_frozen_module_not_in_sys_modules(self) -> None:
        # The frozen runner's canonical module name is `sol_s1_v3_shadow_run`.
        # After `_load_fork_module()` ran at the top of this file, that name
        # must NOT be in sys.modules, because the fork's import of the
        # frozen runner is lazy (inside main() after all three locks pass).
        self.assertNotIn("sol_s1_v3_shadow_run", sys.modules)

    def test_fork_module_loaded_under_testsubject_name(self) -> None:
        # Sanity check: the loader placed the fork under its test-private
        # module name. This is an artifact of how _load_fork_module() runs.
        self.assertTrue(
            _FORK.__name__.endswith("sol_s1_v3r2_shadow_run_testsubject")
            or _FORK.__name__ == "sol_s1_v3r2_shadow_run_testsubject",
            f"unexpected fork module __name__: {_FORK.__name__}",
        )


# NOTE: This test file is intentionally created without any
# `unittest.main()` or pytest hook. IMPL-3 forbids test execution.
# Discovery by a separate test runner under VAL-1 is the intended path.
