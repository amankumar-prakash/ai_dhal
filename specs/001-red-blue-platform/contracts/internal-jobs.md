# Internal Job Dispatch Contract (API → Workers)

**Audience**: `api_service` dispatch + `red_team_backend` / `blue_team_backend`  
**Not** exposed to the analyst browser.

## Endpoint

`POST /internal/jobs` on the target worker (red or blue), authenticated by a shared internal secret (compose network + optional `X-Internal-Token`).

## Request body

```json
{
  "job_id": "uuid",
  "team": "red",
  "profile": "surface-recon",
  "asset_ids": ["uuid"],
  "assets": [
    {
      "id": "uuid",
      "name": "string",
      "hostname": "string|null",
      "ip_address": "string|null"
    }
  ],
  "tools": null,
  "callback_base_url": "http://api_service:8000/api/v1",
  "demo_safe_mode": true,
  "allowlist": ["cidrs or host patterns"]
}
```

## Worker responsibilities

1. Acknowledge with **202** (accepted) or **200** if synchronous stub.
2. `PATCH {callback_base_url}/jobs/{job_id}` → `running` (then terminal states).
3. Create scans updates, findings, threat_events (and optional chains/tool_runs) via callback API using `X-Service-Token`.
4. On out-of-scope or blocked action: emit threat_event with guardrail indication; do not invoke exploit tooling.
5. On tool failure: mark job `failed` with `error` text; related scans `failed`.
6. Poll or check cancel: if job is `cancelled`, stop and avoid further writes (API returns 409).

## Profiles

| Team | Profile | Pipeline |
|------|---------|----------|
| red | `surface-recon` | HexStrike recon adapters (stub OK in S2) |
| red | `deep-emulation` | CAI + tools (S4) |
| red | `defensive-validation` | CAI/validation (S4) |
| blue | `vuln-scan` | nuclei/trivy-style (S3) |
| blue | `monitor` | continuous/tick alerts (S4) |
| blue | `patch` | apply playbook (S3+) |
