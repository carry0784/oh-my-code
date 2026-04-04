"""
Korea Investment & Securities (한국투자증권) Exchange Adapter
I-01: KIS 어댑터 추가

KIS는 CCXT 미지원이므로 KIS Open Trading API (REST) 기반 자체 구현.
국내 주식 현물 전용:
  - fetch_positions()는 보유종목 조회 API로 잔고 반환
  - liquidation_price, leverage는 해당 없음 (현물)
  - 원화(KRW) 기준 거래
"""

import httpx
from typing import Any

from exchanges.base import BaseExchange
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# KIS Open API base URLs
_KIS_BASE_REAL = "https://openapi.koreainvestment.com:9443"
_KIS_BASE_DEMO = "https://openapivts.koreainvestment.com:29443"


class KISExchange(BaseExchange):
    """
    한국투자증권 Open Trading API 어댑터.
    CCXT 미지원이므로 httpx 기반 REST 클라이언트 사용.
    """

    def __init__(self):
        super().__init__(settings.kis_app_key, settings.kis_app_secret)
        self._base_url = _KIS_BASE_DEMO if settings.kis_demo else _KIS_BASE_REAL
        self._account_no = settings.kis_account_no
        self._account_suffix = settings.kis_account_suffix
        self._token: str | None = None
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=30.0,
        )

    async def _ensure_token(self) -> str:
        """OAuth 토큰 발급/캐싱."""
        if self._token:
            return self._token
        try:
            resp = await self._client.post(
                "/oauth2/tokenP",
                json={
                    "grant_type": "client_credentials",
                    "appkey": self.api_key,
                    "appsecret": self.api_secret,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data.get("access_token", "")
            logger.info("KIS token acquired")
            return self._token
        except Exception as e:
            logger.error("KIS token acquisition failed", error=str(e))
            raise

    def _headers(self, token: str, tr_id: str) -> dict:
        """KIS API 공통 헤더."""
        return {
            "authorization": f"Bearer {token}",
            "appkey": self.api_key,
            "appsecret": self.api_secret,
            "tr_id": tr_id,
            "Content-Type": "application/json; charset=utf-8",
        }

    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
    ) -> dict[str, Any]:
        """국내 주식 주문 (매수/매도)."""
        token = await self._ensure_token()
        tr_id = "VTTC0802U" if side == "buy" else "VTTC0801U"
        if not settings.kis_demo:
            tr_id = "TTTC0802U" if side == "buy" else "TTTC0801U"
        try:
            resp = await self._client.post(
                "/uapi/domestic-stock/v1/trading/order-cash",
                headers=self._headers(token, tr_id),
                json={
                    "CANO": self._account_no,
                    "ACNT_PRDT_CD": self._account_suffix,
                    "PDNO": symbol,
                    "ORD_DVSN": "01" if order_type == "limit" else "00",
                    "ORD_QTY": str(int(quantity)),
                    "ORD_UNPR": str(int(price)) if price else "0",
                },
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info("KIS order created", symbol=symbol, side=side)
            return result
        except Exception as e:
            logger.error("KIS order failed", symbol=symbol, error=str(e))
            raise

    async def cancel_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        """주문 취소."""
        token = await self._ensure_token()
        tr_id = "VTTC0803U" if settings.kis_demo else "TTTC0803U"
        resp = await self._client.post(
            "/uapi/domestic-stock/v1/trading/order-rvsecncl",
            headers=self._headers(token, tr_id),
            json={
                "CANO": self._account_no,
                "ACNT_PRDT_CD": self._account_suffix,
                "KRX_FWDG_ORD_ORGNO": "",
                "ORGN_ODNO": order_id,
                "ORD_DVSN": "00",
                "RVSE_CNCL_DVSN_CD": "02",
                "ORD_QTY": "0",
                "ORD_UNPR": "0",
                "QTY_ALL_ORD_YN": "Y",
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def fetch_order(self, order_id: str, symbol: str) -> dict[str, Any]:
        """주문 조회 — KIS는 일별 주문 내역으로 조회."""
        token = await self._ensure_token()
        tr_id = "VTTC8001R" if settings.kis_demo else "TTTC8001R"
        resp = await self._client.get(
            "/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
            headers=self._headers(token, tr_id),
            params={
                "CANO": self._account_no,
                "ACNT_PRDT_CD": self._account_suffix,
                "INQR_STRT_DT": "",
                "INQR_END_DT": "",
                "SLL_BUY_DVSN_CD": "00",
                "INQR_DVSN": "00",
                "PDNO": symbol,
                "CCLD_DVSN": "00",
                "ORD_GNO_BRNO": "",
                "ODNO": order_id,
                "INQR_DVSN_3": "00",
                "INQR_DVSN_1": "",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def fetch_positions(self) -> list[dict[str, Any]]:
        """
        보유종목 조회.
        KIS API: /uapi/domestic-stock/v1/trading/inquire-balance
        반환: position-like dict list (BaseExchange 계약 준수)
        """
        token = await self._ensure_token()
        tr_id = "VTTC8434R" if settings.kis_demo else "TTTC8434R"
        try:
            resp = await self._client.get(
                "/uapi/domestic-stock/v1/trading/inquire-balance",
                headers=self._headers(token, tr_id),
                params={
                    "CANO": self._account_no,
                    "ACNT_PRDT_CD": self._account_suffix,
                    "AFHR_FLPR_YN": "N",
                    "OFL_YN": "",
                    "INQR_DVSN": "02",
                    "UNPR_DVSN": "01",
                    "FUND_STTL_ICLD_YN": "N",
                    "FNCG_AMT_AUTO_RDPT_YN": "N",
                    "PRCS_DVSN": "01",
                    "CTX_AREA_FK100": "",
                    "CTX_AREA_NK100": "",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            output = data.get("output1", [])
            positions = []
            for item in output:
                qty = int(item.get("hldg_qty", "0") or "0")
                if qty <= 0:
                    continue
                positions.append(
                    {
                        "symbol": item.get("pdno", ""),
                        "symbol_name": item.get("prdt_name", ""),
                        "contracts": qty,
                        "side": "long",  # 국내 주식 현물은 항상 long
                        "entryPrice": float(item.get("pchs_avg_pric", "0") or "0"),
                        "markPrice": float(item.get("prpr", "0") or "0"),
                        "unrealizedPnl": float(item.get("evlu_pfls_amt", "0") or "0"),
                        "profitRate": float(item.get("evlu_pfls_rt", "0") or "0"),
                        "evalAmount": float(item.get("evlu_amt", "0") or "0"),
                        "leverage": 1,
                        "liquidationPrice": None,  # 현물은 청산가 없음
                    }
                )
            return positions
        except Exception as e:
            logger.error("KIS fetch_positions failed", error=str(e))
            raise

    async def fetch_balance(self) -> dict[str, Any]:
        """계좌 잔고 요약 조회."""
        token = await self._ensure_token()
        tr_id = "VTTC8434R" if settings.kis_demo else "TTTC8434R"
        resp = await self._client.get(
            "/uapi/domestic-stock/v1/trading/inquire-balance",
            headers=self._headers(token, tr_id),
            params={
                "CANO": self._account_no,
                "ACNT_PRDT_CD": self._account_suffix,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        summary = data.get("output2", [{}])[0] if data.get("output2") else {}
        return {
            "total_eval": float(summary.get("tot_evlu_amt", "0") or "0"),
            "total_purchase": float(summary.get("pchs_amt_smtl_amt", "0") or "0"),
            "total_pnl": float(summary.get("evlu_pfls_smtl_amt", "0") or "0"),
            "deposit": float(summary.get("dnca_tot_amt", "0") or "0"),
        }

    async def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        """현재가 조회."""
        token = await self._ensure_token()
        tr_id = "FHKST01010100"
        resp = await self._client.get(
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            headers=self._headers(token, tr_id),
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol},
        )
        resp.raise_for_status()
        data = resp.json()
        output = data.get("output", {})
        return {
            "symbol": symbol,
            "last": float(output.get("stck_prpr", "0") or "0"),
            "high": float(output.get("stck_hgpr", "0") or "0"),
            "low": float(output.get("stck_lwpr", "0") or "0"),
            "volume": float(output.get("acml_vol", "0") or "0"),
        }

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
    ) -> list[list]:
        """일봉 조회 (KIS는 분봉/일봉 기본 제공)."""
        token = await self._ensure_token()
        tr_id = "FHKST01010400"
        resp = await self._client.get(
            "/uapi/domestic-stock/v1/quotations/inquire-daily-price",
            headers=self._headers(token, tr_id),
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol,
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "0",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        output = data.get("output", [])
        result = []
        for item in output[:limit]:
            result.append(
                [
                    item.get("stck_bsop_date", ""),
                    float(item.get("stck_oprc", "0") or "0"),
                    float(item.get("stck_hgpr", "0") or "0"),
                    float(item.get("stck_lwpr", "0") or "0"),
                    float(item.get("stck_clpr", "0") or "0"),
                    float(item.get("acml_vol", "0") or "0"),
                ]
            )
        return result

    async def close(self):
        """HTTP 클라이언트 종료."""
        await self._client.aclose()
