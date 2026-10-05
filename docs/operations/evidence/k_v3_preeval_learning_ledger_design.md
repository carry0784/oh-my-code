# K-V3 PLRAL: Passive Learning & Reference Accumulation Layer (v3)

> **공식 명칭**: **PLRAL** (Passive Learning & Reference Accumulation Layer)
> **문서 버전**: v3 (2026-04-14 재설계)
> **v1→v2→v3 재설계 사유**: Card와 학습층의 명시적 분리, 4 ledger 구조화, 2 pack 분리 (사용자 6렌즈 평가 반영)
> **발행일**: 2026-04-14
> **수집 기간**: **2026-04-14 ~ 2026-04-28** (P3 기간 전용, TRCC 생애 주기와 동기화)
> **보존 기간**: 영구 보존 (post-P3 후 Dashboard 재설계 및 운영 참고 자료로 활용)
> **상위 헌법**: `k_v3_visualization_layer_governance.md` (VC-01~04)
> **분리 대응**: `k_v3_system_health_card_spec.md` (TRCC, 분리된 카드 스펙)
> **저장 형식**: **JSONL append-only files** (파일 4개로 분리)
> **구현 방식**: 파일 시스템 기반, read-only 수집 (P3 비간섭 최대화)

---

## 0. 설계 철학 (v3 핵심 원칙)

### 0.1 사용자 의도 직접 인용

> "카드의 분리성과 검증기간의 학습데이터를 어떻게 효과적으로 이용하여 검증후에 운영및 시각화에 잘 이용할수 있는가가 중요 핵심이다"
>
> "현재 이 시각부터 모든 데이터 자료들과 운영시스템을 학습하여 검증기간이 지난후에 운영 혹은 시각화에 참고자료로 쓸수 있게 설계도 구축해"

### 0.2 v3 설계 4원칙

| # | 원칙 | 구현 |
|---|------|------|
| **DP-1** | **Card ↔ Learning 엄격 분리** | TRCC와 PLRAL 서로 모르는 구조. 단방향 커플링(Card → PLRAL write-only). PLRAL 실패가 Card 판정을 오염시키지 않음 |
| **DP-2** | **수집 목적별 Ledger 분리** | 단일 ledger 금지. 4개 ledger로 분류 (RHL/IWL/DQL/VRL). 섞지 않음 |
| **DP-3** | **활용 목적별 Pack 분리** | post-P3에 단일 산출물 금지. 운영용(ORP) / 시각화용(VRP) 2개 pack으로 목적 분리 |
| **DP-4** | **학습층은 실행 권한 없음** | PLRAL은 VC-01~04 전승. 기록만, 판정/전이/실행 불가 |

### 0.3 "Passive" 의 의미

- **수동 수집**: 운영자가 TRCC를 실행할 때만 주 ledger(RHL/DQL) append
- **수동 관찰**: 시스템이 PLRAL을 push하지 않음. PLRAL은 pull-only
- **수동 해석**: 자동 경보 없음. 04-28 이후 운영자가 분석 스크립트로 해석
- **수동 반영**: PLRAL이 운영 상태를 변경하지 않음. 기록만

---

## 1. PLRAL 전체 구조

### 1.1 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────────┐
│                        TRCC (분리된 카드)                     │
│                  scripts/health_check.py                     │
│                                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │   Card 판정 로직 (6 필드 → 3 judgement)              │   │
│   │   * PLRAL 미로딩 (Card는 PLRAL을 읽지 않음)          │   │
│   └─────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│   ┌─────────────────────────────────────────────────────┐   │
│   │   Card 출력: stdout (사람이 읽음)                    │   │
│   └─────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼ (write-only, fire-and-forget)    │
└──────────────────────────┼──────────────────────────────────┘
                           │
                           │  append JSONL
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              PLRAL (Passive Learning Layer)                  │
│                                                              │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐│
│  │    RHL    │  │    IWL    │  │    DQL    │  │    VRL    ││
│  │ Runtime   │  │ Incident  │  │   Data    │  │ Visualiz. ││
│  │  Health   │  │ & Warning │  │  Quality  │  │ Reference ││
│  │           │  │           │  │           │  │           ││
│  │ rhl.jsonl │  │ iwl.jsonl │  │ dql.jsonl │  │ vrl.jsonl ││
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘│
│        │              │              │              │      │
└────────┼──────────────┼──────────────┼──────────────┼──────┘
         │              │              │              │
         └──────────────┴──────────────┴──────────────┘
                              │
                              ▼ (04-28 이후, offline analysis)
┌─────────────────────────────────────────────────────────────┐
│                   Post-P3 Analysis Layer                     │
│                                                              │
│   ┌───────────────────────┐     ┌───────────────────────┐   │
│   │   ORP (Operations     │     │   VRP (Visualization  │   │
│   │   Reference Pack)     │     │   Reference Pack)     │   │
│   │                       │     │                       │   │
│   │ - 장애 패턴           │     │ - 자주 본 항목         │   │
│   │ - 건강 추이           │     │ - 꼭 필요한 카드/패널   │   │
│   │ - 주의 발생 근거      │     │ - 불필요했던 정보      │   │
│   │ - 운영 확인 루틴      │     │ - 경고 표현 방식       │   │
│   │                       │     │ - freshness 기준       │   │
│   └───────────┬───────────┘     └───────────┬───────────┘   │
└───────────────┼─────────────────────────────┼───────────────┘
                │                             │
                ▼                             ▼
         운영 표준 개선             Dashboard 전면 재설계
```

### 1.2 단방향 커플링 불변식

| 방향 | 허용 | 금지 |
|------|------|------|
| TRCC → PLRAL | write-only append | - |
| PLRAL → TRCC | - | read, query, subscribe 모두 금지 |
| PLRAL → 운영 시스템 | - | write, mutate 금지 |
| 운영 시스템 → PLRAL | read-only SELECT/GET만 | write 금지 |

**결과**: PLRAL은 완전히 수동적. 고장나도 시스템에 영향 없음.

---

## 2. 4 Ledger 구조

### 2.1 Ledger 한눈에 보기

| Ledger | 공식명 | 경로 | 기록 주체 | 기록 빈도 | 핵심 질문 |
|--------|-------|------|----------|----------|----------|
| **RHL** | Runtime Health Ledger | `logs/preeval/rhl.jsonl` | TRCC 실행 시 자동 | 매 Card 실행 (일 1~3회) | "어느 시점에 시스템이 어떤 상태였는가?" |
| **IWL** | Incident & Warning Ledger | `logs/preeval/iwl.jsonl` | TRCC verdict≠정상가동 시 자동 | 이상 징후 감지 시 | "어떤 장애가 언제 왜 발생했고 어떻게 복구됐는가?" |
| **DQL** | Data Quality Ledger | `logs/preeval/dql.jsonl` | TRCC 실행 시 자동 | 매 Card 실행 | "관측/novelty/freshness 데이터는 얼마나 누적됐고 품질은 어떤가?" |
| **VRL** | Visualization Reference Ledger | `logs/preeval/vrl.jsonl` | **운영자 수동 기록** | 운영 중 발견 시 | "Dashboard에 뭐가 필요하고 뭐가 불필요한가?" |

### 2.2 Ledger 분리가 필요한 이유

1. **RHL + IWL 섞으면**: "어제 주의 몇 번 떴나"를 세려면 매번 전체 파일 스캔 필요
2. **RHL + DQL 섞으면**: "observation count 추이"를 보려면 health 판정과 무관한 필드 섞여 분석 복잡화
3. **RHL + VRL 섞으면**: 운영자의 주관 판단 메모와 기계 판정이 섞여 신뢰도 오염
4. **분리된 현재**: 각 파일이 단일 목적 → 분석 단순, 해석 명확, post-P3 pack 조립 용이

---

## 3. RHL (Runtime Health Ledger)

### 3.1 목적

시점별 worker/beat/db 상태, 관측 지연, 시스템 건강 판정, issue summary를 누적.
**사용자 정의(메시지6)**: "시점별 worker/beat/db 상태, 최근 관측 지연, 시스템 건강 판정, issue summary"

### 3.2 경로

```
logs/preeval/rhl.jsonl
```

### 3.3 스키마

```json
{
  "ts": "2026-04-14T14:05:12Z",
  "ledger": "rhl",
  "schema_version": 1,
  "source": "trcc_v3",
  "card_verdict": "정상가동 | 주의 | 점검필요",
  "fields": {
    "core_runtime_status": "RUNNING | DEGRADED | DOWN | UNKNOWN",
    "worker_status": {
      "alive": true,
      "pid": 88008,
      "ops_state_pid": 110780,
      "pid_mismatch": true
    },
    "beat_status": {
      "alive": true,
      "pid": 97588,
      "ops_state_pid": 25956,
      "pid_mismatch": true
    },
    "db_status": {
      "connected": true,
      "latency_ms": 18,
      "active_connections": 3
    },
    "last_observation_age_seconds": 42,
    "issue_summary_text": "PID mismatch detected (worker, beat)"
  },
  "environment": {
    "flower_reachable": true,
    "postgres_port": 5432,
    "redis_port": 6379
  },
  "exec_latency_ms": 342
}
```

### 3.4 기록 규칙

- TRCC 실행마다 **반드시 1줄** append
- verdict 종류와 무관 (정상/주의/점검 모두 기록)
- Card가 실패해도 부분 정보라도 기록 (DP-1 원칙: PLRAL은 Card 실패를 복구하지 않고 관찰)

### 3.5 활용 질의 예시 (post-P3)

```bash
# verdict 분포
jq 'select(.ledger=="rhl") | .card_verdict' logs/preeval/rhl.jsonl | sort | uniq -c

# worker alive 시간별 추이
jq 'select(.ledger=="rhl") | {ts, worker: .fields.worker_status.alive}' logs/preeval/rhl.jsonl

# PID mismatch 발생 비율
jq 'select(.ledger=="rhl" and .fields.worker_status.pid_mismatch==true)' logs/preeval/rhl.jsonl | wc -l
```

---

## 4. IWL (Incident & Warning Ledger)

### 4.1 목적

주의/점검필요 발생 시각, 원인 분류, 영향 범위, 복구 여부, 반복 발생 여부를 누적.
**사용자 정의(메시지6)**: "주의/점검필요 발생 시각, 원인 분류, 영향 범위, 복구 여부, 반복 발생 여부"

### 4.2 경로

```
logs/preeval/iwl.jsonl
```

### 4.3 스키마

```json
{
  "ts": "2026-04-14T14:05:12Z",
  "ledger": "iwl",
  "schema_version": 1,
  "source": "trcc_v3",
  "incident_id": "iwl-20260414-140512-abc123",
  "severity": "warn | error",
  "category": "pid_mismatch | stale_observation | task_failure | db_unreachable | flower_unreachable | verdict_transition | other",
  "triggering_verdict": "주의 | 점검필요",
  "description": "PID mismatch detected: worker PID 88008 vs ops_state 110780",
  "affected_surface": {
    "core_runtime": false,
    "data_pipeline": false,
    "observation": false,
    "governance_only": true
  },
  "recovery": {
    "auto_recovered": false,
    "manual_action_required": true,
    "suggested_action": "ops_state.json 갱신 (수동)"
  },
  "repeat_count_in_window_24h": 3
}
```

### 4.4 기록 규칙

- TRCC verdict가 `주의` 또는 `점검필요`인 경우 **반드시 append**
- verdict=정상가동인 경우 append하지 않음 (IWL은 이상 전용)
- `incident_id` 는 시각+카테고리 hash로 고유화 (중복 방지 없음, 연속 발생은 연속 기록)
- `repeat_count_in_window_24h` 는 수집 시점 직전 24h 내 동일 category 등장 횟수

### 4.5 활용 질의 예시 (post-P3)

```bash
# 카테고리별 발생 빈도
jq 'select(.ledger=="iwl") | .category' logs/preeval/iwl.jsonl | sort | uniq -c

# 반복 발생 패턴 (post-P3 운영 표준 개선 재료)
jq 'select(.ledger=="iwl" and .repeat_count_in_window_24h>=3)' logs/preeval/iwl.jsonl

# 수동 조치 필요 건만
jq 'select(.ledger=="iwl" and .recovery.manual_action_required==true)' logs/preeval/iwl.jsonl
```

---

## 5. DQL (Data Quality Ledger)

### 5.1 목적

observation 누적, novelty 누적, freshness 문제, gap/mismatch 여부, source 품질 상태를 누적.
**사용자 정의(메시지6)**: "observation 누적, novelty 누적, freshness 문제, gap/mismatch 여부, source 품질 상태"

### 5.2 경로

```
logs/preeval/dql.jsonl
```

### 5.3 스키마

```json
{
  "ts": "2026-04-14T14:05:12Z",
  "ledger": "dql",
  "schema_version": 1,
  "source": "trcc_v3",
  "counts": {
    "shadow_observation_total": 1248,
    "shadow_observation_last_1h": 24,
    "shadow_observation_last_24h": 560,
    "ppf_novelty_event_total": 4,
    "ppf_novelty_event_last_24h": 0
  },
  "latest_timestamps": {
    "shadow_observed_at_max": "2026-04-14T14:04:30Z",
    "ppf_novelty_event_ts_max": "2026-04-14T08:22:11Z"
  },
  "freshness": {
    "shadow_observation_age_seconds": 42,
    "shadow_observation_stale": false,
    "novelty_event_age_seconds": 21061,
    "novelty_recent_24h": false
  },
  "gap_checks": {
    "observation_gap_over_300s_in_last_24h": 2,
    "expected_hourly_count_baseline": 24,
    "hourly_count_deviation_flag": false
  },
  "source_quality": {
    "db_read_success": true,
    "flower_read_success": true,
    "pid_check_success": true,
    "partial_failure": false
  }
}
```

### 5.4 기록 규칙

- TRCC 실행마다 **반드시 1줄** append (verdict 무관)
- DQL은 RHL 과 동시 기록 (같은 ts, 서로 다른 파일)
- 수집 실패 시에도 `source_quality.*_success=false` 로 기록 (누락 금지)

### 5.5 활용 질의 예시 (post-P3)

```bash
# observation 누적 추이
jq 'select(.ledger=="dql") | {ts, total: .counts.shadow_observation_total}' logs/preeval/dql.jsonl

# novelty event 전체 (드물면 드문 대로 기록)
jq 'select(.ledger=="dql") | {ts, novelty_total: .counts.ppf_novelty_event_total}' logs/preeval/dql.jsonl

# freshness 위반 빈도
jq 'select(.ledger=="dql" and .freshness.shadow_observation_stale==true)' logs/preeval/dql.jsonl | wc -l
```

---

## 6. VRL (Visualization Reference Ledger)

### 6.1 목적 (v3 신규 핵심)

운영자가 자주 확인한 항목, 실제 유용했던 경고 문구, 필요했던 패널, 불필요했던 정보, post-P3 dashboard 후보 항목을 누적.
**사용자 정의(메시지6)**: "운영자가 자주 확인한 항목, 실제 유용했던 경고 문구, 필요했던 패널, 불필요했던 정보, post-P3 dashboard 후보 항목"

### 6.2 왜 VRL 이 따로 필요한가

- RHL/IWL/DQL 은 **기계 수집** (객관 데이터)
- VRL 은 **운영자 관찰 메모** (주관 판단, Dashboard 재설계 직접 재료)
- 기계 데이터만으로는 "운영자가 실제로 자주 봤는가", "이 경고가 유용했는가" 를 알 수 없음
- VRL 없이 Dashboard 재설계하면 또다시 개발자 추측 기반 → v3 Stage Dashboard 의 존재 이유 상실

### 6.3 경로

```
logs/preeval/vrl.jsonl
```

### 6.4 스키마

```json
{
  "ts": "2026-04-14T14:05:12Z",
  "ledger": "vrl",
  "schema_version": 1,
  "source": "operator_manual | trcc_v3_post_render_hint",
  "observation_type": "frequent_query | useful_warning | needed_panel | useless_info | threshold_pain | dashboard_candidate",
  "context": {
    "card_verdict_at_time": "주의",
    "card_issue_summary": "PID mismatch detected",
    "time_of_day": "14:05"
  },
  "note": "자유 텍스트 메모. 예: 'PID mismatch는 실제로는 긴급 아님, 경고로 충분'",
  "candidate_for_dashboard": {
    "suggested": true,
    "panel_name_hint": "Process Identity Panel",
    "panel_field_hint": "worker_pid, beat_pid, ops_state_pid, mismatch_flag",
    "priority": "high | medium | low"
  }
}
```

### 6.5 기록 규칙

- **주 기록 방식: 운영자 수동 기록** (TRCC 실행과 무관)
  - 실행 예: 별도 CLI 또는 직접 텍스트 에디터로 append
- 보조 기록: TRCC post-render hint (Card 출력 후 "추가 기록하려면 vrl-append" 안내만, 자동 기록 없음)
- **운영자의 판단**을 기록하는 ledger이므로 기계가 자동 append 금지 (오염 방지)

### 6.6 관찰 타입 (`observation_type`) 6종

| 타입 | 의미 | 활용 |
|------|------|------|
| `frequent_query` | 운영자가 자주 확인한 필드/값 | Dashboard 우선 순위 상위 |
| `useful_warning` | 실제로 도움됐던 경고 | 경고 문구 표준화 |
| `needed_panel` | "이게 한 화면에 있으면" 싶었던 정보 | 신규 패널 후보 |
| `useless_info` | 보기만 하고 쓸모 없던 정보 | Dashboard 제외 목록 |
| `threshold_pain` | 판정 임계값이 맞지 않다고 느낀 순간 | 임계값 재조정 근거 |
| `dashboard_candidate` | 명시적 Dashboard 항목 제안 | VRP 직접 입력 |

### 6.7 활용 질의 예시 (post-P3)

```bash
# Dashboard 후보 우선순위별
jq 'select(.ledger=="vrl" and .candidate_for_dashboard.suggested==true) | {priority: .candidate_for_dashboard.priority, panel: .candidate_for_dashboard.panel_name_hint}' logs/preeval/vrl.jsonl

# 자주 확인한 항목
jq 'select(.ledger=="vrl" and .observation_type=="frequent_query")' logs/preeval/vrl.jsonl

# 불필요 정보 (제거 후보)
jq 'select(.ledger=="vrl" and .observation_type=="useless_info")' logs/preeval/vrl.jsonl
```

---

## 7. Ledger 공통 규칙

### 7.1 공통 필드 (4 ledger 모두)

| 필드 | 타입 | 비고 |
|------|------|------|
| `ts` | ISO8601 UTC | 필수 |
| `ledger` | string | `rhl` / `iwl` / `dql` / `vrl` |
| `schema_version` | int | 현재 1 |
| `source` | string | 기록 주체 식별 |

### 7.2 파일 형식

- JSONL (JSON Lines, 1줄 1이벤트)
- UTF-8, LF 개행, 라인 끝에 `\n` 필수
- BOM 금지, CRLF 금지

### 7.3 파일 크기 예상

| Ledger | 일 라인 수 | 2주 합 | 비고 |
|--------|-----------|-------|------|
| RHL | 1~3 | ~40 | Card 실행 빈도와 동일 |
| IWL | 0~5 | ~30 | verdict≠정상가동 시만 |
| DQL | 1~3 | ~40 | RHL과 동시 기록 |
| VRL | 0~10 | ~50 | 운영자 임의 |
| **합계** | **2~21** | **~160** | 1 line ≈ 500~1500 byte → 2주 총 < 500KB |

Rotation 금지 (연속성 보전).

### 7.4 권한 정책

- 생성자: 운영자 (manual, 최초 1회)
- append 권한: TRCC 실행 권한 보유자 + 운영자 (VRL)
- read 권한: 전체 (감사 투명성)
- **수정/삭제 권한 없음** (정책적 봉인)

---

## 8. 수집 트리거

### 8.1 TRCC 실행이 주 트리거

| Ledger | TRCC 실행 시 | 조건 |
|--------|-------------|------|
| RHL | 반드시 1줄 append | 무조건 |
| DQL | 반드시 1줄 append | 무조건 |
| IWL | 조건부 append | verdict∈{주의, 점검필요} |
| VRL | append 없음 | 운영자 수동만 |

### 8.2 VRL 전용 수동 트리거

- 운영자가 텍스트 에디터/CLI로 직접 append
- TRCC는 VRL을 건드리지 않음 (분리 강제)

### 8.3 자동화 금지

- cron/systemd/scheduled task 등록 금지 (v3 Prohibited Zone B-3 재인용)
- Card 부재 시 RHL/DQL/IWL append 금지 (단일 경로 강제)

### 8.4 트리거 불변식

```
forall e in RHL: exists t in TRCC runs s.t. e.ts ≈ t.ts
forall e in IWL: exists r in RHL s.t. r.ts = e.ts AND r.card_verdict ≠ '정상가동'
forall e in DQL: exists r in RHL s.t. r.ts = e.ts
```

---

## 9. 데이터 원천 및 비간섭 수집 방식

### 9.1 원천별 수집 방식

| 원천 | 수집 방식 | 간섭도 | Ledger |
|------|----------|--------|--------|
| PostgreSQL | read-only SELECT | 무간섭 | RHL(db_status), DQL(counts/latest) |
| Flower REST | HTTP GET `/api/workers`, `/api/tasks` | 무간섭 | RHL(worker/beat alive), DQL(source_quality) |
| OS process | `psutil.pid_exists`, `psutil.Process(pid).cmdline()` | 무간섭 | RHL(pid, alive) |
| ops_state.json | read-only file read | 무간섭 | RHL(ops_state_pid), IWL(pid_mismatch 발견 시) |
| logs/*.pid | read-only file read | 무간섭 | RHL 보조 |

### 9.2 타임아웃 및 부분 실패 처리

| 원천 | 타임아웃 | 실패 시 처리 |
|------|---------|------------|
| DB | 5초 | RHL에 `db_status.connected=false`, DQL에 `source_quality.db_read_success=false` |
| Flower | 3초 | RHL에 `flower_reachable=false`, DQL에 `flower_read_success=false` |
| OS process | 1초 | RHL에 `alive=null` (unknown) |
| ops_state.json | 2초 | RHL에 `ops_state_pid=null` |

**원칙**: 수집 실패도 ledger에 **기록**. 라인 누락 금지.

---

## 10. 2 Packs (Post-P3 활용 계층)

### 10.1 Pack 분리 철학

v2의 단일 활용 로드맵의 한계: "재평가 보조 + Dashboard 재설계" 를 한 묶음으로 둬서 우선순위·포맷·소비자가 혼재.

v3 는 **소비자별 pack** 으로 분리.

### 10.2 ORP (Operations Reference Pack)

**소비자**: 운영자, Mode 1/2 운영 표준 정비 담당
**질문**: "지난 2주 동안 어떤 장애가 얼마나, 왜 발생했고, 현재 운영 루틴 중 어떤 것이 유효했는가?"

#### 10.2.1 구성

| 항목 | 원천 Ledger | 산출 형태 |
|------|-----------|----------|
| 장애 패턴 | IWL | 카테고리별 발생 빈도, 시간대 분포 |
| 건강 상태 추이 | RHL | verdict 시계열, 전이 빈도 |
| 주의/점검필요 발생 근거 | RHL + IWL | 각 incident 당 연관 RHL snapshot |
| 운영 확인 루틴 | RHL (ts 분포) | Card 실행 시간대/빈도 패턴 |
| 반복 발생 문제 | IWL (repeat_count≥3) | top incidents 리스트 |

#### 10.2.2 산출물

- `docs/operations/evidence/p3_post_operations_reference_pack.md` (post-P3 생성)
- 첨부: 분석 jq/python 스크립트 출력물

### 10.3 VRP (Visualization Reference Pack)

**소비자**: Stage Dashboard 설계자
**질문**: "Dashboard 에 뭐가 반드시 필요하고, 뭐는 빼야 하며, 경고 표현은 어떻게 해야 하는가?"

#### 10.3.1 구성

| 항목 | 원천 Ledger | 산출 형태 |
|------|-----------|----------|
| 자주 본 항목 | VRL (frequent_query) | 우선순위 상위 필드 목록 |
| 꼭 필요한 카드/패널 | VRL (needed_panel, dashboard_candidate) | 패널 후보 목록 + 우선순위 |
| 불필요했던 정보 | VRL (useless_info) | 제외 목록 |
| 경고 표현 방식 | VRL (useful_warning) + IWL (category text) | 표현 표준 가이드 |
| freshness/integrity 표시 기준 | DQL (freshness, gap_checks) | 임계값 표준안 |
| 임계값 재조정 후보 | VRL (threshold_pain) + RHL verdict 분포 | 재조정 권고안 |

#### 10.3.2 산출물

- `docs/operations/evidence/p3_post_visualization_reference_pack.md` (post-P3 생성)
- 첨부: Dashboard 요구사항 초안 (VC-01~04 전승)

### 10.4 Pack 간 경계 규칙

- ORP 는 **운영 판정**에 쓰이지만 Dashboard 설계에 직접 인용 금지 (VRP 경유)
- VRP 는 **Dashboard 설계**에 쓰이지만 운영 판정 근거로 인용 금지 (ORP 경유)
- 한 항목이 양쪽 모두 필요하면 **양쪽에 각각 기재** (참조 금지, 중복 허용)

---

## 11. 04-28 전환 절차 (5단계)

### Step 1: 수집 중단 선언 (04-28 00:00 UTC)

- TRCC 실행 중단 (이것이 자연히 RHL/IWL/DQL append 중단)
- 운영자에게 VRL append 중단 안내

### Step 2: Ledger Freeze

- 4 ledger 파일 모두 read-only 권한 변경
- 각 파일 말미에 freeze 마커 파일 `logs/preeval/.frozen_YYYYMMDD` 생성
- Freeze 이후 append 시도 감지 시 오류 (거버넌스 위반)

### Step 3: Integrity Snapshot

- 4 ledger 파일 각각 SHA256 해시 계산 → `logs/preeval/integrity_snapshot.json`
- 라인 수, 첫/마지막 ts 기록
- 무결성 스냅샷은 보존 (위변조 방지)

### Step 4: ORP / VRP 생성

- 운영자가 분석 스크립트 실행 (`scripts/plral_pack_builder.py`, post-P3 설계)
- 산출: `p3_post_operations_reference_pack.md` + `p3_post_visualization_reference_pack.md`
- 두 pack 은 독립적으로 작성, 교차 인용 금지

### Step 5: TRCC 폐기 (별도 절차)

- `scripts/health_check.py` git rm
- PLRAL 은 유지 (영구 보존)
- TRCC 폐기와 PLRAL freeze 를 별도 절차로 분리 (분리성 재강조)

---

## 12. 비간섭 보장 (PLRAL 관점)

### 12.1 PLRAL 자체가 운영에 주는 영향

| # | 체크 | 확인 방법 | 목표 값 |
|---|------|----------|--------|
| 1 | DB 쓰기 0건 | PLRAL 관련 모든 쿼리는 SELECT | 0 writes |
| 2 | DB 스키마 변경 0 | Alembic migration 없음 | 0 migrations |
| 3 | 기존 코드 수정 0 | git diff 에 `app/`, `workers/` 수정 없음 | 0 files |
| 4 | 상주 프로세스 0 | CLI 실행 후 잔여 프로세스 없음 | 0 processes |
| 5 | 네트워크 포트 바인딩 0 | `netstat -an` 변화 없음 | 0 new ports |
| 6 | Celery task 간섭 0 | task 성공률 수집 전/후 동일 | ±0% |

### 12.2 PLRAL 고장이 운영에 주는 영향

| 시나리오 | TRCC 동작 | 운영 시스템 영향 |
|---------|----------|---------------|
| PLRAL 파일 없음 | TRCC 정상 출력, 경고만 | 0 |
| PLRAL 파일 권한 없음 | TRCC 정상 출력, 경고만 | 0 |
| PLRAL 디스크 풀 | TRCC 정상 출력, 경고만 | 0 |
| PLRAL 스키마 오염 | TRCC 정상 출력, 다음 라인 append | 0 |

**결론**: PLRAL 실패는 TRCC 또는 운영 시스템을 중단시키지 않음. 단방향 커플링과 비-블로킹 append 설계.

---

## 13. 금지 조항 (PLRAL 전용, 8항)

| # | 금지 | 근거 |
|---|------|------|
| 1 | Ledger 라인 덮어쓰기/수정 | append-only 원칙 (DP-2) |
| 2 | Ledger 라인 삭제 | 무손실 원칙 |
| 3 | Ledger 간 데이터 상호 이관 | 분리 원칙 (DP-2) |
| 4 | PLRAL → 운영 시스템 write | DP-4 학습층 실행 권한 없음 |
| 5 | PLRAL → TRCC read-back | DP-1 단방향 커플링 |
| 6 | 04-28 이전 pack 생성 | 수집 중 분석 금지 (결과 편향) |
| 7 | cron/systemd 자동 append | Prohibited Zone B-3 재인용 |
| 8 | 외부 네트워크 업로드 | 로컬 보관 원칙 |

---

## 14. 에러 핸들링

### 14.1 ledger 파일 없음

- TRCC가 최초 실행 시 4 파일 자동 생성 (빈 파일)
- 첫 append 는 정상 이벤트로 시작 (별도 init 이벤트 없음)

### 14.2 디스크 풀

- append 실패 시 TRCC stderr 경고, 그러나 Card 출력 자체는 정상
- Exit code 0 유지 (가시성 > 학습)
- 다음 실행 시 복구되면 자동 재개

### 14.3 파일 corruption (수동 편집 등)

- 무결성 스크립트 (post-P3) 가 invalid JSON 라인 탐지
- 오염 라인 삭제 금지, 라인 번호만 `integrity_snapshot.json` 에 기록

### 14.4 시스템 시간 역순

- RHL/DQL 내 ts 가 직전 ts 보다 이른 경우 감지만 (거부 없음, 삭제 없음)
- post-P3 분석 시 주의

---

## 15. 봉인 선언

```
PLRAL_DESIGN_VERSION = v3
PLRAL_NAME = Passive Learning & Reference Accumulation Layer

LEDGER_COUNT = 4
  RHL = logs/preeval/rhl.jsonl  (Runtime Health)
  IWL = logs/preeval/iwl.jsonl  (Incident & Warning)
  DQL = logs/preeval/dql.jsonl  (Data Quality)
  VRL = logs/preeval/vrl.jsonl  (Visualization Reference)

PACK_COUNT = 2
  ORP = p3_post_operations_reference_pack.md  (post-P3)
  VRP = p3_post_visualization_reference_pack.md  (post-P3)

COUPLING = UNIDIRECTIONAL (TRCC → PLRAL write-only)
PLRAL_READS_TRCC = FALSE
PLRAL_WRITES_RUNTIME = FALSE

COLLECTION_START = 사용자 승인 후 TRCC 최초 실행 시점
COLLECTION_END = 2026-04-28 (P3 종료, ledger freeze)
RETENTION = 영구 (삭제 금지)

INTERFERENCE_CHECKS = 6 (DB쓰기/스키마/코드/상주/포트/task 모두 0)
P3_ACTIVE_NON_INTERFERENCE = TRUE (보전)
BASELINE_IMPACT = NONE (48915d2 무변화)

PRIMARY_OUTPUT_FOR_OPERATIONS = ORP
PRIMARY_OUTPUT_FOR_VISUALIZATION = VRP
PACK_CROSS_CITATION = FORBIDDEN

IMPLEMENTATION_STATUS = DESIGN_FROZEN, 파일 생성 사용자 승인 대기
```

---

## 16. 참조 문서

| 관계 | 문서 |
|------|------|
| 상위 헌법 | `k_v3_visualization_layer_governance.md` (VC-01~04) |
| 상위 스펙 | `k_v3_dashboard_safe_mode_framework.md` (v3 Stage 모델) |
| 분리 대응 | `k_v3_system_health_card_spec.md` (TRCC v3) |
| 재평가 계획 | `p3_post_eval_reevaluation_plan.md` |
| 통합점검 | `k_v3_integrated_inspection_report.md` |
| 구현 위치 (설계만) | `scripts/health_check.py` (TRCC), `scripts/plral_pack_builder.py` (post-P3) |
| 분석 스크립트 (설계만) | post-P3 jq/pandas 노트북 |

---

## 17. 원칙 요약 (한 문장)

> **PLRAL 은 TRCC 와 엄격히 분리된 학습·참조 누적 계층이다. 단방향(Card→PLRAL) 커플링, 4 ledger 분리(RHL/IWL/DQL/VRL) 수집, 2 pack 분리(ORP/VRP) 활용을 통해 검증기간(04-14~04-28) 동안 운영 현실을 누락 없이 기록하고, post-P3 에 운영 표준 개선과 Dashboard 전면 재설계의 독립 입력으로 쓴다. 학습은 실행 권한을 갖지 않고, 고장나도 운영을 중단시키지 않는다.**

---

*END OF DOCUMENT (v3)*
