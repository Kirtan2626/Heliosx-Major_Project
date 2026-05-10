from contextlib import asynccontextmanager
from typing import Annotated
from datetime import datetime
import httpx
from fastapi import FastAPI, Depends, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models import CoordinatesRequest, UnifiedEnvironmentalPayload, LatQuery, LonQuery, SimulationResult
from src.weather_service import WeatherService
from src.site_context import SiteContextService
from src.heliosx_sim_server import run_simulation
from src.services.matlab_export_service import format_for_matlab
from src.database import get_db
import src.db_models as db_models

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set up the shared client with a User-Agent to comply with APIs like OSM Overpass
    headers = {"User-Agent": "HeliosX-DigitalTwin/1.0 (contact@heliosx.example.com)"}
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        app.state.client = client
        yield
    # Clean up is handled by async with block

app = FastAPI(title="Helios-X API Gateway", lifespan=lifespan)

# Restrict CORS Origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency Injection helpers
def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.client

def get_weather_service(client: httpx.AsyncClient = Depends(get_http_client)):
    return WeatherService(client=client)

def get_context_service(client: httpx.AsyncClient = Depends(get_http_client)):
    return SiteContextService(client=client)

@app.get("/weather", response_model=UnifiedEnvironmentalPayload)
async def get_weather(
    lat: LatQuery, 
    lon: LonQuery, 
    weather_svc: WeatherService = Depends(get_weather_service)
):
    req = CoordinatesRequest(lat=lat, lon=lon)
    return await weather_svc.get_weather(req)

@app.get("/site-context")
async def get_site_context(
    lat: LatQuery, 
    lon: LonQuery, 
    context_svc: SiteContextService = Depends(get_context_service)
):
    req = CoordinatesRequest(lat=lat, lon=lon)
    return await context_svc.get_context(req)

@app.post("/simulate")
async def simulate(
    lat: LatQuery, 
    lon: LonQuery,
    tariff: float = Query(0.15, ge=0),
    weather_svc: WeatherService = Depends(get_weather_service),
    context_svc: SiteContextService = Depends(get_context_service),
    db: AsyncSession = Depends(get_db)
):
    req = CoordinatesRequest(lat=lat, lon=lon)
    weather = await weather_svc.get_weather(req)
    context = await context_svc.get_context(req)
    
    # Deterministic start time (today at midnight)
    start_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    # Simple lon-based UTC offset
    utc_offset = round(lon / 15.0)
    
    result = await run_in_threadpool(
        run_simulation, 
        lat, lon, 
        weather.model_dump(), 
        context, 
        start_dt=start_dt, 
        utc_offset=utc_offset,
        tariff=tariff
    )

    # Persist to Database
    try:
        # 1. Ensure Site exists
        stmt = select(db_models.Site).where(
            db_models.Site.latitude == lat, 
            db_models.Site.longitude == lon
        )
        site_result = await db.execute(stmt)
        site = site_result.scalar_one_or_none()
        
        if not site:
            site = db_models.Site(
                name=f"Site_{lat}_{lon}",
                latitude=lat,
                longitude=lon,
                timezone_offset=float(utc_offset)
            )
            db.add(site)
            await db.flush()

        # 2. Create Simulation Run record
        run = db_models.SimulationRun(
            site_id=site.id,
            weather_data=weather.model_dump(mode='json'),
            total_fixed_wh=result["daily_totals"]["fixed_wh"],
            total_tracker_wh=result["daily_totals"]["tracker_wh"],
            total_ai_wh=result["daily_totals"]["ai_wh"],
            kwh_loss=result["commercial_impact"]["kwh_loss"],
            financial_loss_usd=result["commercial_impact"]["financial_loss_usd"],
            maintenance_urgency=result["commercial_impact"]["urgency"]
        )
        db.add(run)
        await db.flush()

        # 3. Log Faults
        for f in result.get("faults", []):
            fault = db_models.FaultLog(
                simulation_id=run.id,
                fault_type=f["type"],
                severity=f["severity"],
                message=f["message"]
            )
            db.add(fault)
        
        await db.commit()
        result["db_id"] = run.id
    except Exception as e:
        await db.rollback()
        print(f"Database persistence failed: {e}")

    return result

@app.get("/history")
async def get_history(limit: int = 10, db: AsyncSession = Depends(get_db)):
    stmt = select(db_models.SimulationRun).order_by(db_models.SimulationRun.timestamp.desc()).limit(limit)
    result = await db.execute(stmt)
    runs = result.scalars().all()
    return runs

@app.post("/export-matlab")
async def export_matlab(sim_payload: SimulationResult):
    return format_for_matlab(sim_payload)
