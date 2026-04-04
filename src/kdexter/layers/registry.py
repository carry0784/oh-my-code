"""
Layer Registry — K-Dexter AOS v4

Central registry for L1~L30 layer instances.
Each layer has a lifecycle (INIT → READY → RUNNING → STOPPED → ERROR)
and health status tracked by this registry.

Layers are:
  - Registered at system startup
  - Started/stopped by B2 Orchestration
  - Health-checked by L28 Loop Monitor
  - Attributed to governance tiers (B1/B2/A) per governance_layer_map.md

The registry does NOT own layer implementations — it holds references
and manages lifecycle state. Actual layer logic lives in their own modules.

SSOT for layer names: docs/architecture/governance_layer_map.md Section 2.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any, Protocol


# ─────────────────────────────────────────────────────────────────────────── #
# Layer lifecycle
# ─────────────────────────────────────────────────────────────────────────── #


class LayerStatus(Enum):
    """Lifecycle status of a layer instance."""

    REGISTERED = "REGISTERED"  # registered but not yet initialized
    INIT = "INIT"  # initializing
    READY = "READY"  # initialized, waiting to start
    RUNNING = "RUNNING"  # actively running
    STOPPED = "STOPPED"  # gracefully stopped
    ERROR = "ERROR"  # encountered an error


class HealthStatus(Enum):
    """Health of a running layer."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


# ─────────────────────────────────────────────────────────────────────────── #
# Layer protocol — what a layer implementation must provide
# ─────────────────────────────────────────────────────────────────────────── #


class LayerProtocol(Protocol):
    """
    Interface a layer implementation should satisfy.
    Not all layers need to implement all methods — the registry
    uses duck typing and gracefully handles missing methods.
    """

    async def init(self) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def health_check(self) -> HealthStatus: ...


# ─────────────────────────────────────────────────────────────────────────── #
# Layer descriptor
# ─────────────────────────────────────────────────────────────────────────── #


@dataclass
class LayerDescriptor:
    """Metadata and runtime state for a registered layer."""

    layer_id: str  # "L1" ~ "L30"
    name: str  # human-readable name
    governance_tier: str  # "B1", "B2", "A"
    status: LayerStatus = LayerStatus.REGISTERED
    health: HealthStatus = HealthStatus.UNKNOWN
    instance: Optional[Any] = None  # actual layer object
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    error_message: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────── #
# Layer catalog (governance_layer_map.md Section 2 SSOT)
# ─────────────────────────────────────────────────────────────────────────── #

_LAYER_CATALOG: list[tuple[str, str, str]] = [
    ("L1", "Human Decision", "B1"),
    ("L2", "Doctrine & Policy", "B1"),
    ("L3", "Security & Isolation", "B1"),
    ("L4", "Clarify & Spec", "B2"),
    ("L5", "Harness / Scheduler", "B2"),
    ("L6", "Parallel Agent", "A"),
    ("L7", "Evaluation", "A"),
    ("L8", "Execution Cell", "A"),
    ("L9", "Self-Improvement Engine", "B2"),
    ("L10", "Audit / Evidence Store", "A"),
    ("L11", "Rule Ledger", "B2"),
    ("L12", "Rule Provenance Store", "B2"),
    ("L13", "Compliance Engine", "B2"),
    ("L14", "Operation Evolution", "B2"),
    ("L15", "Intent Drift Engine", "B2"),
    ("L16", "Rule Conflict Engine", "B2"),
    ("L17", "Failure Pattern Memory", "B2"),
    ("L18", "Budget Evolution Engine", "B2"),
    ("L19", "Trust Decay Engine", "B2"),
    ("L20", "Meta Loop Controller", "B2"),
    ("L21", "Completion Engine", "B2"),
    ("L22", "Spec Lock System", "B1"),
    ("L23", "Research Engine", "B2"),
    ("L24", "Knowledge Engine", "B2"),
    ("L25", "Scheduler Engine", "B2"),
    ("L26", "Recovery Engine", "A"),
    ("L27", "Override Controller", "B1"),
    ("L28", "Loop Monitor", "B2"),
    ("L29", "Cost Controller", "B2"),
    ("L30", "Progress Engine", "B2"),
]


# ─────────────────────────────────────────────────────────────────────────── #
# Layer Registry
# ─────────────────────────────────────────────────────────────────────────── #


class LayerRegistry:
    """
    Central registry for all 30 layers of K-Dexter AOS.

    Responsibilities:
      1. Register layer instances at startup
      2. Manage lifecycle (init → start → stop)
      3. Track health status (healthy/degraded/unhealthy)
      4. Provide lookup by ID, tier, status

    Usage:
        registry = LayerRegistry()        # auto-registers all 30 descriptors
        registry.bind("L10", evidence_store_instance)
        await registry.init_layer("L10")
        await registry.start_layer("L10")
        health = await registry.check_health("L10")
    """

    def __init__(self) -> None:
        self._layers: dict[str, LayerDescriptor] = {}
        # Auto-register all 30 layer descriptors
        for layer_id, name, tier in _LAYER_CATALOG:
            self._layers[layer_id] = LayerDescriptor(
                layer_id=layer_id,
                name=name,
                governance_tier=tier,
            )

    # ── Registration ─────────────────────────────────────────────────────── #

    def bind(self, layer_id: str, instance: Any) -> None:
        """
        Bind a layer implementation instance to a layer descriptor.
        Raises LayerNotFoundError if layer_id is not in the catalog.
        """
        desc = self._layers.get(layer_id)
        if desc is None:
            raise LayerNotFoundError(f"Layer {layer_id} not in catalog")
        desc.instance = instance

    def unbind(self, layer_id: str) -> None:
        """Remove instance binding (e.g., for hot-swap)."""
        desc = self._layers.get(layer_id)
        if desc is not None:
            desc.instance = None
            desc.status = LayerStatus.REGISTERED

    # ── Lookup ───────────────────────────────────────────────────────────── #

    def get(self, layer_id: str) -> Optional[LayerDescriptor]:
        return self._layers.get(layer_id)

    def get_instance(self, layer_id: str) -> Optional[Any]:
        desc = self._layers.get(layer_id)
        return desc.instance if desc else None

    def list_all(self) -> list[LayerDescriptor]:
        return list(self._layers.values())

    def list_by_tier(self, tier: str) -> list[LayerDescriptor]:
        return [d for d in self._layers.values() if d.governance_tier == tier]

    def list_by_status(self, status: LayerStatus) -> list[LayerDescriptor]:
        return [d for d in self._layers.values() if d.status == status]

    def list_bound(self) -> list[LayerDescriptor]:
        """List layers that have an instance bound."""
        return [d for d in self._layers.values() if d.instance is not None]

    def list_unbound(self) -> list[LayerDescriptor]:
        """List layers without an instance (stubs/not yet implemented)."""
        return [d for d in self._layers.values() if d.instance is None]

    def count(self) -> int:
        return len(self._layers)

    def bound_count(self) -> int:
        return sum(1 for d in self._layers.values() if d.instance is not None)

    # ── Lifecycle management ─────────────────────────────────────────────── #

    async def init_layer(self, layer_id: str) -> None:
        """
        Initialize a layer. Calls instance.init() if available.
        Transitions: REGISTERED → INIT → READY (or ERROR).
        """
        desc = self._get_or_raise(layer_id)
        if desc.instance is None:
            raise LayerNotBoundError(f"Layer {layer_id} has no instance bound")

        desc.status = LayerStatus.INIT
        try:
            init_fn = getattr(desc.instance, "init", None)
            if init_fn and callable(init_fn):
                await init_fn()
            desc.status = LayerStatus.READY
        except Exception as exc:
            desc.status = LayerStatus.ERROR
            desc.error_message = str(exc)
            raise

    async def start_layer(self, layer_id: str) -> None:
        """
        Start a layer. Calls instance.start() if available.
        Transitions: READY → RUNNING (or ERROR).
        """
        desc = self._get_or_raise(layer_id)
        if desc.status not in (LayerStatus.READY, LayerStatus.STOPPED):
            raise LayerLifecycleError(
                f"Cannot start {layer_id} in status {desc.status.value}. Must be READY or STOPPED."
            )

        try:
            start_fn = getattr(desc.instance, "start", None)
            if start_fn and callable(start_fn):
                await start_fn()
            desc.status = LayerStatus.RUNNING
            desc.started_at = datetime.now(timezone.utc)
            desc.health = HealthStatus.HEALTHY
        except Exception as exc:
            desc.status = LayerStatus.ERROR
            desc.error_message = str(exc)
            raise

    async def stop_layer(self, layer_id: str) -> None:
        """
        Stop a layer. Calls instance.stop() if available.
        Transitions: RUNNING → STOPPED (or ERROR).
        """
        desc = self._get_or_raise(layer_id)

        try:
            stop_fn = getattr(desc.instance, "stop", None)
            if stop_fn and callable(stop_fn):
                await stop_fn()
            desc.status = LayerStatus.STOPPED
            desc.stopped_at = datetime.now(timezone.utc)
            desc.health = HealthStatus.UNKNOWN
        except Exception as exc:
            desc.status = LayerStatus.ERROR
            desc.error_message = str(exc)
            raise

    async def check_health(self, layer_id: str) -> HealthStatus:
        """
        Check layer health. Calls instance.health_check() if available.
        Returns UNKNOWN if no health_check method exists.
        """
        desc = self._get_or_raise(layer_id)
        if desc.instance is None:
            return HealthStatus.UNKNOWN

        hc_fn = getattr(desc.instance, "health_check", None)
        if hc_fn and callable(hc_fn):
            try:
                health = await hc_fn()
                desc.health = health
            except Exception:
                desc.health = HealthStatus.UNHEALTHY
        else:
            desc.health = HealthStatus.UNKNOWN

        desc.last_health_check = datetime.now(timezone.utc)
        return desc.health

    async def check_all_health(self) -> dict[str, HealthStatus]:
        """Check health of all bound layers. Returns {layer_id: HealthStatus}."""
        results = {}
        for desc in self._layers.values():
            if desc.instance is not None and desc.status == LayerStatus.RUNNING:
                results[desc.layer_id] = await self.check_health(desc.layer_id)
        return results

    # ── Batch operations ─────────────────────────────────────────────────── #

    async def init_all_bound(self) -> dict[str, bool]:
        """Init all bound layers. Returns {layer_id: success}."""
        results = {}
        for desc in self._layers.values():
            if desc.instance is not None:
                try:
                    await self.init_layer(desc.layer_id)
                    results[desc.layer_id] = True
                except Exception:
                    results[desc.layer_id] = False
        return results

    async def start_all_ready(self) -> dict[str, bool]:
        """Start all READY layers. Returns {layer_id: success}."""
        results = {}
        for desc in self._layers.values():
            if desc.status == LayerStatus.READY:
                try:
                    await self.start_layer(desc.layer_id)
                    results[desc.layer_id] = True
                except Exception:
                    results[desc.layer_id] = False
        return results

    async def stop_all_running(self) -> dict[str, bool]:
        """Stop all RUNNING layers. Returns {layer_id: success}."""
        results = {}
        for desc in self._layers.values():
            if desc.status == LayerStatus.RUNNING:
                try:
                    await self.stop_layer(desc.layer_id)
                    results[desc.layer_id] = True
                except Exception:
                    results[desc.layer_id] = False
        return results

    # ── Summary ──────────────────────────────────────────────────────────── #

    def summary(self) -> dict:
        """Return a summary of registry state."""
        status_counts = {}
        tier_counts = {}
        for desc in self._layers.values():
            status_counts[desc.status.value] = status_counts.get(desc.status.value, 0) + 1
            tier_counts[desc.governance_tier] = tier_counts.get(desc.governance_tier, 0) + 1

        return {
            "total": self.count(),
            "bound": self.bound_count(),
            "unbound": self.count() - self.bound_count(),
            "by_status": status_counts,
            "by_tier": tier_counts,
        }

    # ── Internal ─────────────────────────────────────────────────────────── #

    def _get_or_raise(self, layer_id: str) -> LayerDescriptor:
        desc = self._layers.get(layer_id)
        if desc is None:
            raise LayerNotFoundError(f"Layer {layer_id} not in registry")
        return desc


# ─────────────────────────────────────────────────────────────────────────── #
# Exceptions
# ─────────────────────────────────────────────────────────────────────────── #


class LayerNotFoundError(Exception):
    """Layer ID not in the registry."""

    pass


class LayerNotBoundError(Exception):
    """Layer has no instance bound."""

    pass


class LayerLifecycleError(Exception):
    """Invalid lifecycle transition attempted."""

    pass
