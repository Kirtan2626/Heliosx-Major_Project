import httpx
from datetime import datetime
from src.models import CoordinatesRequest, UnifiedEnvironmentalPayload
import logging

logger = logging.getLogger(__name__)

class WeatherService:
    def __init__(self, client: httpx.AsyncClient = None):
        """
        Initialize the service.
        :param client: Optional httpx.AsyncClient to reuse. If not provided, one will be created lazily.
        """
        self.client = client
        self._cache = {}

    async def get_weather(self, coords: CoordinatesRequest) -> UnifiedEnvironmentalPayload:
        cache_key = f"{round(coords.lat, 2)},{round(coords.lon, 2)}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            if self.client:
                return await self._fetch_weather(self.client, coords, cache_key)
            else:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    return await self._fetch_weather(client, coords, cache_key)
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error(f"Weather API failed: {e}")
            return self._safe_fallback()

    async def _fetch_weather(self, client: httpx.AsyncClient, coords: CoordinatesRequest, cache_key: str) -> UnifiedEnvironmentalPayload:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={coords.lat}&longitude={coords.lon}&current=temperature_2m,relative_humidity_2m,cloud_cover,wind_speed_10m"
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        
        curr = data.get("current", {})
        payload = UnifiedEnvironmentalPayload(
            temperatureC=float(curr.get("temperature_2m", 35.0)),
            roundedTemperatureC=int(round(curr.get("temperature_2m", 35.0))),
            humidityPercent=float(curr.get("relative_humidity_2m", 50.0)),
            windSpeed=float(curr.get("wind_speed_10m", 3.0)),
            cloudCoverPercent=float(curr.get("cloud_cover", 0.0)),
            source="Open-Meteo",
            sourceLabel="Open-Meteo (Live API)",
            fetchedAt=datetime.now()
        )
        self._cache[cache_key] = payload
        return payload

    def _safe_fallback(self) -> UnifiedEnvironmentalPayload:
        return UnifiedEnvironmentalPayload(
            temperatureC=35.0,
            roundedTemperatureC=35,
            humidityPercent=50.0,
            windSpeed=3.0,
            cloudCoverPercent=0.0,
            source="Fallback",
            sourceLabel="Fallback (Safe Physics Defaults)",
            fetchedAt=datetime.now()
        )
