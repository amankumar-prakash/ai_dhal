# Feature Specification: Supabase as Primary Data & Auth Platform

**Feature Branch**: `003-supabase-primary-db`

**Created**: 2026-08-05

**Status**: Draft

**Input**: User description: "Use Supabase as the primary database, authentication, and data platform for everything — Postgres, Auth, all app data, Storage if needed, Realtime if needed; Python client on backend; versioned migrations; RLS on every table; service role only on backend; anon key + user JWT on client. Add supabase to requirements; apply all migrations; creds in .env."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Analysts persist data in the shared platform store (Priority: P1)

An analyst signs in and creates or updates security assets, scans, findings, and related records. Those records remain available after API restarts and across team members, because the platform API reads and writes the shared project database rather than a temporary in-memory store.

**Why this priority**: Without durable shared storage, the red/blue platform cannot be used as a real lab or product; memory mode loses all data on restart.

**Independent Test**: Sign in → create an asset via the UI/API → restart the API process → asset still listed for the same signed-in user.

**Acceptance Scenarios**:

1. **Given** a signed-in analyst and a configured platform project, **When** they create an asset, **Then** the asset is stored in the shared database and appears on subsequent list requests.
2. **Given** existing seeded or migrated tables, **When** the API is restarted, **Then** previously created business records remain available.
3. **Given** the API is configured for the shared store, **When** an anonymous caller attempts business mutations, **Then** the request is rejected.

---

### User Story 2 - Sign-in uses platform identity (Priority: P1)

Users authenticate through the platform identity service (email/password and any already-enabled lab methods such as magic link or OAuth). The UI continues to use the publishable client credentials; the backend validates the user's session token and never exposes privileged server credentials to the browser.

**Why this priority**: Auth and data must share one identity boundary so RLS and API AuthZ stay consistent.

**Independent Test**: Sign in via the existing UI auth flow → obtain a session → call a protected API route successfully; call the same route without a token and receive unauthorized.

**Acceptance Scenarios**:

1. **Given** valid credentials for a lab user, **When** they sign in through the UI, **Then** they receive a session usable for protected API calls.
2. **Given** no session token, **When** they call a protected business API, **Then** access is denied.
3. **Given** a privileged server key, **When** inspecting the browser bundle or public env, **Then** that key is not present (only publishable/anon credentials).

---

### User Story 3 - Schema is versioned and applied (Priority: P1)

Operators apply the full set of versioned SQL migrations so the remote project schema matches the repository (including jobs, patches, tool runs, team columns, and RLS policies). New schema changes are only introduced as migration files.

**Why this priority**: Remote project currently lacks red/blue extensions; without applied migrations the shared store cannot hold jobs/patches.

**Independent Test**: After migrations are applied, listing jobs/patches/tool_runs against the project succeeds (table exists); selecting new columns such as `scans.team` does not error with “column does not exist.”

**Acceptance Scenarios**:

1. **Given** the migration files in the repository, **When** an operator applies them to the project, **Then** required tables and columns exist.
2. **Given** RLS enabled on operational tables, **When** a browser client uses only the publishable key without a privileged role, **Then** it cannot insert/update/delete business rows that policy reserves for the server path.
3. **Given** a proposed schema change, **When** it is merged, **Then** it exists as a versioned migration file (not an ad-hoc undocumented dashboard edit as the source of truth).

---

### User Story 4 - Live updates still work after API writes (Priority: P2)

When the backend writes findings, scans, or threat events into the shared database, the analyst UI continues to refresh live views without a full page reload (Realtime subscriptions remain valid for those tables).

**Why this priority**: Live dashboards are an existing product expectation; durable storage must not break them.

**Independent Test**: Open Threats view → create a threat event via API/worker path → UI updates without manual refresh.

**Acceptance Scenarios**:

1. **Given** Realtime enabled for relevant tables, **When** the API inserts a threat event, **Then** the subscribed UI invalidates or updates within a few seconds.
2. **Given** Realtime temporarily unavailable, **When** the user refreshes the page, **Then** data still loads correctly from the API.

---

### User Story 5 - Optional files via platform storage (Priority: P3)

If a feature needs file attachments (evidence dumps, report exports), files are stored in the platform object storage with access controlled consistently with auth policies—not on worker local disk as the system of record.

**Why this priority**: Not required for core red/blue job MVP; reserved for evidence/export flows.

**Independent Test**: Upload a small evidence file through an approved backend path → retrieve metadata/URL with an authorized session.

**Acceptance Scenarios**:

1. **Given** a storage bucket configured for evidence, **When** the backend stores a file, **Then** only authorized principals can access it.
2. **Given** no storage feature enabled yet, **When** core scan/job flows run, **Then** they succeed without requiring storage.

---

### Edge Cases

- Missing or empty privileged server credentials: API must fail ready-check clearly rather than silently falling back to memory in production-intended mode.
- Migration partially applied: operator documentation must list verification queries for tables/columns.
- Memory mode retained only as an explicit offline/dev escape hatch, not the default when shared-store credentials are present.
- Service tokens for workers remain for job reporting; they must not replace user Auth for analyst UI actions.
- Last-admin / role tables continue to follow existing RBAC feature rules where already specified.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST persist all application business data (assets, scans, findings, threat events, jobs, patches, tool runs, attack chains/steps, roles) in the shared project PostgreSQL database.
- **FR-002**: System MUST use the platform identity service as the sole sign-in source for analysts and admins in the UI.
- **FR-003**: Browser clients MUST use only publishable/anon credentials plus the user session token; privileged server credentials MUST be used only by backend services.
- **FR-004**: Backend API MUST be the write path for business tables under elevated privileges, consistent with tightened RLS (authenticated SELECT-oriented policies where already designed).
- **FR-005**: All schema changes MUST be delivered as versioned SQL migration files under the project’s `supabase/migrations` folder.
- **FR-006**: Every application table MUST have Row Level Security enabled.
- **FR-007**: Backend MUST depend on the official Python client library for Supabase data access ([supabase-py](https://supabase.com/docs/reference/python/introduction)).
- **FR-008**: Operators MUST be able to apply the full migration set to the configured remote project using credentials from environment configuration.
- **FR-009**: When Realtime is required for a view, subscriptions MUST remain on the shared database tables written by the API.
- **FR-010**: File storage, when introduced, MUST use platform Storage rather than ad-hoc local disks as the system of record.
- **FR-011**: Root and service environment configuration MUST document and load `SUPABASE_URL`, publishable key (UI), elevated secret/service key (API only), and MUST verify user sessions via the platform’s signing-key / public key discovery mechanism (not a shared JWT secret as the primary path), without committing real secrets.
- **FR-012**: Default runtime for the API MUST prefer the shared Supabase store when credentials are present; ephemeral memory store is optional and explicit.

### Key Entities *(include if feature involves data)*

- **Platform Project**: Hosted Postgres + Auth (+ Storage/Realtime) identified by URL and keys in env.
- **User Session**: Identity token issued by platform Auth; used by UI and validated by API.
- **Business Record**: Any security-domain row (asset, scan, finding, job, etc.) stored in Postgres with RLS.
- **Migration**: Versioned SQL change that evolves enums/tables/policies.
- **Service Principal**: Worker service token for reporting results through the API (not a substitute for user Auth).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After API restart, 100% of previously created test assets/jobs remain listable for an authorized user.
- **SC-002**: Unauthenticated callers receive denial on protected business APIs in 100% of smoke attempts.
- **SC-003**: Post-migration verification finds `jobs`, `patches`, and `tool_runs` present and `scans.team` selectable without column errors.
- **SC-004**: Privileged server key is absent from UI env and browser-exposed config in a credentials review checklist.
- **SC-005**: Analysts can complete sign-in and see dashboard data from the shared store in under 2 minutes on a configured lab project.
- **SC-006**: At least one Realtime-backed view updates after an API insert without a full page reload in the happy-path demo.

## Assumptions

- Existing `secure_dash` Auth UI and Supabase JS client remain the analyst-facing Auth integration.
- Existing red/blue domain schema from `001-red-blue-platform` migrations is the schema baseline to apply and extend.
- Workers continue to call the platform API with service tokens; they do not hold the database service role key.
- Lab project credentials live in root `.env` / `secure_dash/.env` and are never committed.
- Email/password is the primary lab Auth method; magic link/OAuth may already be enabled in the project and are in scope as “supported if configured,” not newly designed here.
- Storage buckets are out of MVP unless an evidence-upload story is scheduled; FR-010 is forward-looking.
- Constitution placeholders do not add extra gates beyond security isolation (DB secrets on API only).
