"""Tests for asset model/enum/schema Stage 2A additions.

Stage 2A, CR-048.  Verifies:
  - SymbolStatusAudit model static definition
  - Constitution new constants structure
  - Schema new response models
  - Cross-consistency between model enums and constitution

No asset_service.py imports.  No DB sessions.
"""

from __future__ import annotations

import pytest

from app.models.asset import (
    AssetSector,
    SymbolStatus,
    SymbolStatusReason,
    ScreeningStageReason,
    SymbolStatusAudit,
    Symbol,
    ScreeningResult,
    EXCLUDED_SECTORS,
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
from app.schemas.asset_schema import (
    BrokerPolicyValidationResponse,
    StatusTransitionValidationResponse,
    CandidateTTLResponse,
    SymbolDataValidationResponse,
    SymbolStatusAuditRead,
    SymbolCreate,
    SymbolRead,
)


# ══════════════════════════════════════════════════════════════════════
# SymbolStatusAudit Model
# ══════════════════════════════════════════════════════════════════════


class TestSymbolStatusAuditModel:
    """Verify SymbolStatusAudit table definition (static, no DB)."""

    def test_tablename(self):
        assert SymbolStatusAudit.__tablename__ == "symbol_status_audits"

    def test_required_columns(self):
        cols = {c.name for c in SymbolStatusAudit.__table__.columns}
        required = {
            "id",
            "symbol_id",
            "symbol",
            "from_status",
            "to_status",
            "reason_code",
            "reason_detail",
            "triggered_by",
            "approval_level",
            "context",
            "transitioned_at",
        }
        assert required.issubset(cols), f"Missing columns: {required - cols}"

    def test_primary_key_is_id(self):
        pk_cols = [c.name for c in SymbolStatusAudit.__table__.primary_key.columns]
        assert pk_cols == ["id"]

    def test_indexes_on_symbol_id_and_symbol(self):
        indexed = {c.name for c in SymbolStatusAudit.__table__.columns if c.index}
        assert "symbol_id" in indexed
        assert "symbol" in indexed

    def test_append_only_pattern(self):
        """SymbolStatusAudit should NOT have updated_at column (append-only)."""
        cols = {c.name for c in SymbolStatusAudit.__table__.columns}
        assert "updated_at" not in cols, "Audit table should be append-only"


# ══════════════════════════════════════════════════════════════════════
# Constitution New Constants
# ══════════════════════════════════════════════════════════════════════


class TestConstitutionNewConstants:
    """Verify new constants added in Stage 2A."""

    def test_broker_policy_rules_is_dict(self):
        assert isinstance(BROKER_POLICY_RULES, dict)
        assert len(BROKER_POLICY_RULES) >= 3

    def test_broker_policy_rules_structure(self):
        for ac, rules in BROKER_POLICY_RULES.items():
            assert "allowed" in rules, f"Missing 'allowed' in {ac}"
            assert "forbidden" in rules, f"Missing 'forbidden' in {ac}"
            assert isinstance(rules["allowed"], frozenset)
            assert isinstance(rules["forbidden"], frozenset)

    def test_ttl_defaults_is_dict(self):
        assert isinstance(TTL_DEFAULTS, dict)
        assert len(TTL_DEFAULTS) >= 3

    def test_ttl_defaults_values_in_range(self):
        for ac, hours in TTL_DEFAULTS.items():
            assert TTL_MIN_HOURS <= hours <= TTL_MAX_HOURS, (
                f"TTL for {ac}={hours} out of range [{TTL_MIN_HOURS}, {TTL_MAX_HOURS}]"
            )

    def test_ttl_bounds(self):
        assert TTL_MIN_HOURS == 12
        assert TTL_MAX_HOURS == 168  # 7 days

    def test_status_transition_rules_is_dict(self):
        assert isinstance(STATUS_TRANSITION_RULES, dict)
        assert len(STATUS_TRANSITION_RULES) >= 6

    def test_status_transition_rules_keys_are_tuples(self):
        for key in STATUS_TRANSITION_RULES:
            assert isinstance(key, tuple)
            assert len(key) == 2
            assert all(isinstance(s, str) for s in key)

    def test_excluded_to_core_is_forbidden(self):
        assert STATUS_TRANSITION_RULES[("excluded", "core")] == "forbidden"


# ══════════════════════════════════════════════════════════════════════
# Model Enum Cross-Consistency
# ══════════════════════════════════════════════════════════════════════


class TestEnumConstitutionConsistency:
    """Verify model enums match constitution constants."""

    def test_excluded_sectors_match_forbidden_sector_values(self):
        """EXCLUDED_SECTORS (model) must match FORBIDDEN_SECTOR_VALUES (constitution)."""
        model_values = {s.value for s in EXCLUDED_SECTORS}
        assert model_values == FORBIDDEN_SECTOR_VALUES

    def test_symbol_status_has_3_states(self):
        assert len(SymbolStatus) == 3
        assert SymbolStatus.CORE.value == "core"
        assert SymbolStatus.WATCH.value == "watch"
        assert SymbolStatus.EXCLUDED.value == "excluded"

    def test_status_reason_covers_transitions(self):
        """SymbolStatusReason should have reasons for all major transitions."""
        reason_values = {r.value for r in SymbolStatusReason}
        # EXCLUDED reasons
        assert "exclusion_baseline" in reason_values
        assert "manual_exclusion" in reason_values
        # WATCH reasons
        assert "ttl_expired" in reason_values
        assert "regime_change" in reason_values
        assert "core_demoted" in reason_values
        # CORE reasons
        assert "screening_full_pass" in reason_values

    def test_screening_stage_reasons_complete(self):
        """All 5 screening stages should have at least one reason."""
        values = {r.value for r in ScreeningStageReason}
        # Stage 1
        assert "excluded_sector" in values
        # Stage 2
        assert "low_volume" in values
        # Stage 3
        assert "low_adx" in values
        # Stage 4
        assert "high_per" in values
        # Stage 5
        assert "insufficient_bars" in values
        # Success
        assert "all_stages_passed" in values

    def test_asset_sector_contains_all_excluded(self):
        """Every excluded sector in constitution must exist as AssetSector enum."""
        for v in FORBIDDEN_SECTOR_VALUES:
            assert v in [s.value for s in AssetSector], f"Missing AssetSector: {v}"


# ══════════════════════════════════════════════════════════════════════
# Schema New Response Models
# ══════════════════════════════════════════════════════════════════════


class TestNewSchemaModels:
    """Verify Stage 2A Pydantic response schemas."""

    def test_broker_policy_response_fields(self):
        r = BrokerPolicyValidationResponse(
            exchanges=["BINANCE"],
            asset_class="crypto",
            violations=[],
            valid=True,
        )
        assert r.exchanges == ["BINANCE"]
        assert r.valid is True

    def test_broker_policy_response_with_violations(self):
        r = BrokerPolicyValidationResponse(
            exchanges=["ALPACA"],
            asset_class="crypto",
            violations=["ALPACA is forbidden"],
            valid=False,
        )
        assert r.valid is False
        assert len(r.violations) == 1

    def test_status_transition_response(self):
        r = StatusTransitionValidationResponse(
            current_status="core",
            target_status="watch",
            allowed=True,
            reason="ttl_expired",
        )
        assert r.allowed is True

    def test_candidate_ttl_response(self):
        r = CandidateTTLResponse(
            score=75.0,
            asset_class="crypto",
            ttl_hours=42.0,
            ttl_min_hours=12,
            ttl_max_hours=168,
        )
        assert r.ttl_hours == 42.0

    def test_symbol_data_validation_response(self):
        r = SymbolDataValidationResponse(errors=[], valid=True)
        assert r.valid is True

    def test_symbol_data_validation_response_with_errors(self):
        r = SymbolDataValidationResponse(
            errors=["missing field: name"],
            valid=False,
        )
        assert r.valid is False

    def test_symbol_status_audit_read(self):
        from datetime import datetime

        r = SymbolStatusAuditRead(
            id="audit-001",
            symbol_id="sym-001",
            symbol="SOL/USDT",
            from_status="core",
            to_status="watch",
            reason_code="ttl_expired",
            reason_detail=None,
            triggered_by="system",
            approval_level=None,
            context=None,
            transitioned_at=datetime(2026, 4, 4, 12, 0, 0),
        )
        assert r.from_status == "core"
        assert r.to_status == "watch"

    def test_existing_schemas_unchanged(self):
        """Verify SymbolCreate and SymbolRead still have expected fields."""
        create_fields = set(SymbolCreate.model_fields.keys())
        assert "symbol" in create_fields
        assert "asset_class" in create_fields
        assert "sector" in create_fields
        assert "exchanges" in create_fields

        read_fields = set(SymbolRead.model_fields.keys())
        assert "status" in read_fields
        assert "candidate_expire_at" in read_fields
        assert "manual_override" in read_fields


# ══════════════════════════════════════════════════════════════════════
# Import Safety
# ══════════════════════════════════════════════════════════════════════


class TestImportSafety:
    """Verify Stage 2A files do NOT import asset_service.py in source."""

    def test_this_test_file_does_not_import_asset_service(self):
        """This test file's top-level imports must not include asset_service."""
        import ast
        import pathlib

        src = pathlib.Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "asset_service" not in node.module, (
                    f"Found import from {node.module} in test file"
                )
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "asset_service" not in alias.name, (
                        f"Found import of {alias.name} in test file"
                    )

    def test_asset_validators_source_does_not_import_asset_service(self):
        """asset_validators.py source must not import asset_service."""
        import inspect
        import app.services.asset_validators as validators_module

        source = inspect.getsource(validators_module)
        assert "from app.services.asset_service" not in source
        assert "import app.services.asset_service" not in source
        # Also verify no symbol_screener or backtest_qualification imports
        assert "symbol_screener" not in source
        assert "backtest_qualification" not in source
