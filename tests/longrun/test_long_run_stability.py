import gc
import os
import uuid

import pytest

from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.contracts.causal_graph import CausalGraphBuilder
from cognitive_runtime.intelligence.compression_engine import CompressionEngine
from cognitive_runtime.stability.stability_analyzer import StabilityAnalyzer
from cognitive_runtime.intelligence.intelligence_store import IntelligenceStore
from cognitive_runtime.recovery.checkpoint_manager import CheckpointManager
from cognitive_runtime.recovery.runtime_snapshot import RuntimeSnapshot
from cognitive_runtime.substrate.event_queue import EventQueue
from cognitive_runtime.contracts.execution_contract import HostEvent, ExecutionResult
from cognitive_runtime.runtime.runtime_state import RuntimeState


pytestmark = pytest.mark.longrun


def _make_trace(event_id: str, risk: float = 0.1, status: str = "SUCCESS",
                p4_verdict: str = "ALLOW", final_status: str = "P4_ALLOW",
                total_time: float = 10.0) -> ExecutionTrace:
    return ExecutionTrace(
        event_id=event_id,
        session_id="longrun-session",
        sequence_no=1,
        correlation_id=f"cr-{event_id}",
        preflight_valid=True,
        preflight_reason="preflight_passed",
        risk_score=risk,
        p4_verdict=p4_verdict,
        p4_reason="ok",
        p4_risk_level="low",
        execution_status=status,
        final_status=final_status,
        total_time=total_time,
    )


# ── (a) 10k trace cycle simulation ──

def test_10k_trace_cycle_no_memory_leak():
    store = IntelligenceStore(max_patterns=10000)
    analyzer = StabilityAnalyzer(store, window_size=100, history_size=20)
    builder = CausalGraphBuilder()
    state = RuntimeState()
    state.started_at = 1000.0
    state.status = "running"
    traces_pool = []

    for i in range(10000):
        trace = _make_trace(
            event_id=f"e{i:05d}",
            risk=0.05 + (i % 100) * 0.01,
            status="SUCCESS" if i % 5 != 0 else "FAILED",
            p4_verdict="ALLOW" if i % 20 != 0 else "BLOCK",
            final_status="P4_ALLOW" if i % 20 != 0 else "P4_BLOCK",
            total_time=5.0 + (i % 50) * 0.5,
        )
        traces_pool.append(trace)

        if i > 0 and i % 10 == 0:
            graph = builder.build(traces_pool[-100:])
            report = analyzer.analyze(traces_pool[-100:], state, graph)

    gc.collect()
    assert len(analyzer._window_history) <= analyzer._history_size
    assert len(analyzer._score_history) <= analyzer._history_size
    assert analyzer._window_history[-1].trace_count == 100
    assert 0 <= report.score.overall <= 1.0


def test_10k_unique_traces_stored():
    traces = []
    for i in range(10000):
        trace = _make_trace(
            event_id=f"e{i:05d}",
            risk=0.1 + (i % 100) * 0.008,
            status="SUCCESS" if i % 3 != 0 else "FAILED",
            final_status="P4_ALLOW" if i % 3 != 0 else "SANDBOX_FAILED",
            total_time=10.0 + i * 0.001,
        )
        traces.append(trace)
    assert len(traces) == 10000
    ids = {t.event_id for t in traces}
    assert len(ids) == 10000


# ── (b) Compression engine sustained ──

def test_compression_1000_traces_in_batches():
    engine = CompressionEngine()
    builder = CausalGraphBuilder()

    for batch_idx in range(10):
        batch = []
        for j in range(100):
            t = _make_trace(
                event_id=f"b{batch_idx}_e{j:03d}",
                risk=0.1 * (j % 10) / 10.0,
                status="SUCCESS" if j % 4 != 0 else "FAILED",
                final_status="P4_ALLOW" if j % 4 != 0 else "SANDBOX_FAILED",
            )
            batch.append(t)
        graph = builder.build(batch)
        report = engine.process(graph, batch)
        assert report.total_patterns > 0
        assert report.patterns_found >= 0

    assert engine.total_cycles == 10
    assert engine.store.top_patterns


def test_compression_accumulates_patterns():
    engine = CompressionEngine()
    builder = CausalGraphBuilder()
    all_traces = []

    for batch_idx in range(5):
        batch = []
        for j in range(20):
            t = _make_trace(
                event_id=f"acc{batch_idx}_e{j:03d}",
                risk=0.1,
                status="SUCCESS",
                final_status="P4_ALLOW",
            )
            batch.append(t)
            all_traces.append(t)
        graph = builder.build(batch)
        report = engine.process(graph, batch)
        assert report.total_patterns > 0

    final = engine.process(builder.build(all_traces[-50:]), all_traces[-50:])
    assert final.total_patterns > 0
    assert final.total_failures >= 0
    assert final.total_fingerprints > 0


# ── (c) Stability analyzer sustained ──

def test_stability_analyzer_200_times():
    store = IntelligenceStore()
    analyzer = StabilityAnalyzer(store, window_size=50, history_size=20)
    builder = CausalGraphBuilder()
    state = RuntimeState()
    state.started_at = 1000.0
    state.status = "running"
    traces = []

    for cycle in range(200):
        batch = [
            _make_trace(
                event_id=f"c{cycle}_e{k}",
                risk=0.05 + (cycle % 10) * 0.09,
                status="SUCCESS" if (cycle + k) % 5 != 0 else "FAILED",
                p4_verdict="ALLOW" if (cycle + k) % 20 != 0 else "BLOCK",
                final_status="P4_ALLOW" if (cycle + k) % 20 != 0 else "P4_BLOCK",
                total_time=8.0 + (cycle % 30) * 0.3,
            )
            for k in range(20)
        ]
        traces.extend(batch)
        state.record_cycle(
            duration_ms=10.0 + (cycle % 50) * 0.2,
            success=(cycle % 5 != 0),
            queue_depth=0,
        )
        graph = builder.build(batch)
        report = analyzer.analyze(traces, state, graph)

    assert len(analyzer._score_history) == analyzer._history_size
    assert analyzer._score_history[-1] <= 1.0
    assert report.trend.window_count > 0
    assert report.trend.direction in ("stable", "improving", "degrading")


# ── (d) Checkpoint rotation ──

def test_checkpoint_rotation_keeps_only_10(tmp_path):
    mgr = CheckpointManager(checkpoint_dir=str(tmp_path), max_checkpoints=10)

    for i in range(15):
        snap = RuntimeSnapshot(
            snapshot_id=f"cp-{i:03d}",
            created_at=float(1000 + i),
            runtime_state_snapshot={"cycle": i},
            trace_count=i,
            traces=[],
            cycle_count=i,
        )
        mgr.save(snap)

    assert mgr.checkpoint_count == 10
    ids = [m.checkpoint_id for m in mgr.metadata]
    assert "cp-000" not in ids
    assert "cp-004" not in ids
    assert "cp-005" in ids


def test_checkpoint_files_exist_for_metadata(tmp_path):
    mgr = CheckpointManager(checkpoint_dir=str(tmp_path), max_checkpoints=10)

    for i in range(15):
        snap = RuntimeSnapshot(
            snapshot_id=f"cp-{i:03d}",
            created_at=float(1000 + i),
            runtime_state_snapshot={"cycle": i},
            trace_count=i,
            traces=[],
            cycle_count=i,
        )
        mgr.save(snap)

    assert mgr.checkpoint_count == 10
    for meta in mgr.metadata:
        assert os.path.exists(meta.file_path)


# ── (e) WAL churn ──

def test_wal_push_pop_ack_100_events(db_path):
    q = EventQueue(db_path=db_path)
    q.open()

    for i in range(100):
        ev = HostEvent(
            event_id=f"wal-e{i:04d}",
            session_id="wal-session",
            timestamp=float(1000 + i),
            source="wal_test",
            payload={"seq": i, "data": f"payload-{i}"},
        )
        q.push(ev)

    assert q.queue_depth == 100

    for i in range(100):
        popped = q.pop()
        assert popped is not None
        assert popped.event_id == f"wal-e{i:04d}"

        result = ExecutionResult(
            execution_id=f"res-{popped.event_id}",
            proposal_id=f"prop-{popped.event_id}",
            session_id=popped.session_id,
            status="SUCCESS",
            output={"processed": i},
            error=None,
            started_at=float(1000 + i),
            finished_at=float(1000.5 + i),
        )
        q.ack(popped.event_id, result)

    assert q.queue_depth == 0
    assert q.stats.processed == 100
    assert q.stats.total_events == 100

    q.close()
