# CR-030 — Orphan Aggregation Long-Term Design Review

Effective: 2026-05-14
Status: **SEALED** (설계 검토 전용, 코드 변경 금지)
Author: B (Implementer)
Reviewer: A (Designer)
Scope: orphan count materialization / PRE-POST link 저장 구조 사전 설계 검토

---

## (1) 해석 및 요약

### 핵심 결론

**A안(현행 유지 + 모니터링)이 현재 최선이다.**

orphan count materialization(B안)과 PRE/POST link 별도 저장(C안)은
둘 다 현 시점에서 구현 이득이 비용을 초과하지 않는다.

근거:
- Mode 1(observation-only)에서 phase-tagged evidence는 **0건**
- orphan count 계산 대상은 전체 evidence가 아니라 **artifacts가 있는 행만**
- 현재 512K evidence 중 phase artifacts 보유 행은 agent 실행 사이클분뿐
- agent 실행이 없는 Mode 1에서는 `count_orphan_pre() = 0`이 즉시 반환
- non-hot-path이므로 운영 영향 없음

---

## (2) 현행 구조 분석

### orphan count 계산 위치

| 호출자 | 파일 | 경로 성격 |
|--------|------|-----------|
| `_collect_governance_info()` | `governance_summary_service.py:141` | non-hot-path (governance summary) |
| `_collect_evidence_summary()` | `ai_assist_source.py:166` | non-hot-path (AI assist 수집) |

### 호출 체인

```
/api/ops-aggregate
  → build_ops_aggregate()
    → _check_evidence_summary()
      → collect_ai_assist_sources()
        → _collect_evidence_summary()
          → store.count_orphan_pre()     ← HERE

/api/v2/dashboard (governance panel)
  → build_governance_summary()
    → _collect_governance_info()
      → store.count_orphan_pre()         ← HERE
```

### 현재 비용 성격

| 항목 | 값 |
|------|-----|
| 경로 성격 | **non-hot-path** |
| CR-029 budget | 10K InMemory < 1.0s (PASS) |
| SQLite 구현 | `WHERE artifacts IS NOT NULL AND artifacts != '[]'` 필터 후 JSON 파싱 |
| Memory 구현 | dict 전체 순회 + phase 매핑 |
| 시간복잡도 | O(artifact-bearing rows) — 전체 evidence가 아님 |

### Phase-tagged evidence 생성원

| 생성원 | 파일 | Phase | 발생 조건 |
|--------|------|-------|-----------|
| GovernanceGate | `governance_gate.py:377` | PRE | agent 실행 사이클 시작 |
| GovernanceGate | `governance_gate.py:446` | POST | agent 실행 사이클 성공 |
| GovernanceGate | `governance_gate.py:508` | ERROR | agent 실행 사이클 실패 |

**다른 12개 evidence writer는 phase 태그를 생성하지 않는다.**

### Mode 1 운영 현실

| 항목 | 상태 |
|------|------|
| Agent 실행 | **비활성** (observation-only) |
| Phase-tagged evidence 생성 | **0건/일** |
| count_orphan_pre() 실제 연산량 | **사실상 0** (artifact 있는 행이 없거나 극소) |
| 현재 orphan count | **0** (PRE 번들 자체가 없음) |

---

## (3) 대안 비교

### 3안 비교표

| 기준 | A안: 현행 유지 | B안: Counter Materialization | C안: Link Table |
|------|-------------|------|------|
| **append-only 적합성** | ✅ 완전 적합 | ⚠️ counter 갱신은 update 성격 | ⚠️ link 생성은 write 추가 |
| **read/write 경계 영향** | ✅ 없음 | ⚠️ store() 호출마다 counter 갱신 | ⚠️ POST/ERROR 기록 시 link 생성 |
| **정합성 리스크** | ✅ 없음 | ❌ counter drift 가능 (partial write/crash) | ❌ link 누락 시 false orphan |
| **backfill 필요** | ✅ 없음 | ❌ 기존 데이터 전수 스캔 후 counter 초기화 | ❌ 기존 evidence 전수 스캔 후 link 생성 |
| **SQLite/Memory parity** | ✅ 이미 구현 완료 | ⚠️ 양쪽 counter 동기화 필요 | ⚠️ 양쪽 link storage 필요 |
| **회귀 테스트 난이도** | ✅ 없음 | ⚠️ counter 정합성 테스트 추가 | ⚠️ link 정합성 + orphan 일치 테스트 |
| **rollback 용이성** | ✅ rollback 불필요 | ❌ counter 제거 + 기존 로직 복원 | ❌ link table 제거 + 기존 로직 복원 |
| **운영 이득** | ▬ 현재 이득 없음 (0건) | ▬ Mode 1에서 이득 0 | ▬ Mode 1에서 이득 0 |
| **장기 유지보수성** | ✅ 단순 | ⚠️ counter 정합성 유지 부담 | ⚠️ dual source of truth 관리 부담 |
| **구현 비용** | 0 | 중간 (counter + backfill + parity) | 높음 (table + backfill + parity + migration) |

### 점수 요약

| 안 | 장점 | 단점 | 순이득 |
|----|------|------|--------|
| A안 | 비용 0, 리스크 0, 현재 충분 | 장기 대규모 시 재검토 필요 | **+** |
| B안 | orphan O(1) 조회 가능 | counter drift, backfill, append-only 위반 우려 | **-** |
| C안 | 관계형 쿼리 가능 | 가장 높은 비용, dual SSOT, migration | **--** |

---

## (4) 대안별 실패 모드

### A안: 현행 유지

| 실패 모드 | 발생 조건 | 심각도 | 확률 |
|-----------|-----------|--------|------|
| orphan 계산 느려짐 | phase-tagged evidence > 100K | LOW | **극히 낮음** — Mode 1에서 0건/일, Mode 2 활성화 후에도 agent 실행 빈도 제한적 |
| 전수 스캔 부하 | artifacts 비어있지 않은 행이 대량 증가 | LOW | 낮음 — 현재 대부분 artifacts=[] |

### B안: Counter Materialization

| 실패 모드 | 발생 조건 | 심각도 |
|-----------|-----------|--------|
| **Stale counter** | 프로세스 crash 후 counter 불일치 | MEDIUM — orphan_detected false negative |
| **Partial update** | store() 성공 + counter 갱신 실패 | MEDIUM — 자동 복구 불가 |
| **Backfill 불일치** | 기존 데이터 마이그레이션 시 phase 파싱 오류 | LOW — 1회성이지만 검증 필요 |
| **Append-only 위반** | counter는 본질적으로 UPDATE 성격 | HIGH — 헌법 원칙 충돌 |

### C안: Link Table

| 실패 모드 | 발생 조건 | 심각도 |
|-----------|-----------|--------|
| **Link 누락** | POST evidence 기록 시 link 생성 실패 | HIGH — false orphan, governance 오판 |
| **Dual source of truth** | artifacts.phase vs link table 불일치 | HIGH — 어느 쪽이 진실인지 모호 |
| **Migration 실패** | link table 생성/backfill 중 장애 | MEDIUM — 반자동 복구 필요 |
| **Recovery 오염** | rollback 시 link table만 남고 evidence는 복원 | MEDIUM — ghost links |

---

## (5) Evidence 증가 시나리오 분석

### 현재 증가율

| 항목 | 값 |
|------|-----|
| 현재 총 evidence | ~512K |
| Phase-tagged evidence | **0건** (추정, Mode 1) |
| 일일 evidence 증가 | daily_check + hourly_check + preflight + gate 등 |
| Phase evidence 증가 | **0건/일** (agent 비활성) |

### Mode 2 전환 시 (가정)

| 항목 | 추정 |
|------|------|
| Agent 실행 빈도 | 1~10회/일 (보수적) |
| PRE+POST per execution | 2건 |
| 일일 phase evidence | 2~20건 |
| 1년 누적 | 730~7,300건 |
| count_orphan_pre() 대상 | 730~7,300건 (전체 evidence 대비 극소) |

### 위험 임계점 분석

`count_orphan_pre()`가 문제가 되려면:

| 조건 | 필요 규모 | 도달 시간 (Mode 2 기준) |
|------|-----------|------------------------|
| SQLite JSON 파싱 > 0.5s | artifacts 있는 행 ~50K+ | **7~70년** |
| Memory dict 순회 > 0.5s | phase 있는 번들 ~100K+ | **14~140년** |

**결론: 현실적 운영 수명 내에서 orphan 계산 비용이 문제가 될 가능성은 사실상 0이다.**

---

## (6) 이유 / 근거

### 핵심 논거 3개

**1. 문제가 존재하지 않는다.**

orphan count는 phase-tagged evidence만 스캔한다.
Mode 1에서 phase-tagged evidence는 0건이다.
Mode 2에서도 연간 수천 건 수준이다.
현재 문제가 없고, 예측 가능한 미래에도 문제가 되지 않는다.

**2. B안/C안은 해결할 문제 없이 복잡성만 추가한다.**

Counter materialization은 append-only 원칙과 충돌한다.
Link table은 dual source of truth를 생성한다.
둘 다 backfill이 필요하고, 정합성 검증 부담이 커진다.
이득(orphan O(1) 조회)은 현재 cost(사실상 0)를 고려하면 무의미하다.

**3. "지금 안 하면 나중에 후회"가 아니다.**

나중에 정말 필요해지면 그때 해도 된다.
현재 facade(`count_orphan_pre()`)가 이미 추상화되어 있으므로
내부 구현을 바꾸는 데 외부 영향이 없다.
CR-028이 만든 추상화 경계가 바로 이 유연성을 보장한다.

---

## (7) 반대 논리 검증

### "지금 안 하면 기술 부채가 쌓인다"에 대해

아니다. 현재 구현은:
- facade로 추상화 완료 (CR-028)
- 성능 가드로 보호 (CR-029)
- non-hot-path에 위치
- phase evidence 0건 상태

기술 부채가 아니라 **적정 구현**이다.

### "나중에 Mode 2 전환하면 급하게 고쳐야 한다"에 대해

아니다. Mode 2에서 연간 7,300건이 추가되어도:
- `count_orphan_pre()` < 0.01s
- 10년 후에도 < 0.1s (추정)
- 그때 가서 materialization이 필요하면 facade 내부만 교체하면 된다

### "설계를 미리 해두면 나중에 빠르다"에 대해

맞지만, 설계 비용도 0은 아니다.
지금 설계해 봐야 Mode 2 운영 패턴을 모르는 상태에서의 추정이다.
실제 데이터 없이 하는 설계는 정확도가 낮다.
Mode 2 전환 후 실측 데이터로 설계하는 것이 더 정확하다.

---

## (8) 실현/구현 대책

### 권고: A안 (현행 유지 + 모니터링)

| 항목 | 행동 |
|------|------|
| 코드 변경 | **없음** |
| 모니터링 | ops-aggregate 응답시간 관찰 (기존 dashboard로 충분) |
| 재검토 시점 | Mode 2 전환 후 3개월, 또는 phase evidence > 10K 도달 시 |
| 재검토 방법 | `count_orphan_pre()` 실측 + budget 대조 |

### B안/C안 이행 조건 (미래 트리거)

아래 조건 **모두** 충족 시에만 재검토:

1. Mode 2 활성화 완료
2. Phase-tagged evidence > 10,000건
3. `count_orphan_pre()` > 0.5s 실측
4. non-hot-path에서 hot-path로 경로 변경 요구 발생

현재 4개 조건 중 **0개 충족**이다.

---

## (9) 더 좋은 아이디어

### 유일하게 의미 있는 다음 행동

구현도 설계도 아닌, **관측 기준 고정**이다.

구체적으로:
- CR-029의 `test_count_orphan_pre_budget_10k` (< 1.0s)가 이미 가드 역할
- Mode 2 전환 시 phase evidence 건수를 dashboard에 노출하는 것만으로 충분
- 그 시점에 다시 이 문서를 열어 재검토하면 된다

### 절대 하지 말아야 할 것

- "미래를 대비한" 선행 materialization 구현
- "언젠가 필요하니까" 식의 link table 추가
- 문제 없는 곳에 복잡성을 주입하는 premature optimization

---

## (10) 헌법 조항 대조

| 규칙 | 준수 | 비고 |
|------|------|------|
| Append-only evidence | ✅ | A안은 변경 없음. B안/C안은 원칙 충돌 가능 |
| Read-only 원칙 | ✅ | 설계 검토만, 코드 변경 없음 |
| Fail-closed | ✅ | 기존 fail-closed 유지 |
| 운영 의미 변경 | ✅ | 없음 |

---

## A 판단용 1문장 결론

**장기 후보 2개(materialization, link table)는 둘 다 현 시점에서 구현할 필요가 없으며, Mode 2 전환 후 실측 데이터가 나올 때까지 현행 유지가 최선이다.**
