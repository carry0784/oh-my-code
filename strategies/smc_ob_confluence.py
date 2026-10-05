"""HTF order-block x LTF BOS confluence detector (research / shadow only).

Not a BaseStrategy and never produces orders: it only emits observation events
(zone / bos / signal / fill / outcome) for shadow logging and A/B comparison
against the canonical SMC+WaveTrend strategy.  It does not import or modify any
execution, PPF or canonical-strategy module.

Setups blocked only by STALE are also simulated as counterfactuals (``cf_*`` events,
never mixed with the real ``fill/cancel/outcome`` events) to measure the STALE filter.

Causality contract (verified by ``truncation_audit``): every event is stamped
with ``ts`` = the bar-close time at which it became knowable, and the events
with ``ts <= T`` are identical whether the series is cut at T or not.

Frozen shadow-stage parameters (no runtime adaptation):
    MIN_RR=3.0, SL_BUFFER_FRAC=0.0, COST_BPS_ROUNDTRIP=10.0
The four approved variants are ``VARIANTS`` (LTF swing length x freshness rule).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

MIN_RR = 3.0
SL_BUFFER_FRAC = 0.0
COST_BPS_ROUNDTRIP = 10.0


@dataclass(frozen=True)
class OBVariant:
    swing_len: int  # LTF fractal length L (swing confirmed L bars later)
    unmitigated: str  # "gap": freshness region = imbalance, "touch": = OB body

    def __post_init__(self):
        if self.swing_len not in (1, 5) or self.unmitigated not in ("gap", "touch"):
            raise ValueError(f"unapproved variant: {self}")

    @property
    def id(self) -> str:
        return f"L{self.swing_len}-{self.unmitigated}"


VARIANTS = tuple(OBVariant(n, m) for n in (1, 5) for m in ("gap", "touch"))


@dataclass(frozen=True, eq=False)
class Bars:
    ts: np.ndarray  # bar open time, ms
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray  # noqa: E741
    c: np.ndarray

    @classmethod
    def from_ohlcv(cls, ohlcv: list[list]) -> Bars:
        a = np.asarray(ohlcv, dtype=float)
        return cls(a[:, 0].astype(np.int64), a[:, 1], a[:, 2], a[:, 3], a[:, 4])

    def __len__(self) -> int:
        return len(self.ts)

    def head(self, n: int) -> Bars:
        return Bars(self.ts[:n], self.o[:n], self.h[:n], self.l[:n], self.c[:n])


@dataclass
class _Zone:
    id: str
    d: int  # +1 bullish (demand), -1 bearish (supply)
    lo: float  # OB body
    hi: float
    gap_lo: float
    gap_hi: float
    confirm_ts: int  # close time of the bar after the engulfing candle
    ob_ts: int
    start_idx: int = 0
    edge: float = 0.0  # freshness-region edge facing price
    first_reach: int | None = None
    dead: bool = False
    consumed: bool = False


def _engulf(o: np.ndarray, c: np.ndarray, i: int, d: int) -> bool:
    """Candle i engulfs the body of candle i-1 in direction d (opposite colors)."""
    oi, ci, op, cp = d * o[i], d * c[i], d * o[i - 1], d * c[i - 1]
    return ci > oi and op > cp and ci >= op and oi <= cp


def _adverse(h: float, l: float, level: float, d: int) -> bool:  # noqa: E741
    """Price traded back down to (d=1) / up to (d=-1) ``level``."""
    return l <= level if d == 1 else h >= level


def _favorable(h: float, l: float, level: float, d: int) -> bool:  # noqa: E741
    return h >= level if d == 1 else l <= level


def detect_htf_zones(htf: Bars, htf_ms: int) -> list[_Zone]:
    """Engulfing-preceded OB with a 3-candle imbalance; known at close of bar k+1."""
    zones: list[_Zone] = []
    for k in range(1, len(htf) - 1):
        for d in (1, -1):
            if not _engulf(htf.o, htf.c, k, d):
                continue
            if d == 1 and not htf.l[k + 1] > htf.h[k - 1]:
                continue
            if d == -1 and not htf.h[k + 1] < htf.l[k - 1]:
                continue
            body = (htf.o[k - 1], htf.c[k - 1])
            gap = (htf.h[k - 1], htf.l[k + 1]) if d == 1 else (htf.h[k + 1], htf.l[k - 1])
            zones.append(
                _Zone(
                    id=f"{htf_ms}:{int(htf.ts[k - 1])}:{d}",
                    d=d,
                    lo=float(min(body)),
                    hi=float(max(body)),
                    gap_lo=float(gap[0]),
                    gap_hi=float(gap[1]),
                    confirm_ts=int(htf.ts[k + 1]) + htf_ms,
                    ob_ts=int(htf.ts[k - 1]),
                )
            )
    return zones


def ltf_bos_events(ltf: Bars, swing_len: int) -> list[dict]:
    """Close-beyond-swing BOS using causally confirmed fractal swings (confirmed at i+L)."""
    L = swing_len
    out: list[dict] = []
    sh = sl = np.nan
    sh_i = sl_i = -1
    for i in range(2 * L, len(ltf)):
        cand = i - L
        ws = cand - L
        if ltf.h[cand] == np.max(ltf.h[ws : i + 1]):
            sh, sh_i = ltf.h[cand], cand
        if ltf.l[cand] == np.min(ltf.l[ws : i + 1]):
            sl, sl_i = ltf.l[cand], cand
        if not np.isnan(sh) and ltf.c[i] > sh:
            out.append({"t": i, "d": 1, "level": float(sh), "swing_idx": sh_i})
            sh = np.nan
        if not np.isnan(sl) and ltf.c[i] < sl:
            out.append({"t": i, "d": -1, "level": float(sl), "swing_idx": sl_i})
            sl = np.nan
    return out


def scan(
    ltf: Bars,
    htf: Bars,
    ltf_ms: int,
    htf_ms: int,
    variant: OBVariant,
    min_rr: float = MIN_RR,
    cost_bps: float = COST_BPS_ROUNDTRIP,
) -> list[dict]:
    """Run one variant over the series and return shadow events ordered by ``ts``."""
    n = len(ltf)
    events: list[dict] = []
    end_ts = int(ltf.ts[-1]) + ltf_ms if n else 0
    vid = variant.id

    def emit(ts: int, kind: str, **kw) -> None:
        events.append({"event": kind, "ts": int(ts), "variant": vid, **kw})

    zones = detect_htf_zones(htf, htf_ms)
    for z in zones:
        z.start_idx = int(np.searchsorted(ltf.ts, z.confirm_ts, side="left"))
        if variant.unmitigated == "gap":
            z.edge = z.gap_hi if z.d == 1 else z.gap_lo
        else:
            z.edge = z.hi if z.d == 1 else z.lo
        if z.confirm_ts <= end_ts:
            emit(
                z.confirm_ts, "zone_event", zone_id=z.id, state="CONFIRMED", d=z.d,
                lo=z.lo, hi=z.hi, gap_lo=z.gap_lo, gap_hi=z.gap_hi, tf_ms=htf_ms, ob_ts=z.ob_ts,
            )  # fmt: skip

    bos_at: dict[int, list[dict]] = {}
    for b in ltf_bos_events(ltf, variant.swing_len):
        bos_at.setdefault(b["t"], []).append(b)

    pending: list[dict] = []
    live: list[dict] = []

    def kind(o: dict, name: str) -> str:
        return f"cf_{name}" if o["cf"] else name  # counterfactual events never mix with real ones

    def resolve(tr: dict, ts: int, reason: str) -> None:
        gross = -1.0 if reason == "STOP" else tr["rr"]
        net = gross - cost_bps / 1e4 * tr["entry"] / tr["risk"]
        emit(
            ts, kind(tr, "outcome_event"), signal_id=tr["signal_id"], reason=reason,
            gross_r=gross, net_r=net, mfe_r=tr["mfe"], mae_r=tr["mae"],
        )  # fmt: skip

    for t in range(n):
        ct = int(ltf.ts[t]) + ltf_ms
        h, l, c = float(ltf.h[t]), float(ltf.l[t]), float(ltf.c[t])  # noqa: E741
        bos_now = bos_at.get(t, [])

        # 1) trades filled on earlier bars: stop has priority over target on the same bar
        still_live = []
        for tr in live:
            d = tr["d"]
            tr["mfe"] = max(tr["mfe"], d * ((h if d == 1 else l) - tr["entry"]) / tr["risk"])
            tr["mae"] = max(tr["mae"], d * (tr["entry"] - (l if d == 1 else h)) / tr["risk"])
            if _adverse(h, l, tr["stop"], d):
                resolve(tr, ct, "STOP")
            elif _favorable(h, l, tr["tp"], d):
                resolve(tr, ct, "TARGET")
            else:
                still_live.append(tr)
        live = still_live

        # 2) pending limit orders (created on earlier bars)
        still_pending = []
        for p in pending:
            d = p["d"]
            if _adverse(h, l, p["entry"], d):
                emit(ct, kind(p, "fill_event"), signal_id=p["signal_id"], price=p["entry"],
                     cost_bps_roundtrip=cost_bps)  # fmt: skip
                tr = {**p, "mfe": 0.0,
                      "mae": max(0.0, d * (p["entry"] - (l if d == 1 else h)) / p["risk"])}  # fmt: skip
                if _adverse(h, l, p["stop"], d):
                    resolve(tr, ct, "STOP")
                else:
                    live.append(tr)
            elif _favorable(h, l, p["tp"], d):
                emit(ct, kind(p, "cancel_event"), signal_id=p["signal_id"],
                     reason="TARGET_BEFORE_FILL")  # fmt: skip
            elif any(b["d"] == -d for b in bos_now):
                emit(ct, kind(p, "cancel_event"), signal_id=p["signal_id"],
                     reason="OPPOSITE_BOS")  # fmt: skip
            else:
                still_pending.append(p)
        pending = still_pending

        # 3) zone state: first reach of the freshness region, invalidation by close
        for z in zones:
            if z.dead or z.start_idx > t:
                continue
            if z.first_reach is None and _adverse(h, l, z.edge, z.d):
                z.first_reach = t
                emit(ct, "zone_event", zone_id=z.id, state="ENGAGED")
            if (z.d == 1 and c < z.lo) or (z.d == -1 and c > z.hi):
                z.dead = True
                emit(ct, "zone_event", zone_id=z.id, state="INVALIDATED")

        # 4) BOS events and one setup attempt per zone
        for b in bos_now:
            d = b["d"]
            bos_id = f"{ltf_ms}:{int(ltf.ts[t])}:{d}:L{variant.swing_len}"
            emit(ct, "bos_event", bos_id=bos_id, d=d, level=b["level"],
                 swing_ts=int(ltf.ts[b["swing_idx"]]), tf_ms=ltf_ms)  # fmt: skip
            s = b["swing_idx"]
            ls = s + int(np.argmin(ltf.l[s : t + 1]) if d == 1 else np.argmax(ltf.h[s : t + 1]))
            ext = float(ltf.l[ls] if d == 1 else ltf.h[ls])
            for z in zones:
                if z.d != d or z.dead or z.consumed or z.start_idx > t:
                    continue
                if ls < z.start_idx or not z.lo <= ext <= z.hi:
                    continue
                z.consumed = True
                sig_id = f"{z.id}|{bos_id}|{vid}"
                j = ls - 1
                while j >= z.start_idx and _adverse(ltf.h[j], ltf.l[j], z.edge, d):
                    j -= 1
                stale = z.first_reach is not None and z.first_reach < j + 1
                entry = stop = tp = rr = ob_ts = None
                other = None  # first failing gate other than STALE
                ob = next(
                    (e - 1 for e in range(ls + 1, t + 1) if _engulf(ltf.o, ltf.c, e, d)), None
                )
                if ob is not None:
                    ob_lo = float(min(ltf.o[ob], ltf.c[ob]))
                    ob_hi = float(max(ltf.o[ob], ltf.c[ob]))
                if ob is None or ob_hi < z.lo or ob_lo > z.hi:
                    other = "NO_LTF_OB"
                else:
                    ob_ts = int(ltf.ts[ob])
                    entry = ob_hi if d == 1 else ob_lo
                    stop = z.lo * (1 - SL_BUFFER_FRAC) if d == 1 else z.hi * (1 + SL_BUFFER_FRAC)
                    cands = [
                        (d * ((o.lo if o.d == -1 else o.hi) - entry), (o.lo if o.d == -1 else o.hi))
                        for o in zones
                        if o.d == -d and not o.dead and o.first_reach is None
                        and o.start_idx <= t and d * ((o.lo if o.d == -1 else o.hi) - entry) > 0
                    ]  # fmt: skip
                    if d * (entry - stop) <= 0:
                        other = "INVALID_RISK"
                    elif not cands:
                        other = "NO_TARGET"
                    else:
                        tp = min(cands)[1]
                        rr = abs(tp - entry) / abs(entry - stop)
                        if rr < min_rr:
                            other = "RR_BELOW_MIN"
                reason = "STALE" if stale else other
                # counterfactual: STALE was the only blocker -> simulate it to measure the filter
                cf = stale and other is None
                emit(ct, "signal_event", signal_id=sig_id, zone_id=z.id, bos_id=bos_id, d=d,
                     entry=entry, stop=stop, tp=tp, rr=rr, ob_ts=ob_ts,
                     gate_passed=reason is None, block_reason=reason,
                     counterfactual=cf)  # fmt: skip
                if reason is None or cf:
                    pending.append({"signal_id": sig_id, "d": d, "entry": entry, "stop": stop,
                                    "tp": tp, "rr": rr, "risk": abs(entry - stop),
                                    "cf": cf})  # fmt: skip

    events.sort(key=lambda e: e["ts"])  # stable: emission order kept within a ts
    return events


def truncation_audit(
    ltf: Bars, htf: Bars, ltf_ms: int, htf_ms: int, variant: OBVariant, cuts: list[int]
) -> list[int]:
    """Return the cut indices where events known at the cut differ from the full run."""
    full = scan(ltf, htf, ltf_ms, htf_ms, variant)
    bad = []
    for cut in cuts:
        T = int(ltf.ts[cut]) + ltf_ms
        keep = htf.ts + htf_ms <= T
        part = scan(ltf.head(cut + 1), htf.head(int(keep.sum())), ltf_ms, htf_ms, variant)
        if part != [e for e in full if e["ts"] <= T]:
            bad.append(cut)
    return bad
