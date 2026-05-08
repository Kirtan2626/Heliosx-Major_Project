import httpx
import logging
from typing import Dict, Tuple, Any
from collections import OrderedDict
from src.models import CoordinatesRequest

logger = logging.getLogger(__name__)

class SiteContextService:
    CACHE_LIMIT = 100

    def __init__(self, client: httpx.AsyncClient):
        """
        Initialize the service.
        :param client: Required httpx.AsyncClient to reuse.
        """
        self.client = client
        # Cache mapping (lat, lon) rounded to 5 decimal places to results
        self._cache: OrderedDict[Tuple[float, float], Dict[str, Any]] = OrderedDict()
        
    def _build_bbox(self, lat: float, lon: float, radius: float = 0.002) -> str:
        # approx 200m radius box
        return f"{lat-radius},{lon-radius},{lat+radius},{lon+radius}"

    def _get_cache_key(self, coords: CoordinatesRequest) -> Tuple[float, float]:
        # Round to 5 decimal places for ~1.1m precision
        return (round(coords.lat, 5), round(coords.lon, 5))

    async def get_context(self, coords: CoordinatesRequest) -> dict:
        cache_key = self._get_cache_key(coords)
        if cache_key in self._cache:
            logger.info(f"Returning cached site context for {cache_key}")
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]

        bbox = self._build_bbox(coords.lat, coords.lon)
        overpass_url = "https://overpass-api.de/api/interpreter"
        query = f"""
        [out:json];
        (
          way["building"]({bbox});
          node["natural"="tree"]({bbox});
        );
        out body geom qt;
        """
        
        try:
            resp = await self.client.post(overpass_url, data={"data": query})
            resp.raise_for_status()
            data = resp.json()
            
            buildings = []
            trees = []
            
            for elem in data.get("elements", []):
                elem_type = elem.get("type")
                tags = elem.get("tags", {})
                if elem_type == "way" and "building" in tags:
                    buildings.append(elem)
                elif elem_type == "node" and tags.get("natural") == "tree":
                    trees.append(elem)
            
            result = {"buildings": buildings, "trees": trees}
            
            # LRU Cache update
            self._cache[cache_key] = result
            if len(self._cache) > self.CACHE_LIMIT:
                self._cache.popitem(last=False)
                
            return result
                
        except httpx.ConnectTimeout:
            logger.error("OSM Overpass query failed: Connection timeout")
        except httpx.HTTPStatusError as e:
            logger.error(f"OSM Overpass query failed: HTTP error {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"OSM Overpass query failed: Request error {e}")
        except Exception as e:
            logger.error(f"OSM Overpass query failed: Unexpected error {e}")
            
        return {"buildings": [], "trees": []}
