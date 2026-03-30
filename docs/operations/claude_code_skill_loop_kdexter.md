# K-Dexter Claude Code Skill Loop — 운영 가이드

> agents → scripts → eval-viewer 를 하나의 AutoFix + Validation + Evaluation 루프로 연결

---

## 아키텍처

```
┌─────────────────┐     ┌──────────────────┐     ┌────────────────────┐
│ failure-analyzer │────>│   autofix-agent   │────>│ governance-checker │
│   (분석/분류)     │     │   (최소 수정)      │     │   (위반 점검)       │
└────────┬────────┘     └────────┬─────────┘     └────────┬───────────┘
         │                       │                         │
         │              BLOCK시 중단──────────────────────┘
         │                       │
         v                       v
┌─────────────────┐     ┌──────────────────┐
│  run_tests.py   │     │evaluate_results.py│
│  (테스트 실행)    │     │  (종합 평가)       │
└─────────────────┘     └──────────────────┘
         │                       │
         v                       v
┌─────────────────┐     ┌──────────────────┐
│validate_system.py│    │ data/*.json 출력   │
│  (구조 검증)      │    │ (eval-viewer 호환) │
└─────────────────┘     └──────────────────┘
```

---

## 파일 위치

| 구분 | 파일 | 역할 |
|------|------|------|
| **Agent** | `.claude/agents/autofix-agent.md` | 자동 수정 규칙 정의 |
| **Agent** | `.claude/agents/failure-analyzer.md` | 실패 분석 규칙 정의 |
| **Agent** | `.claude/agents/governance-checker.md` | 거버넌스 검증 규칙 정의 |
| **Script** | `scripts/run_tests.py` | 테스트 실행 + JSON 출력 |
| **Script** | `scripts/validate_system.py` | 시스템 구조 검증 |
| **Script** | `scripts/evaluate_results.py` | 결과 종합 평가 |
| **Eval** | `.claude/evals/kdexter_autofix_eval.md` | 평가 스펙 |
| **Eval** | `.claude/evals/kdexter_autofix_cases.json` | 5개 평가 케이스 |
| **Output** | `data/test_results.json` | 테스트 결과 |
| **Output** | `data/validation_results.json` | 검증 결과 |
| **Output** | `data/evaluation_report.json` | 종합 평가 |

---

## 실행 방법

### 전체 루프 실행 (순차)

```bash
# Step 1: 테스트 실행
python scripts/run_tests.py --scope governance

# Step 2: 시스템 검증
python scripts/validate_system.py

# Step 3: 결과 평가
python scripts/evaluate_results.py
```

### 특정 스코프만 테스트

```bash
python scripts/run_tests.py --scope governance   # 거버넌스
python scripts/run_tests.py --scope dashboard    # 대시보드
python scripts/run_tests.py --scope monitor      # G-MON
python scripts/run_tests.py --scope constitution # 헌법
python scripts/run_tests.py --scope all          # 전체
```

### JSON 출력으로 확인

```bash
python scripts/validate_system.py --json
python scripts/evaluate_results.py --format json
```

---

## agents → scripts → eval-viewer 흐름

### 1. 실패 감지 단계

```
pytest 실행 → 실패 발견 → failure-analyzer가 분류
```

failure-analyzer는 실패를 8가지 유형으로 분류:
F-TEST, F-IMPORT, F-LINT, F-MIGRATION, F-ENDPOINT,
F-GOVERNANCE, F-CONFIG, F-WORKER

### 2. 수정 단계

```
failure-analyzer 결과 → autofix-agent가 수정안 생성
→ governance-checker가 사전 검증
→ PASS 시에만 수정 적용
```

governance-checker는 8개 금지 규칙(GC-01~08)을 점검:
- GovernanceGate 우회 금지
- EvidenceStore append-only 보장
- SecurityState 초기값 보호
- Dashboard read-only 보호

### 3. 검증 단계

```
수정 후 → run_tests.py (재테스트)
        → validate_system.py (구조 검증)
        → evaluate_results.py (종합 평가)
```

### 4. 평가 출력

evaluate_results.py는 3단계 판정:
- **GREEN**: 모든 테스트 + 검증 통과
- **YELLOW**: 일부 실패 (수정 가능 수준)
- **RED**: 구조적 문제 (수동 개입 필요)

---

## 운영 시 주의사항

1. **autofix-agent는 3파일 초과 수정 금지** — 초과 시 중단하고 사람에게 보고
2. **governance-checker BLOCK 시 무조건 중단** — 자동 우회 불가
3. **alembic migration은 자동 수정 대상이 아님** — 경고만 생성
4. **실거래 경로(order_service, execution_cell) 수정은 추가 검증 필수**
5. **data/*.json 출력은 임시 파일** — git에 커밋하지 않음 (.gitignore 추가 권장)

---

## 확장 포인트

### 단기 확장

- G-MON Daily 리포트에 evaluation_report.json 연동
- Discord 알림에 평가 결과 포함
- Celery task로 주기적 자동 루프 실행

### 중기 확장

- failure-analyzer 결과를 FailurePatternMemory에 자동 기록
- autofix-agent 수정 이력을 EvidenceStore에 저장
- 수정 전/후 성능 비교 자동화

### 장기 확장 (4단계: 제한적 자기개선)

- SelfImprovementLoop(`src/kdexter/loops/self_improvement_loop.py`)와 연동
- 반복 실패 패턴 → 자동 재설계 제안 → 실험 레인에서 검증
- EvolutionLoop 트리거로 확장

---

## 헌법 준수 확인

| 원칙 | 준수 상태 |
|------|----------|
| 실행보다 통제 우선 | governance-checker가 autofix-agent보다 먼저 판정 |
| fail-closed | governance-checker BLOCK 시 수정 중단 |
| append-only evidence | EvidenceStore 수정 금지 (GC-03) |
| read-only monitoring | scripts는 모두 read-only (상태 수정 없음) |
| 최소 침습 | autofix-agent 3파일 상한 |
| 검증 후 반영 | 수정 후 재테스트 필수 |
