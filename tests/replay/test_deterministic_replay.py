"""Deterministic replay guarantees -- same traces produce identical graphs and fingerprints."""

from cognitive_runtime.contracts.causal_graph import CausalGraphBuilder
from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.contracts.frozen.schema_version import fingerprint
from cognitive_runtime.recovery.replay_validator import ReplayValidator
from cognitive_runtime.recovery.runtime_snapshot import RuntimeSnapshot
from cognitive_runtime.contracts.frozen.schema_version import FROZEN_SCHEMA_VERSION


def make_trace(event_id, correlation_id, p4_verdict="ALLOW", execution_status="SUCCESS",
               final_status="P4_ALLOW", execution_error=None):
    return ExecutionTrace(
        event_id=event_id, session_id="s1", sequence_no=int(event_id[1:]),
        correlation_id=correlation_id,
        preflight_valid=True, preflight_reason="ok", risk_score=0.1,
        p4_verdict=p4_verdict, p4_reason="ok", p4_risk_level="low",
        execution_status=execution_status, execution_error=execution_error,
        capabilities_checked=["filesystem.read"],
        final_status=final_status,
    )


TRACES_A = [make_trace(f"e{i}", f"c{i}") for i in range(1, 4)]
TRACES_B = [make_trace(f"e{i}", f"c{i}") for i in range(1, 4)]


# ─── a) Same traces -> same graph ────────────


def test_same_traces_same_node_count():
    g1 = CausalGraphBuilder().build(TRACES_A)
    g2 = CausalGraphBuilder().build(TRACES_B)
    assert len(g1.nodes) == len(g2.nodes)
    assert len(g1.edges) == len(g2.edges)


def test_same_traces_same_node_keys():
    g1 = CausalGraphBuilder().build(TRACES_A)
    g2 = CausalGraphBuilder().build(TRACES_B)
    assert list(g1.nodes.keys()) == list(g2.nodes.keys())


def test_same_traces_same_structure():
    g1 = CausalGraphBuilder().build(TRACES_A)
    g2 = CausalGraphBuilder().build(TRACES_B)
    for nid in g1.nodes:
        n1, n2 = g1.get(nid), g2.get(nid)
        assert n1.node_type == n2.node_type
        assert n1.parent_id == n2.parent_id
        assert n1.children == n2.children


def test_empty_traces_empty_graphs():
    g1 = CausalGraphBuilder().build([])
    g2 = CausalGraphBuilder().build([])
    assert len(g1.nodes) == 0 and len(g2.nodes) == 0


def test_single_trace_5_nodes():
    graph = CausalGraphBuilder().build([make_trace("e1", "c1")])
    assert len(graph.nodes) == 5
    assert {n.node_type for n in graph.nodes.values()} == {"host_event", "proposal", "decision", "execution", "outcome"}


# ─── b) Same graph -> same fingerprint ────────


def test_fingerprint_identical_for_same_graph():
    g1 = CausalGraphBuilder().build(TRACES_A)
    g2 = CausalGraphBuilder().build(TRACES_B)
    assert fingerprint(g1) == fingerprint(g2)


def test_fingerprint_differs_for_different_graphs():
    g1 = CausalGraphBuilder().build([make_trace("e1", "c1")])
    g2 = CausalGraphBuilder().build([make_trace("e1", "c1"), make_trace("e2", "c2")])
    assert fingerprint(g1) != fingerprint(g2)


def test_fingerprint_empty_graph():
    g = CausalGraphBuilder().build([])
    fp = fingerprint(g)
    assert isinstance(fp, str) and len(fp) == 16


def test_fingerprint_stable():
    g = CausalGraphBuilder().build(TRACES_A)
    assert fingerprint(g) == fingerprint(g)


def test_fingerprint_length():
    g = CausalGraphBuilder().build(TRACES_A)
    assert len(fingerprint(g)) == 16


# ─── c) No replay divergence ─────────────────


def test_replay_valid_identical_data():
    validator = ReplayValidator()
    traces = [make_trace("e1", "c1"), make_trace("e2", "c2")]
    snap = RuntimeSnapshot(
        snapshot_id="cp_test", created_at=100.0,
        runtime_state_snapshot={"status": "running", "total_events_processed": 2},
        trace_count=2, traces=[t.__dict__ for t in traces],
        schema_version=str(FROZEN_SCHEMA_VERSION),
    )
    v = validator.validate(snap, traces)
    assert v.valid and v.divergence_count == 0 and v.causal_integrity and v.trace_fingerprint_match


def test_replay_validation_counts():
    validator = ReplayValidator()
    traces = [make_trace("e1", "c1")]
    snap = RuntimeSnapshot(snapshot_id="cp_t", created_at=100.0, runtime_state_snapshot={},
                           trace_count=1, traces=[t.__dict__ for t in traces], schema_version=str(FROZEN_SCHEMA_VERSION))
    v = validator.validate(snap, traces)
    assert v.total_original == 1 and v.total_replayed == 1


def test_replay_valid_empty():
    snap = RuntimeSnapshot(snapshot_id="cp_e", created_at=100.0, runtime_state_snapshot={},
                           trace_count=0, traces=[], schema_version=str(FROZEN_SCHEMA_VERSION))
    v = ReplayValidator().validate(snap, [])
    assert v.valid and v.divergence_count == 0


def test_replay_causal_integrity():
    traces = [make_trace("e1", "c1")]
    snap = RuntimeSnapshot(snapshot_id="cp_t", created_at=100.0, runtime_state_snapshot={},
                           trace_count=1, traces=[t.__dict__ for t in traces], schema_version=str(FROZEN_SCHEMA_VERSION))
    assert ReplayValidator().validate(snap, traces).causal_integrity


# ─── d) Order matters ────────────────────────


def test_reversed_order_different_node_keys():
    t1, t2 = make_trace("e1", "c1"), make_trace("e2", "c2")
    gf = CausalGraphBuilder().build([t1, t2])
    gr = CausalGraphBuilder().build([t2, t1])
    assert list(gf.nodes.keys()) != list(gr.nodes.keys())


def test_replay_detects_order_divergence():
    validator = ReplayValidator()
    orig = [make_trace("e1", "c1"), make_trace("e2", "c2")]
    repl = [make_trace("e2", "c2"), make_trace("e1", "c1")]
    snap = RuntimeSnapshot(snapshot_id="cp_o", created_at=100.0, runtime_state_snapshot={},
                           trace_count=2, traces=[t.__dict__ for t in orig], schema_version=str(FROZEN_SCHEMA_VERSION))
    v = validator.validate(snap, repl)
    assert not v.valid or v.divergence_count > 0


def test_reversed_order_different_fingerprints():
    t1, t2 = make_trace("e1", "c1"), make_trace("e2", "c2")
    gf = CausalGraphBuilder().build([t1, t2])
    gr = CausalGraphBuilder().build([t2, t1])
    assert fingerprint(gf) != fingerprint(gr)


# ─── e) Data integrity ───────────────────────


def test_changing_final_status_changes_fingerprint():
    t1 = make_trace("e1", "c1", final_status="P4_ALLOW")
    t2 = make_trace("e1", "c1", final_status="SANDBOX_FAILED", execution_status="FAILED",
                    execution_error="err")
    g1, g2 = CausalGraphBuilder().build([t1]), CausalGraphBuilder().build([t2])
    assert fingerprint(g1) != fingerprint(g2)


def test_changing_p4_verdict_changes_node_count():
    ta = make_trace("e1", "c1", p4_verdict="ALLOW", final_status="P4_ALLOW")
    tb = make_trace("e1", "c1", p4_verdict="BLOCK", final_status="P4_BLOCK", execution_status="UNKNOWN")
    assert len(CausalGraphBuilder().build([ta]).nodes) == 5
    assert len(CausalGraphBuilder().build([tb]).nodes) == 4


def test_changing_event_id_changes_keys():
    g1 = CausalGraphBuilder().build([make_trace("e1", "c1")])
    g2 = CausalGraphBuilder().build([make_trace("e2", "c1")])
    assert list(g1.nodes.keys()) != list(g2.nodes.keys())


def test_replay_detects_status_divergence():
    validator = ReplayValidator()
    orig = [make_trace("e1", "c1", final_status="P4_ALLOW")]
    repl = [make_trace("e1", "c1", final_status="SANDBOX_FAILED", execution_status="FAILED", execution_error="crash")]
    snap = RuntimeSnapshot(snapshot_id="cp_s", created_at=100.0, runtime_state_snapshot={},
                           trace_count=1, traces=[t.__dict__ for t in orig], schema_version=str(FROZEN_SCHEMA_VERSION))
    v = validator.validate(snap, repl)
    assert not v.valid or v.divergence_count > 0


def test_trace_fingerprint_changes_when_field_changed():
    t = make_trace("e1", "c1")
    fp1 = fingerprint(t)
    t.risk_score = 0.9
    assert fp1 != fingerprint(t)
