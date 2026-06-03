import pytest
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from cognitive_runtime.contracts.frozen.graph_contract import (
    CausalNodeContract,
    CausalEdgeContract,
    GraphContract,
)
from cognitive_runtime.contracts.frozen.schema_version import get_expected_fingerprint


def test_causal_node_contract_expected_fields():
    node = CausalNodeContract(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=100.0,
        parent_id=None, children=[],
    )
    assert node.node_id == "n1"
    assert node.event_id == "e1"
    assert node.correlation_id == "c1"
    assert node.node_type == "host_event"
    assert node.data == {}
    assert node.timestamp == 100.0
    assert node.parent_id is None
    assert node.children == []


def test_causal_node_contract_is_frozen():
    node = CausalNodeContract("n1", "e1", "c1", "host_event", {}, 0.0, None, [])
    with pytest.raises(Exception):
        node.node_id = "n2"


def test_causal_node_contract_valid_types():
    for ntype in ("host_event", "proposal", "decision", "execution", "blocked", "outcome"):
        node = CausalNodeContract("n1", "e1", "c1", ntype, {}, 0.0, None, [])
        assert node.node_type == ntype


def test_causal_node_contract_from_instance():
    @dataclass
    class MockNode:
        node_id: str = "n1"
        event_id: str = "e1"
        correlation_id: str = "c1"
        node_type: str = "execution"
        data: dict = None
        timestamp: float = 50.0
        parent_id: Optional[str] = None
        children: list = None
    mock = MockNode()
    mock.data = {"key": "val"}
    mock.children = ["n2"]
    contract = CausalNodeContract.from_instance(mock)
    assert contract.node_id == "n1"
    assert contract.data == {"key": "val"}
    assert contract.children == ["n2"]


def test_causal_node_contract_validate_valid():
    node = CausalNodeContract("n1", "e1", "c1", "host_event", {}, 0.0, None, [])
    assert node.validate() == []


def test_causal_node_contract_validate_empty_node_id():
    node = CausalNodeContract("", "e1", "c1", "host_event", {}, 0.0, None, [])
    violations = node.validate()
    assert "node_id must be non-empty" in violations


def test_causal_node_contract_validate_invalid_type():
    node = CausalNodeContract("n1", "e1", "c1", "invalid_type", {}, 0.0, None, [])
    violations = node.validate()
    assert any("invalid node_type" in v for v in violations)


def test_causal_node_contract_validate_data_not_dict():
    node = CausalNodeContract("n1", "e1", "c1", "host_event", "not_dict", 0.0, None, [])
    violations = node.validate()
    assert any("data must be a dict" in v for v in violations)


def test_causal_node_contract_validate_multiple():
    node = CausalNodeContract("", "e1", "c1", "bad_type", "not_dict", 0.0, None, [])
    assert len(node.validate()) >= 2


def test_causal_edge_contract_expected_fields():
    edge = CausalEdgeContract("e1", "n1", "n2", "proposes", {})
    assert edge.edge_id == "e1"
    assert edge.source_id == "n1"
    assert edge.target_id == "n2"
    assert edge.edge_type == "proposes"
    assert edge.meta == {}


def test_causal_edge_contract_is_frozen():
    edge = CausalEdgeContract("e1", "n1", "n2", "proposes", {})
    with pytest.raises(Exception):
        edge.edge_id = "e2"


def test_causal_edge_contract_valid_types():
    for etype in ("proposes", "validates", "decides", "executes", "results", "blocks"):
        edge = CausalEdgeContract("e1", "n1", "n2", etype, {})
        assert edge.edge_type == etype


def test_causal_edge_contract_from_instance():
    @dataclass
    class MockEdge:
        edge_id: str = "e1"
        source_id: str = "n1"
        target_id: str = "n2"
        edge_type: str = "decides"
        meta: dict = None
    mock = MockEdge()
    mock.meta = {"key": "val"}
    contract = CausalEdgeContract.from_instance(mock)
    assert contract.edge_id == "e1"
    assert contract.meta == {"key": "val"}


def test_causal_edge_contract_validate_valid():
    edge = CausalEdgeContract("e1", "n1", "n2", "proposes", {})
    assert edge.validate() == []


def test_causal_edge_contract_validate_invalid_type():
    edge = CausalEdgeContract("e1", "n1", "n2", "invalid", {})
    violations = edge.validate()
    assert any("invalid edge_type" in v for v in violations)


def test_causal_edge_contract_validate_empty_id():
    edge = CausalEdgeContract("", "n1", "n2", "proposes", {})
    violations = edge.validate()
    assert "edge_id must be non-empty" in violations


def test_graph_contract_expected_properties():
    assert "nodes" in GraphContract.EXPECTED_PROPERTIES
    assert "edges" in GraphContract.EXPECTED_PROPERTIES
    assert "roots" in GraphContract.EXPECTED_PROPERTIES
    assert "dominant_layers" in GraphContract.EXPECTED_PROPERTIES
    assert "failure_points" in GraphContract.EXPECTED_PROPERTIES


def test_graph_contract_expected_methods():
    for method in ("get", "traverse", "incoming", "outgoing",
                   "path_to_outcome", "filter_by_type", "correlation_subgraph"):
        assert method in GraphContract.EXPECTED_METHODS


def test_graph_contract_node_attributes():
    for attr in ("node_id", "event_id", "correlation_id",
                 "node_type", "data", "timestamp", "parent_id", "children"):
        assert attr in GraphContract.NODE_ATTRIBUTES


def test_graph_contract_edge_attributes():
    for attr in ("edge_id", "source_id", "target_id", "edge_type", "meta"):
        assert attr in GraphContract.EDGE_ATTRIBUTES


def test_graph_contract_check_graph_missing_property():
    violations = GraphContract.check_graph(object())
    assert any("missing property" in v for v in violations)


def test_graph_contract_check_graph_missing_method():
    class NoMethods:
        nodes = {}
        edges = []
        roots = []
        dominant_layers = {}
        failure_points = []
    violations = GraphContract.check_graph(NoMethods())
    assert any("missing method" in v for v in violations)


def test_graph_contract_check_against_real_causal_graph():
    from cognitive_runtime.contracts.causal_graph import CausalGraph, CausalNode, CausalEdge
    n1 = CausalNode("n1", "e1", "c1", "host_event", {}, 0.0)
    n2 = CausalNode("n2", "e1", "c1", "outcome", {}, 1.0, parent_id="n1", children=[])
    e1 = CausalEdge("e1", "n1", "n2", "proposes", {})
    graph = CausalGraph({"n1": n1, "n2": n2}, [e1])
    assert GraphContract.check_graph(graph) == []


def test_graph_contract_check_graph_node_missing_attrs():
    from cognitive_runtime.contracts.causal_graph import CausalGraph, CausalNode
    # Mock graph where nodes attribute returns a dict with a partial node
    good = CausalNode("n1", "e1", "c1", "host_event", {}, 0.0)
    class PartialNode:
        def __init__(self):
            self.node_id = "n2"
    class MockGraph:
        nodes = {"n1": good, "n2": PartialNode()}
        edges = []
        roots = ["n1"]
        dominant_layers = {"host_event": 1}
        failure_points = []
        def get(self, nid): return None
        def traverse(self, nid): return []
        def incoming(self, nid): return []
        def outgoing(self, nid): return []
        def path_to_outcome(self, nid): return []
        def filter_by_type(self, nt): return []
        def correlation_subgraph(self, cid): return CausalGraph({}, [])
    violations = GraphContract.check_graph(MockGraph())
    assert any("missing attribute" in v for v in violations)


def test_graph_contract_check_node_instance_valid():
    from cognitive_runtime.contracts.causal_graph import CausalNode
    node = CausalNode("n1", "e1", "c1", "host_event", {}, 0.0)
    assert GraphContract.check_node_instance(node) == []


def test_graph_contract_check_node_instance_missing():
    assert len(GraphContract.check_node_instance(object())) > 0


def test_graph_contract_check_edge_instance_valid():
    from cognitive_runtime.contracts.causal_graph import CausalEdge
    edge = CausalEdge("e1", "n1", "n2", "proposes", {})
    assert GraphContract.check_edge_instance(edge) == []


def test_graph_contract_check_edge_instance_missing():
    assert len(GraphContract.check_edge_instance(object())) > 0


def test_graph_contract_fingerprints_registered():
    assert get_expected_fingerprint("CausalNode") is not None
    assert get_expected_fingerprint("CausalEdge") is not None
    assert get_expected_fingerprint("GraphContract") is not None
