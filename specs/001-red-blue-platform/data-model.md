# Data Model: Red/Blue Security Platform

**Feature**: `001-red-blue-platform`  
**Date**: 2026-08-03  
**Source**: Feature spec Key Entities + existing Supabase migration + planned extensions

## Enums

### Existing (unchanged)

| Enum | Values (as used by product) |
|------|-----------------------------|
| `severity_level` | Existing severity vocabulary |
| `finding_status` | Includes transitions such as `open` → `investigating` → `remediated` (and other existing values) |
| `threat_status` | Existing threat statuses (e.g. `new`, …) |
| `scan_status` | Existing scan lifecycle |
| `chain_stage` | Existing attack-chain stages |
| `app_role` | e.g. analyst / admin via `has_role` |

### New

| Enum | Values |
|------|--------|
| `team_side` | `red`, `blue` |
| `job_status` | `queued`, `dispatched`, `running`, `completed`, `failed`, `cancelled` |
| `patch_status` | `proposed`, `approved`, `applied`, `failed`, `rolled_back` |

## Entities

### Asset (existing)

| Field | Notes |
|-------|--------|
| `id` | UUID PK |
| `name` | Required |
| `hostname`, `ip_address` | Network identity |
| `kind`, `criticality` | Classification |
| `created_at` | Timestamp |

**Validation**: Name required; used as job targets via `asset_ids`.

**Relationships**: 1:N scans, findings, threat_events, patches.

---

### Scan (existing + extensions)

| Field | Notes |
|-------|--------|
| `id` | UUID PK |
| `target` | Display/target string |
| `asset_id` | FK → assets |
| `profile` | e.g. `surface-recon`, `deep-emulation`, `defensive-validation`, blue profiles |
| `status` | `scan_status` |
| `started_at`, `finished_at`, `findings_count`, `created_by`, `created_at` | Existing |
| `team` | **NEW** `team_side NOT NULL DEFAULT 'red'` |
| `job_id` | **NEW** UUID → jobs (nullable for legacy rows) |
| `source_service` | **NEW** text (e.g. `red_team_backend`, `blue_team_backend`) |

**Relationships**: N:1 asset, N:1 job (optional), 1:N findings / threat_events; may own attack_chains.

---

### Finding (existing + extensions)

| Field | Notes |
|-------|--------|
| Core fields | `scan_id`, `asset_id`, `cve`, `title`, `severity`, `cvss`, `status`, `remediation`, `evidence`, `detected_at`, `resolved_at`, `created_at` |
| `team` | **NEW** `team_side` |
| `source_tool` | **NEW** text (e.g. `nmap`, `nuclei`, `trivy`) |

**State transitions (status)**: `open` → `investigating` → … → `remediated` (on successful patch apply). Failed patch must not force remediated.

**Relationships**: N:1 scan/asset; 0:N patches; optional threat_events / chain steps.

---

### Threat Event (existing + extensions)

| Field | Notes |
|-------|--------|
| Core fields | `scan_id`, `asset_id`, `finding_id`, `technique`, `technique_name`, `description`, `source_ip`, `severity`, `status`, `source_tag`, `raw_payload`, `occurred_at` |
| `team` | **NEW** `team_side` (may default from `source_tag` mapping) |

**Special**: Guardrail blocks use identifiable tagging (e.g. technique/source indicating `blocked_by_guardrail`).

**Realtime**: Table remains in realtime publication for UI live updates.

---

### Attack Chain / Attack Chain Step (existing + extensions)

**Chain**: `id`, `name`, `scan_id`, `created_at`, **`team` (NEW)**.

**Step**: `id`, `chain_id`, `stage`, `sequence`, `title`, `severity`, `threat_event_id`, `finding_id`, `created_at`.

**Validation**: `sequence` ordered within chain; stages use `chain_stage`.

---

### User Role (existing)

| Field | Notes |
|-------|--------|
| `id`, `user_id`, `role`, `created_at` | UNIQUE(`user_id`, `role`) |

**AuthZ**: Self-read retained; mutations admin-only via API (service token denied).

---

### Job (new)

| Field | Notes |
|-------|--------|
| `id` | UUID PK |
| `team` | `team_side` NOT NULL |
| `profile` | text NOT NULL |
| `status` | `job_status` DEFAULT `queued` |
| `asset_ids` | uuid[] NOT NULL — **must be non-empty** |
| `requested_by` | auth user UUID |
| `dispatcher_payload` | jsonb DEFAULT `{}` |
| `error` | text |
| `started_at`, `finished_at`, `created_at` | timestamps |

**State transitions**:

```text
queued → dispatched → running → completed
                            ↘ failed
         ↘ cancelled (from queued|dispatched|running)
```

Terminal: `completed`, `failed`, `cancelled`. Further progress writes on terminal/cancelled → **409 Conflict**.

**Relationships**: 1:N scans, 1:N tool_runs.

---

### Patch (new)

| Field | Notes |
|-------|--------|
| `id` | UUID PK |
| `finding_id` | FK findings ON DELETE CASCADE |
| `asset_id` | FK assets ON DELETE SET NULL |
| `title` | NOT NULL |
| `playbook` | NOT NULL (e.g. `upgrade-package`, `firewall-rule`) |
| `status` | `patch_status` DEFAULT `proposed` |
| `evidence` | jsonb DEFAULT `[]` |
| `created_by`, `applied_at`, `created_at` | |

**State transitions**:

```text
proposed → approved → applied
                   ↘ failed
         → applied (if approve optional)
applied → rolled_back (optional later)
```

**Side effect**: Transition to `applied` MUST set linked finding status to `remediated`. Transition to `failed` MUST leave finding non-remediated.

---

### Tool Run (new)

| Field | Notes |
|-------|--------|
| `id` | UUID PK |
| `job_id` | FK jobs ON DELETE CASCADE |
| `team` | `team_side` |
| `tool_name` | NOT NULL |
| `command_summary` | text |
| `exit_code` | int |
| `raw_output` | jsonb |
| `started_at`, `finished_at` | |

**Purpose**: Audit of individual tool invocations (hardening / investigation).

## RLS / Access policy (data layer)

| Principal | Operational tables | user_roles |
|-----------|-------------------|------------|
| Browser `authenticated` | SELECT only (writes revoked) | Self-read; admin via `has_role` |
| API `service_role` | Full CRUD as implemented in API AuthZ | As implemented (admin routes) |
| Service token (via API) | Insert/update findings, events, chains/steps, patches, tool_runs, job/scan status | Denied for role changes; asset delete denied |

## Relationship diagram

```text
User ──requested_by──► Job ──┬──► Scan ──► Finding ──► Patch
                             │         │
                             │         └──► ThreatEvent
                             │
                             └──► ToolRun

Scan ──► AttackChain ──► AttackChainStep ──► (Finding | ThreatEvent)
Asset ◄── Scan | Finding | ThreatEvent | Patch
```
