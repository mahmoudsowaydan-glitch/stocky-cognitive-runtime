"""Tests for cognitive_runtime/governance_evolution/governance_guard.py."""

import pytest

from cognitive_runtime.governance_evolution import GovernanceState, GovernanceGuard


@pytest.fixture
def guard():
    return GovernanceGuard()


@pytest.fixture
def current():
    return GovernanceState(
        version="1.0.0",
        drift_tolerance=0.1,
        confidence_threshold=0.7,
        stability_threshold=0.7,
    )


# ── GOV-001: version must not change ──


def test_version_change_rejected(guard, current):
    proposed = GovernanceState(
        version="2.0.0",
        drift_tolerance=0.1,
        confidence_threshold=0.7,
        stability_threshold=0.7,
    )
    assert guard.approve(current, proposed) is False


def test_same_version_accepted(guard, current):
    proposed = GovernanceState(
        version="1.0.0",
        drift_tolerance=0.11,
        confidence_threshold=0.71,
        stability_threshold=0.71,
    )
    assert guard.approve(current, proposed) is True


# ── delta bounds ──


def test_drift_delta_excessive_rejected(guard, current):
    proposed = GovernanceState(
        version="1.0.0",
        drift_tolerance=0.3,  # delta = 0.2 > 0.1
        confidence_threshold=0.7,
        stability_threshold=0.7,
    )
    assert guard.approve(current, proposed) is False


def test_confidence_delta_excessive_rejected(guard, current):
    proposed = GovernanceState(
        version="1.0.0",
        drift_tolerance=0.1,
        confidence_threshold=0.9,  # delta = 0.2
        stability_threshold=0.7,
    )
    assert guard.approve(current, proposed) is False


def test_stability_delta_excessive_rejected(guard, current):
    proposed = GovernanceState(
        version="1.0.0",
        drift_tolerance=0.1,
        confidence_threshold=0.7,
        stability_threshold=0.9,  # delta = 0.2
    )
    assert guard.approve(current, proposed) is False


# ── range bounds ──


def test_negative_threshold_rejected(guard, current):
    proposed = GovernanceState(
        version="1.0.0",
        drift_tolerance=-0.1,
        confidence_threshold=0.7,
        stability_threshold=0.7,
    )
    assert guard.approve(current, proposed) is False


def test_above_one_threshold_rejected(guard, current):
    proposed = GovernanceState(
        version="1.0.0",
        drift_tolerance=1.5,
        confidence_threshold=0.7,
        stability_threshold=0.7,
    )
    assert guard.approve(current, proposed) is False


# ── invariant: stability <= confidence ──


def test_stability_exceeds_confidence_rejected(guard, current):
    proposed = GovernanceState(
        version="1.0.0",
        drift_tolerance=0.1,
        confidence_threshold=0.5,
        stability_threshold=0.7,  # 0.7 > 0.5
    )
    assert guard.approve(current, proposed) is False


def test_stability_equals_confidence_accepted(guard, current):
    proposed = GovernanceState(
        version="1.0.0",
        drift_tolerance=0.1,
        confidence_threshold=0.75,
        stability_threshold=0.75,
    )
    assert guard.approve(current, proposed) is True


# ── edge cases ──


def test_none_proposed_rejected(guard, current):
    assert guard.approve(current, None) is False


def test_identical_proposed_accepted(guard, current):
    assert guard.approve(current, current) is True
