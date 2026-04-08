# CR-046 SOL C1-B — 24-Bar OHLCV 재현 검증 결과

**상태:** SEALED
**일시:** 2026-04-08
**근거 등급:** observed_from_replay

---

## 표본 경계 정의 (26-bar denominator 봉인)

Stage B receipt는 **24 bars** (04-07 13:50:17 ~ 04-08 13:50:17 UTC, beat dispatch 기준).
C1-B replay는 **26 bars** (04-07 13:00 ~ 04-08 14:00 UTC, OHLCV bar 경계 기준).

차이 원인:
- **receipt 기준:** beat이 매시 `:50:17`에 dispatch → OHLCV의 직전 closed bar를 사용. receipt의 bar_ts는 closed bar의 open timestamp.
- **replay 기준:** exchange에서 OHLCV를 bar 경계(정각)로 조회. replay 윈도우를 `13:00 ~ 14:00`로 설정하여 baseline 전후 1 bar를 포함. 이는 지표 계산의 연속성 검증을 위한 의도적 확장.
- **warmup:** 지표 계산에 필요한 lookback(200 bars)은 전체 172 bars fetch에 포함. 26-bar 윈도우 내부의 지표값은 충분한 history를 기반으로 계산됨.

결론: **receipt 24 bars ⊂ replay 26 bars**. 추가 2 bars는 경계 bar이며, 핵심 분석 결과에 영향 없음. 이후 비교 시 receipt 기준 24 bars를 canonical denominator로 사용한다.

---

## 검증 방법

1. Binance testnet에서 SOL/USDT 1H OHLCV 172 bars 재요청
2. `calc_smc_pure_causal()` 및 `calc_wavetrend()` 함수에 직접 투입
3. Replay 윈도우 (04-07 13:00 ~ 04-08 14:00 UTC, 26 bars) 내 각 bar의 smc_sig, wt_sig, smc_trend, wt1, wt2 원시값 기록

---

## 핵심 결과

### 병목 분포

| 코드 | 비율 | 의미 |
|------|------|------|
| **SMC_ZERO** | **25/26 (96.2%)** | SMC가 거의 모든 bar에서 BOS/CHoCH 돌파 미생성 |
| WT_ZERO | 22/26 (84.6%) | WT가 대부분 bar에서 cross 미발생 |
| BOTH_ZERO | 21/26 (80.8%) | SMC와 WT 모두 0인 bar |
| DIRECTION_MISMATCH | 0/26 (0.0%) | 방향 불일치는 발생하지 않음 |
| CONSENSUS_PASS | 0/26 (0.0%) | 합의 달성한 bar 없음 |

### 1차 병목: **SMC가 주 병목** (96.2% ZERO)

SMC signal이 non-zero인 bar는 **1개뿐** (Bar 7, 04-07 19:00, smc_sig=+1, CHoCH/BOS bullish). 그러나 해당 bar에서 WT가 0이었으므로 consensus 실패.

### 2차 병목: WT cross도 희소 (84.6% ZERO)

WT signal이 non-zero인 bar는 **4개**:
- Bar 5 (04-07 17:00): wt_sig=+1 (bullish cross, wt1=-41.72 > wt2=-50.02)
- Bar 17 (04-08 05:00): wt_sig=-1 (bearish cross, wt1=38.30 < wt2=38.64)
- Bar 21 (04-08 09:00): wt_sig=+1 (bullish cross, wt1=23.52 > wt2=19.55)
- Bar 25 (04-08 13:00): wt_sig=-1 (bearish cross, wt1=25.16 < wt2=25.23)

### 동시 발생: 0건

SMC non-zero (1건)와 WT non-zero (4건)가 같은 bar에서 발생한 적이 없다. 따라서 DIRECTION_MISMATCH도 0건.

---

## 시장 맥락 해석

### SMC 분석
- Bar 1~6: smc_trend=-1 (bearish). SOL이 78~80 구간에서 횡보.
- Bar 7: close=81.65가 swing high를 돌파 → smc_sig=+1, trend 전환 (bearish → bullish)
- Bar 8~26: smc_trend=+1 (bullish) 유지. **그러나 추가 돌파 이벤트 없음.** 이미 bullish trend에서 새로운 swing high를 돌파할 만큼의 추가 상승이 없었음 (81.65 → 85.71 상승 후 84~85 구간 횡보).

**SMC 병목 원인:** bearish→bullish 전환 후 즉시 횡보 진입. 새 swing high 형성 → 돌파가 발생하려면 85.71을 넘는 추가 상승이 필요했으나 발생하지 않음.

### WaveTrend 분석
- Bar 1~4: wt1 < wt2 (bearish zone, -48 ~ -52 수준)
- Bar 5: bullish cross (wt1=-41.72 > wt2=-50.02) — 상승 시작 신호
- Bar 6~16: wt1과 wt2가 같은 방향으로 상승 (cross 없음)
- Bar 17: bearish cross (wt1=38.30 < wt2=38.64, 극히 근접) — 상승 둔화 신호
- Bar 18~20: wt1 < wt2 유지
- Bar 21: bullish cross (wt1=23.52 > wt2=19.55)
- Bar 22~24: wt1 > wt2 유지
- Bar 25: bearish cross (wt1=25.16 < wt2=25.23, 극히 근접)

**WT 병목 원인:** cross 자체는 4회 발생했으나 SMC 돌파와 타이밍이 불일치.

---

## 진실표본 (raw values per bar)

| Bar# | Time (UTC) | Close | SMC_sig | WT_sig | SMC_trend | WT1 | WT2 | WT_dist | skip_codes |
|------|-----------|-------|---------|--------|-----------|-----|-----|---------|------------|
| 1 | 04-07 13:00 | 78.90 | 0 | 0 | -1 | -48.76 | -43.37 | 5.39 | SMC_ZERO,WT_ZERO |
| 2 | 04-07 14:00 | 78.63 | 0 | 0 | -1 | -52.24 | -47.21 | 5.03 | SMC_ZERO,WT_ZERO |
| 3 | 04-07 15:00 | 78.85 | 0 | 0 | -1 | -53.63 | -50.18 | 3.45 | SMC_ZERO,WT_ZERO |
| 4 | 04-07 16:00 | 78.90 | 0 | 0 | -1 | -52.48 | -51.78 | 0.70 | SMC_ZERO,WT_ZERO |
| 5 | 04-07 17:00 | 80.06 | 0 | +1 | -1 | -41.72 | -50.02 | 8.29 | SMC_ZERO |
| 6 | 04-07 18:00 | 79.90 | 0 | 0 | -1 | -32.83 | -45.17 | 12.34 | SMC_ZERO,WT_ZERO |
| 7 | 04-07 19:00 | 81.65 | **+1** | 0 | +1 | -17.50 | -36.13 | 18.63 | WT_ZERO |
| 8 | 04-07 20:00 | 81.92 | 0 | 0 | +1 | -3.34 | -23.85 | 20.51 | SMC_ZERO,WT_ZERO |
| 9 | 04-07 21:00 | 82.91 | 0 | 0 | +1 | 8.46 | -11.30 | 19.76 | SMC_ZERO,WT_ZERO |
| 10 | 04-07 22:00 | 85.14 | 0 | 0 | +1 | 20.67 | 2.07 | 18.59 | SMC_ZERO,WT_ZERO |
| 11 | 04-07 23:00 | 85.71 | 0 | 0 | +1 | 31.01 | 14.20 | 16.81 | SMC_ZERO,WT_ZERO |
| 12 | 04-08 00:00 | 84.72 | 0 | 0 | +1 | 35.37 | 23.88 | 11.49 | SMC_ZERO,WT_ZERO |
| 13 | 04-08 01:00 | 84.68 | 0 | 0 | +1 | 37.49 | 31.13 | 6.35 | SMC_ZERO,WT_ZERO |
| 14 | 04-08 02:00 | 84.58 | 0 | 0 | +1 | 38.58 | 35.61 | 2.97 | SMC_ZERO,WT_ZERO |
| 15 | 04-08 03:00 | 84.55 | 0 | 0 | +1 | 38.70 | 37.54 | 1.16 | SMC_ZERO,WT_ZERO |
| 16 | 04-08 04:00 | 84.55 | 0 | 0 | +1 | 38.97 | 38.44 | 0.53 | SMC_ZERO,WT_ZERO |
| 17 | 04-08 05:00 | 84.45 | 0 | -1 | +1 | 38.30 | 38.64 | 0.33 | SMC_ZERO |
| 18 | 04-08 06:00 | 84.54 | 0 | 0 | +1 | 14.91 | 32.72 | 17.81 | SMC_ZERO,WT_ZERO |
| 19 | 04-08 07:00 | 84.48 | 0 | 0 | +1 | 18.39 | 27.64 | 9.25 | SMC_ZERO,WT_ZERO |
| 20 | 04-08 08:00 | 84.85 | 0 | 0 | +1 | 21.37 | 23.25 | 1.87 | SMC_ZERO,WT_ZERO |
| 21 | 04-08 09:00 | 84.66 | 0 | +1 | +1 | 23.52 | 19.55 | 3.97 | SMC_ZERO |
| 22 | 04-08 10:00 | 84.51 | 0 | 0 | +1 | 24.78 | 22.02 | 2.77 | SMC_ZERO,WT_ZERO |
| 23 | 04-08 11:00 | 84.45 | 0 | 0 | +1 | 25.33 | 23.75 | 1.58 | SMC_ZERO,WT_ZERO |
| 24 | 04-08 12:00 | 84.58 | 0 | 0 | +1 | 25.65 | 24.82 | 0.83 | SMC_ZERO,WT_ZERO |
| 25 | 04-08 13:00 | 84.06 | 0 | -1 | +1 | 25.16 | 25.23 | 0.07 | SMC_ZERO |

---

## Near-Miss 분석

| 유형 | 건수 | Bar 목록 | 해석 |
|------|------|---------|------|
| **SMC_ONLY** (SMC non-zero, WT zero) | 1 | Bar 7 | SMC bullish 돌파 발생, WT는 아직 bearish zone에서 cross 전 |
| **WT_ONLY** (WT non-zero, SMC zero) | 4 | Bar 5, 17, 21, 25 | WT cross 발생, SMC는 추가 돌파 없음 |
| **DIR_MISMATCH** | 0 | — | 해당 없음 |

**Near-miss 총 5건 / 26 bars = 19.2%** — 시장이 "거의 조건 충족 상태"에 자주 도달했으나 타이밍 불일치로 consensus 미달성.

---

## 결론

1. **1차 병목은 SMC (96.2% ZERO)**. 24-bar 윈도우에서 BOS/CHoCH 돌파가 1회만 발생. bearish→bullish 전환 후 횡보 진입이 원인.
2. **2차 병목은 타이밍 불일치**. WT cross는 4회 발생했으나 SMC 돌파(1회)와 같은 bar에서 발생하지 않음.
3. **DIRECTION_MISMATCH는 0건**. 이 시나리오는 현재 시장에서 병목이 아님.
4. **코드 오류/지표 계산 오류 없음**. 전략이 설계대로 동작하고 있으며, 무신호는 시장 조건에 의한 정상 결과.
5. **C1-A 설계 반영:** `smc_sig_raw`와 `wt_sig_raw`가 가장 높은 진단 가치를 가짐. near-miss 3단계 분류(SMC_ONLY/WT_ONLY/DIR_MISMATCH)도 유효함이 실증됨.
