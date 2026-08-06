# Route Guard Contract

Guards run on every navigation. Denied → redirect + permissions message.

| Route | Allowed when |
|-------|----------------|
| `/auth` | Anonymous or forced password-change flow |
| `/` (ops dashboard) | Role ∈ {user, security_analyst, security_manager}; **deny admin** → `/admin` |
| `/threats`, `/scans`, `/attack-chain` | Ops roles only; Admin denied |
| `/tasks`, `/tasks/:id` | `security_analyst` or `security_manager` |
| `/tools/red` | `security_manager` **OR** (`security_analyst` ∧ ∃ own `in_progress` ∧ `task_type=red`) |
| `/tools/blue` | `security_manager` **OR** (`security_analyst` ∧ ∃ own `in_progress` ∧ `task_type=blue`) |
| `/admin` | `admin` only |

## Post-login gate

`profiles.must_change_password = true` → only password-change completion allowed.

## Invite expiry gate

`pending` + unused invite past `invite_expires_at` → reject login; Admin re-issue required.

## Notes

- Concurrent Red + Blue In Progress ⇒ both `/tools/red` and `/tools/blue` allowed for that Analyst.
- First Admin is never created via these routes (out-of-band bootstrap / `TEST_USERNAME` seed only).
- Guards SHOULD call `GET /api/v1/me` (see [live-tools-and-identity.md](./live-tools-and-identity.md)) rather than trusting JWT claims alone.
