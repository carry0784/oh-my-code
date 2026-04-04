# Tab 3 Structure Seal — Control / Action / Execution 계층

---

## 1. Tab 3 전체 목적

> **Tab 3는 실행 / 승인 / 제어 / 로그를 다루는 control 계층이며, 자동 판단 또는 자동 실행 계층이 아니다.**

> **Tab 3는 read-write 가능하지만, 항상 승인 / 정책 / 상태 조건을 통과해야 한다.**

Tab 3는 Tab 2(관측)에서 확인한 상태를 기반으로, 운영자가 **조건을 확인하고 → 승인하고 → 실행을 트리거**하는 제어 계층이다.

Tab 3는 다음 역할**만** 가진다:
- 실행 준비 상태 표시
- 실행 가능 여부 확인
- 승인 필요 여부 표시
- 수동 실행 트리거 (조건 충족 후에만)
- action log 표시

**AI가 거래를 직접 실행하는 구조는 금지한다.**

---

## 2. Tab 3 전체 구조 (기준선)

```
Tab 3: Control / Action / Execution
│
├── Control Context
│   ├── Execution Status      — 현재 실행 상태 표시
│   ├── Approval State        — 승인 상태 + 만료 여부
│   └── Policy Gate           — 정책 충족 여부 + 조건 테이블
│
├── Action Console
│   ├── Manual Action         — 수동 실행 트리거 (조건 통과 후에만 활성)
│   ├── Action Preview        — 실행 전 영향 미리보기 (read-only)
│   └── Action Result         — 실행 결과 표시
│
└── Execution Log
    ├── Action Log            — 실행 이력
    ├── Error Log             — 실행 오류 이력
    └── Audit Log             — 감사 증적
```

**이 구조를 기준선으로 봉인한다.**

---

## 3. Tab 3 금지 규칙

| # | 금지 항목 | 근거 |
|---|----------|------|
| 1 | **자동 실행 금지** | 운영자 트리거 없이 실행 불가 |
| 2 | **승인 없이 실행 금지** | I-06 APPROVED + 미만료 필수 |
| 3 | **정책 위반 실행 금지** | I-07 MATCH 필수 |
| 4 | **새로운 점수 생성 금지** | 기존 ops_score만 참조 |
| 5 | **AI 단독 결정 금지** | AI 추천은 표시만, 실행은 운영자만 |
| 6 | **Pipeline 우회 금지** | I-03→I-04→I-05→I-06→I-07→E-01 전체 통과 필수 |
| 7 | **Ledger 우회 금지** | ForbiddenLedger 검사 필수 |
| 8 | **Evidence 없는 실행 금지** | No Evidence, No Power |
| 9 | **승인 만료 후 실행 금지** | approval_expiry_at 경과 시 재승인 필요 |
| 10 | **scope 초과 실행 금지** | execution_scope ⊆ approval_scope |

---

## 4. Tab 2 vs Tab 3 차이

| 항목 | Tab 2 | Tab 3 |
|------|-------|-------|
| **성격** | 관측 (Observation) | 제어 (Control) |
| **접근 모드** | read-only | controlled write |
| **목적** | 상태 표시 | 실행 준비 + 트리거 |
| **데이터** | 기존 값 기반 | 조건 통과 후 동작 |
| **버튼** | 없음 | 조건부 활성 (조건 미충족 시 비활성) |
| **AI 역할** | 이상 징후 표시, 가설 제시 | 추천 표시만 (실행 권한 없음) |
| **승인** | 불필요 | 필수 (I-06 + I-07) |
| **실행** | 금지 | 조건 충족 후 수동 트리거만 |
| **구조 봉인** | tab2_structure_seal.md | **tab3_structure_seal.md** |

---

## 5. Tab 3 실행 원칙

### Execution Precondition Chain

실행은 반드시 아래 **전체**를 통과해야 한다:

```
1. Pipeline Ready     — I-03 Check ≠ BLOCK
2. Preflight Ready    — I-04 decision = READY
3. Gate Open          — I-05 decision = OPEN (4조건 AND)
4. Approval OK        — I-06 decision = APPROVED + 미만료
5. Policy Match       — I-07 decision = MATCH
6. Risk OK            — RiskFilter 통과
7. Auth OK            — trading_authorized = true + lockdown = inactive
8. Scope Compatible   — execution_scope ⊆ approval_scope
9. Evidence Chain     — I-03~I-07 증거 체인 완전
```

**조건 불충족 시 실행 완전 금지. Fail-closed.**

### 실행 흐름

```
[운영자 확인] → [조건 자동 검증] → [미충족 시 거부 + 사유 표시]
                                  → [충족 시 실행 대기 + Preview 표시]
                                  → [운영자 수동 트리거]
                                  → [실행 + Evidence 기록]
                                  → [결과 표시 + Audit Log]
```

---

## 6. Tab 3 계층별 역할

### Control Context

| 섹션 | 역할 | 데이터 소스 |
|------|------|-----------|
| Execution Status | 현재 E-01/E-02/E-03 상태 표시 | ops-executor / ops-activation / ops-dispatch |
| Approval State | I-06 승인 영수증 + 만료 상태 | ops-approval |
| Policy Gate | I-07 정책 일치 + 조건 상세 | ops-policy + ops-gate |

### Action Console

| 섹션 | 역할 | 조건 |
|------|------|------|
| Manual Action | 수동 실행 트리거 버튼 | **전체 9조건 충족 시에만 활성** |
| Action Preview | 실행 전 영향 범위 미리보기 (read-only) | 항상 표시 |
| Action Result | 직전 실행 결과 | 실행 후 표시 |

### Execution Log

| 섹션 | 역할 |
|------|------|
| Action Log | 실행 이력 (성공/실패/취소) |
| Error Log | 실행 오류 상세 |
| Audit Log | 감사 증적 (evidence bundle) |

---

## 7. Tab 3 변경 규칙

### 구조 변경 절차
1. **문서 먼저 수정** (tab3_structure_seal.md)
2. 카드 발행 (implementation_cards.md)
3. 설계 정의본 제출
4. GO 승인
5. 구현
6. 헌법 조항 대조 검수본
7. PASS 판정

### 봉인 규칙
- 이 문서(tab3_structure_seal.md)를 위반하는 구현은 **REJECT**
- 구조 변경은 반드시 문서 수정이 코드 수정보다 선행
- 금지 규칙 10개 항목은 영구 금지

### 긴급 시
- L-03 emergency override만 허용
- 긴급 시에도 evidence 기록 필수

---

## 8. Tab 3 카드 후보 (구현 대기)

| 카드 | 범위 | 선행 |
|------|------|------|
| C-01 | Execution Status Panel | 봉인 완료 |
| C-02 | Approval State Panel | C-01 |
| C-03 | Policy Gate Panel | C-02 |
| C-04 | Manual Action Console | C-03 |
| C-05 | Action Preview | C-04 |
| C-06 | Action Result | C-05 |
| C-07 | Action Log | C-06 |
| C-08 | Error Log | C-07 |
| C-09 | Audit Log | C-08 |

**카드 발행 순서는 봉인 완료 후 운영자 승인으로 결정.**

---

*문서 확정 시각: 2026-03-26*
*코드 수정: 없음*
*이 문서는 Tab 3 구조 기준선 확정 문서이다.*
*Tab 3 구현은 이 문서의 봉인 후에만 시작 가능하다.*
