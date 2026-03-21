"""
kdexter.layers

30-layer architecture registry. Each layer (L1~L30) encapsulates a distinct
functional concern, attributed to governance tiers B1/B2/A.

See: docs/architecture/governance_layer_map.md
"""
from kdexter.layers.registry import (
    HealthStatus,
    LayerDescriptor,
    LayerLifecycleError,
    LayerNotBoundError,
    LayerNotFoundError,
    LayerProtocol,
    LayerRegistry,
    LayerStatus,
)

__all__ = [
    "HealthStatus",
    "LayerDescriptor",
    "LayerLifecycleError",
    "LayerNotBoundError",
    "LayerNotFoundError",
    "LayerProtocol",
    "LayerRegistry",
    "LayerStatus",
]
