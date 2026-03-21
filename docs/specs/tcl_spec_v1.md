# Trading Command Language (TCL) Specification — v1
**K-Dexter AOS | v4 Priority 5**

TCL은 상위 레이어(L6/L8)와 거래소 API 사이의 추상화 계층이다.
전략·거래소 교체 시 상위 로직 수정 없이 어댑터만 교체할 수 있도록 설계한다.

---

## 1. TCL 존재 이유

| 문제 | TCL 해결 방식 |
|------|--------------|
| 거래소별 API 완전히 상이 (Binance REST vs Kiwoom COM) | 어댑터 패턴으로 상위 레이어 격리 |
| 거래소 교체 시 전략 코드 수정 필요 | 표준 명령으로 추상화 — 어댑터만 교체 |
| 명령 재현(Replay) 불가 | CommandTranscript에 모든 명령 기록 |
| Sandbox/Live 분리 어려움 | mode 필드로 DRY_RUN/LIVE 구분 |
| 감사 로그 불일치 | 모든 명령에 idempotency_key + transcript 필수 |

**B1 교리 (Execution Interface Doctrine) 준수:**
- 거래 실행은 반드시 TCL 명령형 인터페이스를 통한다
- 상위 레이어는 직접 거래소 API를 호출하지 않는다
- 모든 명령은 replay 가능해야 한다
- 명령 결과는 Evidence Pack에 기록된다

---

## 2. 아키텍처 위치

```
L6 Parallel Agent
L8 Execution Cell
      │
      │  TCLCommand (표준 명령)
      ▼
 TCLDispatcher  ←  A 계층 인프라, L8 하위 컴포넌트
      │
      │  ExchangeAdapter.execute(command)
      ▼
 ExchangeAdapter (거래소별)
   ├─ BinanceAdapter    (ccxt)
   ├─ UpbitAdapter      (ccxt)
   ├─ BitgetAdapter     (ccxt)
   ├─ KiwoomAdapter     (COM/CLI 추상화)
   └─ KISAdapter        (한국투자증권 REST)
```

---

## 3. 표준 명령 목록

| CommandType | 설명 | 필수 파라미터 |
|------------|------|--------------|
| `ORDER.BUY` | 매수 주문 | symbol, quantity, order_type |
| `ORDER.SELL` | 매도 주문 | symbol, quantity, order_type |
| `ORDER.CANCEL` | 주문 취소 | exchange_order_id |
| `POSITION.QUERY` | 포지션 조회 | symbol (optional) |
| `BALANCE.QUERY` | 잔고 조회 | currency (optional) |
| `RISK.CHECK` | 리스크 한도 확인 | symbol, quantity, side |
| `ORDER.DRY_RUN` | 샌드박스 시뮬레이션 | symbol, quantity, order_type |
| `ORDER.VERIFY` | 체결 검증 | exchange_order_id |
| `ORDER.REPLAY` | 과거 주문 재현 | original_transcript_id |
| `ORDER.ROLLBACK` | 포지션 롤백 시도 | symbol, target_position |

---

## 4. 명령 실행 흐름

```
[상위 레이어]
     │
     │  TCLCommand(type=ORDER.BUY, symbol='BTC/KRW', ...)
     ▼
TCLDispatcher.dispatch(command)
     │
     ├─ [1] Idempotency check — duplicate key → 이전 transcript 반환
     ├─ [2] Mode check — DRY_RUN mode → ExchangeAdapter.dry_run()
     ├─ [3] RISK.CHECK 선행 (ORDER.BUY/SELL 시 자동 삽입)
     ├─ [4] ExchangeAdapter.execute(command)
     │          │
     │          ├─ raw_response 수신
     │          └─ parsed_response 생성
     ├─ [5] CommandTranscript 완성 + Evidence Pack 추가
     └─ [6] CommandTranscript 반환
```

---

## 5. CommandTranscript — 감사 필수 필드

모든 TCL 명령 실행은 CommandTranscript를 생성한다.
Evidence Bundle(M-07)에 반드시 포함되어야 한다.

| 필드 | 타입 | 설명 |
|------|------|------|
| `transcript_id` | str (UUID) | 고유 식별자 |
| `required_command` | str | 원본 명령 (그대로 기록) |
| `normalized_command` | str | 표준화된 명령 |
| `command_type` | CommandType | 명령 종류 |
| `exchange` | str | 대상 거래소 |
| `mode` | ExecutionMode | DRY_RUN / LIVE |
| `command_timestamp` | datetime | 명령 발행 시각 |
| `idempotency_key` | str (UUID) | 중복 실행 방지 키 (필수) |
| `raw_response` | dict | 거래소 원본 응답 |
| `parsed_response` | dict | 파싱된 응답 |
| `order_ack` | bool | 주문 접수 확인 |
| `exchange_order_id` | str | 거래소 주문 ID |
| `retry_count` | int | 재시도 횟수 |
| `verification_result` | bool | ORDER.VERIFY 결과 |
| `error` | str | 오류 메시지 (실패 시) |
| `completed_at` | datetime | 완료 시각 |

---

## 6. Idempotency 보장

동일 `idempotency_key`로 중복 호출 시:
- dispatcher가 기존 transcript를 반환 (재실행하지 않음)
- ORDER.DRY_RUN은 idempotency 적용 제외 (시뮬레이션은 반복 가능)
- 재시도(retry)는 새 idempotency_key 생성 금지 — 기존 key 재사용

---

## 7. Sandbox / Live 승격 구조

```
ExecutionMode.DRY_RUN → 어댑터가 시뮬레이션 실행 (실제 주문 없음)
ExecutionMode.LIVE    → 어댑터가 실제 주문 실행

승격 조건:
  Phase 4 FINAL_GO 완료 후만 LIVE 모드 허용
  DRY_RUN 결과와 LIVE 결과 비교 → Shadow Integrity Gate (G-07)
```

---

## 8. ExchangeAdapter 인터페이스

모든 어댑터가 구현해야 하는 추상 메서드:

```python
async def execute(command: TCLCommand) -> CommandTranscript
async def dry_run(command: TCLCommand) -> CommandTranscript
async def verify(exchange_order_id: str) -> CommandTranscript
async def cancel(exchange_order_id: str) -> CommandTranscript
async def query_position(symbol: Optional[str]) -> CommandTranscript
async def query_balance(currency: Optional[str]) -> CommandTranscript
```

---

## 9. 거래소별 어댑터 구현 노트

| 거래소 | 라이브러리 | 특이사항 |
|--------|-----------|---------|
| Binance | ccxt | REST + WebSocket, futures/spot 분리 필요 |
| Bitget | ccxt | REST + WebSocket, copy-trading 지원, passphrase 필수 |
| Upbit | ccxt | KRW 원화 페어, 초당 API 제한 있음 |
| 한국투자증권 (KIS) | 자체 REST API | OAuth2 토큰 갱신 필요, 모의투자 서버 별도 |
| 키움증권 (Kiwoom) | pykiwoom (COM) | Windows 전용 COM 인터페이스 — CLI 추상화 필수 |

---

## 10. v1 범위 및 v2 예정

**v1 범위 (이 문서):**
- 표준 명령 10개 정의
- CommandTranscript 구조 확정
- ExchangeAdapter 추상 인터페이스 확정
- TCLDispatcher 기본 흐름 구현
- BinanceAdapter 기본 구현 (spot)

**v2 예정:**
- WebSocket 기반 실시간 체결 스트림
- Order Book 쿼리 명령 (`ORDERBOOK.QUERY`)
- Kiwoom / KIS 어댑터 구현 완성
- 다중 거래소 분산 실행 (`ORDER.SPREAD`)
- Retry 정책 고도화 (지수 백오프)
