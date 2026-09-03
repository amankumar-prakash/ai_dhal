import os
from collections import defaultdict, deque
from time import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.db.store import get_store
from app.routers import (
    admin_users,
    assets,
    auth_login,
    cai_chat,
    findings,
    jobs,
    me,
    misc,
    patches,
    scans,
    tasks,
    threat_events,
)

app = FastAPI(title="Red/Blue Platform API", version="0.1.0")

API = "/api/v1"
app.include_router(auth_login.router, prefix=API)
app.include_router(assets.router, prefix=API)
app.include_router(scans.router, prefix=API)
app.include_router(findings.router, prefix=API)
app.include_router(threat_events.router, prefix=API)
app.include_router(jobs.router, prefix=API)
app.include_router(patches.router, prefix=API)
app.include_router(misc.router_chains, prefix=API)
app.include_router(misc.router_roles, prefix=API)
app.include_router(misc.router_tools, prefix=API)
app.include_router(me.router, prefix=API)
app.include_router(tasks.router, prefix=API)
app.include_router(admin_users.router, prefix=API)
app.include_router(cai_chat.router, prefix=API)

_JOB_HITS: dict[str, deque[float]] = defaultdict(deque)
_JOB_LIMIT = 30
_JOB_WINDOW = 60.0


class JobRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path.rstrip("/").endswith("/jobs"):
            key = request.client.host if request.client else "unknown"
            now = time()
            q = _JOB_HITS[key]
            while q and now - q[0] > _JOB_WINDOW:
                q.popleft()
            if len(q) >= _JOB_LIMIT:
                return Response(
                    content='{"detail":"rate limit"}',
                    status_code=429,
                    media_type="application/json",
                )
            q.append(now)
        return await call_next(request)


# Browser UI (Vite) calls this API cross-origin with Authorization → needs preflight.
# Middleware is applied in reverse order of add_middleware; add CORS last so it is outermost.
def _cors_origins() -> list[str]:
    origins = [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:10100",
        "http://127.0.0.1:10100",
    ]
    public_ip = (os.environ.get("PUBLIC_IPADDR") or "").strip()
    public_ui = (os.environ.get("VAST_TCP_PORT_10100") or "").strip()
    if public_ip and public_ui:
        origins.extend(
            [
                f"http://{public_ip}:{public_ui}",
                f"https://{public_ip}:{public_ui}",
            ]
        )
    return origins


app.add_middleware(JobRateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _seed_lab_assets() -> None:
    settings = get_settings()
    if (settings.api_store or "").lower() != "memory":
        return
    store = get_store()
    if store.list_all("assets"):
        return
    from uuid import NAMESPACE_DNS, uuid5

    demos = [
        ("Edge Gateway", "edge-gw-01.corp.internal", "10.4.1.10", "critical"),
        ("Payments API", "pay-api-prod-03.corp.internal", "10.4.9.31", "critical"),
        ("Identity Store", "idp-ldap-01.corp.internal", "10.4.2.14", "high"),
    ]
    for name, host, ip, crit in demos:
        store.create(
            "assets",
            {
                "id": uuid5(NAMESPACE_DNS, host),
                "name": name,
                "hostname": host,
                "ip_address": ip,
                "kind": "host",
                "criticality": crit,
            },
        )


@app.on_event("startup")
def on_startup():
    _seed_lab_assets()
    from app.lab_users import seed_lab_identities

    seed_lab_identities()


@app.get(f"{API}/health")
def health():
    return {"status": "ok"}


@app.get(f"{API}/ready")
def ready():
    settings = get_settings()
    mode = (settings.api_store or "supabase").lower()
    if mode == "supabase":
        if not settings.supabase_url or not settings.elevated_key():
            return {
                "status": "not_ready",
                "reason": "SUPABASE_URL and SUPABASE_SECRET_KEY (or SERVICE_ROLE_KEY) required",
            }
    return {"status": "ready", "store": mode}
