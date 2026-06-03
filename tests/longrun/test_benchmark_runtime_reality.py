import random

from cognitive_runtime.epoch import BenchmarkRuntime
from cognitive_runtime.epoch.event_generator import EventGenerator
from cognitive_runtime.contracts.causal_graph import CausalGraph


class TestBenchmarkRuntimeReality:
    def test_cycle_uses_event_generator(self):
        rt = BenchmarkRuntime(seed=42, capture_interval=5)
        for _ in range(20):
            result = rt.cycle()
        assert rt.cycle_count == 20
        assert len(rt.traces) >= 20
        assert any(t.p4_verdict in ("BLOCK", "REVIEW", "DEFER") for t in rt.traces)

    def test_causal_graph_built_after_50_cycles(self):
        rt = BenchmarkRuntime(seed=42, capture_interval=5)
        for _ in range(55):
            rt.cycle()
        assert isinstance(rt.causal_graph, CausalGraph)

    def test_causal_graph_has_nodes(self):
        rt = BenchmarkRuntime(seed=42, capture_interval=5)
        for _ in range(100):
            rt.cycle()
        g = rt.causal_graph
        nodes = g.nodes if hasattr(g, 'nodes') else {}
        assert len(nodes) > 0, (
            f"CausalGraph has no nodes after 100 cycles. "
            f"traces={len(rt.traces)} "
            f"trace_types={set(t.final_status for t in rt.traces[:20])}"
        )

    def test_causal_graph_has_edges(self):
        rt = BenchmarkRuntime(seed=42, capture_interval=5)
        for _ in range(100):
            rt.cycle()
        edges = rt.causal_graph.edges if hasattr(rt.causal_graph, 'edges') else []
        assert len(edges) > 0

    def test_causal_graph_has_failure_points_with_real_events(self):
        rt = BenchmarkRuntime(seed=42, capture_interval=5)
        for _ in range(150):
            rt.cycle()
        fps = rt.causal_graph.failure_points
        assert len(fps) > 0, (
            f"No failure_points after 150 cycles. "
            f"Nodes: {len(rt.causal_graph.nodes) if hasattr(rt.causal_graph, 'nodes') else 0}"
        )

    def test_multiple_event_types_appear_in_traces(self):
        rt = BenchmarkRuntime(seed=42, capture_interval=5)
        for _ in range(200):
            rt.cycle()
        verdicts = set(t.p4_verdict for t in rt.traces)
        assert "ALLOW" in verdicts
        assert "BLOCK" in verdicts or "REVIEW" in verdicts or "DEFER" in verdicts

    def test_blocked_events_appear(self):
        rt = BenchmarkRuntime(seed=42, capture_interval=5)
        for _ in range(200):
            rt.cycle()
        blocked = [t for t in rt.traces if t.p4_verdict in ("BLOCK", "REVIEW", "DEFER")]
        assert len(blocked) > 0, "No blocked/review/defer events in 200 cycles"

    def test_preflight_failures_appear(self):
        rt = BenchmarkRuntime(seed=42, capture_interval=5)
        for _ in range(200):
            rt.cycle()
        failed_preflight = [t for t in rt.traces if t.preflight_valid is False]
        assert len(failed_preflight) > 0

    def test_high_risk_traces_appear(self):
        rt = BenchmarkRuntime(seed=42, capture_interval=5)
        for _ in range(200):
            rt.cycle()
        high_risk = [t for t in rt.traces if t.risk_score > 0.7]
        assert len(high_risk) > 0, "No high-risk traces in 200 cycles"

    def test_doctrine_stress_combinations(self):
        rt = BenchmarkRuntime(seed=42, capture_interval=5)
        for _ in range(200):
            rt.cycle()
        stress1 = [
            t for t in rt.traces
            if t.preflight_valid is False and t.risk_score > 0.5
        ]
        stress2 = [
            t for t in rt.traces
            if t.p4_verdict == "BLOCK" and t.risk_score > 0.7
        ]
        assert len(stress1) > 0 or len(stress2) > 0, (
            f"No doctrine stress combinations in 200 cycles. "
            f"Sample verdicts: {[t.p4_verdict for t in rt.traces[:30]]}"
        )

    def test_final_status_populated_for_blocked_events(self):
        rt = BenchmarkRuntime(seed=42, capture_interval=5)
        for _ in range(200):
            rt.cycle()
        blocked = [t for t in rt.traces if t.p4_verdict in ("BLOCK", "REVIEW", "DEFER")]
        blocked_with_fs = [t for t in blocked if t.final_status.startswith("P4_")]
        assert len(blocked_with_fs) > 0, (
            f"Blocked events without P4_ final_status. "
            f"Sample: {[(t.p4_verdict, t.final_status) for t in blocked[:5]]}"
        )

    def test_p4_rule_triggered_on_pressure_events(self):
        rt = BenchmarkRuntime(seed=42, capture_interval=5)
        for _ in range(200):
            rt.cycle()
        with_rules = [t for t in rt.traces if t.p4_rule_triggered is not None]
        assert len(with_rules) > 0, "No events with p4_rule_triggered in 200 cycles"

    def test_deterministic_reproduction(self):
        rt1 = BenchmarkRuntime(seed=42, capture_interval=5)
        rt2 = BenchmarkRuntime(seed=42, capture_interval=5)
        for _ in range(30):
            rt1.cycle()
            rt2.cycle()
        t1_verdicts = [(t.p4_verdict, t.risk_score) for t in rt1.traces]
        t2_verdicts = [(t.p4_verdict, t.risk_score) for t in rt2.traces]
        assert t1_verdicts == t2_verdicts

    def test_custom_event_generator(self):
        eg = EventGenerator(seed=99)
        rt = BenchmarkRuntime(seed=42, capture_interval=5, event_generator=eg)
        for _ in range(20):
            rt.cycle()
        assert rt.event_generator is eg

    def test_migration_events_produce_capabilities(self):
        rt = BenchmarkRuntime(seed=42, capture_interval=5)
        for _ in range(300):
            rt.cycle()
        with_caps = [t for t in rt.traces if len(t.capabilities_checked) > 0]
        assert len(with_caps) > 0, (
            f"No trace with capabilities_checked in 300 cycles. "
            f"Unique verdicts: {set(t.p4_verdict for t in rt.traces)}"
        )

    def test_causal_graph_dominant_layers(self):
        rt = BenchmarkRuntime(seed=42, capture_interval=5)
        for _ in range(100):
            rt.cycle()
        layers = rt.causal_graph.dominant_layers
        assert len(layers) > 0, f"dominant_layers empty: {layers}"

    def test_execution_error_on_failed_events(self):
        rt = BenchmarkRuntime(seed=42, capture_interval=5)
        for _ in range(200):
            rt.cycle()
        with_errors = [t for t in rt.traces if t.execution_error is not None]
        assert len(with_errors) > 0, "No execution_errors in 200 cycles"

    def test_governance_sees_rich_verdicts(self):
        rt = BenchmarkRuntime(seed=42, capture_interval=5)
        for _ in range(200):
            rt.cycle()
        verdicts = set(t.p4_verdict for t in rt.traces)
        assert len(verdicts) >= 3, (
            f"Only {len(verdicts)} unique verdicts: {verdicts}. "
            f"Expected at least ALLOW, BLOCK, and one more."
        )

    def test_confidence_sees_risk_variety(self):
        rt = BenchmarkRuntime(seed=42, capture_interval=5)
        for _ in range(200):
            rt.cycle()
        scores = [t.risk_score for t in rt.traces if t.risk_score > 0]
        max_rs = max(scores) if scores else 0
        min_rs = min(scores) if scores else 0
        assert max_rs > 0.5, f"risk_score range too narrow: [{min_rs}, {max_rs}]"
