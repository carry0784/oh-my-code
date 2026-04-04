# Exclusion Baseline (기준선 제외)

**문서 ID:** CONST-003
**작성일:** 2026-04-02 (v1.0) → 2026-04-04 (v2.0)
**Authority:** A (Decision Authority)
**CR:** CR-048 (K-Dexter Integrated Ops Server v2.3)
**Status:** **ACTIVE**
**변경 등급:** L0 (문서)

---

## 1. 해석 및 요약

### 목적

후보군(CORE/WATCH) 진입 이전에 차단하는 기준선.
Exclusion Baseline에 해당하는 종목은 **분류는 가능하지만 CORE/WATCH 상태 진입 불가. 항상 EXCLUDED.**
이 기준선은 SymbolScreener의 1단계(Exclusion Filter)와 Injection Gateway의 forbidden_sector 체크에서 강제된다.

### 종목 3상태 관리

| 상태 | 의미 | 진입 조건 | 허용 행위 |
|------|------|-----------|-----------|
| **CORE** | 적격 종목 풀, 실전 운영 대상 | 5단계 스크리닝 전부 PASS | 분석, 백테스트, Paper, Live |
| **WATCH** | 관찰 대상, 운영 미허용 | 일부 스크리닝 통과 또는 CORE 탈락 | 분석, 백테스트만 |
| **EXCLUDED** | 완전 제외 | Exclusion Baseline 해당 | 분류만 (운영/백테스트 불가) |

### 제외 대상 요약

| 시장 | 제외 대상 | 수 |
|------|-----------|:--:|
| 암호화폐 | Meme, 저유동성 신생 토큰, GameFi | 3 |
| 미국주식 | 고밸류 순수 SW, 약한 소비 베타 | 2 |
| 한국주식 | 유가 민감 업종, 저유동성 단기 테마주 | 2 |
| **합계** | | **7** |

---

## 2. 장점 / 단점

### 제외 기준선 채택 시 장점

| 장점 | 설명 |
|------|------|
| **위험 종목 원천 차단** | Meme, GameFi 등 극단적 변동성 자산이 후보군에 진입하지 않음 |
| **데이터 품질 보장** | 저유동성/신생 토큰을 제외하여 백테스트 데이터 신뢰성 확보 |
| **스크리닝 효율** | 명확한 EXCLUDED 종목을 사전 제거하여 5단계 스크리닝 연산량 감소 |
| **일관된 기준** | 감이 아닌 정량적 조건(시총, 거래량, PER 등)으로 판단 |
| **자동 강제** | SymbolScreener와 Injection Gateway에서 코드 레벨 차단 |

### 제외 기준선 채택 시 단점/리스크

| 단점 | 완화 방안 |
|------|-----------|
| 기회 손실 (Meme 급등 수익 놓침) | 설계 의도 — Meme의 기대값은 음수, 극단적 변동성은 리스크 관리 불가 |
| 경계 종목 판정 논란 | 정량 조건 명시 (시총 $50M, PER 80, 거래량 5억 등) + A 판정 경로 |
| 기준 변경 시 기존 EXCLUDED 재분류 필요 | 기준 변경은 A 승인 필수, 재분류 자동 실행 |

### 제외 기준선 미채택 시 리스크

| 리스크 | 심각도 |
|--------|--------|
| Meme 코인 급락으로 포트폴리오 치명적 손실 | **치명적** |
| 저유동성 종목 체결 실패/슬리피지 | **높음** |
| 데이터 부족 종목 백테스트 오류 | **높음** |
| GameFi 프로젝트 붕괴 | **높음** |

---

## 3. 이유 / 근거

### 근거 1 — 암호화폐 Meme 코인 제외

| 지표 | Meme 코인 특성 |
|------|----------------|
| 변동성 (일간) | 20~80% (일반 Layer-1: 3~10%) |
| 가격 동인 | 소셜 미디어 감성 (비합리적) |
| 기술적 분석 유효성 | 낮음 (소셜 이벤트 주도) |
| 리스크 관리 | SL/TP 무효화 가능 (급등락) |
| 기대값 | 장기적으로 음수 (생존자 편향) |

→ 기술적 분석 기반 전략에 부적합. 소셜 감성 기반 전략은 본 시스템 범위 외.

### 근거 2 — 저유동성 신생 토큰 제외

| 기준 | 값 | 이유 |
|------|-----|------|
| 시총 | < $50M | 단일 대규모 주문으로 가격 조작 가능 |
| 상장 기간 | < 6개월 | 백테스트 데이터 부족 (최소 500 bars 필요) |
| 거래량 | 불안정 | 체결 실패, 슬리피지 리스크 |

### 근거 3 — 미국주식 고밸류 순수 SW 제외

| 기준 | 값 | 이유 |
|------|-----|------|
| PER | > 80 | 실적이 아닌 성장 기대만으로 가격 유지 |
| 매출 프로필 | 성장만 의존, 이익 없음 | 금리 환경 변화에 극도로 민감 |
| 리스크 | 실적 미달 시 30~50% 급락 가능 | SL 무효화 가능 |

### 근거 4 — 한국주식 유가 민감 업종 제외

| 기준 | 대상 | 이유 |
|------|------|------|
| 업종 | 정유, 화학 | 유가(외부 변수)에 의한 가격 변동이 지배적 |
| 기술적 분석 | 유효성 낮음 | 유가 예측 없이 주가 예측 불가 |
| 대체 | 유가 ETF 직접 매매가 아닌 이상 비효율적 | 시스템 범위 외 |

### 근거 5 — 저유동성 단기 테마주 제외

| 기준 | 값 | 이유 |
|------|-----|------|
| 일거래량 | < 5억원 | 원하는 가격에 체결 불가 |
| 테마 수명 | 1~2주 | Candidate TTL(48h) 내에도 테마 소멸 가능 |
| 스프레드 | 넓음 | 진입/청산 비용 과다 |

---

## 4. 실현 / 구현 대책

### 4.1 제외 대상 상세

#### 암호화폐

| 제외 대상 | 조건 | 제외 사유 | 예시 |
|-----------|------|-----------|------|
| Meme 코인 | 섹터 = MEME | 극단적 변동성, 소셜 주도, 비합리적 가격 | DOGE, SHIB, PEPE, WIF, BONK |
| 저유동성 신생 토큰 | 시총 < $50M **또는** 상장 < 6개월 | 데이터 부족, 유동성 리스크 | (동적 판정) |
| GameFi | 섹터 = GAMEFI | NFT 의존, 유저 이탈, 생태계 붕괴 리스크 | AXS, IMX, SAND |

#### 미국주식

| 제외 대상 | 조건 | 제외 사유 | 예시 |
|-----------|------|-----------|------|
| 고밸류 순수 소프트웨어 | PER > 80 **and** 이익 미달 | 실적 전환 불확실, 금리 민감 | (동적 판정) |
| 약한 소비 베타 | 소비재 소형주 (시총 < $5B) | 경기 민감, 낮은 알파 | (동적 판정) |

#### 한국주식

| 제외 대상 | 조건 | 제외 사유 | 예시 |
|-----------|------|-----------|------|
| 유가 민감 업종 | 업종 = 정유, 화학 | 외부 변수(유가) 과다 | SK이노베이션, 한화솔루션 |
| 저유동성 단기 테마주 | 일거래량 < 5억원 | 체결 리스크, 스프레드 과다 | (동적 판정) |

### 4.2 허용 섹터

#### 암호화폐

| 섹터 | 코드 | 예시 | 비고 |
|------|------|------|------|
| Layer-1 | `LAYER1` | SOL, ETH, AVAX, SUI | ETH는 CR-046에 의해 운영 경로 금지 |
| DeFi | `DEFI` | UNI, AAVE, MKR | |
| AI | `AI` | FET, RENDER, TAO | |
| Infra | `INFRA` | LINK, GRT, FIL | |

> **주의:** ETH는 허용 섹터(Layer-1)에 속하지만, CR-046에 의해 **운영 경로(beat_schedule, paper session, operational import) 금지**. 분류/분석만 허용.

#### 미국주식 (KIS_US)

| 섹터 | 코드 | 테마 | 예시 |
|------|------|------|------|
| Tech | `TECH` | AI, Semiconductor, Cloud | NVDA, MSFT, AVGO |
| Healthcare | `HEALTHCARE` | 대형 바이오/의료기기 | LLY, UNH |
| Energy | `ENERGY` | 대형 전통+재생에너지 | XOM, NEE |
| Finance | `FINANCE` | 대형 금융 | JPM, V |

#### 한국주식

| 섹터 | 코드 | 예시 |
|------|------|------|
| 반도체 | `SEMICONDUCTOR` | 삼성전자, SK하이닉스 |
| IT | `IT` | 네이버, 카카오 |
| 금융 | `FINANCE_KR` | KB금융, 신한지주 |
| 자동차 | `AUTO` | 현대차, 기아 |

### 4.3 금지 섹터 코드

```python
FORBIDDEN_SECTORS = frozenset({
    "MEME",                        # 암호화폐 Meme
    "GAMEFI",                      # 암호화폐 GameFi
    "LOW_LIQUIDITY_NEW_TOKEN",     # 암호화폐 저유동성 신생
    "HIGH_VALUATION_PURE_SW",      # 미국주식 고밸류 순수 SW
    "WEAK_CONSUMER_BETA",          # 미국주식 약한 소비 베타
    "OIL_SENSITIVE",               # 한국주식 유가 민감
    "LOW_LIQUIDITY_THEME",         # 한국주식 저유동성 테마
})
```

### 4.4 5단계 스크리닝과의 연동

| 단계 | 내용 | Exclusion Baseline 관련 |
|------|------|------------------------|
| **1. Exclusion Filter** | Exclusion Baseline 해당 여부 | **직접 적용** → EXCLUDED |
| 2. Liquidity/Execution Quality | 거래량, 시총, 스프레드 | 간접 (저유동성 추가 필터) |
| 3. Technical Structure | ATR 1~20%, ADX>15, 200MA | 비관련 |
| 4. Fundamental/On-chain | PER<100/ROE>5%, TVL | 간접 (고밸류 추가 필터) |
| 5. Backtest Qualification | 500bars+, Sharpe>0 | 비관련 |

**5단계 전부 PASS → CORE, 일부 FAIL → WATCH, 1단계 FAIL → EXCLUDED**

### 4.5 허용/금지/승인 필요 정리

| 행위 | 허용 여부 | 비고 |
|------|:---------:|------|
| EXCLUDED 종목 분류/태깅 | ✅ | 데이터 수집은 가능 |
| 허용 섹터 종목 CORE 진입 | ✅ | 5단계 스크리닝 PASS 시 |
| EXCLUDED 종목 백테스트 | ⛔ | |
| EXCLUDED 종목 Paper/Live | ⛔ | |
| 금지 섹터 전략 등록 | ⛔ | Injection Gateway 차단 |
| 금지 섹터 목록 삭제 | ⛔ | 추가만 가능 |
| 금지 섹터 해제 | ⛔ | **A 승인 필수** |
| 제외 기준 임계값 변경 | ⚠️ | **A 승인 필수** |
| EXCLUDED → WATCH 수동 전환 | ⚠️ | **A 승인 필수** + 제외 사유 해소 증빙 |

---

## 5. 실행방법

### 구현 순서

| 단계 | 작업 | Phase | 등급 |
|------|------|-------|------|
| 1 | 본 기준선 A 승인 | Phase 0 | L0 |
| 2 | `FORBIDDEN_SECTORS` 상수 정의 | Phase 1 | L3 |
| 3 | Asset 모델에 sector/status 필드 추가 | Phase 2 | L3 |
| 4 | SymbolScreener 1단계 Exclusion Filter 구현 | Phase 3A | L3 |
| 5 | Injection Gateway에 forbidden_sector 체크 추가 | Phase 1 | L3 |
| 6 | Candidate TTL 만료 시 재심사 Exclusion 재검증 | Phase 3A | L3 |
| 7 | 통합 테스트 (EXCLUDED → CORE 진입 불가 검증) | Phase 3A | L1 |

### 제외 판정 흐름

```
종목 데이터 수신
    │
    ├─ 섹터 = FORBIDDEN_SECTORS? ── YES → EXCLUDED (즉시)
    │
    ├─ 시총 < $50M? ── YES → EXCLUDED (저유동성)
    │
    ├─ 상장 < 6개월? ── YES → EXCLUDED (데이터 부족)
    │
    ├─ PER > 80 & 이익 미달? ── YES → EXCLUDED (고밸류 SW)
    │
    ├─ 소비재 소형주? ── YES → EXCLUDED (약한 소비 베타)
    │
    ├─ 업종 = 정유/화학? ── YES → EXCLUDED (유가 민감)
    │
    ├─ 일거래량 < 5억원? ── YES → EXCLUDED (저유동성 테마)
    │
    └─ 모두 통과 → 2~5단계 스크리닝 진행
```

---

## 6. 더 좋은 아이디어

### 6.1 동적 제외 기준 (시장 환경 연동)

| 시장 환경 | 기준 조정 |
|-----------|-----------|
| HIGH_VOL / CRISIS | 시총 기준 $50M → $100M 상향 (유동성 더 엄격) |
| TRENDING_UP | 기준 유지 (기본) |
| RANGING | PER 기준 80 → 60 하향 (밸류에이션 더 엄격) |

→ 시장 환경별 기준 강화/완화로 적응형 제외.
→ 단, 기준 변경 자체는 A 승인 필요. 자동 적용 시 사전 승인된 범위 내에서만.

### 6.2 EXCLUDED → WATCH 승격 경로

현재 EXCLUDED는 영구 차단이지만, 종목 상황이 변하는 경우:
- 예: Meme 코인이 Layer-1으로 전환 (실질적 유틸리티 확보)
- 예: 저유동성 토큰이 시총 $50M 돌파

→ 자동 재분류 (6개월 주기 전수 재심사) + A 승인 경로.

### 6.3 Exclusion Reason 코드 표준화

```python
class ExclusionReason(str, Enum):
    MEME_SECTOR = "MEME_SECTOR"
    GAMEFI_SECTOR = "GAMEFI_SECTOR"
    LOW_MCAP = "LOW_MCAP"
    NEW_LISTING = "NEW_LISTING"
    HIGH_PER_NO_PROFIT = "HIGH_PER_NO_PROFIT"
    WEAK_CONSUMER = "WEAK_CONSUMER"
    OIL_SENSITIVE = "OIL_SENSITIVE"
    LOW_VOLUME_THEME = "LOW_VOLUME_THEME"
    MANUAL_EXCLUSION = "MANUAL_EXCLUSION"  # A 수동 제외
```

→ 각 EXCLUDED 종목에 정확한 제외 사유 코드를 기록하여 감사 추적 가능.

### 6.4 CR-046 ETH 특별 규칙 반영

ETH는 허용 섹터(Layer-1)에 속하지만 CR-046에 의해 운영 경로 금지.
이를 Exclusion Baseline과 별도로 관리하는 방법:

| 방법 | 장점 | 단점 |
|------|------|------|
| A. EXCLUDED로 분류 | 단순 | 기술적으로 ETH는 유효 종목 |
| B. CORE이되 operational_ban 플래그 | 정확 | 구현 복잡 |
| **C. WATCH로 분류 + 별도 금지 플래그** | 균형 | 추천 — 분석은 가능, 운영만 차단 |

→ 방법 C 권장. WATCH 상태 + `operational_ban: true` + `ban_reason: "CR-046"`.

---

## L3 구현 선행조건 체크리스트

Phase 2 / Phase 3A 구현(L3) 착수 전 아래 조건 **전부 충족** 필요:

| # | 조건 | 충족 여부 | 비고 |
|---|------|:---------:|------|
| 1 | 본 문서(제외 기준선) A 승인 | ⬜ | |
| 2 | injection_constitution.md A 승인 | ⬜ | |
| 3 | broker_matrix.md A 승인 | ⬜ | |
| 4 | Phase 1 설계 카드 4종 A 승인 | ⬜ | Asset 모델 의존 |
| 5 | Phase 2 Asset 모델 설계 카드 A 승인 | ⬜ | |
| 6 | Gate LOCKED 해제 또는 L3 개별 A 승인 | ⬜ | 현재 Gate LOCKED |
| 7 | 전체 회귀 테스트 PASS | ⬜ | |
| 8 | baseline-check 6/6 PASS | ⬜ | |

**0/8 충족. 구현 착수 불가.**

---

```
Exclusion Baseline v2.0
Authority: A
Date: 2026-04-04
CR: CR-048
```
