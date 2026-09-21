"""Contract tests — backward compatibility of every shared data contract.

Spec ref: §5.5 Maintainability — "Memory schemas, scoring policies, MCP tools,
and prompts must be versioned and independently testable"; §7.7 Contract —
"Backward compatibility for event, API, MCP tool, graph, vector, and
context-package schemas."

Why this exists. Every service imports `packages.contracts`, and the two web
apps consume the JSON Schema exports in `data/schemas/`. A field quietly
renamed here breaks all of them at runtime, in a way no unit test would catch.
These tests make that a build failure instead.

The mechanism is a frozen snapshot, `contract_baseline.json`, recording every
field of every shared model and whether it was required. The tests compare the
live models against it.

When you intend to change a contract
------------------------------------
1. Make the change.
2. Run the suite — it will fail and name exactly what broke.
3. If the change really is intended, bump SCHEMA_VERSION in
   packages/contracts/events.py, regenerate the baseline, and regenerate the
   JSON Schemas:

       python data/schemas/generate_schemas.py
       python tests/contract/regenerate_baseline.py

4. Do all of that in the same pull request, so the version bump and the
   breaking change can never be separated in the history.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from packages import contracts
from packages.contracts import SCHEMA_VERSION

_BASELINE_PATH = Path(__file__).parent / "contract_baseline.json"
_BASELINE = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
_SCHEMA_DIR = _REPO_ROOT / "data" / "schemas"


def _baseline_models():
    return sorted(_BASELINE["models"].items())


def test_schema_version_is_pinned():
    """SCHEMA_VERSION must not drift without a deliberate, reviewed change.

    ingestion-api rejects any event whose schema_version does not match this
    exactly (§5.4 "Reject ... unsupported events before graph processing"), so
    changing it silently would start rejecting live traffic.
    """
    assert SCHEMA_VERSION == _BASELINE["schema_version"], (
        f"SCHEMA_VERSION moved from {_BASELINE['schema_version']!r} to {SCHEMA_VERSION!r}. "
        "If that is intended, regenerate the baseline in the same pull request "
        "and confirm ingestion-api's version check was updated with it."
    )


@pytest.mark.parametrize("model_name,frozen", _baseline_models())
def test_model_still_exists(model_name, frozen):
    """A contract the baseline knows about may not simply disappear."""
    assert hasattr(contracts, model_name), (
        f"{model_name} is no longer exported from packages.contracts. "
        "Every service imports from this package; removing a contract is a breaking change."
    )


@pytest.mark.parametrize("model_name,frozen", _baseline_models())
def test_no_field_removed_or_renamed(model_name, frozen):
    """Removing or renaming a field breaks every consumer that reads it.

    A rename shows up here as a removal, which is the point — the old name is
    gone, and anything sending or reading it stops working.
    """
    model = getattr(contracts, model_name)
    live = set(model.model_fields)
    frozen_fields = set(frozen["fields"])
    missing = sorted(frozen_fields - live)
    assert not missing, (
        f"{model_name} lost field(s) {missing}. This is a breaking change for every "
        "service and for the JSON Schema consumed by the web apps. If it is intended, "
        "bump SCHEMA_VERSION and regenerate the baseline in the same pull request."
    )


@pytest.mark.parametrize("model_name,frozen", _baseline_models())
def test_optional_field_did_not_become_required(model_name, frozen):
    """Tightening a field breaks existing producers.

    A caller that has always omitted an optional field starts failing validation
    the moment it becomes mandatory. That is a breaking change even though no
    field was removed.
    """
    model = getattr(contracts, model_name)
    tightened = []
    for fname, spec in frozen["fields"].items():
        if fname not in model.model_fields:
            continue  # reported by test_no_field_removed_or_renamed
        if not spec["required"] and model.model_fields[fname].is_required():
            tightened.append(fname)
    assert not tightened, (
        f"{model_name} made optional field(s) {sorted(tightened)} required. "
        "Existing callers that omit them will now fail validation."
    )


@pytest.mark.parametrize("model_name,frozen", _baseline_models())
def test_new_field_is_optional(model_name, frozen):
    """Adding a field is fine. Adding a *required* field is not.

    §7.7 asks for backward compatibility, and the compatible way to extend a
    contract is with a field that has a default, so existing producers keep
    validating unchanged.
    """
    model = getattr(contracts, model_name)
    added_required = [
        fname
        for fname, finfo in model.model_fields.items()
        if fname not in frozen["fields"] and finfo.is_required()
    ]
    assert not added_required, (
        f"{model_name} added required field(s) {sorted(added_required)}. "
        "Give them a default so existing producers keep working, or bump "
        "SCHEMA_VERSION and regenerate the baseline if the break is intended."
    )


def test_interaction_event_keeps_its_mandatory_capture_fields():
    """§5.4 names these explicitly: 'Attach subject scope, surface, locale,
    timestamp, consent state, source-event identifier, and idempotency key to
    every event.' They are called out separately from the generic baseline
    because losing any one of them is a privacy and correctness failure, not
    just a compatibility break."""
    required = {
        name for name, f in contracts.InteractionEvent.model_fields.items() if f.is_required()
    }
    mandated = {
        "event_id",        # source-event identifier
        "subject_id",      # subject scope
        "surface",
        "event_type",
        "timestamp",
        "consent_state",
        "idempotency_key",
    }
    missing = sorted(mandated - required)
    assert not missing, (
        f"InteractionEvent no longer requires {missing}. §5.4 requires every event to carry these."
    )


def test_memory_id_is_shared_between_graph_and_vector_contracts():
    """§5.4: 'store vectors under the same stable memory identifier used in the
    graph.' If these two ever diverge — a separate vector id, say — deletion
    propagation becomes unprovable, which §9 treats as a release blocker."""
    assert "memory_id" in contracts.Memory.model_fields
    assert "memory_id" in contracts.VectorRecord.model_fields
    assert "memory_id" in contracts.RetrievalCandidate.model_fields, (
        "RetrievalCandidate must carry the same memory_id so a retrieved item can be "
        "traced back to its graph fact and its vector."
    )


def test_exported_json_schemas_exist():
    """The web apps and any external consumer read these files, not the Python
    models. A contract without an export is a contract nobody outside Python
    can use (§6.3 Data Assets Required)."""
    expected = {
        "interaction_event.schema.json",
        "memory.schema.json",
        "extraction_result.schema.json",
        "context_package.schema.json",
        "policy_decision.schema.json",
        "feedback_event.schema.json",
        "trace.schema.json",
        "retrieval_candidate_set.schema.json",
        "vector_record.schema.json",
    }
    present = {p.name for p in _SCHEMA_DIR.glob("*.schema.json")}
    missing = sorted(expected - present)
    assert not missing, (
        f"missing JSON Schema export(s): {missing}. Run `python data/schemas/generate_schemas.py`."
    )


def _schema_export_map():
    """The filename -> model mapping, read from the generator so the two cannot
    disagree about what is supposed to be exported."""
    spec = importlib.util.spec_from_file_location(
        "generate_schemas", _REPO_ROOT / "data" / "schemas" / "generate_schemas.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MODELS


@pytest.mark.parametrize("filename,model", sorted(_schema_export_map().items()))
def test_exported_json_schema_matches_its_model(filename, model):
    """The committed schema file must be exactly what the current model produces.

    data/schemas/README.md says never to hand-edit these files. This enforces
    it, and it also catches the far more common mistake: changing a model and
    forgetting to regenerate.

    The comparison is done in memory rather than by shelling out to git, so it
    does not care whether the file happens to be staged, and it reports the
    specific field that drifted rather than just "something changed".
    """
    path = _SCHEMA_DIR / filename
    assert path.exists(), f"{filename} was never generated. Run `python data/schemas/generate_schemas.py`."

    committed = json.loads(path.read_text(encoding="utf-8"))
    live = model.model_json_schema()

    if committed != live:
        committed_props = set(committed.get("properties", {}))
        live_props = set(live.get("properties", {}))
        detail = ""
        if committed_props != live_props:
            detail = (
                f"\n  fields only in the committed file: {sorted(committed_props - live_props)}"
                f"\n  fields only in the live model:     {sorted(live_props - committed_props)}"
            )
        pytest.fail(
            f"{filename} is out of date with {model.__name__}.{detail}\n"
            "Run `python data/schemas/generate_schemas.py` and commit the result."
        )
