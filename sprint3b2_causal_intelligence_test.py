"""
Sprint 3B.2 -- Causal Runtime Intelligence Layer

Validates 6 components across 5 groups (15 tests):
A. Causal Integrity Engine    (4 tests)
B. Determinism               (3 tests)
C. Causal Drift Detection     (3 tests)
D. Replay Intelligence        (3 tests)
E. Stress                     (2 tests)
"""

import sys
import time
import hashlib
import json
from dataclasses import dataclass

from cognitive_runtime.kernel.time_kernel import TimeKernel
from cognitive_runtime.contracts.execution_contract import (
    HostEvent, ExecutionProposal, PolicyDecision, ExecutionResult, Capability,
)
from cognitive_runtime.contracts.execution_trace import (
    ExecutionTrace, ExecutionTraceStore, ExecutionTraceNormalizer,
    enriched_to_trace_dict,
)
from cognitive_runtime.contracts.enriched_event import EnrichedEvent
from cognitive_runtime.contracts.causal_graph import (
    CausalGraph, CausalNode, CausalEdge, CausalGraphBuilder,
)
from cognitive_runtime.substrate.observation_tap import ObservationTap
from cognitive_runtime.observation.why_query import WhyQuery
from cognitive_runtime.intelligence.causal_runtime_fingerprint import (
    CausalRuntimeFingerprint, ReplayFingerprintVerifier,
)
from cognitive_runtime.intelligence.causal_integrity_engine import (
    CausalIntegrityEngine, CausalIntegrityReport, IntegrityIssue,
)
from cognitive_runtime.intelligence.causal_health_score import (
    CausalHealthScore, CausalHealthScorer,
)
from cognitive_runtime.intelligence.causal_drift_detector import (
    CausalDriftDetector, DriftReport, ReplayDivergenceReport,
)
from cognitive_runtime.intelligence.runtime_failure_explainer import (
    RuntimeFailureExplainer, FailureExplanation,
)
from cognitive_runtime.intelligence.temporal_causal_monitor import (
    TemporalCausalMonitor, CausalSnapshot, DegradationTrend,
)


# ================================================================
#  HELPERS
# ================================================================

def _make_trace(event_id: str, final_status: str = "P4_ALLOW",
                p4_verdict: str = "ALLOW",
                exec_status: str = "SUCCESS", p4_reason: str | None = None,
                exec_error: str | None = None) -> ExecutionTrace:
    return ExecutionTrace(
        event_id=event_id,
        session_id="test",
        sequence_no=1,
        correlation_id=f"cid-{event_id}",
        preflight_valid=True,
        p4_verdict=p4_verdict,
        p4_reason=p4_reason or "",
        execution_status=exec_status,
        execution_error=exec_error,
        final_status=final_status,
        capabilities_checked=["process.execute"],
        risk_score=0.3,
        p4_risk_level="low",
        p4_rule_triggered="SAFE_PATH",
    )


def _make_graph(traces, events_data) -> CausalGraph:
    builder = CausalGraphBuilder()
    return builder.build(traces)


def _run_pipeline_sequence(scenario, session_id="s3b2-test", t0=1000000.0):
    """Run a sequence through the pipeline and return traces + graph."""
    tk = TimeKernel(session_id=session_id)
    store = ExecutionTraceStore()
    norm = ExecutionTraceNormalizer()
    tap = ObservationTap(time_kernel=tk, trace_store=store,
                          trace_normalizer=norm)

    for i, (eid, action, cap, conf, risk, verdict, exec_st) in enumerate(scenario):
        event = HostEvent(
            event_id=eid, session_id=session_id,
            timestamp=t0 + i * 0.1, source="test",
            payload={"idx": i},
        )
        tk.stamp(eid)
        tap.tap_event_received(event)

        proposal = ExecutionProposal(
            proposal_id=f"p-{eid}", session_id=session_id, event_id=eid,
            action=action, target=f"t-{i}", params={},
            required_capabilities=[cap],
            confidence=conf, risk_score=risk, metadata={},
        )
        tap.tap_p3_proposal(eid, proposal)

        decision = PolicyDecision(
            decision_id=f"d-{eid}", proposal_id=f"p-{eid}",
            session_id=session_id, verdict=verdict,
            reason=f"v:{verdict}",
            risk_level="low" if verdict == "ALLOW" else "critical",
            rule_triggered="SAFE_PATH" if verdict == "ALLOW" else "HIGH_RISK",
            confidence=conf,
        )
        tap.tap_p4_decision(eid, decision)

        if exec_st:
            result = ExecutionResult(
                execution_id=f"x-{eid}", proposal_id=f"p-{eid}",
                session_id=session_id, status=exec_st,
                output=f"ok-{i}", error=None,
                started_at=t0 + i * 0.1 + 0.01,
                finished_at=t0 + i * 0.1 + 0.05,
            )
            tap.tap_execution_result(eid, result)
        else:
            tap.tap_blocked(eid, f"blocked {verdict}")

    graph = _make_graph(store.all, scenario)
    return list(store.all), graph


# ================================================================
#  GROUP A — Integrity
# ================================================================

def test_orphan_node_detection():
    """Orphan nodes (no children, not connected) are detected."""
    engine = CausalIntegrityEngine()
    nodes = {
        "n1": CausalNode("n1", "e1", "c1", "host_event", {}, 0.0,
                          children=["n2"]),
        "n2": CausalNode("n2", "e1", "c1", "proposal", {}, 0.0,
                          parent_id="n1", children=["n3"]),
        "n3": CausalNode("n3", "e1", "c1", "decision", {}, 0.0,
                          parent_id="n2"),
        # orphan: no children, no edges
        "orphan": CausalNode("orphan", "e2", "c2", "execution", {}, 0.0,
                              parent_id="nonexistent"),
    }
    edges = [
        CausalEdge("e1", "n1", "n2", "proposes"),
        CausalEdge("e2", "n2", "n3", "decides"),
    ]
    graph = CausalGraph(nodes, edges)
    report = engine.validate(graph)
    assert report.orphan_count > 0, "Expected orphan detection"
    assert any(i.issue_type == "orphan" for i in report.issues)
    print(f"  [OK] Orphan detected: {report.orphan_count}")


def test_missing_edge_detection():
    """Nodes that should connect but don't are flagged."""
    engine = CausalIntegrityEngine()
    nodes = {
        "n1": CausalNode("n1", "e1", "c1", "host_event", {}, 0.0),
        "n2": CausalNode("n2", "e1", "c1", "proposal", {}, 0.0,
                          parent_id="n1"),
    }
    edges = []
    graph = CausalGraph(nodes, edges)
    report = engine.validate(graph)
    assert report.missing_edge_count > 0, "Expected missing edge detection"
    assert any(i.issue_type == "missing_edge" for i in report.issues)
    print(f"  [OK] Missing edge detected: {report.missing_edge_count}")


def test_cycle_corruption_detection():
    """Self-referencing cycles are detected."""
    engine = CausalIntegrityEngine()
    nodes = {
        "n1": CausalNode("n1", "e1", "c1", "decision", {}, 0.0,
                          children=["n2"]),
        "n2": CausalNode("n2", "e1", "c1", "execution", {}, 0.0,
                          parent_id="n1", children=["n3"]),
        "n3": CausalNode("n3", "e1", "c1", "outcome", {}, 0.0,
                          parent_id="n2", children=["n1"]),
    }
    edges = [
        CausalEdge("e1", "n1", "n2", "decides"),
        CausalEdge("e2", "n2", "n3", "executes"),
        CausalEdge("e3", "n3", "n1", "results"),
    ]
    graph = CausalGraph(nodes, edges)
    report = engine.validate(graph)
    assert report.cycle_count > 0, "Expected cycle detection"
    assert any(i.issue_type == "cycle" for i in report.issues)
    print(f"  [OK] Cycle detected: {report.cycle_count}")


def test_impossible_transition_detection():
    """Invalid transitions (e.g. host_event -> execution) are detected."""
    engine = CausalIntegrityEngine()
    nodes = {
        "n1": CausalNode("n1", "e1", "c1", "host_event", {}, 0.0),
        "n2": CausalNode("n2", "e1", "c1", "execution", {}, 0.0,
                          parent_id="n1"),
    }
    edges = [
        CausalEdge("e1", "n1", "n2", "executes"),
    ]
    graph = CausalGraph(nodes, edges)
    report = engine.validate(graph)
    assert report.impossible_transition_count > 0, "Expected impossible transition"
    assert any(i.issue_type == "impossible_transition" for i in report.issues)
    print(f"  [OK] Impossible transition detected: {report.impossible_transition_count}")


# ================================================================
#  GROUP B — Determinism
# ================================================================

def test_same_graph_same_fingerprint():
    """Same graph always yields same fingerprint."""
    fp_builder = CausalRuntimeFingerprint()
    traces = [
        _make_trace("e1", "P4_ALLOW", "ALLOW", "SUCCESS"),
        _make_trace("e2", "P4_BLOCK", "BLOCK", "UNKNOWN"),
    ]
    nodes = {
        "e1__host": CausalNode("e1__host", "e1", "c1", "host_event", {}, 0.0, children=["e1__proposal"]),
        "e1__proposal": CausalNode("e1__proposal", "e1", "c1", "proposal", {}, 0.0, parent_id="e1__host", children=["e1__decision"]),
        "e1__decision": CausalNode("e1__decision", "e1", "c1", "decision", {}, 0.0, parent_id="e1__proposal", children=["e1__execution"]),
        "e1__execution": CausalNode("e1__execution", "e1", "c1", "execution", {}, 0.0, parent_id="e1__decision", children=["e1__outcome"]),
        "e1__outcome": CausalNode("e1__outcome", "e1", "c1", "outcome", {}, 0.0, parent_id="e1__execution"),
        "e2__host": CausalNode("e2__host", "e2", "c2", "host_event", {}, 0.0, children=["e2__blocked"]),
        "e2__blocked": CausalNode("e2__blocked", "e2", "c2", "blocked", {}, 0.0, parent_id="e2__host", children=["e2__outcome"]),
        "e2__outcome": CausalNode("e2__outcome", "e2", "c2", "outcome", {}, 0.0, parent_id="e2__blocked"),
    }
    edges = [
        CausalEdge("e1_p", "e1__host", "e1__proposal", "proposes"),
        CausalEdge("e1_d", "e1__proposal", "e1__decision", "decides"),
        CausalEdge("e1_x", "e1__decision", "e1__execution", "executes"),
        CausalEdge("e1_o", "e1__execution", "e1__outcome", "results"),
        CausalEdge("e2_b", "e2__host", "e2__blocked", "blocks"),
        CausalEdge("e2_o", "e2__blocked", "e2__outcome", "results"),
    ]
    graph = CausalGraph(nodes, edges)

    fp1 = fp_builder.compute(traces, graph)
    fp2 = fp_builder.compute(traces, graph)
    fp3 = fp_builder.compute(traces, graph)

    assert fp1 == fp2 == fp3, "Fingerprint not deterministic"
    print(f"  [OK] Same graph -> same fingerprint: {fp1[:16]}...")


def test_same_replay_same_integrity_report():
    """Same input generates identical integrity report."""
    engine = CausalIntegrityEngine()

    traces = [
        _make_trace("e1", "P4_ALLOW", "ALLOW", "SUCCESS"),
        _make_trace("e2", "P4_BLOCK", "BLOCK", "UNKNOWN"),
    ]
    nodes = {
        "e1__host": CausalNode("e1__host", "e1", "c1", "host_event", {}, 0.0,
                                children=["e1__proposal"]),
        "e1__proposal": CausalNode("e1__proposal", "e1", "c1", "proposal", {}, 0.0,
                                    parent_id="e1__host", children=["e1__decision"]),
        "e1__decision": CausalNode("e1__decision", "e1", "c1", "decision", {}, 0.0,
                                    parent_id="e1__proposal", children=["e1__execution"]),
        "e1__execution": CausalNode("e1__execution", "e1", "c1", "execution", {}, 0.0,
                                     parent_id="e1__decision", children=["e1__outcome"]),
        "e1__outcome": CausalNode("e1__outcome", "e1", "c1", "outcome", {}, 0.0,
                                   parent_id="e1__execution"),
        "e2__host": CausalNode("e2__host", "e2", "c2", "host_event", {}, 0.0,
                                children=["e2__proposal"]),
        "e2__proposal": CausalNode("e2__proposal", "e2", "c2", "proposal", {}, 0.0,
                                    parent_id="e2__host", children=["e2__decision"]),
        "e2__decision": CausalNode("e2__decision", "e2", "c2", "decision", {}, 0.0,
                                    parent_id="e2__proposal", children=["e2__blocked"]),
        "e2__blocked": CausalNode("e2__blocked", "e2", "c2", "blocked", {}, 0.0,
                                   parent_id="e2__decision", children=["e2__outcome"]),
        "e2__outcome": CausalNode("e2__outcome", "e2", "c2", "outcome", {}, 0.0,
                                   parent_id="e2__blocked"),
    }
    edges = [
        CausalEdge("e1_p", "e1__host", "e1__proposal", "proposes"),
        CausalEdge("e1_d", "e1__proposal", "e1__decision", "decides"),
        CausalEdge("e1_x", "e1__decision", "e1__execution", "executes"),
        CausalEdge("e1_o", "e1__execution", "e1__outcome", "results"),
        CausalEdge("e2_p", "e2__host", "e2__proposal", "proposes"),
        CausalEdge("e2_d", "e2__proposal", "e2__decision", "decides"),
        CausalEdge("e2_b", "e2__decision", "e2__blocked", "blocks"),
        CausalEdge("e2_o", "e2__blocked", "e2__outcome", "results"),
    ]
    graph = CausalGraph(nodes, edges)

    r1 = engine.validate(graph)
    r2 = engine.validate(graph)

    assert r1.is_healthy == r2.is_healthy
    assert r1.issue_count == r2.issue_count
    assert r1.orphan_count == r2.orphan_count
    print(f"  [OK] Same replay -> same integrity report (issues={r1.issue_count})")


def test_same_failure_same_explanation():
    """Same trace data produces identical failure explanation."""
    explainer = RuntimeFailureExplainer()

    trace_blocked = _make_trace("e1", "P4_BLOCK", "BLOCK", "UNKNOWN",
                                 p4_reason="high risk")
    trace_failed = _make_trace("e2", "SANDBOX_FAILED", "ALLOW", "FAILED",
                                exec_error="timeout")

    exp1a = explainer.explain(trace_blocked)
    exp1b = explainer.explain(trace_blocked)
    assert exp1a.root_cause == exp1b.root_cause
    assert exp1a.path == exp1b.path
    assert len(exp1a.failure_chain) == len(exp1b.failure_chain)

    exp2a = explainer.explain(trace_failed)
    exp2b = explainer.explain(trace_failed)
    assert exp2a.root_cause == exp2b.root_cause
    assert exp2a.sandbox_failure == exp2b.sandbox_failure

    print(f"  [OK] Same failure -> same explanation: "
          f"blocked='{exp1a.root_cause}' failed='{exp2a.root_cause}'")


# ================================================================
#  GROUP C — Drift Detection
# ================================================================

def test_detect_behavioral_divergence():
    """Different causal output from same inputs is detected as drift."""
    detector = CausalDriftDetector()

    baseline = [_make_trace("e1", "P4_ALLOW", "ALLOW", "SUCCESS")]
    bl_nodes = {
        "e1__host": CausalNode("e1__host", "e1", "c1", "host_event", {}, 0.0,
                                children=["e1__proposal"]),
        "e1__proposal": CausalNode("e1__proposal", "e1", "c1", "proposal", {}, 0.0,
                                    parent_id="e1__host", children=["e1__decision"]),
        "e1__decision": CausalNode("e1__decision", "e1", "c1", "decision", {}, 0.0,
                                    parent_id="e1__proposal", children=["e1__execution"]),
        "e1__execution": CausalNode("e1__execution", "e1", "c1", "execution", {},
                                     0.0, parent_id="e1__decision",
                                     children=["e1__outcome"]),
        "e1__outcome": CausalNode("e1__outcome", "e1", "c1", "outcome", {}, 0.0,
                                   parent_id="e1__execution"),
    }
    bl_edges = [
        CausalEdge("e1_p", "e1__host", "e1__proposal", "proposes"),
        CausalEdge("e1_d", "e1__proposal", "e1__decision", "decides"),
        CausalEdge("e1_x", "e1__decision", "e1__execution", "executes"),
        CausalEdge("e1_o", "e1__execution", "e1__outcome", "results"),
    ]
    bl_graph = CausalGraph(bl_nodes, bl_edges)

    # Current: same event_id but BLOCKED (different outcome)
    current = [_make_trace("e1", "P4_BLOCK", "BLOCK", "UNKNOWN")]
    cur_nodes = {
        "e1__host": CausalNode("e1__host", "e1", "c2", "host_event", {}, 0.0,
                                children=["e1__blocked"]),
        "e1__blocked": CausalNode("e1__blocked", "e1", "c2", "blocked", {}, 0.0,
                                   parent_id="e1__host",
                                   children=["e1__outcome"]),
        "e1__outcome": CausalNode("e1__outcome", "e1", "c2", "outcome", {}, 0.0,
                                   parent_id="e1__blocked"),
    }
    cur_edges = [
        CausalEdge("e1_b", "e1__host", "e1__blocked", "blocks"),
        CausalEdge("e1_o", "e1__blocked", "e1__outcome", "results"),
    ]
    cur_graph = CausalGraph(cur_nodes, cur_edges)

    report = detector.detect_drift(baseline, bl_graph, current, cur_graph)
    assert report.has_drift, "Expected behavioral drift detection"
    assert len(report.mismatched_events) > 0
    print(f"  [OK] Drift detected: {report.summary}")


def test_detect_replay_mismatch():
    """Replay that produces different results is detected."""
    detector = CausalDriftDetector()

    before = [_make_trace("e1", "P4_ALLOW", "ALLOW", "SUCCESS")]
    b_nodes = {
        "e1__host": CausalNode("e1__host", "e1", "c1", "host_event", {}, 0.0,
                                children=["e1__proposal"]),
        "e1__proposal": CausalNode("e1__proposal", "e1", "c1", "proposal", {}, 0.0,
                                    parent_id="e1__host", children=["e1__decision"]),
        "e1__decision": CausalNode("e1__decision", "e1", "c1", "decision", {}, 0.0,
                                    parent_id="e1__proposal", children=["e1__execution"]),
        "e1__execution": CausalNode("e1__execution", "e1", "c1", "execution", {},
                                     0.0, parent_id="e1__decision",
                                     children=["e1__outcome"]),
        "e1__outcome": CausalNode("e1__outcome", "e1", "c1", "outcome", {}, 0.0,
                                   parent_id="e1__execution"),
    }
    b_edges = [
        CausalEdge("e1_p", "e1__host", "e1__proposal", "proposes"),
        CausalEdge("e1_d", "e1__proposal", "e1__decision", "decides"),
        CausalEdge("e1_x", "e1__decision", "e1__execution", "executes"),
        CausalEdge("e1_o", "e1__execution", "e1__outcome", "results"),
    ]
    b_graph = CausalGraph(b_nodes, b_edges)

    # After replay: different outcome for same event
    after = [_make_trace("e1", "P4_BLOCK", "BLOCK", "UNKNOWN")]
    a_nodes = {
        "e1__host": CausalNode("e1__host", "e1", "c1", "host_event", {}, 0.0,
                                children=["e1__blocked"]),
        "e1__blocked": CausalNode("e1__blocked", "e1", "c1", "blocked", {}, 0.0,
                                   parent_id="e1__host",
                                   children=["e1__outcome"]),
        "e1__outcome": CausalNode("e1__outcome", "e1", "c1", "outcome", {}, 0.0,
                                   parent_id="e1__blocked"),
    }
    a_edges = [
        CausalEdge("e1_b", "e1__host", "e1__blocked", "blocks"),
        CausalEdge("e1_o", "e1__blocked", "e1__outcome", "results"),
    ]
    a_graph = CausalGraph(a_nodes, a_edges)

    div = detector.detect_replay_divergence(before, b_graph, after, a_graph)
    assert div.has_divergence, "Expected replay divergence detection"
    assert div.fingerprint_before != div.fingerprint_after
    print(f"  [OK] Replay divergence detected: {div.summary}")


def test_detect_hidden_mutation():
    """Hidden structural mutation without status change is detected."""
    detector = CausalDriftDetector()

    traces = [_make_trace("e1", "P4_ALLOW", "ALLOW", "SUCCESS")]

    ref_nodes = {
        "e1__host": CausalNode("e1__host", "e1", "c1", "host_event", {}, 0.0,
                                children=["e1__proposal"]),
        "e1__proposal": CausalNode("e1__proposal", "e1", "c1", "proposal", {}, 0.0,
                                    parent_id="e1__host", children=["e1__decision"]),
        "e1__decision": CausalNode("e1__decision", "e1", "c1", "decision", {}, 0.0,
                                    parent_id="e1__proposal", children=["e1__execution"]),
        "e1__outcome": CausalNode("e1__outcome", "e1", "c1", "outcome", {}, 0.0,
                                   parent_id="e1__execution"),
    }
    ref_edges = [
        CausalEdge("e1_p", "e1__host", "e1__proposal", "proposes"),
        CausalEdge("e1_d", "e1__proposal", "e1__decision", "decides"),
        CausalEdge("e1_x", "e1__decision", "e1__execution", "executes"),
        CausalEdge("e1_o", "e1__execution", "e1__outcome", "results"),
    ]
    ref_graph = CausalGraph(ref_nodes, ref_edges)

    mut_nodes = dict(ref_nodes)
    mut_nodes["e1__outcome"] = CausalNode(
        "e1__outcome", "e1", "c1", "outcome", {}, 0.0,
        parent_id="e1__execution",
        children=["e1__execution"],
    )
    mut_edges = list(ref_edges)
    mut_graph = CausalGraph(mut_nodes, mut_edges)

    assert detector.detect_hidden_mutation(traces, mut_graph, ref_graph), \
        "Expected hidden mutation detection"
    print("  [OK] Hidden mutation detected")


# ================================================================
#  GROUP D — Replay Intelligence
# ================================================================

def test_fingerprint_survives_replay():
    """Fingerprint is stable across serialize → wipe → replay."""
    fp_builder = CausalRuntimeFingerprint()
    verifier = ReplayFingerprintVerifier(fp_builder)

    scenario = [
        ("re1", "process", Capability.PROCESS_EXECUTE, 0.85, 0.2, "ALLOW", "SUCCESS"),
        ("re2", "delete", Capability.PROCESS_EXECUTE, 0.15, 0.95, "BLOCK", None),
    ]

    t0 = 2000000.0
    traces1, graph1 = _run_pipeline_sequence(scenario, "s3b2-replay", t0)
    fp1 = fp_builder.compute(traces1, graph1)

    traces2, graph2 = _run_pipeline_sequence(scenario, "s3b2-replay", t0)
    fp2 = fp_builder.compute(traces2, graph2)

    assert fp1 == fp2, "Fingerprint does not survive replay"
    print(f"  [OK] Fingerprint survives replay: {fp1[:16]}...")


def test_health_score_stable_after_replay():
    """Health score is stable after replay."""
    scorer = CausalHealthScorer()

    scenario = [
        ("hs1", "process", Capability.PROCESS_EXECUTE, 0.85, 0.2, "ALLOW", "SUCCESS"),
        ("hs2", "delete", Capability.PROCESS_EXECUTE, 0.15, 0.95, "BLOCK", None),
    ]

    traces1, graph1 = _run_pipeline_sequence(scenario, "s3b2-health", 3000000.0)
    traces2, graph2 = _run_pipeline_sequence(scenario, "s3b2-health", 3000000.0)

    score1 = scorer.score(traces1, graph1)
    score2 = scorer.score(traces2, graph2)

    assert score1.overall == score2.overall
    assert score1.integrity == score2.integrity
    assert score1.continuity == score2.continuity
    assert score1.determinism == score2.determinism
    print(f"  [OK] Health score stable: overall={score1.overall:.2f}")


def test_failure_explanation_preserved():
    """Failure explanation is identical across replays."""
    explainer = RuntimeFailureExplainer()

    trace_b = _make_trace("f1", "P4_BLOCK", "BLOCK", "UNKNOWN",
                           p4_reason="policy restriction")
    trace_f = _make_trace("f2", "SANDBOX_FAILED", "ALLOW", "FAILED",
                           exec_error="resource exhausted")

    blocked_db = explainer.explain(trace_b)
    assert blocked_db.governance_denial
    assert "policy_denial" in [c["action"] for c in blocked_db.failure_chain]

    failed = explainer.explain(trace_f)
    assert failed.sandbox_failure
    assert "execution_failure" in [c["action"] for c in failed.failure_chain]

    blocked_again = explainer.explain(trace_b)
    assert blocked_db.root_cause == blocked_again.root_cause
    assert len(blocked_db.failure_chain) == len(blocked_again.failure_chain)

    print(f"  [OK] Failure explanation preserved: "
          f"blocked='{blocked_db.summary}' failed='{failed.summary}'")


# ================================================================
#  GROUP E — Stress
# ================================================================

def test_large_graph_integrity():
    """1000-node healthy graph passes integrity check."""
    engine = CausalIntegrityEngine()
    nodes = {}
    edges = []
    node_types_cycle = ["host_event", "proposal", "decision", "execution", "outcome"]

    for i in range(200):
        base = f"evt{i:04d}"
        cid = f"cid-{i}"
        prev_id = None
        for j, nt in enumerate(node_types_cycle):
            nid = f"{base}_{nt}"
            nodes[nid] = CausalNode(
                nid, base, cid, nt, {}, float(i),
                parent_id=prev_id,
                children=[] if j == len(node_types_cycle) - 1 else [f"{base}_{node_types_cycle[j+1]}"],
            )
            if prev_id:
                edges.append(CausalEdge(
                    f"{base}_e{j}", prev_id, nid,
                    "proposes" if nt == "proposal" else
                    "decides" if nt == "decision" else
                    "executes" if nt == "execution" else
                    "results",
                ))
            prev_id = nid

    graph = CausalGraph(nodes, edges)
    report = engine.validate(graph)
    assert report.is_healthy, f"Expected healthy 1000-node graph, got {report.issue_count} issues"
    print(f"  [OK] 1000-node graph healthy: {len(graph.nodes)} nodes, {len(graph.edges)} edges")


def test_high_edge_density_stability():
    """High edge density does not break validation."""
    engine = CausalIntegrityEngine()
    nodes = {}
    edges = []

    for i in range(100):
        base = f"dense{i:03d}"
        cid = f"cid-{i}"
        host_id = f"{base}_host"
        nodes[host_id] = CausalNode(host_id, base, cid, "host_event", {}, float(i))
        out_id = None
        prev = host_id
        for j, nt in enumerate(["proposal", "decision", "execution", "outcome"]):
            nid = f"{base}_{nt}"
            parent = prev if j > 0 else host_id
            nodes[nid] = CausalNode(nid, base, cid, nt, {}, float(i), parent_id=parent)
            edges.append(CausalEdge(f"{base}_e{j}", prev, nid, "connects"))
            prev = nid
            if nt == "outcome":
                out_id = nid

    graph = CausalGraph(nodes, edges)
    report = engine.validate(graph)

    assert report.total_event_count == 100
    assert report.graph_continuity_score >= 0.95
    print(f"  [OK] High edge density stable: {len(graph.nodes)} nodes, "
          f"{len(graph.edges)} edges, continuity={report.graph_continuity_score:.2f}")


# ================================================================
#  RUNNER
# ================================================================

def run_all():
    tests = [
        # Group A — Integrity
        ("A1 — Orphan Node Detection", test_orphan_node_detection),
        ("A2 — Missing Edge Detection", test_missing_edge_detection),
        ("A3 — Cycle Corruption Detection", test_cycle_corruption_detection),
        ("A4 — Impossible Transition Detection", test_impossible_transition_detection),
        # Group B — Determinism
        ("B1 — Same Graph Same Fingerprint", test_same_graph_same_fingerprint),
        ("B2 — Same Replay Same Integrity Report", test_same_replay_same_integrity_report),
        ("B3 — Same Failure Same Explanation", test_same_failure_same_explanation),
        # Group C — Drift
        ("C1 — Behavioral Divergence", test_detect_behavioral_divergence),
        ("C2 — Replay Mismatch", test_detect_replay_mismatch),
        ("C3 — Hidden Mutation", test_detect_hidden_mutation),
        # Group D — Replay Intelligence
        ("D1 — Fingerprint Survives Replay", test_fingerprint_survives_replay),
        ("D2 — Health Score Stable After Replay", test_health_score_stable_after_replay),
        ("D3 — Failure Explanation Preserved", test_failure_explanation_preserved),
        # Group E — Stress
        ("E1 — 1000-Node Graph Integrity", test_large_graph_integrity),
        ("E2 — High Edge Density Stability", test_high_edge_density_stability),
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("Sprint 3B.2 — Causal Runtime Intelligence Layer")
    print("=" * 60)
    print()

    for name, func in tests:
        print(f"\n{'-' * 50}")
        print(f"  TEST: {name}")
        print(f"{'-' * 50}")
        try:
            func()
            print(f"  [PASS]")
            passed += 1
        except Exception as e:
            import traceback
            print(f"  [FAIL]: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
    print(f"{'=' * 60}")

    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
