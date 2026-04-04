"""CR-046 Isolation Guard Tests — contamination prevention"""

import ast
import os
import pytest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestStringSearchGuards:
    """First-line defense: string searches for prohibited patterns."""

    def test_eth_not_in_beat_schedule(self):
        """ETH must not appear in celery beat schedule."""
        import workers.celery_app as celery_mod

        schedule = celery_mod.celery_app.conf.beat_schedule
        for key, config in schedule.items():
            kwargs = config.get("kwargs", {})
            symbol = kwargs.get("symbol", "")
            assert "ETH" not in symbol.upper(), f"ETH found in beat schedule: {key}"
            # Also check task name
            assert "eth" not in key.lower(), f"ETH found in schedule key: {key}"

    def test_no_dry_run_false_in_codebase(self):
        """dry_run=False must not appear in CR-046 operational code."""
        # Check only CR-046 specific files (new code), not pre-existing modules
        cr046_files = [
            os.path.join(PROJECT_ROOT, "strategies", "smc_wavetrend_strategy.py"),
            os.path.join(PROJECT_ROOT, "app", "services", "paper_trading_session_cr046.py"),
            os.path.join(PROJECT_ROOT, "app", "services", "session_store_cr046.py"),
            os.path.join(PROJECT_ROOT, "workers", "tasks", "sol_paper_tasks.py"),
            os.path.join(PROJECT_ROOT, "workers", "tasks", "btc_paper_tasks.py"),
        ]
        violations = []
        for path in cr046_files:
            if not os.path.isfile(path):
                continue
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
            if "dry_run=False" in content or "dry_run = False" in content:
                violations.append(path)
        assert not violations, f"dry_run=False found in CR-046 code: {violations}"

    def test_no_smc_version_a_import(self):
        """calc_smc( (Version A) must not be called in operational code. Only calc_smc_pure_causal allowed."""
        dirs_to_check = [
            os.path.join(PROJECT_ROOT, "strategies"),
            os.path.join(PROJECT_ROOT, "app", "services"),
            os.path.join(PROJECT_ROOT, "workers", "tasks"),
        ]
        violations = []
        for d in dirs_to_check:
            if not os.path.isdir(d):
                continue
            for root, _, files in os.walk(d):
                for f in files:
                    if not f.endswith(".py"):
                        continue
                    path = os.path.join(root, f)
                    with open(path, "r", encoding="utf-8") as fh:
                        for line_no, line in enumerate(fh, 1):
                            # Match calc_smc( but not calc_smc_pure_causal(
                            stripped = line.strip()
                            if "calc_smc(" in stripped and "calc_smc_pure_causal(" not in stripped:
                                violations.append(f"{path}:{line_no}: {stripped}")
        assert not violations, f"SMC Version A (calc_smc) found: {violations}"

    def test_no_regime_filter_in_signal_pipeline(self):
        """ADX/BB Width/ATR ratio filter must not be in signal pipeline."""
        dirs_to_check = [
            os.path.join(PROJECT_ROOT, "strategies"),
            os.path.join(PROJECT_ROOT, "workers", "tasks"),
        ]
        prohibited = ["adx_filter", "bb_width_filter", "atr_ratio_filter", "RegimeFilter"]
        violations = []
        for d in dirs_to_check:
            if not os.path.isdir(d):
                continue
            for root, _, files in os.walk(d):
                for f in files:
                    if not f.endswith(".py"):
                        continue
                    path = os.path.join(root, f)
                    with open(path, "r", encoding="utf-8") as fh:
                        content = fh.read()
                    for pattern in prohibited:
                        if pattern in content:
                            violations.append(f"{path}: {pattern}")
        assert not violations, f"Regime filter found in signal pipeline: {violations}"


class TestRuntimeContracts:
    """Second-line defense: runtime assertions."""

    def test_sol_task_import_graph_no_eth_research(self):
        """sol_paper_tasks must not import track_b_eth_research."""
        import importlib

        mod = importlib.import_module("workers.tasks.sol_paper_tasks")
        source_file = mod.__file__
        with open(source_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "track_b_eth_research" not in content

    def test_signal_pipeline_no_regime_v1_filter_object(self):
        """Strategy object must not have ADX/BB/ATR filter attributes."""
        from strategies.smc_wavetrend_strategy import SMCWaveTrendStrategy

        strategy = SMCWaveTrendStrategy(symbol="SOL/USDT")
        assert not hasattr(strategy, "adx_filter")
        assert not hasattr(strategy, "bb_width_filter")
        assert not hasattr(strategy, "atr_ratio_filter")
        assert not hasattr(strategy, "regime_filter")

    def test_strategy_uses_version_b_only(self):
        """Strategy file must reference Version B (pure-causal) only."""
        from strategies import smc_wavetrend_strategy as mod

        source = open(mod.__file__, "r", encoding="utf-8").read()
        assert "pure_causal" in source or "pure-causal" in source
        # Must NOT have calc_smc( without _pure_causal suffix
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            if "calc_smc(" in line and "calc_smc_pure_causal(" not in line:
                pytest.fail(f"Line {i}: Version A calc_smc found: {line.strip()}")
