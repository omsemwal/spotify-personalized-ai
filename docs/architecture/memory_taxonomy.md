# Memory Taxonomy

**What this is:** the definitive list of what this system is allowed to
remember. Five types, and nothing else.

**Why it exists:** §7.2 step 1 of the requirements says to define the taxonomy
*before* building against it — *"Document examples, counterexamples,
sensitivity, retention, and retrieval eligibility for each type."* Everything
downstream agrees with this document: the policy registry
(`packages/policy-engine/registry.py`), the extraction prompt
(`services/memory-processor/llm_extractor.py`), the graph schema, and the
labels shown in the two web apps.

**Why it is deliberately small:** §4, Chief Product Officer — *"Do not widen the
stored-memory taxonomy until the evaluation data supports it."* Adding a sixth
type is a governed change, not a code change. See "Changing this document" at
the end.

---

## The five types at a glance

| Type | One-line meaning | Durable? | Retention | Confirmation needed |
|---|---|---|---|---|
| `explicit_preference` | The user said they want something, lastingly | yes | 365 days | no |
| `exclusion` | The user said they do **not** want something | yes | 365 days | no |
| `correction` | The user is fixing or retracting something we stored | yes | 365 days | no |
| `candidate_preference` | A preference that is only implied, or explicitly temporary | not yet | 90 days | **yes** |
| `episode` | A single thing that happened, with no preference stated | no | 30 days | no |

The distinction that matters most is the one the Data Science Lead drew in §4:

> *"Played focus music this morning"* is an **episode**. *"Prefers low-vocal
> focus playlists while working"* may become a **durable preference** only after
> explicit confirmation or repeated supporting evidence.

An episode is a fact about *an event*. A preference is a fact about *the person*.
Promoting one to the other is the single most consequential decision this system
makes, and it never happens silently.

---

## 1. `explicit_preference`

**Definition.** The user directly stated a lasting taste, want or habit, in
their own words, with no time limit attached.

**Example.**
> "I like low-vocal music when I'm working."

This is durable: it describes how they want things to be, not what happened
once. It is stated, not guessed.

**Counter-examples — these are NOT `explicit_preference`:**

| Text | Why not | Correct type |
|---|---|---|
| "Play something low-vocal" | A request for right now, not a statement about lasting taste | `episode` |
| "I'm into lo-fi this week" | Explicitly time-bounded by "this week" | `candidate_preference` |
| *(user skipped three loud tracks in a row)* | Behaviour, not a statement. The user never said anything. | `episode` |
| "I don't want podcasts in my mixes" | This is a negative statement | `exclusion` |
| "Actually, I meant instrumental, not acoustic" | This retracts something earlier | `correction` |

**Sensitivity:** `normal`.
**Retention:** 365 days from `recorded_at`.
**Allowed purposes:** `continuity`, `personalization`, `correction`.
**Retrieval eligibility:** eligible on any surface whose policy includes one of
those purposes, while `status == "active"` and within retention.
**Confidence:** starts high (the user said it outright). Repetition raises it;
a `correction` supersedes it outright regardless of confidence.
**How it ends:** superseded by a `correction`, expired by retention, or deleted
by the user.

---

## 2. `exclusion`

**Definition.** The user directly stated something they do not want. Kept as its
own type rather than as a negative preference, because it has to behave
differently: an exclusion must be applied even when it is not "relevant" to the
current intent.

**Example.**
> "Never put true crime in my podcast recommendations."

**Counter-examples:**

| Text | Why not | Correct type |
|---|---|---|
| "Not this one" *(while skipping a track)* | Rejects one item, not a category | `episode` |
| "I'm not in the mood for this today" | Time-bounded, and about mood | `candidate_preference`, and see §"Prohibited inferences" |
| "I used to hate jazz but it's growing on me" | This revises a previous position | `correction` |

**Sensitivity:** `normal`.
**Retention:** 365 days.
**Allowed purposes:** `personalization`, `safety`.
**Retrieval eligibility:** the widest of any type. An exclusion should be
retrievable whenever the surface could plausibly produce the excluded thing —
getting this wrong is worse than a missed preference, because the system
actively does the thing the user asked it not to do.
**How it ends:** superseded by a `correction` ("actually true crime is fine
now"), expired, or deleted.

---

## 3. `correction`

**Definition.** The user is telling us that something we remembered is wrong, or
no longer applies. The highest-authority type in the system.

**Example.**
> "No — I said I like *instrumental*, not acoustic."

**What makes it special.** §4, Graph Platform Lead: *"Corrections should
supersede prior facts; they should not silently overwrite history."* A
correction does two things at once:

1. closes the `valid_to` of the fact it corrects, setting its status to
   `superseded`, and
2. creates the new fact, linked back to the one it replaced.

The old fact stays in the graph and stays visible in the audit trail. It just
stops being retrievable.

**Counter-examples:**

| Text | Why not | Correct type |
|---|---|---|
| "I don't like that" *(about a track just played)* | Rejects one item; no stored memory is being corrected | `episode` |
| "Stop suggesting jazz" | A new negative statement, not a fix to a stored one | `exclusion` |
| *(user edits a memory in the memory-controls UI)* | Same effect, but it arrives through the correction API, not through extraction | `correction`, created directly |

**Sensitivity:** `normal`.
**Retention:** 365 days.
**Allowed purposes:** `continuity`, `correction`.
**Confidence:** always 1.0. The user is the authority on their own preferences.
**Critical rule:** a correction is never produced by inference. Only an explicit
user signal — a statement or a UI action — can create one.

---

## 4. `candidate_preference`

**Definition.** Something that *looks* like a durable preference but has not
earned that status yet. Two ways to land here:

1. **Implied, not stated.** The behaviour suggests a preference, but the user
   never said it.
2. **Explicitly temporary.** The user did state it, but bounded it in time —
   "this week", "while I'm studying", "for now", "today".

**Examples.**
> "I'm going to keep it lo-fi while I'm studying." *(temporary)*
> *(user has saved six ambient tracks in a row)* *(implied)*

**Why this type exists.** It is the holding pen that stops the system from
hardening a guess into a fact. §5.3 — *"Combines explicit statements and
repeated evidence, creates a confidence-scored graph relationship, and surfaces
it only for relevant requests."*

**How it gets promoted.** Only two routes, and both are explicit:

- the user confirms it (`requires_explicit_confirmation = true` in the registry), or
- repeated supporting evidence accumulates and crosses the confidence threshold.

It is **never** promoted because a model asserted it, and never because it was
used successfully in a response. §7.5 — *"never write a new durable fact solely
because the model generated it in a response."*

**Counter-examples:**

| Text | Why not | Correct type |
|---|---|---|
| "I like lo-fi" | Stated, unbounded — this is durable | `explicit_preference` |
| *(user played one ambient track)* | One event is not a pattern | `episode` |
| "I'm feeling low today, play something gentle" | See "Prohibited inferences" below | no memory |

**Sensitivity:** `normal`, but treated more cautiously at retrieval.
**Retention:** 90 days — shorter on purpose. If a guess has not been confirmed
in three months, it should lapse rather than harden.
**Allowed purposes:** `personalization` only. Not `continuity` — we do not build
conversational continuity on top of something the user never said.
**Retrieval eligibility:** eligible, but ranks below explicit types, and should
be described to the user in hedged language ("it looks like you often…") rather
than asserted.

---

## 5. `episode`

**Definition.** One thing that happened. A play, a save, a follow, a skip, a
single request. No claim about lasting preference.

**Example.**
> "Played *Weightless* on the focus playlist at 09:12."

**What it is for.** Recent-behaviour context. §5.3, "Resume podcast discovery" —
the system needs to know which episodes were already heard so it can continue
rather than restart. That is an episodic question, not a preference question.

**Counter-examples:**

| Text | Why not | Correct type |
|---|---|---|
| "I always start my day with this playlist" | A stated habit, unbounded | `explicit_preference` |
| *(user skipped the same artist eleven times)* | A pattern this strong is evidence | `candidate_preference` |

**Sensitivity:** `normal`.
**Retention:** 30 days — the shortest. Episodes age out fastest because their
value is almost entirely recency.
**Allowed purposes:** `continuity`, `personalization`.
**Retrieval eligibility:** eligible, but weighted heavily toward recency and
capped so episodes cannot crowd out stated preferences in the context package.
**Volume warning:** this is the highest-volume type by far. §5.4 — *"Separate
raw event retention from memory retention; not every event becomes a
retrievable memory."* Most play and skip events should produce **no memory at
all**. An episode is written when it is plausibly useful later, not by default.

---

## Prohibited inferences

These are not a sixth memory type. They are things the system must refuse to
store, whatever form they arrive in.

§4, Privacy Lead: *"Mood patterns can be sensitive or easily misread. We should
not store inferred emotional state as a durable profile by default."*

The blocked categories, mirrored in
`packages/policy-engine/registry.py::BLOCKED_INFERRED_CATEGORIES`:

| Category | Example of what must not be stored |
|---|---|
| `emotional_state` | "user is sad" |
| `mood_inference` | "user prefers melancholic music when down" |
| `mental_health_inference` | anything about anxiety, depression, therapy |
| `medical_inference` | anything about conditions, medication, symptoms |
| `political_affiliation_inference` | anything inferred from podcast topics |

**The rule.** If a user says *"I'm feeling low today, play something gentle"*,
the correct outcome is **no durable memory**. The request is served in the
moment and nothing is retained about their emotional state.

**The narrow exception.** A neutral *context tag* attached to a listening
session — for example `mood_context:melancholic` as a label on a playlist
choice — is allowed, because it describes content, not the person. The line is:
a label on *music* is fine, a claim about *the human* is not.

---

## How a type is chosen

The order matters. The first rule that matches wins.

```
1. Is the user correcting something we already stored?        -> correction
2. Is the user stating something they do NOT want?            -> exclusion
3. Is the user stating a lasting want, with no time bound?    -> explicit_preference
4. Is it a preference that is implied, or time-bounded?       -> candidate_preference
5. Is it a single action worth remembering briefly?           -> episode
6. Otherwise                                                   -> no memory
```

Rule 6 is not a failure case. It is the expected outcome for most events, and
§7.5 requires the extractor to return nothing rather than guess:
*"if the event carries no memory-worthy content, return an empty candidates
array."*

---

## Fields every memory carries

Regardless of type. Enforced by `packages/contracts/memory.py` and by the graph
constraints.

| Field | Why it must be there |
|---|---|
| `memory_id` | Stable across the graph **and** the vector index, so deletion is deterministic (§7.2 step 6) |
| `subject_id` | Subject isolation is enforced on this in every query |
| `fact_text` | The canonical statement, kept close to the user's own words |
| `memory_type` | One of the five above |
| `entities` | Resolved canonical identifiers, never raw text |
| `confidence` | 0.0–1.0 |
| `policy_class` | `normal` / `sensitive` / `blocked` |
| `source_event_id` | Provenance: which event produced this |
| `valid_from` / `valid_to` | When it was true. `valid_to = null` means still true. |
| `recorded_at` | When we learned it — distinct from when it became true |
| `status` | `active` / `superseded` / `expired` / `deleted` |

The pair `valid_from`/`recorded_at` is what makes this a *temporal* graph rather
than a table with a timestamp. A correction recorded today can close a fact that
stopped being true last month.

---

## Changing this document

Adding a type, changing a retention period, or changing a sensitivity class is a
**governed change**, not a refactor. §7.5 — *"require policy or data-governance
approval for new memory types, sensitive categories, and scoring-rule changes;
routine user corrections should not require manual approval."*

The process:

1. Edit this document first, including the counter-examples.
2. Update `packages/policy-engine/registry.py` to match.
3. Update the extraction prompt's allowed taxonomy.
4. Add golden-set cases that cover the new type, including cases that must
   **not** produce it.
5. Show the evaluation results, per §4 — the taxonomy widens when the data
   supports it, not before.
