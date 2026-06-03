import pytest
from cognitive_runtime.intelligence.intelligence_store import (
    IntelligenceStore,
)
from cognitive_runtime.intelligence.pattern_miner import PatternMiner
from cognitive_runtime.intelligence.failure_signature import FailureSignatureDetector
from cognitive_runtime.intelligence.decision_fingerprint import DecisionFingerprintBuilder
from cognitive_runtime.intelligence.compression_engine import CompressionEngine, CompressionReport
from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.contracts.causal_graph import CausalGraph


def empty_graph():
    return CausalGraph({}, [])


def make_trace(event_id, preflight_valid=True, p4_verdict="ALLOW",
               execution_status="SUCCESS", final_status="P4_ALLOW",
               risk_score=0.1, capabilities=None, p4_risk_level="low",
               p4_rule_triggered=None, preflight_reason=None,
               preflight_rules_triggered=None, execution_error=None,
               p4_reason="test", total_time=0.0):
    return ExecutionTrace(
        event_id=event_id,
        session_id="s1",
        sequence_no=1,
        correlation_id=f"c_{event_id}",
        preflight_valid=preflight_valid,
        preflight_reason=preflight_reason,
        preflight_rules_triggered=preflight_rules_triggered or [],
        risk_score=risk_score,
        p4_verdict=p4_verdict,
        p4_reason=p4_reason,
        p4_risk_level=p4_risk_level,
        p4_rule_triggered=p4_rule_triggered,
        execution_status=execution_status,
        execution_error=execution_error,
        capabilities_checked=capabilities or [],
        total_time=total_time,
        final_status=final_status,
    )


# ════════════════════════════════════════════
# PatternMiner
# ════════════════════════════════════════════

class TestPatternMiner:
    def test_mine_returns_new_pattern_count(self):
        store = IntelligenceStore()
        miner = PatternMiner(store)
        traces = [
            make_trace("e1", p4_verdict="ALLOW", execution_status="SUCCESS"),
            make_trace("e2", p4_verdict="BLOCK", final_status="P4_BLOCK"),
        ]
        count = miner.mine(empty_graph(), traces)
        assert count == 2
        assert len(store.patterns) == 2

    def test_mine_with_duplicate_traces_does_not_create_new(self):
        store = IntelligenceStore()
        miner = PatternMiner(store)
        trace = make_trace("e1", p4_verdict="ALLOW", execution_status="SUCCESS", capabilities=["fs.read"])
        traces = [trace, trace]
        count = miner.mine(empty_graph(), traces)
        assert count == 1
        assert len(store.patterns) == 1

    def test_mine_duplicate_increments_frequency(self):
        store = IntelligenceStore()
        miner = PatternMiner(store)
        t = make_trace("e1", p4_verdict="ALLOW", execution_status="SUCCESS")
        miner.mine(empty_graph(), [t])
        miner.mine(empty_graph(), [t])
        assert len(store.patterns) == 1
        stored = list(store.patterns.values())[0]
        assert stored.frequency == 2

    def test_mine_multiple_batches_accumulates(self):
        store = IntelligenceStore()
        miner = PatternMiner(store)
        batch1 = [make_trace("e1", p4_verdict="ALLOW", execution_status="SUCCESS")]
        batch2 = [make_trace("e2", p4_verdict="BLOCK", final_status="P4_BLOCK")]
        miner.mine(empty_graph(), batch1)
        miner.mine(empty_graph(), batch2)
        assert len(store.patterns) == 2

    def test_trace_structure_signature_consistency(self):
        miner = PatternMiner(IntelligenceStore())
        t1 = make_trace("e1", p4_verdict="ALLOW", execution_status="SUCCESS")
        t2 = make_trace("e2", p4_verdict="ALLOW", execution_status="SUCCESS")
        sig1 = miner._trace_structure_signature(t1)
        sig2 = miner._trace_structure_signature(t2)
        assert sig1 == sig2

    def test_trace_structure_signature_different_verdict(self):
        miner = PatternMiner(IntelligenceStore())
        t1 = make_trace("e1", p4_verdict="ALLOW")
        t2 = make_trace("e2", p4_verdict="BLOCK")
        assert miner._trace_structure_signature(t1) != miner._trace_structure_signature(t2)

    def test_build_context_shape_includes_fields(self):
        miner = PatternMiner(IntelligenceStore())
        t = make_trace("e1", p4_verdict="ALLOW", execution_status="SUCCESS",
                        final_status="P4_ALLOW", risk_score=0.75,
                        capabilities=["fs.read", "net.http"])
        ctx = miner._build_context_shape(t)
        assert ctx["preflight_valid"] is True
        assert ctx["p4_verdict"] == "ALLOW"
        assert ctx["execution_status"] == "SUCCESS"
        assert ctx["final_status"] == "P4_ALLOW"
        assert ctx["risk_score"] == 0.75
        assert ctx["capabilities"] == ["fs.read", "net.http"]
        assert ctx["has_error"] is False

    def test_build_context_shape_has_error(self):
        miner = PatternMiner(IntelligenceStore())
        t = make_trace("e1", execution_status="FAILED", execution_error="crash")
        ctx = miner._build_context_shape(t)
        assert ctx["has_error"] is True

    def test_mine_empty_traces(self):
        store = IntelligenceStore()
        miner = PatternMiner(store)
        count = miner.mine(empty_graph(), [])
        assert count == 0


# ════════════════════════════════════════════
# FailureSignatureDetector
# ════════════════════════════════════════════

class TestFailureSignatureDetector:
    def test_detect_skips_successful_traces(self):
        store = IntelligenceStore()
        detector = FailureSignatureDetector(store)
        traces = [make_trace("e1", execution_status="SUCCESS", final_status="P4_ALLOW")]
        count = detector.detect(empty_graph(), traces)
        assert count == 0
        assert len(store.failures) == 0

    def test_detect_sandbox_failed(self):
        store = IntelligenceStore()
        detector = FailureSignatureDetector(store)
        traces = [make_trace("e1", execution_status="FAILED",
                             final_status="SANDBOX_FAILED",
                             execution_error="segfault")]
        count = detector.detect(empty_graph(), traces)
        assert count == 1
        assert len(store.failures) == 1

    def test_detect_p4_block(self):
        store = IntelligenceStore()
        detector = FailureSignatureDetector(store)
        traces = [make_trace("e1", p4_verdict="BLOCK", final_status="P4_BLOCK")]
        count = detector.detect(empty_graph(), traces)
        assert count == 1

    def test_detect_p4_defer(self):
        store = IntelligenceStore()
        detector = FailureSignatureDetector(store)
        traces = [make_trace("e1", p4_verdict="DEFER", final_status="P4_DEFER")]
        count = detector.detect(empty_graph(), traces)
        assert count == 1

    def test_detect_p4_review(self):
        store = IntelligenceStore()
        detector = FailureSignatureDetector(store)
        traces = [make_trace("e1", p4_verdict="REVIEW", final_status="P4_REVIEW")]
        count = detector.detect(empty_graph(), traces)
        assert count == 1

    def test_detect_blocked_by_preflight(self):
        store = IntelligenceStore()
        detector = FailureSignatureDetector(store)
        traces = [make_trace("e1", preflight_valid=False,
                             final_status="BLOCKED_BY_PREFLIGHT")]
        count = detector.detect(empty_graph(), traces)
        assert count == 1

    def test_detect_duplicate_chain_does_not_create_new(self):
        store = IntelligenceStore()
        detector = FailureSignatureDetector(store)
        t = make_trace("e1", execution_status="FAILED",
                       final_status="SANDBOX_FAILED", execution_error="crash")
        detector.detect(empty_graph(), [t])
        count = detector.detect(empty_graph(), [t])
        assert count == 0
        assert len(store.failures) == 1

    def test_detect_duplicate_chain_increments_frequency(self):
        store = IntelligenceStore()
        detector = FailureSignatureDetector(store)
        t = make_trace("e1", execution_status="FAILED",
                       final_status="SANDBOX_FAILED", execution_error="crash")
        detector.detect(empty_graph(), [t])
        detector.detect(empty_graph(), [t])
        stored = list(store.failures.values())[0]
        assert stored.frequency == 2

    def test_extract_trigger_chain_preflight_block(self):
        detector = FailureSignatureDetector(IntelligenceStore())
        t = make_trace("e1", preflight_valid=False,
                       preflight_reason="bad_sandbox",
                       preflight_rules_triggered=["rule_1"],
                       final_status="BLOCKED_BY_PREFLIGHT")
        chain = detector._extract_trigger_chain(t)
        assert chain[0] == "PREFLIGHT_BLOCK"
        assert "reason:bad_sandbox" in chain
        assert "rules:rule_1" in chain

    def test_extract_trigger_chain_p4_block(self):
        detector = FailureSignatureDetector(IntelligenceStore())
        t = make_trace("e1", p4_verdict="BLOCK",
                       p4_reason="violation", p4_risk_level="high",
                       final_status="P4_BLOCK")
        chain = detector._extract_trigger_chain(t)
        assert "PREFLIGHT_PASS" in chain
        assert "P4_BLOCK" in chain

    def test_extract_trigger_chain_sandbox_failed(self):
        detector = FailureSignatureDetector(IntelligenceStore())
        t = make_trace("e1", p4_verdict="ALLOW",
                       execution_status="FAILED",
                       execution_error="crash",
                       final_status="SANDBOX_FAILED")
        chain = detector._extract_trigger_chain(t)
        assert "SANDBOX_FAILED" in chain
        assert "error:crash" in chain

    def test_classify_severity_sandbox_failed(self):
        detector = FailureSignatureDetector(IntelligenceStore())
        t = make_trace("e1", p4_verdict="ALLOW", execution_status="FAILED",
                       final_status="SANDBOX_FAILED")
        assert detector._classify_severity(t) == "critical"

    def test_classify_severity_p4_block(self):
        detector = FailureSignatureDetector(IntelligenceStore())
        t = make_trace("e1", p4_verdict="BLOCK", final_status="P4_BLOCK")
        assert detector._classify_severity(t) == "high"

    def test_classify_severity_p4_defer(self):
        detector = FailureSignatureDetector(IntelligenceStore())
        t = make_trace("e1", p4_verdict="DEFER", final_status="P4_DEFER")
        assert detector._classify_severity(t) == "medium"

    def test_classify_severity_p4_review(self):
        detector = FailureSignatureDetector(IntelligenceStore())
        t = make_trace("e1", p4_verdict="REVIEW", final_status="P4_REVIEW")
        assert detector._classify_severity(t) == "medium"

    def test_classify_severity_preflight_block(self):
        detector = FailureSignatureDetector(IntelligenceStore())
        t = make_trace("e1", preflight_valid=False, final_status="BLOCKED_BY_PREFLIGHT")
        assert detector._classify_severity(t) == "low"

    def test_classify_severity_unknown(self):
        detector = FailureSignatureDetector(IntelligenceStore())
        t = make_trace("e1", p4_verdict="ALLOW", execution_status="UNKNOWN",
                       final_status="UNKNOWN")
        assert detector._classify_severity(t) == "unknown"

    def test_detect_empty_traces(self):
        detector = FailureSignatureDetector(IntelligenceStore())
        assert detector.detect(empty_graph(), []) == 0

    def test_detect_mixed_skips_and_processes(self):
        store = IntelligenceStore()
        detector = FailureSignatureDetector(store)
        traces = [
            make_trace("e1", execution_status="SUCCESS", final_status="P4_ALLOW"),
            make_trace("e2", execution_status="FAILED", final_status="SANDBOX_FAILED"),
            make_trace("e3", p4_verdict="BLOCK", final_status="P4_BLOCK"),
        ]
        count = detector.detect(empty_graph(), traces)
        assert count == 2
        assert len(store.failures) == 2


# ════════════════════════════════════════════
# DecisionFingerprintBuilder
# ════════════════════════════════════════════

class TestDecisionFingerprintBuilder:
    def test_build_returns_fingerprint_count(self):
        store = IntelligenceStore()
        builder = DecisionFingerprintBuilder(store)
        traces = [
            make_trace("e1", p4_verdict="ALLOW", risk_score=0.1,
                       capabilities=["fs.read"]),
            make_trace("e2", p4_verdict="BLOCK", risk_score=0.9,
                       capabilities=["net.http"]),
        ]
        count = builder.build(traces)
        assert count == 2
        assert len(store.fingerprints) == 2

    def test_build_duplicate_context_hash_skipped(self):
        store = IntelligenceStore()
        builder = DecisionFingerprintBuilder(store)
        t = make_trace("e1", p4_verdict="ALLOW", risk_score=0.1,
                       capabilities=["fs.read"])
        builder.build([t])
        count = builder.build([t])
        assert count == 0
        assert len(store.fingerprints) == 1

    def test_build_same_context_different_event_id(self):
        store = IntelligenceStore()
        builder = DecisionFingerprintBuilder(store)
        t1 = make_trace("e1", p4_verdict="ALLOW", risk_score=0.1, capabilities=["fs.read"])
        t2 = make_trace("e2", p4_verdict="ALLOW", risk_score=0.1, capabilities=["fs.read"])
        builder.build([t1])
        count = builder.build([t2])
        assert count == 0

    def test_build_context_hash_different_risk_score(self):
        store = IntelligenceStore()
        builder = DecisionFingerprintBuilder(store)
        t1 = make_trace("e1", p4_verdict="ALLOW", risk_score=0.1, capabilities=["fs.read"])
        t2 = make_trace("e2", p4_verdict="ALLOW", risk_score=0.9, capabilities=["fs.read"])
        assert builder.build([t1]) == 1
        assert builder.build([t2]) == 1

    def test_fingerprint_fields_set_correctly(self):
        store = IntelligenceStore()
        builder = DecisionFingerprintBuilder(store)
        t = make_trace("e1", p4_verdict="BLOCK", risk_score=0.8,
                       capabilities=["net.http", "fs.read"],
                       p4_risk_level="high", p4_rule_triggered="rule_42")
        builder.build([t])
        fp = list(store.fingerprints.values())[0]
        assert fp.p4_verdict == "BLOCK"
        assert fp.capability_profile == ["fs.read", "net.http"]

    def test_build_empty_traces(self):
        builder = DecisionFingerprintBuilder(IntelligenceStore())
        assert builder.build([]) == 0

    def test_build_multiple_batches(self):
        store = IntelligenceStore()
        builder = DecisionFingerprintBuilder(store)
        batch1 = [make_trace("e1", p4_verdict="ALLOW", risk_score=0.1)]
        batch2 = [make_trace("e2", p4_verdict="BLOCK", risk_score=0.9)]
        builder.build(batch1)
        builder.build(batch2)
        assert len(store.fingerprints) == 2


# ════════════════════════════════════════════
# CompressionEngine
# ════════════════════════════════════════════

class TestCompressionEngine:
    def test_process_with_traces_returns_report(self):
        engine = CompressionEngine()
        traces = [make_trace("e1", p4_verdict="ALLOW", execution_status="SUCCESS")]
        report = engine.process(empty_graph(), traces)
        assert isinstance(report, CompressionReport)

    def test_process_returns_counts(self):
        engine = CompressionEngine()
        traces = [
            make_trace("e1", p4_verdict="ALLOW", execution_status="SUCCESS"),
            make_trace("e2", p4_verdict="BLOCK", execution_status="UNKNOWN",
                       final_status="P4_BLOCK"),
        ]
        report = engine.process(empty_graph(), traces)
        assert report.patterns_found >= 1
        assert report.failures_detected >= 1
        assert report.fingerprints_built >= 1

    def test_process_empty_traces_returns_empty_report(self):
        engine = CompressionEngine()
        report = engine.process(empty_graph(), [])
        assert report.patterns_found == 0
        assert report.failures_detected == 0
        assert report.fingerprints_built == 0
        assert report.total_patterns == 0
        assert report.total_failures == 0
        assert report.total_fingerprints == 0

    def test_process_multiple_batches_accumulates_totals(self):
        engine = CompressionEngine()
        t1 = make_trace("e1", p4_verdict="ALLOW", execution_status="SUCCESS")
        t2 = make_trace("e2", p4_verdict="BLOCK", execution_status="UNKNOWN",
                        final_status="P4_BLOCK")
        t3 = make_trace("e3", p4_verdict="ALLOW", execution_status="FAILED",
                        final_status="SANDBOX_FAILED")

        r1 = engine.process(empty_graph(), [t1, t2])
        assert r1.total_patterns == 2
        assert r1.total_failures >= 1
        assert r1.total_fingerprints >= 2

        r2 = engine.process(empty_graph(), [t3])
        assert r2.patterns_found >= 1
        assert r2.failures_detected >= 1
        # fingerprint context may be deduplicated if identical to batch 1
        assert r2.total_patterns >= 1
        assert r2.total_failures >= 1

    def test_process_returns_cumulative_in_report(self):
        engine = CompressionEngine()
        t = make_trace("e1", p4_verdict="ALLOW", execution_status="SUCCESS")
        r1 = engine.process(empty_graph(), [t])
        r2 = engine.process(empty_graph(), [t])
        assert r2.total_patterns == r1.total_patterns
        assert r2.total_failures == r1.total_failures

    def test_store_property(self):
        engine = CompressionEngine()
        assert engine.store is not None
        assert isinstance(engine.store, IntelligenceStore)

    def test_total_cycles_property(self):
        engine = CompressionEngine()
        assert engine.total_cycles == 0
        engine.process(empty_graph(), [make_trace("e1", execution_status="SUCCESS")])
        assert engine.total_cycles == 1
        engine.process(empty_graph(), [make_trace("e2", execution_status="SUCCESS")])
        assert engine.total_cycles == 2

    def test_store_shares_state_across_components(self):
        engine = CompressionEngine()
        t = make_trace("e1", p4_verdict="ALLOW", execution_status="SUCCESS")
        engine.process(empty_graph(), [t])
        assert len(engine.store.patterns) >= 1
        assert len(engine.store.fingerprints) >= 1
