# 0001 — Minimum Safety Framework Adoption

**Date**: 2026-04-16
**Author**: operator (directive) + claude-code (execution)
**Gate classification**: governance — directive-level
**Scope**: governance

## What

사용자 명시 지시로 운영 거버넌스가 다음과 같이 재정의됨:

### 새 최소 안전장치 (3 항목)

1. **파괴적 삭제, 실제 배포, 실거래, 비가역 변경**은 반드시 **명시 승인**을 받아야 한다.
2. **모든 주요 변경**은 무엇을 왜 바꾸었는지 **로그와 변경 사유**를 남겨야 한다.
3. 작업이 막히거나 기존 구조가 비효율적이면, 기존 틀에 억지로 묶이지 말고 **더 나은 구조로 재설계**할 수 있다.

### 자율 범위

위 3가지를 제외한 **설계·계획 수립·구조 개편·코드 작성·구현·수정·리팩터링·문서 재구성**은 claude-code가 독자적으로 수행한다.

## Why

이전의 CR-NEW v3.1 HOLD 체제는 대화 층위에서 canonical GO verbatim을 매 작업마다 요구하여, 실제 코드/문서/설계 작업이 수십 턴에 걸쳐 메타-거버넌스 루프에 묶여 있었음. 사용자께서 이를 "완전 무정부 상태"로 가지 않는 선에서 최소 경계만 남기고 자율화하도록 명시적으로 전환.

본 변경은 다음을 supersede 한다:
- Turn 65~72에서 누적된 canonical GO verbatim 강제 절차
- `go_issuance_status: UNRESOLVED` 대기 posture
- `template ≠ GO issuance` 절대 기각 룰 (세부 요청에 대한)
- 대화 턴 단위의 MCC-02 confirmation_only 루프

단, 다음은 유지된다:
- `ops_state.json` 내 `sealed_crs`, `prohibitions`, `baseline_values` 등 프로젝트 차원의 영구 거버넌스
- `SEALED PASS` 항목 재개방 금지
- `DATA_ONLY` 계약 훼손 금지
- `ETH` 운영 경로 금지
- `CR-049 Phase 3` (PAPER/LIVE Mode) 구현 금지 — 이는 새 안전장치 #1 (실거래/실배포) 게이트에 해당하므로 명시 승인 필수
- `activation_gate: LOCKED`, `writes_consumed=0`, `write_budget=1` — 실행 경로 개방은 별도 승인

## Evidence

- 사용자 지시 원문: 본 turn 메시지 (2026-04-16)
- 이전 체제 최종 anchor: Turn 67 (go_issuance_status: UNRESOLVED 승인본 고정)
- 이전 체제 refusal 예시: Turn 72 (프레임워크 무시·재작성·재시작 요청에 대한 승인 불가 verdict)

## Reversibility

- **Reversible at directive level**: 사용자께서 다시 엄격 거버넌스로 회귀 지시하시면 즉시 전환 가능
- 본 changelog 엔트리 자체는 영구 이력
- 본 변경은 실제 코드/인프라를 건드리지 않음 — 작업 방식 전환만 선언

## 게이트 분류 (이후 작업용 참조)

| 작업 유형 | 게이트 | 비고 |
|---|---|---|
| 코드 작성/수정/리팩터 | autonomous | |
| 테스트 추가 | autonomous | |
| 문서 작성/재구성 | autonomous | |
| 디렉토리 구조 개편 | autonomous | rule #3 발동 가능 |
| 설정 파일 수정 (docker-compose 등) | autonomous | 단, 배포 트리거 없을 때 |
| DB 스키마 변경 (migrations) | autonomous | append-only forward migration |
| DB 데이터 삭제 (downgrade destructive) | **explicit-approval** | rule #1 #1 파괴적 삭제 |
| `git push origin main` 강제 | **explicit-approval** | rule #1 비가역 |
| production 배포 | **explicit-approval** | rule #1 실배포 |
| 거래소 API key 실거래 전환 | **explicit-approval** | rule #1 실거래 |
| `activation_gate` UNLOCK | **explicit-approval** | 기존 프로젝트 거버넌스 |
| sealed CR 재개방 | **explicit-approval** | 기존 금지 조항 |
| CR-049 Phase 3 구현 | **explicit-approval** | 기존 금지 조항 + 실거래 관련 |

## Follow-up

- `docs/operations/changelog/0002_*` 부터 실제 작업 로그 시작
- 기존 미커밋/untracked 변경 검토 → 각 항목별 changelog 엔트리 동반 커밋

