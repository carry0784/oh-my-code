---
document_id: DOC-L4-COND-MULTI-EXCHANGE
title: "조건부 잠금: 다중 거래소"
level: L4
authority_mode: CONDITIONAL
parent: DOC-L2-INVARIANT-LENS
version: "1.0.0"
last_updated: "2026-03-21"
defines: []
may_reference: [DOC-L1-CONSTITUTION, DOC-L2-INVARIANT-LENS]
may_not_define: [CI-xxx, D-xxx, SecurityStateEnum, M-xx, G-xx, Invariant Lens 정의]
unlock_reason_class: SCALE_EXPANSION
---

## Lock Declaration

- **lock_declaration**: 본 문서는 잠금 상태이며, 해제 조건 충족 전까지 설계 확장이 금지된다.
- **해제 조건**: 다중 거래소 동시 운영이 필요하고, B1 비준이 완료된 경우
- **전제 교리**: D-001(TCL-only execution) — 모든 거래소는 TCL을 통해야 한다
- **향후 내용**: 다중 거래소 TCL 어댑터 확장, 교차 거래소 리스크 관리 정책
