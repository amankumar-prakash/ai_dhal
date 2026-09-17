import os
from collections import defaultdict, deque
from contextlib import asynccontextmanager
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

API = "/api/v1"

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
def _cors_origins() -> list[str]:
    settings = get_settings()
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
    # CR-18 FIX: read public IP/port from structured Settings rather than raw os.environ.
    public_ip = settings.public_ipaddr.strip()
    public_ui = settings.vast_tcp_port_10100.strip()
    if public_ip and public_ui:
        origins.extend(
            [
                f"http://{public_ip}:{public_ui}",
                f"https://{public_ip}:{public_ui}",
            ]
        )
    return origins


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


def _seed_juice_shop_task() -> None:
    """Restore the lab Juice Shop recon draft after an in-memory API restart."""
    settings = get_settings()
    if (settings.api_store or "").lower() != "memory":
        return
    from datetime import datetime, timezone
    from uuid import UUID

    from app.lab_users import lab_accounts, user_id_for_email

    store = get_store()
    task_id = UUID("7d15e2c7-8ed3-425c-955c-732f66b6c56f")
    if store.get("tasks", task_id):
        return
    mgr = next((a for a in lab_accounts(settings) if a["role"] == "security_manager"), None)
    manager_id = user_id_for_email(mgr["email"]) if mgr else None
    now = datetime.now(timezone.utc)
    store.create(
        "tasks",
        {
            "id": task_id,
            "target": "http://81.183.231.113:25429",
            "description": (
                "Authorized HexStrike recon of OWASP Juice Shop "
                "(from source on :10200 / public :25429). "
                "Phases: nmap, httpx-toolkit, gobuster/feroxbuster, katana, "
                "/rest+/api probe, nuclei exposure tags."
            ),
            "patch_scope": "none — lab Juice Shop, no WAF, no edge hardening",
            "asset_id": None,
            "task_type": "red",
            "status": "draft",
            "created_by": manager_id,
            "assignee_id": None,
            "assigning_manager_id": manager_id,
            "linked_job_id": None,
            "created_at": now,
            "updated_at": now,
        },
    )


# CR-06 FIX: Replace deprecated @app.on_event("startup") with the modern
# lifespan context manager (FastAPI ≥ 0.93 / 0.115).
@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    _seed_lab_assets()
    from app.lab_users import seed_lab_identities

    seed_lab_identities()
    _seed_juice_shop_task()
    yield  # application runs here


app = FastAPI(title="Red/Blue Platform API", version="0.1.0", lifespan=lifespan)

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

# Middleware is applied in reverse order of add_middleware; add CORS last so it is outermost.
app.add_middleware(JobRateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
