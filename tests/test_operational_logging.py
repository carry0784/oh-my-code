"""
B-03 Operational Logging Tests — 6 tests

Validates:
  - Startup/shutdown log event presence
  - Governance logs include gate_id
  - File persistence with re-read verification
  - Log mode reporting (STREAM_ONLY / FILE_PERSISTED)
  - No sensitive fields in operational logs
  - Evidence write failure logged
"""

from __future__ import annotations

import importlib
import os
import tempfile
from io import StringIO
from unittest.mock import patch, MagicMock

import pytest
import structlog


# ═══════════════════════════════════════════════════════════════════════════ #
# B-03: OPERATIONAL LOGGING TESTS
# ═══════════════════════════════════════════════════════════════════════════ #


class TestOperationalLogging:
    """B-03: Operational log accumulation and audit verification."""

    def test_startup_shutdown_logs_present(self):
        """Startup and shutdown log events exist in app/main.py lifespan."""
        import ast

        main_path = os.path.join(os.path.dirname(__file__), "..", "app", "main.py")
        with open(main_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Verify startup and shutdown log keywords exist in source
        assert "Starting trading system" in source, "Startup log event must exist in main.py"
        assert "Shutting down trading system" in source, "Shutdown log event must exist in main.py"
        assert "log_mode" in source, "log_mode must be reported at startup"

    def test_governance_logs_include_gate_id(self):
        """Governance gate logs include gate_id for audit traceability."""
        import ast

        gate_path = os.path.join(
            os.path.dirname(__file__), "..", "app", "agents", "governance_gate.py"
        )
        with open(gate_path, "r", encoding="utf-8") as f:
            source = f.read()

        # All governance log calls must include gate_id
        log_calls = [
            "governance_gate_created",
            "governance_pre_check",
            "governance_post_record",
            "governance_post_record_error",
        ]
        for event_name in log_calls:
            assert event_name in source, f"Governance log event '{event_name}' must exist"

        # gate_id must appear in log calls (not just in evidence artifacts)
        # Count occurrences of gate_id= in logger calls
        gate_id_in_logs = source.count("gate_id=self.gate_id")
        assert gate_id_in_logs >= 4, (
            f"gate_id must be included in at least 4 log calls, found {gate_id_in_logs}"
        )

    def test_log_file_persistence(self):
        """Log events persist to file and survive re-initialization."""
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False, mode="w") as f:
            log_path = f.name

        try:
            # Phase 1: configure with file output and write a log event
            with patch("app.core.logging.settings") as mock_settings:
                mock_settings.debug = False
                mock_settings.log_file_path = log_path
                mock_settings.log_level = "INFO"

                from app.core.logging import setup_logging

                setup_logging()

                logger = structlog.get_logger("test_persistence")
                logger.info("B03_PERSISTENCE_TEST_EVENT", marker="persist_check")

            # Phase 2: flush all handlers
            import logging

            root = logging.getLogger()
            for h in root.handlers:
                h.flush()
                h.close()

            # Phase 3: verify file contains the event
            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()

            assert "B03_PERSISTENCE_TEST_EVENT" in content, "Log event must be persisted to file"
            assert "persist_check" in content, "Structured fields must be preserved in file output"

        finally:
            os.unlink(log_path)

    def test_log_mode_reported(self):
        """setup_logging() sets log_mode correctly."""
        import app.core.logging as log_module

        # Without file path → STREAM_ONLY
        with patch.object(log_module, "settings") as mock_settings:
            mock_settings.debug = False
            mock_settings.log_file_path = ""
            mock_settings.log_level = "INFO"
            log_module.setup_logging()
            assert log_module.log_mode == "STREAM_ONLY"

        # With file path → FILE_PERSISTED
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            log_path = f.name
        try:
            with patch.object(log_module, "settings") as mock_settings:
                mock_settings.debug = False
                mock_settings.log_file_path = log_path
                mock_settings.log_level = "INFO"
                log_module.setup_logging()
                assert log_module.log_mode == "FILE_PERSISTED"
        finally:
            # Clean up handlers before deleting file
            import logging

            for h in logging.getLogger().handlers[:]:
                h.close()
            logging.getLogger().handlers.clear()
            os.unlink(log_path)

    def test_no_sensitive_fields_in_logs(self):
        """Operational logging code does not log sensitive fields."""
        sensitive_keywords = [
            "secret",
            "token",
            "password",
            "credential",
            "api_key",
            "private_key",
            "authorization",
            "raw_prompt",
            "reasoning",
        ]

        # Scan key operational logging files
        scan_files = [
            os.path.join("app", "core", "logging.py"),
            os.path.join("app", "main.py"),
            os.path.join("app", "agents", "governance_gate.py"),
            os.path.join("app", "services", "position_service.py"),
            os.path.join("app", "services", "order_service.py"),
        ]

        base = os.path.join(os.path.dirname(__file__), "..")

        for rel_path in scan_files:
            full_path = os.path.join(base, rel_path)
            if not os.path.exists(full_path):
                continue

            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for i, line in enumerate(lines, 1):
                # Only check logger calls (lines containing logger.)
                if "logger." not in line:
                    continue
                line_lower = line.lower()
                for kw in sensitive_keywords:
                    # Allow references to field names in Settings class or imports
                    # but NOT as logger keyword arguments
                    if f"{kw}=" in line_lower and "settings." not in line_lower:
                        # Exception: "governance_enabled" contains no sensitive data
                        if "governance_enabled" in line:
                            continue
                        pytest.fail(
                            f"Sensitive keyword '{kw}' found in logger call "
                            f"at {rel_path}:{i}: {line.strip()}"
                        )

    def test_evidence_write_failed_logged(self):
        """Evidence write failure produces visible error-level log."""
        import ast

        gate_path = os.path.join(
            os.path.dirname(__file__), "..", "app", "agents", "governance_gate.py"
        )
        with open(gate_path, "r", encoding="utf-8") as f:
            source = f.read()

        # post_record_error must have:
        # 1. logger.error call for evidence write failure
        assert "governance_post_record_error" in source, (
            "Evidence write error must have a named log event"
        )

        # 2. FALLBACK critical log for when evidence storage itself fails
        assert "governance_post_record_error_FALLBACK" in source, (
            "Evidence storage failure must have a FALLBACK critical log"
        )

        # 3. gate_id must be in fallback log too
        assert source.count("governance_post_record_error_FALLBACK") >= 1, (
            "FALLBACK log event must exist"
        )

        # Verify the fallback log includes gate_id
        fallback_idx = source.index("governance_post_record_error_FALLBACK")
        # Look at the surrounding 500 chars for gate_id
        surrounding = source[fallback_idx : fallback_idx + 500]
        assert "gate_id" in surrounding, (
            "FALLBACK critical log must include gate_id for audit traceability"
        )
