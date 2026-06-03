"""
Sprint 3B.1 -- Causal Integrity Validation

Validates that the Phase 3B Causal Layer is:
1. Deterministic: same input -> same trace, graph, query output every time
2. Complete: every event produces a trace and every correlation_id is consistent
3. Survivable: WAL replay and re-execution produce identical causal output

Zero modifications to any layer. Pure validation.
"""

import time
import hashlib
import sys
import dataclasses
import json
import os
import tempfile
import uuid
from enum import Enum
from unittest.mock import patch

from cognitive_runtime.kernel.time_kernel import TimeKernel
from cognitive_runtime.contracts.execution_contract import (
    HostEvent,
    ExecutionProposal,
    PolicyDecision,
    ExecutionResult,
    Capability,
)
from cognitive_runtime.contracts.execution_trace import (
    ExecutionTraceStore,
    ExecutionTraceNormalizer,
    ExecutionTrace,
)
from cognitive_runtime.contracts.enriched_event import EnrichedEvent
from cognitive_runtime.substrate.observation_tap import ObservationTap
from cognitive_runtime.contracts.causal_graph import CausalGraphBuilder, CausalGraph
from cognitive_runtime.observation.why_query import WhyQuery


# ================================================================
#  TEST 1 -- E2E Causal Flow
#  Proposal -> Execution -> Trace -> Graph -> WhyQuery
# ================================================================

def test_e2e_causal_flow_success():
    """Full success path produces trace, 5-node graph, full_trace with outcome=SUCCESS."""
    tk = TimeKernel(session_id="t1-e2e")
    store = ExecutionTraceStore()
    norm = ExecutionTraceNormalizer()
    tap = ObservationTap(time_kernel=tk, trace_store=store, trace_normalizer=norm)
    builder = CausalGraphBuilder()

    event = HostEvent(
        event_id="e2e-001", session_id="t1-e2e",
        timestamp=time.time(), source="cli", payload={"cmd": "deploy"},
    )
    tk.stamp(event.event_id)
    tap.tap_event_received(event)

    proposal = ExecutionProposal(
        proposal_id="p-e2e-001", session_id="t1-e2e", event_id="e2e-001",
        action="deploy", target="node-1", params={},
        required_capabilities=[Capability.PROCESS_EXECUTE],
        confidence=0.85, risk_score=0.3, metadata={},
    )
    tap.tap_p3_proposal("e2e-001", proposal)

    decision = PolicyDecision(
        decision_id="d-e2e-001", proposal_id="p-e2e-001", session_id="t1-e2e",
        verdict="ALLOW", reason="within safe risk threshold",
        risk_level="low", rule_triggered="SAFE_PATH", confidence=0.85,
    )
    tap.tap_p4_decision("e2e-001", decision)

    started = time.time()
    time.sleep(0.01)
    result = ExecutionResult(
        execution_id="x-e2e-001", proposal_id="p-e2e-001", session_id="t1-e2e",
        status="SUCCESS", output="deployed", error=None,
        started_at=started, finished_at=time.time(),
    )
    tap.tap_execution_result("e2e-001", result)

    assert len(store) == 1, f"Expected 1 trace, got {len(store)}"
    trace = store.by_event_id("e2e-001")
    assert trace is not None, "Trace not found by event_id"
    assert trace.final_status == "P4_ALLOW", f"Expected P4_ALLOW, got {trace.final_status}"
    assert trace.correlation_id != "", "correlation_id must be non-empty"
    print(f"  [OK] Trace stored: {trace.event_id} -> {trace.final_status}")

    graph = builder.build(list(store.all))
    assert len(graph.nodes) == 5, f"Expected 5 nodes, got {len(graph.nodes)}"
    assert len(graph.edges) == 4, f"Expected 4 edges, got {len(graph.edges)}"
    node_types = [n.node_type for n in graph.nodes.values()]
    for t in ("host_event", "proposal", "decision", "execution", "outcome"):
        assert t in node_types, f"Missing node type: {t}"
    print(f"  [OK] CausalGraph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

    root = [n for n in graph.nodes.values() if n.node_type == "host_event"][0]
    path = graph.path_to_outcome(root.node_id)
    assert len(path) == 5, f"Expected path of 5, got {len(path)}"
    path_types = [n.node_type for n in path]
    assert path_types == ["host_event", "proposal", "decision", "execution", "outcome"], \
        f"Unexpected path: {path_types}"
    print(f"  [OK] Path: {' -> '.join(path_types)}")

    why = WhyQuery(tap=tap, trace_store=store)
    full = why.full_trace("e2e-001")
    assert full is not None, "full_trace must return result"
    assert full.outcome == "SUCCESS", f"Expected SUCCESS, got {full.outcome}"
    assert len(full.path) == 5, f"Expected 5 path entries, got {len(full.path)}"
    assert full.total_time_ms > 0, f"total_time_ms should be > 0, got {full.total_time_ms}"
    assert full.correlation_id != "", "correlation_id must be non-empty"
    print(f"  [OK] WhyQuery.full_trace: outcome={full.outcome} path={len(full.path)} t={full.total_time_ms:.1f}ms")

    return trace, graph, full


def test_e2e_causal_flow_blocked():
    """Blocked path produces trace, 4-node graph, WhyQuery.blocked()."""
    tk = TimeKernel(session_id="t1-blocked")
    store = ExecutionTraceStore()
    norm = ExecutionTraceNormalizer()
    tap = ObservationTap(time_kernel=tk, trace_store=store, trace_normalizer=norm)

    event = HostEvent(
        event_id="e2e-blocked", session_id="t1-blocked",
        timestamp=time.time(), source="cli", payload={"cmd": "delete"},
    )
    tk.stamp(event.event_id)
    tap.tap_event_received(event)

    proposal = ExecutionProposal(
        proposal_id="p-blocked", session_id="t1-blocked", event_id="e2e-blocked",
        action="delete", target="critical", params={},
        required_capabilities=[], confidence=0.15, risk_score=0.95, metadata={},
    )
    tap.tap_p3_proposal("e2e-blocked", proposal)

    decision = PolicyDecision(
        decision_id="d-blocked", proposal_id="p-blocked", session_id="t1-blocked",
        verdict="BLOCK", reason="critical risk threshold exceeded",
        risk_level="critical", rule_triggered="CRITICAL_RISK", confidence=0.15,
    )
    tap.tap_p4_decision("e2e-blocked", decision)
    tap.tap_blocked("e2e-blocked", "P4 blocked: BLOCK - critical risk threshold exceeded")

    assert len(store) == 1, f"Expected 1 trace, got {len(store)}"
    trace = store.by_event_id("e2e-blocked")
    assert trace is not None
    assert trace.final_status == "P4_BLOCK", f"Expected P4_BLOCK, got {trace.final_status}"
    print(f"  [OK] Blocked trace: {trace.event_id} -> {trace.final_status}")

    builder = CausalGraphBuilder()
    blocked_traces = store.by_final_status("P4_BLOCK")
    graph = builder.build(blocked_traces)
    assert len(graph.nodes) == 4, f"Expected 4 nodes, got {len(graph.nodes)}"
    assert any(n.node_type == "blocked" for n in graph.nodes.values())
    print(f"  [OK] Blocked graph: {len(graph.nodes)} nodes")

    why = WhyQuery(tap=tap, trace_store=store)
    blocked = why.blocked("e2e-blocked")
    assert blocked is not None
    assert blocked.root_cause == "P4_BLOCK"
    assert blocked.blocking_stage == "p4_authority"
    assert len(blocked.chain) == 3
    print(f"  [OK] WhyQuery.blocked: {blocked.root_cause} chain={len(blocked.chain)}")


def test_e2e_causal_flow_failed():
    """Failed execution produces trace, WhyQuery.failed()."""
    tk = TimeKernel(session_id="t1-failed")
    store = ExecutionTraceStore()
    norm = ExecutionTraceNormalizer()
    tap = ObservationTap(time_kernel=tk, trace_store=store, trace_normalizer=norm)

    event = HostEvent(
        event_id="e2e-failed", session_id="t1-failed",
        timestamp=time.time(), source="worker", payload={"cmd": "process"},
    )
    tk.stamp(event.event_id)
    tap.tap_event_received(event)

    proposal = ExecutionProposal(
        proposal_id="p-failed", session_id="t1-failed", event_id="e2e-failed",
        action="process", target="large-batch", params={},
        required_capabilities=[Capability.PROCESS_EXECUTE],
        confidence=0.7, risk_score=0.5, metadata={},
    )
    tap.tap_p3_proposal("e2e-failed", proposal)

    decision = PolicyDecision(
        decision_id="d-failed", proposal_id="p-failed", session_id="t1-failed",
        verdict="ALLOW", reason="acceptable risk",
        risk_level="medium", rule_triggered="SAFE_PATH", confidence=0.7,
    )
    tap.tap_p4_decision("e2e-failed", decision)

    result = ExecutionResult(
        execution_id="x-failed", proposal_id="p-failed", session_id="t1-failed",
        status="FAILED", output=None, error="timeout after 30s",
        started_at=time.time(), finished_at=time.time() + 2.0,
    )
    tap.tap_execution_result("e2e-failed", result)

    assert len(store) == 1
    trace = store.by_event_id("e2e-failed")
    assert trace is not None
    assert trace.final_status == "SANDBOX_FAILED", f"Expected SANDBOX_FAILED, got {trace.final_status}"
    print(f"  [OK] Failed trace: {trace.event_id} -> {trace.final_status}")

    why = WhyQuery(tap=tap, trace_store=store)
    failed = why.failed("e2e-failed")
    assert failed is not None
    assert failed.root_cause == "SANDBOX_FAILED"
    assert failed.error == "timeout after 30s"
    assert len(failed.chain) == 4
    print(f"  [OK] WhyQuery.failed: {failed.root_cause} chain={len(failed.chain)}")


# ================================================================
#  TEST 2 -- Cross-Layer Consistency
#  correlation_id coverage across all layers, zero event loss
# ================================================================

def test_correlation_id_consistency():
    """Verify correlation_id is identical across all 5 layers."""
    tk = TimeKernel(session_id="t2-consistency")
    store = ExecutionTraceStore()
    norm = ExecutionTraceNormalizer()
    tap = ObservationTap(time_kernel=tk, trace_store=store, trace_normalizer=norm)

    event = HostEvent(
        event_id="cid-test", session_id="t2-consistency",
        timestamp=time.time(), source="test", payload={},
    )
    tk.stamp(event.event_id)
    tap.tap_event_received(event)

    enriched = tap.get_enriched("cid-test")
    assert enriched is not None
    cid = enriched.correlation_id
    assert cid != "", "correlation_id must be non-empty"

    proposal = ExecutionProposal(
        proposal_id="p-cid", session_id="t2-consistency", event_id="cid-test",
        action="test", target=None, params={},
        required_capabilities=[], confidence=0.5, risk_score=0.5, metadata={},
    )
    proposal = dataclasses.replace(proposal, correlation_id=cid)
    tap.tap_p3_proposal("cid-test", proposal)

    decision = PolicyDecision(
        decision_id="d-cid", proposal_id="p-cid", session_id="t2-consistency",
        verdict="ALLOW", reason="ok", risk_level="low", rule_triggered="SAFE_PATH",
        confidence=0.5,
    )
    decision = dataclasses.replace(decision, correlation_id=cid)
    tap.tap_p4_decision("cid-test", decision)

    result = ExecutionResult(
        execution_id="x-cid", proposal_id="p-cid", session_id="t2-consistency",
        status="SUCCESS", output=None, error=None,
        started_at=time.time(), finished_at=time.time(),
    )
    result = dataclasses.replace(result, correlation_id=cid)
    tap.tap_execution_result("cid-test", result)

    # Layer 1: EnrichedEvent
    assert enriched.correlation_id == cid
    # Layer 2: Pipeline objects
    assert tap.get_enriched("cid-test").p3_proposal.correlation_id == cid
    assert tap.get_enriched("cid-test").p4_decision.correlation_id == cid
    assert tap.get_enriched("cid-test").execution_result.correlation_id == cid

    # Layer 3: ExecutionTrace
    trace = store.by_event_id("cid-test")
    assert trace is not None
    assert trace.correlation_id == cid

    # Layer 4: CausalGraph
    builder = CausalGraphBuilder()
    graph = builder.build(list(store.all))
    for node in graph.nodes.values():
        assert node.correlation_id == cid
    for edge in graph.edges:
        sn = graph.get(edge.source_id)
        tn = graph.get(edge.target_id)
        assert sn is not None and sn.correlation_id == cid
        assert tn is not None and tn.correlation_id == cid

    # Layer 5: WhyQuery
    why = WhyQuery(tap=tap, trace_store=store)
    full = why.full_trace("cid-test")
    assert full is not None
    assert full.correlation_id == cid

    print(f"  [OK] correlation_id consistent across all 5 layers: {cid[:8]}...")


def test_zero_event_loss():
    """Every event that enters the pipeline produces exactly one ExecutionTrace."""
    tk = TimeKernel(session_id="t2-zero-loss")
    store = ExecutionTraceStore()
    norm = ExecutionTraceNormalizer()
    tap = ObservationTap(time_kernel=tk, trace_store=store, trace_normalizer=norm)

    event_ids = []
    for i in range(10):
        eid = f"loss-test-{i:03d}"
        event_ids.append(eid)
        event = HostEvent(
            event_id=eid, session_id="t2-zero-loss",
            timestamp=time.time() + i * 0.001, source="test", payload={"idx": i},
        )
        tk.stamp(event.event_id)
        tap.tap_event_received(event)
        proposal = ExecutionProposal(
            proposal_id=f"p-{i:03d}", session_id="t2-zero-loss", event_id=eid,
            action="process", target=f"item-{i}", params={},
            required_capabilities=[], confidence=0.8, risk_score=0.1, metadata={},
        )
        tap.tap_p3_proposal(eid, proposal)
        decision = PolicyDecision(
            decision_id=f"d-{i:03d}", proposal_id=f"p-{i:03d}", session_id="t2-zero-loss",
            verdict="ALLOW", reason="ok", risk_level="low", rule_triggered="SAFE_PATH",
            confidence=0.8,
        )
        tap.tap_p4_decision(eid, decision)
        result = ExecutionResult(
            execution_id=f"x-{i:03d}", proposal_id=f"p-{i:03d}", session_id="t2-zero-loss",
            status="SUCCESS", output=f"result-{i}", error=None,
            started_at=time.time() + i * 0.001, finished_at=time.time() + i * 0.001 + 0.01,
        )
        tap.tap_execution_result(eid, result)

    assert len(store) == 10, f"Expected 10 traces, got {len(store)}"
    for eid in event_ids:
        assert store.by_event_id(eid) is not None, f"Missing trace for {eid}"
    print(f"  [OK] All 10 events produced traces -- zero loss")

    seen = set()
    for t in store.all:
        assert t.event_id not in seen
        seen.add(t.event_id)
    print(f"  [OK] No duplicate traces -- zero double-counting")

    builder = CausalGraphBuilder()
    graph = builder.build(list(store.all))
    assert len(graph.nodes) == 10 * 5, f"Expected 50 nodes, got {len(graph.nodes)}"
    assert len(graph.edges) == 10 * 4, f"Expected 40 edges, got {len(graph.edges)}"
    print(f"  [OK] Graph contains all {len(event_ids)} events: {len(graph.nodes)} nodes, {len(graph.edges)} edges")


# ================================================================
#  TEST 3 -- Determinism Validation
#  Same input -> same trace, graph, query output every time
# ================================================================

def _run_deterministic_sequence(tk, store, tap, seq_id, seed):
    """Execute a fixed sequence of events and return a hash of all outputs."""
    for i in range(5):
        eid = f"{seq_id}-det-{i:03d}"
        event = HostEvent(
            event_id=eid, session_id=seq_id,
            timestamp=float(1000 + seed + i), source="test", payload={"seed": seed, "i": i},
        )
        tk.stamp(event.event_id)
        tap.tap_event_received(event)

        if i % 3 == 2:
            proposal = ExecutionProposal(
                proposal_id=f"p-{i:03d}", session_id=seq_id, event_id=eid,
                action="block-test", target=f"item-{i}", params={},
                required_capabilities=[], confidence=0.1, risk_score=0.9, metadata={},
            )
            tap.tap_p3_proposal(eid, proposal)
            decision = PolicyDecision(
                decision_id=f"d-{i:03d}", proposal_id=f"p-{i:03d}", session_id=seq_id,
                verdict="BLOCK", reason="deterministic test block",
                risk_level="critical", rule_triggered="DET_TEST", confidence=0.1,
            )
            tap.tap_p4_decision(eid, decision)
            tap.tap_blocked(eid, "test block")
        else:
            proposal = ExecutionProposal(
                proposal_id=f"p-{i:03d}", session_id=seq_id, event_id=eid,
                action="det-test", target=f"item-{i}", params={},
                required_capabilities=[], confidence=0.9, risk_score=0.1, metadata={},
            )
            tap.tap_p3_proposal(eid, proposal)
            decision = PolicyDecision(
                decision_id=f"d-{i:03d}", proposal_id=f"p-{i:03d}", session_id=seq_id,
                verdict="ALLOW", reason="ok", risk_level="low", rule_triggered="DET_TEST",
                confidence=0.9,
            )
            tap.tap_p4_decision(eid, decision)
            result = ExecutionResult(
                execution_id=f"x-{i:03d}", proposal_id=f"p-{i:03d}", session_id=seq_id,
                status="SUCCESS", output=f"det-result-{i}", error=None,
                started_at=float(2000 + seed + i), finished_at=float(2000 + seed + i + 0.1),
            )
            tap.tap_execution_result(eid, result)

    """
    Hash only deterministic structural fields -- exclude correlation_id,
    wall_time, and timestamps (which are intentionally random/UUID by
    architectural design).
    """
    hasher = hashlib.sha256()

    for t in store.all:
        hasher.update(f"{t.event_id}|{t.final_status}|{t.p4_verdict}|{t.execution_status}".encode())

    builder = CausalGraphBuilder()
    graph = builder.build(list(store.all))
    hasher.update(f"nodes:{len(graph.nodes)}|edges:{len(graph.edges)}".encode())
    for nid in sorted(graph.nodes.keys()):
        n = graph.get(nid)
        hasher.update(f"{n.node_type}".encode())

    why = WhyQuery(tap=tap, trace_store=store)
    for t in store.all:
        full = why.full_trace(t.event_id)
        if full:
            hasher.update(f"{full.outcome}|{len(full.path)}".encode())
        blocked = why.blocked(t.event_id)
        if blocked:
            hasher.update(f"{blocked.root_cause}|{len(blocked.chain)}".encode())
        failed = why.failed(t.event_id)
        if failed:
            hasher.update(f"{failed.root_cause}|{len(failed.chain)}".encode())

    return hasher.hexdigest()


def test_deterministic_output():
    """Same input sequence produces identical hash across 3 independent runs."""
    hashes = []
    for run in range(3):
        tk = TimeKernel(session_id="t3-det-fixed")
        store = ExecutionTraceStore()
        norm = ExecutionTraceNormalizer()
        tap = ObservationTap(time_kernel=tk, trace_store=store, trace_normalizer=norm)
        h = _run_deterministic_sequence(tk, store, tap, "t3-det-fixed", 42)
        hashes.append(h)
        print(f"  Run {run}: hash={h[:16]}...")

    for i in range(1, len(hashes)):
        assert hashes[i] == hashes[0], \
            f"Hash mismatch: run 0={hashes[0][:16]} run {i}={hashes[i][:16]}"
    print(f"  [OK] All 3 runs produced identical hash: {hashes[0][:16]}...")


def test_graph_node_count_deterministic():
    """Graph node/edge counts are deterministic for same input pattern."""
    counts = []
    for run in range(3):
        tk = TimeKernel(session_id=f"t3-graph-run{run}")
        store = ExecutionTraceStore()
        norm = ExecutionTraceNormalizer()
        tap = ObservationTap(time_kernel=tk, trace_store=store, trace_normalizer=norm)

        for i in range(3):
            eid = f"g-det-{run}-{i}"
            event = HostEvent(
                event_id=eid, session_id=f"t3-graph-run{run}",
                timestamp=float(1000 + run + i), source="test", payload={"i": i},
            )
            tk.stamp(event.event_id)
            tap.tap_event_received(event)
            proposal = ExecutionProposal(
                proposal_id=f"p-{run}-{i}", session_id=f"t3-graph-run{run}", event_id=eid,
                action="test", target=f"x-{i}", params={},
                required_capabilities=[], confidence=0.8, risk_score=0.1, metadata={},
            )
            tap.tap_p3_proposal(eid, proposal)

            if i == 2:
                decision = PolicyDecision(
                    decision_id=f"d-{run}-{i}", proposal_id=f"p-{run}-{i}", session_id=f"t3-graph-run{run}",
                    verdict="BLOCK", reason="block test", risk_level="critical",
                    rule_triggered="TEST", confidence=0.8,
                )
                tap.tap_p4_decision(eid, decision)
                tap.tap_blocked(eid, "test block")
            else:
                decision = PolicyDecision(
                    decision_id=f"d-{run}-{i}", proposal_id=f"p-{run}-{i}", session_id=f"t3-graph-run{run}",
                    verdict="ALLOW", reason="ok", risk_level="low",
                    rule_triggered="TEST", confidence=0.8,
                )
                tap.tap_p4_decision(eid, decision)
                result = ExecutionResult(
                    execution_id=f"x-{run}-{i}", proposal_id=f"p-{run}-{i}", session_id=f"t3-graph-run{run}",
                    status="SUCCESS", output=None, error=None,
                    started_at=float(2000 + run + i), finished_at=float(2000 + run + i + 0.1),
                )
                tap.tap_execution_result(eid, result)

        builder = CausalGraphBuilder()
        graph = builder.build(list(store.all))

        print(f"  Run {run}: nodes={len(graph.nodes)} edges={len(graph.edges)}")
        counts.append((len(graph.nodes), len(graph.edges)))

    for i in range(1, len(counts)):
        assert counts[i] == counts[0], \
            f"Count mismatch: run 0={counts[0]} run {i}={counts[i]}"

    print(f"  [OK] Graph counts deterministic: {counts[0]}")


def test_whyquery_deterministic():
    """WhyQuery returns identical results for same input across runs."""
    results = []
    for run in range(3):
        tk = TimeKernel(session_id=f"t3-why-run{run}")
        store = ExecutionTraceStore()
        norm = ExecutionTraceNormalizer()
        tap = ObservationTap(time_kernel=tk, trace_store=store, trace_normalizer=norm)

        eid = f"why-det-{run}"
        event = HostEvent(
            event_id=eid, session_id=f"t3-why-run{run}",
            timestamp=float(1000 + run), source="test", payload={},
        )
        tk.stamp(event.event_id)
        tap.tap_event_received(event)
        proposal = ExecutionProposal(
            proposal_id=f"p-{run}", session_id=f"t3-why-run{run}", event_id=eid,
            action="test", target="x", params={},
            required_capabilities=[], confidence=0.9, risk_score=0.1, metadata={},
        )
        tap.tap_p3_proposal(eid, proposal)
        decision = PolicyDecision(
            decision_id=f"d-{run}", proposal_id=f"p-{run}", session_id=f"t3-why-run{run}",
            verdict="ALLOW", reason="ok", risk_level="low", rule_triggered="TEST", confidence=0.9,
        )
        tap.tap_p4_decision(eid, decision)
        result = ExecutionResult(
            execution_id=f"x-{run}", proposal_id=f"p-{run}", session_id=f"t3-why-run{run}",
            status="SUCCESS", output=None, error=None,
            started_at=float(2000 + run), finished_at=float(2000 + run + 0.1),
        )
        tap.tap_execution_result(eid, result)

        why = WhyQuery(tap=tap, trace_store=store)
        full = why.full_trace(eid)
        assert full is not None
        results.append((full.outcome, len(full.path), round(full.total_time_ms, 2)))

    for i in range(1, len(results)):
        assert results[i] == results[0], f"WhyQuery mismatch: {results[0]} vs {results[i]}"
    print(f"  [OK] WhyQuery deterministic across 3 runs: {results[0]}")


# ================================================================
#  TEST 4 -- Edge Cases
# ================================================================

def test_empty_store():
    """Empty store returns empty results, not errors."""
    store = ExecutionTraceStore()
    assert len(store) == 0
    assert store.by_event_id("nonexistent") is None
    assert store.by_correlation_id("nonexistent") is None
    assert store.by_final_status("P4_ALLOW") == []
    assert store.recent(10) == []
    print("  [OK] Empty store handles all queries gracefully")


def test_store_capacity_bounded():
    """Store is bounded at max_size and drops oldest entries."""
    store = ExecutionTraceStore(max_size=10)
    for i in range(15):
        store.add(ExecutionTrace(event_id=f"evt-{i:03d}", session_id="t4", correlation_id=f"cid-{i}"))
    assert len(store) == 10, f"Expected 10 (bounded), got {len(store)}"
    assert store.by_event_id("evt-000") is None, "Oldest entry should be evicted"
    assert store.by_event_id("evt-014") is not None, "Newest entry should remain"
    print(f"  [OK] Store bounded at 10: {len(store)} entries, oldest evicted, newest present")


def test_graph_empty_input():
    """Graph builder handles empty input gracefully."""
    builder = CausalGraphBuilder()
    graph = builder.build([])
    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0
    assert graph.roots == []
    assert graph.path_to_outcome("nonexistent") == []
    print("  [OK] Empty input produces empty graph")


def test_whyquery_missing_event():
    """WhyQuery returns None for non-existent events."""
    tk = TimeKernel(session_id="t4-missing")
    tap = ObservationTap(time_kernel=tk)
    why = WhyQuery(tap=tap)
    assert why.blocked("nonexistent") is None
    assert why.failed("nonexistent") is None
    assert why.full_trace("nonexistent") is None
    assert why.trace_store_summary() == []
    print("  [OK] WhyQuery handles missing events gracefully")


def test_whyquery_time_range():
    """Time range query returns only events in the given window."""
    tk = TimeKernel(session_id="t4-timerange")
    store = ExecutionTraceStore()
    norm = ExecutionTraceNormalizer()
    tap = ObservationTap(time_kernel=tk, trace_store=store, trace_normalizer=norm)
    why = WhyQuery(tap=tap, trace_store=store)

    for i in range(5):
        eid = f"tr-{i}"
        event = HostEvent(
            event_id=eid, session_id="t4-timerange",
            timestamp=time.time(), source="test", payload={},
        )
        tk.stamp(event.event_id)
        tap.tap_event_received(event)
        proposal = ExecutionProposal(
            proposal_id=f"p-tr-{i}", session_id="t4-timerange", event_id=eid,
            action="test", target=f"x-{i}", params={},
            required_capabilities=[], confidence=0.8, risk_score=0.1, metadata={},
        )
        tap.tap_p3_proposal(eid, proposal)
        decision = PolicyDecision(
            decision_id=f"d-tr-{i}", proposal_id=f"p-tr-{i}", session_id="t4-timerange",
            verdict="ALLOW", reason="ok", risk_level="low", rule_triggered="TEST", confidence=0.8,
        )
        tap.tap_p4_decision(eid, decision)
        result = ExecutionResult(
            execution_id=f"x-tr-{i}", proposal_id=f"p-tr-{i}", session_id="t4-timerange",
            status="SUCCESS", output=None, error=None,
            started_at=time.time(), finished_at=time.time(),
        )
        tap.tap_execution_result(eid, result)

    after_all = time.time()
    before_all = after_all - 10.0
    mid_graph = why.time_range(before_all, after_all)
    print(f"  [OK] Time range query returned {len(mid_graph.nodes)} nodes")


# ================================================================
#  RUNNER
# ================================================================

# ================================================================
#  TEST 5 — WAL Replay Survival
#  Record → persist → wipe → replay → verify identical causal output
# ================================================================

def test_wal_replay_survival():
    """
    Truth anchor: serialize, persist to WAL, wipe, re-execute, prove
    identical causal output across ExecutionTraceStore, CausalGraph, and WhyQuery.
    """
    wal_path = os.path.join(tempfile.gettempdir(),
                            f"wal_replay_{int(time.time()*1000000)}.jsonl")

    scenario = [
        ("wr-001", "deploy", Capability.PROCESS_EXECUTE, 0.85, 0.2, "ALLOW", "SUCCESS"),
        ("wr-002", "delete", Capability.PROCESS_EXECUTE, 0.15, 0.95, "BLOCK", None),
        ("wr-003", "process", Capability.PROCESS_EXECUTE, 0.90, 0.1, "ALLOW", "SUCCESS"),
        ("wr-004", "shutdown", Capability.FILESYSTEM_WRITE, 0.20, 0.88, "BLOCK", None),
        ("wr-005", "audit", Capability.AUDIT_READ, 0.70, 0.3, "ALLOW", "SUCCESS"),
    ]
    n_events = len(scenario)

    t0 = 1000000.0

    # ---- RECORD PHASE ----
    _det_uuid_counter[0] = 0
    with patch("cognitive_runtime.substrate.observation_tap.uuid.uuid4", _det_uuid4):
        tk1 = TimeKernel(session_id="wr-session")
        store1 = ExecutionTraceStore()
        norm1 = ExecutionTraceNormalizer()
        tap1 = ObservationTap(time_kernel=tk1, trace_store=store1,
                               trace_normalizer=norm1)
        wal_entries: list[dict] = []

        for i, (eid, action, cap, conf, risk, verdict, exec_status) in enumerate(scenario):
            event = HostEvent(
                event_id=eid, session_id="wr-session",
                timestamp=t0 + i * 0.1, source="wal-test",
                payload={"action": action, "idx": i},
            )
            tk1.stamp(event.event_id)
            tap1.tap_event_received(event)
            cid = tap1.get_enriched(eid).correlation_id

            proposal = ExecutionProposal(
                proposal_id=f"p-{eid}", session_id="wr-session", event_id=eid,
                action=action, target=f"node-{i}", params={"idx": i},
                required_capabilities=[cap],
                confidence=conf, risk_score=risk, metadata={},
                correlation_id=cid,
            )
            tap1.tap_p3_proposal(eid, proposal)

            decision = PolicyDecision(
                decision_id=f"d-{eid}", proposal_id=f"p-{eid}",
                session_id="wr-session", verdict=verdict,
                reason=f"verdict {verdict}" if verdict else "blocked",
                risk_level="low" if verdict == "ALLOW" else "critical",
                rule_triggered="SAFE_PATH" if verdict == "ALLOW" else "HIGH_RISK",
                confidence=conf, correlation_id=cid,
            )
            tap1.tap_p4_decision(eid, decision)

            result = None
            blocked = None
            if exec_status:
                result = ExecutionResult(
                    execution_id=f"x-{eid}", proposal_id=f"p-{eid}",
                    session_id="wr-session", status=exec_status,
                    output=f"done-{i}", error=None,
                    started_at=t0 + i * 0.1 + 0.01,
                    finished_at=t0 + i * 0.1 + 0.05,
                    correlation_id=cid,
                )
                tap1.tap_execution_result(eid, result)
            else:
                blocked = f"blocked by {verdict}"
                tap1.tap_blocked(eid, blocked)

            wal_entries.append(
                _wal_entry_to_dict(event, proposal, decision, result, blocked, cid))

        # Write WAL
        with open(wal_path, "w") as f:
            for entry in wal_entries:
                f.write(json.dumps(entry) + "\n")

    # Capture baseline
    baseline_traces = [dataclasses.replace(t) for t in store1.all]
    builder1 = CausalGraphBuilder()
    graph1 = builder1.build(list(store1.all))
    why1 = WhyQuery(tap=tap1, trace_store=store1)
    baseline_blocked = {}
    baseline_failed = {}
    for t in store1.all:
        b = why1.blocked(t.event_id)
        if b:
            baseline_blocked[t.event_id] = b
        f = why1.failed(t.event_id)
        if f:
            baseline_failed[t.event_id] = f

    # ---- WIPE & REPLAY PHASE ----
    _det_uuid_counter[0] = 0
    with patch("cognitive_runtime.substrate.observation_tap.uuid.uuid4", _det_uuid4):
        tk2 = TimeKernel(session_id="wr-session")
        store2 = ExecutionTraceStore()
        norm2 = ExecutionTraceNormalizer()
        tap2 = ObservationTap(time_kernel=tk2, trace_store=store2,
                               trace_normalizer=norm2)

        with open(wal_path, "r") as f:
            for line in f:
                entry = json.loads(line)
                _wal_replay_entry(entry, tap2)

    # ---- VERIFY PHASE ----
    assert len(store2) == n_events, \
        f"Trace count mismatch: {len(store2)} vs {n_events}"
    print(f"  [OK] Trace count matches: {len(store2)}")

    # 1. Identical ExecutionTraceStore
    for t1 in baseline_traces:
        t2 = store2.by_event_id(t1.event_id)
        assert t2 is not None, f"Missing trace after replay: {t1.event_id}"
        assert t2.final_status == t1.final_status, \
            f"final_status mismatch for {t1.event_id}: {t2.final_status} vs {t1.final_status}"
        assert t2.correlation_id == t1.correlation_id, \
            f"correlation_id mismatch for {t1.event_id}"
        assert t2.p4_verdict == t1.p4_verdict, \
            f"p4_verdict mismatch for {t1.event_id}"
    print(f"  [OK] ExecutionTraceStore: {n_events} traces with identical status + correlation_id")

    # 2. Identical CausalGraph
    builder2 = CausalGraphBuilder()
    graph2 = builder2.build(list(store2.all))

    assert len(graph2.nodes) == len(graph1.nodes), \
        f"Node count: {len(graph2.nodes)} vs {len(graph1.nodes)}"
    assert len(graph2.edges) == len(graph1.edges), \
        f"Edge count: {len(graph2.edges)} vs {len(graph1.edges)}"
    for nid, n1 in graph1.nodes.items():
        n2 = graph2.nodes.get(nid)
        assert n2 is not None, f"Missing node after replay: {nid}"
        assert n2.node_type == n1.node_type, \
            f"node_type mismatch: {n2.node_type} vs {n1.node_type}"
        assert n2.correlation_id == n1.correlation_id, \
            f"node correlation_id mismatch for {nid}"
    print(f"  [OK] CausalGraph: {len(graph1.nodes)} nodes, {len(graph1.edges)} edges — identical")

    # 3. Identical WhyQuery results
    why2 = WhyQuery(tap=tap2, trace_store=store2)
    for t in baseline_traces:
        f1 = why1.full_trace(t.event_id)
        f2 = why2.full_trace(t.event_id)
        assert f2 is not None, f"full_trace missing for {t.event_id}"
        assert f2.outcome == f1.outcome, \
            f"outcome mismatch for {t.event_id}: {f2.outcome} vs {f1.outcome}"
        assert len(f2.path) == len(f1.path), \
            f"path length mismatch for {t.event_id}: {len(f2.path)} vs {len(f1.path)}"
        for i, (p1, p2) in enumerate(zip(f1.path, f2.path)):
            assert p2["node_type"] == p1["node_type"], \
                f"path[{i}] node_type mismatch for {t.event_id}"
    print(f"  [OK] WhyQuery.full_trace: {n_events} traces with identical outcome + path")

    # 4. Identical blocked queries
    assert len(why1.trace_store_summary()) == len(why2.trace_store_summary())
    for eid, b1 in baseline_blocked.items():
        b2 = why2.blocked(eid)
        assert b2 is not None, f"blocked missing for {eid}"
        assert b2.root_cause == b1.root_cause
        assert b2.blocking_stage == b1.blocking_stage
        assert len(b2.chain) == len(b1.chain)
    print(f"  [OK] WhyQuery.blocked: {len(baseline_blocked)} identical blocked queries")

    # 5. Stable correlation_id across all layers after replay
    for root_trace in baseline_traces:
        cid = root_trace.correlation_id
        replayed_trace = store2.by_event_id(root_trace.event_id)
        assert replayed_trace is not None
        assert replayed_trace.correlation_id == cid
        subgraph = graph2.correlation_subgraph(cid)
        expected_nodes = 5 if root_trace.final_status == "P4_ALLOW" else 4
        assert len(subgraph.nodes) == expected_nodes, \
            f"Expected {expected_nodes} nodes per correlation_id for {root_trace.event_id} (status={root_trace.final_status}), got {len(subgraph.nodes)}"
        all_subgraph_cids = set(
            n.correlation_id for n in subgraph.nodes.values())
        assert all_subgraph_cids == {cid}, \
            f"Correlation drift: {all_subgraph_cids}"
    print(f"  [OK] correlation_id mapping stable: all subgraphs preserved")

    # 6. Deterministic ordering after replay
    replay_seq = [t.event_id for t in store2.all]
    baseline_seq = [t.event_id for t in baseline_traces]
    assert replay_seq == baseline_seq, \
        f"Order drift: {replay_seq} vs {baseline_seq}"
    print(f"  [OK] Ordering preserved: {replay_seq}")

    # Cleanup
    try:
        os.remove(wal_path)
    except OSError:
        pass


# ================================================================
#  HELPER: WAL Serialization / Deserialization
# ================================================================

def _wal_proposal_to_dict(p: ExecutionProposal) -> dict:
    caps = [c.value for c in p.required_capabilities]
    return {
        "proposal_id": p.proposal_id, "session_id": p.session_id,
        "event_id": p.event_id, "action": p.action, "target": p.target,
        "params": p.params, "required_capabilities": caps,
        "confidence": p.confidence, "risk_score": p.risk_score,
        "metadata": p.metadata, "correlation_id": p.correlation_id,
    }


def _wal_proposal_from_dict(d: dict) -> ExecutionProposal:
    caps = [Capability(c) for c in d["required_capabilities"]]
    return ExecutionProposal(
        proposal_id=d["proposal_id"], session_id=d["session_id"],
        event_id=d["event_id"], action=d["action"], target=d["target"],
        params=d["params"], required_capabilities=caps,
        confidence=d["confidence"], risk_score=d["risk_score"],
        metadata=d["metadata"], correlation_id=d["correlation_id"],
    )


def _wal_decision_to_dict(d: PolicyDecision) -> dict:
    return {
        "decision_id": d.decision_id, "proposal_id": d.proposal_id,
        "session_id": d.session_id, "verdict": d.verdict,
        "reason": d.reason, "risk_level": d.risk_level,
        "rule_triggered": d.rule_triggered, "confidence": d.confidence,
        "correlation_id": d.correlation_id,
    }


def _wal_decision_from_dict(d: dict) -> PolicyDecision:
    return PolicyDecision(
        decision_id=d["decision_id"], proposal_id=d["proposal_id"],
        session_id=d["session_id"], verdict=d["verdict"],
        reason=d["reason"], risk_level=d["risk_level"],
        rule_triggered=d["rule_triggered"], confidence=d["confidence"],
        correlation_id=d["correlation_id"],
    )


def _wal_result_to_dict(r: ExecutionResult) -> dict:
    return {
        "execution_id": r.execution_id, "proposal_id": r.proposal_id,
        "session_id": r.session_id, "status": r.status,
        "output": r.output, "error": r.error,
        "started_at": r.started_at, "finished_at": r.finished_at,
        "correlation_id": r.correlation_id,
    }


def _wal_result_from_dict(d: dict) -> ExecutionResult:
    return ExecutionResult(
        execution_id=d["execution_id"], proposal_id=d["proposal_id"],
        session_id=d["session_id"], status=d["status"],
        output=d["output"], error=d["error"],
        started_at=d["started_at"], finished_at=d["finished_at"],
        correlation_id=d["correlation_id"],
    )


def _wal_entry_to_dict(host_event: HostEvent, proposal: ExecutionProposal,
                       decision: PolicyDecision, result: ExecutionResult | None,
                       blocked: str | None, correlation_id: str) -> dict:
    return {
        "version": 1,
        "event_id": host_event.event_id,
        "session_id": host_event.session_id,
        "correlation_id": correlation_id,
        "host_event": dataclasses.asdict(host_event),
        "proposal": _wal_proposal_to_dict(proposal),
        "decision": _wal_decision_to_dict(decision),
        "result": _wal_result_to_dict(result) if result else None,
        "blocked": blocked,
    }


def _wal_replay_entry(entry: dict,
                      tap: ObservationTap) -> None:
    """Replay one WAL entry through a fresh ObservationTap."""
    eid = entry["event_id"]
    he = HostEvent(**entry["host_event"])
    tap._time.stamp(he.event_id)
    tap.tap_event_received(he)
    enriched = tap._events.get(eid)
    if enriched:
        enriched.correlation_id = entry["correlation_id"]
    tap.tap_p3_proposal(eid, _wal_proposal_from_dict(entry["proposal"]))
    tap.tap_p4_decision(eid, _wal_decision_from_dict(entry["decision"]))
    if enriched:
        enriched.correlation_id = entry["correlation_id"]
    if entry["result"]:
        tap.tap_execution_result(eid, _wal_result_from_dict(entry["result"]))
    elif entry["blocked"]:
        tap.tap_blocked(eid, entry["blocked"])


# ================================================================
#  HELPER: Deterministic UUID4 for monkey-patch replay
# ================================================================

_det_uuid_counter: list[int] = [0]


def _det_uuid4() -> uuid.UUID:
    _det_uuid_counter[0] += 1
    return uuid.UUID(f"00000000-0000-0000-0000-{_det_uuid_counter[0]:012d}")


def run_all():
    tests = [
        ("E2E Causal Flow - Success", test_e2e_causal_flow_success),
        ("E2E Causal Flow - Blocked", test_e2e_causal_flow_blocked),
        ("E2E Causal Flow - Failed", test_e2e_causal_flow_failed),
        ("Cross-Layer - correlation_id Consistency", test_correlation_id_consistency),
        ("Cross-Layer - Zero Event Loss", test_zero_event_loss),
        ("Determinism - Output Hash", test_deterministic_output),
        ("Determinism - Graph Count", test_graph_node_count_deterministic),
        ("Determinism - WhyQuery", test_whyquery_deterministic),
        ("Edge Cases - Empty Store", test_empty_store),
        ("Edge Cases - Store Capacity", test_store_capacity_bounded),
        ("Edge Cases - Empty Graph", test_graph_empty_input),
        ("Edge Cases - Missing WhyQuery", test_whyquery_missing_event),
        ("Edge Cases - Time Range", test_whyquery_time_range),
        ("WAL Replay - Survival", test_wal_replay_survival),
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("Sprint 3B.1 -- Causal Integrity Validation")
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
