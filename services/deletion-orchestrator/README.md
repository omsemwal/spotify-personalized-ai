# services/deletion-orchestrator

**What this is:** Cross-store erasure. Owns the final 2 of the 10 required APIs.

## APIs owned (§7.3)
| Endpoint | Behavior |
|---|---|
| `DELETE /v1/memories/{id}` | Starts a deletion job across every connected store, returns `job_id` immediately (`202 Accepted`). |
| `GET /v1/deletions/{job_id}` | Reports **per-store** status — `graph`, `vector`, `cache`, `operational_store`, `backup_policy` — never a single boolean. A partial failure is visible, never silently swallowed (§5.4). |

## Why per-store status, not one boolean
> "Revokes retrieval eligibility, propagates deletion to graph and vector
> stores, and confirms completion status." — §5.3 journey table
> "prevent silent partial completion" — §7.6 Correction and deletion

If graph deletion succeeds but vector deletion fails, `GET /v1/deletions/{job_id}`
must show that distinction so operators can retry the specific failed store
rather than re-running the whole job blind.

## Backups
`backup_policy` is reported as `scheduled`, not `completed` — backups erase on
their own retention cycle per the backup system's own policy, and this is
tracked rather than claimed as instantly done (§5.4, §5.5 Deployment readiness).

## Audit trail vs. hard delete
The `operational_store` entry tombstones (marks deleted, retains for audit)
rather than hard-deletes feedback/audit rows — cross-referenced against
`packages/policy-engine`'s retention rules so audit history required for
compliance isn't destroyed by a user-initiated memory deletion.
