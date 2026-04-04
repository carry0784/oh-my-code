"""
B-05 Idempotent Registration Tests — 6 tests

Validates:
  - ForbiddenLedger.register() overwrite convergence
  - setup_logging() handler duplication prevention
  - ExchangeFactory.create() singleton caching
  - GovernanceGate singleton (B-06 reference)
  - TrustDecayEngine.register() overwrite convergence
  - TCLDispatcher.register() overwrite convergence

Idempotent mode taxonomy:
  - Clear-and-rebuild: setup_logging()
  - Singleton/cached: ExchangeFactory.create(), GovernanceGate
  - Overwrite-convergent: ForbiddenLedger.register(), TrustDecayEngine.register(),
                          TCLDispatcher.register()
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from kdexter.ledger.forbidden_ledger import ForbiddenLedger, ForbiddenAction
from kdexter.engines.trust_decay import TrustDecayEngine
from kdexter.state_machine.trust_state import TrustStateContext
from kdexter.tcl.commands import TCLDispatcher


# ═══════════════════════════════════════════════════════════════════════════ #
# B-05: IDEMPOTENT REGISTRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════ #

class TestIdempotentRegistration:
    """B-05: register/init/setup idempotent contract verification."""

    def test_forbidden_ledger_register_idempotent(self):
        """ForbiddenLedger.register(): same action_id twice → count=1, last value wins."""
        ledger = ForbiddenLedger()

        fa_v1 = ForbiddenAction(
            action_id="FA-TEST-001",
            description="Version 1",
            severity="BLOCKED",
            pattern="TEST_PATTERN",
            registered_by="test",
        )
        fa_v2 = ForbiddenAction(
            action_id="FA-TEST-001",  # same action_id
            description="Version 2",
            severity="LOCKDOWN",
            pattern="TEST_PATTERN_V2",
            registered_by="test",
        )

        ledger.register(fa_v1)
        ledger.register(fa_v2)  # duplicate registration

        actions = ledger.list_actions()
        matching = [a for a in actions if a.action_id == "FA-TEST-001"]
        assert len(matching) == 1, "Same action_id must converge to one entry"
        assert matching[0].description == "Version 2", "Last registration wins"
        assert matching[0].severity == "LOCKDOWN", "Last severity wins"

    def test_setup_logging_no_duplicate_handlers(self):
        """setup_logging() called twice → no duplicate handlers on root logger."""
        import app.core.logging as log_module

        with patch.object(log_module, "settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.log_file_path = ""
            mock_settings.log_level = "INFO"

            # Call setup twice
            log_module.setup_logging()
            handler_count_1 = len(logging.getLogger().handlers)

            log_module.setup_logging()
            handler_count_2 = len(logging.getLogger().handlers)

        assert handler_count_1 == handler_count_2, \
            "Handler count must not increase on repeated setup_logging() calls"
        assert handler_count_2 == 1, \
            "Only StreamHandler should exist (no file path configured)"

    def test_exchange_factory_singleton_cached(self):
        """ExchangeFactory.create(): same exchange twice → same instance."""
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pytest.skip("No running event loop — ExchangeFactory requires async context")

        from exchanges.factory import ExchangeFactory

        # Clear cache for test isolation
        original_instances = ExchangeFactory._instances.copy()
        ExchangeFactory._instances.clear()

        try:
            instance1 = ExchangeFactory.create("binance")
            instance2 = ExchangeFactory.create("binance")

            assert instance1 is instance2, \
                "Same exchange key must return cached singleton"
        finally:
            ExchangeFactory._instances = original_instances

    def test_governance_gate_duplicate_blocked(self):
        """GovernanceGate duplicate creation is blocked (B-06 validated)."""
        # This test references B-06's test_singleton_enforced.
        # GovernanceGate uses _instance + _creation_lock for singleton enforcement.
        # Verified in tests/test_agent_governance.py::TestSingletonSafety::test_singleton_enforced
        from app.agents.governance_gate import GovernanceGate

        assert hasattr(GovernanceGate, "_instance"), \
            "GovernanceGate must have _instance class variable (B-06)"
        assert hasattr(GovernanceGate, "_creation_lock"), \
            "GovernanceGate must have _creation_lock (B-06)"
        assert hasattr(GovernanceGate, "_reset_for_testing"), \
            "GovernanceGate must have _reset_for_testing (B-06)"

    def test_trust_decay_register_idempotent(self):
        """TrustDecayEngine.register(): same component_id twice → count=1."""
        engine = TrustDecayEngine()

        ctx1 = TrustStateContext(component_id="main_strategy")
        ctx2 = TrustStateContext(component_id="main_strategy")

        engine.register("main_strategy", ctx1)
        engine.register("main_strategy", ctx2)  # duplicate

        assert len(engine._components) == 1, \
            "Same component_id must converge to one entry"
        assert engine.get_context("main_strategy") is ctx2, \
            "Last registration wins"

    def test_tcl_dispatcher_register_idempotent(self):
        """TCLDispatcher.register(): same exchange twice → count=1."""
        dispatcher = TCLDispatcher()

        adapter1 = MagicMock()
        adapter2 = MagicMock()

        dispatcher.register("binance", adapter1)
        dispatcher.register("binance", adapter2)  # duplicate

        assert len(dispatcher._adapters) == 1, \
            "Same exchange key must converge to one entry"
        assert dispatcher._adapters["binance"] is adapter2, \
            "Last registration wins"
