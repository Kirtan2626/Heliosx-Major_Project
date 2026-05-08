from contextlib import asynccontextmanager
from typing import Annotated
import httpx
from fastapi import FastAPI, Depends, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from src.models import CoordinatesRequest, UnifiedEnvironmentalPayload, LatQuery, LonQuery
from src.weather_service import WeatherService
from src.site_context import SiteContextService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set up the shared client
    async with httpx.AsyncClient(timeout=10.0) as client:
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
    lon: LonQuery
):
    # Stub for future physics engine loop
    return {"status": "Simulation dispatched. Not fully implemented yet."}
