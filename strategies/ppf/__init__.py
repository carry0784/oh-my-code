"""Pattern Projection Filter (PPF) - Supplementary gate filter module.

Authority Chain:
    PPF-DESIGN-001 -> PPF-IMPLEMENTATION-001 -> PPF-CODE-IMPLEMENTATION-001

PPF is NOT an independent strategy. It is a supplementary gate filter that
sits ABOVE the existing execution engine as an external orchestration wrapper.
PPF does NOT generate orders, does NOT modify the execution engine, and does
NOT operate as a standalone trading system.

Constitution: C1-C11 prohibitions enforced. See constitution.py.
"""

from strategies.ppf.constants import PPFState, RejectionCode
from strategies.ppf.gate import PPFGate

__all__ = ["PPFGate", "PPFState", "RejectionCode"]
