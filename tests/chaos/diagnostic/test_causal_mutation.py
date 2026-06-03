"""Diagnostic: Causal mutation — tests CausalGraphBuilder under trace anomalies."""

from cognitive_runtime.contracts.causal_graph import CausalGraphBuilder
from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from chaos.harness.causal_mutator import CausalMutator


def make_traces(count: int) -> list:
    return [
        ExecutionTrace(
            event_id=f"e{i}", session_id="s1", sequence_no=i,
            correlation_id=f"c{i}",
            preflight_valid=True, preflight_reason="ok",
            risk_score=0.1,
            p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low",
            execution_status="SUCCESS",
            final_status="P4_ALLOW",
        ) for i in range(count)
    ]


def test_cycle_injection_does_not_crash_builder():
    traces = make_traces(5)
    mutator = CausalMutator(seed=42)
    mutated = mutator.inject_cycle(traces)
    builder = CausalGraphBuilder()
    graph = builder.build(mutated)
    assert len(graph.nodes) >= 1


def test_orphan_traces_produce_separate_roots():
    traces = make_traces(3)
    mutator = CausalMutator(seed=42)
    mutated = mutator.create_orphan(traces)
    builder = CausalGraphBuilder()
    graph = builder.build(mutated)
    assert len(graph.roots) >= 2


def test_duplicate_event_ids_produce_one_graph():
    traces = make_traces(4)
    mutator = CausalMutator(seed=42)
    mutated = mutator.duplicate_event_id(traces)
    builder = CausalGraphBuilder()
    graph = builder.build(mutated)
    assert len(graph.nodes) >= 1


def test_corrupted_final_status_preserved_in_trace():
    traces = make_traces(3)
    mutator = CausalMutator(seed=42)
    mutated = mutator.corrupt_final_status(traces, rate=1.0)
    corrupted = any(
        getattr(t, "final_status", "") in ("UNKNOWN", "CORRUPTED", None)
        for t in mutated
    )
    assert corrupted


def test_random_mutation_never_crashes():
    for _ in range(10):
        traces = make_traces(5)
        mutator = CausalMutator(seed=42)
        mutated = mutator.random_mutation(traces)
        builder = CausalGraphBuilder()
        graph = builder.build(mutated)
        assert len(graph.nodes) >= 1
