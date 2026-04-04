# BL-OPS-RESTART01 — Clean Restart Hygiene

**제정일**: 2026-04-03
**근거**: Ops Incident — Stale Beat State + Queue Residue (23 messages)
**승인자**: A

---

## 1. 목적

Worker/Beat 재기동 시 stale state와 queue residue로 인한 관찰 오염을 방지한다.
이전 기준선의 잔존 메시지가 새 기준선 관찰을 오염시키는 것을 원천 차단한다.

## 1.1 근본 원인: PersistentScheduler shelve merge

Celery beat의 기본 스케줄러는 `PersistentScheduler`이며, `shelve` (SQLite 기반)에 schedule 항목을 영속화한다.

**문제 메커니즘**:
1. beat가 실행되면 shelve 파일(`celerybeat-schedule`)에 현재 schedule 항목을 저장
2. 코드에서 `beat_schedule`의 항목을 제거(주석 처리)해도, 기존 shelve 파일에 해당 항목이 남아 있음
3. beat 재시작 시 `merge_inplace()`가 symmetric difference로 stale 항목을 제거하지만, 일부 edge case(shelve 손상, 타이밍)에서 누수 가능
4. **결과**: 코드에서 비활성화한 `check_pending_orders`와 `sync_all_positions`가 shelve에서 복원되어 계속 dispatch됨

**방어 계층**:
- **Layer 1 (수동)**: 재기동 전 `celerybeat-schedule*` 삭제 (이 문서의 절차)
- **Layer 2 (자동)**: `beat_init` signal에서 effective schedule과 code schedule의 불일치를 감지하고 stale 항목 자동 제거 (`workers/celery_app.py`)
- **Layer 3 (감시)**: startup fingerprint에서 active/disabled task 수 로그 출력

## 2. 재기동 전 필수 절차

### 2.1 Beat 종료 확인

```bash
# Beat 프로세스 확인
tasklist /FI "IMAGENAME eq celery.exe"  # Windows
ps aux | grep "celery beat"              # Linux

# Beat 종료
# (Ctrl+C 또는 kill)
```

### 2.2 Stale Beat State 삭제

```bash
# beat scheduler state 파일 확인 및 삭제
dir celerybeat-schedule* 2>nul
del celerybeat-schedule*
# 또는
rm -f celerybeat-schedule*
```

**왜 필요한가**: `celerybeat-schedule` 파일은 이전 schedule의 next-run 시각을 저장한다.
기준선이 변경된 후에도 이 파일이 남아 있으면, 이미 비활성화된 task가 "예정 시각"에 다시 발송된다.

### 2.3 Queue Residue 점검 및 정리

```bash
# 잔존 메시지 확인 + 정리
python -m celery -A workers.celery_app purge -f

# 결과 해석:
# "Purged N messages from 1 known task queue." → N개 잔존 메시지 제거됨
# "No messages purged from 1 queue." → 큐 깨끗함
```

**왜 필요한가**: 비활성화된 task가 이미 enqueue된 상태로 남아 있으면,
schedule에서 제거해도 worker가 나중에 소비한다.

### 2.4 Repo 루트 확인

```bash
# 반드시 프로젝트 루트에서 실행
cd C:\Users\Admin\K-V3  # (또는 해당 경로)
```

## 3. 재기동 절차

### 3.1 Worker 시작

```bash
python -m celery -A workers.celery_app worker --loglevel=info --pool=solo --concurrency=1
```

### 3.2 Beat 시작

```bash
python -m celery -A workers.celery_app beat --loglevel=info
```

### 3.3 Startup Fingerprint 확인

Worker/Beat 시작 시 아래 로그가 자동 출력된다:

```
celery_worker_startup_fingerprint:
  exchange_mode=DATA_ONLY
  contract=BL-EXMODE01
  active_beat_tasks=12
  disabled_beat_tasks=3
  active_keys=[...]
```

이 fingerprint가 보이지 않으면 기동에 문제가 있는 것이다.

## 4. 재기동 후 첫 관찰 항목

### 4.1 5분 내 확인 (첫 beat cycle)

| 확인 항목 | 기대값 | 이상 시 |
|-----------|--------|---------|
| `check_pending_orders` 미발생 | 로그에 없음 | stale state 잔존 |
| `sync_all_positions` 미발생 | 로그에 없음 | stale state 잔존 |
| `collect_market_state` 성공 | succeeded | runtime path 확인 필요 |
| `expire_signals` 성공 | succeeded | DB 연결 확인 |
| `strategy-cycle-*` 성공 | succeeded (dry_run) | 정상 |

### 4.2 10분 내 확인

| 확인 항목 | 기대값 |
|-----------|--------|
| `no running event loop` 에러 없음 | 0건 |
| `OperationNotPermitted` 에러 없음 | 0건 (DATA_ONLY 정상이면) |
| 모든 active task 1회 이상 실행 | 로그 확인 |

## 5. 금지 사항

| 금지 | 이유 |
|------|------|
| **오염 로그 상태에서 코드 회귀 판정** | stale state 가능성 우선 배제 필요 |
| **repo 루트 외부에서 worker/beat 실행** | import path 불일치 |
| **purge 없이 기준선 변경 후 restart** | queue residue 위험 |
| **stale beat state 파일 유지한 채 restart** | 비활성화 task 재발송 위험 |

## 6. 체크리스트 (복사용)

```
[ ] Beat 프로세스 종료 확인
[ ] celerybeat-schedule* 삭제
[ ] queue purge 실행 (결과 기록)
[ ] repo 루트에서 실행 확인
[ ] Worker 시작
[ ] Beat 시작
[ ] Startup fingerprint 로그 확인
[ ] 5분 후 첫 관찰: disabled task 미발생 확인
[ ] 5분 후 첫 관찰: active task 성공 확인
[ ] 10분 후: 에러 로그 0건 확인
```

---

**BL-OPS-RESTART01 제정 완료. Stale Beat State + Queue Residue incident 근거.**
