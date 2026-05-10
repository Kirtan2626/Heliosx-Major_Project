import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import SessionLocal, Base, engine
import src.db_models as db_models
from sqlalchemy import select

import pytest_asyncio

@pytest_asyncio.fixture(autouse=True, scope="module")
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_database_connection():
    # Verify engine can connect
    async with engine.connect() as conn:
        assert conn is not None

@pytest.mark.asyncio
async def test_site_persistence():
    async with SessionLocal() as session:
        # Create site
        site = db_models.Site(
            name="Test Site",
            latitude=12.34,
            longitude=56.78,
            timezone_offset=1.0
        )
        session.add(site)
        await session.commit()
        
        # Verify
        stmt = select(db_models.Site).where(db_models.Site.name == "Test Site")
        result = await session.execute(stmt)
        saved_site = result.scalar_one()
        assert saved_site.latitude == 12.34
        
        # Cleanup
        await session.delete(saved_site)
        await session.commit()

from sqlalchemy.orm import selectinload

@pytest.mark.asyncio
async def test_simulation_run_persistence():
    async with SessionLocal() as session:
        # 1. Create site
        site = db_models.Site(name="Sim Site", latitude=0, longitude=0)
        session.add(site)
        await session.flush()
        
        # 2. Create run
        run = db_models.SimulationRun(
            site_id=site.id,
            total_fixed_wh=100.0,
            total_tracker_wh=150.0,
            total_ai_wh=145.0,
            maintenance_urgency="Healthy"
        )
        session.add(run)
        await session.flush()
        
        # 3. Add fault
        fault = db_models.FaultLog(
            simulation_id=run.id,
            fault_type="test",
            severity="low"
        )
        session.add(fault)
        await session.commit()
        
        # Verify relationship with eager loading
        stmt = (
            select(db_models.SimulationRun)
            .where(db_models.SimulationRun.id == run.id)
            .options(selectinload(db_models.SimulationRun.faults), selectinload(db_models.SimulationRun.site))
        )
        result = await session.execute(stmt)
        saved_run = result.scalar_one()
        assert len(saved_run.faults) == 1
        assert saved_run.site.name == "Sim Site"
        
        # Cleanup
        await session.delete(fault)
        await session.delete(saved_run)
        await session.delete(site)
        await session.commit()
