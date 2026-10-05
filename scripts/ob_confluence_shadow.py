"""Shadow run of the HTF-OB x LTF-BOS confluence detector (no orders, observation only).

Usage:
    python scripts/ob_confluence_shadow.py --ltf sol_5m.csv --htf sol_1h.csv \
        --ltf-ms 300000 --htf-ms 3600000 --out events.jsonl

CSV columns (no header): timestamp_ms,open,high,low,close,volume.
Exits non-zero if the truncation (look-ahead) audit finds any mismatch; results of a
run whose audit failed must not be used for any verdict.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from strategies.smc_ob_confluence import VARIANTS, Bars, scan, truncation_audit  # noqa: E402


def _load(path: str) -> Bars:
    return Bars.from_ohlcv(np.loadtxt(path, delimiter=",").tolist())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ltf", required=True)
    ap.add_argument("--htf", required=True)
    ap.add_argument("--ltf-ms", type=int, default=300_000)
    ap.add_argument("--htf-ms", type=int, default=3_600_000)
    ap.add_argument("--out", required=True)
    ap.add_argument("--audit-cuts", type=int, default=20)
    a = ap.parse_args()

    ltf, htf = _load(a.ltf), _load(a.htf)
    cuts = sorted(set(np.linspace(2 * 5 + 1, len(ltf) - 1, a.audit_cuts, dtype=int).tolist()))
    failed = False
    with open(a.out, "w") as f:
        for v in VARIANTS:
            bad = truncation_audit(ltf, htf, a.ltf_ms, a.htf_ms, v, cuts)
            failed |= bool(bad)
            events = scan(ltf, htf, a.ltf_ms, a.htf_ms, v)
            for e in events:
                f.write(json.dumps(e) + "\n")
            sig = [e for e in events if e["event"] == "signal_event"]
            out = [e for e in events if e["event"] == "outcome_event"]
            blocked = Counter(e["block_reason"] for e in sig if not e["gate_passed"])
            cf = [e for e in events if e["event"] == "cf_outcome_event"]
            net = [e["net_r"] for e in out]
            cf_net = [e["net_r"] for e in cf]
            print(
                f"{v.id}: audit={'FAIL ' + str(bad) if bad else 'PASS'} "
                f"signals={len(sig)} passed={sum(e['gate_passed'] for e in sig)} "
                f"blocked={dict(blocked)} trades={len(out)} "
                f"win={sum(e['reason'] == 'TARGET' for e in out)} "
                f"mean_net_R={np.mean(net) if net else float('nan'):.3f} | "
                f"STALE-counterfactual trades={len(cf)} "
                f"win={sum(e['reason'] == 'TARGET' for e in cf)} "
                f"mean_net_R={np.mean(cf_net) if cf_net else float('nan'):.3f}"
            )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
