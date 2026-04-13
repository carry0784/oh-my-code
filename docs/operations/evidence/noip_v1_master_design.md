# NOIP v1 — Narrative-OrderFlow Injection Pack 마스터 설계서

**작성일:** 2026-04-09
**모듈명:** `Narrative-OrderFlow Injection Pack (NOIP) v1`
**성격:** 기존 O-I-D-E-L-E-C 골격 안 주입형 운영 모듈
**상태:** DESIGN_LOCKED (구현 미착수)

---

## 정의

기존 Observation~Constitution 고정 골격 안에,
유동성 sweep / 흡수 / 수용-거부 / 서사 정렬성을 계량화하여
진입 판단의 질을 높이고 추격/오판/이벤트 충돌을 줄이는 주입형 운영 모듈.

## 주입 위치

| 계층 | 역할 |
|------|------|
| Observation | 유동성/체결/뉴스 이벤트 수집 (1차 핵심) |
| Interpretation | 흡수/고갈/수용/거부/충돌 점수화 (2차 핵심) |
| Decision | 진입 허용/차단/보류 판정 (3차 보조) |
| Execution | 추격 억제, 마찰비용 통제 (4차 제한) |
| Learning | setup별 기대값 누적 (폐루프) |
| Evolution | 임계값/weight 제한 조정 (폐루프) |
| Constitution | 골격/헌법 잠금 (최상위) |

## 금지영역

- 의도 추정 금지 ("기관이 일부러 털었다" 직접 규칙화 금지)
- 눈대중 패턴 금지
- 단일 지표 확정 금지
- 시장 무차별 이식 금지
- 사후 해석 자동 승인 금지

## 헌법 10개 조항

1. 자동/자율/자가진화 원칙 유지 (구조 파괴 금지)
2. 골격 고정 유지
3. 단일 신호 진입 금지
4. 설명 가능성 의무
5. 데이터 품질 fail → fail-closed
6. shadow → paper → live 순차 강제
7. 의도 추정 금지
8. 시장 간 무검증 이식 금지
9. 진화 변경은 receipt/audit 대상
10. 실행보다 차단 우선

## 실행 5단계

1. Observation Shadow
2. Interpretation Shadow
3. Decision Paper
4. Execution Controlled Live
5. Learning/Evolution Enable

## 시장 적용 순서

1. 바이낸스/비트겟 선물
2. 미국주식 지수/대형주
3. 한국주식 지수/대형주
4. 중소형/테마 종목 (마지막)

## 선택형 보강안

- Counter-Scenario Ledger
- Narrative Silence Rule
- Setup Expiry Clock

---

**상세 설계는 3종 운영 명세서 참조:**
- `noip_v1_observation_field_dictionary.md`
- `noip_v1_interpretation_scoring_spec.md`
- `noip_v1_decision_state_transition_spec.md`
