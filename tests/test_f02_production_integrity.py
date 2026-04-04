"""
Card F-02: Production Integrity Audit — Automated enforcement tests

Purpose:
  Verify production state matches frozen baseline.
  Detect configuration drift, boundary violations,
  and governance erosion in production.

No production code changes. Test-only audit card.

NOTE: This entire module requires APP_ENV=production.
      Skipped in CI where APP_ENV defaults to 'development'.
"""

from pathlib import Path
import os

import pytest

# Skip entire module when not in production environment (e.g. CI)
pytestmark = pytest.mark.skipif(
    os.environ.get("APP_ENV", "development") != "production",
    reason="F-02 production integrity audit requires APP_ENV=production",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS = PROJECT_ROOT / "docs"
APP = PROJECT_ROOT / "app"


# ===========================================================================
# F02-1: Phase and config verification
# ===========================================================================
class TestF02PhaseConfig:
    def test_app_env_production(self):
        """APP_ENV must be production."""
        from app.core.config import Settings

        s = Settings()
        assert s.app_env == "production", f"APP_ENV={s.app_env}, expected production"

    def test_is_production_true(self):
        from app.core.config import Settings

        s = Settings()
        assert s.is_production is True

    def test_debug_disabled(self):
        from app.core.config import Settings

        s = Settings()
        assert s.debug is False

    def test_governance_enabled(self):
        from app.core.config import Settings

        s = Settings()
        assert s.governance_enabled is True

    def test_evidence_path_set(self):
        from app.core.config import Settings

        s = Settings()
        assert s.evidence_db_path != "", "Evidence DB path must be set in production"

    def test_receipt_path_set(self):
        from app.core.config import Settings

        s = Settings()
        assert s.receipt_file_path != "", "Receipt file path must be set in production"

    def test_log_path_set(self):
        from app.core.config import Settings

        s = Settings()
        assert s.log_file_path != "", "Log file path must be set in production"

    def test_no_default_secret_key(self):
        from app.core.config import Settings

        s = Settings()
        assert s.secret_key != "change-me-in-production", (
            "Secret key must not be default in production"
        )


# ===========================================================================
# F02-2: Constitution documents
# ===========================================================================
class TestF02ConstitutionDocs:
    def test_constitution(self):
        assert (DOCS / "system_final_constitution.md").exists()

    def test_law_freeze(self):
        assert (DOCS / "system_law_freeze.md").exists()

    def test_production_freeze(self):
        assert (DOCS / "f01_production_freeze.md").exists()


# ===========================================================================
# F02-3: Law documents
# ===========================================================================
class TestF02LawDocs:
    def test_change_protocol(self):
        assert (DOCS / "law_change_protocol.md").exists()

    def test_emergency_override(self):
        assert (DOCS / "law_emergency_override.md").exists()

    def test_audit_law(self):
        assert (DOCS / "law_audit.md").exists()

    def test_phase_law(self):
        assert (DOCS / "law_phase.md").exists()


# ===========================================================================
# F02-4: Seal documents
# ===========================================================================
class TestF02SealDocs:
    def test_retry_seal(self):
        assert (DOCS / "retry_layer_final_seal.md").exists()

    def test_notification_seal(self):
        assert (DOCS / "notification_layer_seal.md").exists()

    def test_execution_seal(self):
        assert (DOCS / "execution_layer_seal.md").exists()

    def test_engine_seal(self):
        assert (DOCS / "engine_layer_seal.md").exists()

    def test_governance_seal(self):
        assert (DOCS / "governance_layer_seal.md").exists()


# ===========================================================================
# F02-5: Prod operational docs
# ===========================================================================
class TestF02ProdDocs:
    def test_prod_runbook(self):
        assert (DOCS / "prod_operational_runbook.md").exists()

    def test_prod_config_guide(self):
        assert (DOCS / "prod_configuration_guide.md").exists()

    def test_prod_rollback(self):
        assert (DOCS / "prod_rollback_override_procedure.md").exists()


# ===========================================================================
# F02-6: Audit/boundary tests present
# ===========================================================================
class TestF02AuditPresence:
    def test_a01_audit_exists(self):
        assert (PROJECT_ROOT / "tests" / "test_a01_constitution_audit.py").exists()

    def test_c40_boundary_exists(self):
        assert (PROJECT_ROOT / "tests" / "test_c40_execution_boundary_lock.py").exists()


# ===========================================================================
# F02-7: No illegal execution path
# ===========================================================================
class TestF02ExecutionIntegrity:
    def test_execute_single_plan_defined_once(self):
        core_files = list((APP / "core").glob("*.py"))
        defining = [
            f.name
            for f in core_files
            if "def execute_single_plan(" in f.read_text(encoding="utf-8")
        ]
        assert defining == ["retry_executor.py"]

    def test_orchestrator_no_direct_sender(self):
        content = (APP / "core" / "auto_retry_orchestrator.py").read_text(encoding="utf-8")
        lines = [
            l for l in content.split("\n") if "get_sender" in l and not l.strip().startswith("#")
        ]
        assert len(lines) == 0


# ===========================================================================
# F02-8: No forbidden patterns
# ===========================================================================
class TestF02ForbiddenPatterns:
    def _scan(self, pattern):
        hits = []
        for fpath in APP.rglob("*.py"):
            content = fpath.read_text(encoding="utf-8")
            parts = content.split('"""')
            body = parts[-1] if len(parts) >= 3 else content
            if pattern in body:
                hits.append(fpath.name)
        return hits

    def test_no_chain_of_thought(self):
        assert self._scan("chain_of_thought") == []

    def test_no_raw_prompt(self):
        assert self._scan("raw_prompt") == []

    def test_no_internal_reasoning(self):
        assert self._scan("internal_reasoning") == []

    def test_no_debug_trace(self):
        assert self._scan("debug_trace") == []


# ===========================================================================
# F02-9: No dev/staging config drift
# ===========================================================================
class TestF02NoDrift:
    def test_not_development(self):
        from app.core.config import Settings

        s = Settings()
        assert s.app_env != "development"

    def test_not_staging(self):
        from app.core.config import Settings

        s = Settings()
        assert s.app_env != "staging"

    def test_data_dir_exists(self):
        assert (PROJECT_ROOT / "data").is_dir()

    def test_logs_dir_exists(self):
        assert (PROJECT_ROOT / "logs").is_dir()


# ===========================================================================
# F02-10: Production integrity classification
# ===========================================================================
class TestF02IntegrityClassification:
    def test_all_checks_pass(self):
        """
        Meta-test: if this file runs without failures,
        production integrity is INTACT.
        If any test above fails, integrity is DRIFT.
        """
        pass  # This test exists to make the classification explicit
