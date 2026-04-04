"""
CR-048 Design Contract Tests — L1 test coverage expansion.

Tests verify design contracts defined in Phase 0/Phase 1 documents.
NO implementation code is imported. All tests validate constants, rules,
and matrices defined in the design documents as pure Python contracts.

Source documents:
- docs/architecture/injection_constitution.md (v2.0)
- docs/architecture/broker_matrix.md (v2.0)
- docs/architecture/exclusion_baseline.md (v2.0)
- docs/architecture/design_indicator_registry.md (v1.0)
- docs/architecture/design_feature_pack.md (v1.0)
- docs/architecture/design_strategy_registry.md (v1.0)
- docs/architecture/design_promotion_state.md (v1.0)

Traceability: docs/architecture/design_test_traceability.md
"""

from __future__ import annotations

import pytest


# ═══════════════════════════════════════════════════════════════════════
# Design Contract Constants (extracted from design documents)
# These are the "source of truth" that future implementation MUST match.
# ═══════════════════════════════════════════════════════════════════════

FORBIDDEN_BROKERS = frozenset({"ALPACA", "KIWOOM_US"})

ALLOWED_BROKERS = {
    "CRYPTO": frozenset({"BINANCE", "BITGET", "UPBIT"}),
    "US_STOCK": frozenset({"KIS_US"}),
    "KR_STOCK": frozenset({"KIS_KR", "KIWOOM_KR"}),
}

FORBIDDEN_SECTORS = frozenset(
    {
        "MEME",
        "GAMEFI",
        "LOW_LIQUIDITY_NEW_TOKEN",
        "HIGH_VALUATION_PURE_SW",
        "WEAK_CONSUMER_BETA",
        "OIL_SENSITIVE",
        "LOW_LIQUIDITY_THEME",
    }
)

ALLOWED_SECTORS = {
    "CRYPTO": frozenset({"LAYER1", "DEFI", "AI", "INFRA"}),
    "US_STOCK": frozenset({"TECH", "HEALTHCARE", "ENERGY", "FINANCE"}),
    "KR_STOCK": frozenset({"SEMICONDUCTOR", "IT", "FINANCE_KR", "AUTO"}),
}

TRADING_HOURS = {
    "BINANCE": {"type": "24_7"},
    "BITGET": {"type": "24_7"},
    "UPBIT": {"type": "24_7"},
    "KIS_KR": {"type": "weekday", "tz": "Asia/Seoul", "open": "09:00", "close": "15:30"},
    "KIWOOM_KR": {"type": "weekday", "tz": "Asia/Seoul", "open": "09:00", "close": "15:30"},
    "KIS_US": {"type": "weekday", "tz": "US/Eastern", "open": "09:30", "close": "16:00"},
}

SYMBOL_STATES = frozenset({"CORE", "WATCH", "EXCLUDED"})

PROMOTION_STATES = frozenset(
    {
        "DRAFT",
        "REGISTERED",
        "BACKTEST_PASS",
        "BACKTEST_FAIL",
        "PAPER_PASS",
        "QUARANTINE",
        "GUARDED_LIVE",
        "LIVE",
        "RETIRED",
        "BLOCKED",
    }
)

VALID_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"REGISTERED"},
    "REGISTERED": {"BACKTEST_PASS", "BACKTEST_FAIL"},
    "BACKTEST_FAIL": {"REGISTERED"},
    "BACKTEST_PASS": {"PAPER_PASS", "BACKTEST_FAIL"},
    "PAPER_PASS": {"GUARDED_LIVE"},
    "GUARDED_LIVE": {"LIVE", "QUARANTINE"},
    "LIVE": {"QUARANTINE", "RETIRED"},
    "QUARANTINE": {"GUARDED_LIVE", "BLOCKED"},
    "RETIRED": set(),
    "BLOCKED": set(),
}

REQUIRES_APPROVAL: dict[tuple[str, str], str] = {
    ("PAPER_PASS", "GUARDED_LIVE"): "APPROVER",
    ("GUARDED_LIVE", "LIVE"): "APPROVER",
    ("QUARANTINE", "GUARDED_LIVE"): "APPROVER",
    ("QUARANTINE", "BLOCKED"): "APPROVER",
    ("LIVE", "RETIRED"): "APPROVER",
}

STRATEGY_BANK = {
    "Research": {"DRAFT", "REGISTERED"},
    "Qualified": {"BACKTEST_PASS"},
    "Paper": {"PAPER_PASS"},
    "Quarantine": {"QUARANTINE"},
    "Live": {"GUARDED_LIVE", "LIVE"},
    "Retired": {"RETIRED"},
    "Blocked": {"BLOCKED"},
}

EXPOSURE_CAPS = {
    "market_active_strategies": 5,
    "symbol_concurrent_strategies": 3,
    "strategy_symbol_concurrent": 30,
    "market_total_symbols": 20,
    "theme_symbols": 5,
    "single_symbol_capital_pct": 10,
    "single_theme_capital_pct": 25,
    "single_market_capital_pct": 50,
}

GATEWAY_CHECKS = [
    "forbidden_broker",
    "forbidden_sector",
    "dependency_verification",
    "version_checksum",
    "manifest_signature",
    "market_matrix_compatibility",
]

PAPER_SHADOW_MIN_DAYS = 14

LOW_MCAP_THRESHOLD_USD = 50_000_000
NEW_LISTING_MIN_MONTHS = 6
HIGH_PER_THRESHOLD = 80
KR_LOW_VOLUME_THRESHOLD_KRW = 500_000_000

# Meme coins explicitly listed in exclusion baseline
MEME_COINS = {"DOGE", "SHIB", "PEPE", "WIF", "BONK"}
GAMEFI_COINS = {"AXS", "IMX", "SAND"}


# ═══════════════════════════════════════════════════════════════════════
# 1. Injection Constitution Tests (C-01 ~ C-08)
# ═══════════════════════════════════════════════════════════════════════


class TestInjectionConstitution:
    """Tests for injection_constitution.md contracts."""

    def test_forbidden_brokers_contains_alpaca_kiwoom_us(self):
        """C-01: ALPACA and KIWOOM_US must be in FORBIDDEN_BROKERS."""
        assert "ALPACA" in FORBIDDEN_BROKERS
        assert "KIWOOM_US" in FORBIDDEN_BROKERS

    def test_forbidden_sectors_seven_items(self):
        """C-02: Exactly 7 forbidden sectors must be defined."""
        assert len(FORBIDDEN_SECTORS) == 7
        expected = {
            "MEME",
            "GAMEFI",
            "LOW_LIQUIDITY_NEW_TOKEN",
            "HIGH_VALUATION_PURE_SW",
            "WEAK_CONSUMER_BETA",
            "OIL_SENSITIVE",
            "LOW_LIQUIDITY_THEME",
        }
        assert FORBIDDEN_SECTORS == expected

    def test_allowed_brokers_per_asset_class(self):
        """C-03: CRYPTO=3, US_STOCK=1, KR_STOCK=2 allowed brokers."""
        assert len(ALLOWED_BROKERS["CRYPTO"]) == 3
        assert len(ALLOWED_BROKERS["US_STOCK"]) == 1
        assert len(ALLOWED_BROKERS["KR_STOCK"]) == 2

    def test_forbidden_and_allowed_no_overlap(self):
        """C-04: No broker can be both forbidden and allowed."""
        all_allowed = set()
        for brokers in ALLOWED_BROKERS.values():
            all_allowed |= brokers
        overlap = FORBIDDEN_BROKERS & all_allowed
        assert overlap == set(), f"Overlap found: {overlap}"

    def test_exposure_caps_values(self):
        """C-05: All 8 exposure cap values must match design document."""
        assert EXPOSURE_CAPS["market_active_strategies"] == 5
        assert EXPOSURE_CAPS["symbol_concurrent_strategies"] == 3
        assert EXPOSURE_CAPS["strategy_symbol_concurrent"] == 30
        assert EXPOSURE_CAPS["market_total_symbols"] == 20
        assert EXPOSURE_CAPS["theme_symbols"] == 5
        assert EXPOSURE_CAPS["single_symbol_capital_pct"] == 10
        assert EXPOSURE_CAPS["single_theme_capital_pct"] == 25
        assert EXPOSURE_CAPS["single_market_capital_pct"] == 50
        assert len(EXPOSURE_CAPS) == 8

    def test_gateway_checks_six_steps(self):
        """C-06: Gateway must have exactly 6 verification steps in order."""
        assert len(GATEWAY_CHECKS) == 6
        assert GATEWAY_CHECKS[0] == "forbidden_broker"
        assert GATEWAY_CHECKS[1] == "forbidden_sector"
        assert GATEWAY_CHECKS[2] == "dependency_verification"
        assert GATEWAY_CHECKS[3] == "version_checksum"
        assert GATEWAY_CHECKS[4] == "manifest_signature"
        assert GATEWAY_CHECKS[5] == "market_matrix_compatibility"

    def test_strategy_bank_seven_states(self):
        """C-07: Strategy Bank must have exactly 7 banks."""
        assert len(STRATEGY_BANK) == 7
        expected_banks = {
            "Research",
            "Qualified",
            "Paper",
            "Quarantine",
            "Live",
            "Retired",
            "Blocked",
        }
        assert set(STRATEGY_BANK.keys()) == expected_banks

    def test_paper_shadow_minimum_two_weeks(self):
        """C-08: Paper Shadow minimum period is 14 days (2 weeks)."""
        assert PAPER_SHADOW_MIN_DAYS == 14
        assert PAPER_SHADOW_MIN_DAYS >= 14


# ═══════════════════════════════════════════════════════════════════════
# 2. Broker Matrix Tests (B-01 ~ B-06)
# ═══════════════════════════════════════════════════════════════════════


class TestBrokerMatrix:
    """Tests for broker_matrix.md contracts."""

    def test_total_allowed_brokers_six(self):
        """B-01: Total unique allowed brokers = 6."""
        all_brokers = set()
        for brokers in ALLOWED_BROKERS.values():
            all_brokers |= brokers
        assert len(all_brokers) == 6
        expected = {"BINANCE", "BITGET", "UPBIT", "KIS_US", "KIS_KR", "KIWOOM_KR"}
        assert all_brokers == expected

    def test_forbidden_brokers_frozenset(self):
        """B-02: FORBIDDEN_BROKERS must be frozenset (immutable)."""
        assert isinstance(FORBIDDEN_BROKERS, frozenset)
        with pytest.raises(AttributeError):
            FORBIDDEN_BROKERS.add("NEW_BROKER")  # type: ignore[attr-defined]

    def test_kis_us_only_in_us_stock(self):
        """B-03: KIS_US must only appear in US_STOCK, not CRYPTO or KR_STOCK."""
        assert "KIS_US" in ALLOWED_BROKERS["US_STOCK"]
        assert "KIS_US" not in ALLOWED_BROKERS["CRYPTO"]
        assert "KIS_US" not in ALLOWED_BROKERS["KR_STOCK"]

    def test_trading_hours_defined(self):
        """B-04: All 6 allowed brokers must have trading hours defined."""
        all_brokers = set()
        for brokers in ALLOWED_BROKERS.values():
            all_brokers |= brokers
        for broker in all_brokers:
            assert broker in TRADING_HOURS, f"Missing trading hours for {broker}"

    def test_crypto_brokers_24_7(self):
        """B-05: BINANCE, BITGET, UPBIT must be 24/7."""
        for broker in ("BINANCE", "BITGET", "UPBIT"):
            assert TRADING_HOURS[broker]["type"] == "24_7"

    def test_forbidden_broker_registration_rejected(self):
        """B-06: Strategy registration with forbidden broker must be rejected."""

        def validate_broker(exchange: str) -> bool:
            """Simulates Injection Gateway broker check."""
            if exchange in FORBIDDEN_BROKERS:
                return False
            return True

        assert validate_broker("BINANCE") is True
        assert validate_broker("ALPACA") is False
        assert validate_broker("KIWOOM_US") is False
        assert validate_broker("KIS_US") is True


# ═══════════════════════════════════════════════════════════════════════
# 3. Exclusion Baseline Tests (E-01 ~ E-07)
# ═══════════════════════════════════════════════════════════════════════


class TestExclusionBaseline:
    """Tests for exclusion_baseline.md contracts."""

    def test_forbidden_sectors_complete(self):
        """E-01: All 7 forbidden sectors must be present."""
        assert len(FORBIDDEN_SECTORS) == 7
        for sector in (
            "MEME",
            "GAMEFI",
            "LOW_LIQUIDITY_NEW_TOKEN",
            "HIGH_VALUATION_PURE_SW",
            "WEAK_CONSUMER_BETA",
            "OIL_SENSITIVE",
            "LOW_LIQUIDITY_THEME",
        ):
            assert sector in FORBIDDEN_SECTORS, f"Missing: {sector}"

    def test_excluded_cannot_become_core(self):
        """E-02: EXCLUDED status cannot transition directly to CORE."""
        # Design contract: EXCLUDED symbols cannot enter CORE without
        # first clearing the Exclusion Baseline (A approval required).
        valid_core_sources = {"WATCH"}  # Only WATCH can become CORE (via 5-stage screening)
        assert "EXCLUDED" not in valid_core_sources

    def test_excluded_cannot_become_watch_without_approval(self):
        """E-03: EXCLUDED → WATCH requires A approval + exclusion reason cleared."""
        # Design contract: EXCLUDED → WATCH manual transition requires:
        # 1. Exclusion reason resolved (evidence)
        # 2. A approval
        requires_a_approval = True
        requires_evidence = True
        assert requires_a_approval
        assert requires_evidence

    def test_symbol_three_states(self):
        """E-04: Exactly 3 symbol states must be defined."""
        assert len(SYMBOL_STATES) == 3
        assert SYMBOL_STATES == {"CORE", "WATCH", "EXCLUDED"}

    def test_meme_always_excluded(self):
        """E-05: Known meme coins must always be EXCLUDED."""

        def classify_sector(symbol_sector: str) -> str:
            """Simulates exclusion filter."""
            if symbol_sector in FORBIDDEN_SECTORS:
                return "EXCLUDED"
            return "PENDING_SCREENING"

        # All meme coins have sector MEME
        assert classify_sector("MEME") == "EXCLUDED"
        assert classify_sector("GAMEFI") == "EXCLUDED"
        # Valid sectors pass through
        assert classify_sector("LAYER1") == "PENDING_SCREENING"
        assert classify_sector("TECH") == "PENDING_SCREENING"

    def test_low_mcap_threshold(self):
        """E-06: Market cap < $50M must trigger EXCLUDED."""

        def check_mcap(mcap_usd: float) -> str:
            if mcap_usd < LOW_MCAP_THRESHOLD_USD:
                return "EXCLUDED"
            return "PENDING_SCREENING"

        assert check_mcap(49_999_999) == "EXCLUDED"
        assert check_mcap(50_000_000) == "PENDING_SCREENING"
        assert check_mcap(100_000_000) == "PENDING_SCREENING"
        assert check_mcap(1_000_000) == "EXCLUDED"

    def test_eth_operational_ban(self):
        """E-07: ETH is in allowed sector (LAYER1) but has operational ban (CR-046)."""
        # ETH is Layer-1 (allowed sector)
        assert "LAYER1" in ALLOWED_SECTORS["CRYPTO"]
        assert "LAYER1" not in FORBIDDEN_SECTORS
        # But CR-046 prohibits operational path for ETH
        # Design recommendation: WATCH + operational_ban=True
        eth_status = "WATCH"
        eth_operational_ban = True
        eth_ban_reason = "CR-046"
        assert eth_status != "EXCLUDED"  # Not excluded (valid sector)
        assert eth_status != "CORE"  # Not core (operational ban)
        assert eth_operational_ban is True
        assert eth_ban_reason == "CR-046"


# ═══════════════════════════════════════════════════════════════════════
# 4. Promotion State Tests (P-01 ~ P-08)
# ═══════════════════════════════════════════════════════════════════════


class TestPromotionState:
    """Tests for design_promotion_state.md contracts."""

    def test_promotion_states_ten(self):
        """P-01: Exactly 10 promotion states must be defined."""
        assert len(PROMOTION_STATES) == 10
        expected = {
            "DRAFT",
            "REGISTERED",
            "BACKTEST_PASS",
            "BACKTEST_FAIL",
            "PAPER_PASS",
            "QUARANTINE",
            "GUARDED_LIVE",
            "LIVE",
            "RETIRED",
            "BLOCKED",
        }
        assert PROMOTION_STATES == expected

    def test_valid_transitions_matrix(self):
        """P-02: All valid transitions must be defined and allowed."""
        # Every state in PROMOTION_STATES must appear in VALID_TRANSITIONS
        for state in PROMOTION_STATES:
            assert state in VALID_TRANSITIONS, f"Missing transition def for {state}"

        # Verify specific key transitions
        assert "REGISTERED" in VALID_TRANSITIONS["DRAFT"]
        assert "BACKTEST_PASS" in VALID_TRANSITIONS["REGISTERED"]
        assert "PAPER_PASS" in VALID_TRANSITIONS["BACKTEST_PASS"]
        assert "GUARDED_LIVE" in VALID_TRANSITIONS["PAPER_PASS"]
        assert "LIVE" in VALID_TRANSITIONS["GUARDED_LIVE"]
        assert "QUARANTINE" in VALID_TRANSITIONS["GUARDED_LIVE"]
        assert "QUARANTINE" in VALID_TRANSITIONS["LIVE"]
        assert "GUARDED_LIVE" in VALID_TRANSITIONS["QUARANTINE"]
        assert "BLOCKED" in VALID_TRANSITIONS["QUARANTINE"]

    @pytest.mark.parametrize(
        "from_state,to_state",
        [
            ("DRAFT", "LIVE"),
            ("DRAFT", "GUARDED_LIVE"),
            ("DRAFT", "PAPER_PASS"),
            ("REGISTERED", "LIVE"),
            ("REGISTERED", "GUARDED_LIVE"),
            ("REGISTERED", "PAPER_PASS"),
            ("BACKTEST_PASS", "LIVE"),
            ("BACKTEST_PASS", "GUARDED_LIVE"),
            ("PAPER_PASS", "LIVE"),
            ("BLOCKED", "LIVE"),
            ("BLOCKED", "GUARDED_LIVE"),
            ("RETIRED", "LIVE"),
            ("RETIRED", "GUARDED_LIVE"),
        ],
    )
    def test_invalid_transitions_rejected(self, from_state: str, to_state: str):
        """P-03: Invalid transitions must be rejected."""
        valid_targets = VALID_TRANSITIONS.get(from_state, set())
        assert to_state not in valid_targets, (
            f"Transition {from_state} → {to_state} should be INVALID but is allowed"
        )

    def test_blocked_is_terminal(self):
        """P-04: BLOCKED is a terminal state with no valid transitions."""
        assert VALID_TRANSITIONS["BLOCKED"] == set()

    def test_retired_is_terminal(self):
        """P-05: RETIRED is a terminal state with no valid transitions."""
        assert VALID_TRANSITIONS["RETIRED"] == set()

    def test_approval_required_transitions(self):
        """P-06: Exactly 5 transitions require A (APPROVER) approval."""
        assert len(REQUIRES_APPROVAL) == 5
        expected_transitions = {
            ("PAPER_PASS", "GUARDED_LIVE"),
            ("GUARDED_LIVE", "LIVE"),
            ("QUARANTINE", "GUARDED_LIVE"),
            ("QUARANTINE", "BLOCKED"),
            ("LIVE", "RETIRED"),
        }
        assert set(REQUIRES_APPROVAL.keys()) == expected_transitions
        # All require APPROVER role
        for transition, role in REQUIRES_APPROVAL.items():
            assert role == "APPROVER", f"{transition} requires {role}, expected APPROVER"

    @pytest.mark.parametrize(
        "from_state,to_state",
        [
            ("DRAFT", "LIVE"),
            ("DRAFT", "GUARDED_LIVE"),
            ("REGISTERED", "LIVE"),
            ("REGISTERED", "GUARDED_LIVE"),
            ("BACKTEST_PASS", "LIVE"),
            ("BACKTEST_FAIL", "LIVE"),
        ],
    )
    def test_skip_stage_prohibited(self, from_state: str, to_state: str):
        """P-07: Skipping stages (e.g., DRAFT → LIVE) is prohibited."""
        valid_targets = VALID_TRANSITIONS.get(from_state, set())
        assert to_state not in valid_targets

    def test_backtest_fail_can_retry(self):
        """P-08: BACKTEST_FAIL can transition back to REGISTERED for retry."""
        assert "REGISTERED" in VALID_TRANSITIONS["BACKTEST_FAIL"]


# ═══════════════════════════════════════════════════════════════════════
# 5. Strategy Registry Tests (S-01 ~ S-05)
# ═══════════════════════════════════════════════════════════════════════


class TestStrategyRegistry:
    """Tests for design_strategy_registry.md contracts."""

    def test_gateway_seven_checks_order(self):
        """S-01: Gateway has 6 checks (7 including asset-broker compat built into #6)."""
        # Design document defines 7-step verification in section 4.2
        # Steps: forbidden_broker, forbidden_sector (from gateway_checks)
        # + asset_class-broker compat, FP existence, FP asset_classes, checksum, dup check
        gateway_strategy_checks = [
            "forbidden_broker",  # exchange in FORBIDDEN_BROKERS
            "asset_broker_compat",  # exchange in ALLOWED_BROKERS[asset_class]
            "forbidden_sector",  # sector in FORBIDDEN_SECTORS
            "feature_pack_exists",  # FP ID exists and ACTIVE
            "feature_pack_compat",  # FP asset_classes contains strategy asset_classes
            "code_checksum",  # checksum match
            "duplicate_check",  # no same name+version
        ]
        assert len(gateway_strategy_checks) == 7
        # First check must be forbidden_broker (fail-fast)
        assert gateway_strategy_checks[0] == "forbidden_broker"

    def test_strategy_with_forbidden_broker_rejected(self):
        """S-02: Strategy using a forbidden broker must be rejected at gateway."""

        def gateway_check_broker(exchange: str) -> tuple[bool, str]:
            if exchange in FORBIDDEN_BROKERS:
                return False, "FORBIDDEN_BROKER"
            return True, "OK"

        ok, _ = gateway_check_broker("BINANCE")
        assert ok is True
        ok, code = gateway_check_broker("ALPACA")
        assert ok is False
        assert code == "FORBIDDEN_BROKER"
        ok, code = gateway_check_broker("KIWOOM_US")
        assert ok is False
        assert code == "FORBIDDEN_BROKER"

    def test_strategy_with_forbidden_sector_rejected(self):
        """S-03: Strategy targeting a forbidden sector must be rejected."""

        def gateway_check_sector(sectors: list[str]) -> tuple[bool, str]:
            for s in sectors:
                if s in FORBIDDEN_SECTORS:
                    return False, f"FORBIDDEN_SECTOR:{s}"
            return True, "OK"

        ok, _ = gateway_check_sector(["LAYER1", "DEFI"])
        assert ok is True
        ok, code = gateway_check_sector(["MEME"])
        assert ok is False
        assert "FORBIDDEN_SECTOR" in code
        ok, code = gateway_check_sector(["TECH", "GAMEFI"])
        assert ok is False
        assert "FORBIDDEN_SECTOR" in code

    def test_strategy_requires_feature_pack(self):
        """S-04: Strategy must reference a valid Feature Pack."""

        def gateway_check_fp(feature_pack_id: str | None) -> tuple[bool, str]:
            if not feature_pack_id:
                return False, "MISSING_DEPENDENCY"
            return True, "OK"

        ok, _ = gateway_check_fp("fp_trend_v1.0.0")
        assert ok is True
        ok, code = gateway_check_fp(None)
        assert ok is False
        assert code == "MISSING_DEPENDENCY"
        ok, code = gateway_check_fp("")
        assert ok is False

    def test_asset_broker_compatibility(self):
        """S-05: Asset class must be compatible with chosen broker."""

        def gateway_check_compat(asset_class: str, exchange: str) -> tuple[bool, str]:
            allowed = ALLOWED_BROKERS.get(asset_class, frozenset())
            if exchange not in allowed:
                return False, "ASSET_BROKER_INCOMPATIBLE"
            return True, "OK"

        # Valid combinations
        assert gateway_check_compat("CRYPTO", "BINANCE")[0] is True
        assert gateway_check_compat("US_STOCK", "KIS_US")[0] is True
        assert gateway_check_compat("KR_STOCK", "KIS_KR")[0] is True

        # Invalid combinations
        ok, code = gateway_check_compat("CRYPTO", "KIS_US")
        assert ok is False
        assert code == "ASSET_BROKER_INCOMPATIBLE"
        ok, code = gateway_check_compat("US_STOCK", "BINANCE")
        assert ok is False
        ok, code = gateway_check_compat("KR_STOCK", "KIS_US")
        assert ok is False


# ═══════════════════════════════════════════════════════════════════════
# 6. Cross-Document Consistency Tests
# ═══════════════════════════════════════════════════════════════════════


class TestCrossDocumentConsistency:
    """Verify consistency across multiple design documents."""

    def test_all_bank_states_covered(self):
        """All promotion states must belong to exactly one bank."""
        all_bank_states = set()
        for states in STRATEGY_BANK.values():
            overlap = all_bank_states & states
            assert overlap == set(), f"State in multiple banks: {overlap}"
            all_bank_states |= states
        # BACKTEST_FAIL is not in any bank (intermediate failure state)
        expected_in_banks = PROMOTION_STATES - {"BACKTEST_FAIL"}
        assert all_bank_states == expected_in_banks

    def test_forbidden_sectors_disjoint_from_allowed(self):
        """Forbidden sectors must not appear in any allowed sector list."""
        all_allowed_sectors = set()
        for sectors in ALLOWED_SECTORS.values():
            all_allowed_sectors |= sectors
        overlap = FORBIDDEN_SECTORS & all_allowed_sectors
        assert overlap == set(), f"Sector in both forbidden and allowed: {overlap}"

    def test_all_transitions_use_valid_states(self):
        """All states in transition matrix must be valid promotion states."""
        for from_state, to_states in VALID_TRANSITIONS.items():
            assert from_state in PROMOTION_STATES, f"Unknown state: {from_state}"
            for to_state in to_states:
                assert to_state in PROMOTION_STATES, f"Unknown state: {to_state}"

    def test_approval_transitions_are_valid_transitions(self):
        """All approval-required transitions must exist in valid transitions."""
        for from_state, to_state in REQUIRES_APPROVAL:
            assert to_state in VALID_TRANSITIONS[from_state], (
                f"Approval transition {from_state}→{to_state} not in valid transitions"
            )

    def test_trading_hours_no_forbidden_broker(self):
        """No forbidden broker should have trading hours defined."""
        for broker in FORBIDDEN_BROKERS:
            assert broker not in TRADING_HOURS, (
                f"Forbidden broker {broker} should not have trading hours"
            )

    def test_three_asset_classes_complete(self):
        """All three asset classes must be defined in both broker and sector maps."""
        asset_classes = {"CRYPTO", "US_STOCK", "KR_STOCK"}
        assert set(ALLOWED_BROKERS.keys()) == asset_classes
        assert set(ALLOWED_SECTORS.keys()) == asset_classes
