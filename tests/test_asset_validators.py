"""Tests for asset_validators.py — pure function validation.

Stage 2A, CR-048.  All tests are unit tests with no DB, no async,
no mock sessions.  Only pure function calls.

Imports: asset_validators.py only (no asset_service.py).
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.services.asset_validators import (
    check_forbidden_brokers,
    compute_candidate_ttl,
    is_excluded_sector,
    validate_broker_policy,
    validate_constitution_consistency,
    validate_status_transition,
    validate_symbol_data,
)
from app.core.constitution import (
    ALLOWED_BROKERS,
    BROKER_POLICY_RULES,
    FORBIDDEN_BROKERS,
    FORBIDDEN_SECTOR_VALUES,
    STATUS_TRANSITION_RULES,
    TTL_DEFAULTS,
    TTL_MAX_HOURS,
    TTL_MIN_HOURS,
)


# ══════════════════════════════════════════════════════════════════════
# Broker Policy Validation
# ══════════════════════════════════════════════════════════════════════


class TestCheckForbiddenBrokers:
    """Verify forbidden broker detection (pure function)."""

    def test_alpaca_detected(self):
        result = check_forbidden_brokers(["BINANCE", "ALPACA"])
        assert result == ["ALPACA"]

    def test_kiwoom_us_detected(self):
        result = check_forbidden_brokers(["KIS_US", "KIWOOM_US"])
        assert result == ["KIWOOM_US"]

    def test_multiple_forbidden(self):
        result = check_forbidden_brokers(["ALPACA", "KIWOOM_US"])
        assert set(result) == {"ALPACA", "KIWOOM_US"}

    def test_no_forbidden(self):
        result = check_forbidden_brokers(["BINANCE", "BITGET", "UPBIT"])
        assert result == []

    def test_empty_list(self):
        result = check_forbidden_brokers([])
        assert result == []

    def test_all_forbidden_brokers_covered(self):
        """Every broker in FORBIDDEN_BROKERS must be detected."""
        for broker in FORBIDDEN_BROKERS:
            result = check_forbidden_brokers([broker])
            assert result == [broker], f"{broker} not detected as forbidden"


class TestValidateBrokerPolicy:
    """Verify asset-class broker compatibility (pure function)."""

    # Crypto
    def test_crypto_binance_valid(self):
        assert validate_broker_policy(["BINANCE"], "crypto") == []

    def test_crypto_bitget_valid(self):
        assert validate_broker_policy(["BITGET"], "crypto") == []

    def test_crypto_upbit_valid(self):
        assert validate_broker_policy(["UPBIT"], "crypto") == []

    def test_crypto_kis_us_invalid(self):
        violations = validate_broker_policy(["KIS_US"], "crypto")
        assert len(violations) == 1
        assert "KIS_US" in violations[0]
        assert "crypto" in violations[0]

    def test_crypto_alpaca_forbidden(self):
        violations = validate_broker_policy(["ALPACA"], "crypto")
        assert any("forbidden" in v.lower() for v in violations)

    # US Stock
    def test_us_stock_kis_us_valid(self):
        assert validate_broker_policy(["KIS_US"], "us_stock") == []

    def test_us_stock_binance_invalid(self):
        violations = validate_broker_policy(["BINANCE"], "us_stock")
        assert len(violations) >= 1
        assert "BINANCE" in violations[0]

    # KR Stock
    def test_kr_stock_kis_kr_valid(self):
        assert validate_broker_policy(["KIS_KR"], "kr_stock") == []

    def test_kr_stock_kiwoom_kr_valid(self):
        assert validate_broker_policy(["KIWOOM_KR"], "kr_stock") == []

    def test_kr_stock_binance_invalid(self):
        violations = validate_broker_policy(["BINANCE"], "kr_stock")
        assert len(violations) >= 1

    # Unknown asset class
    def test_unknown_asset_class(self):
        violations = validate_broker_policy(["BINANCE"], "forex")
        assert any("Unknown" in v or "unknown" in v.lower() for v in violations)

    # All allowed brokers per asset class
    @pytest.mark.parametrize("asset_class", ["crypto", "us_stock", "kr_stock"])
    def test_all_allowed_brokers_pass(self, asset_class: str):
        """Every allowed broker for the asset class should pass."""
        allowed = ALLOWED_BROKERS[asset_class]
        for broker in allowed:
            violations = validate_broker_policy([broker], asset_class)
            assert violations == [], f"{broker} failed for {asset_class}: {violations}"


# ══════════════════════════════════════════════════════════════════════
# Sector Validation
# ══════════════════════════════════════════════════════════════════════


class TestIsExcludedSector:
    """Verify excluded sector detection (pure function)."""

    @pytest.mark.parametrize("sector", list(FORBIDDEN_SECTOR_VALUES))
    def test_all_excluded_sectors_detected(self, sector: str):
        assert is_excluded_sector(sector) is True

    def test_allowed_sector_not_excluded(self):
        assert is_excluded_sector("layer1") is False
        assert is_excluded_sector("defi") is False
        assert is_excluded_sector("tech") is False
        assert is_excluded_sector("semiconductor") is False

    def test_case_insensitive(self):
        assert is_excluded_sector("MEME") is True
        assert is_excluded_sector("Gamefi") is True


# ══════════════════════════════════════════════════════════════════════
# Status Transition Validation
# ══════════════════════════════════════════════════════════════════════


class TestValidateStatusTransition:
    """Verify status transition matrix (pure function, no execution)."""

    # Same-status no-ops
    @pytest.mark.parametrize("status", ["core", "watch", "excluded"])
    def test_same_status_noop(self, status: str):
        ok, reason = validate_status_transition(status, status)
        assert ok is True
        assert "no-op" in reason

    # CORE → WATCH (allowed)
    def test_core_to_watch_allowed(self):
        ok, reason = validate_status_transition("core", "watch")
        assert ok is True

    # CORE → EXCLUDED (allowed)
    def test_core_to_excluded_allowed(self):
        ok, reason = validate_status_transition("core", "excluded")
        assert ok is True

    # WATCH → CORE (allowed)
    def test_watch_to_core_allowed(self):
        ok, reason = validate_status_transition("watch", "core")
        assert ok is True

    # WATCH → EXCLUDED (allowed)
    def test_watch_to_excluded_allowed(self):
        ok, reason = validate_status_transition("watch", "excluded")
        assert ok is True

    # EXCLUDED → CORE (always forbidden)
    def test_excluded_to_core_forbidden(self):
        ok, reason = validate_status_transition("excluded", "core")
        assert ok is False
        assert "forbidden" in reason.lower()

    def test_excluded_to_core_forbidden_even_with_override(self):
        ok, reason = validate_status_transition("excluded", "core", manual_override=True)
        assert ok is False
        assert "forbidden" in reason.lower()

    # EXCLUDED → WATCH (requires manual_override)
    def test_excluded_to_watch_without_override_rejected(self):
        ok, reason = validate_status_transition("excluded", "watch")
        assert ok is False
        assert "manual_override" in reason

    def test_excluded_to_watch_with_override_allowed(self):
        ok, reason = validate_status_transition("excluded", "watch", manual_override=True)
        assert ok is True
        assert "manual_override" in reason

    # Excluded-sector symbols: can never leave EXCLUDED
    def test_excluded_sector_cannot_leave_excluded(self):
        ok, reason = validate_status_transition(
            "excluded", "watch", manual_override=True, sector="meme"
        )
        assert ok is False
        assert "exclusion baseline" in reason

    @pytest.mark.parametrize("sector", list(FORBIDDEN_SECTOR_VALUES))
    def test_all_excluded_sectors_block_transition(self, sector: str):
        ok, _ = validate_status_transition("excluded", "watch", manual_override=True, sector=sector)
        assert ok is False

    # Full 3x3 matrix (except same-status)
    def test_transition_matrix_completeness(self):
        """All 6 cross-status transitions should return definite results."""
        statuses = ["core", "watch", "excluded"]
        for current in statuses:
            for target in statuses:
                if current == target:
                    continue
                ok, reason = validate_status_transition(current, target)
                assert isinstance(ok, bool), f"({current}, {target}) returned non-bool"
                assert isinstance(reason, str), f"({current}, {target}) returned non-str"


# ══════════════════════════════════════════════════════════════════════
# TTL Computation
# ══════════════════════════════════════════════════════════════════════


class TestComputeCandidateTTL:
    """Verify TTL computation (pure function, no DB write)."""

    def test_default_crypto(self):
        ttl = compute_candidate_ttl(50.0, "crypto")
        assert isinstance(ttl, timedelta)
        assert ttl.total_seconds() > 0

    def test_perfect_score_gets_max_base(self):
        ttl = compute_candidate_ttl(100.0, "crypto")
        expected_hours = TTL_DEFAULTS["crypto"]  # 100% of base
        assert ttl == timedelta(hours=expected_hours)

    def test_zero_score_gets_half_base(self):
        ttl = compute_candidate_ttl(0.0, "crypto")
        expected_hours = TTL_DEFAULTS["crypto"] * 0.5  # 50% of base
        # Must be at least TTL_MIN_HOURS
        expected_hours = max(TTL_MIN_HOURS, expected_hours)
        assert ttl == timedelta(hours=expected_hours)

    def test_us_stock_base_different(self):
        ttl_crypto = compute_candidate_ttl(50.0, "crypto")
        ttl_us = compute_candidate_ttl(50.0, "us_stock")
        # us_stock has 72h base vs crypto 48h base
        assert ttl_us > ttl_crypto

    def test_min_hours_enforced(self):
        ttl = compute_candidate_ttl(0.0, "crypto")
        assert ttl >= timedelta(hours=TTL_MIN_HOURS)

    def test_max_hours_enforced(self):
        ttl = compute_candidate_ttl(100.0, "us_stock")
        assert ttl <= timedelta(hours=TTL_MAX_HOURS)

    def test_negative_score_clamped(self):
        ttl = compute_candidate_ttl(-50.0, "crypto")
        ttl_zero = compute_candidate_ttl(0.0, "crypto")
        assert ttl == ttl_zero  # negative clamped to 0

    def test_over_100_score_clamped(self):
        ttl = compute_candidate_ttl(200.0, "crypto")
        ttl_100 = compute_candidate_ttl(100.0, "crypto")
        assert ttl == ttl_100  # >100 clamped to 100

    @pytest.mark.parametrize("asset_class", ["crypto", "us_stock", "kr_stock"])
    def test_all_asset_classes_produce_valid_ttl(self, asset_class: str):
        ttl = compute_candidate_ttl(50.0, asset_class)
        assert timedelta(hours=TTL_MIN_HOURS) <= ttl <= timedelta(hours=TTL_MAX_HOURS)


# ══════════════════════════════════════════════════════════════════════
# Symbol Data Validation
# ══════════════════════════════════════════════════════════════════════


class TestValidateSymbolData:
    """Verify symbol data pre-validation (pure function)."""

    def test_valid_crypto_symbol(self):
        errors = validate_symbol_data(
            {
                "symbol": "SOL/USDT",
                "name": "Solana",
                "asset_class": "crypto",
                "sector": "layer1",
                "exchanges": ["BINANCE"],
            }
        )
        assert errors == []

    def test_valid_us_stock(self):
        errors = validate_symbol_data(
            {
                "symbol": "NVDA",
                "name": "NVIDIA Corp",
                "asset_class": "us_stock",
                "sector": "tech",
                "exchanges": ["KIS_US"],
            }
        )
        assert errors == []

    def test_missing_required_fields(self):
        errors = validate_symbol_data({"symbol": "SOL/USDT", "name": "Solana"})
        assert len(errors) >= 3  # asset_class, sector, exchanges
        assert any("asset_class" in e for e in errors)
        assert any("sector" in e for e in errors)
        assert any("exchanges" in e for e in errors)

    def test_empty_exchanges(self):
        errors = validate_symbol_data(
            {
                "symbol": "SOL/USDT",
                "name": "Solana",
                "asset_class": "crypto",
                "sector": "layer1",
                "exchanges": [],
            }
        )
        assert any("empty" in e.lower() for e in errors)

    def test_forbidden_broker_in_exchanges(self):
        errors = validate_symbol_data(
            {
                "symbol": "SOL/USDT",
                "name": "Solana",
                "asset_class": "crypto",
                "sector": "layer1",
                "exchanges": ["ALPACA"],
            }
        )
        assert any("forbidden" in e.lower() for e in errors)

    def test_excluded_sector_forces_status_warning(self):
        errors = validate_symbol_data(
            {
                "symbol": "DOGE/USDT",
                "name": "Dogecoin",
                "asset_class": "crypto",
                "sector": "meme",
                "exchanges": ["BINANCE"],
                "status": "watch",
            }
        )
        assert any("exclusion baseline" in e.lower() for e in errors)

    def test_excluded_sector_with_excluded_status_no_warning(self):
        errors = validate_symbol_data(
            {
                "symbol": "DOGE/USDT",
                "name": "Dogecoin",
                "asset_class": "crypto",
                "sector": "meme",
                "exchanges": ["BINANCE"],
                "status": "excluded",
            }
        )
        # No warning because status is already excluded
        assert not any("exclusion baseline" in e.lower() for e in errors)

    def test_incompatible_broker_for_asset_class(self):
        errors = validate_symbol_data(
            {
                "symbol": "AAPL",
                "name": "Apple",
                "asset_class": "us_stock",
                "sector": "tech",
                "exchanges": ["BINANCE"],  # Wrong broker for us_stock
            }
        )
        assert any("BINANCE" in e for e in errors)


# ══════════════════════════════════════════════════════════════════════
# Constitution Consistency
# ══════════════════════════════════════════════════════════════════════


class TestConstitutionConsistency:
    """Verify internal consistency of constitution constants."""

    def test_no_inconsistencies(self):
        issues = validate_constitution_consistency()
        assert issues == [], f"Constitution inconsistencies: {issues}"

    def test_broker_policy_covers_all_asset_classes(self):
        """BROKER_POLICY_RULES must cover all asset classes in ALLOWED_BROKERS."""
        for ac in ALLOWED_BROKERS:
            assert ac in BROKER_POLICY_RULES, f"Missing {ac} in BROKER_POLICY_RULES"

    def test_broker_policy_allowed_matches(self):
        """BROKER_POLICY_RULES.allowed must match ALLOWED_BROKERS for each."""
        for ac, rules in BROKER_POLICY_RULES.items():
            assert rules["allowed"] == ALLOWED_BROKERS[ac], f"Mismatch for {ac}"

    def test_broker_policy_forbidden_matches(self):
        """BROKER_POLICY_RULES.forbidden must match FORBIDDEN_BROKERS."""
        for ac, rules in BROKER_POLICY_RULES.items():
            assert rules["forbidden"] == FORBIDDEN_BROKERS

    def test_forbidden_sectors_all_lowercase(self):
        for v in FORBIDDEN_SECTOR_VALUES:
            assert v == v.lower(), f"Non-lowercase forbidden sector: {v}"

    def test_status_transition_rules_complete(self):
        """All 6 cross-status transitions must be defined."""
        statuses = ["core", "watch", "excluded"]
        for current in statuses:
            for target in statuses:
                if current == target:
                    continue
                key = (current, target)
                assert key in STATUS_TRANSITION_RULES, f"Missing rule: {key}"

    def test_ttl_defaults_all_asset_classes(self):
        """TTL_DEFAULTS must cover all asset classes."""
        for ac in ALLOWED_BROKERS:
            assert ac in TTL_DEFAULTS, f"Missing TTL default for {ac}"
            assert TTL_DEFAULTS[ac] >= TTL_MIN_HOURS
            assert TTL_DEFAULTS[ac] <= TTL_MAX_HOURS
