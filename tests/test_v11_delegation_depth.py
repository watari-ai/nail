"""
NAIL v1.1 — Delegation Depth Tracking Tests (Draft)

These tests define the expected behaviour of delegation depth enforcement.
All tests are skipped until implementation lands (Issue #108 Phase 2).

Spec reference: designs/v1.1/delegation-depth.md

To run: pytest tests/test_v11_delegation_depth.py -v
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="v1.1 not yet implemented — Issue #108 Phase 2")

# ---------------------------------------------------------------------------
# Minimal fixtures for reuse across tests
# ---------------------------------------------------------------------------

TASK_MAX_DEPTH_1 = {
    "op": "def",
    "name": "orchestrate_write",
    "effects": {"allow": [{"op": "FS:write_file", "delegation": "explicit"}]},
    "can_delegate": {
        "max_delegation_depth": 1,
    },
}

TASK_MAX_DEPTH_0 = {
    "op": "def",
    "name": "write_chunk",
    "effects": {"allow": [{"op": "FS:write_file", "delegation": "explicit"}]},
    "can_delegate": {
        "max_delegation_depth": 0,
    },
}

TASK_NO_CAN_DELEGATE = {
    "op": "def",
    "name": "read_config",
    "effects": {"allow": [{"op": "FS:read_file", "delegation": "explicit"}]},
    # no can_delegate block — v1.0 backward compat
}

TASK_REVERSIBLE_FALSE = {
    "op": "def",
    "name": "delete_records",
    "effects": {"allow": [{"op": "STATE:delete", "delegation": "explicit"}]},
    "can_delegate": {
        "reversible": False,
        # max_delegation_depth not set → defaults to 0 per #112 rule
    },
}


# ===========================================================================
# Test 1: max_delegation_depth: 1 allows single hop
# ===========================================================================


def test_max_delegation_depth_1_allows_single_hop():
    """A task with max_delegation_depth: 1 can delegate exactly once.

    Runtime context starts at depth 0 (top-level invocation).
    After one hop, delegation_depth becomes 1.
    depth 1 == max_delegation_depth 1: the hop is permitted (no DelegationDepthError).

    Spec: "1 — the task may delegate once; the delegated task may not delegate further."
    """
    from nail_lang.delegation import RuntimeContext, delegate

    ctx = RuntimeContext(task_id="orchestrate_write", delegation_depth=0)

    child_ctx = delegate(
        caller_task=TASK_MAX_DEPTH_1,
        caller_ctx=ctx,
        target_task_id="write_chunk",
    )

    assert child_ctx.delegation_depth == 1
    assert child_ctx.task_id == "write_chunk"


# ===========================================================================
# Test 2: max_delegation_depth: 1 rejects second hop → DelegationDepthError
# ===========================================================================


def test_max_delegation_depth_1_rejects_second_hop():
    """A task with max_delegation_depth: 1 raises DelegationDepthError on the second hop.

    After one delegation, delegation_depth == 1.
    Attempting a second delegation exceeds max_delegation_depth: 1 → error.

    Spec: "effective_remaining_depth = max_delegation_depth - delegation_depth;
    if <= 0: raise DelegationDepthError"
    """
    from nail_lang.delegation import DelegationDepthError, RuntimeContext, delegate

    # Already at depth 1 (one hop has occurred)
    ctx_at_depth_1 = RuntimeContext(task_id="orchestrate_write", delegation_depth=1)

    with pytest.raises(DelegationDepthError) as exc_info:
        delegate(
            caller_task=TASK_MAX_DEPTH_1,
            caller_ctx=ctx_at_depth_1,
            target_task_id="any_task",
        )

    err = exc_info.value
    assert err.depth == 1
    assert err.max_depth == 1
    assert err.code == "DELEGATION_DEPTH_EXCEEDED"


# ===========================================================================
# Test 3: max_delegation_depth: 0 forbids any delegation
# ===========================================================================


def test_max_delegation_depth_0_forbids_any_delegation():
    """A task with max_delegation_depth: 0 raises DelegationDepthError on the first attempt.

    Spec: "0 — the task may not delegate to any further task."
    Even at depth 0, attempting to delegate from this task must immediately raise.
    """
    from nail_lang.delegation import DelegationDepthError, RuntimeContext, delegate

    ctx = RuntimeContext(task_id="write_chunk", delegation_depth=0)

    with pytest.raises(DelegationDepthError) as exc_info:
        delegate(
            caller_task=TASK_MAX_DEPTH_0,
            caller_ctx=ctx,
            target_task_id="any_task",
        )

    err = exc_info.value
    assert err.max_depth == 0
    assert err.code == "DELEGATION_DEPTH_EXCEEDED"


# ===========================================================================
# Test 4: no can_delegate block → default depth = unlimited (backward compat)
# ===========================================================================


def test_no_can_delegate_block_allows_unlimited_depth():
    """A task with no can_delegate block has no depth limit (v1.0 backward compat).

    Spec: "Absent — no depth constraint is applied (equivalent to v1.0 behaviour
    when can_delegate is truthy)."

    Delegates at depth 0, 5, and 100 must all succeed without raising.
    """
    from nail_lang.delegation import RuntimeContext, delegate

    for depth in (0, 5, 100):
        ctx = RuntimeContext(task_id="read_config", delegation_depth=depth)
        child_ctx = delegate(
            caller_task=TASK_NO_CAN_DELEGATE,
            caller_ctx=ctx,
            target_task_id="sub_task",
        )
        assert child_ctx.delegation_depth == depth + 1, (
            f"Expected child depth {depth + 1}, got {child_ctx.delegation_depth}"
        )


# ===========================================================================
# Test 5: reversible: false without explicit can_delegate → depth defaults to 0
# ===========================================================================


def test_reversible_false_without_explicit_depth_defaults_to_0():
    """reversible: false with no max_delegation_depth defaults to depth 0 (#112 rule).

    When reversible: false and max_delegation_depth is not specified, the runtime
    treats max_delegation_depth as 0 — any delegation attempt must raise.

    Spec: "If reversible: false and max_delegation_depth is not explicitly specified,
    the runtime treats max_delegation_depth as 0."
    """
    from nail_lang.delegation import DelegationDepthError, RuntimeContext, delegate

    ctx = RuntimeContext(task_id="delete_records", delegation_depth=0)

    with pytest.raises(DelegationDepthError) as exc_info:
        delegate(
            caller_task=TASK_REVERSIBLE_FALSE,
            caller_ctx=ctx,
            target_task_id="sub_task",
        )

    err = exc_info.value
    assert err.max_depth == 0, (
        "reversible: false without explicit depth must default to max_delegation_depth=0"
    )


# ===========================================================================
# Test 6: delegation_allowed_effects must be subset of parent effects
# ===========================================================================


def test_delegation_allowed_effects_must_be_subset_of_parent():
    """delegation_allowed_effects on a child must be a subset of the parent's grants.

    A delegatee cannot receive effect labels that the delegating task does not hold.
    Attempting to grant an effect the parent lacks must raise EffectEscalationError.

    Spec rationale: "Sensitive effects (e.g. FS_WRITE, STATE) can propagate arbitrarily
    deep" — depth bounding and effect scoping together limit effect propagation.
    """
    from nail_lang.delegation import EffectEscalationError, RuntimeContext, delegate

    parent_task = {
        "op": "def",
        "name": "net_only_task",
        "effects": {"allow": [{"op": "NET:call", "delegation": "explicit"}]},
        "can_delegate": {
            "max_delegation_depth": 1,
            "delegation_allowed_effects": ["NET", "FS"],  # FS not held by parent
        },
    }

    ctx = RuntimeContext(
        task_id="net_only_task",
        delegation_depth=0,
        effect_grants={"NET"},  # parent holds only NET
    )

    with pytest.raises(EffectEscalationError) as exc_info:
        delegate(
            caller_task=parent_task,
            caller_ctx=ctx,
            target_task_id="child_task",
        )

    err = exc_info.value
    assert "FS" in err.escalated_effects, (
        "EffectEscalationError must identify the effect(s) that exceed parent grants"
    )


# ===========================================================================
# Test 7: DelegationDepthError has correct properties (task, depth, max_depth)
# ===========================================================================


def test_delegation_depth_error_has_correct_properties():
    """DelegationDepthError exposes task_id, target_id, depth, max_depth, code, message.

    Spec error structure:
      DelegationDepthError {
        code:       "DELEGATION_DEPTH_EXCEEDED"
        task_id:    string    # ID of the task that attempted the delegation
        target_id:  string    # ID of the task that would have been delegated to
        depth:      int       # current depth at the point of the attempted delegation
        max_depth:  int       # declared max_delegation_depth on the source task
        message:    string    # human-readable description
      }
    """
    from nail_lang.delegation import DelegationDepthError, RuntimeContext, delegate

    caller_task = {
        "op": "def",
        "name": "write_sensitive",
        "effects": {"allow": [{"op": "FS:write_file", "delegation": "explicit"}]},
        "can_delegate": {"max_delegation_depth": 1},
    }
    # depth 2 already exceeds max_delegation_depth 1
    ctx = RuntimeContext(task_id="write_sensitive", delegation_depth=2)

    with pytest.raises(DelegationDepthError) as exc_info:
        delegate(
            caller_task=caller_task,
            caller_ctx=ctx,
            target_task_id="archive_records",
        )

    err = exc_info.value
    assert err.code == "DELEGATION_DEPTH_EXCEEDED"
    assert err.task_id == "write_sensitive"
    assert err.target_id == "archive_records"
    assert err.depth == 2
    assert err.max_depth == 1
    assert isinstance(err.message, str) and len(err.message) > 0, (
        "DelegationDepthError must carry a non-empty human-readable message"
    )


# ===========================================================================
# Test 8: depth counter resets at new top-level invocation
# ===========================================================================


def test_depth_counter_resets_at_new_top_level_invocation():
    """delegation_depth resets to 0 when a new top-level invocation begins.

    Spec lifecycle rules:
      1. Top-level invocation sets delegation_depth = 0.
      4. A new top-level invocation resets delegation_depth = 0.
      5. Concurrent invocations each maintain independent counters.

    Two sequential top-level invocations must each start at depth 0, regardless
    of what the previous invocation's final depth was.
    """
    from nail_lang.delegation import RuntimeContext, invoke_top_level

    # First top-level invocation
    ctx_1 = invoke_top_level(task_id="orchestrate_write")
    assert ctx_1.delegation_depth == 0, "First top-level invocation must start at depth 0"

    # Simulate that the first invocation reached depth 1 via delegation (internal to ctx_1)
    ctx_1_child = RuntimeContext(task_id="write_chunk", delegation_depth=1)
    assert ctx_1_child.delegation_depth == 1  # child context is correctly at depth 1

    # Second top-level invocation must be fully independent and start at depth 0
    ctx_2 = invoke_top_level(task_id="orchestrate_write")
    assert ctx_2.delegation_depth == 0, (
        "Second top-level invocation must reset depth to 0, "
        "independent of any prior invocation's depth"
    )
    # The two contexts must not share state
    assert ctx_1 is not ctx_2, "Each top-level invocation must produce a fresh context"
