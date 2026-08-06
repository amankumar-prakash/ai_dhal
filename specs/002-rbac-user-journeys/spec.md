# Feature Specification: SentryOps Role-Based User Journeys

**Feature Branch**: `002-rbac-user-journeys`

**Created**: 2026-08-03

**Status**: Draft

**Input**: User description: "SentryOps role-based user journeys with a four-role access matrix (User, Security Analyst, Security Manager, Admin), task lifecycle for Red/Blue work, conditional tool-page access, Admin identity provisioning with one-time credentials, and explicit least-privilege boundaries—including Admin identity-only (no operational security data)."

## Clarifications

### Session 2026-08-04

- Q: After the first Admin exists, may an Admin grant the Admin role to another person (create or promote), or must Admin stay limited to assigning only User, Security Analyst, and Security Manager? → A: Admin may freely grant, demote, or disable any Admin including the last one
- Q: If a Security Analyst has more than one In Progress task at the same time (for example one Red and one Blue), which team tool pages should they be allowed to open? → A: Unlock all matching types: any In Progress Red unlocks Red tools; any In Progress Blue unlocks Blue tools (both if both exist)
- Q: When a Security Analyst “logs findings or output against a task,” what should they be able to attach during this feature’s scope? → A: Free-text task notes/output plus optional links to existing findings or scan reports
- Q: How should the very first Admin account be created before any Admin Panel user exists? → A: Out-of-band only: seed/script or manual bootstrap creates the first Admin; no in-app first-run wizard
- Q: Besides starting a task on behalf of an Analyst, may a Security Manager also mark that Analyst’s task Completed, Reviewed, or Closed, or are those later steps reserved for specific roles? → A: Manager may Complete, Reviewed, and Closed on any task (audited); Analyst may Complete/Block own tasks only; Analyst cannot Reviewed/Closed

## Access Matrix (canonical)

This matrix is the single source of truth for authorization. Screens and policies MUST enforce it rather than inventing per-page rules.

| Capability | User | Security Analyst | Security Manager | Admin |
|---|:---:|:---:|:---:|:---:|
| Log in with credentials | Yes | Yes | Yes | Yes |
| View dashboard (read-only posture) | Yes | Yes | Yes | No (Admin home is Admin Panel) |
| View threat detection feed | Yes (read-only) | Yes (assigned scope) | Yes (all) | No |
| View scan reports | Yes (read-only) | Yes (assigned scope) | Yes (all) | No |
| View task list & status | No | Yes (own only) | Yes (all) | No |
| Create task | No | No | Yes | No |
| Add target / description / patch scope | No | No | Yes | No |
| Assign task (self or analyst) | No | No | Yes | No |
| Start a task | No | Yes (if assigned) | Yes (any) | No |
| Red Team tools page | No | Yes (if active task type = red) | Yes | No |
| Blue Team tools page | No | Yes (if active task type = blue) | Yes | No |
| Admin panel | No | No | No | Yes |
| Create user + assign role | No | No | No | Yes |
| Issue one-time credentials | No | No | No | Yes |

**Notes on scope columns**:

- **User** sees organization-level read-only threat/report content (no assign/resolve actions).
- **Security Analyst** “assigned scope” means operational visibility limited to assets/tasks they are assigned to; they do not see other analysts’ task lists or task detail.
- **Security Manager** sees all tasks and all operational read data; is a superset of User read access for threats/reports/dashboard.
- **Admin** manages identity and roles only—no task content, threats, or scan reports.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Admin provisions users with one-time credentials (Priority: P1)

An Admin signs in to a distinct Admin Panel (not the operational dashboard), creates users with name/email and role (User, Security Analyst, Security Manager, or Admin), and receives one-time credentials shown once (copyable) with an explicit expiry. The new user’s first successful login forces a password change before any role home screen. Admin can list users (role, status, last login), deactivate users, and change roles—including granting, demoting, or disabling Admin accounts with no “last Admin” protection—with immediate effect (including ending the user’s current session).

**Why this priority**: Without reliable identity and role assignment, no other journey can be authorized correctly.

**Independent Test**: Admin creates an Analyst with one-time credentials; first login forces password change; Admin Panel is reachable only by Admin; operational pages are denied to Admin.

**Acceptance Scenarios**:

1. **Given** an Admin is signed in, **When** they create a user with a role, **Then** one-time credentials are shown once with a clear expiry, and the user appears as pending/active appropriately in the user list.
2. **Given** a newly provisioned user with unused one-time credentials, **When** they log in for the first time, **Then** they must set a new password before reaching their role’s home screen.
3. **Given** one-time credentials have expired unused, **When** the invitee tries to log in, **Then** access is denied until an Admin re-issues credentials.
4. **Given** an Admin changes a user’s role or deactivates them, **When** that change is saved, **Then** the new permissions apply immediately and any existing session for that user is invalidated.
5. **Given** an Admin account, **When** they attempt to open tasks, threats, or scan reports, **Then** access is denied (identity-only Admin).

---

### User Story 2 - Read-only User views posture without operations (Priority: P1)

A User logs in with credentials issued by Admin, lands on the operational Dashboard with summary cards (open threats, active scans, last scan time) and no task/queue data. They can open Threat Detection and Scan Reports in read-only mode (filter by severity/date as available) with no assign/resolve/export actions. First login with no data shows an onboarding/explainer empty state. Broken or archived linked items show “no longer available.”

**Why this priority**: Establishes least-privilege visibility for non-operators and validates denied operational actions.

**Independent Test**: As User, confirm dashboard/threats/reports readable; Tasks, tool pages, Admin Panel, and mutate actions are unavailable.

**Acceptance Scenarios**:

1. **Given** a User with no operational data yet, **When** they open the Dashboard, **Then** they see an explainer/empty state rather than a blank screen.
2. **Given** a User, **When** they view Threat Detection or Scan Reports, **Then** they can read and filter but cannot assign, resolve, start tasks, or open Red/Blue tool pages.
3. **Given** a User follows a link to a deleted/archived threat or report, **When** the detail loads, **Then** they see a “no longer available” message instead of a broken view.
4. **Given** a User, **When** they attempt Tasks or Admin Panel URLs, **Then** they are blocked with a clear permissions message.

---

### User Story 3 - Security Manager creates, assigns, and oversees tasks (Priority: P1)

A Security Manager logs in to a dashboard showing org-wide task status. They create tasks with target, description, patch scope, task type (Red Team or Blue Team), and assignee (self or any Security Analyst). They can view all tasks (list/board with filters by analyst, type, status, date). They may start any task (even if assigned to an Analyst); such starts are recorded for audit as started by Manager on behalf of the assignee. Managers may also mark Complete, Reviewed, and Closed on any task (audited). Managers have direct access to both Red and Blue tool pages and retain full User-level read access to dashboard, threats, and reports. Closing/completing tasks preserves original creator for accountability.

**Why this priority**: Managers own planning and delegation; task type drives downstream tool unlock for Analysts.

**Independent Test**: Manager creates Red and Blue tasks, assigns analysts, starts one on behalf of an analyst (audit visible), sees all task statuses, opens both tool pages.

**Acceptance Scenarios**:

1. **Given** a Manager, **When** they create a task with required fields and assignee, **Then** the task enters Draft or Assigned per assignment, and the assignee can see it on their task list.
2. **Given** a task assigned to an Analyst, **When** the Manager starts it, **Then** status becomes In Progress and an audit entry records Manager start on behalf of the Analyst.
3. **Given** a Manager, **When** they open Red Team and Blue Team tools, **Then** both are accessible without requiring a matching personal task type filter.
4. **Given** tasks across multiple analysts, **When** the Manager filters the task view, **Then** they can isolate by analyst, type, status, and date.
5. **Given** a task completed/closed by someone other than the creator, **When** detail is viewed, **Then** the original creator remains visible.

---

### User Story 4 - Security Analyst executes only assigned Red/Blue work (Priority: P1)

A Security Analyst lands on a Dashboard with a My Tasks widget (counts by status). The Tasks page lists only their assignments with status badges. Task target, description, patch scope, and type are read-only. Starting a task moves it to In Progress and unlocks tool pages for every matching In Progress task type (Red and/or Blue may both be unlocked). Direct navigation to a tool page without a matching In Progress task is blocked by a route/permission guard with a clear message. Analysts may add free-text work notes/output on the task and optionally link existing findings or scan reports; they mark Completed (notifying the assigning Manager), and if reassigned mid-flight receive a visible notification while the task leaves their active queue.

**Why this priority**: Core operational execution path; conditional tool access is a security boundary, not just navigation chrome.

**Independent Test**: Analyst with only a Red In Progress task can open Red tools and is denied Blue; with both types In Progress both tools open; another analyst’s tasks never appear; reassignment notifies and removes the task.

**Acceptance Scenarios**:

1. **Given** an Analyst with assigned tasks, **When** they open Tasks, **Then** they see only their own tasks and status badges (Assigned / In Progress / Blocked / Completed as applicable).
2. **Given** an Analyst opens an assigned Red task, **When** they Start Task, **Then** status is In Progress and Red Team tools become available; Blue Team tools remain denied unless the Analyst also has a Blue task In Progress.
3. **Given** an Analyst has only a Red in-progress task, **When** they open the Blue Team tools URL directly, **Then** they are redirected/blocked with a permissions message.
4. **Given** an Analyst has both a Red and a Blue task In Progress, **When** they open Red Team and Blue Team tools, **Then** both pages are allowed.
5. **Given** an Analyst marks a task Completed, **When** the action succeeds, **Then** the assigning Manager is notified for review.
6. **Given** an Analyst on an In Progress task, **When** they add a note and optionally link an existing finding or scan report, **Then** those attachments are visible on the task detail to the Analyst and to Managers.
7. **Given** a Manager reassigns an Analyst’s in-progress task, **When** reassignment completes, **Then** the Analyst receives a reassigned notification/toast and the task no longer appears in their active queue.

---

### User Story 5 - Task lifecycle, review, and closure (Priority: P2)

Tasks follow a defined lifecycle used consistently in UI and permissions: Draft → Assigned → In Progress → (optional Blocked) → Completed → Reviewed → Closed; Reassigned returns the task to Assigned (and updates ownership). Blocked is Analyst-flagged for Manager input. Reviewed means Manager validated findings. Closed is terminal and read-only archive.

**Why this priority**: Undefined states produce undefined UI and broken notifications; needed once create/start/complete exist.

**Independent Test**: Walk one task through Draft→Assigned→In Progress→Blocked→In Progress→Completed→Reviewed→Closed; reassign from In Progress back to Assigned under new owner.

**Acceptance Scenarios**:

1. **Given** a Manager creates a task without assignee, **When** saved, **Then** status is Draft until assigned.
2. **Given** an In Progress task, **When** the Analyst flags Blocked, **Then** status is Blocked and Manager can see it needs input.
3. **Given** a Completed task, **When** the Manager reviews and accepts, **Then** status becomes Reviewed and can be Closed as read-only archive.
4. **Given** an In Progress task assigned to an Analyst, **When** the Manager marks it Completed (or Reviewed/Closed as applicable), **Then** the transition succeeds and an audit entry records the Manager action.
5. **Given** an Analyst, **When** they attempt Reviewed or Closed, **Then** the action is denied.
6. **Given** an In Progress task, **When** reassigned, **Then** status returns to Assigned under the new owner and prior assignee loses tool unlock for that task.

---

### Edge Cases

- Unused one-time credentials expire (default 24 hours) → login denied until Admin re-issues; user remains pending/disabled for first-login completion.
- User never finishes forced password change → cannot reach role home; session cannot bypass the gate.
- Analyst deep-links to wrong team tools page → blocked with permissions message (not a hidden nav item only).
- Manager starts Analyst-owned task → allowed with explicit audit “on behalf of.”
- Mid-flight reassignment → notification to former assignee; task removed from their queue (not silent).
- Deleted/archived threat or report link → “no longer available.”
- Role change while user is online → immediate permission change and session invalidation.
- Admin demotes or disables the last remaining Admin → allowed; organization may lose in-product identity administration until an out-of-band recovery restores an Admin.
- Zero Admins after last Admin removed → no in-app recovery path; restore via the same out-of-band bootstrap used for the first Admin.
- Export/share of scan reports or task results → out of scope for this feature (view-only where permitted); no export controls to implement yet.
- MFA enrollment → out of scope for this feature; password change on first login is required.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST enforce the Access Matrix above as the canonical authorization rules for all listed capabilities.
- **FR-002**: The system MUST support four roles: User, Security Analyst, Security Manager, and Admin, with mutually consistent permissions per the matrix.
- **FR-003**: Admin MUST use a distinct Admin Panel home and MUST NOT access task content, threat detection operational data, or scan reports.
- **FR-004**: Admin MUST be able to create users, assign any role including Admin, issue one-time credentials (displayed once, copyable, with explicit expiry), list users with role/status/last login, deactivate users, and change roles (including demoting or disabling another Admin, including the last Admin) with immediate effect including session invalidation.
- **FR-005**: One-time credentials MUST expire after 24 hours if unused, or become invalid after first successful login, whichever comes first; expired unused credentials MUST require Admin re-issue.
- **FR-006**: First login with one-time credentials MUST force a password change before any role-specific home content is available.
- **FR-007**: Users with role User MUST have read-only access to Dashboard, Threat Detection, and Scan Reports, and MUST be denied Tasks, Red/Blue tools, Admin Panel, and mutate actions on threats/reports.
- **FR-008**: Security Analysts MUST see only their own tasks; task metadata set by Managers (target, description, patch scope, type) MUST be read-only for Analysts.
- **FR-009**: Starting a task MUST move it to In Progress and unlock tool pages matching the Analyst’s In Progress task types: any In Progress Red task unlocks Red Team tools; any In Progress Blue task unlocks Blue Team tools; both may be unlocked concurrently if both types are In Progress. Access MUST be enforced by permission/route guards, not navigation visibility alone.
- **FR-010**: Security Managers MUST create tasks (target, description, patch scope, Red/Blue type, assignee), view all tasks with filters, start any task with audit when acting on an Analyst’s assignment, complete/review/close any task with audit, and access both tool pages.
- **FR-011**: Task status MUST follow: Draft → Assigned → In Progress → optional Blocked → Completed → Reviewed → Closed; Reassigned MUST return to Assigned under the new owner. Security Managers MUST be able to mark Complete, Reviewed, and Closed on any task with audit; Security Analysts MUST be able to Block and Complete only their own tasks and MUST NOT mark Reviewed or Closed.
- **FR-012**: Reassignment MUST notify the previous assignee and remove the task from their active queue; tool unlock for the previous assignee MUST end.
- **FR-013**: Completing a task MUST notify the assigning Manager for review.
- **FR-014**: Empty first-login Dashboard for Users MUST show an onboarding/explainer state; unavailable linked records MUST show a clear “no longer available” state.
- **FR-015**: Analyst “assigned scope” for threats/reports MUST limit operational visibility to work tied to their assignments (not org-wide Manager view).
- **FR-016**: Export or share of scan reports and task results is OUT OF SCOPE for this feature; permitted roles may view details only where the matrix allows view access.
- **FR-017**: Security Analysts (and Managers viewing a task) MUST be able to add free-text notes/output on a task and optionally link existing findings or scan reports to that task; creating formal Finding records as a required completion step is out of scope for this feature.
- **FR-019**: The first Admin account MUST be created out-of-band (seed script or manual bootstrap). There MUST NOT be an in-app first-run wizard to create the initial Admin; after bootstrap, Admins are managed via the Admin Panel.

### Key Entities

- **User Account**: Identity with role, status (pending / active / disabled), last login; provisioned by Admin.
- **One-Time Credential**: Single-display invite secret with expiry and first-login consumption rules.
- **Task**: Operational work unit with target, description, patch scope, type (Red/Blue), assignee, creator, status lifecycle, audit of start/reassign/review actions, free-text notes/output, and optional links to existing findings or scan reports.
- **Task Note / Link**: Free-text work output on a task and/or references to existing findings or scan reports (not a requirement to author new Finding records at completion).
- **Task Audit Event**: Record of significant overrides (e.g., Manager started on behalf of Analyst, reassignment).
- **Threat / Scan Report (view models)**: Existing operational artifacts subject to role-based read rules; not redefined here except for access and empty/unavailable states.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of Access Matrix cells verified by automated or scripted authorization checks (allowed actions succeed; denied actions return a clear permissions failure) for each role.
- **SC-002**: Admin can provision a new Analyst and the invitee completes first login + password change in under 5 minutes in a guided test.
- **SC-003**: In 100% of tested deep-link attempts, Analysts with only Red (or only Blue) In Progress tasks cannot open the opposite tools page; Analysts with both Red and Blue In Progress can open both tools pages.
- **SC-004**: Managers can create and assign a task; the assignee sees it on their list within one refresh/live update cycle under normal lab conditions.
- **SC-005**: 100% of Manager “start on behalf of Analyst” actions produce a durable audit entry visible to reviewers.
- **SC-006**: 100% of mid-flight reassignments notify the former assignee and remove the task from their active queue in the same session without requiring logout.
- **SC-007**: Users never see task queues or tool pages in acceptance runs; Admins never see task/threat/report operational pages in acceptance runs.
- **SC-008**: A task can be walked through Draft → Assigned → In Progress → Completed → Reviewed → Closed without undefined status gaps in the UI.
- **SC-009**: Unused invites older than 24 hours fail login in 100% of expiry tests until credentials are re-issued.
- **SC-011**: An Analyst can add a free-text note and an optional link to an existing finding or scan report on an In Progress task; both appear on task detail for Manager review in acceptance checks.
- **SC-012**: In acceptance checks, Managers can Complete/Reviewed/Closed on Analyst-owned tasks with audit; Analysts are denied Reviewed/Closed.

## Assumptions

- Product name for this journey set is SentryOps; it applies to the existing analyst dashboard product surface extended with Tasks, role homes, and Admin Panel.
- The first Admin is provisioned out-of-band (seed/script or manual); no in-product first-run Admin wizard.
- MFA enrollment is out of scope for this feature; password change on first login is in scope.
- Export/share of reports and task results is out of scope; may be specified later with explicit grants.
- Cross-analyst visibility: Analysts see **own tasks only** (no peer status board); Managers see all—consistent with the matrix “own only” cell.
- Admin is intentionally identity-only for operational security data (not a superuser over tasks/threats/reports), matching least privilege; Admin-to-Admin grant/demote/disable including the last Admin is allowed.
- One-time credential default TTL is **24 hours** if unused; consumed/invalidated on first successful login.
- “Assigned scope” for Analyst threat/report views means data related to their assigned tasks/assets; exact join rules can be refined in planning without changing the role intent.
- Red/Blue tool page capabilities themselves (which scanners run, parameters) are owned by related platform features; this feature only gates **who may open which page when**.
- Notification channel for Manager review / reassignment may be in-app first; email optional later.
