from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.reporters.api_reporter import ApiReporter
from app.settings import WorkerSettings


@pytest.mark.asyncio
async def test_reporter_retries_503():
    settings = WorkerSettings(
        api_base_url="http://api.test/api/v1",
        red_service_token="tok",
        llm_stub="1",
    )
    resp503 = MagicMock()
    resp503.status_code = 503
    resp503.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("503", request=MagicMock(), response=resp503))

    resp200 = MagicMock()
    resp200.status_code = 200
    resp200.json = MagicMock(return_value={"id": "j1", "status": "running"})
    resp200.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.request = AsyncMock(side_effect=[resp503, resp200])

    with patch("app.reporters.api_reporter.httpx.AsyncClient", return_value=mock_client):
        reporter = ApiReporter(settings)
        out = await reporter.patch_job("j1", status="running")
    assert out["status"] == "running"
    assert mock_client.request.call_count == 2
