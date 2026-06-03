import pytest

from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.governance.architectural_decay import ArchitecturalDecay
from cognitive_runtime.governance.governance_report import EntropyMetrics, DecaySignal


def _make_trace(event_id="e1", final_status="P4_ALLOW"):
    return ExecutionTrace(
        event_id=event_id, session_id="s1", sequence_no=1,
        correlation_id="c1",
        preflight_valid=True, preflight_reason="ok",
        risk_score=0.1,
        p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low",
        execution_status="SUCCESS",
        final_status=final_status,
    )


class _MockStability:
    def __init__(self, score_history=None):
        self._score_history = score_history or []


class _MockConfidence:
    def __init__(self, score_history=None):
        self._score_history = score_history or []


class _MinimalStability:
    pass


def test_decay_fewer_than_10_traces_returns_empty():
    decay = ArchitecturalDecay()
    signals = decay.analyze([_make_trace(f"e{i}") for i in range(5)],
                            EntropyMetrics(0, 0, 0, 0, 0),
                            _MockStability())
    assert signals == []


def test_decay_exactly_10_traces_proceeds():
    decay = ArchitecturalDecay()
    signals = decay.analyze([_make_trace(f"e{i}") for i in range(10)],
                            EntropyMetrics(0, 0, 0, 0, 0),
                            _MockStability())
    assert isinstance(signals, list)


def test_decay_cyclic_chains_detected_all_same_status():
    decay = ArchitecturalDecay()
    traces = [_make_trace(f"e{i}", final_status="P4_ALLOW") for i in range(10)]
    entropy = EntropyMetrics(0, 0, 0, 0, 0)
    signals = decay.analyze(traces, entropy, _MockStability())
    cyclic = [s for s in signals if s.signal_type == "cyclic_causal_chains"]
    assert len(cyclic) >= 1
    assert cyclic[0].severity > 0


def test_decay_cyclic_chains_severity():
    decay = ArchitecturalDecay()
    traces = [_make_trace(f"e{i}", final_status="P4_ALLOW") for i in range(10)]
    result = decay._detect_cyclic_chains(traces)
    assert result == min(1.0, 1 / 1)


def test_decay_cyclic_chains_multiple_statuses():
    decay = ArchitecturalDecay()
    traces = []
    for i in range(5):
        traces.append(_make_trace(f"e{i}a", final_status="P4_ALLOW"))
        traces.append(_make_trace(f"e{i}b", final_status="P4_BLOCK"))
    result = decay._detect_cyclic_chains(traces)
    assert result == min(1.0, 2 / 2)


def test_decay_entropy_acceleration_not_enough_history():
    decay = ArchitecturalDecay()
    entropy = EntropyMetrics(0.5, 0, 0, 0, 0.5)
    signals = decay.analyze([_make_trace(f"e{i}") for i in range(10)], entropy,
                            _MockStability([0.9]))
    accel = [s for s in signals if s.signal_type == "entropy_acceleration"]
    assert len(accel) == 0


def test_decay_entropy_acceleration_detected():
    decay = ArchitecturalDecay()
    entropy = EntropyMetrics(0.5, 0, 0, 0, 0.5)
    signals = decay.analyze([_make_trace(f"e{i}") for i in range(10)], entropy,
                            _MockStability([0.9, 0.85, 0.8, 0.7]))
    accel = [s for s in signals if s.signal_type == "entropy_acceleration"]
    assert len(accel) >= 1
    assert accel[0].severity > 0


def test_decay_entropy_acceleration_small_drop():
    decay = ArchitecturalDecay()
    entropy = EntropyMetrics(0.5, 0, 0, 0, 0.5)
    signals = decay.analyze([_make_trace(f"e{i}") for i in range(10)], entropy,
                            _MockStability([0.9, 0.9, 0.89, 0.88]))
    accel = [s for s in signals if s.signal_type == "entropy_acceleration"]
    assert len(accel) == 0


def test_decay_entropy_acceleration_low_entropy():
    decay = ArchitecturalDecay()
    entropy = EntropyMetrics(0.1, 0, 0, 0, 0.1)
    signals = decay.analyze([_make_trace(f"e{i}") for i in range(10)], entropy,
                            _MockStability([0.9, 0.85, 0.8, 0.7]))
    accel = [s for s in signals if s.signal_type == "entropy_acceleration"]
    assert len(accel) == 0


def test_decay_detect_entropy_acceleration_direct():
    decay = ArchitecturalDecay()
    entropy = EntropyMetrics(0, 0, 0, 0, 0.5)
    result = decay._detect_entropy_acceleration(entropy, [0.9, 0.85, 0.8, 0.7])
    stability_delta = 0.7 - 0.9
    expected = abs(stability_delta) * 0.5
    assert result == expected


def test_decay_detect_entropy_acceleration_short():
    decay = ArchitecturalDecay()
    entropy = EntropyMetrics(0, 0, 0, 0, 0.5)
    assert decay._detect_entropy_acceleration(entropy, [0.5]) == 0.0


def test_decay_confidence_no_engine():
    decay = ArchitecturalDecay()
    signals = decay.analyze([_make_trace(f"e{i}") for i in range(10)],
                            EntropyMetrics(0, 0, 0, 0, 0),
                            _MockStability())
    conf_sigs = [s for s in signals if s.signal_type == "confidence_entropy_divergence"]
    assert len(conf_sigs) == 0


def test_decay_confidence_detected():
    decay = ArchitecturalDecay()
    entropy = EntropyMetrics(0.5, 0, 0, 0, 0.5)
    signals = decay.analyze([_make_trace(f"e{i}") for i in range(10)], entropy,
                            _MockStability([0.9, 0.9, 0.9, 0.9]),
                            confidence_engine=_MockConfidence([0.9, 0.85, 0.8, 0.75, 0.7, 0.65]))
    conf_sigs = [s for s in signals if s.signal_type == "confidence_entropy_divergence"]
    assert len(conf_sigs) >= 1
    assert conf_sigs[0].severity > 0


def test_decay_detect_confidence_correlation_triggered():
    decay = ArchitecturalDecay()
    entropy = EntropyMetrics(0, 0, 0, 0, 0.5)
    result = decay._detect_confidence_correlation(entropy, [0.9, 0.85, 0.8, 0.75, 0.7, 0.65])
    conf_delta = 0.65 - 0.9
    expected = abs(conf_delta) * 0.5
    assert result == expected


def test_decay_detect_confidence_correlation_not_triggered():
    decay = ArchitecturalDecay()
    entropy = EntropyMetrics(0, 0, 0, 0, 0.1)
    result = decay._detect_confidence_correlation(entropy, [0.9, 0.85, 0.8, 0.75, 0.7, 0.65])
    assert result == 0.0


def test_decay_unstable_pattern_emergence_detected():
    decay = ArchitecturalDecay()
    entropy = EntropyMetrics(0, 0.6, 0.3, 0, 0)
    signals = decay.analyze([_make_trace(f"e{i}") for i in range(10)], entropy,
                            _MockStability())
    unstable = [s for s in signals if s.signal_type == "unstable_pattern_emergence"]
    assert len(unstable) >= 1
    assert unstable[0].severity == pytest.approx(0.6 * 0.3)


def test_decay_unstable_pattern_emergence_low_pattern():
    decay = ArchitecturalDecay()
    entropy = EntropyMetrics(0, 0.3, 0.3, 0, 0)
    signals = decay.analyze([_make_trace(f"e{i}") for i in range(10)], entropy,
                            _MockStability())
    unstable = [s for s in signals if s.signal_type == "unstable_pattern_emergence"]
    assert len(unstable) == 0


def test_decay_unstable_pattern_emergence_low_inflation():
    decay = ArchitecturalDecay()
    entropy = EntropyMetrics(0, 0.6, 0.1, 0, 0)
    signals = decay.analyze([_make_trace(f"e{i}") for i in range(10)], entropy,
                            _MockStability())
    unstable = [s for s in signals if s.signal_type == "unstable_pattern_emergence"]
    assert len(unstable) == 0


def test_decay_detect_unstable_patterns_calculation():
    decay = ArchitecturalDecay()
    entropy = EntropyMetrics(0, 0.6, 0.3, 0, 0)
    result = decay._detect_unstable_patterns([_make_trace() for _ in range(10)], entropy)
    assert result == 0.6 * 0.3


def test_decay_detect_unstable_patterns_not_triggered():
    decay = ArchitecturalDecay()
    entropy = EntropyMetrics(0, 0.5, 0.2, 0, 0)
    result = decay._detect_unstable_patterns([_make_trace() for _ in range(10)], entropy)
    assert result == 0.0


def test_decay_multiple_signals_combined():
    decay = ArchitecturalDecay()
    traces = [_make_trace(f"e{i}", final_status="P4_ALLOW") for i in range(10)]
    entropy = EntropyMetrics(0.5, 0.6, 0.3, 0, 0.5)
    signals = decay.analyze(traces, entropy, _MockStability([0.9, 0.85, 0.8, 0.7]),
                            confidence_engine=_MockConfidence([0.9, 0.85, 0.8, 0.75, 0.7, 0.65]))
    signal_types = {s.signal_type for s in signals}
    assert "cyclic_causal_chains" in signal_types
    assert "unstable_pattern_emergence" in signal_types


def test_decay_no_stability_history_attr():
    decay = ArchitecturalDecay()
    signals = decay.analyze([_make_trace(f"e{i}") for i in range(10)],
                            EntropyMetrics(0.5, 0, 0, 0, 0.5),
                            _MinimalStability())
    assert isinstance(signals, list)
