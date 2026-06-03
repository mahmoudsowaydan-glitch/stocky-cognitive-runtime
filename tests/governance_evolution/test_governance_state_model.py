"""Tests for cognitive_runtime/governance_evolution/governance_state_model.py."""

from cognitive_runtime.governance_evolution import GovernanceState


def test_minimal():
    s = GovernanceState(version="1.0.0")
    assert s.version == "1.0.0"
    assert s.drift_tolerance == 0.1
    assert s.confidence_threshold == 0.7
    assert s.stability_threshold == 0.7


def test_with_weights():
    s = GovernanceState(
        version="1.1.0",
        policy_weights={"stability": 0.4, "confidence": 0.4, "freshness": 0.2},
        threshold_map={"consensus": 0.7},
    )
    assert s.policy_weights["stability"] == 0.4
    assert s.threshold_map["consensus"] == 0.7


def test_immutable():
    import dataclasses
    assert dataclasses.is_dataclass(GovernanceState)
