"""
CR-048 Observatory API Tests — L1/L2 endpoint verification.

Tests verify that CR-048 read-only observation endpoints:
1. Return correct structure and data
2. Include source_of_truth field in every response
3. Match design contract constants
4. Contain no write paths or mutation capabilities

All tests use FastAPI TestClient (no external dependencies).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_PREFIX = "/api/v1/ops/cr048"


# ═══════════════════════════════════════════════════════════════════════
# 1. Indicator Registry Endpoint
# ═══════════════════════════════════════════════════════════════════════


class TestIndicatorRegistryEndpoint:
    """GET /api/v1/ops/cr048/registry/indicators"""

    def test_returns_200(self):
        resp = client.get(f"{_PREFIX}/registry/indicators")
        assert resp.status_code == 200

    def test_has_source_of_truth(self):
        data = client.get(f"{_PREFIX}/registry/indicators").json()
        assert data["source_of_truth"] == "design_document"

    def test_returns_ten_indicators(self):
        data = client.get(f"{_PREFIX}/registry/indicators").json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    def test_all_items_design_status(self):
        data = client.get(f"{_PREFIX}/registry/indicators").json()
        for item in data["items"]:
            assert item["status"] == "DESIGN"

    def test_contains_cr038_indicators(self):
        data = client.get(f"{_PREFIX}/registry/indicators").json()
        names = {i["name"] for i in data["items"]}
        for expected in ("RSI", "MACD", "Bollinger Bands", "ATR", "OBV", "SMA", "EMA"):
            assert expected in names, f"Missing CR-038 indicator: {expected}"

    def test_contains_planned_indicators(self):
        data = client.get(f"{_PREFIX}/registry/indicators").json()
        names = {i["name"] for i in data["items"]}
        assert "ADX" in names
        assert "VWAP" in names

    def test_categories_present(self):
        data = client.get(f"{_PREFIX}/registry/indicators").json()
        cats = set(data["categories"])
        assert cats == {"MOMENTUM", "VOLATILITY", "VOLUME", "TREND", "OSCILLATOR"}

    def test_has_measured_at(self):
        data = client.get(f"{_PREFIX}/registry/indicators").json()
        assert "measured_at" in data


# ═══════════════════════════════════════════════════════════════════════
# 2. Feature Pack Registry Endpoint
# ═══════════════════════════════════════════════════════════════════════


class TestFeaturePackRegistryEndpoint:
    """GET /api/v1/ops/cr048/registry/feature-packs"""

    def test_returns_200(self):
        resp = client.get(f"{_PREFIX}/registry/feature-packs")
        assert resp.status_code == 200

    def test_has_source_of_truth(self):
        data = client.get(f"{_PREFIX}/registry/feature-packs").json()
        assert data["source_of_truth"] == "design_document"

    def test_returns_four_packs(self):
        data = client.get(f"{_PREFIX}/registry/feature-packs").json()
        assert data["total"] == 4
        assert len(data["items"]) == 4

    def test_all_items_design_status(self):
        data = client.get(f"{_PREFIX}/registry/feature-packs").json()
        for item in data["items"]:
            assert item["status"] == "DESIGN"

    def test_pack_names(self):
        data = client.get(f"{_PREFIX}/registry/feature-packs").json()
        names = {i["name"] for i in data["items"]}
        assert names == {
            "trend_pack_v1",
            "oscillator_pack_v1",
            "mean_rev_pack_v1",
            "volume_pack_v1",
        }

    def test_each_pack_has_indicators(self):
        data = client.get(f"{_PREFIX}/registry/feature-packs").json()
        for item in data["items"]:
            assert len(item["indicators"]) > 0


# ═══════════════════════════════════════════════════════════════════════
# 3. Strategy Registry Endpoint
# ═══════════════════════════════════════════════════════════════════════


class TestStrategyRegistryEndpoint:
    """GET /api/v1/ops/cr048/registry/strategies"""

    def test_returns_200(self):
        resp = client.get(f"{_PREFIX}/registry/strategies")
        assert resp.status_code == 200

    def test_has_source_of_truth(self):
        data = client.get(f"{_PREFIX}/registry/strategies").json()
        assert data["source_of_truth"] == "design_document"

    def test_returns_four_strategies(self):
        data = client.get(f"{_PREFIX}/registry/strategies").json()
        assert data["total"] == 4
        assert len(data["items"]) == 4

    def test_all_items_design_status(self):
        data = client.get(f"{_PREFIX}/registry/strategies").json()
        for item in data["items"]:
            assert item["status"] == "DESIGN"

    def test_strategy_names(self):
        data = client.get(f"{_PREFIX}/registry/strategies").json()
        names = {i["name"] for i in data["items"]}
        assert names == {"SMC+WaveTrend", "RSI Cross", "Mean Reversion", "Momentum"}

    def test_has_seven_banks(self):
        data = client.get(f"{_PREFIX}/registry/strategies").json()
        assert len(data["strategy_banks"]) == 7

    def test_smc_wavetrend_crypto_only(self):
        data = client.get(f"{_PREFIX}/registry/strategies").json()
        smc = next(i for i in data["items"] if i["name"] == "SMC+WaveTrend")
        assert smc["asset_classes"] == ["CRYPTO"]


# ═══════════════════════════════════════════════════════════════════════
# 4. Promotion States Endpoint
# ═══════════════════════════════════════════════════════════════════════


class TestPromotionStatesEndpoint:
    """GET /api/v1/ops/cr048/promotion-states"""

    def test_returns_200(self):
        resp = client.get(f"{_PREFIX}/promotion-states")
        assert resp.status_code == 200

    def test_has_source_of_truth(self):
        data = client.get(f"{_PREFIX}/promotion-states").json()
        assert data["source_of_truth"] == "design_document"

    def test_ten_states(self):
        data = client.get(f"{_PREFIX}/promotion-states").json()
        assert data["state_count"] == 10
        assert len(data["states"]) == 10

    def test_terminal_states(self):
        data = client.get(f"{_PREFIX}/promotion-states").json()
        assert set(data["terminal_states"]) == {"RETIRED", "BLOCKED"}

    def test_five_approval_required(self):
        data = client.get(f"{_PREFIX}/promotion-states").json()
        assert len(data["requires_approval"]) == 5

    def test_seven_banks(self):
        data = client.get(f"{_PREFIX}/promotion-states").json()
        assert data["bank_count"] == 7

    def test_valid_transitions_complete(self):
        data = client.get(f"{_PREFIX}/promotion-states").json()
        transitions = data["valid_transitions"]
        assert len(transitions) == 10
        # Key path: DRAFT → REGISTERED → BACKTEST_PASS → PAPER_PASS → GUARDED_LIVE → LIVE
        assert "REGISTERED" in transitions["DRAFT"]
        assert "BACKTEST_PASS" in transitions["REGISTERED"]
        assert "PAPER_PASS" in transitions["BACKTEST_PASS"]
        assert "GUARDED_LIVE" in transitions["PAPER_PASS"]
        assert "LIVE" in transitions["GUARDED_LIVE"]

    def test_blocked_no_transitions(self):
        data = client.get(f"{_PREFIX}/promotion-states").json()
        assert data["valid_transitions"]["BLOCKED"] == []

    def test_retired_no_transitions(self):
        data = client.get(f"{_PREFIX}/promotion-states").json()
        assert data["valid_transitions"]["RETIRED"] == []


# ═══════════════════════════════════════════════════════════════════════
# 5. Injection Policy Summary Endpoint
# ═══════════════════════════════════════════════════════════════════════


class TestInjectionPolicySummaryEndpoint:
    """GET /api/v1/ops/cr048/injection-policy-summary"""

    def test_returns_200(self):
        resp = client.get(f"{_PREFIX}/injection-policy-summary")
        assert resp.status_code == 200

    def test_has_source_of_truth(self):
        data = client.get(f"{_PREFIX}/injection-policy-summary").json()
        assert data["source_of_truth"] == "policy_matrix"

    def test_forbidden_brokers(self):
        data = client.get(f"{_PREFIX}/injection-policy-summary").json()
        fb = set(data["broker_matrix"]["forbidden_brokers"])
        assert fb == {"ALPACA", "KIWOOM_US"}

    def test_allowed_brokers_structure(self):
        data = client.get(f"{_PREFIX}/injection-policy-summary").json()
        ab = data["broker_matrix"]["allowed_brokers"]
        assert len(ab["CRYPTO"]) == 3
        assert len(ab["US_STOCK"]) == 1
        assert len(ab["KR_STOCK"]) == 2

    def test_forbidden_sectors_seven(self):
        data = client.get(f"{_PREFIX}/injection-policy-summary").json()
        fs = data["exclusion_baseline"]["forbidden_sectors"]
        assert len(fs) == 7

    def test_symbol_states_three(self):
        data = client.get(f"{_PREFIX}/injection-policy-summary").json()
        ss = data["exclusion_baseline"]["symbol_states"]
        assert set(ss) == {"CORE", "WATCH", "EXCLUDED"}

    def test_gateway_checks_six(self):
        data = client.get(f"{_PREFIX}/injection-policy-summary").json()
        gc = data["gateway_checks"]
        assert len(gc) == 6
        assert gc[0]["check"] == "forbidden_broker"

    def test_exposure_caps_eight(self):
        data = client.get(f"{_PREFIX}/injection-policy-summary").json()
        ec = data["exposure_caps"]
        assert len(ec) == 8

    def test_llm_permanently_forbidden(self):
        data = client.get(f"{_PREFIX}/injection-policy-summary").json()
        assert data["llm_live_path"] == "PERMANENTLY_FORBIDDEN"
        assert data["ai_execution_judgment"] == "PERMANENTLY_FORBIDDEN"

    def test_paper_shadow_min_14(self):
        data = client.get(f"{_PREFIX}/injection-policy-summary").json()
        assert data["paper_shadow_min_days"] == 14

    def test_governance_state_present(self):
        data = client.get(f"{_PREFIX}/injection-policy-summary").json()
        gs = data["governance_state"]
        assert gs["source_of_truth"] == "ops_state"
        assert "operational_mode" in gs
        assert "gate_status" in gs
        assert "allowed_scope" in gs
        assert "prohibitions" in gs

    def test_governance_state_reads_ops_state(self):
        """Governance state must reflect current ops_state.json values."""
        data = client.get(f"{_PREFIX}/injection-policy-summary").json()
        gs = data["governance_state"]
        # Current ops_state.json has GUARDED_RELEASE
        assert gs["operational_mode"] in ("BASELINE_HOLD", "GUARDED_RELEASE")

    def test_three_documents_referenced(self):
        data = client.get(f"{_PREFIX}/injection-policy-summary").json()
        assert len(data["documents"]) == 3


# ═══════════════════════════════════════════════════════════════════════
# 6. Cross-Endpoint Consistency
# ═══════════════════════════════════════════════════════════════════════


class TestCrossEndpointConsistency:
    """Verify consistency across all CR-048 observatory endpoints."""

    def test_all_endpoints_return_200(self):
        endpoints = [
            f"{_PREFIX}/registry/indicators",
            f"{_PREFIX}/registry/feature-packs",
            f"{_PREFIX}/registry/strategies",
            f"{_PREFIX}/promotion-states",
            f"{_PREFIX}/injection-policy-summary",
        ]
        for ep in endpoints:
            resp = client.get(ep)
            assert resp.status_code == 200, f"{ep} returned {resp.status_code}"

    def test_all_endpoints_have_source_of_truth(self):
        endpoints = [
            f"{_PREFIX}/registry/indicators",
            f"{_PREFIX}/registry/feature-packs",
            f"{_PREFIX}/registry/strategies",
            f"{_PREFIX}/promotion-states",
            f"{_PREFIX}/injection-policy-summary",
        ]
        for ep in endpoints:
            data = client.get(ep).json()
            assert "source_of_truth" in data, f"{ep} missing source_of_truth"

    def test_all_endpoints_have_measured_at(self):
        endpoints = [
            f"{_PREFIX}/registry/indicators",
            f"{_PREFIX}/registry/feature-packs",
            f"{_PREFIX}/registry/strategies",
            f"{_PREFIX}/promotion-states",
            f"{_PREFIX}/injection-policy-summary",
        ]
        for ep in endpoints:
            data = client.get(ep).json()
            assert "measured_at" in data, f"{ep} missing measured_at"

    def test_strategy_banks_consistent_across_endpoints(self):
        """Strategy banks in /strategies and /promotion-states must match."""
        strat_data = client.get(f"{_PREFIX}/registry/strategies").json()
        promo_data = client.get(f"{_PREFIX}/promotion-states").json()
        assert set(strat_data["strategy_banks"].keys()) == set(promo_data["strategy_banks"].keys())

    def test_no_write_endpoints_exist(self):
        """CR-048 observatory must have NO POST/PUT/PATCH/DELETE endpoints."""
        endpoints = [
            f"{_PREFIX}/registry/indicators",
            f"{_PREFIX}/registry/feature-packs",
            f"{_PREFIX}/registry/strategies",
            f"{_PREFIX}/promotion-states",
            f"{_PREFIX}/injection-policy-summary",
        ]
        for ep in endpoints:
            for method in ("post", "put", "patch"):
                resp = getattr(client, method)(ep, json={})
                assert resp.status_code == 405, (
                    f"{method.upper()} {ep} should return 405, got {resp.status_code}"
                )
            resp = client.delete(ep)
            assert resp.status_code == 405, f"DELETE {ep} should return 405, got {resp.status_code}"
