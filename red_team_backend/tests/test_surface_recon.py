import pytest

from app.adapters import hexstrike_client


@pytest.mark.asyncio
async def test_surface_recon_payload():
    result = await hexstrike_client.run_recon("lab.local", "10.0.0.1")
    assert result["tool"]
    assert result["findings"]
    assert result["findings"][0]["title"]
