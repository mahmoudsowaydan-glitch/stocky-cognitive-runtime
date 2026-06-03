"""Tests for cognitive_runtime/governance_evolution/test_governance_evolution_engine.py."""

import pytest

from cognitive_runtime.governance_evolution import (
    GovernanceState, GovernanceEvolutionEngine,
)


@pytest.fixture
def engine():
    return GovernanceEvolutionEngine()


@pytest.fixture
def state():
    return GovernanceState(
        version="1.0.0",
        policy_weights={"stability": 0.4, "confidence": 0.4, "freshness": 0.2},
        threshold_map={"consensus": 0.7},
        drift_tolerance=0.1,
        confidence_threshold=0.7,
        stability_threshold=0.7,
    )


# ── GOV-002: freeze under instability ──


def test_evolution_frozen_when_unstable(engine, state):
    metrics = {"stability": 0.5, "drift_pressure": 0.3}
    result = engine.evolve(state, metrics)
    assert result == state  # no evolution


def test_evolution_allowed_when_stable(engine, state):
    metrics = {"stability": 0.9, "drift_pressure": 0.3}
    result = engine.evolve(state, metrics)
    assert result != state  # evolution happened


# ── GOV-004: deterministic ──


def test_evolution_deterministic(engine, state):
    metrics = {"stability": 0.9, "drift_pressure": 0.3}
    r1 = engine.evolve(state, metrics)
    r2 = engine.evolve(state, metrics)
    assert r1 == r2


# ── Rule 2: gradual adaptation <= 10% ──


def test_change_rate_bounded(engine, state):
    metrics = {"stability": 0.9, "drift_pressure": 0.5}
    result = engine.evolve(state, metrics)
    # drift_tolerance must not change by more than 10%
    delta = abs(result.drift_tolerance - state.drift_tolerance)
    assert delta <= state.drift_tolerance * (
        engine.MAX_CHANGE_RATE + 0.001  # allow rounding
    )


# ── Rule 4: consensus safety gate ──


def test_fragmentation_blocks_evolution(engine, state):
    metrics = {
        "stability": 0.9, "drift_pressure": 0.5,
        "consensus_fragmentation": 0.2,  # above drift_tolerance=0.1
    }
    result = engine.evolve(state, metrics)
    assert result == state


def test_low_fragmentation_allows_evolution(engine, state):
    metrics = {
        "stability": 0.9, "drift_pressure": 0.3,
        "consensus_fragmentation": 0.05,  # below drift_tolerance=0.1
    }
    result = engine.evolve(state, metrics)
    assert result != state


# ── zero drift → no change ──


def test_no_drift_no_change(engine, state):
    metrics = {"stability": 0.9, "drift_pressure": 0.05}
    result = engine.evolve(state, metrics)
    # drift (0.05) <= drift_tolerance (0.1) → no change
    assert result == state


def test_drift_exceeds_tolerance(engine, state):
    metrics = {"stability": 0.9, "drift_pressure": 0.15}
    result = engine.evolve(state, metrics)
    # drift (0.15) > drift_tolerance (0.1) → change
    assert result != state


# ── GOV-003: no randomness ──


def test_no_randomness(engine, state):
    metrics = {"stability": 0.9, "drift_pressure": 0.3}
    results = []
    for _ in range(5):
        results.append(engine.evolve(state, metrics))
    for r in results:
        assert r == results[0]
