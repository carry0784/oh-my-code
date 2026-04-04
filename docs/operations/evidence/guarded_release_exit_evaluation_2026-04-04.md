# Guarded Release 종료 조건 평가서

**문서 ID:** GR-EXIT-EVAL-001
**작성일:** 2026-04-04
**작성자:** System
**판정 권한:** A
**문서 성격:** Guarded Release 종료 조건 평가 + L3 개방 권고
**변경 등급:** L0 (문서)

---

## 1. 현재 기준선 요약

### 거버넌스 상태

| 항목 | 값 |
|------|-----|
| operational_mode | `GUARDED_RELEASE` |
| Gate | **LOCKED** |
| allowed_scope | `L0, L1, L2` |
| blocked_scope | `L3, L4` |
| rules | BL-EXMODE01, BL-OPS-RESTART01, GR-RULE-01~03 |
| prohibitions | 7건 유지 |
| sealed_crs | 5건 (CR-038, CR-048, CR-048A, CR-048B, CR-049 Phase 1+2) |
| open_issues | **0건** |
| resolved_issues | 2건 (TEST-ORDERDEP-001, EX-001) |

### 테스트 기준선

| 항목 | 값 |
|------|-----|
| 전체 테스트 | **4549 PASS** |
| 테스트 파일 | 174개 |
| 신규 실패 | **0건** |
| drift | **0건** |
| Gate 위반 | **0건** |
| 금지 범위 침범 | **0건** |

### 기준선 6항목 drift 체크

| 항목 | 기대값 | 현재값 | 일치 |
|------|--------|--------|:----:|
| operational_mode | GUARDED_RELEASE | GUARDED_RELEASE | ✅ |
| exchange_mode | DATA_ONLY | DATA_ONLY | ✅ |
| blocked_api_count | 5 | 5 | ✅ |
| disabled_beat_tasks | 3 | 3 | ✅ |
| forbidden_beat_tasks_absent | absent | absent | ✅ |
| startup_log_consistency | consistent | consistent | ✅ |

**6/6 일치. drift 0.**

---

## 2. L2 범위 작업 완료 목록

### Phase 0 — Constitution 문서 (L0, ACCEPTED)

| 문서 | 버전 | 승인 |
|------|------|:----:|
| `injection_constitution.md` | v2.0 | ✅ |
| `broker_matrix.md` | v2.0 | ✅ |
| `exclusion_baseline.md` | v2.0 | ✅ |

### Phase 1 — Registry 설계 카드 (L0, ACCEPTED)

| 문서 | 버전 | 승인 |
|------|------|:----:|
| `design_indicator_registry.md` | v1.0 | ✅ |
| `design_feature_pack.md` | v1.0 | ✅ |
| `design_strategy_registry.md` | v1.0 | ✅ |
| `design_promotion_state.md` | v1.0 | ✅ |

### 문서-테스트 추적표 (L0, ACCEPTED)

| 문서 | 버전 | 승인 |
|------|------|:----:|
| `design_test_traceability.md` | v1.0 | ✅ |

### 계약 테스트 (L1, ACCEPTED)

| 파일 | 테스트 수 | 결과 |
|------|:---------:|:----:|
| `test_cr048_design_contracts.py` | 57 | ✅ PASS |

### Observatory API (L2, ACCEPTED)

| 파일 | 엔드포인트 | 테스트 수 | 결과 |
|------|:---------:|:---------:|:----:|
| `cr048_observatory.py` | 5 GET | — | ✅ |
| `test_cr048_observatory.py` | — | 48 | ✅ PASS |

### L2 작업 완료 합계

| 구분 | 수량 |
|------|:----:|
| 설계 문서 | 8 |
| 코드 파일 | 1 (`cr048_observatory.py`) |
| 라우터 등록 | 1줄 (`__init__.py`) |
| 테스트 파일 | 2 |
| 신규 테스트 | 105 (57 + 48) |
| write endpoint | **0** |
| DB 모델 | **0** |
| 서비스 로직 | **0** |

---

## 3. 잔존 금지 범위

### L3/L4 차단 유지 항목

| 항목 | 등급 | 상태 |
|------|------|------|
| Registry DB 모델 생성 | L3 | **차단** |
| Injection Gateway 실행 로직 | L3 | **차단** |
| PromotionState 상태 전이 실행 | L3 | **차단** |
| RuntimeStrategyLoader 구현 | L3 | **차단** |
| Feature Cache 구현 | L3 | **차단** |
| KIS_US 어댑터 신규 생성 | L3 | **차단** |
| exchange_mode 변경 (DATA_ONLY → PAPER/LIVE) | L4 | **차단** |
| blocked API 해제 | L4 | **차단** |
| disabled beat task 재활성화 | L4 | **차단** |
| 금지 task 등록 | L4 | **차단** |
| 실주문 경로 활성화 | L4 | **차단** |

### 금지 사항 7건 유지

1. CR-049 Phase 3 구현 금지
2. SEALED PASS 범위 재개방 금지
3. DATA_ONLY 계약 훼손 금지
4. ETH 운영 경로 금지 (CR-046)
5. L3 변경 A 승인 없이 금지
6. L4 변경 별도 CR 없이 금지
7. Gate 무단 개방 금지

### write path 금지

| 확인 항목 | 상태 |
|-----------|------|
| cr048_observatory.py에 POST/PUT/PATCH/DELETE | **없음** (405 테스트 확인) |
| ops_state.json 쓰기 경로 | **없음** (A 전용 편집) |
| DB INSERT/UPDATE/DELETE | **없음** |
| exchange API 호출 | **없음** |

### runtime registry 부재 명시

현재 Observatory API가 반환하는 데이터는 **설계 문서 기반 정적 카탈로그**이며:
- 실제 DB에서 조회하는 것이 아님
- 등록/수정/삭제 기능 없음
- `source_of_truth: "design_document"` 태그로 명시
- 런타임 상태를 반영하지 않음 (ops_state.json governance_state만 예외)

---

## 4. L3 개방 필요성

### 왜 필요한가

| 이유 | 설명 |
|------|------|
| **설계-구현 간극** | 8개 설계 문서 + 105개 계약 테스트가 완성되었으나, 실제 Registry 모델이 없으면 코드 기반 검증 불가 |
| **CR-048 Phase 1 진행** | Phase 1(Registry 모델)은 L3 등급 — 현재 Gate LOCKED 상태에서는 착수 불가 |
| **Observatory 한계** | 현재 API는 설계 카탈로그만 반환 — 실제 등록/조회 기능은 DB 모델 필요 |
| **계약 테스트 연결** | 57개 계약 테스트가 설계 상수만 검증 — 실제 모델과 연결되어야 완전한 검증 |

### 지금 열지 않아도 되는가

**예, 열지 않아도 됩니다.** 현재 상태로도:
- 설계 기준선은 고정되어 있음
- 계약 테스트는 독립 실행 가능
- Observatory API는 정상 작동
- 4549 테스트 기준선은 안정적

**L3를 열지 않아도 시스템은 안정 상태를 유지합니다.**
다만, CR-048 Phase 1~9 구현을 시작하려면 언젠가는 L3 개방이 필요합니다.

### 열 경우 범위를 어디까지 제한할지

#### CR-048 L3 최소 범위안 (LIMITED L3)

| 허용 | 조건 | 등급 |
|------|------|------|
| IndicatorRegistry SQLAlchemy 모델 골격 | 테이블/칼럼 정의만, 서비스 없음 | L3 (최소) |
| FeaturePackRegistry 모델 골격 | 테이블/칼럼 정의만, 서비스 없음 | L3 (최소) |
| StrategyRegistry 모델 골격 | 테이블/칼럼 정의만, 서비스 없음 | L3 (최소) |
| PromotionState/PromotionHistory 모델 골격 | 테이블/칼럼 + enum 정의만 | L3 (최소) |
| Alembic 마이그레이션 | 004_control_plane_tables | L3 |
| 모델 단위 테스트 | CRUD mock 테스트 | L1 |

| 금지 유지 | 사유 |
|-----------|------|
| Injection Gateway 실행 로직 | write path 발생 |
| Promotion 상태 전이 실행 | 실행 판단 로직 |
| RuntimeStrategyLoader | Data Plane 영향 |
| Feature Cache | 런타임 영향 |
| KIS_US 어댑터 | 외부 의존성 |
| Strategy 등록/수정/삭제 API | write endpoint |
| beat schedule 변경 | L4 |
| exchange_mode 변경 | L4 |

**요약: "모델 골격 + 마이그레이션 + 테스트"만 허용. 서비스/실행/쓰기 로직은 차단 유지.**

---

## 5. 리스크 평가

### 리스크 1 — 설계/관측과 구현 사이의 간극

| 항목 | 현재 | L3 최소 개방 후 |
|------|------|----------------|
| 설계 문서 | 8건 고정 | 변경 없음 |
| 계약 테스트 | 105건 PASS | 모델 테스트 추가 |
| Observatory API | 설계 카탈로그 | 향후 실제 DB 조회로 전환 가능 |
| DB 모델 | **없음** | **골격 생성** |
| 서비스 로직 | **없음** | **없음 유지** |

**간극:** 설계 문서 → 모델 전환 시 스키마 불일치 가능. 계약 테스트가 이를 감지.

### 리스크 2 — Observatory 오해 가능성

| 오해 | 실제 | 대응 |
|------|------|------|
| "API가 실시간 registry를 반환한다" | 설계 카탈로그 반환 | `source_of_truth: "design_document"` 태그 |
| "전략이 이미 등록되었다" | DESIGN 상태 | `status: "DESIGN"` 태그 |
| "Promotion이 작동한다" | 정의만 있음 | 실행 로직 없음 명시 |

### 리스크 3 — L3 개방 시 범위 이탈

| 이탈 시나리오 | 발생 확률 | 대응 |
|-------------|----------|------|
| 모델 골격 → 서비스 로직 추가 | 중간 | GR-RULE-02 (A 승인 필수) |
| 마이그레이션 → 실 데이터 투입 | 낮음 | DATA_ONLY 모드 유지 |
| 모델 정의 → write API 추가 | 중간 | 금지 목록 명시 + 405 테스트 |

### 리스크 4 — 통제 수단

| 통제 | 상태 |
|------|------|
| Gate LOCKED | 유지 |
| GR-RULE-01 (연쇄 수정 등급 분석) | 적용 중 |
| GR-RULE-02 (L2+ 변경 시 A 승인) | 적용 중 |
| GR-RULE-03 (분류표 기준 판단) | 적용 중 |
| 재진입 조건 4개 | 활성 (drift/regression/forbidden/write_path) |
| 금지 사항 7건 | 유지 |
| 전체 회귀 4549 PASS 기준선 | 유지 |

---

## 6. 최종 권고

### 권고: **RECOMMEND LIMITED L3 REVIEW**

#### 근거

1. **L0/L1/L2 작업이 1차 완결**되어 허용 범위 내 추가 작업이 사실상 없음
2. **CR-048 Phase 1 진행에 L3가 필수** — 모델 골격 없이는 구현 단계 진입 불가
3. **충분한 통제 수단** 존재 — Gate LOCKED + GR-RULE-01~03 + 재진입 조건 4개
4. **최소 범위를 명시** — 모델 골격 + 마이그레이션만, 서비스/실행/쓰기 차단 유지
5. **4549 PASS 기준선**이 이탈 감지 역할

#### 권고 범위

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│  권고:  LIMITED L3 REVIEW                           │
│                                                     │
│  허용:  모델 골격 4종 + Alembic 마이그레이션 1건     │
│         + 모델 단위 테스트                           │
│                                                     │
│  차단 유지:                                         │
│    - Injection Gateway 실행 로직                    │
│    - Promotion 상태 전이 실행                        │
│    - RuntimeStrategyLoader                          │
│    - write API (POST/PUT/PATCH/DELETE)              │
│    - beat schedule 변경                              │
│    - exchange_mode 변경                              │
│    - KIS_US 어댑터                                   │
│    - Feature Cache                                  │
│                                                     │
│  Gate:  LOCKED 유지                                 │
│  L4:    차단 유지                                    │
│                                                     │
│  조건:                                              │
│    - 모델이 설계 카드와 불일치 시 즉시 중단           │
│    - 회귀 테스트 기준선 유지 필수                     │
│    - baseline-check 6/6 유지 필수                    │
│    - 모델에 write 서비스 연결 시 A 재승인 필요        │
│                                                     │
└─────────────────────────────────────────────────────┘
```

#### 대안: HOLD L3

L3를 열지 않고 현재 상태를 유지하는 것도 유효합니다.
이 경우 CR-048은 설계+관측 단계에 머물며, Phase 1 구현 착수는 별도 시점에 판단합니다.

---

## A에게 요청하는 판정

| 판정 | 내용 |
|------|------|
| **APPROVE LIMITED L3** | 모델 골격 + 마이그레이션만 허용, 서비스/실행/쓰기 차단 유지 |
| **HOLD L3** | 현재 상태 유지, CR-048 구현은 별도 시점에 판단 |

---

**본 문서는 Guarded Release 종료 조건 평가서이며, A 판정 전까지 L3는 차단 상태입니다.**
**현재 상태: Guarded Release ACTIVE · Gate LOCKED · L0/L1/L2 허용 · L3/L4 차단 유지**

---

```
Guarded Release Exit Evaluation v1.0
Authority: A
Date: 2026-04-04
CR: CR-048
```
