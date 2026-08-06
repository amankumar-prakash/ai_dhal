# Contracts: SentryOps RBAC User Journeys

**Feature**: `002-rbac-user-journeys`  
**Updated**: 2026-08-05

| Artifact | Purpose |
|----------|---------|
| [access-matrix.json](./access-matrix.json) | Canonical AuthZ + bootstrap flags |
| [route-guards.md](./route-guards.md) | UI route predicates (multi-task unlock) |
| [openapi.yaml](./openapi.yaml) | HTTP shapes: admin, tasks, notes/links, notifications |
| [live-tools-and-identity.md](./live-tools-and-identity.md) | `/me`, bootstrap TEST_USER, HexStrike/CAI worker env |

**AuthZ path**: browser route guards + `api_service` principal from `user_roles` (003 API-primary). OpenAPI remains the handoff contract; implement routers under `api_service`.
