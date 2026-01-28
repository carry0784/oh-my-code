import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_list_orders_empty(client: AsyncClient):
    response = await client.get("/api/v1/orders/")
    assert response.status_code == 200
    data = response.json()
    assert data["orders"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_signals_empty(client: AsyncClient):
    response = await client.get("/api/v1/signals/")
    assert response.status_code == 200
    data = response.json()
    assert data["signals"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_agent_status(client: AsyncClient):
    response = await client.get("/api/v1/agents/status")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert data["status"] == "ready"
