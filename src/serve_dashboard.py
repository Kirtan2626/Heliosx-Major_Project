from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from src.models import CoordinatesRequest, UnifiedEnvironmentalPayload
from src.weather_service import WeatherService
from src.site_context import SiteContextService

# Shared state to hold the client
class AppState:
    def __init__(self):
        self.client: httpx.AsyncClient = None

state = AppState()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set up the shared client
    state.client = httpx.AsyncClient(timeout=10.0)
    yield
    # Clean up the shared client
    await state.client.aclose()

app = FastAPI(title="Helios-X API Gateway", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency Injection helpers
def get_http_client():
    return state.client

def get_weather_service(client: httpx.AsyncClient = Depends(get_http_client)):
    return WeatherService(client=client)

def get_context_service(client: httpx.AsyncClient = Depends(get_http_client)):
    return SiteContextService(client=client)

@app.get("/weather", response_model=UnifiedEnvironmentalPayload)
async def get_weather(
    lat: float, 
    lon: float, 
    weather_svc: WeatherService = Depends(get_weather_service)
):
    req = CoordinatesRequest(lat=lat, lon=lon)
    return await weather_svc.get_weather(req)

@app.get("/site-context")
async def get_site_context(
    lat: float, 
    lon: float, 
    context_svc: SiteContextService = Depends(get_context_service)
):
    req = CoordinatesRequest(lat=lat, lon=lon)
    return await context_svc.get_context(req)

@app.post("/simulate")
async def simulate(lat: float, lon: float):
    # Stub for future physics engine loop
    return {"status": "Simulation dispatched. Not fully implemented yet."}
