"""
Tests for Runtime Immutability Zone — bundle contracts, hash computation,
runtime verification, drift detection, and ledger recording.

Coverage:
  - Canonical serialization stability
  - Hash determinism (same input → same hash)
  - All 4 bundle types: Strategy, Feature Pack, Broker Policy, Risk Limit
  - Load-time mismatch → refuse load
  - Runtime drift detection
  - False positive prevention (identical reload OK)
  - drift_severity per bundle type
  - canonical_snapshot preservation
  - SM-3 candidate flagging
  - DriftLedgerEntry model instantiation
"""

from __future__ import annotations

import json
import pytest

from app.services.runtime_bundle import (
    BundleType,
    DriftSeverity,
    BUNDLE_SEVERITY,
    BundleManifest,
    build_strategy_manifest,
    build_feature_pack_manifest,
    build_broker_policy_manifest,
    build_risk_limit_manifest,
    compute_hash,
    _canonicalize,
)
from app.services.runtime_verifier import (
    RuntimeBundleStore,
    DriftEvent,
    DriftAction,
    get_bundle_store,
    reset_bundle_store,
)
from app.models.drift_ledger import (
    DriftLedgerEntry,
    DriftAction as LedgerDriftAction,
    DriftSeverity as LedgerDriftSeverity,
    BundleType as LedgerBundleType,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def store():
    """Fresh RuntimeBundleStore for each test."""
    return RuntimeBundleStore()


@pytest.fixture(autouse=True)
def reset_global_store():
    """Ensure singleton is clean between tests."""
    reset_bundle_store()
    yield
    reset_bundle_store()


def _sample_strategy_manifest(**overrides):
    defaults = dict(
        name="smc_wavetrend_v3",
        version="3.0.0",
        compute_module="strategies.smc_wavetrend",
        feature_pack_id="fp-001",
        checksum="abc123def456",
        asset_classes=["crypto"],
        exchanges=["BINANCE", "UPBIT"],
        sectors=["LAYER1", "DEFI"],
        timeframes=["1h", "4h"],
        regimes=["trending_up"],
        max_symbols=10,
    )
    defaults.update(overrides)
    return build_strategy_manifest(**defaults)


def _sample_fp_manifest(**overrides):
    defaults = dict(
        name="trend_pack_v1",
        version="1.0.0",
        indicator_ids=["ind-001", "ind-002"],
        weights={"ind-001": 1.0, "ind-002": 0.5},
        checksum="fp_checksum_xyz",
    )
    defaults.update(overrides)
    return build_feature_pack_manifest(**defaults)


def _sample_broker_manifest():
    return build_broker_policy_manifest(
        allowed_brokers={
            "crypto": frozenset({"BINANCE", "BITGET", "UPBIT"}),
            "us_stock": frozenset({"KIS_US"}),
            "kr_stock": frozenset({"KIS_KR", "KIWOOM_KR"}),
        },
        forbidden_brokers=frozenset({"ALPACA", "KIWOOM_US"}),
    )


def _sample_risk_manifest():
    return build_risk_limit_manifest(
        exposure_limits={
            "max_strategies_per_market": 5,
            "max_strategies_per_symbol": 3,
            "max_concurrent_strategy_symbol": 30,
            "max_symbols_per_market": 20,
            "max_symbols_per_theme": 5,
            "max_single_symbol_pct": 10,
            "max_single_theme_pct": 25,
            "max_single_market_pct": 50,
        }
    )


# ── Canonical Serialization ──────────────────────────────────────────


class TestCanonicalSerialization:
    def test_sorted_keys(self):
        result = _canonicalize({"z": 1, "a": 2, "m": 3})
        assert result == '{"a":2,"m":3,"z":1}'

    def test_no_whitespace(self):
        result = _canonicalize({"key": "value"})
        assert " " not in result

    def test_nested_sort(self):
        result = _canonicalize({"b": {"z": 1, "a": 2}})
        parsed = json.loads(result)
        inner_keys = list(parsed["b"].keys())
        assert inner_keys == ["a", "z"]

    def test_determinism(self):
        """Same input must always produce same output."""
        d = {"x": [3, 1, 2], "a": "hello"}
        assert _canonicalize(d) == _canonicalize(d)

    def test_list_order_preserved(self):
        result = _canonicalize({"items": [3, 1, 2]})
        assert json.loads(result)["items"] == [3, 1, 2]


# ── Hash Computation ─────────────────────────────────────────────────


class TestHashComputation:
    def test_deterministic_hash(self):
        text = '{"a":1,"b":2}'
        assert compute_hash(text) == compute_hash(text)

    def test_different_input_different_hash(self):
        assert compute_hash('{"a":1}') != compute_hash('{"a":2}')

    def test_hash_is_sha256_hex(self):
        h = compute_hash("test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ── Strategy Bundle ──────────────────────────────────────────────────


class TestStrategyBundle:
    def test_build_manifest(self):
        m = _sample_strategy_manifest()
        assert m.bundle_type == BundleType.STRATEGY
        assert m.severity == DriftSeverity.HIGH
        assert len(m.hash) == 64
        assert m.canonical_json  # non-empty

    def test_field_order_irrelevant(self):
        """Exchanges in different order must produce same hash."""
        m1 = _sample_strategy_manifest(exchanges=["BINANCE", "UPBIT"])
        m2 = _sample_strategy_manifest(exchanges=["UPBIT", "BINANCE"])
        assert m1.hash == m2.hash

    def test_asset_class_order_irrelevant(self):
        m1 = _sample_strategy_manifest(asset_classes=["crypto", "us_stock"])
        m2 = _sample_strategy_manifest(asset_classes=["us_stock", "crypto"])
        assert m1.hash == m2.hash

    def test_sectors_order_irrelevant(self):
        m1 = _sample_strategy_manifest(sectors=["DEFI", "LAYER1"])
        m2 = _sample_strategy_manifest(sectors=["LAYER1", "DEFI"])
        assert m1.hash == m2.hash

    def test_version_change_changes_hash(self):
        m1 = _sample_strategy_manifest(version="3.0.0")
        m2 = _sample_strategy_manifest(version="3.0.1")
        assert m1.hash != m2.hash

    def test_compute_module_change_changes_hash(self):
        m1 = _sample_strategy_manifest(compute_module="strategies.smc_wavetrend")
        m2 = _sample_strategy_manifest(compute_module="strategies.smc_wavetrend_v2")
        assert m1.hash != m2.hash

    def test_none_sectors_excluded(self):
        m = _sample_strategy_manifest(sectors=None)
        payload = json.loads(m.canonical_json)
        assert "sectors" not in payload

    def test_none_checksum_excluded(self):
        m = _sample_strategy_manifest(checksum=None)
        payload = json.loads(m.canonical_json)
        assert "checksum" not in payload

    def test_max_symbols_change_changes_hash(self):
        m1 = _sample_strategy_manifest(max_symbols=10)
        m2 = _sample_strategy_manifest(max_symbols=20)
        assert m1.hash != m2.hash

    def test_repeated_build_same_hash(self):
        """Stability: building the same manifest twice yields identical hash."""
        m1 = _sample_strategy_manifest()
        m2 = _sample_strategy_manifest()
        assert m1.hash == m2.hash


# ── Feature Pack Bundle ──────────────────────────────────────────────


class TestFeaturePackBundle:
    def test_build_manifest(self):
        m = _sample_fp_manifest()
        assert m.bundle_type == BundleType.FEATURE_PACK
        assert m.severity == DriftSeverity.MEDIUM
        assert len(m.hash) == 64

    def test_indicator_order_irrelevant(self):
        m1 = _sample_fp_manifest(indicator_ids=["ind-001", "ind-002"])
        m2 = _sample_fp_manifest(indicator_ids=["ind-002", "ind-001"])
        assert m1.hash == m2.hash

    def test_weight_change_changes_hash(self):
        m1 = _sample_fp_manifest(weights={"ind-001": 1.0, "ind-002": 0.5})
        m2 = _sample_fp_manifest(weights={"ind-001": 1.0, "ind-002": 0.8})
        assert m1.hash != m2.hash

    def test_added_indicator_changes_hash(self):
        m1 = _sample_fp_manifest(indicator_ids=["ind-001", "ind-002"])
        m2 = _sample_fp_manifest(indicator_ids=["ind-001", "ind-002", "ind-003"])
        assert m1.hash != m2.hash

    def test_none_weights_excluded(self):
        m = _sample_fp_manifest(weights=None)
        payload = json.loads(m.canonical_json)
        assert "weights" not in payload

    def test_repeated_build_same_hash(self):
        m1 = _sample_fp_manifest()
        m2 = _sample_fp_manifest()
        assert m1.hash == m2.hash


# ── Broker Policy Bundle ─────────────────────────────────────────────


class TestBrokerPolicyBundle:
    def test_build_manifest(self):
        m = _sample_broker_manifest()
        assert m.bundle_type == BundleType.BROKER_POLICY
        assert m.severity == DriftSeverity.HIGH
        assert len(m.hash) == 64

    def test_allowed_brokers_order_irrelevant(self):
        m1 = build_broker_policy_manifest(
            allowed_brokers={"crypto": {"BINANCE", "UPBIT"}, "us_stock": {"KIS_US"}},
            forbidden_brokers={"ALPACA"},
        )
        m2 = build_broker_policy_manifest(
            allowed_brokers={"us_stock": {"KIS_US"}, "crypto": {"UPBIT", "BINANCE"}},
            forbidden_brokers={"ALPACA"},
        )
        assert m1.hash == m2.hash

    def test_forbidden_broker_change_changes_hash(self):
        m1 = build_broker_policy_manifest(
            allowed_brokers={"crypto": {"BINANCE"}},
            forbidden_brokers={"ALPACA"},
        )
        m2 = build_broker_policy_manifest(
            allowed_brokers={"crypto": {"BINANCE"}},
            forbidden_brokers={"ALPACA", "KIWOOM_US"},
        )
        assert m1.hash != m2.hash

    def test_added_allowed_broker_changes_hash(self):
        m1 = build_broker_policy_manifest(
            allowed_brokers={"crypto": {"BINANCE"}},
            forbidden_brokers={"ALPACA"},
        )
        m2 = build_broker_policy_manifest(
            allowed_brokers={"crypto": {"BINANCE", "BITGET"}},
            forbidden_brokers={"ALPACA"},
        )
        assert m1.hash != m2.hash

    def test_repeated_build_same_hash(self):
        m1 = _sample_broker_manifest()
        m2 = _sample_broker_manifest()
        assert m1.hash == m2.hash


# ── Risk Limit Bundle ────────────────────────────────────────────────


class TestRiskLimitBundle:
    def test_build_manifest(self):
        m = _sample_risk_manifest()
        assert m.bundle_type == BundleType.RISK_LIMIT
        assert m.severity == DriftSeverity.CRITICAL
        assert len(m.hash) == 64

    def test_limit_change_changes_hash(self):
        m1 = build_risk_limit_manifest({"max_single_symbol_pct": 10})
        m2 = build_risk_limit_manifest({"max_single_symbol_pct": 15})
        assert m1.hash != m2.hash

    def test_key_order_irrelevant(self):
        m1 = build_risk_limit_manifest({"a": 1, "b": 2})
        m2 = build_risk_limit_manifest({"b": 2, "a": 1})
        assert m1.hash == m2.hash

    def test_repeated_build_same_hash(self):
        m1 = _sample_risk_manifest()
        m2 = _sample_risk_manifest()
        assert m1.hash == m2.hash


# ── Severity Mapping ─────────────────────────────────────────────────


class TestDriftSeverity:
    def test_strategy_severity_high(self):
        assert BUNDLE_SEVERITY[BundleType.STRATEGY] == DriftSeverity.HIGH

    def test_feature_pack_severity_medium(self):
        assert BUNDLE_SEVERITY[BundleType.FEATURE_PACK] == DriftSeverity.MEDIUM

    def test_broker_policy_severity_high(self):
        assert BUNDLE_SEVERITY[BundleType.BROKER_POLICY] == DriftSeverity.HIGH

    def test_risk_limit_severity_critical(self):
        assert BUNDLE_SEVERITY[BundleType.RISK_LIMIT] == DriftSeverity.CRITICAL


# ── Runtime Verifier: Load-Time ──────────────────────────────────────


class TestLoadTimeVerification:
    def test_first_load_registers(self, store: RuntimeBundleStore):
        m = _sample_strategy_manifest()
        event = store.verify_load("strat-001", m)
        assert event is None
        assert store.is_registered("strat-001")

    def test_identical_reload_passes(self, store: RuntimeBundleStore):
        """False positive prevention: reloading same manifest is OK."""
        m = _sample_strategy_manifest()
        store.verify_load("strat-001", m)
        event = store.verify_load("strat-001", m)
        assert event is None  # No drift

    def test_mismatch_refuses_load(self, store: RuntimeBundleStore):
        m1 = _sample_strategy_manifest(version="3.0.0")
        m2 = _sample_strategy_manifest(version="3.0.1")  # changed
        store.verify_load("strat-001", m1)
        event = store.verify_load("strat-001", m2)
        assert event is not None
        assert event.action == DriftAction.REFUSE_LOAD
        assert event.expected_hash == m1.hash
        assert event.observed_hash == m2.hash
        assert event.sm3_candidate is True

    def test_mismatch_records_event(self, store: RuntimeBundleStore):
        m1 = _sample_strategy_manifest(version="3.0.0")
        m2 = _sample_strategy_manifest(version="3.0.1")
        store.verify_load("strat-001", m1)
        store.verify_load("strat-001", m2)
        assert len(store.drift_events) == 1

    def test_mismatch_preserves_canonical_snapshot(self, store: RuntimeBundleStore):
        m1 = _sample_strategy_manifest(version="3.0.0")
        m2 = _sample_strategy_manifest(version="3.0.1")
        store.verify_load("strat-001", m1)
        event = store.verify_load("strat-001", m2)
        assert event.canonical_snapshot == m2.canonical_json

    def test_multiple_bundles_independent(self, store: RuntimeBundleStore):
        s = _sample_strategy_manifest()
        fp = _sample_fp_manifest()
        store.verify_load("strat-001", s)
        store.verify_load("fp-001", fp)
        assert store.is_registered("strat-001")
        assert store.is_registered("fp-001")


# ── Runtime Verifier: Periodic Integrity ─────────────────────────────


class TestPeriodicIntegrity:
    def test_no_drift(self, store: RuntimeBundleStore):
        m = _sample_broker_manifest()
        store.register("broker-policy", m)
        event = store.verify_integrity("broker-policy", m)
        assert event is None

    def test_drift_detected(self, store: RuntimeBundleStore):
        m1 = _sample_risk_manifest()
        store.register("risk-limits", m1)
        m2 = build_risk_limit_manifest({"max_single_symbol_pct": 99})
        event = store.verify_integrity("risk-limits", m2)
        assert event is not None
        assert event.action == DriftAction.RUNTIME_DRIFT_DETECTED
        assert event.severity == DriftSeverity.CRITICAL
        assert event.sm3_candidate is True

    def test_unregistered_key_skipped(self, store: RuntimeBundleStore):
        m = _sample_strategy_manifest()
        event = store.verify_integrity("nonexistent", m)
        assert event is None

    def test_drift_event_count(self, store: RuntimeBundleStore):
        m1 = _sample_strategy_manifest(version="3.0.0")
        store.register("strat-001", m1)
        m2 = _sample_strategy_manifest(version="3.0.1")
        m3 = _sample_strategy_manifest(version="3.0.2")
        store.verify_integrity("strat-001", m2)
        store.verify_integrity("strat-001", m3)
        assert len(store.drift_events) == 2

    def test_count_recent_drifts(self, store: RuntimeBundleStore):
        m1 = _sample_strategy_manifest(version="3.0.0")
        store.register("strat-001", m1)
        m2 = _sample_strategy_manifest(version="3.0.1")
        store.verify_integrity("strat-001", m2)
        count = store.count_recent_drifts(BundleType.STRATEGY, within_hours=24)
        assert count == 1


# ── Runtime Verifier: Store Operations ───────────────────────────────


class TestStoreOperations:
    def test_unregister(self, store: RuntimeBundleStore):
        m = _sample_strategy_manifest()
        store.register("strat-001", m)
        assert store.is_registered("strat-001")
        store.unregister("strat-001")
        assert not store.is_registered("strat-001")

    def test_registered_keys(self, store: RuntimeBundleStore):
        store.register("a", _sample_strategy_manifest())
        store.register("b", _sample_fp_manifest())
        keys = store.registered_keys()
        assert "a" in keys
        assert "b" in keys

    def test_clear_events(self, store: RuntimeBundleStore):
        m1 = _sample_strategy_manifest(version="3.0.0")
        store.register("strat-001", m1)
        m2 = _sample_strategy_manifest(version="3.0.1")
        store.verify_integrity("strat-001", m2)
        assert len(store.drift_events) == 1
        store.clear_events()
        assert len(store.drift_events) == 0

    def test_get_manifest(self, store: RuntimeBundleStore):
        m = _sample_strategy_manifest()
        store.register("strat-001", m)
        retrieved = store.get_manifest("strat-001")
        assert retrieved is not None
        assert retrieved.hash == m.hash

    def test_get_manifest_missing(self, store: RuntimeBundleStore):
        assert store.get_manifest("nonexistent") is None


# ── Singleton ────────────────────────────────────────────────────────


class TestGlobalSingleton:
    def test_get_bundle_store_returns_same_instance(self):
        s1 = get_bundle_store()
        s2 = get_bundle_store()
        assert s1 is s2

    def test_reset_creates_new_instance(self):
        s1 = get_bundle_store()
        reset_bundle_store()
        s2 = get_bundle_store()
        assert s1 is not s2


# ── Drift Ledger Model ──────────────────────────────────────────────


class TestDriftLedgerModel:
    def test_create_entry(self):
        entry = DriftLedgerEntry(
            bundle_type=LedgerBundleType.STRATEGY,
            expected_hash="a" * 64,
            observed_hash="b" * 64,
            action=LedgerDriftAction.REFUSE_LOAD,
            sm3_candidate=True,
            severity=LedgerDriftSeverity.HIGH,
            canonical_snapshot='{"name":"test"}',
        )
        assert entry.bundle_type == LedgerBundleType.STRATEGY
        assert entry.sm3_candidate is True
        assert entry.severity == LedgerDriftSeverity.HIGH

    def test_bundle_type_enum(self):
        assert LedgerBundleType.STRATEGY.value == "strategy"
        assert LedgerBundleType.FEATURE_PACK.value == "feature_pack"
        assert LedgerBundleType.BROKER_POLICY.value == "broker_policy"
        assert LedgerBundleType.RISK_LIMIT.value == "risk_limit"

    def test_drift_action_enum(self):
        assert LedgerDriftAction.REFUSE_LOAD.value == "refuse_load"
        assert LedgerDriftAction.QUARANTINE_CANDIDATE.value == "quarantine_candidate"
        assert LedgerDriftAction.RUNTIME_DRIFT_DETECTED.value == "runtime_drift_detected"

    def test_severity_enum(self):
        assert LedgerDriftSeverity.CRITICAL.value == "critical"
        assert LedgerDriftSeverity.HIGH.value == "high"
        assert LedgerDriftSeverity.MEDIUM.value == "medium"


# ── Cross-Bundle Serialization Drift Prevention ──────────────────────


class TestSerializationStability:
    """Verify that the same logical input always produces the same hash,
    regardless of Python dict ordering or set iteration order."""

    def test_strategy_100_iterations(self):
        """Build the same strategy manifest 100 times, hash must be stable."""
        hashes = set()
        for _ in range(100):
            m = _sample_strategy_manifest()
            hashes.add(m.hash)
        assert len(hashes) == 1

    def test_feature_pack_100_iterations(self):
        hashes = set()
        for _ in range(100):
            m = _sample_fp_manifest()
            hashes.add(m.hash)
        assert len(hashes) == 1

    def test_broker_policy_100_iterations(self):
        hashes = set()
        for _ in range(100):
            m = _sample_broker_manifest()
            hashes.add(m.hash)
        assert len(hashes) == 1

    def test_risk_limit_100_iterations(self):
        hashes = set()
        for _ in range(100):
            m = _sample_risk_manifest()
            hashes.add(m.hash)
        assert len(hashes) == 1
