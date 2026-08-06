from __future__ import annotations

import logging
from typing import Any

import httpx

from app.settings import WorkerSettings, get_settings

log = logging.getLogger(__name__)


class ApiReporter:
    def __init__(self, settings: WorkerSettings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def headers(self) -> dict[str, str]:
        return {"X-Service-Token": self.settings.blue_service_token}

    async def _request(self, method: str, path: str, json: dict[str, Any] | None = None) -> Any:
        url = f"{self.settings.api_base_url.rstrip('/')}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(2):
                resp = await client.request(method, url, headers=self.headers, json=json)
                if resp.status_code == 503 and attempt == 0:
                    continue
                resp.raise_for_status()
                if resp.status_code == 204:
                    return None
                return resp.json()
        return None

    async def patch_job(self, job_id: str, **fields: Any) -> Any:
        return await self._request("PATCH", f"jobs/{job_id}", json=fields)

    async def post_finding(self, payload: dict[str, Any]) -> Any:
        return await self._request("POST", "findings", json=payload)

    async def post_threat_event(self, payload: dict[str, Any]) -> Any:
        return await self._request("POST", "threat-events", json=payload)

    async def post_tool_run(self, payload: dict[str, Any]) -> Any:
        return await self._request("POST", "tool-runs", json=payload)

    async def post_patch(self, payload: dict[str, Any]) -> Any:
        return await self._request("POST", "patches", json=payload)

    async def patch_patch(self, patch_id: str, payload: dict[str, Any]) -> Any:
        return await self._request("PATCH", f"patches/{patch_id}", json=payload)
