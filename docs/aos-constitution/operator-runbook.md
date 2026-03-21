---
document_id: DOC-L3-RUNBOOK
title: "운영자 대응 절차서"
level: L3
authority_mode: OPERATIONAL
parent: DOC-L2-SPRINT-PLAN
version: "1.0.0"
last_updated: "2026-03-21"
defines: [LOCKDOWN 대응 절차, SecurityState 에스컬레이션 절차, 금지행위 대응 절차, Recovery 절차, Doctrine 일시중지 절차, 동시 실패 대응, Deadlock 해소]
may_reference: [DOC-L1-CONSTITUTION, DOC-L2-EXT-API-GOV, DOC-L2-INVARIANT-LENS, DOC-L2-RSG]
may_not_define: [CI-xxx, D-xxx, SecurityStateEnum 값, Invariant Lens 정의]
---

# 운영자 대응 절차서

## 1. LOCKDOWN 대응 절차

1. LOCKDOWN 트리거 원인을 EvidenceBundle에서 확인한다.
2. 원인이 CONSTITUTIONAL 교리 위반인 경우, 위반 doctrine_id와 violated_by를 확인한다.
3. 원인이 Forbidden Action LOCKDOWN severity인 경우, 해당 FA-xxx를 확인한다.
4. L27 Override Controller를 통해 Human Override를 요청한다.
5. authorized_by = "HUMAN_OVERRIDE"로 release_lockdown()을 호출한다.
6. RSG(DOC-L2-RSG)를 통해 안정화 판정을 수행한다.
7. 해제 결과가 EvidenceBundle로 기록됨을 확인한다.

## 2. SecurityState 에스컬레이션 절차

SecurityState 정의 및 전이 규칙: DOC-L1-CONSTITUTION §6. 아래는 운영자 조치만 기술한다.

| 현재 상태 | 조치 |
|-----------|------|
| NORMAL → RESTRICTED | Failure 원인 확인, 자동 복구 대기 |
| RESTRICTED → QUARANTINED | 수동 개입 준비, Sandbox 격리 확인 |
| QUARANTINED → LOCKDOWN | 즉시 Human Override 준비, 모든 자동 작업 중지 |

de-escalation은 RSG 통과가 필요하다.
LOCKDOWN de-escalation은 반드시 Human Override가 필요하다(D-004).

## 3. 금지행위 사고 대응

1. VALIDATING [1] FORBIDDEN_CHECK에서 위반이 감지된다.
2. ForbiddenViolation의 severity를 확인한다.
3. LOCKDOWN severity → §1 LOCKDOWN 대응 절차로 이동한다.
4. BLOCKED severity → BLOCKED 상태에서 원인 분석 후 재시도를 판단한다.
5. 모든 위반은 EvidenceBundle에 기록된다.

## 4. Recovery Loop 발동 절차

1. Failure Taxonomy(DOC-L2-EXT-API-GOV §8)에 따라 Domain, Severity, Recurrence를 판정한다.
2. Loop 라우팅 정책(DOC-L2-EXT-API-GOV §9)에 따라 담당 Loop를 결정한다.
3. Recovery Loop가 발동되면 Main Loop는 일시 중단된다.
4. Recovery는 사고당 최대 3회 시도 가능하다(D-006).
5. 3회 초과 시 Human Override를 요청한다.

## 5. Doctrine 일시중지 절차

1. 핵심 교리(D-001~D-010)는 일시중지할 수 없다.
2. 추가 교리의 일시중지는 B1 비준이 필요하다.
3. suspend_doctrine()을 B1 권한으로 호출한다.
4. 일시중지 사유가 EvidenceBundle에 기록된다.

## 6. 동시 실패 대응

우선순위: Recovery > Main > Self-Improvement > Evolution
Recovery 활성 중 새 Failure → 기존 Recovery에 병합한다.
Evolution Queue 대기가 timeout_evolution_defer를 초과하면 Human Override를 알린다.

## 7. Deadlock 해소

Deadlock 감지 조건(DOC-L2-EXT-API-GOV §10) 충족 시:
1. Recovery Loop와 Main Loop의 Lock 상태를 확인한다.
2. Human Override를 요청하여 Lock을 강제 해제한다.
3. 해소 결과를 EvidenceBundle에 기록한다.

## 8. U0~U3 대응 절차

U0~U3 상태 정의: DOC-L2-INVARIANT-LENS §6. 아래는 운영자 대응 수준만 기술한다.

| 상태 | 대응 |
|------|------|
| U0 | 정상 운영 |
| U1 | 추가 정보 수집 권고, 실행 허용 |
| U2 | 실행 보류, 검토 필요 |
| U3 | 외부 실행 금지, outbound 시 LOCKDOWN 대상 |

## 9. E0~E4 대응 절차

E0~E4 상태 정의: DOC-L2-INVARIANT-LENS §8. 아래는 운영자 대응 수준만 기술한다.

| 상태 | 대응 |
|------|------|
| E0 | 판단 불가, 증거 수집 필요 |
| E1 | 추가 증거 수집 후 재판정 |
| E2 | 판정 진행 가능 |
| E3 | 판정 확정 가능 |
| E4 | 판정 확정 + 교차 검증 완료 |

### Invariant Lens 반영

본 절차서는 구조적 불변량 §3.3(LOCKDOWN 해제 제한), §3.4(증거 의무)를 행사한다.
모든 대응 절차에서 EvidenceBundle 생산이 필수이며, LOCKDOWN 해제는 Human Override만 가능하다.
U·C·E 상태(DOC-L2-INVARIANT-LENS §6~§8)에 따른 대응 수준을 준수한다.
