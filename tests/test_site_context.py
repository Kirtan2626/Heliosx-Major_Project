import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock
from src.site_context import SiteContextService
from src.models import CoordinatesRequest

@pytest.fixture
def mock_client():
    return AsyncMock(spec=httpx.AsyncClient)

@pytest.fixture
def service(mock_client):
    return SiteContextService(client=mock_client)

@pytest.mark.asyncio
async def test_get_context_success(service, mock_client):
    coords = CoordinatesRequest(lat=51.5074, lon=-0.1278)
    
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "elements": [
            {"type": "way", "tags": {"building": "yes"}},
            {"type": "node", "tags": {"natural": "tree"}}
        ]
    }
    mock_client.post.return_value = mock_response
    
    result = await service.get_context(coords)
    
    assert "buildings" in result
    assert "trees" in result
    assert len(result["buildings"]) == 1
    assert len(result["trees"]) == 1
    mock_client.post.assert_called_once()

@pytest.mark.asyncio
async def test_get_context_failure(service, mock_client):
    coords = CoordinatesRequest(lat=51.5074, lon=-0.1278)
    mock_client.post.side_effect = httpx.HTTPError("API Down")
    
    result = await service.get_context(coords)
    
    assert result == {"buildings": [], "trees": []}
    mock_client.post.assert_called_once()

@pytest.mark.asyncio
async def test_get_context_caching(service, mock_client):
    coords = CoordinatesRequest(lat=51.5074, lon=-0.1278)
    
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"elements": []}
    mock_client.post.return_value = mock_response
    
    # First call should hit the API
    await service.get_context(coords)
    # Second call should use cache
    await service.get_context(coords)
    
    assert mock_client.post.call_count == 1

@pytest.mark.asyncio
async def test_cache_limit(mock_client):
    # Use a small limit for testing
    service = SiteContextService(client=mock_client)
    service.CACHE_LIMIT = 2
    
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"elements": []}
    mock_client.post.return_value = mock_response
    
    # Fill cache
    await service.get_context(CoordinatesRequest(lat=1.0, lon=1.0))
    await service.get_context(CoordinatesRequest(lat=2.0, lon=2.0))
    assert len(service._cache) == 2
    
    # Add third item, first should be evicted
    await service.get_context(CoordinatesRequest(lat=3.0, lon=3.0))
    assert len(service._cache) == 2
    
    # Verify lat=1.0 is evicted
    cache_keys = list(service._cache.keys())
    assert (1.0, 1.0) not in cache_keys
    assert (2.0, 2.0) in cache_keys
    assert (3.0, 3.0) in cache_keys
