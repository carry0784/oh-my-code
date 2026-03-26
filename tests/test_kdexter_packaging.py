"""
B-04 kdexter Packaging Tests — 4 tests

Validates editable install contract, NOT local src path injection.
All tests assume `pip install -e .` has been run.
sys.path hacks are forbidden — import must work via installed package.
"""
from __future__ import annotations

import os

import pytest


class TestKdexterPackaging:
    """B-04: kdexter pip packaging verification."""

    def test_kdexter_import(self):
        """import kdexter succeeds and __version__ exists."""
        import kdexter

        assert hasattr(kdexter, "__version__")
        assert isinstance(kdexter.__version__, str)
        assert len(kdexter.__version__) > 0

    def test_kdexter_submodule_import(self):
        """Core submodules are importable via installed package."""
        from kdexter.ledger.forbidden_ledger import ForbiddenLedger
        from kdexter.audit.evidence_store import EvidenceStore
        from kdexter.state_machine.security_state import SecurityStateContext
        from kdexter.engines.trust_decay import TrustDecayEngine
        from kdexter.tcl.commands import TCLDispatcher

        # All classes are importable
        assert ForbiddenLedger is not None
        assert EvidenceStore is not None
        assert SecurityStateContext is not None
        assert TrustDecayEngine is not None
        assert TCLDispatcher is not None

    def test_package_metadata(self):
        """Installed package metadata contains name and version."""
        from importlib.metadata import metadata

        meta = metadata("kdexter")
        assert meta["Name"] == "kdexter"
        assert meta["Version"] == "0.1.0"

    def test_no_sys_path_hack_in_new_tests(self):
        """B-01~B-07 new test files do not use sys.path.insert hack."""
        new_test_files = [
            "test_position_symbol_name.py",      # B-01
            "test_historical_stats.py",           # B-02
            "test_operational_logging.py",        # B-03
            "test_kdexter_packaging.py",          # B-04
            "test_idempotent_registration.py",    # B-05
            "test_agent_governance.py",           # B-06
            "test_evidence_persistence.py",       # B-07
        ]

        tests_dir = os.path.dirname(__file__)

        for filename in new_test_files:
            if filename == "test_kdexter_packaging.py":
                continue  # skip self — contains pattern as string literal
            filepath = os.path.join(tests_dir, filename)
            if not os.path.exists(filepath):
                continue
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            assert "sys.path.insert" not in content, \
                f"{filename} must not contain sys.path hack — use pip install instead"
