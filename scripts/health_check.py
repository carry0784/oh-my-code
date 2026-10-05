#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRCC (Temporary Runtime Confirmation Card) v3
=============================================

임시 검증용 카드 / 2026-04-28 이후 폐기 예정.

Purpose:
    P3 기간 (2026-04-14 ~ 2026-04-28) 동안 "현재 시스템이 가동 중인가"
    를 즉시 확인하는 분리된 CLI 도구.

Governance (사용자 승인 8 조건):
    1) 수동 실행만 허용
    2) cron / systemd / task scheduler / beat 등록 금지
    3) TRCC는 PLRAL을 읽지 않는다 (단방향 커플링)
    4) PLRAL은 runtime에 쓰지 않는다 (write-only append from TRCC)
    5) ledger는 append-only
    6) VRL은 운영자 수동 기록만 허용 (이 스크립트는 VRL에 append 안 함)
    7) 2026-04-28 이후 5단계 전환 절차
    8) TRCC는 post-P3에 폐기 대상

Operator Rules (사용자 추가 규칙):
    A. 실행 빈도 상한: 기본 하루 1~3회, 이상 징후 시 추가 허용,
       상시 감시처럼 반복 수동 실행 금지.
    B. VRL 수동 기록은 별도 절차 (본 스크립트 미처리).

Usage:
    python scripts/health_check.py

Exit codes:
    0  정상가동
    1  주의
    2  점검필요
    3  fatal (실행 자체 실패)

Constitution enforced by this module:
    - VC-01: no execution authority (read-only SELECT/GET + file append only)
    - VC-02: display/summarize/compare only
    - VC-03: no transition authorization
    - VC-04: fail closed on missing data (partial failure recorded, no guess)
    - DP-1: Card ↔ PLRAL 단방향 (Card never reads PLRAL)
    - DP-4: PLRAL has no execution authority (append-only file writes)
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Force UTF-8 stdout/stderr on Windows (avoid cp949 UnicodeEncodeError for '—', 한글 등)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

# ---------------------------------------------------------------------------
# Constants (fixed by spec v3, NO runtime mutation)
# ---------------------------------------------------------------------------

CARD_NAME = "TRCC"
CARD_VERSION = "v3"
DISPOSAL_DATE = "2026-04-28"
P3_WINDOW_START = "2026-04-14"
P3_WINDOW_END = "2026-04-28"
BASELINE_SHA = "48915d2"

REPO_ROOT = Path(__file__).resolve().parent.parent
OPS_STATE_PATH = REPO_ROOT / "ops_state.json"
PLRAL_DIR = REPO_ROOT / "logs" / "preeval"
RHL_PATH = PLRAL_DIR / "rhl.jsonl"
IWL_PATH = PLRAL_DIR / "iwl.jsonl"
DQL_PATH = PLRAL_DIR / "dql.jsonl"
VRL_PATH = PLRAL_DIR / "vrl.jsonl"  # read/ref only; not written by TRCC
FROZEN_MARKER_GLOB = ".frozen_*"

# Timeouts (per spec §9; 04-14 revised: tasklist on busy Windows needs >1s)
DB_TIMEOUT_S = 5
FLOWER_TIMEOUT_S = 3
PID_CHECK_TIMEOUT_S = 3
FILE_READ_TIMEOUT_S = 2

# Thresholds
OBSERVATION_STALE_THRESHOLD_S = 3600  # 1h without observation = 주의

FLOWER_API_URL = "http://localhost:5555/api/workers"
FLOWER_UI_URL = "http://localhost:5555/"

# Path A/A2 (contract: GCF-FLOWER-PROBE-VERIFICATION-CONTRACT-LOCK-v1 v1).
# Operator injects probe credential via this env var (format: user:password).
# NO default, NO fallback: unset -> hard-fail (see check_flower()).
FLOWER_PROBE_CREDENTIAL_ENV = "FLOWER_PROBE_CREDENTIAL"

DB_URL_DEFAULT = "postgresql://postgres:postgres@localhost:5432/trading"

# Reason codes for ledger-internal classification (card surface stays 3-verdict).
# Operator rule A2 — cause separation at ledger layer for post-P3 ORP/VRP.
REASON_CODES = (
    "PID_STALE_OR_UNKNOWN",
    "OBSERVED_CELERY_MATCHES",        # discovered by CommandLine scan
    "OBSERVED_CELERY_ABSENT",
    "FLOWER_UI_OK_API_AUTH_REQUIRED",   # 401: pre-injection or credential-mismatch fallback
    "FLOWER_UI_OK_API_AUTHENTICATED_OK", # Path A/A2: probe sent Basic auth, server replied 200
    "FLOWER_UNREACHABLE",              # TCP-level fail
    "DB_OK_BUT_RUNTIME_UNCONFIRMED",
    "OBSERVATION_SOURCE_EMPTY",
    "OBSERVATION_SOURCE_STALE",
    "OBSERVATION_QUERY_MISSING_TABLE",
    "OK_FULL",
)

# 3-bucket aggregation (operator 아이디어 1, 2026-04-14).
# Ledger-only metadata — card surface stays unchanged.
# Used by post-P3 ORP/VRP panel prioritization; also aggregated by offline
# analyzer. No runtime coupling.
#
# REGISTRY — ops_state / 등록정보 / PID 관리 계층
# PROBE    — 외부 접근 / 진단 계층 (Flower 등)
# DATA     — 관측 파이프라인 / DB 계층
# POSITIVE — 전 계층 정상
REASON_CODE_BUCKETS = {
    "PID_STALE_OR_UNKNOWN":              "REGISTRY",
    "OBSERVED_CELERY_MATCHES":           "REGISTRY",  # positive-signal under REGISTRY
    "OBSERVED_CELERY_ABSENT":            "REGISTRY",
    "FLOWER_UI_OK_API_AUTH_REQUIRED":    "PROBE",
    "FLOWER_UI_OK_API_AUTHENTICATED_OK": "PROBE",     # positive-signal under PROBE (Path A/A2)
    "FLOWER_UNREACHABLE":                "PROBE",
    "DB_OK_BUT_RUNTIME_UNCONFIRMED":     "DATA",
    "OBSERVATION_SOURCE_EMPTY":          "DATA",
    "OBSERVATION_SOURCE_STALE":          "DATA",
    "OBSERVATION_QUERY_MISSING_TABLE":   "DATA",
    "OK_FULL":                           "POSITIVE",
}


def bucketize_codes(codes) -> Dict[str, list]:
    """Group reason_codes by 3-bucket classification.
    Unknown codes fall into 'OTHER' bucket (forward-compat)."""
    out: Dict[str, list] = {
        "REGISTRY": [], "PROBE": [], "DATA": [], "POSITIVE": [], "OTHER": [],
    }
    for c in codes:
        b = REASON_CODE_BUCKETS.get(c, "OTHER")
        out.setdefault(b, []).append(c)
    return out


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_pid_running(pid: Optional[int]) -> Optional[bool]:
    """
    Cross-platform PID check. Returns True / False / None (unknown).
    Uses `tasklist` on Windows, os.kill(pid, 0) on Unix. No psutil required.
    Korean Windows: tasklist output may be cp949, so use bytes + decode with errors='replace'.
    """
    if pid is None:
        return None
    try:
        if sys.platform == "win32":
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, timeout=PID_CHECK_TIMEOUT_S,
            )
            # Decode safely regardless of cp949/utf-8/other
            stdout = r.stdout.decode("utf-8", errors="replace") if isinstance(
                r.stdout, (bytes, bytearray)) else str(r.stdout)
            if not stdout:
                stdout = r.stdout.decode("cp949", errors="replace") if isinstance(
                    r.stdout, (bytes, bytearray)) else ""
            # tasklist prints "INFO: No tasks..." (en) or 한국어 메시지 when PID absent.
            # Presence = the PID string quoted in CSV row.
            return f"\"{pid}\"" in stdout or f",{pid},".replace("\n", "") in stdout
        else:
            os.kill(pid, 0)
            return True
    except subprocess.TimeoutExpired:
        return None
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, not ours
    except Exception:
        return None


def plral_frozen() -> bool:
    """Return True if any .frozen_* marker exists (P3 post-04-28 freeze)."""
    try:
        for p in PLRAL_DIR.glob(".frozen_*"):
            return True
    except Exception:
        pass
    return False


def append_jsonl(path: Path, obj: Dict[str, Any]) -> Optional[str]:
    """
    Fire-and-forget append. Returns None on success, error string on failure.
    NEVER raises. NEVER reads existing lines. append-only enforcement.
    """
    try:
        if plral_frozen():
            return "PLRAL_FROZEN"
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(line + "\n")
        return None
    except Exception as e:
        return str(e)[:200]


# ---------------------------------------------------------------------------
# Collectors (READ-ONLY; VC-01 compliance)
# ---------------------------------------------------------------------------

def read_ops_state() -> Optional[Dict[str, Any]]:
    try:
        with open(OPS_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def expected_pids_from_ops_state(ops_state: Optional[Dict[str, Any]]
                                 ) -> Tuple[Optional[int], Optional[int]]:
    worker_pid: Optional[int] = None
    beat_pid: Optional[int] = None
    if not ops_state:
        return worker_pid, beat_pid
    tracks = ops_state.get("observation_tracks", []) or []
    for t in tracks:
        if t.get("status") == "ACTIVE":
            if worker_pid is None and "worker_pid" in t:
                try:
                    worker_pid = int(t["worker_pid"])
                except Exception:
                    pass
            if beat_pid is None and "beat_pid" in t:
                try:
                    beat_pid = int(t["beat_pid"])
                except Exception:
                    pass
    return worker_pid, beat_pid


def check_flower() -> Dict[str, Any]:
    """
    Probe Flower at two layers (UI root + /api/workers) to separate causes.
    - TCP/UI reachable vs. API auth required vs. fully unreachable

    Path A/A2 (contract GCF-FLOWER-PROBE-VERIFICATION-CONTRACT-LOCK-v1 v1):
        API probe reads FLOWER_PROBE_CREDENTIAL (format: user:password) and
        injects "Authorization: Basic <b64>" on GET /api/workers.

        Hard-fail if FLOWER_PROBE_CREDENTIAL is unset: raises RuntimeError
        with explicit message. No default, no fallback, no inline credential.

        Existing FLOWER_UI_OK_API_AUTH_REQUIRED (401) path is preserved for
        pre-injection and credential-mismatch fallback cases.

    No new dependency.
    """
    probe_credential = os.environ.get(FLOWER_PROBE_CREDENTIAL_ENV)
    if not probe_credential:
        raise RuntimeError(
            f"{FLOWER_PROBE_CREDENTIAL_ENV} is not set. "
            "Path A/A2 contract (GCF-FLOWER-PROBE-VERIFICATION-CONTRACT-LOCK-v1) "
            "requires operator-injected probe credential. "
            f"Set {FLOWER_PROBE_CREDENTIAL_ENV}=probe:<password> out-of-band "
            "(.env or shell env), then re-run TRCC."
        )

    out: Dict[str, Any] = {
        "ui_reachable": False,
        "api_reachable": False,
        "api_auth_required": False,
        "api_authenticated": False,   # Path A/A2: True only when probe auth + 200
        "worker_count": 0,
        "api_http_code": None,
        "ui_http_code": None,
        "api_error": None,
        "ui_error": None,
    }
    # UI probe (no auth needed for root UI)
    try:
        req = urllib.request.Request(FLOWER_UI_URL)
        with urllib.request.urlopen(req, timeout=FLOWER_TIMEOUT_S) as resp:
            out["ui_reachable"] = True
            out["ui_http_code"] = resp.getcode()
    except urllib.error.HTTPError as e:
        # Even HTTPError means TCP/HTTP layer is up
        out["ui_reachable"] = True
        out["ui_http_code"] = e.code
    except Exception as e:
        out["ui_error"] = f"{type(e).__name__}: {e}"[:120]

    # API probe (Path A/A2: Basic auth header injected, /api/workers only)
    try:
        req = urllib.request.Request(FLOWER_API_URL)
        auth_b64 = base64.b64encode(
            probe_credential.encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {auth_b64}")
        with urllib.request.urlopen(req, timeout=FLOWER_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            out["api_reachable"] = True
            out["api_http_code"] = resp.getcode()
            out["api_authenticated"] = True  # auth chain succeeded end-to-end
            out["worker_count"] = len(data) if isinstance(data, dict) else 0
    except urllib.error.HTTPError as e:
        out["api_http_code"] = e.code
        if e.code == 401:
            # Preserved fallback: credential mismatch or server rejection.
            out["api_auth_required"] = True
        out["api_error"] = f"HTTP {e.code}"[:120]
    except Exception as e:
        out["api_error"] = f"{type(e).__name__}: {e}"[:120]

    # Back-compat derived field: reachable = either UI or API at HTTP layer
    out["reachable"] = bool(out["ui_reachable"] or out["api_reachable"]
                            or out["api_auth_required"])
    return out


def scan_celery_processes() -> Dict[str, Any]:
    """
    Scan OS processes for python running 'celery ... worker' / 'celery ... beat'.
    Uses PowerShell Get-WmiObject (Windows) or ps (Unix). Read-only.
    Returns dict with observed PIDs (if found) and a 'error' note otherwise.

    This does NOT modify ops_state.json. It only records what is actually
    running at observation time. Separation of "registered" vs "observed"
    is preserved per user's direction.
    """
    out: Dict[str, Any] = {
        "observed_worker_pid": None,
        "observed_beat_pid": None,
        "scan_success": False,
        "scan_error": None,
        "raw_process_count": None,
    }
    try:
        if sys.platform == "win32":
            ps_cmd = (
                "Get-WmiObject Win32_Process -Filter \"name='python.exe' "
                "or name='celery.exe'\" | "
                "Select-Object ProcessId,CommandLine | Format-List"
            )
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, timeout=8,
            )
            raw = r.stdout.decode("utf-8", errors="replace")
            if not raw:
                raw = r.stdout.decode("cp949", errors="replace")
        else:
            r = subprocess.run(
                ["ps", "-eo", "pid,command"],
                capture_output=True, timeout=8,
            )
            raw = r.stdout.decode("utf-8", errors="replace")

        # Parse: look for "celery ... worker" / "celery ... beat"
        # Windows Format-List format: blocks separated by blank lines,
        # each with ProcessId : N / CommandLine : ...
        current_pid: Optional[int] = None
        current_cmd = ""
        blocks = []
        buf: Dict[str, str] = {}
        for line in raw.splitlines():
            line = line.rstrip()
            if not line:
                if buf:
                    blocks.append(buf)
                    buf = {}
                continue
            if ":" in line:
                key, _, val = line.partition(":")
                key = key.strip()
                val = val.strip()
                if key in ("ProcessId", "CommandLine"):
                    buf[key] = val
                else:
                    # continuation of previous multi-line value
                    if "CommandLine" in buf:
                        buf["CommandLine"] = buf["CommandLine"] + " " + line.strip()
            else:
                if "CommandLine" in buf:
                    buf["CommandLine"] = buf["CommandLine"] + " " + line.strip()
        if buf:
            blocks.append(buf)

        # Also handle Unix ps output: each line "<pid> <command>"
        if sys.platform != "win32":
            blocks = []
            for line in raw.splitlines():
                line = line.strip()
                if not line or not line[0].isdigit():
                    continue
                parts = line.split(None, 1)
                if len(parts) == 2:
                    blocks.append({"ProcessId": parts[0], "CommandLine": parts[1]})

        out["raw_process_count"] = len(blocks)
        # Tokenized matching — avoids "worker" vs "beat" substring false-positives
        # and handles trailing / interior positioning without requiring spaces.
        for b in blocks:
            cmd = b.get("CommandLine", "") or ""
            lc = cmd.lower()
            if "celery" not in lc:
                continue
            try:
                pid = int(b.get("ProcessId", "0"))
            except Exception:
                continue
            # Extract bare tokens (strip argument prefixes like -A / --)
            raw_tokens = lc.replace("\\", "/").split()
            tokens = [t.lstrip("-") for t in raw_tokens]
            has_worker = "worker" in tokens
            has_beat = "beat" in tokens
            app_hint = ("workers.celery_app" in lc
                        or "workers/celery_app" in lc)
            # worker (more specific first)
            if has_worker and out["observed_worker_pid"] is None:
                if app_hint or True:  # any celery worker is interesting
                    out["observed_worker_pid"] = pid
                    continue
            if has_beat and out["observed_beat_pid"] is None:
                if app_hint or True:
                    out["observed_beat_pid"] = pid
                    continue
        out["scan_success"] = True
    except subprocess.TimeoutExpired:
        out["scan_error"] = "timeout"
    except Exception as e:
        out["scan_error"] = f"{type(e).__name__}: {e}"[:120]
    return out


def check_db() -> Dict[str, Any]:
    """
    Read-only DB check via psycopg2. Falls back gracefully if unavailable.
    Executes SELECT-only queries. autocommit=True + readonly session.

    Table targets (verified 2026-04-14 against live schema):
        - shadow_observation_log    (shadow_timestamp, created_at)
        - paper_observations        (observed_at)  — P3 primary observation
        - ppf_novelty_events        (event_ts, created_at)  — plural

    Missing table -> per-table error field + "*_missing_table: true"
    """
    out: Dict[str, Any] = {
        "connected": False,
        "latency_ms": None,
        "read_success": False,
        # shadow_observation_log (was incorrectly "shadow_observation" in v3 rev0)
        "shadow_observation_log_total": None,
        "shadow_observation_log_last_24h": None,
        "shadow_observation_log_ts_max": None,
        "shadow_observation_log_missing_table": False,
        "shadow_observation_log_error": None,
        # paper_observations (P3 primary)
        "paper_observations_total": None,
        "paper_observations_last_24h": None,
        "paper_observations_last_1h": None,
        "paper_observations_ts_max": None,
        "paper_observations_missing_table": False,
        "paper_observations_error": None,
        # ppf_novelty_events (plural, v3 rev0 used singular)
        "ppf_novelty_events_total": None,
        "ppf_novelty_events_last_24h": None,
        "ppf_novelty_events_ts_max": None,
        "ppf_novelty_events_missing_table": False,
        "ppf_novelty_events_error": None,
        "error": None,
    }
    try:
        import psycopg2  # type: ignore
        from psycopg2 import errors as pg_errors  # type: ignore
    except Exception as e:
        out["error"] = f"psycopg2 import failed: {e}"[:120]
        return out

    db_url = os.environ.get("DATABASE_URL_SYNC") or DB_URL_DEFAULT
    t0 = time.time()
    conn = None
    try:
        conn = psycopg2.connect(db_url, connect_timeout=DB_TIMEOUT_S)
        conn.set_session(readonly=True, autocommit=True)
        out["connected"] = True
        out["latency_ms"] = int((time.time() - t0) * 1000)
        cur = conn.cursor()

        def _fmt_ts(val):
            if val is None:
                return None
            if getattr(val, "tzinfo", None) is None:
                val = val.replace(tzinfo=timezone.utc)
            return val.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # shadow_observation_log
        try:
            cur.execute("SELECT COUNT(*) FROM shadow_observation_log")
            out["shadow_observation_log_total"] = int(cur.fetchone()[0])
            cur.execute(
                "SELECT COUNT(*) FROM shadow_observation_log "
                "WHERE shadow_timestamp > NOW() - INTERVAL '24 hours'")
            out["shadow_observation_log_last_24h"] = int(cur.fetchone()[0])
            cur.execute("SELECT MAX(shadow_timestamp) FROM shadow_observation_log")
            out["shadow_observation_log_ts_max"] = _fmt_ts(cur.fetchone()[0])
        except Exception as e:
            msg = str(e).lower()
            if "does not exist" in msg or "undefined" in msg:
                out["shadow_observation_log_missing_table"] = True
            out["shadow_observation_log_error"] = str(e)[:120]

        # paper_observations — P3 primary
        try:
            cur.execute("SELECT COUNT(*) FROM paper_observations")
            out["paper_observations_total"] = int(cur.fetchone()[0])
            cur.execute(
                "SELECT COUNT(*) FROM paper_observations "
                "WHERE observed_at > NOW() - INTERVAL '24 hours'")
            out["paper_observations_last_24h"] = int(cur.fetchone()[0])
            cur.execute(
                "SELECT COUNT(*) FROM paper_observations "
                "WHERE observed_at > NOW() - INTERVAL '1 hour'")
            out["paper_observations_last_1h"] = int(cur.fetchone()[0])
            cur.execute("SELECT MAX(observed_at) FROM paper_observations")
            out["paper_observations_ts_max"] = _fmt_ts(cur.fetchone()[0])
        except Exception as e:
            msg = str(e).lower()
            if "does not exist" in msg or "undefined" in msg:
                out["paper_observations_missing_table"] = True
            out["paper_observations_error"] = str(e)[:120]

        # ppf_novelty_events
        try:
            cur.execute("SELECT COUNT(*) FROM ppf_novelty_events")
            out["ppf_novelty_events_total"] = int(cur.fetchone()[0])
            cur.execute(
                "SELECT COUNT(*) FROM ppf_novelty_events "
                "WHERE event_ts > NOW() - INTERVAL '24 hours'")
            out["ppf_novelty_events_last_24h"] = int(cur.fetchone()[0])
            cur.execute("SELECT MAX(event_ts) FROM ppf_novelty_events")
            out["ppf_novelty_events_ts_max"] = _fmt_ts(cur.fetchone()[0])
        except Exception as e:
            msg = str(e).lower()
            if "does not exist" in msg or "undefined" in msg:
                out["ppf_novelty_events_missing_table"] = True
            out["ppf_novelty_events_error"] = str(e)[:120]

        out["read_success"] = True
        cur.close()
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"[:200]
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass

    # Primary observation for verdict = paper_observations (P3 target).
    # Fallback chain for age computation: paper_observations > shadow_observation_log
    # This keeps judgment simple for card surface; ledger keeps all sources.
    return out


def last_observation_iso(db: Dict[str, Any]) -> Optional[str]:
    """Prefer paper_observations, fallback shadow_observation_log."""
    return (db.get("paper_observations_ts_max")
            or db.get("shadow_observation_log_ts_max"))


def observation_age_seconds(observed_at_iso: Optional[str]) -> Optional[int]:
    if not observed_at_iso:
        return None
    try:
        ts = datetime.strptime(observed_at_iso, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return max(0, int((now - ts).total_seconds()))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Judgment (6 fields -> 3 verdicts; spec v3 §compute)
# ---------------------------------------------------------------------------

def compute_snapshot(ops_state: Optional[Dict[str, Any]],
                     flower: Dict[str, Any],
                     db: Dict[str, Any],
                     celery_scan: Dict[str, Any]) -> Dict[str, Any]:
    # Registered (ops_state) vs observed (CommandLine scan): keep separated.
    reg_w, reg_b = expected_pids_from_ops_state(ops_state)
    obs_w = celery_scan.get("observed_worker_pid")
    obs_b = celery_scan.get("observed_beat_pid")
    scan_ok = bool(celery_scan.get("scan_success"))

    reg_w_alive = check_pid_running(reg_w) if reg_w is not None else None
    reg_b_alive = check_pid_running(reg_b) if reg_b is not None else None

    # If scan_ok AND observed_pid is not None, we KNOW the PID was alive
    # at scan time (Win32_Process / ps only returns running processes).
    # The tasklist check is a secondary cross-check but must not contradict
    # the direct observation -- fall back to tasklist only when scan didn't find one.
    if obs_w is not None and scan_ok:
        obs_w_alive: Optional[bool] = True
    elif obs_w is not None:
        obs_w_alive = check_pid_running(obs_w)
    else:
        obs_w_alive = None
    if obs_b is not None and scan_ok:
        obs_b_alive: Optional[bool] = True
    elif obs_b is not None:
        obs_b_alive = check_pid_running(obs_b)
    else:
        obs_b_alive = None

    # ops_state_stale: registered PID recorded but does not match the live one.
    # Trigger when (registered_pid differs from observed_pid) AND observed is alive.
    # Also trigger if registered_pid is confirmed dead AND observed is alive.
    def _is_stale(reg, reg_alive, obs, obs_alive):
        if obs is None or obs_alive is not True:
            return False
        if reg is None:
            return True  # nothing registered but something is running
        if reg != obs:
            return True  # registry points elsewhere
        if reg_alive is False:
            return True  # registry PID confirmed dead but something else alive
        return False

    w_stale = _is_stale(reg_w, reg_w_alive, obs_w, obs_w_alive)
    b_stale = _is_stale(reg_b, reg_b_alive, obs_b, obs_b_alive)

    # alive = True if either registered PID or observed scan confirms
    def _combine_alive(reg_alive, obs_alive):
        if reg_alive is True or obs_alive is True:
            return True
        if reg_alive is False and obs_alive is False:
            return False
        return None  # UNKNOWN

    w_alive = _combine_alive(reg_w_alive, obs_w_alive)
    b_alive = _combine_alive(reg_b_alive, obs_b_alive)

    obs_age = observation_age_seconds(last_observation_iso(db))

    return {
        "worker": {
            "registered_pid": reg_w,
            "registered_pid_alive": reg_w_alive,
            "observed_pid": obs_w,
            "observed_pid_alive": obs_w_alive,
            "ops_state_stale": w_stale,
            "alive": w_alive,
        },
        "beat": {
            "registered_pid": reg_b,
            "registered_pid_alive": reg_b_alive,
            "observed_pid": obs_b,
            "observed_pid_alive": obs_b_alive,
            "ops_state_stale": b_stale,
            "alive": b_alive,
        },
        "db": {
            "connected": bool(db.get("connected")),
            "read_success": bool(db.get("read_success")),
            "latency_ms": db.get("latency_ms"),
        },
        "flower": {
            "ui_reachable": bool(flower.get("ui_reachable")),
            "api_reachable": bool(flower.get("api_reachable")),
            "api_auth_required": bool(flower.get("api_auth_required")),
            "api_authenticated": bool(flower.get("api_authenticated")),
            "worker_count": flower.get("worker_count", 0),
            "ui_http_code": flower.get("ui_http_code"),
            "api_http_code": flower.get("api_http_code"),
        },
        "celery_scan": {
            "scan_success": bool(celery_scan.get("scan_success")),
            "scan_error": celery_scan.get("scan_error"),
            "raw_process_count": celery_scan.get("raw_process_count"),
        },
        "last_observation_age_seconds": obs_age,
        "last_observation_source": (
            "paper_observations" if db.get("paper_observations_ts_max")
            else ("shadow_observation_log"
                  if db.get("shadow_observation_log_ts_max") else None)
        ),
    }


def compute_verdict(snap: Dict[str, Any], db: Dict[str, Any]
                    ) -> Tuple[str, str, str, list]:
    """Return (verdict, issue_summary, core_runtime_status, reason_codes).

    Card surface uses only (verdict, issue_summary, crs).
    reason_codes is ledger-only (operator rule A2 — cause separation).
    """
    issues = []
    severity = 0  # 0 normal, 1 주의, 2 점검필요
    codes: list = []

    w = snap["worker"]
    be = snap["beat"]
    fl = snap["flower"]
    dd = snap["db"]

    # 점검필요 (critical) — strictly False, NOT None (VC-04 fail-closed).
    # Note: "UNKNOWN" maps to 주의, not 점검필요.
    if w["alive"] is False:
        severity = max(severity, 2); issues.append("worker DOWN")
    if be["alive"] is False:
        severity = max(severity, 2); issues.append("beat DOWN")
    if dd["connected"] is False:
        severity = max(severity, 2); issues.append("DB unreachable")

    # 주의 (warn)
    # PID registry drift: observed process running but ops_state PID stale.
    if w.get("ops_state_stale"):
        severity = max(severity, 1); issues.append("worker ops_state PID stale")
    if be.get("ops_state_stale"):
        severity = max(severity, 1); issues.append("beat ops_state PID stale")
    # Flower unreachable = neither UI nor API reachable. 401 alone is NOT unreachable.
    flower_unreachable = (not fl["ui_reachable"]
                          and not fl["api_reachable"]
                          and not fl["api_auth_required"])
    if flower_unreachable:
        severity = max(severity, 1); issues.append("Flower unreachable")
    if dd["connected"] is True and dd["read_success"] is False:
        severity = max(severity, 1); issues.append("DB read partial")
    if w["alive"] is None:
        severity = max(severity, 1); issues.append("worker alive UNKNOWN")
    if be["alive"] is None:
        severity = max(severity, 1); issues.append("beat alive UNKNOWN")
    obs_age = snap["last_observation_age_seconds"]
    if obs_age is not None and obs_age > OBSERVATION_STALE_THRESHOLD_S:
        severity = max(severity, 1)
        issues.append(f"observation stale ({obs_age}s)")
    if obs_age is None:
        severity = max(severity, 1); issues.append("observation age UNKNOWN")

    # --------- reason_codes emission (ledger-only) ---------
    # PID_STALE_OR_UNKNOWN: registered PID not alive or unknown, regardless of observed.
    reg_w_bad = (w.get("registered_pid") is None
                 or w.get("registered_pid_alive") is False)
    reg_b_bad = (be.get("registered_pid") is None
                 or be.get("registered_pid_alive") is False)
    if reg_w_bad or reg_b_bad:
        codes.append("PID_STALE_OR_UNKNOWN")

    # OBSERVED_CELERY_MATCHES: CommandLine scan found a live worker/beat.
    if (w.get("observed_pid_alive") is True
            or be.get("observed_pid_alive") is True):
        codes.append("OBSERVED_CELERY_MATCHES")
    # OBSERVED_CELERY_ABSENT: scan succeeded but nothing matched.
    if (snap.get("celery_scan", {}).get("scan_success")
            and w.get("observed_pid") is None
            and be.get("observed_pid") is None):
        codes.append("OBSERVED_CELERY_ABSENT")

    # Flower codes.
    # Path A/A2 positive signal: probe authenticated and /api/workers returned 200.
    if fl["ui_reachable"] and fl.get("api_reachable") and fl.get("api_authenticated"):
        codes.append("FLOWER_UI_OK_API_AUTHENTICATED_OK")
    # Preserved fallback: 401 (pre-injection on server side, or credential mismatch).
    if fl["ui_reachable"] and fl["api_auth_required"]:
        codes.append("FLOWER_UI_OK_API_AUTH_REQUIRED")
    if flower_unreachable:
        codes.append("FLOWER_UNREACHABLE")

    # DB ok but runtime unconfirmed: DB responds but worker/beat alive is not True.
    if (dd["connected"] is True and dd["read_success"] is True
            and not (w["alive"] is True and be["alive"] is True)):
        codes.append("DB_OK_BUT_RUNTIME_UNCONFIRMED")

    # Observation codes (prefer explicit empty vs stale).
    src = snap.get("last_observation_source")
    if src is None and obs_age is None:
        codes.append("OBSERVATION_SOURCE_EMPTY")
    if obs_age is not None and obs_age > OBSERVATION_STALE_THRESHOLD_S:
        codes.append("OBSERVATION_SOURCE_STALE")

    # Missing table across any of the 3 observation tables.
    if (db.get("shadow_observation_log_missing_table")
            or db.get("paper_observations_missing_table")
            or db.get("ppf_novelty_events_missing_table")):
        codes.append("OBSERVATION_QUERY_MISSING_TABLE")

    if not codes:
        codes.append("OK_FULL")

    verdict = ("정상가동", "주의", "점검필요")[severity]
    crs = ("RUNNING", "DEGRADED", "DOWN")[severity]
    issue_summary = "; ".join(issues) if issues else "none"
    return verdict, issue_summary, crs, codes


# ---------------------------------------------------------------------------
# Ledger append (PLRAL write-only; DP-1)
# ---------------------------------------------------------------------------

def append_rhl(ts: str, verdict: str, crs: str, issue: str,
               snap: Dict[str, Any], exec_latency_ms: int,
               flower: Dict[str, Any], reason_codes: list) -> Optional[str]:
    obj = {
        "ts": ts,
        "ledger": "rhl",
        "schema_version": 3,  # v3: adds reason_code_buckets (3-bucket aggregation)
        "source": f"trcc_{CARD_VERSION}",
        "card_verdict": verdict,
        "reason_codes": list(reason_codes),
        "reason_code_buckets": bucketize_codes(reason_codes),
        "fields": {
            "core_runtime_status": crs,
            "worker_status": {
                "alive": snap["worker"]["alive"],
                "registered_pid": snap["worker"].get("registered_pid"),
                "registered_pid_alive": snap["worker"].get("registered_pid_alive"),
                "observed_pid": snap["worker"].get("observed_pid"),
                "observed_pid_alive": snap["worker"].get("observed_pid_alive"),
                "ops_state_stale": snap["worker"].get("ops_state_stale"),
            },
            "beat_status": {
                "alive": snap["beat"]["alive"],
                "registered_pid": snap["beat"].get("registered_pid"),
                "registered_pid_alive": snap["beat"].get("registered_pid_alive"),
                "observed_pid": snap["beat"].get("observed_pid"),
                "observed_pid_alive": snap["beat"].get("observed_pid_alive"),
                "ops_state_stale": snap["beat"].get("ops_state_stale"),
            },
            "db_status": snap["db"],
            "last_observation_age_seconds": snap["last_observation_age_seconds"],
            "last_observation_source": snap.get("last_observation_source"),
            "issue_summary_text": issue,
        },
        "environment": {
            "flower_ui_reachable": bool(flower.get("ui_reachable")),
            "flower_api_reachable": bool(flower.get("api_reachable")),
            "flower_api_auth_required": bool(flower.get("api_auth_required")),
            "flower_api_authenticated": bool(flower.get("api_authenticated")),
            "flower_ui_http_code": flower.get("ui_http_code"),
            "flower_api_http_code": flower.get("api_http_code"),
            "flower_worker_count": flower.get("worker_count", 0),
            "celery_scan_success": bool(snap.get("celery_scan", {}).get("scan_success")),
            "celery_scan_raw_process_count": snap.get("celery_scan", {}).get("raw_process_count"),
        },
        "exec_latency_ms": exec_latency_ms,
    }
    return append_jsonl(RHL_PATH, obj)


def append_dql(ts: str, db: Dict[str, Any],
               flower: Dict[str, Any]) -> Optional[str]:
    paper_age = observation_age_seconds(db.get("paper_observations_ts_max"))
    shadow_age = observation_age_seconds(db.get("shadow_observation_log_ts_max"))
    nov_age = observation_age_seconds(db.get("ppf_novelty_events_ts_max"))
    # primary observation for P3 = paper_observations; shadow is fallback.
    primary_age = paper_age if paper_age is not None else shadow_age
    primary_source = (
        "paper_observations" if db.get("paper_observations_ts_max")
        else ("shadow_observation_log"
              if db.get("shadow_observation_log_ts_max") else None)
    )
    obj = {
        "ts": ts,
        "ledger": "dql",
        "schema_version": 2,  # v2: correct table names + per-table missing_table flags
        "source": f"trcc_{CARD_VERSION}",
        "counts": {
            "shadow_observation_log_total": db.get("shadow_observation_log_total"),
            "shadow_observation_log_last_24h": db.get("shadow_observation_log_last_24h"),
            "paper_observations_total": db.get("paper_observations_total"),
            "paper_observations_last_1h": db.get("paper_observations_last_1h"),
            "paper_observations_last_24h": db.get("paper_observations_last_24h"),
            "ppf_novelty_events_total": db.get("ppf_novelty_events_total"),
            "ppf_novelty_events_last_24h": db.get("ppf_novelty_events_last_24h"),
        },
        "latest_timestamps": {
            "paper_observations_ts_max": db.get("paper_observations_ts_max"),
            "shadow_observation_log_ts_max": db.get("shadow_observation_log_ts_max"),
            "ppf_novelty_events_ts_max": db.get("ppf_novelty_events_ts_max"),
        },
        "freshness": {
            "primary_observation_source": primary_source,
            "primary_observation_age_seconds": primary_age,
            "primary_observation_stale": (
                primary_age is not None
                and primary_age > OBSERVATION_STALE_THRESHOLD_S
            ),
            "paper_observation_age_seconds": paper_age,
            "shadow_observation_age_seconds": shadow_age,
            "novelty_event_age_seconds": nov_age,
            "novelty_recent_24h": (
                (db.get("ppf_novelty_events_last_24h") or 0) > 0
            ),
        },
        "source_quality": {
            "db_connect_success": bool(db.get("connected")),
            "db_read_success": bool(db.get("read_success")),
            "flower_ui_reachable": bool(flower.get("ui_reachable")),
            "flower_api_reachable": bool(flower.get("api_reachable")),
            "flower_api_auth_required": bool(flower.get("api_auth_required")),
            "flower_api_authenticated": bool(flower.get("api_authenticated")),
            "partial_failure": (
                not bool(db.get("read_success"))
                or not (flower.get("ui_reachable")
                        or flower.get("api_reachable"))
            ),
            "missing_tables": {
                "paper_observations": bool(db.get("paper_observations_missing_table")),
                "shadow_observation_log": bool(db.get("shadow_observation_log_missing_table")),
                "ppf_novelty_events": bool(db.get("ppf_novelty_events_missing_table")),
            },
            "per_table_errors": {
                "paper_observations": db.get("paper_observations_error"),
                "shadow_observation_log": db.get("shadow_observation_log_error"),
                "ppf_novelty_events": db.get("ppf_novelty_events_error"),
            },
        },
    }
    return append_jsonl(DQL_PATH, obj)


def append_iwl(ts: str, verdict: str, issue: str,
               snap: Dict[str, Any], reason_codes: list) -> Optional[str]:
    # severity 분류
    if verdict == "점검필요":
        severity = "error"
    elif verdict == "주의":
        severity = "warn"
    else:
        return "SKIP_VERDICT_NORMAL"  # should not reach here

    # category 1차 추정 (issue_summary + reason_codes 기반)
    i_lower = issue.lower()
    codes_set = set(reason_codes)
    if "DB_OK_BUT_RUNTIME_UNCONFIRMED" in codes_set and "DOWN" not in i_lower:
        # DB fine but cannot prove runtime alive — classify as observation gap
        category = "runtime_unconfirmed"
    elif "ops_state pid stale" in i_lower or "PID_STALE_OR_UNKNOWN" in codes_set:
        category = "pid_registry_drift"
    elif "down" in i_lower:
        category = "process_down"
    elif "db" in i_lower:
        category = "db_issue"
    elif "flower" in i_lower or "FLOWER_UNREACHABLE" in codes_set:
        category = "flower_unreachable"
    elif "stale" in i_lower:
        category = "stale_observation"
    elif "unknown" in i_lower:
        category = "unknown_state"
    else:
        category = "other"

    incident_id = (
        f"iwl-{ts.replace('-', '').replace(':', '').replace('Z', '')}"
        f"-{category}"
    )

    # suggested_action selected from dominant reason_code
    suggested_action = "상세 확인 필요 (Flower + DB + logs)"
    if "PID_STALE_OR_UNKNOWN" in codes_set and "OBSERVED_CELERY_MATCHES" in codes_set:
        suggested_action = ("ops_state.json PID 갱신 권장 "
                            "(관측된 PID로 registered 필드 동기화)")
    elif "FLOWER_UI_OK_API_AUTH_REQUIRED" in codes_set:
        suggested_action = (
            "Flower API auth required — FLOWER_UNAUTHENTICATED_API=true "
            "환경변수 확인 또는 운영자 인증 정보 설정")
    elif "OBSERVATION_QUERY_MISSING_TABLE" in codes_set:
        suggested_action = (
            "TRCC 테이블명 업데이트 필요 — 스키마와 불일치")
    elif "OBSERVATION_SOURCE_EMPTY" in codes_set:
        suggested_action = (
            "paper_observations 비어있음 — P3 관측 파이프라인 상태 확인")

    obj = {
        "ts": ts,
        "ledger": "iwl",
        "schema_version": 3,  # v3: adds reason_code_buckets
        "source": f"trcc_{CARD_VERSION}",
        "incident_id": incident_id,
        "severity": severity,
        "category": category,
        "triggering_verdict": verdict,
        "reason_codes": list(reason_codes),
        "reason_code_buckets": bucketize_codes(reason_codes),
        "description": issue,
        "affected_surface": {
            "core_runtime": verdict == "점검필요",
            "data_pipeline": ("db" in i_lower or "stale" in i_lower
                              or "OBSERVATION_QUERY_MISSING_TABLE" in codes_set),
            "observation": ("observation" in i_lower or "stale" in i_lower
                            or "OBSERVATION_SOURCE_EMPTY" in codes_set
                            or "OBSERVATION_SOURCE_STALE" in codes_set),
            "governance_only": (verdict == "주의"
                                and category == "pid_registry_drift"
                                and "down" not in i_lower),
        },
        "recovery": {
            "auto_recovered": False,
            "manual_action_required": True,
            "suggested_action": suggested_action,
        },
        "repeat_count_in_window_24h": None,  # 분석 시 계산 (post-P3)
    }
    return append_jsonl(IWL_PATH, obj)


# ---------------------------------------------------------------------------
# Output rendering (fixed layout, spec v3)
# ---------------------------------------------------------------------------

VERDICT_BANNER = {
    "정상가동": "[ OK       ] 정상가동",
    "주의":     "[ WARN     ] 주의",
    "점검필요": "[ INVEST   ] 점검필요",
}


def _fmt_pid(pid: Optional[int]) -> str:
    return str(pid) if pid is not None else "-"


def render_card(snap: Dict[str, Any], verdict: str, issue: str,
                crs: str, db: Dict[str, Any], flower: Dict[str, Any],
                ts: str, exec_latency_ms: int,
                rhl_err: Optional[str], dql_err: Optional[str],
                iwl_err: Optional[str]) -> str:
    """사용자에게 보여주는 카드. 하단 3줄 고정 (v3 spec).

    Card surface는 3판정만 노출 (정상가동 / 주의 / 점검필요).
    reason_codes는 카드 표면에 노출하지 않고 ledger에만 기록.
    """
    lines = []
    lines.append("=" * 72)
    lines.append(f"  {CARD_NAME} {CARD_VERSION}  --  {VERDICT_BANNER[verdict]}")
    lines.append("=" * 72)
    lines.append(f"  ts                    : {ts}")
    lines.append(f"  core_runtime_status   : {crs}")
    # worker
    w = snap["worker"]
    lines.append(
        f"  worker_status         : alive={str(w['alive']):<5} "
        f"reg_pid={_fmt_pid(w.get('registered_pid'))} "
        f"obs_pid={_fmt_pid(w.get('observed_pid'))} "
        f"stale={w.get('ops_state_stale')}"
    )
    # beat
    be = snap["beat"]
    lines.append(
        f"  beat_status           : alive={str(be['alive']):<5} "
        f"reg_pid={_fmt_pid(be.get('registered_pid'))} "
        f"obs_pid={_fmt_pid(be.get('observed_pid'))} "
        f"stale={be.get('ops_state_stale')}"
    )
    # db
    d = snap["db"]
    lines.append(
        f"  db_status             : connected={str(d['connected']):<5} "
        f"read={str(d['read_success']):<5} "
        f"latency_ms={d['latency_ms']}"
    )
    # observation
    obs = snap["last_observation_age_seconds"]
    src = snap.get("last_observation_source") or "-"
    obs_str = f"{obs}s" if obs is not None else "UNKNOWN"
    lines.append(f"  last_observation_age  : {obs_str}  (source={src})")
    lines.append(f"  issue_summary         : {issue}")
    lines.append("-" * 72)
    # 보조 정보 (정보성, 판정 반영됨)
    fl = flower
    lines.append(
        f"  aux: flower ui={fl.get('ui_reachable')} "
        f"api={fl.get('api_reachable')} "
        f"auth_required={fl.get('api_auth_required')} "
        f"authenticated={fl.get('api_authenticated')} "
        f"wc={fl.get('worker_count')} | exec={exec_latency_ms}ms"
    )
    cs = snap.get("celery_scan", {})
    lines.append(
        f"  aux: celery_scan success={cs.get('scan_success')} "
        f"raw_procs={cs.get('raw_process_count')} "
        f"err={cs.get('scan_error')}"
    )
    if db.get("paper_observations_total") is not None:
        lines.append(
            f"  aux: paper_obs total={db.get('paper_observations_total')} "
            f"1h={db.get('paper_observations_last_1h')} "
            f"24h={db.get('paper_observations_last_24h')}"
        )
    elif db.get("paper_observations_missing_table"):
        lines.append("  aux: paper_obs MISSING TABLE")
    if db.get("shadow_observation_log_total") is not None:
        lines.append(
            f"  aux: shadow_obs total={db.get('shadow_observation_log_total')} "
            f"24h={db.get('shadow_observation_log_last_24h')}"
        )
    elif db.get("shadow_observation_log_missing_table"):
        lines.append("  aux: shadow_obs MISSING TABLE")
    if db.get("ppf_novelty_events_total") is not None:
        lines.append(
            f"  aux: ppf_novelty total={db.get('ppf_novelty_events_total')} "
            f"24h={db.get('ppf_novelty_events_last_24h')} "
            f"max_ts={db.get('ppf_novelty_events_ts_max')}"
        )
    elif db.get("ppf_novelty_events_missing_table"):
        lines.append("  aux: ppf_novelty MISSING TABLE")
    lines.append("-" * 72)
    # 고정 하단 3줄 (spec v3)
    lines.append(
        f"  임시 검증용 카드 / {DISPOSAL_DATE} 이후 폐기 예정 "
        f"(P3: {P3_WINDOW_START} ~ {P3_WINDOW_END})"
    )
    lines.append(
        "  상세 분석  : Flower http://localhost:5555  "
        "+  DB psql (read-only)  +  tail logs/celery_*.log"
    )
    rhl_mark = "ok" if rhl_err is None else f"FAIL({rhl_err})"
    dql_mark = "ok" if dql_err is None else f"FAIL({dql_err})"
    if iwl_err is None and verdict == "정상가동":
        iwl_mark = "skip"
    elif iwl_err == "SKIP_VERDICT_NORMAL":
        iwl_mark = "skip"
    elif iwl_err is None:
        iwl_mark = "ok"
    else:
        iwl_mark = f"FAIL({iwl_err})"
    lines.append(
        f"  학습 기록  : RHL={rhl_mark}  DQL={dql_mark}  "
        f"IWL={iwl_mark}  (VRL = 운영자 수동)"
    )
    lines.append("=" * 72)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _safe_print(text: str) -> None:
    """Print with encoding fallback. Never raises."""
    try:
        print(text)
    except UnicodeEncodeError:
        try:
            enc = getattr(sys.stdout, "encoding", None) or "ascii"
            sys.stdout.write(text.encode(enc, errors="replace").decode(enc, errors="replace"))
            sys.stdout.write("\n")
            sys.stdout.flush()
        except Exception:
            try:
                sys.stdout.write(text.encode("ascii", errors="replace").decode("ascii"))
                sys.stdout.write("\n")
                sys.stdout.flush()
            except Exception:
                pass
    except Exception:
        pass


def main() -> int:
    t_start = time.time()
    ts = utc_iso()

    # verdict computation + PLRAL append inside try.
    # Print isolated afterwards so encoding failures don't mask the verdict exit code.
    verdict = "점검필요"  # fail-closed default (VC-04)
    exit_code = 3
    try:
        ops_state = read_ops_state()
        flower = check_flower()
        db = check_db()
        celery_scan = scan_celery_processes()
        snap = compute_snapshot(ops_state, flower, db, celery_scan)
        verdict, issue, crs, reason_codes = compute_verdict(snap, db)
        exec_latency_ms = int((time.time() - t_start) * 1000)

        # PLRAL append (fire-and-forget, DP-1 preserves isolation)
        rhl_err = append_rhl(ts, verdict, crs, issue, snap,
                             exec_latency_ms, flower, reason_codes)
        dql_err = append_dql(ts, db, flower)
        iwl_err: Optional[str] = None
        if verdict != "정상가동":
            iwl_err = append_iwl(ts, verdict, issue, snap, reason_codes)

        exit_code = {"정상가동": 0, "주의": 1, "점검필요": 2}[verdict]

        out = render_card(snap, verdict, issue, crs, db, flower, ts,
                          exec_latency_ms, rhl_err, dql_err, iwl_err)
    except Exception as e:
        # fatal collection/judgment path; PLRAL append at least should not
        # propagate exceptions, so this is only for catastrophic failures.
        sys.stderr.write(f"[TRCC FATAL] {type(e).__name__}: {e}\n")
        return 3

    # Print outside try: encoding failures must not change exit code.
    _safe_print(out)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
