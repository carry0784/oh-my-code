---
document_id: DOC-L5-CHANGELOG
title: "헌법 문서 체계 변경 이력"
level: L5
authority_mode: APPEND_ONLY
parent: DOC-L1-CONSTITUTION
version: "1.0.0"
last_updated: "2026-03-21"
defines: [문서 변경 이력]
may_reference: [DOC-L1-CONSTITUTION, DOC-L2-SPRINT-PLAN, DOC-L2-EXT-API-GOV, DOC-L2-INVARIANT-LENS, DOC-L2-RSG, DOC-L2-AI-TOOL-ROLE, DOC-L2-HARNESS]
may_not_define: [CI-xxx, D-xxx, SecurityStateEnum, M-xx, G-xx, 정책, Sprint 내용]
---

# 헌법 문서 체계 변경 이력

> 본 문서는 APPEND_ONLY이다. 기존 항목을 수정하거나 삭제할 수 없다.
> 새 항목은 항상 최상단에 추가한다.

## 변경 이력

| 날짜 | document_id | 변경 유형 | 요약 |
|------|------------|-----------|------|
| 2026-03-30 | DOC-L2-HARNESS | 신규 추가 | Claude Code A/B/C Harness Constitution 최초 작성. 3인 역할 분리(설계/구현/검수), 금지행위(A-P01~04, B-P01~07, C-P01~05), 자동 BLOCK 사유(CB-01~07), 등급별 적용(Level A/B/C), Sprint Contract Card 템플릿, Claude Code C 검수 기준표. DOC-L2-AI-TOOL-ROLE §8을 모든 개발 작업으로 확장. |
| 2026-03-29 | DOC-L2-AI-TOOL-ROLE | 갱신 | BUDGET_CHECK, PATTERN_CHECK를 deferred → passed/failed로 전환. L29 CostController, L17 FailurePatternMemory 연결 반영. |
| 2026-03-29 | DOC-L2-AI-TOOL-ROLE | 신규 추가 | AI 도구 역할 헌법 최초 작성. 4개 연결 도구 역할·권한·금지행위 정의, 7개 공통 금지행위(P-01~P-07), Provider 변경 거버넌스(R-01~R-06), 상태별 도구 허용 매핑, 설계 운영 3단계, 미연결 도구 도입 절차. verify_constitution.py 기대값 25→26 갱신. |
| 2026-03-21 | ALL | OPS-GATE-008 | 최종 운영 기준선 봉인. OPS-GATE-001~008 유효 선언, 작업 시작 규약 7항, 게이트 종료 선언, 작업 시작 프롬프트 추가. 헌법 의미 변경 없음. |
| 2026-03-21 | ALL | OPS-GATE-007 | Reference Drift Guard 추가. OPS_GUIDE.md에 비정의 원칙·drift 갱신 규칙·의심 시 조치를, MERGE_RULES.md §5.5에 Reference Check 절차를 추가. 운영 게이트 의미 변경 없음. |
| 2026-03-21 | ALL | OPS-GATE-006 | 운영 게이트 기준선 봉인. OPS-GATE-001~005 유효 기준선 선언, SSOT 우선순위/참조 관계/운영자 절차표/중복 검사 결과를 .github/OPS_GUIDE.md로 정리. 헌법 의미 변경 없음. |
| 2026-03-21 | ALL | OPS-GATE-005 | Merge 직전 게이트 최적화. 5줄→3줄 축약(목적/변경유형은 사전 점검 참조, 예상-실제 diff/verify/merge 가능 여부만 유지). 통제 강도 유지, 마찰 감소. 헌법 의미 변경 없음. |
| 2026-03-21 | ALL | OPS-GATE-004 | 운영 게이트 리허설. PR 템플릿 차단 용어를 "merge 금지"로 통일 (승인 불가, 승인 및 병합 금지 표현 제거). 헌법 의미 변경 없음. |
| 2026-03-21 | ALL | OPS-GATE-003 | PR Merge 강제 검문 규칙 문서화 (.github/MERGE_RULES.md). Merge Blocker 7조건, Approve 6조건, Close/Reopen 규칙, Exception 규칙, Post-Merge 규칙 정의. 헌법 의미 변경 없음. |
| 2026-03-21 | ALL | OPS-BASELINE | 운영 기준선 확정. PR #2(main<-master, baseline 도입) 병합 후 PR #3(master<-dedup/wave-2-clean, DEDUP R-1~R-5 12파일) 병합 완료. main=RC1 baseline, master=RC1+DEDUP 최종본. verify PASS(BLOCKER 0 / MAJOR 0, 25파일, 1865줄). dedup 브랜치 전량 삭제. |
| 2026-03-21 | DOC-L3-SPRINT-4A | DEDUP-R3 | Gate 이름/Mandatory 개별 열거를 DOC-L2-EXT-API-GOV §4.2, §5 참조로 전환 |
| 2026-03-21 | DOC-L3-SPRINT-4B | DEDUP-R3 | Gate 이름/Mandatory 개별 열거를 DOC-L2-EXT-API-GOV §4.3, §5 참조로 전환 |
| 2026-03-21 | DOC-L3-SPRINT-* | DEDUP-R4 | 전 Sprint §5에 Mandatory SSOT 참조 각주 추가 (DOC-L2-EXT-API-GOV §6) |
| 2026-03-21 | DOC-L3-RUNBOOK | DEDUP-R5 | SecurityState/U/E 상태 정의를 SSOT 참조로 전환, 운영자 조치만 유지 |
| 2026-03-21 | DOC-L3-SPRINT-2 | DEDUP-R1 | 상태 경로 열거를 DOC-L2-EXT-API-GOV §2 참조로 전환 |
| 2026-03-21 | DOC-L3-SPRINT-2 | DEDUP-R2 | 10-check 순서 열거를 DOC-L2-EXT-API-GOV §3 참조로 전환 |
| 2026-03-21 | ALL | BASELINE | v5.4-RC1 승인 후보본 봉인 (BLOCKER 0 / MAJOR 0 / C-1,C-2 해소) |
| 2026-03-21 | DOC-L2-EXT-API-GOV | FIX-C2 | Recovery Loop 면제 수 8개->10개 정정 (열거 목록과 일치) |
| 2026-03-21 | DOC-L3-SPRINT-2 | FIX-C1 | 제목 21상태->22상태, 상태 분류 독립 선언 제거 후 SSOT 참조로 전환 |
| 2026-03-21 | DOC-L4-COND-DISASTER-RECOVERY | CREATED | 재해 복구 조건부 잠금 문서 생성 |
| 2026-03-21 | DOC-L4-COND-REGULATORY | CREATED | 규제 대응 조건부 잠금 문서 생성 |
| 2026-03-21 | DOC-L4-COND-MODEL-UPGRADE | CREATED | 모델 업그레이드 조건부 잠금 문서 생성 |
| 2026-03-21 | DOC-L4-COND-EXTERNAL-DATA | CREATED | 외부 데이터 조건부 잠금 문서 생성 |
| 2026-03-21 | DOC-L4-COND-CROSS-STRATEGY | CREATED | 교차 전략 조건부 잠금 문서 생성 |
| 2026-03-21 | DOC-L4-COND-LIVE-TRADING | CREATED | 실거래 전환 조건부 잠금 문서 생성 |
| 2026-03-21 | DOC-L4-COND-MULTI-EXCHANGE | CREATED | 다중 거래소 조건부 잠금 문서 생성 |
| 2026-03-21 | DOC-L3-RUNBOOK | CREATED | 운영자 대응 절차서 생성 |
| 2026-03-21 | DOC-L3-SPRINT-7A | CREATED | Sprint 7a 확장 플레이스홀더 생성 |
| 2026-03-21 | DOC-L3-SPRINT-6 | CREATED | Sprint 6 자가개선 제한 축 생성 |
| 2026-03-21 | DOC-L3-SPRINT-6-GATE | CREATED | Sprint 6-gate 개선 자격 축 생성 |
| 2026-03-21 | DOC-L3-SPRINT-5 | CREATED | Sprint 5 차단 축 생성 |
| 2026-03-21 | DOC-L3-SPRINT-4B | CREATED | Sprint 4b Active Gate 생성 |
| 2026-03-21 | DOC-L3-SPRINT-4A | CREATED | Sprint 4a Shadow Gate 생성 |
| 2026-03-21 | DOC-L3-SPRINT-3B2 | CREATED | Sprint 3b2 ForbiddenLedger 생성 |
| 2026-03-21 | DOC-L3-SPRINT-3B1 | CREATED | Sprint 3b1 상태 분리 축 생성 |
| 2026-03-21 | DOC-L3-SPRINT-3A | CREATED | Sprint 3a Judgement 축 생성 |
| 2026-03-21 | DOC-L3-SPRINT-2 | CREATED | Sprint 2 WorkState 21상태 머신 생성 |
| 2026-03-21 | DOC-L3-SPRINT-1 | CREATED | Sprint 1 B1/Doctrine/Security 기초 생성 |
| 2026-03-21 | DOC-L2-RSG | CREATED | Runtime Stabilization Gate 스펙 생성 |
| 2026-03-21 | DOC-L2-INVARIANT-LENS | CREATED | Invariant Lens 정책 스펙 생성 (v5.4 통합) |
| 2026-03-21 | DOC-L2-EXT-API-GOV | CREATED | 외부 실행/API 거버넌스 정책 생성 |
| 2026-03-21 | DOC-L2-SPRINT-PLAN | CREATED | Sprint 계획 및 순서 정책 생성 |
| 2026-03-21 | DOC-L5-CHANGELOG | CREATED | 변경 이력 문서 생성 (APPEND_ONLY) |
| 2026-03-21 | DOC-L1-CONSTITUTION | CREATED | K-Dexter AOS 헌법 v5.4 초판 생성 |
