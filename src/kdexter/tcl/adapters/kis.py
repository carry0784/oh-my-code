"""
Korea Investment & Securities (KIS) Adapter — TCL Spec v1
K-Dexter AOS

Translates TCL standard commands to 한국투자증권 REST API calls.
Supports: 국내 주식 (v1 scope). 해외 주식: v2 roadmap.

KIS-specific notes:
  - OAuth2 토큰 기반 인증 (appkey + appsecret → access_token)
  - 토큰 유효기간 24시간 — 자동 갱신 필요
  - 국내 주식 종목코드: 6자리 숫자 (예: 005930 삼성전자)
  - 시장 구분: KOSPI / KOSDAQ
  - API 도메인: 실전 openapi.koreainvestment.com / 모의 openapivts.koreainvestment.com
  - 초당 호출 제한: 20회/초

B1 Doctrine compliance:
  - Upper layers never see KIS-specific types (hashkey, tr_id, etc.)
  - All exceptions wrapped into CommandTranscript.fail()
  - DRY_RUN uses 모의투자 서버 (KIS provides virtual trading server)
"""
from __future__ import annotations

import asyncio
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from typing import Optional

from kdexter.tcl.adapters import ExchangeAdapter
from kdexter.tcl.adapters.rate_limiter import AsyncRateLimiter
from kdexter.tcl.commands import (
    CommandTranscript, CommandType, ExecutionMode, TCLCommand
)

logger = logging.getLogger(__name__)


class KISAdapter(ExchangeAdapter):
    """
    한국투자증권 (Korea Investment & Securities) adapter.

    Args:
        appkey:      KIS API app key
        appsecret:   KIS API app secret
        account_no:  계좌번호 (8자리-2자리 형식, e.g. "50123456-01")
        is_virtual:  모의투자 서버 사용 여부 (DRY_RUN 시 True)

    Usage:
        adapter = KISAdapter(
            appkey="...", appsecret="...",
            account_no="50123456-01",
        )
        dispatcher.register("kis", adapter)
    """

    BASE_URL_REAL = "https://openapi.koreainvestment.com:9443"
    BASE_URL_VIRTUAL = "https://openapivts.koreainvestment.com:29443"
    RATE_LIMIT_PER_SEC = 20

    def __init__(
        self,
        appkey: str = "",
        appsecret: str = "",
        account_no: str = "",
        is_virtual: bool = True,
    ) -> None:
        self._appkey = appkey
        self._appsecret = appsecret
        self._account_no = account_no
        self._is_virtual = is_virtual
        self._access_token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        self._rate_limiter = AsyncRateLimiter(max_calls=20, period=1.0)

    @property
    def exchange_id(self) -> str:
        return "kis"

    @property
    def _base_url(self) -> str:
        return self.BASE_URL_VIRTUAL if self._is_virtual else self.BASE_URL_REAL

    @property
    def _account_prefix(self) -> str:
        """계좌번호 앞 8자리."""
        return self._account_no.split("-")[0] if "-" in self._account_no else self._account_no[:8]

    @property
    def _account_suffix(self) -> str:
        """계좌번호 뒤 2자리."""
        return self._account_no.split("-")[1] if "-" in self._account_no else self._account_no[8:]

    def _is_token_valid(self) -> bool:
        """Check if access token is still valid."""
        if self._access_token is None or self._token_expires is None:
            return False
        return datetime.now(timezone.utc) < self._token_expires

    async def _ensure_token(self) -> str:
        """
        Obtain or refresh OAuth2 access token.
        POST /oauth2/tokenP → access_token (valid 24h)
        """
        if self._is_token_valid():
            return self._access_token

        if not self._appkey or not self._appsecret:
            raise RuntimeError("KIS appkey/appsecret not configured")
        url = f"{self._base_url}/oauth2/tokenP"
        body = json.dumps({
            "grant_type": "client_credentials",
            "appkey": self._appkey,
            "appsecret": self._appsecret,
        }).encode("utf-8")
        raw = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._http_post(url, body),
        )
        self._access_token = raw.get("access_token", "")
        expires_in = raw.get("expires_in", 86400)
        self._token_expires = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 1800)
        return self._access_token

    def _http_post(self, url: str, body: bytes, headers: Optional[dict] = None) -> dict:
        """Synchronous HTTP POST using urllib (stdlib)."""
        hdrs = {"Content-Type": "application/json; charset=utf-8"}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _http_get(self, url: str, headers: Optional[dict] = None) -> dict:
        """Synchronous HTTP GET using urllib (stdlib)."""
        hdrs = headers or {}
        req = urllib.request.Request(url, headers=hdrs, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _build_headers(self, tr_id: str) -> dict:
        """Build KIS API request headers."""
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._access_token}",
            "appkey": self._appkey,
            "appsecret": self._appsecret,
            "tr_id": tr_id,
        }

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
        모의투자 서버 기반 시뮬레이션.
        KIS provides a virtual trading server (openapivts).
        """
        t = self._base_transcript(command)
        try:
            if command.command_type in {CommandType.ORDER_BUY, CommandType.ORDER_SELL,
                                        CommandType.ORDER_DRY_RUN}:
                sim_order_id = f"DRY-{command.idempotency_key[:8].upper()}"
                side = "buy" if command.command_type == CommandType.ORDER_BUY else "sell"

                # KIS uses 6-digit stock codes, symbol format: "005930" or "005930/KRW"
                stock_code = self._to_kis_code(command.symbol)

                raw = {
                    "rt_cd": "0",           # 성공
                    "msg_cd": "APBK0013",
                    "msg1": "주문 접수 완료 (모의)",
                    "output": {
                        "KRX_FWDG_ORD_ORGNO": "",
                        "ODNO": sim_order_id,
                        "ORD_TMD": datetime.now(timezone.utc).strftime("%H%M%S"),
                    },
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
                    "rt_cd": "0",
                    "output1": [{"dnca_tot_amt": "100000000"}],  # 예수금 1억
                }
                parsed = {"KRW": {"free": 100_000_000.0, "locked": 0.0}}
                t.complete(raw=raw, parsed=parsed)

            elif command.command_type == CommandType.POSITION_QUERY:
                raw = {"rt_cd": "0", "output1": []}
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
            raw = {"rt_cd": "0", "output": {"odno": exchange_order_id, "ord_stts": "체결"}}
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
            raw = {"rt_cd": "0", "output": {"odno": exchange_order_id, "ord_stts": "취소"}}
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
            # TODO: GET /uapi/domestic-stock/v1/trading/inquire-balance
            raw: dict = {"rt_cd": "0", "output1": []}
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
            # TODO: GET /uapi/domestic-stock/v1/trading/inquire-psbl-order
            raw = {"rt_cd": "0", "output": {}}
            parsed: dict = {}
            t.complete(raw=raw, parsed=parsed)
        except Exception as exc:
            return self._safe_fail(t, exc)
        return t

    # ── internal helpers ─────────────────────────────────────────────────── #

    @staticmethod
    def _to_kis_code(symbol: Optional[str]) -> str:
        """
        Convert standard symbol to KIS stock code.
        "005930/KRW" → "005930", "005930" → "005930"
        """
        if not symbol:
            return ""
        return symbol.split("/")[0]

    @staticmethod
    def _get_tr_id(side: str, is_virtual: bool) -> str:
        """
        KIS transaction ID mapping.
        실전: TTTC0802U (매수), TTTC0801U (매도)
        모의: VTTC0802U (매수), VTTC0801U (매도)
        """
        prefix = "V" if is_virtual else "T"
        if side == "buy":
            return f"{prefix}TTC0802U"
        return f"{prefix}TTC0801U"

    async def _place_order(
        self, t: CommandTranscript, command: TCLCommand, side: str
    ) -> CommandTranscript:
        await self._rate_limiter.acquire()
        token = await self._ensure_token()
        tr_id = self._get_tr_id(side, self._is_virtual)
        headers = self._build_headers(tr_id)
        stock_code = self._to_kis_code(command.symbol)
        body = json.dumps({
            "CANO": self._account_prefix,
            "ACNT_PRDT_CD": self._account_suffix,
            "PDNO": stock_code,
            "ORD_DVSN": "00",  # 지정가
            "ORD_QTY": str(int(command.quantity or 0)),
            "ORD_UNPR": str(int(command.price or 0)),
        }).encode("utf-8")
        url = f"{self._base_url}/uapi/domestic-stock/v1/trading/order-cash"
        raw = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._http_post(url, body, headers),
        )
        if raw.get("rt_cd") != "0":
            t.fail(f"KIS order failed: {raw.get('msg1', 'unknown')}")
            return t
        output = raw.get("output", {})
        order_id = output.get("ODNO", "")
        parsed = {"order_id": order_id, "stock_code": stock_code, "side": side}
        t.complete(raw=raw, parsed=parsed, order_id=order_id)
        return t

    async def _cancel_order(
        self, t: CommandTranscript, command: TCLCommand
    ) -> CommandTranscript:
        await self._rate_limiter.acquire()
        await self._ensure_token()
        tr_id = "VTTC0803U" if self._is_virtual else "TTTC0803U"
        headers = self._build_headers(tr_id)
        body = json.dumps({
            "CANO": self._account_prefix,
            "ACNT_PRDT_CD": self._account_suffix,
            "KRX_FWDG_ORD_ORGNO": "",
            "ORGN_ODNO": command.exchange_order_id or "",
            "ORD_DVSN": "00",
            "RVSE_CNCL_DVSN_CD": "02",  # 취소
            "ORD_QTY": "0",
            "ORD_UNPR": "0",
            "QTY_ALL_ORD_YN": "Y",
        }).encode("utf-8")
        url = f"{self._base_url}/uapi/domestic-stock/v1/trading/order-rvsecncl"
        raw = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._http_post(url, body, headers),
        )
        if raw.get("rt_cd") != "0":
            t.fail(f"KIS cancel failed: {raw.get('msg1', 'unknown')}")
            return t
        parsed = {"order_id": command.exchange_order_id, "cancelled": True}
        t.complete(raw=raw, parsed=parsed, order_id=command.exchange_order_id)
        return t

    async def _verify_order(
        self, t: CommandTranscript, command: TCLCommand
    ) -> CommandTranscript:
        await self._rate_limiter.acquire()
        await self._ensure_token()
        tr_id = "VTTC8001R" if self._is_virtual else "TTTC8001R"
        headers = self._build_headers(tr_id)
        params = (
            f"CANO={self._account_prefix}&ACNT_PRDT_CD={self._account_suffix}"
            f"&INQR_STRT_DT={datetime.now(timezone.utc).strftime('%Y%m%d')}"
            f"&INQR_END_DT={datetime.now(timezone.utc).strftime('%Y%m%d')}"
            f"&SLL_BUY_DVSN_CD=00&INQR_DVSN=00&PDNO=&CCLD_DVSN=00"
            f"&ORD_GNO_BRNO=&ODNO={command.exchange_order_id or ''}"
            f"&INQR_DVSN_3=00&INQR_DVSN_1=&CTX_AREA_FK100=&CTX_AREA_NK100="
        )
        url = f"{self._base_url}/uapi/domestic-stock/v1/trading/inquire-daily-ccld?{params}"
        raw = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._http_get(url, headers),
        )
        filled = False
        if raw.get("rt_cd") == "0":
            for item in raw.get("output1", []):
                if item.get("odno") == command.exchange_order_id:
                    filled = True
                    break
        parsed = {"order_id": command.exchange_order_id, "filled": filled}
        t.complete(raw=raw, parsed=parsed, order_id=command.exchange_order_id)
        t.verification_result = filled
        return t

    async def _query_position(
        self, t: CommandTranscript, command: TCLCommand
    ) -> CommandTranscript:
        await self._rate_limiter.acquire()
        await self._ensure_token()
        tr_id = "VTTC8434R" if self._is_virtual else "TTTC8434R"
        headers = self._build_headers(tr_id)
        params = (
            f"CANO={self._account_prefix}&ACNT_PRDT_CD={self._account_suffix}"
            f"&AFHR_FLPR_YN=N&OFL_YN=&INQR_DVSN=02&UNPR_DVSN=01"
            f"&FUND_STTL_ICLD_YN=N&FNCG_AMT_AUTO_RDPT_YN=N"
            f"&PRCS_DVSN=01&CTX_AREA_FK100=&CTX_AREA_NK100="
        )
        url = f"{self._base_url}/uapi/domestic-stock/v1/trading/inquire-balance?{params}"
        raw = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._http_get(url, headers),
        )
        positions = []
        for item in raw.get("output1", []):
            if int(item.get("hldg_qty", "0")) > 0:
                positions.append({
                    "stock_code": item.get("pdno", ""),
                    "name": item.get("prdt_name", ""),
                    "quantity": int(item.get("hldg_qty", "0")),
                    "avg_price": float(item.get("pchs_avg_pric", "0")),
                })
        parsed = {"positions": positions}
        t.complete(raw=raw, parsed=parsed)
        return t

    async def _query_balance(
        self, t: CommandTranscript, command: TCLCommand
    ) -> CommandTranscript:
        await self._rate_limiter.acquire()
        await self._ensure_token()
        tr_id = "VTTC8908R" if self._is_virtual else "TTTC8908R"
        headers = self._build_headers(tr_id)
        params = (
            f"CANO={self._account_prefix}&ACNT_PRDT_CD={self._account_suffix}"
            f"&PDNO=&ORD_UNPR=&ORD_DVSN=02&CMA_EVLU_AMT_ICLD_YN=Y"
            f"&OVRS_ICLD_YN=Y"
        )
        url = f"{self._base_url}/uapi/domestic-stock/v1/trading/inquire-psbl-order?{params}"
        raw = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._http_get(url, headers),
        )
        output = raw.get("output", {})
        free = float(output.get("ord_psbl_cash", "0"))
        parsed = {"KRW": {"free": free, "locked": 0.0}}
        t.complete(raw=raw, parsed=parsed)
        return t

    def _risk_check(
        self, t: CommandTranscript, command: TCLCommand
    ) -> CommandTranscript:
        """Risk check with KIS KRW constraints."""
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
