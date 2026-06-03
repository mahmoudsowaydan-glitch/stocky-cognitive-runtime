import pytest

from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.contracts.causal_graph import (
    CausalGraph,
    CausalNode,
    CausalEdge,
    CausalGraphBuilder,
)


def test_causal_node_creation():
    node = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={"key": "val"},
        timestamp=100.0, parent_id=None, children=["n2"],
    )
    assert node.node_id == "n1"
    assert node.event_id == "e1"
    assert node.correlation_id == "c1"
    assert node.node_type == "host_event"
    assert node.data == {"key": "val"}
    assert node.timestamp == 100.0
    assert node.parent_id is None
    assert node.children == ["n2"]


def test_causal_node_default_children():
    node = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="outcome", data={}, timestamp=0.0,
    )
    assert node.children == []


def test_causal_node_is_frozen():
    node = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
    )
    with pytest.raises((AttributeError, TypeError)):
        node.node_id = "changed"


def test_causal_node_type_literals():
    for ntype in ("host_event", "proposal", "decision", "execution", "blocked", "outcome"):
        node = CausalNode(
            node_id="n1", event_id="e1", correlation_id="c1",
            node_type=ntype, data={}, timestamp=0.0,
        )
        assert node.node_type == ntype


def test_causal_edge_creation():
    edge = CausalEdge(
        edge_id="e1", source_id="n1", target_id="n2",
        edge_type="proposes", meta={"k": "v"},
    )
    assert edge.edge_id == "e1"
    assert edge.source_id == "n1"
    assert edge.target_id == "n2"
    assert edge.edge_type == "proposes"
    assert edge.meta == {"k": "v"}


def test_causal_edge_default_meta():
    edge = CausalEdge(
        edge_id="e1", source_id="n1", target_id="n2",
        edge_type="results",
    )
    assert edge.meta == {}


def test_causal_edge_is_frozen():
    edge = CausalEdge(
        edge_id="e1", source_id="n1", target_id="n2",
        edge_type="blocks",
    )
    with pytest.raises((AttributeError, TypeError)):
        edge.edge_id = "changed"


def test_causal_edge_type_literals():
    for etype in ("proposes", "validates", "decides", "executes", "results", "blocks"):
        edge = CausalEdge(
            edge_id="e1", source_id="n1", target_id="n2",
            edge_type=etype,
        )
        assert edge.edge_type == etype


def test_causal_graph_nodes_returns_copy():
    n = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
    )
    g = CausalGraph({"n1": n}, [])
    nodes = g.nodes
    nodes["new_key"] = n
    assert "new_key" not in g._nodes


def test_causal_graph_edges_returns_copy():
    e = CausalEdge(
        edge_id="e1", source_id="n1", target_id="n2",
        edge_type="proposes",
    )
    n1 = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
    )
    g = CausalGraph({"n1": n1}, [e])
    edges = g.edges
    edges.clear()
    assert len(g._edges) == 1


def test_causal_graph_roots_empty():
    g = CausalGraph({}, [])
    assert g.roots == []


def test_causal_graph_roots_parentless():
    n1 = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
    )
    n2 = CausalNode(
        node_id="n2", event_id="e1", correlation_id="c1",
        node_type="proposal", data={}, timestamp=0.0,
        parent_id="n1",
    )
    g = CausalGraph({"n1": n1, "n2": n2}, [])
    assert g.roots == ["n1"]


def test_causal_graph_roots_returns_copy():
    n1 = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
    )
    g = CausalGraph({"n1": n1}, [])
    roots = g.roots
    roots.append("n2")
    assert g.roots == ["n1"]


def test_dominant_layers():
    n1 = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
    )
    n2 = CausalNode(
        node_id="n2", event_id="e1", correlation_id="c1",
        node_type="proposal", data={}, timestamp=0.0,
    )
    n3 = CausalNode(
        node_id="n3", event_id="e2", correlation_id="c2",
        node_type="host_event", data={}, timestamp=0.0,
    )
    g = CausalGraph({"n1": n1, "n2": n2, "n3": n3}, [])
    assert g.dominant_layers == {"host_event": 2, "proposal": 1}


def test_dominant_layers_empty():
    g = CausalGraph({}, [])
    assert g.dominant_layers == {}


def test_failure_points():
    n_ok = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="outcome", data={"final_status": "success"}, timestamp=0.0,
    )
    n_fail = CausalNode(
        node_id="n2", event_id="e2", correlation_id="c2",
        node_type="outcome", data={"final_status": "failed"}, timestamp=0.0,
    )
    n_block = CausalNode(
        node_id="n3", event_id="e3", correlation_id="c3",
        node_type="outcome", data={"final_status": "blocked"}, timestamp=0.0,
    )
    n_err = CausalNode(
        node_id="n4", event_id="e4", correlation_id="c4",
        node_type="outcome", data={"final_status": "error"}, timestamp=0.0,
    )
    n_host = CausalNode(
        node_id="n5", event_id="e5", correlation_id="c5",
        node_type="host_event", data={"final_status": "failed"}, timestamp=0.0,
    )
    g = CausalGraph({"n1": n_ok, "n2": n_fail, "n3": n_block, "n4": n_err, "n5": n_host}, [])
    fps = g.failure_points
    assert len(fps) == 3
    assert n_fail in fps
    assert n_block in fps
    assert n_err in fps
    assert n_ok not in fps
    assert n_host not in fps


def test_failure_points_empty():
    n = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="outcome", data={"final_status": "success"}, timestamp=0.0,
    )
    g = CausalGraph({"n1": n}, [])
    assert g.failure_points == []


def test_causal_graph_get():
    n = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
    )
    g = CausalGraph({"n1": n}, [])
    assert g.get("n1") is n
    assert g.get("missing") is None


def test_traverse():
    n1 = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
        children=["n2"],
    )
    n2 = CausalNode(
        node_id="n2", event_id="e1", correlation_id="c1",
        node_type="proposal", data={}, timestamp=0.0,
        parent_id="n1", children=["n3"],
    )
    n3 = CausalNode(
        node_id="n3", event_id="e1", correlation_id="c1",
        node_type="outcome", data={}, timestamp=0.0,
        parent_id="n2",
    )
    g = CausalGraph({"n1": n1, "n2": n2, "n3": n3}, [])
    assert [n.node_id for n in g.traverse("n1")] == ["n1", "n2", "n3"]


def test_traverse_unknown():
    g = CausalGraph({}, [])
    assert g.traverse("missing") == []


def test_incoming_edges():
    e1 = CausalEdge(
        edge_id="e1", source_id="n1", target_id="n2", edge_type="proposes",
    )
    e2 = CausalEdge(
        edge_id="e2", source_id="n2", target_id="n3", edge_type="decides",
    )
    n1 = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
    )
    n2 = CausalNode(
        node_id="n2", event_id="e1", correlation_id="c1",
        node_type="proposal", data={}, timestamp=0.0,
        parent_id="n1",
    )
    n3 = CausalNode(
        node_id="n3", event_id="e1", correlation_id="c1",
        node_type="decision", data={}, timestamp=0.0,
        parent_id="n2",
    )
    g = CausalGraph({"n1": n1, "n2": n2, "n3": n3}, [e1, e2])
    assert len(g.incoming("n2")) == 1
    assert g.incoming("n2")[0].source_id == "n1"


def test_outgoing_edges():
    e1 = CausalEdge(
        edge_id="e1", source_id="n1", target_id="n2", edge_type="proposes",
    )
    e2 = CausalEdge(
        edge_id="e2", source_id="n1", target_id="n3", edge_type="validates",
    )
    n1 = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
    )
    n2 = CausalNode(
        node_id="n2", event_id="e1", correlation_id="c1",
        node_type="proposal", data={}, timestamp=0.0,
        parent_id="n1",
    )
    n3 = CausalNode(
        node_id="n3", event_id="e1", correlation_id="c1",
        node_type="outcome", data={}, timestamp=0.0,
        parent_id="n1",
    )
    g = CausalGraph({"n1": n1, "n2": n2, "n3": n3}, [e1, e2])
    assert len(g.outgoing("n1")) == 2


def test_path_to_outcome():
    n1 = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
        children=["n2"],
    )
    n2 = CausalNode(
        node_id="n2", event_id="e1", correlation_id="c1",
        node_type="proposal", data={}, timestamp=0.0,
        parent_id="n1", children=["n3"],
    )
    n3 = CausalNode(
        node_id="n3", event_id="e1", correlation_id="c1",
        node_type="outcome", data={}, timestamp=0.0,
        parent_id="n2",
    )
    g = CausalGraph({"n1": n1, "n2": n2, "n3": n3}, [])
    assert [n.node_id for n in g.path_to_outcome("n1")] == ["n1", "n2", "n3"]


def test_path_to_outcome_unknown():
    g = CausalGraph({}, [])
    assert g.path_to_outcome("missing") == []


def test_path_to_outcome_no_outcome():
    n1 = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
        children=["n2"],
    )
    n2 = CausalNode(
        node_id="n2", event_id="e1", correlation_id="c1",
        node_type="proposal", data={}, timestamp=0.0,
        parent_id="n1",
    )
    g = CausalGraph({"n1": n1, "n2": n2}, [])
    assert g.path_to_outcome("n1") == []


def test_filter_by_type():
    n1 = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
    )
    n2 = CausalNode(
        node_id="n2", event_id="e1", correlation_id="c1",
        node_type="execution", data={}, timestamp=0.0,
    )
    n3 = CausalNode(
        node_id="n3", event_id="e2", correlation_id="c2",
        node_type="execution", data={}, timestamp=0.0,
    )
    g = CausalGraph({"n1": n1, "n2": n2, "n3": n3}, [])
    assert len(g.filter_by_type("execution")) == 2
    assert len(g.filter_by_type("outcome")) == 0


def test_correlation_subgraph():
    n1 = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
    )
    n2 = CausalNode(
        node_id="n2", event_id="e1", correlation_id="c1",
        node_type="proposal", data={}, timestamp=0.0,
        parent_id="n1",
    )
    n3 = CausalNode(
        node_id="n3", event_id="e2", correlation_id="c2",
        node_type="host_event", data={}, timestamp=0.0,
    )
    e = CausalEdge(
        edge_id="e1", source_id="n1", target_id="n2", edge_type="proposes",
    )
    g = CausalGraph({"n1": n1, "n2": n2, "n3": n3}, [e])
    sg = g.correlation_subgraph("c1")
    assert len(sg.nodes) == 2
    assert "n1" in sg.nodes
    assert "n2" in sg.nodes


def test_correlation_subgraph_empty():
    n = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
    )
    g = CausalGraph({"n1": n}, [])
    assert len(g.correlation_subgraph("c2").nodes) == 0


def test_builder_success_path():
    trace = ExecutionTrace(
        event_id="e1", session_id="s1", correlation_id="c1",
        preflight_valid=True, risk_score=0.1,
        p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low",
        execution_status="SUCCESS",
        final_status="P4_ALLOW",
    )
    graph = CausalGraphBuilder().build([trace])
    assert len(graph.nodes) == 5
    assert len(graph.edges) == 4
    types = {n.node_type for n in graph.nodes.values()}
    assert types == {"host_event", "proposal", "decision", "execution", "outcome"}
    host = graph.get("e1__host")
    assert host is not None and host.parent_id is None
    outcome = graph.get("e1__outcome")
    assert outcome is not None and outcome.data["final_status"] == "success"
    path = graph.path_to_outcome("e1__host")
    assert [n.node_type for n in path] == ["host_event", "proposal", "decision", "execution", "outcome"]


def test_builder_blocked_path_p4():
    trace = ExecutionTrace(
        event_id="e1", session_id="s1", correlation_id="c1",
        preflight_valid=True, risk_score=0.8,
        p4_verdict="BLOCK", p4_reason="policy",
        p4_risk_level="high", p4_rule_triggered="rule_42",
        execution_status="UNKNOWN",
        final_status="P4_BLOCK",
    )
    graph = CausalGraphBuilder().build([trace])
    assert len(graph.nodes) == 4
    assert len(graph.edges) == 3
    types = {n.node_type for n in graph.nodes.values()}
    assert types == {"host_event", "proposal", "blocked", "outcome"}
    blocked = graph.get("e1__blocked")
    assert blocked is not None and blocked.data["verdict"] == "BLOCK"


def test_builder_preflight_invalid():
    trace = ExecutionTrace(
        event_id="e1", session_id="s1", correlation_id="c1",
        preflight_valid=False, preflight_reason="bad_payload",
        risk_score=0.0,
        p4_verdict="UNKNOWN",
        execution_status="UNKNOWN",
        final_status="BLOCKED_BY_PREFLIGHT",
    )
    graph = CausalGraphBuilder().build([trace])
    assert len(graph.nodes) == 3
    assert len(graph.edges) == 2
    types = {n.node_type for n in graph.nodes.values()}
    assert types == {"host_event", "blocked", "outcome"}
    blocked = graph.get("e1__blocked")
    assert blocked is not None and blocked.data["verdict"] == "BLOCKED"


def test_builder_children_wired():
    trace = ExecutionTrace(
        event_id="e1", session_id="s1", correlation_id="c1",
        preflight_valid=True, risk_score=0.1,
        p4_verdict="ALLOW", p4_reason="ok",
        execution_status="SUCCESS",
        final_status="P4_ALLOW",
    )
    graph = CausalGraphBuilder().build([trace])
    assert graph.get("e1__host").children == ["e1__proposal"]
    assert graph.get("e1__proposal").children == ["e1__decision"]
    assert graph.get("e1__decision").children == ["e1__execution"]
    assert graph.get("e1__execution").children == ["e1__outcome"]
    assert graph.get("e1__outcome").children == []


def test_builder_multiple_events():
    traces = [
        ExecutionTrace(
            event_id=f"e{i}", session_id="s1", correlation_id=f"c{i}",
            preflight_valid=True, risk_score=0.1,
            p4_verdict="ALLOW", p4_reason="ok",
            execution_status="SUCCESS",
            final_status="P4_ALLOW",
        )
        for i in range(3)
    ]
    graph = CausalGraphBuilder().build(traces)
    assert len(graph.nodes) == 3 * 5
    assert len(graph.edges) == 3 * 4


def test_builder_empty():
    graph = CausalGraphBuilder().build([])
    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0
    assert graph.roots == []


def test_builder_failed_execution_outcome():
    trace = ExecutionTrace(
        event_id="e1", session_id="s1", correlation_id="c1",
        preflight_valid=True, risk_score=0.5,
        p4_verdict="ALLOW", p4_reason="ok",
        execution_status="FAILED", execution_error="timeout",
        final_status="SANDBOX_FAILED",
    )
    graph = CausalGraphBuilder().build([trace])
    outcome = graph.get("e1__outcome")
    assert outcome is not None
    assert outcome.data["final_status"] == "failed"
    assert outcome.data["error"] == "timeout"
