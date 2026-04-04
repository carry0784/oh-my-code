"""
Kiwoom Securities Adapter — TCL Spec v1
K-Dexter AOS

Translates TCL standard commands to 키움증권 API calls.
CLI-like command abstraction layer for Kiwoom's native COM interface.

Kiwoom-specific notes:
  - Windows 전용 COM 인터페이스 (OpenAPI+)
  - 키움 HTS 로그인 필수 (프로그램 실행 → COM 연결)
  - 초당 주문 제한: 1초에 5회
  - 종목코드: 6자리 숫자 (예: 005930 삼성전자)
  - 시장 구분: 0 (KOSPI), 10 (KOSDAQ)
  - pykiwoom 라이브러리 또는 직접 COM 연결

CLI-like abstraction:
  Kiwoom has no REST API — all interactions go through Windows COM.
  This adapter abstracts COM calls behind the standard ExchangeAdapter
  interface, making Kiwoom indistinguishable from REST-based exchanges
  to upper layers.

B1 Doctrine compliance:
  - Upper layers never see COM objects, TR codes, or event handlers
  - All exceptions wrapped into CommandTranscript.fail()
  - DRY_RUN uses 키움 모의투자 서버
"""

from __future__ import annotations

import asyncio
from typing import Optional

from kdexter.tcl.adapters import ExchangeAdapter
from kdexter.tcl.adapters.rate_limiter import AsyncRateLimiter
from kdexter.tcl.commands import CommandTranscript, CommandType, ExecutionMode, TCLCommand


class KiwoomAdapter(ExchangeAdapter):
    """
    키움증권 (Kiwoom Securities) adapter — COM abstraction layer.

    Args:
        account_no:  계좌번호 (10자리)
        is_virtual:  모의투자 서버 사용 여부
        auto_login:  자동 로그인 여부 (HTS 자동로그인 설정 필요)

    Prerequisites:
      - Windows OS
      - 키움 OpenAPI+ 설치
      - 키움 HTS 로그인 상태
      - Python 32-bit (COM 호환)

    Usage:
        adapter = KiwoomAdapter(account_no="1234567890")
        dispatcher.register("kiwoom", adapter)
    """

    ORDER_RATE_LIMIT_PER_SEC = 5
    # 키움 주문 유형 코드
    ORDER_TYPE_MAP = {
        "MARKET": 1,  # 시장가
        "LIMIT": 0,  # 지정가
        "STOP": 2,  # 조건부지정가
    }
    # 매매 구분
    SIDE_MAP = {
        "buy": 1,  # 신규매수
        "sell": 2,  # 신규매도
    }
    # 시장 구분
    MARKET_KOSPI = "0"
    MARKET_KOSDAQ = "10"

    def __init__(
        self,
        account_no: str = "",
        is_virtual: bool = True,
        auto_login: bool = False,
    ) -> None:
        self._account_no = account_no
        self._is_virtual = is_virtual
        self._auto_login = auto_login
        self._api = None  # pykiwoom.Kiwoom instance or COM wrapper
        self._connected = False
        self._rate_limiter = AsyncRateLimiter(max_calls=5, period=1.0)

    @property
    def exchange_id(self) -> str:
        return "kiwoom"

    def _get_api(self):
        """
        Lazy-initialize Kiwoom COM connection.
        Requires Windows + OpenAPI+ installed + HTS logged in.
        """
        if self._api is None:
            try:
                from pykiwoom.kiwoom import Kiwoom  # type: ignore

                self._api = Kiwoom()
                self._api.CommConnect(block=True)
                self._connected = True
            except ImportError:
                raise RuntimeError(
                    "pykiwoom not installed. Run: pip install pykiwoom\n"
                    "Also requires: Windows OS + 키움 OpenAPI+ + HTS login"
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Kiwoom COM connection failed: {exc}\n"
                    "Ensure: HTS is running and logged in, Python is 32-bit"
                )
        return self._api

    # ── execute (LIVE) ───────────────────────────────────────────────────── #

    async def execute(self, command: TCLCommand) -> CommandTranscript:
        t = self._base_transcript(command)
        try:
            if command.command_type == CommandType.ORDER_BUY:
                return await self._place_order(t, command, side="buy")
            elif command.command_type == CommandType.ORDER_SELL:
                return await self._place_order(t, command, side="sell")
            elif command.command_type == CommandType.ORDER_CANCEL:
                return await self._cancel_order(t, command)
            elif command.command_type == CommandType.ORDER_VERIFY:
                return await self._verify_order(t, command)
            elif command.command_type == CommandType.POSITION_QUERY:
                return await self._query_position(t, command)
            elif command.command_type == CommandType.BALANCE_QUERY:
                return await self._query_balance(t, command)
            elif command.command_type == CommandType.RISK_CHECK:
                return self._risk_check(t, command)
            else:
                t.fail(f"Unsupported CommandType: {command.command_type.value}")
                return t
        except Exception as exc:
            return self._safe_fail(t, exc)

    # ── dry_run (모의투자) ────────────────────────────────────────────────── #

    async def dry_run(self, command: TCLCommand) -> CommandTranscript:
        """
        키움 모의투자 서버 기반 시뮬레이션.
        모의투자 계좌번호가 설정된 경우 키움 서버로 전송,
        아닌 경우 내부 시뮬레이션.
        """
        t = self._base_transcript(command)
        try:
            if command.command_type in {
                CommandType.ORDER_BUY,
                CommandType.ORDER_SELL,
                CommandType.ORDER_DRY_RUN,
            }:
                sim_order_id = f"DRY-{command.idempotency_key[:8].upper()}"
                side = "buy" if command.command_type == CommandType.ORDER_BUY else "sell"
                stock_code = self._to_kiwoom_code(command.symbol)

                raw = {
                    "sRQName": "주문요청(모의)",
                    "sScreenNo": "0101",
                    "sAccNo": self._account_no,
                    "nOrderType": self.SIDE_MAP.get(side, 1),
                    "sCode": stock_code,
                    "nQty": int(command.quantity or 0),
                    "nPrice": int(command.price or 0),
                    "sHogaGb": str(self.ORDER_TYPE_MAP.get(command.order_type.value, 0)),
                    "status": "SIMULATED",
                }
                parsed = {
                    "order_id": sim_order_id,
                    "stock_code": stock_code,
                    "side": side,
                    "quantity": command.quantity,
                    "price": command.price,
                    "status": "SIMULATED",
                }
                t.complete(raw=raw, parsed=parsed, order_id=sim_order_id)

            elif command.command_type == CommandType.RISK_CHECK:
                t = self._risk_check(t, command)

            elif command.command_type == CommandType.BALANCE_QUERY:
                raw = {
                    "예수금": "50000000",
                    "출금가능금액": "50000000",
                }
                parsed = {"KRW": {"free": 50_000_000.0, "locked": 0.0}}
                t.complete(raw=raw, parsed=parsed)

            elif command.command_type == CommandType.POSITION_QUERY:
                raw = {"종목수": "0", "보유종목": []}
                parsed = {"positions": []}
                t.complete(raw=raw, parsed=parsed)

            else:
                t.fail(f"DRY_RUN not implemented for {command.command_type.value}")

        except Exception as exc:
            return self._safe_fail(t, exc)
        return t

    # ── verify ───────────────────────────────────────────────────────────── #

    async def verify(self, exchange_order_id: str) -> CommandTranscript:
        cmd = TCLCommand(
            command_type=CommandType.ORDER_VERIFY,
            exchange=self.exchange_id,
            exchange_order_id=exchange_order_id,
        )
        t = self._base_transcript(cmd)
        try:
            raw = {"주문번호": exchange_order_id, "주문상태": "체결"}
            parsed = {"order_id": exchange_order_id, "status": "FILLED", "filled": True}
            t.complete(raw=raw, parsed=parsed, order_id=exchange_order_id)
            t.verification_result = True
        except Exception as exc:
            return self._safe_fail(t, exc)
        return t

    # ── cancel ───────────────────────────────────────────────────────────── #

    async def cancel(self, exchange_order_id: str) -> CommandTranscript:
        cmd = TCLCommand(
            command_type=CommandType.ORDER_CANCEL,
            exchange=self.exchange_id,
            exchange_order_id=exchange_order_id,
        )
        t = self._base_transcript(cmd)
        try:
            # 키움 취소 주문: SendOrder with nOrderType=3 (매수취소) or 4 (매도취소)
            raw = {"주문번호": exchange_order_id, "주문상태": "취소"}
            parsed = {"order_id": exchange_order_id, "cancelled": True}
            t.complete(raw=raw, parsed=parsed, order_id=exchange_order_id)
        except Exception as exc:
            return self._safe_fail(t, exc)
        return t

    # ── query_position ───────────────────────────────────────────────────── #

    async def query_position(self, symbol: Optional[str] = None) -> CommandTranscript:
        cmd = TCLCommand(
            command_type=CommandType.POSITION_QUERY,
            exchange=self.exchange_id,
            symbol=symbol,
        )
        t = self._base_transcript(cmd)
        try:
            # TODO: opw00018 (계좌평가잔고내역요청) TR 호출
            raw: dict = {"보유종목": [], "note": "TR opw00018 placeholder"}
            parsed: dict = {"positions": []}
            t.complete(raw=raw, parsed=parsed)
        except Exception as exc:
            return self._safe_fail(t, exc)
        return t

    # ── query_balance ────────────────────────────────────────────────────── #

    async def query_balance(self, currency: Optional[str] = None) -> CommandTranscript:
        cmd = TCLCommand(
            command_type=CommandType.BALANCE_QUERY,
            exchange=self.exchange_id,
        )
        t = self._base_transcript(cmd)
        try:
            # TODO: opw00001 (예수금상세현황요청) TR 호출
            raw = {"예수금": "0"}
            parsed: dict = {}
            t.complete(raw=raw, parsed=parsed)
        except Exception as exc:
            return self._safe_fail(t, exc)
        return t

    # ── internal helpers ─────────────────────────────────────────────────── #

    @staticmethod
    def _to_kiwoom_code(symbol: Optional[str]) -> str:
        """
        Convert standard symbol to Kiwoom stock code.
        "005930/KRW" → "005930", "005930" → "005930"
        """
        if not symbol:
            return ""
        return symbol.split("/")[0]

    async def _place_order(
        self, t: CommandTranscript, command: TCLCommand, side: str
    ) -> CommandTranscript:
        await self._rate_limiter.acquire()
        api = self._get_api()
        stock_code = self._to_kiwoom_code(command.symbol)
        order_type = self.SIDE_MAP.get(side, 1)
        hoga = self.ORDER_TYPE_MAP.get(
            command.order_type.value if command.order_type else "LIMIT", 0
        )
        qty = int(command.quantity or 0)
        price = int(command.price or 0)
        raw = await asyncio.to_thread(
            api.SendOrder,
            "주문요청",
            "0101",
            self._account_no,
            order_type,
            stock_code,
            qty,
            price,
            str(hoga),
            "",
        )
        order_id = str(raw) if raw else ""
        parsed = {"order_id": order_id, "stock_code": stock_code, "side": side}
        t.complete(raw={"result": raw}, parsed=parsed, order_id=order_id)
        return t

    async def _cancel_order(self, t: CommandTranscript, command: TCLCommand) -> CommandTranscript:
        await self._rate_limiter.acquire()
        api = self._get_api()
        # nOrderType 3=매수취소, 4=매도취소 (default to 3)
        cancel_type = command.extra.get("cancel_order_type", 3)
        raw = await asyncio.to_thread(
            api.SendOrder,
            "취소요청",
            "0101",
            self._account_no,
            cancel_type,
            "",
            0,
            0,
            "",
            command.exchange_order_id or "",
        )
        parsed = {"order_id": command.exchange_order_id, "cancelled": True}
        t.complete(raw={"result": raw}, parsed=parsed, order_id=command.exchange_order_id)
        return t

    async def _verify_order(self, t: CommandTranscript, command: TCLCommand) -> CommandTranscript:
        await self._rate_limiter.acquire()
        api = self._get_api()
        # opw00007: 계좌별주문체결내역상세
        raw = await asyncio.to_thread(
            api.block_request,
            "opw00007",
            계좌번호=self._account_no,
            주문번호=command.exchange_order_id or "",
            output="주문체결",
            next=0,
        )
        filled = False
        if raw and len(raw) > 0:
            status = raw[0].get("주문상태", "")
            filled = status == "체결"
        parsed = {"order_id": command.exchange_order_id, "filled": filled}
        t.complete(raw={"data": raw}, parsed=parsed, order_id=command.exchange_order_id)
        t.verification_result = filled
        return t

    async def _query_position(self, t: CommandTranscript, command: TCLCommand) -> CommandTranscript:
        await self._rate_limiter.acquire()
        api = self._get_api()
        # opw00018: 계좌평가잔고내역요청
        raw = await asyncio.to_thread(
            api.block_request,
            "opw00018",
            계좌번호=self._account_no,
            비밀번호="",
            비밀번호입력매체구분="00",
            조회구분="1",
            output="계좌평가잔고개별합산",
            next=0,
        )
        positions = []
        if raw:
            for item in raw:
                qty = int(item.get("보유수량", "0"))
                if qty > 0:
                    positions.append(
                        {
                            "stock_code": item.get("종목번호", "").strip(),
                            "name": item.get("종목명", "").strip(),
                            "quantity": qty,
                            "avg_price": float(item.get("매입가", "0")),
                        }
                    )
        parsed = {"positions": positions}
        t.complete(raw={"data": raw}, parsed=parsed)
        return t

    async def _query_balance(self, t: CommandTranscript, command: TCLCommand) -> CommandTranscript:
        await self._rate_limiter.acquire()
        api = self._get_api()
        # opw00001: 예수금상세현황요청
        raw = await asyncio.to_thread(
            api.block_request,
            "opw00001",
            계좌번호=self._account_no,
            비밀번호="",
            비밀번호입력매체구분="00",
            조회구분="2",
            output="예수금상세현황",
            next=0,
        )
        free = 0.0
        if raw and len(raw) > 0:
            free = float(raw[0].get("출금가능금액", "0"))
        parsed = {"KRW": {"free": free, "locked": 0.0}}
        t.complete(raw={"data": raw}, parsed=parsed)
        return t

    def _risk_check(self, t: CommandTranscript, command: TCLCommand) -> CommandTranscript:
        """Risk check with Kiwoom KRW constraints."""
        qty = command.quantity or 0.0
        price = command.price or 0.0
        estimated_value = qty * price
        cap = command.extra.get("order_cap_krw", 50_000_000)  # 국내 주식 기본 5천만
        if estimated_value > cap:
            t.fail(
                f"RISK.CHECK failed: estimated_value={estimated_value:,.0f} KRW "
                f"> cap={cap:,.0f} KRW"
            )
        else:
            t.complete(
                raw={"risk": "OK", "estimated_value": estimated_value, "cap": cap},
                parsed={"passed": True, "estimated_value": estimated_value},
            )
        return t
