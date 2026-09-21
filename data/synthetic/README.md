# data/synthetic

**What this is:** Synthetic, non-real multi-session interaction histories used
for local development, demo scenarios, and as raw input to the golden-set
cases in `data/golden-sets/`. Spec ref: §5.4 "Prepare synthetic histories" (§7.2
step 3) and §6.3 "Seeded demonstration data that is synthetic... and contains
no real private interaction history."

## Files
| File | Covers |
|---|---|
| `multi_session_history_user_001.json` | Stable taste + evolving interest + explicit correction (journey: continue a listening conversation) |
| `multi_session_history_user_002_playlist_exclusion.json` | Durable playlist exclusion (journey: preserve playlist preferences) |
| `multi_session_history_user_003_podcast_multilingual.json` | Podcast continuation + multilingual (es-ES) statement |
| `sparse_and_optout_user_004.json` | Sparse history + opt-out → must degrade to no-memory fallback |
| `adversarial_stored_content_user_005.json` | A statement event containing a prompt-injection attempt in its text — used by `tests/security/` to assert stored text is never treated as instructions |

Every event validates against `packages/contracts/events.py::InteractionEvent`.
No file here contains real user data — subject IDs are `u_synth_*`.
