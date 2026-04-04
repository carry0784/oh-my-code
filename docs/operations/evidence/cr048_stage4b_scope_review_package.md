# CR-048 Stage 4B: 범위 심사 패키지

**문서 ID:** STAGE4B-SCOPE-001
**작성일:** 2026-04-03
**전제 기준선:** v1.8 (5248/5248 PASS, Stage 4A SEALED)

---

## 1. 해석 및 요약

### 핵심 발견

Stage 4A 봉인 후, Stage 4B 후보인 `universe_manager.py`를 심사한 결과
**원래 제안(Option B)의 전제가 사실과 다릅니다.**

원래 Option B는 `universe_manager.py`에서 **DB/런타임 계층과 순수 선별 로직을 분리 추출**하는 것이었습니다.
그러나 실제 코드 분석 결과:

| 항목 | 원래 가정 | 실제 |
|------|----------|------|
| DB 의존성 | 있음 (SQLAlchemy) | **없음** |
| async | 있음 | **없음** |
| 외부 서비스 import | 있음 | **없음** (app.services.*, app.models.* import 0) |
| 네트워크/Redis | 있음 | **없음** |
| 파일 크기 | 혼합 책임 | **210줄, 순수 로직만** |

`universe_manager.py`는 **이미 100% pure**입니다.
추출 대상이 없는 파일에서 "순수 코어 추출"을 시도하면 **scope inflation**입니다.

### 조건 목록 불일치

Option B 문서의 7조건과 실제 구현 7조건이 다릅니다:

| Option B 문서 | 실제 구현 | 일치 |
|--------------|----------|:----:|
| status == CORE | status == "core" | O |
| qualification_passed | qualification_status == "pass" | O |
| TTL_valid | candidate_expire_at > now | O |
| broker_available | **(미구현)** | X |
| exposure_under_limit | **(미구현)** | X |
| no_forbidden_sector | **(미구현)** | X |
| regime_compatible | **(미구현)** | X |
| — | promotion_eligibility_status ∈ {eligible_for_paper, paper_pass} | 신규 |
| — | paper_evaluation_status == "pass" | 신규 |
| — | safe_mode_active == False | 신규 |
| — | drift_active == False | 신규 |

문서 작성 시점과 구현 시점의 차이로 인한 불일치입니다.
이 불일치 자체가 **"추출 범위"를 문서 기준으로 잡으면 안 된다**는 증거입니다.

---

## 2. 장점 / 단점

### Option A: Pure Zone 등록만 (권장)

| 장점 | 단점 |
|------|------|
| 운영 코드 변경 0줄 → 위험 0 | Stage 4B라는 이름에 비해 범위가 작음 |
| purity guard 9번째 파일로 퇴행 방지 | 새 아키텍처 가치가 낮음 |
| 기존 28개 테스트와 중복 없이 보완 | — |
| 롤백 비용: 테스트 삭제만 | — |

### Option B: 원래 계획 (파일 분할 추출)

| 장점 | 단점 |
|------|------|
| — | **추출 대상 없음** (이미 pure) |
| — | 새 파일 생성 = 불필요한 인디렉션 |
| — | 기존 consumer (multi_symbol_runner) 수정 필요 |
| — | 롤백 비용: 중간 (파일 삭제 + import 복원) |

### Option C: Pipeline 연결 (4A → universe)

| 장점 | 단점 |
|------|------|
| 향후 통합 경로 대비 | **런타임 경계 침범** |
| — | PipelineOutput → dict 매핑이 orchestration concern |
| — | pure zone에서 할 일이 아님 |
| — | 새 위험: multi_symbol_runner.py 접촉 |

---

## 3. 이유 / 근거

### Stage 4B가 정당한가?

**"순수 코어 추출"로서는 정당하지 않습니다.**
추출할 impure 코드가 없기 때문입니다.

**"순수 존 등록"으로서는 정당합니다.**
현재 universe_manager.py는 purity guard 밖에 있어서,
누군가 DB import나 async를 추가해도 자동으로 잡히지 않습니다.
Purity guard에 등록하면 이 퇴행을 영구 차단합니다.

### 정직한 분류

| 분류 | 해당 여부 |
|------|:---------:|
| Pure extraction (순수 추출) | **X** — 이미 pure |
| Responsibility movement (책임 이동) | **X** — 이동할 책임 없음 |
| Pure zone enrollment (순수 존 등록) | **O** — 유일하게 정당한 작업 |
| Pipeline connection (파이프라인 연결) | **X** — 런타임 concern, 별도 stage |

---

## 4. 실현 · 구현 대책

### 권장안: Stage 4B → Pure Zone 등록 (축소 범위)

| 작업 | 파일 | 변경 |
|------|------|------|
| `_PURE_ZONE_FILES`에 추가 | `tests/test_purity_guard.py` | +1줄 |
| `TestUniverseManagerPurity` 클래스 | `tests/test_purity_guard.py` | +~70줄 (12 tests) |
| 기존 테스트 감사 | `tests/test_universe_runner.py` | 0줄 (읽기만) |
| 기준선 v1.9 갱신 | 거버넌스 문서 | docs만 |
| **universe_manager.py** | **수정 0줄** | **0줄** |

### Stage 4A 대비 Stage 4B 추가 위험

| 위험 항목 | Stage 4A | Stage 4B (등록만) |
|----------|:--------:|:-----------------:|
| 신규 서비스 파일 | 1 (pipeline.py) | **0** |
| 기존 서비스 수정 | 0 | **0** |
| FROZEN 접촉 | 0 | **0** |
| RED 접촉 | 0 | **0** |
| 새 import 경로 | 4 sealed assets | **0** |
| 롤백 비용 | LOW (파일 삭제) | **TRIVIAL** (테스트 삭제) |
| 운영 코드 위험 | 없음 | **없음** |

### 재사용 가능 sealed 자산 목록

| 자산 | 재사용 방식 | Stage 4B 변경 |
|------|------------|:------------:|
| universe_manager.py | purity guard 대상 | **0줄** |
| test_universe_runner.py | 기존 테스트 감사 참조 | **0줄** |
| test_purity_guard.py | 확장 (9th file) | **+~71줄** |
| 기존 8 pure zone files | 무접촉 | **0줄** |
| screening_qualification_pipeline.py | 무접촉 | **0줄** |

### 수정 필요 파일 목록

| 파일 | 수정 내용 | 위험도 |
|------|----------|:------:|
| `tests/test_purity_guard.py` | 9th Pure Zone 추가 | ZERO |
| 거버넌스 문서 3종 | baseline v1.9, exception register, expansion proposal | ZERO |

### 허용/금지 접촉 매트릭스

| 파일 | 허용 | 금지 |
|------|:----:|:----:|
| `tests/test_purity_guard.py` | **수정** (테스트 추가) | — |
| `app/services/universe_manager.py` | **읽기** (purity 검증 대상) | **수정 금지** |
| `tests/test_universe_runner.py` | **읽기** (감사 참조) | **수정 금지** |
| `app/services/multi_symbol_runner.py` | — | **접촉 금지** |
| `app/services/strategy_router.py` | — | **접촉 금지** |
| `app/services/regime_detector.py` | — | **접촉 금지 (RED)** |
| `app/services/asset_service.py` | — | **접촉 금지 (RED)** |
| `app/services/runtime_strategy_loader.py` | — | **접촉 금지 (RED)** |
| `app/services/feature_cache.py` | — | **접촉 금지 (RED)** |
| `workers/*` | — | **접촉 금지 (RED)** |

### FROZEN 유지 대상

기존 8개 Pure Zone 파일 전부:
1. sector_rotator.py
2. data_provider.py
3. symbol_screener.py
4. backtest_qualification.py
5. asset_validators.py
6. constitution.py
7. screening_transform.py
8. screening_qualification_pipeline.py

### RED 유지 대상

1. regime_detector.py (CR-046)
2. asset_service.py (runtime path)
3. runtime_strategy_loader.py (runtime)
4. feature_cache.py (Phase 5)
5. strategy_router.py (Phase 5)
6. multi_symbol_runner.py (Phase 6)
7. workers/* (Celery/beat)
8. exchanges/* (broker adapters)

---

## 5. 실행방법

### 4B-1 / 4B-2 분할 필요 여부

**불필요합니다.**

범위가 테스트 파일 1개 수정 + 거버넌스 문서 갱신뿐이므로,
분할하면 오히려 거버넌스 오버헤드가 작업량을 초과합니다.

단일 Stage 4B로 **설계 + 구현을 동시 진행**해도 무방합니다.
(운영 코드 변경 0줄이므로 설계/구현 분리의 실익이 없음)

### 완료 기준 10항

| # | 기준 |
|---|------|
| 1 | `universe_manager.py` 수정 0줄 |
| 2 | purity guard 9th file 등록 완료 |
| 3 | `TestUniverseManagerPurity` 12 tests PASS |
| 4 | 기존 `test_universe_runner.py` 회귀 PASS |
| 5 | FROZEN 8 files 무접촉 (0줄 diff) |
| 6 | RED files 무접촉 (0줄 diff) |
| 7 | 기존 7-condition contract 감사 완료 (기존 28+ tests 확인) |
| 8 | 기준선 v1.9 갱신 (9 pure zone files, ~105 purity tests) |
| 9 | 전체 회귀 PASS |
| 10 | 신규 경고/예외 0건 |

### 테스트 증가 예상치

| 항목 | 예상 |
|------|:----:|
| TestUniverseManagerPurity | +12 |
| 운영 코드 테스트 | +0 (기존 28+ 충분) |
| **총 증가** | **+12** |
| **새 기준선** | **~5260** |

### fail-closed 위험 분석

**위험 없음.** 운영 코드 수정이 0줄이므로 fail-closed chain에 영향을 주는 변경이 없습니다.
기존 universe selection의 7-condition 체인은 그대로 유지됩니다.

### 롤백 비용

**TRIVIAL.** test_purity_guard.py에서 추가된 클래스와 `_PURE_ZONE_FILES` 항목을 삭제하면 완전 롤백됩니다.
운영 코드 롤백: 해당 없음 (변경 0줄).

---

## 6. 더 좋은 아이디어

1. **Stage 4B를 "Stage 4A+" 또는 "Stage 4A addendum"으로 명명**하는 게 더 정직합니다.
   독립 stage로 부르기에는 범위가 작고, 4A와 같은 패턴(purity guard 확장)의 연속입니다.

2. **향후 진짜 의미 있는 Stage 4B가 있다면**, 그것은
   "PipelineOutput → UniverseManager 입력 매핑"일 수 있습니다.
   하지만 이것은 **런타임 통합 단계**이지 pure extraction이 아니므로,
   별도 CR 또는 Phase 5/6 범위에서 다루는 게 맞습니다.

3. **"logging" import 관련 판단이 필요합니다.**
   universe_manager.py는 `import logging`을 사용합니다.
   현재 purity guard의 `_FORBIDDEN_MODULES`에 logging은 포함되어 있지 않으므로
   purity 검증에 통과하지만, 엄격한 "순수 함수" 기준에서는 로깅이 side effect입니다.
   이 부분은 기존 관례(logging 허용)를 따를지, 별도 판단할지 결정이 필요합니다.

4. **OBS-001 carried flaky ledger**를 이번에 정식으로 만들면,
   이후 기준선 판정에서 매번 설명하지 않아도 됩니다.

---

## A 판정 요청

| 판정 대상 | 선택지 |
|----------|--------|
| Stage 4B 범위 | (A) Pure Zone 등록만 — 권장 |
| | (B) 원래 계획 (파일 분할) — 비권장, 추출 대상 없음 |
| | (C) Pipeline 연결 — 비권장, 런타임 concern |
| 명명 | "Stage 4B" 유지 또는 "Stage 4A+" 축소 |
| 설계/구현 분리 | 동시 진행 허용 여부 |
| logging 판단 | 기존 관례(허용) 유지 또는 별도 규칙 |

---

```
Stage 4B Scope Review v1.0
Recommended: Pure Zone enrollment only
Expected: +12 tests, 0 production code changes
Risk: ZERO (test-only modification)
Rollback: TRIVIAL
```
