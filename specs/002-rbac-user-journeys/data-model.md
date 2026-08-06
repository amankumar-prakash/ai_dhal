# Data Model: SentryOps Role-Based User Journeys

**Feature**: `002-rbac-user-journeys`  
**Date**: 2026-08-05  
**Source**: spec.md + Clarifications 2026-08-04 + delivery deltas (TEST_USER admin, live tools)

## Enums

### `app_role`

`user` | `security_analyst` | `security_manager` | `admin`  
Migration: `analyst` → `security_analyst`.

### `user_account_status`

`pending` | `active` | `disabled`

### `task_type`

`red` | `blue`

### `task_status`

`draft` | `assigned` | `in_progress` | `blocked` | `completed` | `reviewed` | `closed`

### `task_audit_action`

`created` | `assigned` | `started` | `started_on_behalf` | `blocked` | `unblocked` | `completed` | `reviewed` | `closed` | `reassigned` | `note_added` | `link_added`

### `task_link_kind`

`finding` | `scan`

### `notification_type`

`task_assigned` | `task_reassigned` | `task_completed_for_review` | `generic`

## Entities

### Profile (`profiles`)

| Field | Notes |
|-------|--------|
| `user_id` | PK = auth.users.id |
| `display_name`, `email` | |
| `status` | pending/active/disabled |
| `must_change_password` | boolean |
| `invite_expires_at`, `invite_consumed_at` | one-time credential |
| `last_login_at`, `created_at`, `updated_at` | |

**Rules**: Invite invalid if unused and `now() > invite_expires_at`. Password change clears `must_change_password`, sets consumed, `status=active`.

### User Role (`user_roles`)

One `app_role` per user in v1. Admin may set role to `admin`.

### Task (`tasks`)

| Field | Notes |
|-------|--------|
| `id` | UUID PK |
| `target`, `description`, `patch_scope` | NOT NULL; Manager-writable |
| `asset_id` | nullable FK assets |
| `task_type` | red/blue |
| `status` | default draft |
| `created_by` | Manager |
| `assignee_id` | Analyst or Manager self |
| `assigning_manager_id` | notify on complete |
| `linked_job_id` | nullable FK → `jobs.id` when tool page starts a platform job |
| timestamps | started/completed/closed/created/updated |

### Task status transitions

```text
draft ──assign──► assigned ──start──► in_progress ──complete──► completed ──review──► reviewed ──close──► closed
                      ▲                    │
                      │                    ├──block──► blocked ──► in_progress
                      └──reassign──────────┘
```

**Who may transition**

| Action | Analyst (assignee) | Manager |
|--------|--------------------|---------|
| assign / edit metadata | No | Yes |
| start | Own assigned | Any (audit `started_on_behalf` if not self) |
| block / unblock | Own | Yes |
| complete | Own | Any (audit) |
| reviewed / closed | **No** | Yes (audit) |
| reassign | No | Yes → status `assigned` |

### Task Note (`task_notes`)

| Field | Notes |
|-------|--------|
| `id`, `task_id`, `author_id` | |
| `body` | free-text NOT NULL |
| `created_at` | |

Authors: assignee Analyst or Manager with task access.

### Task Link (`task_links`)

| Field | Notes |
|-------|--------|
| `id`, `task_id`, `author_id` | |
| `kind` | finding \| scan |
| `ref_id` | UUID of finding or scan |
| `created_at` | |

Optional; does not create Findings. Validate ref exists when linking.

### Task Audit Event (`task_audit_events`)

`task_id`, `actor_id`, `action`, from/to status, from/to assignee, `message`, `created_at`.

### Notification (`notifications`)

`user_id`, `type`, `task_id`, `title`, `body`, `read_at`, `created_at`.

## Tool unlock predicate (application)

```text
can_open_red(analyst)  ⇔ ∃ task: assignee=analyst ∧ status=in_progress ∧ task_type=red
can_open_blue(analyst) ⇔ ∃ task: assignee=analyst ∧ status=in_progress ∧ task_type=blue
can_open_*(manager)    ⇔ true
```

## RLS intent

| Role | tasks / notes / links | threats/scans | profiles | admin provision |
|------|----------------------|---------------|----------|-----------------|
| User | deny | SELECT org RO | self | deny |
| Analyst | own tasks + notes/links | assigned-scope SELECT | self | deny |
| Manager | all task CRUD + notes/links | SELECT all | read for assign | deny |
| Admin | deny | deny | list via server | server Auth Admin |

## Bootstrap (TEST_USER)

No table for “setup wizard.” Script `scripts/bootstrap_admin.py`:

1. Read root `.env`: `TEST_USERNAME`, `TEST_PASSWORD`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY` (or service role), optional `DATABASE_URL`.
2. Create or update Auth user (email confirmed).
3. Upsert `profiles` (`status=active`, `must_change_password=false` for this lab seed).
4. Upsert `user_roles` → `admin` (replace legacy `analyst` if present).

Zero-Admin recovery: re-run the same script. Invited users (Admin Panel) still use `must_change_password=true` + invite TTL.

## Live tool provenance (001 tables)

Workers writing through API MUST set:

| Field | HexStrike recon | CAI deep plan |
|-------|-----------------|---------------|
| `findings.source_tool` | e.g. `nmap`, `nuclei` | `cai` |
| `threat_events.source_tag` | `hexstrike` | `cai` |
| `tool_runs.tool_name` | HexStrike tool id | `cai-plan` |
| `scans.source_service` | `red_team_backend` / `blue_team_backend` | same |

Stub mode (`HEXSTRIKE_STUB=1` / `CAI_STUB=1`) may keep `*-stub` tags for CI only.

## Relationships

```text
auth.users ── profiles
          └── user_roles (one app_role)

tasks ── task_notes
      ├── task_links ──► findings | scans
      ├── task_audit_events
      └── notifications → users
```
