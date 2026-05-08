import pytest
import httpx
from unittest.mock import AsyncMock, patch
from src.site_context import SiteContextService
from src.models import CoordinatesRequest

@pytest.mark.asyncio
async def test_get_context_success():
    service = SiteContextService()
    coords = CoordinatesRequest(lat=51.5074, lon=-0.1278)
    
    mock_response = {
        "elements": [
            {"type": "way", "tags": {"building": "yes"}},
            {"type": "node", "tags": {"natural": "tree"}}
        ]
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = AsyncMock(spec=httpx.Response)
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_response
        
        result = await service.get_context(coords)
        
        assert "buildings" in result
        assert "trees" in result
        assert len(result["buildings"]) == 1
        assert len(result["trees"]) == 1
        mock_post.assert_called_once()

@pytest.mark.asyncio
async def test_get_context_failure():
    service = SiteContextService()
    coords = CoordinatesRequest(lat=51.5074, lon=-0.1278)
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.HTTPError("API Down")
        
        result = await service.get_context(coords)
        
        assert result == {"buildings": [], "trees": []}
        mock_post.assert_called_once()

@pytest.mark.asyncio
async def test_get_context_caching():
    service = SiteContextService()
    coords = CoordinatesRequest(lat=51.5074, lon=-0.1278)
    
    mock_response = {"elements": []}
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = AsyncMock(spec=httpx.Response)
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_response
        
        # First call should hit the API
        await service.get_context(coords)
        # Second call should use cache
        await service.get_context(coords)
        
        assert mock_post.call_count == 1
