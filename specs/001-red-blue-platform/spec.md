# Feature Specification: Red/Blue Security Platform

**Feature Branch**: `001-red-blue-platform`

**Created**: 2026-08-03

**Status**: Draft

**Input**: User description: "Red/Blue Security Platform Architecture — monorepo where a central API owns all database access; the analyst dashboard talks only to that API; red-team and blue-team worker services run offensive and defensive tool pipelines and persist results exclusively through the API. Stages cover foundations, full CRUD, red MVP (surface recon), blue MVP (vuln scan + patches), deep profiles/monitors/attack chains, and hardening (allowlists, tests)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Analyst manages security data through the platform API (Priority: P1)

An authenticated security analyst uses the existing dashboard to create, view, update, and delete operational records (assets, scans, findings, threat events, attack chains, roles) without the dashboard writing directly to the business database. All business reads and writes go through the central platform API. Login and live dashboard refresh continue to work as they do today.

**Why this priority**: Without a single, authenticated data path, red/blue workers and the UI cannot share a trustworthy source of truth. This is the foundation for every later story.

**Independent Test**: With only the API and dashboard wired for assets (and parity for other entities), an analyst can sign in, list and create assets, and see dashboard KPIs load—without direct business-table writes from the browser.

**Acceptance Scenarios**:

1. **Given** an analyst is signed in, **When** they view the dashboard or asset list, **Then** data loads from the platform API and matches expected shapes for the UI.
2. **Given** an analyst is signed in, **When** they create or update an asset (or other supported entity), **Then** the change persists and is visible on refresh or via live update.
3. **Given** a user is not signed in, **When** they call the platform API or open a protected page, **Then** they receive unauthorized access denial and are redirected to sign-in for the UI.
4. **Given** an analyst without admin privileges, **When** they attempt a privileged delete (e.g., delete a scan), **Then** the action is denied; an admin can complete the same action.

---

### User Story 2 - Analyst launches a red-team reconnaissance job (Priority: P1)

An analyst selects one or more assets, chooses a red-team profile (starting with surface reconnaissance), and starts a job from the Scans experience. The platform queues and dispatches work to the red-team worker. The worker runs allowed recon tooling against in-scope targets, reports progress and results through the API, and the UI shows the scan moving from queued/running to completed with findings and threat events.

**Why this priority**: Offensive job execution is the core value of the red side of the platform and the first end-to-end worker path.

**Independent Test**: From the Scans page, start a red surface-recon job against seeded assets with a mocked or stubbed tool layer; verify job lifecycle, at least one finding/event in the UI, and no direct database credentials on the red worker.

**Acceptance Scenarios**:

1. **Given** an analyst has selected assets and a red profile, **When** they start a job, **Then** a job and related scan records are created in queued/dispatched state and appear in the UI.
2. **Given** a red job is running, **When** the worker reports progress and findings, **Then** scan status, findings, and threat events appear in the dashboard without requiring a full page reload for live-subscribed views.
3. **Given** a red job completes successfully, **When** the analyst opens findings/threats, **Then** they see results attributed to the red team (and source tool where applicable).
4. **Given** a job request with no assets selected, **When** the analyst submits, **Then** the request is rejected with a clear validation error.

---

### User Story 3 - Analyst runs blue-team scanning and remediates with patches (Priority: P2)

An analyst launches a blue-team vulnerability scan against selected assets. Findings appear with blue-team attribution. From a new Patches experience, the analyst can propose and apply remediation playbooks linked to findings; successful apply marks the patch applied and the finding remediated.

**Why this priority**: Completes the defensive half of the platform and closes the loop from detection to remediation; depends on the same job and API foundations as red.

**Independent Test**: Start a blue vuln-scan job (mocked tools), confirm blue-tagged findings, propose a patch, apply it, and verify finding status becomes remediated.

**Acceptance Scenarios**:

1. **Given** an analyst selects assets and a blue scan action, **When** the job completes, **Then** findings exist with blue-team attribution and tool source.
2. **Given** an open finding from a blue scan, **When** the analyst proposes a patch with a playbook, **Then** a patch appears in proposed status on the Patches page.
3. **Given** a proposed patch, **When** the analyst applies it successfully, **Then** patch status is applied and the linked finding becomes remediated.
4. **Given** a patch apply fails, **When** the result is recorded, **Then** patch status is failed and the finding remains open (or non-remediated).

---

### User Story 4 - Filter and observe red vs blue activity live (Priority: P2)

An analyst filters threats, findings, and dashboard KPIs by team (red or blue). New threat events and scan/finding updates continue to refresh live views without manual reload, after data is written through the API.

**Why this priority**: Separating offensive and defensive signal is required for operational clarity once both teams produce data.

**Independent Test**: Seed or create red and blue threat events; toggle team filters; insert a new threat event via the API and confirm the Threat Detection view updates without refresh.

**Acceptance Scenarios**:

1. **Given** mixed red and blue threat events exist, **When** the analyst filters by team, **Then** only matching records are shown and KPIs respect the filter.
2. **Given** the Threat Detection page is open with live updates enabled, **When** a new threat event is created via the API, **Then** the list updates without a manual reload.

---

### User Story 5 - Deep profiles, monitoring, and attack chains (Priority: P3)

An analyst can run deeper red profiles (multi-step emulation / defensive validation) that produce MITRE-tagged events and attack-chain steps. Blue continuous monitoring emits new threat events over time. Existing attack-chain views continue to render seeded and newly built chains.

**Why this priority**: Extends MVP pipelines into fuller kill-chain and continuous-defense demos after basic red/blue jobs work.

**Independent Test**: Run a deep red profile (with agent/tool stubs as needed) and a blue monitor tick; verify attack-chain steps and blue monitor events appear; confirm attack-chain page still renders seeded data.

**Acceptance Scenarios**:

1. **Given** a deep red profile job completes, **When** the analyst opens the related attack chain, **Then** ordered stages/steps link to findings or threat events where applicable.
2. **Given** blue monitoring is active for in-scope assets, **When** a monitor cycle detects an alert, **Then** a new blue-team threat event appears with status reflecting a new detection.
3. **Given** seeded attack-chain data exists, **When** the analyst opens the attack-chain page, **Then** steps still render correctly (regression).

---

### User Story 6 - Safe execution boundaries and service isolation (Priority: P1)

Operators require hard isolation: only the central API holds database credentials; red and blue workers authenticate with service credentials limited to reporting job progress and security results (not deleting assets or changing roles). Red pipelines refuse out-of-scope targets and record guardrail blocks instead of performing unsafe/destructive demo actions. The full stack starts via the project compose setup with health checks.

**Why this priority**: Trust and safety boundaries are non-negotiable for a dual-use offensive/defensive platform; must be true from the first worker MVP onward.

**Independent Test**: Configuration review shows only the API has DB credentials; service token cannot delete assets or change roles; out-of-scope target produces a guardrail event and no exploit attempt; compose health endpoints succeed.

**Acceptance Scenarios**:

1. **Given** red or blue worker configuration, **When** credentials are reviewed, **Then** neither worker holds database credentials; only the API does.
2. **Given** a valid service credential, **When** a worker creates findings or updates job status, **Then** the write succeeds; attempts to delete assets or change user roles are denied.
3. **Given** a red job targeting an asset outside the configured allowlist, **When** the pipeline runs, **Then** no exploit/destructive tool call occurs and a guardrail-blocked threat event is recorded.
4. **Given** the platform compose stack is started, **When** health checks run for API, red, and blue services, **Then** all report healthy.

---

### Edge Cases

- Job submitted with empty asset list → rejected before dispatch.
- Worker cannot reach the API temporarily → reporter retries at least once on transient failure, then surfaces job failure if still unsuccessful.
- Tool failure mid-pipeline → job and related scan marked failed with an error message retained.
- Analyst cancels a running job → further result writes are rejected or ignored consistently (conflict), and worker observes cancellation.
- Patch dry-run / propose vs apply → propose or dry-run does not change finding to remediated; only successful apply does.
- Unauthenticated or wrong credential type on API → clear denial (no data leak).
- Browser client attempts direct business-table writes → denied by data-access policy (reads may remain for live subscribe as designed).
- Schema migration on empty vs seeded database → applies cleanly; existing seed data remains readable.
- Demo/safe mode → destructive actions only produce guardrail-blocked events, never real destructive effect.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The platform MUST expose authenticated create/read/update/delete operations for assets, scans, findings, threat events, attack chains (and steps), user roles, jobs, and patches for authorized analysts/admins according to role.
- **FR-002**: The analyst dashboard MUST perform all business data reads and writes through the central platform API base URL; the identity provider client MUST be used only for sign-in and live subscription to change notifications.
- **FR-003**: Only the central API service MAY hold database credentials. Red-team and blue-team workers MUST NOT be configured with database access.
- **FR-004**: Workers MUST authenticate to the API with a service credential distinct from analyst sessions, and MUST be limited to inserting/updating findings, threat events, attack chains/steps, patches, tool-run audit records, and job/scan status—not deleting assets or changing user roles.
- **FR-005**: Analysts MUST be able to create jobs specifying team (red or blue), profile, and one or more asset identifiers; the system MUST create the job and related scan records and dispatch work to the matching worker.
- **FR-006**: Analysts MUST be able to list, inspect, and cancel jobs; cancelled or terminal jobs MUST not accept conflicting further progress writes.
- **FR-007**: Red-team pipelines MUST support at least the surface-reconnaissance profile for MVP, and later deep-emulation and defensive-validation profiles that emit findings, MITRE-oriented threat events, and optional attack-chain steps.
- **FR-008**: Blue-team pipelines MUST support vulnerability scanning that produces blue-attributed findings, continuous monitoring that emits blue threat events, and patch propose/apply workflows linked to findings.
- **FR-009**: Successful patch apply MUST set patch status to applied and linked finding status to remediated; failed apply MUST set patch status to failed without marking the finding remediated.
- **FR-010**: Operational records that are team-scoped (scans, findings, threat events, attack chains, jobs) MUST record red vs blue team attribution so the UI can filter and report by team.
- **FR-011**: The dashboard MUST provide a team toggle/filter on scans/job launch and on threats/findings/dashboard KPIs, and a Patches page to list and apply proposed patches.
- **FR-012**: Live dashboard views that today refresh on new threat events, scans, or findings MUST continue to update when those records are written through the API.
- **FR-013**: Unauthenticated API requests MUST be rejected; analyst credentials MUST NOT authorize service-only operations; admin-only actions MUST require an admin role.
- **FR-014**: Red pipelines MUST refuse targets outside a configured scope allowlist and MUST record a guardrail-blocked event instead of performing out-of-scope or destructive demo actions.
- **FR-015**: The system MUST retain optional per-tool execution audit (tool name, summary, outcome, timing) associated with jobs for hardening and investigation.
- **FR-016**: Platform services (API, red worker, blue worker, and optionally the UI) MUST start together via the project’s local orchestration with passing health/readiness checks.
- **FR-017**: Schema changes for jobs, patches, tool-run audit, team attribution, and related statuses MUST apply cleanly on empty and seeded databases without breaking readability of existing seed data.
- **FR-018**: The platform MUST publish a documented API contract that the dashboard types and job-create payloads conform to.
- **FR-019**: Existing enums and core entities (assets, scans, findings, threat events, attack chains/steps, user roles, severity/status vocabularies) MUST remain the system of record, extended rather than replaced.

### Key Entities

- **Asset**: A host or system under management (name, network identity, kind, criticality).
- **Job**: An async work unit requested by an analyst for red or blue execution (profile, status lifecycle, asset set, requester, errors, timing).
- **Scan**: A scan instance tied to a target/asset, optionally linked to a job and team, with status and findings count.
- **Finding**: A vulnerability or issue discovered on an asset/scan, with severity, status, evidence, remediation text, team and source tool.
- **Threat Event**: A timed security signal (technique, severity, status, payload), optionally linked to scan/asset/finding and team.
- **Attack Chain / Step**: Ordered narrative of an intrusion or validation path linking stages to events or findings.
- **Patch**: A remediation proposal or action against a finding/asset with playbook, status lifecycle, and evidence.
- **Tool Run**: Optional audit of a single tool invocation within a job.
- **User Role**: Mapping of users to application roles (e.g., analyst vs admin) governing privileged actions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of business-table create/update/delete operations from the analyst UI go through the platform API; identity client usage is limited to authentication and live update subscription (verified by review of UI data access).
- **SC-002**: Configuration review confirms zero red or blue worker processes hold database credentials; only the API service does.
- **SC-003**: An analyst can start a red surface-recon job from the Scans UI and, within the configured job timeout, see the scan reach completed with at least one finding or threat event visible without manual DB intervention.
- **SC-004**: An analyst can start a blue vulnerability scan and, within the job timeout, see at least one blue-attributed finding, propose a patch, and on successful apply see the finding marked remediated.
- **SC-005**: Unauthenticated API calls fail closed (denied); service credentials cannot delete assets or change roles; analysts cannot use service-only routes—verified by automated authorization checks.
- **SC-006**: With the Threat Detection view open, a newly created threat event becomes visible without manual page reload in normal interactive use.
- **SC-007**: Team filters on threats/findings/KPIs correctly separate red vs blue records in side-by-side checks (no cross-team leakage in filtered views).
- **SC-008**: Out-of-scope red targets produce a guardrail-blocked event and zero exploit/destructive tool invocations in demo/safe mode.
- **SC-009**: Local orchestration brings up API, red, and blue services with all health checks passing on a clean start.
- **SC-010**: Schema migration succeeds on both empty and seeded databases; previously seeded operational data remains readable afterward.
- **SC-011**: Documented API contract covers all listed entities; job-create payloads used by the UI match the contract in automated contract checks.
- **SC-012**: Automated acceptance suite covering API authZ, job lifecycle, red/blue reporting, patch remediation, UI auth gate, and compose health is green in CI before hardening stage exit.

## Assumptions

- Existing analyst authentication (current sign-in provider used by the dashboard) remains the identity source; the API validates analyst tokens issued by that provider.
- The existing dashboard application is retained and refactored for data access rather than replaced.
- Sibling offensive/defensive tool platforms remain external and are invoked by workers over the network; MVP may use stubs/mocks where live tools are unavailable.
- Default job profiles map from names already used in the UI (surface-recon, deep-emulation, defensive-validation for red; vuln scan / monitor / patch for blue).
- Browser clients may retain read-oriented live subscriptions to operational tables for refresh, while direct browser writes to those tables are revoked or prevented.
- Demo/safe mode is the default for destructive offensive actions until explicitly configured otherwise.
- Rate limiting and expanded allowlist governance are part of the hardening stage, not blockers for first red/blue MVP demos, but scope allowlist refusal is required whenever red jobs run against targets.
- Single-deployment local/dev orchestration is the primary delivery vehicle for acceptance; multi-tenant SaaS isolation is out of scope for this feature.
- Performance expectations follow typical internal security-console norms: interactive list/detail views feel responsive under normal lab data volumes (hundreds to low thousands of findings/events), not internet-scale multi-tenant load.
