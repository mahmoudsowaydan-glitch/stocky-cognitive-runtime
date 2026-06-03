from cognitive_runtime.governance.governance_report import (
    EntropyMetrics,
    DriftMetrics,
    PressureMetrics,
    DecaySignal,
    GovernanceReport,
)


def test_entropy_metrics_default_values():
    m = EntropyMetrics(0.0, 0.0, 0.0, 0.0, 0.0)
    assert m.causal_density == 0.0
    assert m.pattern_explosion == 0.0
    assert m.trace_inflation == 0.0
    assert m.graph_branching == 0.0
    assert m.overall == 0.0


def test_entropy_metrics_field_types():
    m = EntropyMetrics(0.5, 0.3, 0.2, 0.1, 0.275)
    assert isinstance(m.causal_density, float)
    assert isinstance(m.pattern_explosion, float)
    assert isinstance(m.trace_inflation, float)
    assert isinstance(m.graph_branching, float)
    assert isinstance(m.overall, float)


def test_entropy_metrics_various_values():
    m = EntropyMetrics(causal_density=1.0, pattern_explosion=0.75, trace_inflation=0.5, graph_branching=0.25, overall=0.625)
    assert m.causal_density == 1.0
    assert m.pattern_explosion == 0.75
    assert m.trace_inflation == 0.5
    assert m.graph_branching == 0.25
    assert m.overall == 0.625


def test_drift_metrics_default_values():
    m = DriftMetrics(0.0, 0.0, 0.0, 0.0, 0.0)
    assert m.preflight_overreach == 0.0
    assert m.p4_avoidance == 0.0
    assert m.risk_influence == 0.0
    assert m.coherence_drift_rate == 0.0
    assert m.overall == 0.0


def test_drift_metrics_field_types():
    m = DriftMetrics(0.1, 0.2, 0.3, 0.4, 0.25)
    assert all(isinstance(v, float) for v in (m.preflight_overreach, m.p4_avoidance, m.risk_influence, m.coherence_drift_rate, m.overall))


def test_drift_metrics_max_values():
    m = DriftMetrics(1.0, 1.0, 1.0, 1.0, 1.0)
    assert m.overall == 1.0


def test_pressure_metrics_default_values():
    m = PressureMetrics(0.0, 0.0, 0.0, 0.0, 0.0)
    assert m.rule_conflict_rate == 0.0
    assert m.p4_overload_rate == 0.0
    assert m.ambiguity_rate == 0.0
    assert m.escalation_rate == 0.0
    assert m.overall == 0.0


def test_pressure_metrics_field_types():
    m = PressureMetrics(0.5, 0.4, 0.3, 0.2, 0.35)
    assert all(isinstance(v, float) for v in (m.rule_conflict_rate, m.p4_overload_rate, m.ambiguity_rate, m.escalation_rate, m.overall))


def test_pressure_metrics_various_values():
    m = PressureMetrics(rule_conflict_rate=0.9, p4_overload_rate=0.0, ambiguity_rate=0.1, escalation_rate=0.5, overall=0.375)
    assert m.rule_conflict_rate == 0.9
    assert m.p4_overload_rate == 0.0
    assert m.ambiguity_rate == 0.1
    assert m.escalation_rate == 0.5


def test_decay_signal_fields():
    s = DecaySignal(signal_type="cyclic_causal_chains", severity=0.5, description="test")
    assert s.signal_type == "cyclic_causal_chains"
    assert s.severity == 0.5
    assert s.description == "test"


def test_decay_signal_field_types():
    s = DecaySignal("type_a", 0.75, "desc")
    assert isinstance(s.signal_type, str)
    assert isinstance(s.severity, float)
    assert isinstance(s.description, str)


def test_decay_signal_minimal():
    s = DecaySignal("", 0.0, "")
    assert s.signal_type == ""
    assert s.severity == 0.0
    assert s.description == ""


def test_governance_report_fields():
    entropy = EntropyMetrics(0.1, 0.2, 0.3, 0.4, 0.25)
    drift = DriftMetrics(0.1, 0.1, 0.1, 0.1, 0.1)
    pressure = PressureMetrics(0.2, 0.2, 0.2, 0.2, 0.2)
    decay = [DecaySignal("t1", 0.5, "d1"), DecaySignal("t2", 0.3, "d2")]
    report = GovernanceReport(
        entropy=entropy, drift=drift, pressure=pressure,
        decay_signals=decay, governance_status="NOMINAL",
        score=0.15, trend_direction="stable", trend_delta=0.0,
    )
    assert report.entropy is entropy
    assert report.drift is drift
    assert report.pressure is pressure
    assert report.decay_signals == decay
    assert report.governance_status == "NOMINAL"
    assert report.score == 0.15
    assert report.trend_direction == "stable"
    assert report.trend_delta == 0.0


def test_governance_report_types():
    report = GovernanceReport(
        entropy=EntropyMetrics(0, 0, 0, 0, 0),
        drift=DriftMetrics(0, 0, 0, 0, 0),
        pressure=PressureMetrics(0, 0, 0, 0, 0),
        decay_signals=[], governance_status="CRITICAL",
        score=0.95, trend_direction="worsening", trend_delta=0.05,
    )
    assert isinstance(report.score, float)
    assert isinstance(report.trend_delta, float)
    assert isinstance(report.governance_status, str)
    assert isinstance(report.trend_direction, str)
    assert isinstance(report.decay_signals, list)


def test_governance_report_empty_decay():
    report = GovernanceReport(
        entropy=EntropyMetrics(0, 0, 0, 0, 0),
        drift=DriftMetrics(0, 0, 0, 0, 0),
        pressure=PressureMetrics(0, 0, 0, 0, 0),
        decay_signals=[], governance_status="NOMINAL",
        score=0.0, trend_direction="stable", trend_delta=0.0,
    )
    assert report.decay_signals == []


def test_governance_report_all_statuses():
    entropy = EntropyMetrics(0, 0, 0, 0, 0)
    drift = DriftMetrics(0, 0, 0, 0, 0)
    pressure = PressureMetrics(0, 0, 0, 0, 0)
    for status in ("NOMINAL", "MONITORING", "ELEVATED", "CRITICAL"):
        r = GovernanceReport(entropy, drift, pressure, [], status, 0.0, "stable", 0.0)
        assert r.governance_status == status
