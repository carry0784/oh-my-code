---
document_id: DOC-L4-COND-MODEL-UPGRADE
title: "조건부 잠금: 모델 업그레이드"
level: L4
authority_mode: CONDITIONAL
parent: DOC-L2-INVARIANT-LENS
version: "1.0.0"
last_updated: "2026-03-21"
defines: []
may_reference: [DOC-L1-CONSTITUTION, DOC-L2-INVARIANT-LENS]
may_not_define: [CI-xxx, D-xxx, SecurityStateEnum, M-xx, G-xx, Invariant Lens 정의]
unlock_reason_class: MODEL_EVOLUTION
---

## Lock Declaration

- **lock_declaration**: 본 문서는 잠금 상태이며, 해제 조건 충족 전까지 설계 확장이 금지된다.
- **해제 조건**: AI/ML 모델 업그레이드가 필요하고, B1 비준이 완료된 경우
- **전제 교리**: D-005(B1 immutability) — 모델 변경이 B1 교리를 위반하지 않아야 한다
- **향후 내용**: 모델 교체 Sandbox 정책, 모델 성능 비교 Gate 기준
