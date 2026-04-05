"""CR-048 RI-2B-2c Session 2 — Path L SQLite compatibility tests.

Purpose
-------
Validates the Option A2 remediation in
`app/services/shadow_write_service.py` line ~568-579, where the raw
`text("SELECT ... FOR UPDATE")` Step 6 query was replaced by a
dialect-aware ORM `select(...).with_for_update()` construct.

Before Option A2
    `sqlite3.OperationalError: near "FOR": syntax error`
    blocked every Path L (aiosqlite) test, forcing the B3'' Path L
    bounded CAS write session to return 0 calls / 0 writes.

After Option A2
    SQLAlchemy's SQLite dialect silently drops the row-lock hint
    (SQLite serializes writers per database file, so a row lock is
    meaningless anyway), allowing the exact same Python code path
    to execute on both SQLite (tests) and PostgreSQL (production).

Scope boundaries (governance lock)
----------------------------------
- Tests the remediated Step 6 query only (the ORM construct used by
  `execute_bounded_write`).
- Does NOT invoke `execute_bounded_write()` end-to-end — that is
  Session 3 scope (B3'' retry) and requires a full 17-column Symbol
  bootstrap plus additional governance gates.
- Does NOT mutate any existing shadow_write_receipt data.
- Does NOT touch `data/cr048_prior_shadow.sqlite` — each test
  creates its own isolated temporary aiosqlite database.
"""

from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

# Plain imports. Harness pollution from module-level sys.modules stubs in
# ~60 peer test files is neutralized by Option P: tests/conftest.py eager
# imports app.models.asset at plugin-load time, before any test-file
# module body runs. See:
#   docs/operations/evidence/cr048_ri2b2c_session2_amendment_v2.md
# (CR-048 RI-2B-2c Session 2 Amendment Sheet v2 — controlling spec).
from app.models.asset import Symbol, AssetClass, AssetSector

# Route metadata through `Symbol.__table__` — always bound to the real
# DeclarativeBase metadata captured at Symbol class creation time.
_REAL_METADATA = Symbol.__table__.metadata


# ── Dialect compilation tests (no database required) ────────────


def test_with_for_update_compiles_to_for_update_on_postgres() -> None:
    """Regression guard: Postgres dialect must still emit 'FOR UPDATE'.

    Semantic equivalence with the pre-Option-A2 raw
    `text('SELECT ... FOR UPDATE')` path is the whole point of the
    dialect-aware switch.
    """
    stmt = (
        select(Symbol.qualification_status)
        .where(Symbol.symbol == "SOL/USDT")
        .with_for_update()
    )
    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in compiled, (
        f"Postgres dialect must emit FOR UPDATE; got: {compiled}"
    )


def test_with_for_update_drops_for_update_on_sqlite() -> None:
    """Regression guard: SQLite dialect must NOT emit 'FOR UPDATE'.

    SQLite has no row-level locks; SQLAlchemy's sqlite dialect is
    documented to silently drop the hint. This is the exact property
    that unblocks Path L.
    """
    stmt = (
        select(Symbol.qualification_status)
        .where(Symbol.symbol == "SOL/USDT")
        .with_for_update()
    )
    compiled = str(stmt.compile(dialect=sqlite.dialect()))
    assert "FOR UPDATE" not in compiled, (
        f"SQLite dialect must NOT emit FOR UPDATE; got: {compiled}"
    )


# ── Real aiosqlite integration tests ────────────────────────────


@pytest_asyncio.fixture
async def aiosqlite_engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    """Fresh isolated aiosqlite engine — one per test function.

    Each test gets its own SQLite file under pytest's tmp_path, so
    tests do not share state and do not touch the real
    `data/cr048_prior_shadow.sqlite` file.
    """
    db_path = tmp_path / "cr048_path_l_compat.sqlite"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path.as_posix()}",
        echo=False,
    )
    async with engine.begin() as conn:
        # Use Symbol-bound metadata (not app.core.database.Base.metadata)
        # to stay immune to MagicMock stubbing from other test files.
        await conn.run_sync(_REAL_METADATA.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_step6_query_executes_on_aiosqlite_without_syntax_error(
    aiosqlite_engine: AsyncEngine,
) -> None:
    """The Option A2 Step 6 query must execute cleanly on aiosqlite.

    Before Option A2 this exact code path raised
    `sqlite3.OperationalError: near "FOR": syntax error`. After
    Option A2 it must succeed and return the stored
    `qualification_status`.
    """
    async with AsyncSession(aiosqlite_engine, expire_on_commit=False) as session:
        row = Symbol(
            symbol="SOL/USDT",
            name="Solana / Tether USD",
            asset_class=AssetClass.CRYPTO,
            sector=AssetSector.LAYER1,
            exchanges='["binance"]',
        )
        session.add(row)
        await session.commit()

        # Exact construct emitted by shadow_write_service.execute_bounded_write
        # Step 6 after the Option A2 remediation.
        stmt = (
            select(Symbol.qualification_status)
            .where(Symbol.symbol == "SOL/USDT")
            .with_for_update()
        )
        result = await session.execute(stmt)
        fetched = result.fetchone()

    assert fetched is not None, "Step 6 query returned no row for inserted symbol"
    assert fetched[0] == "unchecked", (
        f"qualification_status should default to 'unchecked'; got: {fetched[0]!r}"
    )


@pytest.mark.asyncio
async def test_step6_query_returns_none_for_missing_symbol(
    aiosqlite_engine: AsyncEngine,
) -> None:
    """When no matching row exists, Step 6 must return None, not raise.

    This mirrors the TOCTOU-defense behaviour of the production path:
    `current_db_value = db_row[0] if db_row else None` immediately
    after `fetchone()`.
    """
    async with AsyncSession(aiosqlite_engine, expire_on_commit=False) as session:
        stmt = (
            select(Symbol.qualification_status)
            .where(Symbol.symbol == "NONEXISTENT/PAIR")
            .with_for_update()
        )
        result = await session.execute(stmt)
        fetched = result.fetchone()

    assert fetched is None, (
        f"Missing symbol must yield None; got: {fetched!r}"
    )


@pytest.mark.asyncio
async def test_step6_query_reflects_updated_qualification_status(
    aiosqlite_engine: AsyncEngine,
) -> None:
    """After updating `qualification_status`, Step 6 must see the new value.

    This proves the query is a real SELECT against live DB state, not
    a cached/stale read — essential for the CAS guard that
    `execute_bounded_write` performs one line later.
    """
    async with AsyncSession(aiosqlite_engine, expire_on_commit=False) as session:
        row = Symbol(
            symbol="BTC/USDT",
            name="Bitcoin / Tether USD",
            asset_class=AssetClass.CRYPTO,
            sector=AssetSector.LAYER1,
            exchanges='["binance"]',
        )
        session.add(row)
        await session.commit()

        # Flip status through the model API (not via the sealed
        # execute_bounded_write — Session 3 scope).
        row.qualification_status = "pass"
        await session.commit()

        stmt = (
            select(Symbol.qualification_status)
            .where(Symbol.symbol == "BTC/USDT")
            .with_for_update()
        )
        result = await session.execute(stmt)
        fetched = result.fetchone()

    assert fetched is not None
    assert fetched[0] == "pass", (
        f"Step 6 query must reflect latest DB value; got: {fetched[0]!r}"
    )
