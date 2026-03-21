# Governance ↔ Layer Map
**K-Dexter AOS — v1.0 | Step 2 of v4 Architecture Work**

이 문서는 L1~L30 각 레이어가 어느 거버넌스 계층(B1/B2/A)에 귀속되는지, 그리고 변경 권한이 누구에게 있는지를 명시한다.
v3 문서 Gap #2 해소. "이 레이어를 변경할 권한이 누구에게 있는가?"의 SSOT.

---

## 1. 거버넌스 계층 요약

| 계층 | 이름 | 역할 | 실행 여부 | Ledger 쓰기 |
|------|------|------|-----------|-------------|
| **B1** | Constitutional Foundry | 헌법 제정 / 교리 생성 / 비준 / 정당성 검증 | **금지** | 교리(Doctrine)만 |
| **B2** | Build Orchestration | Phase / Sandbox / Release / Rollback 관리 | 간접(빌드) | Rule Ledger (제한적) |
| **A** | Runtime Execution | 실제 트레이딩 실행 / 감사 로그 | **허용** | Evidence Store만 |

**변경 권한 원칙:**
- B1 귀속 레이어 → B1 비준 없이 변경 불가
- B2 귀속 레이어 → B2 승인 + B1 교리 준수 조건
- A 귀속 레이어 → B2 승인 (B1 교리 읽기 전용)
- **어떤 레이어도 B1 교리를 직접 수정할 수 없다**

---

## 2. L1~L30 거버넌스 귀속 테이블

| Layer | 이름 | 분류 | 구현 상태 | 거버넌스 계층 | 변경 권한 | 비고 |
|-------|------|------|-----------|---------------|-----------|------|
| **L1** | Human Decision | 거버넌스 | 완료 | **B1** | Human Only | 최상위 의사결정, 기계 변경 불가 |
| **L2** | Doctrine & Policy | 거버넌스 | 완료 | **B1** | B1 비준 필수 | 교리 생성·비준·활성화 |
| **L3** | Security & Isolation | 거버넌스 | 완료 | **B1** | B1 비준 필수 | 보안 정책은 헌법급 |
| **L4** | Clarify & Spec | 설계 | 완료 | **B2** | B2 승인 | Spec Twin 생성 담당 |
| **L5** | Harness / Scheduler | 설계 | 부분 | **B2** | B2 승인 | 실행 하네스, Research Engine 공백 포함 |
| **L6** | Parallel Agent | 실행 | 설계 중 | **A** | B2 승인 | TCL 통해서만 거래소 호출 |
| **L7** | Evaluation | 실행 | 완료 | **A** | B2 승인 | 전략 성과 평가 |
| **L8** | Execution Cell | 실행 | 설계 중 | **A** | B2 승인 | TCL 통해서만 거래소 호출 |
| **L9** | Self-Improvement Engine | 진화 | 설계 완료 | **B2** | B2 승인 + B1 교리 준수 | 진화 실험은 Sandbox 격리 |
| **L10** | Audit / Evidence Store | 감사 | 완료 | **A** | B2 승인 (정책은 B1) | 런타임 기록, 정책은 B1 교리 |
| **L11** | Rule Ledger | 감사 | 완료 | **B2** | B2 승인 + B1 교리 준수 | 동시 쓰기 제어 필수 (concurrency.py) |
| **L12** | Rule Provenance Store | 감사 | 완료 | **B2** | B2 승인 | 출처 추적, 읽기는 A도 가능 |
| **L13** | Compliance Engine | 감사 | 완료 | **B2** | B2 승인 | B1 교리 준수율 측정 |
| **L14** | Operation Evolution Engine | 진화 | 설계 완료 | **B2** | B2 승인 + B1 교리 준수 | Evolution Loop 핵심 |
| **L15** | Intent Drift Engine | 안전 | 미구현 | **B2** | B2 승인 | drift_high 임계값 미정의 (OQ) |
| **L16** | Rule Conflict Engine | 안전 | 미구현 | **B2** | B2 승인 | 충돌 검사, 결과는 B1 보고 |
| **L17** | Failure Pattern Memory | 안전 | 미구현 | **B2** | B2 승인 | Failure Taxonomy 연동 필수 |
| **L18** | Budget Evolution Engine | 예산 | 미구현 | **B2** | B2 승인 + B1 교리 준수 | Budget Doctrine 역산 필요 |
| **L19** | Trust Decay Engine | 신뢰 | 미구현 | **B2** | B2 승인 | 감소 함수 미정의 (OQ) |
| **L20** | Meta Loop Controller | 루프 | 미구현 | **B2** | B2 승인 | loop_count 상한 미정의 (OQ) |
| **L21** | Completion Engine | 검증 | 미구현 | **B2** | B2 승인 | completion score 공식 미정의 (OQ) |
| **L22** | Spec Lock System | 제어 | 미구현 | **B1/B2** | B1 비준 (잠금 해제) | 잠금 승인 주체 = B1 (v3 미정의 해소) |
| **L23** | Research Engine | 리서치 | 미구현 | **B2** | B2 승인 | L5 공백과 연동 |
| **L24** | Knowledge Engine | 리서치 | 미구현 | **B2** | B2 승인 | Research Engine 산출물 저장 |
| **L25** | Scheduler Engine | 운영 | 부분 | **B2** | B2 승인 | Main Loop 스케줄링 |
| **L26** | Recovery Engine | 복구 | 미구현 | **A** | B2 승인 (정책은 B1) | rollback anchor 미정의 (OQ) |
| **L27** | Override Controller | 제어 | 설계 완료 | **B1** | Human Only | LOCKDOWN 해제 권한 유일 보유 |
| **L28** | Loop Monitor | 루프 | 미구현 | **B2** | B2 승인 | 4개 루프 건강 상태 감시 |
| **L29** | Cost Controller | 예산 | 미구현 | **B2** | B2 승인 | LLM 비용 Budget Guard |
| **L30** | Progress Engine | 진화 | 미구현 | **B2** | B2 승인 | 진화 진척도 추적 |

---

## 3. TCL (Trading Command Language) 위치

v3 문서 Gap #6 해소: TCL은 L1~L30 레이어 맵에 존재하지 않았다.

**결정: TCL은 A 계층 인프라 레이어 (L8 하위 컴포넌트)**

```
L6 / L8 (Parallel Agent / Execution Cell)
        │
        │  표준 명령 (ORDER.BUY, ORDER.SELL ...)
        ▼
   TCL Layer  ← A 계층 인프라, L8의 하위 컴포넌트
        │
        │  거래소별 API 번역
        ▼
  Exchange Adapters (Binance / Bitget / Upbit / 한국투자증권 / 키움증권)
```

| 항목 | 결정 |
|------|------|
| 레이어 위치 | L8 하위 컴포넌트 (별도 레이어 번호 불필요) |
| 거버넌스 계층 | **A** (런타임 실행 인프라) |
| 변경 권한 | B2 승인 (어댑터 추가/변경) |
| B1 교리 | Execution Interface Doctrine 준수 필수 |
| 상위 레이어 직접 API 호출 | **금지** (TCL 통해서만) |

---

## 4. 거버넌스 계층별 귀속 레이어 요약

### B1 귀속 (5개)
```
L1  Human Decision
L2  Doctrine & Policy
L3  Security & Isolation
L22 Spec Lock System        ← 잠금 해제 승인 권한만 B1
L27 Override Controller
```

### B2 귀속 (21개)
```
L4  Clarify & Spec          L5  Harness / Scheduler
L9  Self-Improvement        L11 Rule Ledger
L12 Rule Provenance         L13 Compliance Engine
L14 Operation Evolution     L15 Intent Drift Engine
L16 Rule Conflict Engine    L17 Failure Pattern Memory
L18 Budget Evolution        L19 Trust Decay Engine
L20 Meta Loop Controller    L21 Completion Engine
L23 Research Engine         L24 Knowledge Engine
L25 Scheduler Engine        L28 Loop Monitor
L29 Cost Controller         L30 Progress Engine
L22 Spec Lock System        ← 잠금 실행은 B2
```

### A 귀속 (5개)
```
L6  Parallel Agent
L7  Evaluation
L8  Execution Cell  (+ TCL 하위 컴포넌트)
L10 Audit / Evidence Store
L26 Recovery Engine
```

---

## 5. 변경 권한 매트릭스

| 변경 유형 | B1 | B2 | A (Runtime) | Human |
|-----------|:--:|:--:|:-----------:|:-----:|
| B1 귀속 레이어 코드 변경 | 비준 필수 | 제안만 | 금지 | 최종 승인 |
| B2 귀속 레이어 코드 변경 | 교리 준수 확인 | 승인 | 금지 | - |
| A 귀속 레이어 코드 변경 | 교리 정책 적용 | 승인 | 금지 | - |
| Doctrine 변경 | 비준 필수 | 제안만 | 금지 | 최종 승인 |
| Rule Ledger 쓰기 | - | 루프별 Lock | 금지 | - |
| LOCKDOWN 해제 | - | 요청만 | 금지 | **Only** |
| TCL 어댑터 추가 | 교리 준수 확인 | 승인 | 금지 | - |

---

## 6. Open Questions (v4 확정 필요)

| # | 항목 | 관련 레이어 | 현재 상태 |
|---|------|-------------|-----------|
| OQ-4 | L15 drift_high 임계값 | L15 Intent Drift Engine | 미정의 |
| OQ-5 | L19 Trust 감소 함수 (선형/지수/이벤트) | L19 Trust Decay Engine | 미정의 |
| OQ-6 | L20 loop_count 상한 수치 | L20 Meta Loop Controller | 미정의 |
| OQ-7 | L21 completion score 공식 | L21 Completion Engine | 미정의 |
| OQ-8 | L26 rollback anchor 정의 | L26 Recovery Engine | 미정의 |

---

## 7. 연관 파일

| 파일 | 연관 이유 |
|------|-----------|
| `src/kdexter/governance/b1_constitution.py` | L1/L2/L3/L22/L27 구현 |
| `src/kdexter/governance/b2_orchestration.py` | B2 귀속 21개 레이어 조율 |
| `src/kdexter/layers/registry.py` | L1~L30 인스턴스 레지스트리 |
| `src/kdexter/tcl/` | L8 하위 TCL 컴포넌트 |
| `docs/architecture/failure_taxonomy.md` | L26 Recovery Engine 진입 조건 |
| `docs/architecture/mandatory_enforcement_map.md` | 각 레이어의 Mandatory 강제 시점 |
