"""
Tier 4 Tests -- LayerRegistry (L1~L30 instance management)
K-Dexter AOS v4

Tests:
  1. Catalog: 30 layers auto-registered, correct tiers
  2. Binding: bind/unbind instances
  3. Lifecycle: init -> start -> stop -> error
  4. Health: check health, batch operations
  5. Lookup: by tier, status, bound/unbound
  6. Summary

Run: python tests/test_tier4.py
"""

from __future__ import annotations

import asyncio
import sys

from kdexter.layers.registry import (
    HealthStatus,
    LayerDescriptor,
    LayerLifecycleError,
    LayerNotBoundError,
    LayerNotFoundError,
    LayerRegistry,
    LayerStatus,
)


# ── Mock layer implementations ──────────────────────────────────────────── #


class GoodLayer:
    """A layer that works correctly."""

    def __init__(self):
        self.initialized = False
        self.started = False
        self.stopped = False

    async def init(self):
        self.initialized = True

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def health_check(self) -> HealthStatus:
        return HealthStatus.HEALTHY


class DegradedLayer:
    """A layer that reports degraded health."""

    async def init(self):
        pass

    async def start(self):
        pass

    async def stop(self):
        pass

    async def health_check(self) -> HealthStatus:
        return HealthStatus.DEGRADED


class FailingLayer:
    """A layer that fails on init."""

    async def init(self):
        raise RuntimeError("init explosion")

    async def start(self):
        raise RuntimeError("start explosion")


class MinimalLayer:
    """A layer with no lifecycle methods."""

    pass


# ======================================================================== #
# 1. Catalog
# ======================================================================== #


def test_30_layers_registered():
    reg = LayerRegistry()
    assert reg.count() == 30
    print("  [1] 30 layers auto-registered  OK")


def test_layer_ids():
    reg = LayerRegistry()
    for i in range(1, 31):
        lid = f"L{i}"
        desc = reg.get(lid)
        assert desc is not None, f"{lid} missing"
        assert desc.layer_id == lid
    print("  [2] All L1~L30 IDs present  OK")


def test_tier_counts():
    reg = LayerRegistry()
    b1 = reg.list_by_tier("B1")
    b2 = reg.list_by_tier("B2")
    a = reg.list_by_tier("A")
    assert len(b1) == 5  # L1, L2, L3, L22, L27
    assert len(a) == 5  # L6, L7, L8, L10, L26
    assert len(b2) == 20  # the rest
    assert len(b1) + len(b2) + len(a) == 30
    print("  [3] Tier counts B1=5 B2=20 A=5  OK")


def test_b1_layers():
    reg = LayerRegistry()
    b1_ids = {d.layer_id for d in reg.list_by_tier("B1")}
    assert b1_ids == {"L1", "L2", "L3", "L22", "L27"}
    print("  [4] B1 layer IDs correct  OK")


def test_a_layers():
    reg = LayerRegistry()
    a_ids = {d.layer_id for d in reg.list_by_tier("A")}
    assert a_ids == {"L6", "L7", "L8", "L10", "L26"}
    print("  [5] A layer IDs correct  OK")


# ======================================================================== #
# 2. Binding
# ======================================================================== #


def test_bind_instance():
    reg = LayerRegistry()
    layer = GoodLayer()
    reg.bind("L10", layer)
    assert reg.get_instance("L10") is layer
    assert reg.bound_count() == 1
    print("  [6] Bind instance  OK")


def test_unbind_instance():
    reg = LayerRegistry()
    reg.bind("L10", GoodLayer())
    reg.unbind("L10")
    assert reg.get_instance("L10") is None
    assert reg.bound_count() == 0
    print("  [7] Unbind instance  OK")


def test_bind_unknown_layer():
    reg = LayerRegistry()
    try:
        reg.bind("L99", GoodLayer())
        assert False, "Should have raised LayerNotFoundError"
    except LayerNotFoundError:
        pass
    print("  [8] Bind unknown layer rejected  OK")


def test_list_bound_unbound():
    reg = LayerRegistry()
    reg.bind("L10", GoodLayer())
    reg.bind("L11", GoodLayer())
    assert len(reg.list_bound()) == 2
    assert len(reg.list_unbound()) == 28
    print("  [9] List bound/unbound  OK")


# ======================================================================== #
# 3. Lifecycle
# ======================================================================== #


def test_lifecycle_full():
    reg = LayerRegistry()
    layer = GoodLayer()
    reg.bind("L10", layer)

    asyncio.run(reg.init_layer("L10"))
    assert reg.get("L10").status == LayerStatus.READY
    assert layer.initialized

    asyncio.run(reg.start_layer("L10"))
    assert reg.get("L10").status == LayerStatus.RUNNING
    assert layer.started
    assert reg.get("L10").started_at is not None

    asyncio.run(reg.stop_layer("L10"))
    assert reg.get("L10").status == LayerStatus.STOPPED
    assert layer.stopped
    assert reg.get("L10").stopped_at is not None
    print("  [10] Full lifecycle (init->start->stop)  OK")


def test_init_without_bind():
    reg = LayerRegistry()
    try:
        asyncio.run(reg.init_layer("L10"))
        assert False, "Should have raised LayerNotBoundError"
    except LayerNotBoundError:
        pass
    print("  [11] Init without bind rejected  OK")


def test_init_failure():
    reg = LayerRegistry()
    reg.bind("L10", FailingLayer())
    try:
        asyncio.run(reg.init_layer("L10"))
        assert False, "Should have raised"
    except RuntimeError:
        pass
    assert reg.get("L10").status == LayerStatus.ERROR
    assert reg.get("L10").error_message == "init explosion"
    print("  [12] Init failure -> ERROR status  OK")


def test_start_requires_ready():
    reg = LayerRegistry()
    reg.bind("L10", GoodLayer())
    # Status is REGISTERED, not READY
    try:
        asyncio.run(reg.start_layer("L10"))
        assert False, "Should have raised LayerLifecycleError"
    except LayerLifecycleError:
        pass
    print("  [13] Start requires READY status  OK")


def test_restart_stopped_layer():
    reg = LayerRegistry()
    layer = GoodLayer()
    reg.bind("L10", layer)
    asyncio.run(reg.init_layer("L10"))
    asyncio.run(reg.start_layer("L10"))
    asyncio.run(reg.stop_layer("L10"))

    # Can restart from STOPPED
    asyncio.run(reg.start_layer("L10"))
    assert reg.get("L10").status == LayerStatus.RUNNING
    print("  [14] Restart stopped layer  OK")


def test_minimal_layer_lifecycle():
    """Layer with no lifecycle methods still transitions correctly."""
    reg = LayerRegistry()
    reg.bind("L10", MinimalLayer())
    asyncio.run(reg.init_layer("L10"))
    assert reg.get("L10").status == LayerStatus.READY

    asyncio.run(reg.start_layer("L10"))
    assert reg.get("L10").status == LayerStatus.RUNNING
    print("  [15] Minimal layer lifecycle  OK")


# ======================================================================== #
# 4. Health
# ======================================================================== #


def test_health_check_healthy():
    reg = LayerRegistry()
    reg.bind("L10", GoodLayer())
    asyncio.run(reg.init_layer("L10"))
    asyncio.run(reg.start_layer("L10"))

    health = asyncio.run(reg.check_health("L10"))
    assert health == HealthStatus.HEALTHY
    assert reg.get("L10").last_health_check is not None
    print("  [16] Health check healthy  OK")


def test_health_check_degraded():
    reg = LayerRegistry()
    reg.bind("L10", DegradedLayer())
    asyncio.run(reg.init_layer("L10"))
    asyncio.run(reg.start_layer("L10"))

    health = asyncio.run(reg.check_health("L10"))
    assert health == HealthStatus.DEGRADED
    print("  [17] Health check degraded  OK")


def test_health_check_no_method():
    reg = LayerRegistry()
    reg.bind("L10", MinimalLayer())
    asyncio.run(reg.init_layer("L10"))
    asyncio.run(reg.start_layer("L10"))

    health = asyncio.run(reg.check_health("L10"))
    assert health == HealthStatus.UNKNOWN
    print("  [18] Health check no method -> UNKNOWN  OK")


def test_health_check_unbound():
    reg = LayerRegistry()
    health = asyncio.run(reg.check_health("L10"))
    assert health == HealthStatus.UNKNOWN
    print("  [19] Health check unbound -> UNKNOWN  OK")


# ======================================================================== #
# 5. Batch operations
# ======================================================================== #


def test_init_all_bound():
    reg = LayerRegistry()
    reg.bind("L10", GoodLayer())
    reg.bind("L11", GoodLayer())
    reg.bind("L12", FailingLayer())

    results = asyncio.run(reg.init_all_bound())
    assert results["L10"] is True
    assert results["L11"] is True
    assert results["L12"] is False
    print("  [20] Init all bound (partial failure)  OK")


def test_start_all_ready():
    reg = LayerRegistry()
    reg.bind("L10", GoodLayer())
    reg.bind("L11", GoodLayer())
    asyncio.run(reg.init_layer("L10"))
    asyncio.run(reg.init_layer("L11"))

    results = asyncio.run(reg.start_all_ready())
    assert results["L10"] is True
    assert results["L11"] is True
    assert reg.get("L10").status == LayerStatus.RUNNING
    print("  [21] Start all ready  OK")


def test_stop_all_running():
    reg = LayerRegistry()
    reg.bind("L10", GoodLayer())
    asyncio.run(reg.init_layer("L10"))
    asyncio.run(reg.start_layer("L10"))

    results = asyncio.run(reg.stop_all_running())
    assert results["L10"] is True
    assert reg.get("L10").status == LayerStatus.STOPPED
    print("  [22] Stop all running  OK")


def test_check_all_health():
    reg = LayerRegistry()
    reg.bind("L10", GoodLayer())
    reg.bind("L11", DegradedLayer())
    asyncio.run(reg.init_layer("L10"))
    asyncio.run(reg.start_layer("L10"))
    asyncio.run(reg.init_layer("L11"))
    asyncio.run(reg.start_layer("L11"))

    results = asyncio.run(reg.check_all_health())
    assert results["L10"] == HealthStatus.HEALTHY
    assert results["L11"] == HealthStatus.DEGRADED
    print("  [23] Check all health  OK")


# ======================================================================== #
# 6. Summary & Lookup
# ======================================================================== #


def test_summary():
    reg = LayerRegistry()
    reg.bind("L10", GoodLayer())

    s = reg.summary()
    assert s["total"] == 30
    assert s["bound"] == 1
    assert s["unbound"] == 29
    assert s["by_tier"]["B1"] == 5
    assert s["by_tier"]["A"] == 5
    print("  [24] Summary  OK")


def test_list_by_status():
    reg = LayerRegistry()
    reg.bind("L10", GoodLayer())
    asyncio.run(reg.init_layer("L10"))

    ready = reg.list_by_status(LayerStatus.READY)
    assert len(ready) == 1
    assert ready[0].layer_id == "L10"

    registered = reg.list_by_status(LayerStatus.REGISTERED)
    assert len(registered) == 29
    print("  [25] List by status  OK")


def test_layer_names():
    """Verify key layer names from governance_layer_map.md."""
    reg = LayerRegistry()
    assert reg.get("L1").name == "Human Decision"
    assert reg.get("L10").name == "Audit / Evidence Store"
    assert reg.get("L27").name == "Override Controller"
    assert reg.get("L30").name == "Progress Engine"
    print("  [26] Layer names match governance map  OK")


# ======================================================================== #
# Runner
# ======================================================================== #

if __name__ == "__main__":
    print("\nTier 4 Tests -- LayerRegistry (L1~L30)")
    print("=" * 60)

    tests = [
        (
            "Catalog",
            [
                test_30_layers_registered,
                test_layer_ids,
                test_tier_counts,
                test_b1_layers,
                test_a_layers,
            ],
        ),
        (
            "Binding",
            [
                test_bind_instance,
                test_unbind_instance,
                test_bind_unknown_layer,
                test_list_bound_unbound,
            ],
        ),
        (
            "Lifecycle",
            [
                test_lifecycle_full,
                test_init_without_bind,
                test_init_failure,
                test_start_requires_ready,
                test_restart_stopped_layer,
                test_minimal_layer_lifecycle,
            ],
        ),
        (
            "Health",
            [
                test_health_check_healthy,
                test_health_check_degraded,
                test_health_check_no_method,
                test_health_check_unbound,
            ],
        ),
        (
            "Batch",
            [
                test_init_all_bound,
                test_start_all_ready,
                test_stop_all_running,
                test_check_all_health,
            ],
        ),
        (
            "Summary & Lookup",
            [
                test_summary,
                test_list_by_status,
                test_layer_names,
            ],
        ),
    ]

    total = 0
    passed = 0
    failed_tests = []

    for section, fns in tests:
        print(f"\n--- {section} ---")
        for fn in fns:
            total += 1
            try:
                fn()
                passed += 1
            except Exception as e:
                failed_tests.append((fn.__name__, str(e)))
                print(f"  FAILED: {fn.__name__}: {e}")

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} passed")
    if failed_tests:
        print("FAILED:")
        for name, err in failed_tests:
            print(f"  - {name}: {err}")
        sys.exit(1)
    else:
        print("All tests PASSED")
