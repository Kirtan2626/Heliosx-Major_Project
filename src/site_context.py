import httpx
import logging
import math
import random
from typing import Dict, Tuple, Any, List
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
        
    def _get_cache_key(self, coords: CoordinatesRequest) -> Tuple[float, float]:
        # Round to 5 decimal places for ~1.1m precision
        return (round(coords.lat, 5), round(coords.lon, 5))

    async def get_context(self, coords: CoordinatesRequest, radius: int = 150) -> dict:
        cache_key = self._get_cache_key(coords)
        if cache_key in self._cache:
            logger.info(f"Returning cached site context for {cache_key}")
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]

        overpass_url = "https://overpass-api.de/api/interpreter"
        # Using 'around' query for better proximity matching
        query = f"""
        [out:json][timeout:15];
        (
          way["building"](around:{radius},{coords.lat},{coords.lon});
          relation["building"](around:{radius},{coords.lat},{coords.lon});
          node["natural"="tree"](around:{radius},{coords.lat},{coords.lon});
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
                
                if "building" in tags or "building:part" in tags:
                    # Capture way and relation footprints
                    buildings.append(elem)
                elif elem_type == "node" and tags.get("natural") == "tree":
                    trees.append(elem)
            
            # Procedural Fallback if no real data
            if not buildings and not trees:
                logger.warning(f"No OSM data found for {cache_key}. Using procedural fallback.")
                buildings, trees = self._generate_procedural_context(coords.lat, coords.lon)

            result = {"buildings": buildings, "trees": trees}
            
            # LRU Cache update
            self._cache[cache_key] = result
            if len(self._cache) > self.CACHE_LIMIT:
                self._cache.popitem(last=False)
                
            return result
                
        except Exception as e:
            logger.error(f"OSM Overpass query failed: {e}. Using procedural fallback.")
            buildings, trees = self._generate_procedural_context(coords.lat, coords.lon)
            return {"buildings": buildings, "trees": trees}

    def _generate_procedural_context(self, lat: float, lon: float) -> Tuple[List[dict], List[dict]]:
        """
        Generates deterministic fake buildings/trees based on coordinates 
        to ensure the 3D scene is never empty.
        """
        seed = int(abs(lat * 1000) + abs(lon * 1000))
        rng = random.Random(seed)
        
        buildings = []
        # Generate 3-5 fake buildings
        for i in range(rng.randint(3, 6)):
            # Random offset in degrees (~50-100m)
            off_lat = rng.uniform(0.0005, 0.0015) * (1 if rng.random() > 0.5 else -1)
            off_lon = rng.uniform(0.0005, 0.0015) * (1 if rng.random() > 0.5 else -1)
            
            b_lat, b_lon = lat + off_lat, lon + off_lon
            # Create a square footprint
            s = 0.0001 # approx 10m
            geometry = [
                {"lat": b_lat - s, "lon": b_lon - s},
                {"lat": b_lat + s, "lon": b_lon - s},
                {"lat": b_lat + s, "lon": b_lon + s},
                {"lat": b_lat - s, "lon": b_lon + s},
                {"lat": b_lat - s, "lon": b_lon - s}
            ]
            
            buildings.append({
                "type": "way",
                "id": 999000 + i,
                "tags": {"building": "yes", "height": str(rng.randint(8, 25)), "name": "Procedural Block"},
                "geometry": geometry
            })
            
        trees = []
        # Generate 2-4 fake trees
        for i in range(rng.randint(2, 5)):
            off_lat = rng.uniform(0.0002, 0.0008) * (1 if rng.random() > 0.5 else -1)
            off_lon = rng.uniform(0.0002, 0.0008) * (1 if rng.random() > 0.5 else -1)
            trees.append({
                "type": "node",
                "id": 888000 + i,
                "lat": lat + off_lat,
                "lon": lon + off_lon,
                "tags": {"natural": "tree"}
            })
            
        return buildings, trees
