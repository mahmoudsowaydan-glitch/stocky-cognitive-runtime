"""Tests for cognitive_runtime/governance_evolution/governance_policy_engine.py."""

import pytest

from cognitive_runtime.governance_evolution import GovernancePolicyEngine


@pytest.fixture
def engine():
    return GovernancePolicyEngine()


def test_healthy_system(engine):
    metrics = engine.evaluate({
        "stability": 0.95, "confidence": 0.95,
        "consensus_strength": 0.95, "replay_accuracy": 1.0,
    })
    assert metrics["drift_pressure"] < 0.1
    assert metrics["stability_gap"] == 0.0
    assert metrics["confidence_gap"] == 0.0
    assert metrics["consensus_fragmentation"] < 0.1


def test_unstable_system(engine):
    metrics = engine.evaluate({
        "stability": 0.3, "confidence": 0.9,
        "consensus_strength": 0.9, "replay_accuracy": 1.0,
    })
    assert metrics["drift_pressure"] > 0.5
    assert metrics["stability_gap"] > 0.3


def test_low_confidence(engine):
    metrics = engine.evaluate({
        "stability": 0.9, "confidence": 0.2,
        "consensus_strength": 0.9, "replay_accuracy": 1.0,
    })
    assert metrics["confidence_gap"] > 0.4
    assert metrics["drift_pressure"] > 0.1


def test_high_fragmentation(engine):
    metrics = engine.evaluate({
        "stability": 0.9, "confidence": 0.9,
        "consensus_strength": 0.3, "replay_accuracy": 1.0,
    })
    assert metrics["consensus_fragmentation"] > 0.5


def test_empty_metrics(engine):
    metrics = engine.evaluate({})
    assert metrics["stability_gap"] == 0.0
    assert metrics["confidence_gap"] == 0.0
