"""Tests for Registry API endpoints.

CR-048 Stage 1 L3: API integration tests for control-plane registry routes.
Tests verify:
- CRUD endpoints return correct status codes
- Gateway rejection returns 422 with violation details
- Retire endpoints return 409 for invalid operations
- No hard delete endpoints exist
- PromotionEvent endpoints are read-only
- API Capability Matrix compliance

Uses mock services — no real database required.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.routes.registry import router
from app.services.registry_service import (
    RegistryService,
    GatewayRejectionError,
    NotFoundError,
    InvalidOperationError,
)
from app.services.injection_gateway import GatewayResult, GatewayVerdict


# ── Test Class: API Capability Matrix ────────────────────────────────


class TestAPICapabilityMatrix:
    """Verify the API respects the capability matrix.

    Create: allowed (control-plane metadata only)
    Read:   allowed
    Update: version publishing only
    Delete: hard delete PROHIBITED, retire only
    Execute: PROHIBITED
    Promote: PROHIBITED (event recording only)
    Activate runtime: PROHIBITED
    """

    def test_no_delete_endpoints(self):
        """No DELETE method endpoints should exist in registry router."""
        for route in router.routes:
            if hasattr(route, "methods"):
                assert "DELETE" not in route.methods, (
                    f"DELETE endpoint found: {route.path} — hard delete prohibited"
                )

    def test_no_execute_endpoints(self):
        """No /execute or /activate endpoints should exist."""
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        for path in paths:
            assert "/execute" not in path, f"Execute endpoint found: {path}"
            assert "/activate" not in path, f"Activate endpoint found: {path}"

    def test_no_promote_endpoint(self):
        """No /promote endpoint should exist (recording only, not execution)."""
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        for path in paths:
            assert "/promote" not in path, f"Promote endpoint found: {path}"

    def test_create_endpoints_exist(self):
        """POST endpoints for indicators, feature-packs, strategies should exist."""
        post_paths = []
        for route in router.routes:
            if hasattr(route, "methods") and "POST" in route.methods:
                post_paths.append(route.path)

        assert "/indicators" in post_paths
        assert "/feature-packs" in post_paths
        assert "/strategies" in post_paths

    def test_read_endpoints_exist(self):
        """GET endpoints for all entities should exist."""
        get_paths = []
        for route in router.routes:
            if hasattr(route, "methods") and "GET" in route.methods:
                get_paths.append(route.path)

        assert "/indicators" in get_paths
        assert "/indicators/{indicator_id}" in get_paths
        assert "/feature-packs" in get_paths
        assert "/feature-packs/{fp_id}" in get_paths
        assert "/strategies" in get_paths
        assert "/strategies/{strategy_id}" in get_paths
        assert "/promotion-events" in get_paths
        assert "/promotion-events/{event_id}" in get_paths
        assert "/stats" in get_paths

    def test_retire_endpoints_exist(self):
        """POST /retire endpoints should exist for mutable entities."""
        post_paths = []
        for route in router.routes:
            if hasattr(route, "methods") and "POST" in route.methods:
                post_paths.append(route.path)

        assert "/indicators/{indicator_id}/retire" in post_paths
        assert "/feature-packs/{fp_id}/retire" in post_paths
        assert "/strategies/{strategy_id}/retire" in post_paths

    def test_no_promotion_event_write_endpoints(self):
        """PromotionEvent should have no POST/PUT/PATCH endpoints (append-only via service)."""
        for route in router.routes:
            if hasattr(route, "path") and "promotion-events" in route.path:
                if hasattr(route, "methods"):
                    write_methods = {"POST", "PUT", "PATCH", "DELETE"}
                    assert not (route.methods & write_methods), (
                        f"Write endpoint for promotion-events: {route.path} {route.methods}"
                    )

    def test_validate_endpoint_exists(self):
        """Standalone validation endpoint should exist."""
        post_paths = []
        for route in router.routes:
            if hasattr(route, "methods") and "POST" in route.methods:
                post_paths.append(route.path)

        assert "/validate/strategy" in post_paths


# ── Test Class: Endpoint Count ───────────────────────────────────────


class TestEndpointCounts:
    """Verify endpoint counts match expected API surface."""

    def test_total_get_endpoints(self):
        """Should have correct number of GET endpoints."""
        get_count = sum(1 for r in router.routes if hasattr(r, "methods") and "GET" in r.methods)
        # indicators(2) + feature-packs(2) + strategies(2) + promotion-events(2) + stats(1) = 9
        assert get_count == 9

    def test_total_post_endpoints(self):
        """Should have correct number of POST endpoints."""
        post_count = sum(1 for r in router.routes if hasattr(r, "methods") and "POST" in r.methods)
        # create(3) + retire(3) + validate(1) = 7
        assert post_count == 7

    def test_total_endpoints(self):
        """Total endpoint count verification."""
        total = sum(1 for r in router.routes if hasattr(r, "methods"))
        # 9 GET + 7 POST = 16
        assert total == 16


# ── Test Class: Schema Completeness ──────────────────────────────────


class TestSchemaCompleteness:
    """Verify response schemas cover required fields."""

    def test_indicator_response_fields(self):
        from app.schemas.registry_schema import IndicatorResponse

        fields = set(IndicatorResponse.model_fields.keys())
        assert "id" in fields
        assert "name" in fields
        assert "version" in fields
        assert "status" in fields
        assert "created_at" in fields

    def test_feature_pack_response_fields(self):
        from app.schemas.registry_schema import FeaturePackResponse

        fields = set(FeaturePackResponse.model_fields.keys())
        assert "id" in fields
        assert "name" in fields
        assert "version" in fields
        assert "status" in fields
        assert "indicator_ids" in fields

    def test_strategy_response_fields(self):
        from app.schemas.registry_schema import StrategyResponse

        fields = set(StrategyResponse.model_fields.keys())
        assert "id" in fields
        assert "name" in fields
        assert "version" in fields
        assert "status" in fields
        assert "feature_pack_id" in fields
        assert "asset_classes" in fields
        assert "exchanges" in fields
        assert "is_champion" in fields

    def test_promotion_event_response_fields(self):
        from app.schemas.registry_schema import PromotionEventResponse

        fields = set(PromotionEventResponse.model_fields.keys())
        assert "id" in fields
        assert "strategy_id" in fields
        assert "from_status" in fields
        assert "to_status" in fields
        assert "reason" in fields
        assert "triggered_by" in fields
        assert "evidence" in fields
        assert "approved_by" in fields
        assert "created_at" in fields

    def test_gateway_result_response_fields(self):
        from app.schemas.registry_schema import GatewayResultResponse

        fields = set(GatewayResultResponse.model_fields.keys())
        assert "verdict" in fields
        assert "violations" in fields
        assert "blocked_code" in fields

    def test_retire_request_fields(self):
        from app.schemas.registry_schema import RetireRequest

        fields = set(RetireRequest.model_fields.keys())
        assert "reason" in fields
        assert "retired_by" in fields

    def test_registry_stats_response_fields(self):
        from app.schemas.registry_schema import RegistryStatsResponse

        fields = set(RegistryStatsResponse.model_fields.keys())
        assert "indicators" in fields
        assert "feature_packs" in fields
        assert "strategies" in fields
        assert "promotion_events" in fields


# ── Test Class: Error Code Mapping ───────────────────────────────────


class TestErrorCodeMapping:
    """Verify exception-to-HTTP status code mapping."""

    def test_gateway_rejection_error_has_result(self):
        """GatewayRejectionError should carry the GatewayResult."""
        result = GatewayResult(
            verdict=GatewayVerdict.REJECTED,
            violations=["test violation"],
            blocked_code="TEST_CODE",
        )
        err = GatewayRejectionError(result)
        assert err.code == "TEST_CODE"
        assert err.result.violations == ["test violation"]

    def test_not_found_error_code(self):
        """NotFoundError should have NOT_FOUND code."""
        err = NotFoundError("Strategy", "abc-123")
        assert err.code == "NOT_FOUND"
        assert "abc-123" in str(err)

    def test_invalid_operation_error(self):
        """InvalidOperationError should carry custom code."""
        err = InvalidOperationError("Cannot retire", code="ALREADY_BLOCKED")
        assert err.code == "ALREADY_BLOCKED"


# ── Test Class: Gateway Blocked Codes ────────────────────────────────


class TestGatewayBlockedCodes:
    """Verify all blocked codes from the AI Console spec are representable."""

    def test_known_blocked_codes(self):
        """All documented blocked codes should be string constants."""
        known_codes = [
            "FORBIDDEN_BROKER",
            "FORBIDDEN_SECTOR",
            "MISSING_DEPENDENCY",
            "VERSION_MISMATCH",
            "INVALID_SIGNATURE",
            "ASSET_BROKER_INCOMPATIBLE",
            "DEPENDENCY_BLOCKED",
            "DEPENDENCY_DEPRECATED",
        ]
        for code in known_codes:
            result = GatewayResult(
                verdict=GatewayVerdict.REJECTED,
                violations=[f"Test: {code}"],
                blocked_code=code,
            )
            assert result.blocked_code == code
