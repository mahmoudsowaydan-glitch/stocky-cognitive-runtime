import pytest

from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.contracts.causal_graph import CausalGraph, CausalNode, CausalEdge
from cognitive_runtime.intelligence.intelligence_store import IntelligenceStore, Pattern
from cognitive_runtime.governance.entropy_index import EntropyIndex
from cognitive_runtime.governance.governance_report import EntropyMetrics


@pytest.fixture
def empty_graph():
    return CausalGraph({}, [])


@pytest.fixture
def single_node_graph():
    node = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
    )
    return CausalGraph({"n1": node}, [])


def _make_trace(event_id="e1"):
    return ExecutionTrace(
        event_id=event_id, session_id="s1", sequence_no=1,
        correlation_id="c1",
        preflight_valid=True, preflight_reason="ok",
        risk_score=0.1,
        p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low",
        execution_status="SUCCESS",
        final_status="P4_ALLOW",
    )


def test_entropy_index_empty_traces(empty_graph):
    index = EntropyIndex()
    store = IntelligenceStore()
    result = index.analyze([], empty_graph, store)
    assert isinstance(result, EntropyMetrics)
    assert result.causal_density == 0.0
    assert result.pattern_explosion == 0.0
    assert result.trace_inflation == 0.0
    assert result.graph_branching == 0.0
    assert result.overall == 0.0


def test_entropy_index_single_trace_no_patterns(single_node_graph):
    index = EntropyIndex()
    store = IntelligenceStore()
    result = index.analyze([_make_trace()], single_node_graph, store)
    assert result.pattern_explosion == 0.0
    assert isinstance(result.overall, float)


def test_entropy_pattern_explosion_uses_len_store_patterns(single_node_graph):
    """Key bug fix: uses len(store.patterns) not store.pattern_count"""
    index = EntropyIndex()
    store = IntelligenceStore()
    store.upsert_pattern(Pattern("p1", 1, "sig1", {}))
    store.upsert_pattern(Pattern("p2", 1, "sig2", {}))
    store.upsert_pattern(Pattern("p3", 1, "sig3", {}))
    traces = [_make_trace() for _ in range(10)]
    result = index.analyze(traces, CausalGraph({}, []), store)
    assert result.pattern_explosion == pytest.approx(3 / 10)


def test_entropy_pattern_explosion_no_traces():
    index = EntropyIndex()
    store = IntelligenceStore()
    store.upsert_pattern(Pattern("p1", 1, "sig1", {}))
    result = index.analyze([], CausalGraph({}, []), store)
    assert result.pattern_explosion == 0.0


def test_entropy_trace_inflation_below_ideal(single_node_graph):
    index = EntropyIndex()
    store = IntelligenceStore()
    result = index.analyze([_make_trace()], single_node_graph, store)
    assert result.trace_inflation == 0.0


def test_entropy_trace_inflation_above_ideal():
    index = EntropyIndex()
    store = IntelligenceStore()
    nodes = {f"n{i}": CausalNode(
        node_id=f"n{i}", event_id="e1", correlation_id="c1",
        node_type="host_event" if i == 0 else "execution",
        data={}, timestamp=0.0,
    ) for i in range(20)}
    graph = CausalGraph(nodes, [])
    result = index.analyze([_make_trace()], graph, store)
    avg = 20 / 1
    expected = min(1.0, (avg - 5.0) / 10.0)
    assert result.trace_inflation == round(expected, 4)


def test_entropy_graph_branching_no_children(single_node_graph):
    index = EntropyIndex()
    store = IntelligenceStore()
    result = index.analyze([_make_trace()], single_node_graph, store)
    assert result.graph_branching == 0.0


def test_entropy_graph_branching_with_children():
    index = EntropyIndex()
    store = IntelligenceStore()
    nodes = {
        "n1": CausalNode("n1", "e1", "c1", "host_event", {}, 0.0, children=["n2", "n3", "n4"]),
        "n2": CausalNode("n2", "e1", "c1", "outcome", {}, 0.0),
        "n3": CausalNode("n3", "e1", "c1", "outcome", {}, 0.0),
        "n4": CausalNode("n4", "e1", "c1", "outcome", {}, 0.0),
    }
    graph = CausalGraph(nodes, [])
    result = index.analyze([_make_trace()], graph, store)
    avg_children = 3 / 4
    # avg_children (0.75) <= 1.0 => returns 0.0
    if avg_children <= 1.0:
        expected = 0.0
    else:
        expected = min(1.0, (avg_children - 1.0) / 2.0)
    assert result.graph_branching == expected


def test_entropy_causal_density_empty_graph(empty_graph):
    index = EntropyIndex()
    assert index._causal_density(empty_graph) == 0.0


def test_entropy_causal_density_ideal():
    index = EntropyIndex()
    nodes = {f"n{i}": CausalNode(f"n{i}", "e1", "c1", "host_event", {}, 0.0) for i in range(4)}
    edges = [CausalEdge(f"e{i}", f"n{i}", f"n{(i+1)%4}", "proposes", {}) for i in range(3)]
    graph = CausalGraph(nodes, edges)
    density = 3 / 4
    deviation = abs(density - 0.75) / 0.25
    assert index._causal_density(graph) == min(1.0, deviation)


def test_entropy_overall_weighted_sum(single_node_graph):
    index = EntropyIndex()
    store = IntelligenceStore()
    result = index.analyze([_make_trace()], single_node_graph, store)
    expected = 0.30 * result.causal_density + 0.25 * result.pattern_explosion + 0.25 * result.trace_inflation + 0.20 * result.graph_branching
    assert result.overall == round(min(1.0, expected), 4)


def test_entropy_rounding_to_4_places(single_node_graph):
    index = EntropyIndex()
    store = IntelligenceStore()
    result = index.analyze([_make_trace() for _ in range(3)], single_node_graph, store)
    for val in (result.causal_density, result.pattern_explosion, result.trace_inflation, result.graph_branching, result.overall):
        s = str(val)
        if "." in s:
            assert len(s.split(".")[1]) <= 4


def test_entropy_overall_capped_at_1():
    index = EntropyIndex()
    store = IntelligenceStore()
    nodes = {f"n{i}": CausalNode(
        node_id=f"n{i}", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
        children=["child"],
    ) for i in range(100)}
    for i in range(100):
        store.upsert_pattern(Pattern(f"p{i}", 1, f"sig{i}", {}))
    edges = [CausalEdge(f"e{i}", f"n{i}", "child", "proposes", {}) for i in range(100)]
    graph = CausalGraph(nodes, edges)
    result = index.analyze([_make_trace()], graph, store)
    assert result.overall <= 1.0
