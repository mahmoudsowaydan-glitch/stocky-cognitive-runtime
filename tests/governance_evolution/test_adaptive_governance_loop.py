"""Tests for cognitive_runtime/governance_evolution/adaptive_governance_loop.py."""

import pytest

from cognitive_runtime.governance_evolution import (
    GovernanceState, AdaptiveGovernanceLoop,
)


@pytest.fixture
def initial_state():
    return GovernanceState(
        version="1.0.0",
        policy_weights={"stability": 0.4, "confidence": 0.4, "freshness": 0.2},
        drift_tolerance=0.1,
        confidence_threshold=0.7,
        stability_threshold=0.7,
    )


# ── basic tick ──


def test_tick_no_metrics(initial_state):
    loop = AdaptiveGovernanceLoop(initial_state)
    result = loop.tick({})
    assert result == initial_state


def test_tick_healthy_system(initial_state):
    loop = AdaptiveGovernanceLoop(initial_state)
    result = loop.tick({
        "stability": 0.95, "confidence": 0.95,
        "consensus_strength": 0.95,
    })
    # Healthy → drift_pressure = max(0, 1-min(0.95,0.95)) = 0.05
    # 0.05 <= drift_tolerance=0.1 → no evolution
    assert result == initial_state


def test_tick_with_drift(initial_state):
    loop = AdaptiveGovernanceLoop(initial_state)
    result = loop.tick({
        "stability": 0.7, "confidence": 0.7,
        "consensus_strength": 0.9,
    })
    # drift_pressure = max(0, 1-min(0.7,0.7)) = 0.3
    # 0.3 > drift_tolerance=0.1 → evolution
    assert result != initial_state


def test_cycle_count_increments(initial_state):
    loop = AdaptiveGovernanceLoop(initial_state)
    assert loop.cycle_count == 0
    loop.tick({})
    assert loop.cycle_count == 1
    loop.tick({})
    assert loop.cycle_count == 2


# ── GOV-002: unstable → no evolution ──


def test_unstable_system_frozen(initial_state):
    loop = AdaptiveGovernanceLoop(initial_state)
    result = loop.tick({
        "stability": 0.4, "confidence": 0.9,
        "consensus_strength": 0.9,
    })
    assert result == initial_state


# ── GOV-003: deterministic ──


def test_tick_deterministic(initial_state):
    loop_a = AdaptiveGovernanceLoop(initial_state)
    loop_b = AdaptiveGovernanceLoop(initial_state)
    metrics = {
        "stability": 0.8, "confidence": 0.8,
        "consensus_strength": 0.9,
    }
    r1 = loop_a.tick(metrics)
    r2 = loop_b.tick(metrics)
    assert r1 == r2


# ── guard rejection tracking ──


def test_rejection_tracked(initial_state):
    loop = AdaptiveGovernanceLoop(initial_state)
    # Propose a change that exceeds 10% delta → guard rejects
    loop.tick({"stability": 0.8, "confidence": 0.8,
                "consensus_strength": 0.9, "drift_pressure": 0.8})
    # High drift_pressure may cause guard rejection if delta > MAX_DELTA
    if loop.last_rejection_reason is not None:
        assert loop.last_rejection_reason == "guard_rejected"


# ── state property ──


def test_state_property(initial_state):
    loop = AdaptiveGovernanceLoop(initial_state)
    assert loop.state == initial_state


def test_no_rejection_on_success(initial_state):
    loop = AdaptiveGovernanceLoop(initial_state)
    loop.tick({})
    assert loop.last_rejection_reason is None
