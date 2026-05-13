"""
Market State Observation Receipt Schema — F5b-LOG

Pydantic schema for structured log emission of Market State API observation
receipts. F5b stops at log emission only; DB persistence (F5c) and
decision-engine validator (F7) are separate phases.

This schema defines the receipt contract; the route emits one receipt per
result via the application logger. No DB write, no EvidenceStore write, no
response-shape change.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

SourceStatus = Literal[
    "EXCHANGE_OK",
    "EXCHANGE_FAIL",
    "SENTIMENT_FAIL",
    "INDICATOR_FAIL",
    "MIXED",
]

ValidationStatus = Literal["PASS", "INVALID_EXCHANGE", "INVALID_SYMBOL"]

FreshnessStatus = Literal["FRESH", "STALE_UNKNOWN"]

EndpointName = Literal["snapshot", "regime", "score"]


class MarketStateObservationReceipt(BaseModel):  # type: ignore[misc]
    """F5b-LOG observation receipt — emitted via structured log only.

    Admissibility rule (computed at emission time):
        admissible_for_decision = (
            validation_status == "PASS"
            and source_status == "EXCHANGE_OK"
            and error_type is None
            and freshness_status == "FRESH"
        )

    F5b does not enforce admissibility; downstream consumers (future F7
    decision-engine validator) are expected to read this field after F5c
    persistence is in place.
    """

    receipt_id: str = Field(
        description="Unique receipt id; suggested prefix `market-obs-`",
    )
    endpoint: EndpointName = Field(
        description="Market State endpoint that produced the receipt",
    )
    exchange: str = Field(
        description="User-supplied exchange (post-F3-validation)",
    )
    symbol: str = Field(
        description="User-supplied symbol (post-F3-validation)",
    )
    requested_at: str = Field(
        description="ISO-8601 UTC timestamp of request entry",
    )
    observed_at: str = Field(
        description="ISO-8601 UTC timestamp of observation; empty string if no real observation occurred",
    )
    source_status: SourceStatus = Field(
        description="Upstream data source result classification",
    )
    validation_status: ValidationStatus = Field(
        description="F3 input validation result (PASS on clean input)",
    )
    freshness_status: FreshnessStatus = Field(
        description="FRESH only when a successful real observation occurred; STALE_UNKNOWN otherwise",
    )
    error_type: Optional[str] = Field(
        description="F3 error_type or exception class name; None on success",
    )
    response_shape_version: str = Field(
        default="v1",
        description="Bump when the API success response shape changes (F5b: v1)",
    )
    admissible_for_decision: bool = Field(
        description="Future F7 gate input; TRUE only on clean success",
    )
    audit_created_at: str = Field(
        description="ISO-8601 UTC timestamp of receipt creation",
    )
    rollback_note: str = Field(
        description="Plain-text statement of how the receipt is invalidated if needed",
    )
    evidence_bundle_id: Optional[str] = Field(
        default=None,
        description="Reserved for future F5c persistence; None in F5b-LOG phase",
    )
