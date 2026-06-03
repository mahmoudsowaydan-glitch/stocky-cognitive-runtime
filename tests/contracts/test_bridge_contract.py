from cognitive_runtime.contracts.frozen.bridge_contract import BridgeContract
from cognitive_runtime.contracts.frozen.schema_version import get_expected_fingerprint


def test_tap_expected_methods():
    methods = BridgeContract.TAP_EXPECTED_METHODS
    for m in ("tap_event_received", "tap_p3_proposal", "tap_p4_decision",
               "tap_execution_result", "tap_blocked", "get_enriched",
               "get_by_session", "get_by_status", "subscribe"):
        assert m in methods
    assert len(methods) == 9


def test_tap_expected_properties():
    assert BridgeContract.TAP_EXPECTED_PROPERTIES == ["total_traced", "completed_cycles"]


def test_feedback_expected_methods():
    assert BridgeContract.FEEDBACK_EXPECTED_METHODS == ["analyze"]


def test_feedback_expected_properties():
    assert BridgeContract.FEEDBACK_EXPECTED_PROPERTIES == ["history"]


def test_feedback_report_fields():
    fields = BridgeContract.FEEDBACK_REPORT_FIELDS
    assert "insights" in fields
    assert "failure_clusters" in fields
    assert "dominant_layer_trends" in fields
    assert len(fields) == 3


def test_feedback_insight_fields():
    fields = BridgeContract.FEEDBACK_INSIGHT_FIELDS
    assert fields == ["insight_type", "description", "severity", "data"]


def test_enriched_event_fields():
    fields = BridgeContract.ENRICHED_EVENT_FIELDS
    for f in ("event_id", "session_id", "sequence_no", "correlation_id",
               "host_event", "p3_proposal", "p4_decision", "execution_result",
               "hal_trace", "status"):
        assert f in fields
    assert len(fields) == 10


def test_enriched_event_methods():
    assert BridgeContract.ENRICHED_EVENT_METHODS == ["add_trace"]


def test_enriched_event_properties():
    props = BridgeContract.ENRICHED_EVENT_PROPERTIES
    assert "has_full_cycle" in props
    assert "final_verdict" in props
    assert "final_status" in props
    assert len(props) == 3


def test_check_observation_tap_missing():
    violations = BridgeContract.check_observation_tap(object())
    assert len(violations) > 0
    assert any("missing method" in v for v in violations)


def test_check_observation_tap_valid():
    class GoodTap:
        total_traced = 0
        completed_cycles = 0
        def tap_event_received(self): pass
        def tap_p3_proposal(self): pass
        def tap_p4_decision(self): pass
        def tap_execution_result(self): pass
        def tap_blocked(self): pass
        def get_enriched(self): pass
        def get_by_session(self): pass
        def get_by_status(self): pass
        def subscribe(self): pass
    assert BridgeContract.check_observation_tap(GoodTap()) == []


def test_check_observation_tap_property_callable():
    class BadTap:
        total_traced = lambda self: None
        completed_cycles = lambda self: None
        def tap_event_received(self): pass
        def tap_p3_proposal(self): pass
        def tap_p4_decision(self): pass
        def tap_execution_result(self): pass
        def tap_blocked(self): pass
        def get_enriched(self): pass
        def get_by_session(self): pass
        def get_by_status(self): pass
        def subscribe(self): pass
    violations = BridgeContract.check_observation_tap(BadTap())
    assert any("is callable" in v for v in violations)


def test_check_feedback_bridge_missing():
    violations = BridgeContract.check_feedback_bridge(object())
    assert any("missing method" in v for v in violations)


def test_check_feedback_bridge_valid():
    class GoodBridge:
        history = []
        def analyze(self): pass
    assert BridgeContract.check_feedback_bridge(GoodBridge()) == []


def test_check_feedback_report_missing():
    assert len(BridgeContract.check_feedback_report(object())) == 3


def test_check_feedback_report_valid():
    class GoodReport:
        insights = []
        failure_clusters = {}
        dominant_layer_trends = {}
    assert BridgeContract.check_feedback_report(GoodReport()) == []


def test_check_feedback_insight_missing():
    assert len(BridgeContract.check_feedback_insight(object())) == 4


def test_check_feedback_insight_valid():
    class GoodInsight:
        insight_type = ""
        description = ""
        severity = 0.0
        data = {}
    assert BridgeContract.check_feedback_insight(GoodInsight()) == []


def test_check_enriched_event_missing_all():
    assert len(BridgeContract.check_enriched_event(object())) > 0


def test_check_enriched_event_valid():
    class GoodEvent:
        event_id = ""
        session_id = ""
        sequence_no = 0
        correlation_id = ""
        host_event = None
        p3_proposal = None
        p4_decision = None
        execution_result = None
        hal_trace = None
        status = ""
        has_full_cycle = False
        final_verdict = ""
        final_status = ""
        def add_trace(self): pass
    assert BridgeContract.check_enriched_event(GoodEvent()) == []


def test_check_enriched_event_missing_method():
    class PartialEvent:
        event_id = ""
        session_id = ""
        sequence_no = 0
        correlation_id = ""
        host_event = None
        p3_proposal = None
        p4_decision = None
        execution_result = None
        hal_trace = None
        status = ""
        has_full_cycle = False
        final_verdict = ""
        final_status = ""
    violations = BridgeContract.check_enriched_event(PartialEvent())
    assert any("missing method" in v for v in violations)


def test_check_enriched_event_method_not_callable():
    class BadEvent:
        event_id = ""
        session_id = ""
        sequence_no = 0
        correlation_id = ""
        host_event = None
        p3_proposal = None
        p4_decision = None
        execution_result = None
        hal_trace = None
        status = ""
        has_full_cycle = False
        final_verdict = ""
        final_status = ""
        add_trace = "not_callable"
    violations = BridgeContract.check_enriched_event(BadEvent())
    assert any("not callable" in v for v in violations)


def test_bridge_contract_fingerprint_registered():
    fp = get_expected_fingerprint("BridgeContract")
    assert fp is not None
    assert isinstance(fp, str)
