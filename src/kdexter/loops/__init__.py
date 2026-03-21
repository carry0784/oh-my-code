"""
kdexter.loops

Four operational loops of K-Dexter AOS:
- MainLoop              — core 12-step governance cycle orchestrator
- RecoveryLoop          — 5-phase failure recovery (Isolate→Replay→Rollback→Repair→Resume)
- SelfImprovementLoop   — performance analysis + incremental parameter updates
- EvolutionLoop         — AI-driven strategy variant generation + sandbox + promotion

Also provides concurrency primitives (priority queue, lock management, deadlock detection).
"""
