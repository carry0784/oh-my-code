# Promotion State 설계 카드

**문서 ID:** DESIGN-P1-004
**작성일:** 2026-04-04
**Authority:** A (Decision Authority)
**CR:** CR-048 Phase 1 (Control Plane — Registry)
**Status:** **DESIGN_ONLY**
**변경 등급:** L0 (설계 문서)

---

## 1. 해석 및 요약

### 목적

전략의 생애 상태(Promotion State)와 상태 전이 조건을 관리.
7개 Bank, 10개 상태, 엄격한 전이 조건으로 미검증 전략의 실전 진입을 원천 차단.

### 상태 정의

| Bank | 상태 | 코드 | 설명 |
|------|------|------|------|
| Research | DRAFT | `DRAFT` | 초안 작성 중 |
| Research | REGISTERED | `REGISTERED` | 등록 완료, 백테스트 대기 |
| Qualified | BACKTEST_PASS | `BACKTEST_PASS` | 9단계 백테스트 통과 |
| Qualified | BACKTEST_FAIL | `BACKTEST_FAIL` | 백테스트 실패 (재시도 가능) |
| Paper | PAPER_PASS | `PAPER_PASS` | Paper Shadow 2주 통과 |
| **Quarantine** | QUARANTINE | `QUARANTINE` | 이상 징후 격리 |
| Live | GUARDED_LIVE | `GUARDED_LIVE` | 제한적 실전 (자본 50%, 종목 50%) |
| Live | LIVE | `LIVE` | 완전 실전 |
| Retired | RETIRED | `RETIRED` | 정상 은퇴 |
| Blocked | BLOCKED | `BLOCKED` | 영구 차단 |

### 상태 전이 다이어그램

```
DRAFT → REGISTERED
    → [9단계 Backtest]
        → BACKTEST_PASS
        → BACKTEST_FAIL → (수정 후) → REGISTERED (재시도)

BACKTEST_PASS → [Paper Shadow 2주]
    → PAPER_PASS
    → BACKTEST_FAIL (Paper 중 실패)

PAPER_PASS → [A 승인] → GUARDED_LIVE (자본 50%, 종목 50%)
GUARDED_LIVE → [4주 안정] → LIVE
GUARDED_LIVE → [이상 징후] → QUARANTINE

LIVE → [이상 징후] → QUARANTINE
LIVE → [성과 장기 하락] → RETIRED

QUARANTINE → [복구 가능] → GUARDED_LIVE
QUARANTINE → [복구 불가] → BLOCKED

Any → [문제 발생] → 이전 Champion으로 즉시 롤백
```

### 전이 조건 요약

| 전이 | 조건 | 승인 |
|------|------|------|
| DRAFT → REGISTERED | Injection Gateway 검증 PASS | 자동 |
| REGISTERED → BACKTEST_PASS | 9단계 전부 PASS | 자동 |
| REGISTERED → BACKTEST_FAIL | 9단계 중 하나 FAIL | 자동 |
| BACKTEST_PASS → PAPER_PASS | Paper Shadow 2주 + 7개 기준 PASS | 자동 |
| PAPER_PASS → GUARDED_LIVE | — | **A 승인 필수** |
| GUARDED_LIVE → LIVE | 4주 안정 (건전성 점수 > 60%) | **A 승인 필수** |
| * → QUARANTINE | 이상 징후 감지 | 자동 (Phase 9 Recovery) |
| QUARANTINE → GUARDED_LIVE | 원인 해소 + 검증 PASS | **A 승인 필수** |
| QUARANTINE → BLOCKED | 복구 불가 판정 | **A 승인 필수** |
| LIVE → RETIRED | 90일 음수 수익 또는 A 판정 | **A 승인 필수** |
| Any → 롤백 | 이전 Champion 복귀 | Approver |

---

## 2. 장점 / 단점

### 장점

| 장점 | 설명 |
|------|------|
| **미검증 전략 실전 진입 불가** | REGISTERED → LIVE 직행 경로 없음 |
| **격리 체계** | Quarantine Bank으로 이상 전략 즉시 격리 |
| **점진적 노출** | GUARDED_LIVE (50%) → LIVE (100%) 단계적 확대 |
| **전이 이력 완전 추적** | 모든 전이에 시각, 행위자, 사유 기록 |
| **자동+수동 균형** | 백테스트/Paper는 자동, Live 승격은 A 승인 |

### 단점

| 단점 | 완화 방안 |
|------|-----------|
| 최소 6주+ 소요 (Paper 2주 + Guarded 4주) | Fast-Track (A 승인 시 단축 가능) |
| Quarantine 오탐 가능 | 오탐 시 A 승인으로 GUARDED_LIVE 복귀 |
| BLOCKED 해제 불가 | 의도적 — 영구 차단은 새 전략으로 대체 |

---

## 3. 이유 / 근거

### 근거 1 — 단계적 검증의 필요성

| 단계 | 발견 가능한 문제 |
|------|-----------------|
| 9단계 Backtest | 데이터 오류, 미래 누수, OOS 실패, 비용 미반영 |
| Paper Shadow 2주 | 실시간 데이터에서의 성능 괴리, 슬리피지 영향 |
| Guarded Live 4주 | 실자본 효과, 시장 충격, 체결 품질 |

각 단계에서 다른 유형의 문제를 발견 → 단축 불가(Fast-Track 제외).

### 근거 2 — Quarantine의 필요성

CR-046 Track B의 `CV_INSTABILITY`:
- 초기 fold에서는 55% 승률 → 후기 fold에서 25%로 붕괴
- Paper 통과했더라도 Live에서 같은 현상 발생 가능

→ 실시간 성과 하락 감지 시 즉시 Quarantine 전환 필요.

### 근거 3 — Champion/Challenger 패턴

- 현행 전략(Champion)이 항상 존재
- 새 전략(Challenger)은 반드시 Champion보다 우수해야 승격
- 문제 발생 시 즉시 Champion으로 롤백

→ 서비스 중단 없는 전략 교체 보장.

---

## 4. 실현 / 구현 대책

### 4.1 DB 모델 (설계만)

```python
class PromotionState(str, Enum):
    DRAFT = "DRAFT"
    REGISTERED = "REGISTERED"
    BACKTEST_PASS = "BACKTEST_PASS"
    BACKTEST_FAIL = "BACKTEST_FAIL"
    PAPER_PASS = "PAPER_PASS"
    QUARANTINE = "QUARANTINE"
    GUARDED_LIVE = "GUARDED_LIVE"
    LIVE = "LIVE"
    RETIRED = "RETIRED"
    BLOCKED = "BLOCKED"

class PromotionHistory(Base):
    __tablename__ = "promotion_history"

    id: int                     # PK
    strategy_id: str            # FK → StrategyRegistry.id
    from_state: PromotionState
    to_state: PromotionState
    reason: str                 # 전이 사유
    evidence: dict | None       # 백테스트 결과, Paper 성과 등
    triggered_by: str           # "auto" | user_id
    approved_by: str | None     # A 승인 시 승인자 ID
    created_at: datetime
```

### 4.2 전이 유효성 매트릭스

```python
VALID_TRANSITIONS = {
    "DRAFT":          {"REGISTERED"},
    "REGISTERED":     {"BACKTEST_PASS", "BACKTEST_FAIL"},
    "BACKTEST_FAIL":  {"REGISTERED"},          # 재시도
    "BACKTEST_PASS":  {"PAPER_PASS", "BACKTEST_FAIL"},
    "PAPER_PASS":     {"GUARDED_LIVE"},        # A 승인 필수
    "GUARDED_LIVE":   {"LIVE", "QUARANTINE"},
    "LIVE":           {"QUARANTINE", "RETIRED"},
    "QUARANTINE":     {"GUARDED_LIVE", "BLOCKED"},  # A 승인 필수
    "RETIRED":        set(),                   # 종료 상태
    "BLOCKED":        set(),                   # 종료 상태
}
```

### 4.3 승인 요구 전이

```python
REQUIRES_APPROVAL = {
    ("PAPER_PASS", "GUARDED_LIVE"):    "APPROVER",   # A 승인
    ("GUARDED_LIVE", "LIVE"):          "APPROVER",   # A 승인
    ("QUARANTINE", "GUARDED_LIVE"):    "APPROVER",   # A 승인
    ("QUARANTINE", "BLOCKED"):         "APPROVER",   # A 승인
    ("LIVE", "RETIRED"):               "APPROVER",   # A 승인
}
```

### 4.4 자동 전이 트리거

| 트리거 | 전이 | 출처 |
|--------|------|------|
| Backtest 9단계 전부 PASS | REGISTERED → BACKTEST_PASS | Phase 4 |
| Backtest 중 하나 FAIL | REGISTERED → BACKTEST_FAIL | Phase 4 |
| Paper Shadow 2주 + 7기준 PASS | BACKTEST_PASS → PAPER_PASS | Phase 4 |
| 이상 징후 감지 | * → QUARANTINE | Phase 9 |
| Champion rollback 실행 | 현행 → 이전 Champion 상태 복원 | Phase 9 |

### 4.5 Quarantine 진입 조건 (Phase 9 연동)

| 조건 | 자동 Quarantine |
|------|:--------------:|
| 건전성 점수 < 30% (7일 유지) | ✅ |
| MaxDD > 등록 시 기대값 × 2 | ✅ |
| Win rate < 등록 시 기대값 × 0.5 | ✅ |
| 체크섬 불일치 감지 | ✅ |
| 금지 경로 접근 시도 | ✅ |
| 7일 내 같은 fault 3회 | ✅ (면역 체계) |

### 4.6 API 엔드포인트 (설계만)

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| `GET` | `/api/v1/registry/strategies/{id}/promotion` | 현재 승격 상태 | Viewer+ |
| `GET` | `/api/v1/registry/strategies/{id}/promotion/history` | 전이 이력 | Viewer+ |
| `POST` | `/api/v1/registry/strategies/{id}/promotion/transition` | 상태 전이 요청 | Operator+ (자동 전이) / Approver+ (승인 전이) |

### 4.7 허용/금지/승인 필요 정리

| 행위 | 허용 여부 | 비고 |
|------|:---------:|------|
| DRAFT → REGISTERED (자동) | ✅ | Gateway 검증 PASS 시 |
| REGISTERED → BACKTEST_PASS (자동) | ✅ | 9단계 PASS 시 |
| BACKTEST_PASS → PAPER_PASS (자동) | ✅ | Paper 2주 PASS 시 |
| PAPER_PASS → GUARDED_LIVE | ⚠️ | **A 승인 필수** |
| GUARDED_LIVE → LIVE | ⚠️ | **A 승인 필수** |
| QUARANTINE → GUARDED_LIVE | ⚠️ | **A 승인 필수** |
| 유효하지 않은 전이 | ⛔ | VALID_TRANSITIONS 위반 |
| BLOCKED 해제 | ⛔ | 종료 상태, 새 전략으로 대체 |
| RETIRED 복활 | ⛔ | 종료 상태, 새 버전 발행 |
| 단계 건너뛰기 (REGISTERED → LIVE) | ⛔ | **영구 금지** |

---

## 5. 실행방법

| 단계 | 작업 | 등급 |
|------|------|------|
| 1 | 본 설계 카드 A 승인 | L0 |
| 2 | StrategyRegistry 구현 완료 (선행) | L3 |
| 3 | PromotionState enum 구현 | L3 |
| 4 | PromotionHistory 모델 구현 | L3 |
| 5 | 전이 유효성 검사 + 승인 요구 로직 | L3 |
| 6 | API 엔드포인트 구현 | L3 |
| 7 | 자동 전이 트리거 연동 (Phase 4+9) | L3 |
| 8 | 단위 테스트 | L1 |

테스트 항목:
- `test_valid_transitions.py` — 모든 유효 전이 PASS
- `test_invalid_transitions.py` — 유효하지 않은 전이 거부
- `test_approval_required.py` — A 승인 없이 고위험 전이 거부
- `test_quarantine_auto.py` — 자동 Quarantine 트리거
- `test_promotion_history.py` — 전이 이력 정확 기록

---

## 6. 더 좋은 아이디어

### 6.1 승격 대시보드 (Phase 7)

Strategy Bank 탭에 승격 현황 시각화:

```
Research [■■□□□] 2 strategies
Qualified [■□□□□] 1 strategy
Paper [□□□□□] 0 strategies
Quarantine [□□□□□] 0 strategies
Live [□□□□□] 0 strategies (목표: 5~10)
Retired [□□□□□] 0 strategies
Blocked [□□□□□] 0 strategies
```

### 6.2 전이 예측 (ETA)

각 전략의 다음 단계 예상 도달 시각:
```
strat_momentum_v2.1.4:
  현재: BACKTEST_PASS
  Paper Shadow 시작: 2026-04-10
  Paper Shadow 완료 예상: 2026-04-24 (2주)
  GUARDED_LIVE 가능 시점: 2026-04-24 (A 승인 대기)
  LIVE 가능 시점: 2026-05-22 (4주 안정 후)
```

### 6.3 Quarantine 자동 진단 리포트

Quarantine 진입 시 자동으로 진단 리포트 생성:
- 최근 7일 성과 그래프
- 원인 후보 목록 (regime 변화, 데이터 이상, 체결 품질)
- 복구 가능성 평가 (HIGH/MEDIUM/LOW)
- 추천 조치 (파라미터 조정/FP 교체/BLOCKED)

→ A의 판단 시간 단축.

---

## L3 구현 선행조건 체크리스트

| # | 조건 | 충족 여부 |
|---|------|:---------:|
| 1 | Phase 0 문서 3종 A 승인 | ⬜ |
| 2 | Indicator / FeaturePack / Strategy 설계 카드 A 승인 | ⬜ |
| 3 | 본 설계 카드 A 승인 | ⬜ |
| 4 | StrategyRegistry 구현 완료 | ⬜ |
| 5 | Gate LOCKED 해제 또는 L3 개별 A 승인 | ⬜ |
| 6 | 전체 회귀 테스트 PASS | ⬜ |

**0/6 충족. 구현 착수 불가.**

---

```
Promotion State Design Card v1.0
Authority: A
Date: 2026-04-04
CR: CR-048 Phase 1
```
