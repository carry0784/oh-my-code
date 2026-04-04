# CR-026+ 개시 판정 템플릿

---

## 요청 정보

```
요청일: YYYY-MM-DD
요청자: (A / B / C)
요청 제목: (한 줄)
요청 설명: (2-3줄)
영향 파일: (목록 또는 "문서만")
```

---

## 1단계: 개시 사유 판정 (7-check)

| # | 체크 항목 | YES/NO |
|---|---------|--------|
| 1 | 실제 운영 필요인가? | |
| 2 | 기준선(832/0/0, safety 7/7)에 영향이 있는가? | |
| 3 | 단순 메모/문서 수준이 아닌 정식 변경인가? | |
| 4 | 검증 표면 / board field / safety invariant에 닿는가? | |
| 5 | Mode 2 / Production gate 관련인가? | |
| 6 | 변경 후 회귀 검증 기준을 명확히 적을 수 있는가? | |
| 7 | 지금 당장 열어야 하는가? (다음 review cadence로 이월 불가?) | |

### 판정

```
핵심(1,2,6) 결과: ___/3 YES
고위험(4,5) 결과: ___/2 YES

판정: [ ] CR 개시  [ ] CR 미개시  [ ] 다음 review로 이월
사유: (한 줄)
```

---

## 2단계: 사유 분류

| 유형 | 해당 여부 | 권장 Level/Category |
|------|---------|-------------------|
| (1) 운영 유지형 | [ ] | L1/A 또는 L1/B, 일부 L2/B |
| (2) 관찰/검증 보강형 | [ ] | 검증 표면 → default-to-C, board field → L3/C |
| (3) 운영 설정/인프라 조정형 | [ ] | L2/B, sealed 접촉 시 상향 |
| (4) 고위험 게이트 검토형 | [ ] | L3 이상, Category D 가능 |

```
선택 유형: ( )
Level: L_
Category: _
```

---

## 3단계: 금지선 확인

| 금지 항목 | 해당? |
|---------|------|
| 승인 없는 Mode 2 착수 | [ ] |
| 승인 없는 Production gate 착수 | [ ] |
| action_allowed 완화 | [ ] |
| prediction 생성/확장 | [ ] |
| write path 확장 | [ ] |
| safety invariant 완화 | [ ] |
| board sealed field 무승인 변경 | [ ] |

**위 항목 중 하나라도 해당 시: CR 개시 금지. A 승인 후 재검토.**

```
금지선 통과: [ ] YES  [ ] NO — 사유:
```

---

## 4단계: CR 등록

금지선 통과 + 개시 판정 YES인 경우에만 아래를 작성합니다.

```
CR-ID: CR-___
Date: YYYY-MM-DD
Requester: (A / B / C)
Description: (한 줄)
Category: (A / B / C / D)
Level: (L1 / L2 / L3)
Reviewer(s): (B / A+B / A+B+C)
회귀 검증: [ ] 832/0/0 필수  [ ] 권장  [ ] 불필요 (L1 문서)

제목 형식: CR-___ — [영역] [행위] Pack
```

---

## 경계 규칙 요약 (CR-022 + CR-025 확정)

| 변경 대상 | 기본 분류 |
|---------|---------|
| 문서만 수정 | L1/A |
| 테스트 추가 (단언 완화 없음) | L1/A 또는 L1/B |
| 검증 표면 (grep, governance check, red line tool) | default-to-C |
| board field 추가/삭제 | L3/C |
| safety invariant 변경 | L3/D |
| execution/write/prediction path | L3/D |
