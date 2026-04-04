"""Asset Validators — pure functions for Symbol validation.

Stage 2A, CR-048.  ALL functions in this module are:
  - Pure: (input) -> (output), no side effects
  - DB-free: no AsyncSession, no ORM instances
  - Network-free: no HTTP, no exchange, no cache
  - Import-safe: only constitution.py and model enums (no asset_service.py)

These validators are designed to be called from asset_service.py in Stage 2B,
or from tests/schemas independently.
"""

from __future__ import annotations

from datetime import timedelta

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


# ── Broker Policy Validation ────────────────────────────────────────


def check_forbidden_brokers(exchanges: list[str]) -> list[str]:
    """Return list of forbidden brokers found in the given exchanges.

    Pure function.  No DB access.

    >>> check_forbidden_brokers(["BINANCE", "ALPACA"])
    ['ALPACA']
    >>> check_forbidden_brokers(["BINANCE", "BITGET"])
    []
    """
    return [e for e in exchanges if e.upper() in FORBIDDEN_BROKERS]


def validate_broker_policy(
    exchanges: list[str],
    asset_class: str,
) -> list[str]:
    """Validate exchanges against allowed brokers for the given asset class.

    Returns list of violation descriptions (empty = valid).
    Pure function.  No DB access.

    >>> validate_broker_policy(["KIS_US"], "crypto")
    ['KIS_US is not allowed for crypto (allowed: BINANCE, BITGET, UPBIT)']
    """
    violations: list[str] = []

    # Check forbidden brokers first
    forbidden = check_forbidden_brokers(exchanges)
    for fb in forbidden:
        violations.append(f"{fb} is a forbidden broker")

    # Check asset-class compatibility
    ac = asset_class.lower()
    allowed = ALLOWED_BROKERS.get(ac, frozenset())
    if not allowed:
        violations.append(f"Unknown asset class: {asset_class}")
        return violations

    for ex in exchanges:
        ex_upper = ex.upper()
        if ex_upper not in FORBIDDEN_BROKERS and ex_upper not in allowed:
            sorted_allowed = sorted(allowed)
            violations.append(
                f"{ex} is not allowed for {ac} (allowed: {', '.join(sorted_allowed)})"
            )

    return violations


# ── Sector Validation ────────────────────────────────────────────────


def is_excluded_sector(sector: str) -> bool:
    """Check if a sector is in the exclusion baseline.

    Pure function.  No DB access.

    >>> is_excluded_sector("meme")
    True
    >>> is_excluded_sector("layer1")
    False
    """
    return sector.lower() in FORBIDDEN_SECTOR_VALUES


# ── Status Transition Validation ────────────────────────────────────


def validate_status_transition(
    current_status: str,
    target_status: str,
    manual_override: bool = False,
    sector: str | None = None,
) -> tuple[bool, str]:
    """Validate whether a status transition is allowed.

    Returns (allowed: bool, reason: str).
    Pure function.  Does NOT execute the transition.

    Rules:
      1. Same-status transitions are no-ops (allowed).
      2. EXCLUDED-sector symbols can never leave EXCLUDED.
      3. EXCLUDED→CORE is always forbidden (no direct promotion).
      4. EXCLUDED→WATCH requires manual_override.
      5. All other transitions follow STATUS_TRANSITION_RULES.

    >>> validate_status_transition("core", "watch")
    (True, 'transition allowed: ttl_expired|regime_change|screening_fail')
    >>> validate_status_transition("excluded", "core", manual_override=True)
    (False, 'EXCLUDED to CORE direct transition is forbidden')
    """
    current = current_status.lower()
    target = target_status.lower()

    # Same-status: no-op
    if current == target:
        return True, "no-op: same status"

    # Excluded-sector: can never leave EXCLUDED
    if sector and is_excluded_sector(sector) and target != "excluded":
        return False, (
            f"sector {sector} is in exclusion baseline; "
            f"cannot transition from EXCLUDED to {target.upper()}"
        )

    # EXCLUDED→CORE: always forbidden
    if current == "excluded" and target == "core":
        return False, "EXCLUDED to CORE direct transition is forbidden"

    # EXCLUDED→WATCH: requires manual_override
    if current == "excluded" and target == "watch":
        if not manual_override:
            return False, ("EXCLUDED to WATCH requires manual_override=True (A approval required)")
        return True, "transition allowed with manual_override"

    # Look up transition rule
    key = (current, target)
    rule = STATUS_TRANSITION_RULES.get(key)
    if rule is None:
        return False, f"transition {current.upper()} to {target.upper()} is not defined"
    if rule == "forbidden":
        return False, f"{current.upper()} to {target.upper()} direct transition is forbidden"

    return True, f"transition allowed: {rule}"


# ── TTL Computation ──────────────────────────────────────────────────


def compute_candidate_ttl(
    score: float = 0.0,
    asset_class: str = "crypto",
) -> timedelta:
    """Compute candidate TTL based on screening score and asset class.

    Returns a timedelta.  Does NOT write to DB.
    Higher scores get longer TTL (up to TTL_MAX_HOURS).
    Lower scores get shorter TTL (down to TTL_MIN_HOURS).

    Policy: base_hours * (0.5 + 0.5 * normalized_score)
    where normalized_score = clamp(score, 0, 100) / 100

    >>> compute_candidate_ttl(100.0, "crypto")
    datetime.timedelta(days=2)
    >>> compute_candidate_ttl(0.0, "crypto")
    datetime.timedelta(seconds=86400)
    """
    ac = asset_class.lower()
    base_hours = TTL_DEFAULTS.get(ac, 48)

    # Normalize score to [0, 1]
    norm = max(0.0, min(100.0, score)) / 100.0

    # Scale: 50% to 100% of base hours
    hours = base_hours * (0.5 + 0.5 * norm)

    # Clamp to global bounds
    hours = max(TTL_MIN_HOURS, min(TTL_MAX_HOURS, hours))

    return timedelta(hours=hours)


# ── Symbol Data Validation ───────────────────────────────────────────


def validate_symbol_data(data: dict) -> list[str]:
    """Pre-validate symbol registration data.

    Returns list of error descriptions (empty = valid).
    Pure function.  No DB access.

    Checks:
      - Required fields present (symbol, name, asset_class, sector, exchanges)
      - Exchanges not empty
      - Broker policy valid for asset class
      - Excluded sector → forces EXCLUDED status warning

    >>> validate_symbol_data({"symbol": "SOL/USDT", "name": "Solana"})
    ['missing required field: asset_class', 'missing required field: sector', 'missing required field: exchanges']
    """
    errors: list[str] = []

    # Required fields
    for field in ("symbol", "name", "asset_class", "sector", "exchanges"):
        if field not in data or data[field] is None:
            errors.append(f"missing required field: {field}")

    if errors:
        return errors  # Can't validate further without required fields

    # Exchanges must not be empty
    exchanges = data["exchanges"]
    if isinstance(exchanges, str):
        import json

        try:
            exchanges = json.loads(exchanges)
        except (json.JSONDecodeError, TypeError):
            errors.append("exchanges must be a JSON array of broker codes")
            return errors

    if not exchanges:
        errors.append("exchanges must not be empty")

    # Broker policy validation
    if exchanges:
        broker_violations = validate_broker_policy(exchanges, str(data["asset_class"]))
        errors.extend(broker_violations)

    # Excluded sector warning (not an error, but flagged)
    sector = str(data["sector"]).lower()
    if is_excluded_sector(sector):
        status = data.get("status", "")
        if isinstance(status, str):
            status = status.lower()
        else:
            status = getattr(status, "value", str(status)).lower()
        if status != "excluded":
            errors.append(
                f"sector {sector} is in exclusion baseline; status will be forced to EXCLUDED"
            )

    return errors


# ── Cross-Validation Helpers ─────────────────────────────────────────


def validate_constitution_consistency() -> list[str]:
    """Verify internal consistency of constitution constants.

    Cross-checks:
      - BROKER_POLICY_RULES.allowed == ALLOWED_BROKERS for each asset class
      - BROKER_POLICY_RULES.forbidden == FORBIDDEN_BROKERS for each
      - All forbidden sectors in FORBIDDEN_SECTOR_VALUES are lowercase

    Returns list of inconsistencies (empty = consistent).
    """
    issues: list[str] = []

    # Check BROKER_POLICY_RULES vs ALLOWED_BROKERS
    for ac, rules in BROKER_POLICY_RULES.items():
        expected_allowed = ALLOWED_BROKERS.get(ac, frozenset())
        if rules["allowed"] != expected_allowed:
            issues.append(
                f"BROKER_POLICY_RULES[{ac}].allowed != ALLOWED_BROKERS[{ac}]: "
                f"{rules['allowed']} vs {expected_allowed}"
            )
        if rules["forbidden"] != FORBIDDEN_BROKERS:
            issues.append(
                f"BROKER_POLICY_RULES[{ac}].forbidden != FORBIDDEN_BROKERS: "
                f"{rules['forbidden']} vs {FORBIDDEN_BROKERS}"
            )

    # Check all asset classes covered
    for ac in ALLOWED_BROKERS:
        if ac not in BROKER_POLICY_RULES:
            issues.append(f"ALLOWED_BROKERS has {ac} but BROKER_POLICY_RULES does not")

    # Check forbidden sector values are lowercase
    for v in FORBIDDEN_SECTOR_VALUES:
        if v != v.lower():
            issues.append(f"FORBIDDEN_SECTOR_VALUES contains non-lowercase: {v}")

    return issues
