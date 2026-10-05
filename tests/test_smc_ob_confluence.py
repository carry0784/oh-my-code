"""Shadow-stage tests for the HTF-OB x LTF-BOS confluence detector."""

import numpy as np
import pytest

from strategies.smc_ob_confluence import (
    VARIANTS,
    Bars,
    OBVariant,
    detect_htf_zones,
    ltf_bos_events,
    scan,
    truncation_audit,
)

HTF_MS = 3_600_000
LTF_MS = 300_000


def _bars(rows, ms, t0=0):
    return Bars.from_ohlcv([[t0 + i * ms, *r, 1.0] for i, r in enumerate(rows)])


# HTF: bearish zone (supply, body 118-121) then bullish zone (demand, body 100-105).
HTF_ROWS = [
    (118, 122, 114, 121),  # 0 bullish -> OB of the bearish zone
    (122, 123, 116, 117),  # 1 bearish engulfing
    (116, 113, 100, 101),  # 2 gap: high 113 < low[0] 114 -> zone confirmed
    (105, 106, 99, 100),  # 3 bearish -> OB of the bullish zone
    (99, 112, 98, 110),  # 4 bullish engulfing
    (110, 115, 108, 114),  # 5 gap: low 108 > high[3] 106 -> zone confirmed at 6h
]
T0 = 6 * HTF_MS  # LTF starts once both zones are confirmed

# LTF path: tap the demand zone, bullish BOS (close > 111), retest 103, run to 119.
BASE = [
    (109.5, 110, 109, 109.8),
    (109.8, 111, 109.2, 109.5),  # swing high 111
    (109.5, 109.6, 106, 106.5),  # enters gap region (low <= 108)
    (106.5, 107.5, 104, 104.5),  # touches OB body (low <= 105)
    (103, 104, 100.5, 101),  # leg low inside body, LTF OB candle [101, 103]
    (100.8, 104, 100.7, 103.5),  # bullish engulfing
    (103.5, 106, 103.4, 105.5),
    (105.5, 109, 105.4, 108.5),
    (108.5, 111.8, 108.4, 111.5),  # BOS: close > 111
    (111.5, 112, 108, 108.2),
    (108.2, 108.5, 102.9, 103.2),  # retest fills the limit at 103
]
WIN_TAIL = [(103.2, 119, 103, 118.5)]
LOSS_TAIL = [(103.2, 103.5, 99.5, 100)]


def _run(rows, variant, htf_rows=HTF_ROWS):
    ltf = _bars(rows, LTF_MS, T0)
    htf = _bars(htf_rows, HTF_MS)
    return scan(ltf, htf, LTF_MS, HTF_MS, variant)


def _by(events, kind):
    return [e for e in events if e["event"] == kind]


def test_only_four_approved_variants():
    assert [v.id for v in VARIANTS] == ["L1-gap", "L1-touch", "L5-gap", "L5-touch"]
    with pytest.raises(ValueError):
        OBVariant(3, "gap")


def test_zones_detected_with_close_time_confirmation():
    zones = detect_htf_zones(_bars(HTF_ROWS, HTF_MS), HTF_MS)
    assert [(z.d, z.lo, z.hi) for z in zones] == [(-1, 118, 121), (1, 100, 105)]
    assert [z.confirm_ts for z in zones] == [3 * HTF_MS, 6 * HTF_MS]


def test_no_zone_without_imbalance():
    rows = list(HTF_ROWS)
    rows[5] = (110, 115, 105.5, 114)  # low 105.5 <= high[3] 106 -> no gap
    assert [z.d for z in detect_htf_zones(_bars(rows, HTF_MS), HTF_MS)] == [-1]


def test_wick_break_is_not_bos():
    rows = [(10, 11, 9, 10), (10, 12, 9.5, 10), (10, 11, 9.4, 10), (10, 13, 9.5, 10.5)]
    # swing high 12 confirmed at bar 2; bar 3 wicks to 13 but closes 10.5 -> no BOS
    assert ltf_bos_events(_bars(rows, LTF_MS), 1) == []


@pytest.mark.parametrize("variant", VARIANTS[:2])  # L1 variants
def test_full_setup_target(variant):
    ev = _run(BASE + WIN_TAIL, variant)
    sig = _by(ev, "signal_event")
    assert len(sig) == 1 and sig[0]["gate_passed"] and sig[0]["block_reason"] is None
    assert (sig[0]["entry"], sig[0]["stop"], sig[0]["tp"]) == (103, 100, 118)
    assert sig[0]["rr"] == pytest.approx(5.0)
    assert len(_by(ev, "fill_event")) == 1
    out = _by(ev, "outcome_event")
    assert out[0]["reason"] == "TARGET" and out[0]["gross_r"] == pytest.approx(5.0)
    assert out[0]["net_r"] < out[0]["gross_r"]  # cost is always charged


def test_stop_has_priority_and_is_minus_one_r():
    out = _by(_run(BASE + LOSS_TAIL, VARIANTS[1]), "outcome_event")
    assert out[0]["reason"] == "STOP" and out[0]["gross_r"] == -1.0


def test_rr_gate_blocks_and_consumes_zone():
    ltf, htf = _bars(BASE + WIN_TAIL, LTF_MS, T0), _bars(HTF_ROWS, HTF_MS)
    ev = scan(ltf, htf, LTF_MS, HTF_MS, VARIANTS[1], min_rr=6.0)
    sig = _by(ev, "signal_event")
    assert sig[0]["block_reason"] == "RR_BELOW_MIN" and not sig[0]["gate_passed"]
    assert _by(ev, "fill_event") == []


def test_stale_zone_differs_between_gap_and_touch():
    # price grazes the gap earlier, leaves for a bar, then returns for the real setup
    pre = [(109.5, 110, 109, 109.8), (109.8, 111, 109.2, 109.5)]
    stale_path = pre + [(109.5, 109.6, 107.5, 108.9), (108.9, 110, 108.6, 109.8)] + BASE[2:]
    gap = _by(_run(stale_path + WIN_TAIL, OBVariant(1, "gap")), "signal_event")
    touch = _by(_run(stale_path + WIN_TAIL, OBVariant(1, "touch")), "signal_event")
    assert gap[0]["block_reason"] == "STALE"
    assert touch[0]["gate_passed"]


STALE_PATH = (
    BASE[:2]
    + [(109.5, 109.6, 107.5, 108.9), (108.9, 110, 108.6, 109.8)]  # grazes the gap, then leaves
    + BASE[2:]
)


def _kinds(ev):
    return {e["event"] for e in ev}


def test_stale_setup_is_simulated_as_counterfactual_win():
    ev = _run(STALE_PATH + WIN_TAIL, OBVariant(1, "gap"))
    sig = _by(ev, "signal_event")[0]
    assert sig["block_reason"] == "STALE" and not sig["gate_passed"] and sig["counterfactual"]
    assert (sig["entry"], sig["stop"], sig["tp"]) == (103, 100, 118)
    # simulated end to end, but only under cf_* names: the real event stream stays empty
    assert len(_by(ev, "cf_fill_event")) == 1
    out = _by(ev, "cf_outcome_event")
    assert out[0]["reason"] == "TARGET" and out[0]["gross_r"] == pytest.approx(5.0)
    assert not _kinds(ev) & {"fill_event", "outcome_event", "cancel_event"}


def test_stale_counterfactual_stop_is_minus_one_r():
    out = _by(_run(STALE_PATH + LOSS_TAIL, OBVariant(1, "gap")), "cf_outcome_event")
    assert out[0]["reason"] == "STOP" and out[0]["gross_r"] == -1.0


def test_non_stale_signal_has_no_counterfactual():
    ev = _run(STALE_PATH + WIN_TAIL, OBVariant(1, "touch"))  # same path, touch reads it as fresh
    assert _by(ev, "signal_event")[0]["counterfactual"] is False
    assert not any(k.startswith("cf_") for k in _kinds(ev))
    assert len(_by(ev, "outcome_event")) == 1


def test_stale_with_another_blocker_is_not_simulated():
    ltf, htf = _bars(STALE_PATH + WIN_TAIL, LTF_MS, T0), _bars(HTF_ROWS, HTF_MS)
    ev = scan(ltf, htf, LTF_MS, HTF_MS, OBVariant(1, "gap"), min_rr=6.0)
    sig = _by(ev, "signal_event")[0]
    assert sig["block_reason"] == "STALE" and sig["counterfactual"] is False
    assert not any(k.startswith("cf_") for k in _kinds(ev))


def test_zone_invalidated_by_close_beyond_far_edge():
    rows = BASE[:4] + [(103, 104, 98, 99)] + BASE[5:]  # closes 99 < lo 100
    ev = _run(rows, VARIANTS[1])
    assert any(e.get("state") == "INVALIDATED" for e in _by(ev, "zone_event"))
    assert _by(ev, "signal_event") == []


def _random_case(seed, n=1800, factor=12):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.25, n))
    open_ = np.concatenate([[100.0], close[:-1]]) + rng.normal(0, 0.05, n)
    high = np.maximum(open_, close) + rng.uniform(0, 0.3, n)
    low = np.minimum(open_, close) - rng.uniform(0, 0.3, n)
    ts = np.arange(n, dtype=np.int64) * LTF_MS
    ltf = Bars(ts, open_, high, low, close)
    m = n // factor
    sl = slice(0, m * factor)
    htf = Bars(
        ts[sl][::factor],
        open_[sl].reshape(m, factor)[:, 0],
        high[sl].reshape(m, factor).max(1),
        low[sl].reshape(m, factor).min(1),
        close[sl].reshape(m, factor)[:, -1],
    )
    return ltf, htf


def test_truncation_equivalence_no_lookahead():
    """Events known at time T must not change when later bars are removed."""
    total = 0
    cuts = list(range(60, 1700, 97))
    for seed in range(6):
        ltf, htf = _random_case(seed)
        for v in VARIANTS:
            assert truncation_audit(ltf, htf, LTF_MS, 12 * LTF_MS, v, cuts) == []
            total += len(scan(ltf, htf, LTF_MS, 12 * LTF_MS, v))
    assert total > 0  # non-vacuous: the random series do produce events


def test_scenario_events_survive_truncation():
    htf = _bars(HTF_ROWS, HTF_MS)
    for rows in (BASE + WIN_TAIL, STALE_PATH + WIN_TAIL, STALE_PATH + LOSS_TAIL):
        ltf = _bars(rows, LTF_MS, T0)
        for v in VARIANTS[:2]:
            assert truncation_audit(ltf, htf, LTF_MS, HTF_MS, v, list(range(0, len(ltf)))) == []


# --- planted-structure tests: the same setup at other price scales / mirrored / time ratios ---
# Recall: the detector must find the planted setup exactly once. Precision: breaking one
# ingredient of the structure must yield no signal. Needs no market data.

PLANT_PRICES = [(1.0, 200.0), (0.0001, 1.0), (250.0, 60000.0)]  # (scale, offset), FX/BTC-like
PLANT_TIMES = [(300_000, 12), (300_000, 48), (60_000, 15)]  # (ltf_ms, htf/ltf ratio)


def _xf(rows, scale, offset, mirror):
    s = -scale if mirror else scale  # mirror turns the bullish setup into a bearish one
    out = []
    for row in rows:
        o, h, l, c = (s * x + offset for x in row)  # noqa: E741
        out.append((o, max(h, l), min(h, l), c))
    return out


def _planted(prices, mirror, times, variant, htf_rows=HTF_ROWS, ltf_rows=BASE + WIN_TAIL):
    scale, offset = prices
    ltf_ms, ratio = times
    htf_ms = ratio * ltf_ms
    htf = _bars(_xf(htf_rows, scale, offset, mirror), htf_ms)
    ltf = _bars(_xf(ltf_rows, scale, offset, mirror), ltf_ms, 6 * htf_ms)
    return scan(ltf, htf, ltf_ms, htf_ms, variant)


@pytest.mark.parametrize("variant", VARIANTS[:2], ids=lambda v: v.id)
@pytest.mark.parametrize("times", PLANT_TIMES, ids=lambda t: f"{t[0] // 1000}s-x{t[1]}")
@pytest.mark.parametrize("mirror", [False, True], ids=["long", "short"])
@pytest.mark.parametrize("prices", PLANT_PRICES, ids=["unit", "fx", "btc"])
def test_planted_setup_is_found_exactly_once(prices, mirror, times, variant):
    ev = _planted(prices, mirror, times, variant)
    sig = _by(ev, "signal_event")
    assert len(sig) == 1 and sig[0]["gate_passed"] and sig[0]["d"] == (-1 if mirror else 1)
    scale, offset = prices
    s = -scale if mirror else scale
    expected = [s * x + offset for x in (103, 100, 118)]
    assert [sig[0]["entry"], sig[0]["stop"], sig[0]["tp"]] == pytest.approx(expected, rel=1e-9)
    assert sig[0]["rr"] == pytest.approx(5.0)
    assert len(_by(ev, "fill_event")) == 1
    out = _by(ev, "outcome_event")
    assert len(out) == 1 and out[0]["reason"] == "TARGET"
    assert not any(e["event"].startswith("cf_") for e in ev)


@pytest.mark.parametrize("mirror", [False, True], ids=["long", "short"])
@pytest.mark.parametrize("prices", PLANT_PRICES, ids=["unit", "fx", "btc"])
@pytest.mark.parametrize("variant", VARIANTS[:2], ids=lambda v: v.id)
def test_planted_structure_with_a_missing_ingredient_gives_no_signal(variant, prices, mirror):
    no_imbalance = list(HTF_ROWS)
    no_imbalance[5] = (110, 115, 105.5, 114)  # low 105.5 <= high[3] 106: no gap, no demand zone
    no_bos = list(BASE)
    no_bos[8] = (108.5, 110.9, 108.4, 110.8)  # never closes above the swing high 111 ...
    no_bos_tail = [(103.2, 110.5, 103, 110.4)]  # ... and neither does the last bar
    for htf_rows, ltf_rows in ((no_imbalance, BASE + WIN_TAIL), (HTF_ROWS, no_bos + no_bos_tail)):
        ev = _planted(prices, mirror, PLANT_TIMES[0], variant, htf_rows, ltf_rows)
        assert _by(ev, "signal_event") == []


# --- cost option ---


def test_cost_bps_zero_means_net_equals_gross_and_cost_lowers_net():
    ltf, htf = _bars(BASE + WIN_TAIL, LTF_MS, T0), _bars(HTF_ROWS, HTF_MS)

    def outcome(cost_bps):
        ev = scan(ltf, htf, LTF_MS, HTF_MS, VARIANTS[1], cost_bps=cost_bps)
        return _by(ev, "outcome_event")[0]

    assert outcome(0.0)["net_r"] == pytest.approx(outcome(0.0)["gross_r"])
    assert outcome(50.0)["net_r"] < outcome(10.0)["net_r"] < outcome(0.0)["net_r"]


def test_shadow_script_cost_bps_flag(tmp_path):
    import csv
    import subprocess
    import sys
    from pathlib import Path

    def dump(path, rows, ms, t0=0):
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            for i, r in enumerate(rows):
                w.writerow([t0 + i * ms, *r, 1.0])

    dump(tmp_path / "htf.csv", HTF_ROWS, HTF_MS)
    dump(tmp_path / "ltf.csv", BASE + WIN_TAIL, LTF_MS, T0)
    root = Path(__file__).resolve().parent.parent

    def run(*extra):
        r = subprocess.run(
            [sys.executable, str(root / "scripts" / "ob_confluence_shadow.py"),
             "--ltf", str(tmp_path / "ltf.csv"), "--htf", str(tmp_path / "htf.csv"),
             "--ltf-ms", str(LTF_MS), "--htf-ms", str(HTF_MS), "--out", str(tmp_path / "e.jsonl"),
             "--audit-cuts", "3", *extra],
            capture_output=True, text=True, cwd=root,
        )  # fmt: skip
        assert r.returncode == 0, r.stderr
        return r.stdout

    free = run("--cost-bps", "0")
    assert "cost_bps_roundtrip=0.0" in free and "mean_net_R=5.000" in free  # TARGET = +5R gross
    default = run()
    assert "cost_bps_roundtrip=10.0" in default and "mean_net_R=5.000" not in default
