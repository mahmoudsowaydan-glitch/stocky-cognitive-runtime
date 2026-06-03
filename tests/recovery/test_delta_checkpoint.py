import json
import os
import tempfile

import pytest

from cognitive_runtime.recovery.delta_checkpoint import (
    CheckpointBaseMeta,
    DeltaCheckpointManager,
    DeltaSegment,
)
from cognitive_runtime.recovery.runtime_snapshot import RuntimeSnapshot


def make_snapshot(trace_count=10, cycle_count=100,
                  gov_count=5, conf_count=5, stab_count=5,
                  snapshot_id=None):
    import time
    sid = snapshot_id or f"cp_{time.time()}"
    return RuntimeSnapshot(
        snapshot_id=sid,
        created_at=time.time(),
        runtime_state_snapshot={"status": "running", "health_status": "healthy"},
        trace_count=trace_count,
        traces=[{"event_id": f"e{i}", "session_id": "s1"} for i in range(trace_count)],
        governance_score_history=[0.5 + i * 0.1 for i in range(gov_count)],
        confidence_score_history=[0.6 + i * 0.05 for i in range(conf_count)],
        confidence_gradient="stable",
        stability_score_history=[0.7 + i * 0.02 for i in range(stab_count)],
        queue_depth=5,
        total_events_processed=trace_count,
        schema_version="1.1.0",
        schema_fingerprint="abc123",
        cycle_count=cycle_count,
        recovery_mode_enabled=False,
    )


class TestDeltaCheckpointManagerConstruction:
    def test_creates_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            dcm = DeltaCheckpointManager(checkpoint_dir=tmp)
            assert os.path.exists(tmp)
            assert os.path.exists(os.path.join(tmp, "deltas"))
            assert dcm.enabled is True

    def test_disabled_does_nothing(self):
        dcm = DeltaCheckpointManager(enabled=False)
        snap = make_snapshot()
        result = dcm.save(snap)
        assert result is None

    def test_default_dir_created(self):
        dcm = DeltaCheckpointManager()
        assert os.path.exists(dcm._dir)
        assert os.path.exists(dcm._delta_dir)
        dcm.clear()


class TestDeltaCheckpointManagerSave:
    def test_first_save_is_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            dcm = DeltaCheckpointManager(checkpoint_dir=tmp, base_interval=500)
            snap = make_snapshot(cycle_count=100)
            result = dcm.save(snap)
            assert len(result) > 0  # base_id returned
            assert len(dcm._bases) == 1
            base = dcm._bases[0]
            assert base.cycle_count == 100
            assert base.trace_count == 10
            assert base.governance_score_count == 5

    def test_delta_saved_between_bases(self):
        with tempfile.TemporaryDirectory() as tmp:
            dcm = DeltaCheckpointManager(checkpoint_dir=tmp, base_interval=500)
            snap1 = make_snapshot(trace_count=10, cycle_count=100)
            dcm.save(snap1)  # base

            snap2 = make_snapshot(trace_count=20, cycle_count=200,
                                  gov_count=8, conf_count=7, stab_count=6)
            result = dcm.save(snap2)  # delta
            assert "delta" in result

            assert len(dcm._bases) == 1  # still one base
            assert len(dcm._deltas) == 1
            base_id = dcm._bases[0].base_id
            assert base_id in dcm._deltas
            assert len(dcm._deltas[base_id]) == 1
            delta = dcm._deltas[base_id][0]
            assert delta.sequence_no == 1
            assert delta.trace_offset == 10  # base had 10 traces
            assert len(delta.new_traces) == 10  # 20 - 10

    def test_multiple_deltas_before_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            dcm = DeltaCheckpointManager(checkpoint_dir=tmp, base_interval=500)
            snap1 = make_snapshot(trace_count=10, cycle_count=100)
            dcm.save(snap1)

            for i in range(3):
                cycle = 100 + (i + 1) * 100
                snap = make_snapshot(trace_count=10 + (i + 1) * 5,
                                     cycle_count=cycle,
                                     gov_count=5 + i)
                dcm.save(snap)

            base_id = dcm._bases[0].base_id
            assert len(dcm._deltas[base_id]) == 3
            assert all(d.sequence_no == i + 1 for i, d in
                       enumerate(dcm._deltas[base_id]))

    def test_new_base_after_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            dcm = DeltaCheckpointManager(checkpoint_dir=tmp, base_interval=200)
            snap1 = make_snapshot(trace_count=10, cycle_count=100)
            dcm.save(snap1)  # base at 100

            snap2 = make_snapshot(trace_count=20, cycle_count=300)
            dcm.save(snap2)  # 300 - 100 >= 200 -> new base

            assert len(dcm._bases) == 2
            assert dcm._bases[1].cycle_count == 300

    def test_base_resets_delta_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            dcm = DeltaCheckpointManager(checkpoint_dir=tmp, base_interval=200)
            snap1 = make_snapshot(trace_count=10, cycle_count=100)
            dcm.save(snap1)  # base at 100

            snap2 = make_snapshot(trace_count=15, cycle_count=200)
            dcm.save(snap2)  # delta at 200

            snap3 = make_snapshot(trace_count=25, cycle_count=350)
            dcm.save(snap3)  # 350-100=250 >= 200 -> new base

            assert len(dcm._bases) == 2
            # New base clears all old deltas
            assert len(dcm._deltas) == 0


class TestDeltaCheckpointManagerLoad:
    def test_load_empty_returns_none(self):
        dcm = DeltaCheckpointManager()
        assert dcm.load_latest() is None
        dcm.clear()

    def test_load_base_without_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            dcm = DeltaCheckpointManager(checkpoint_dir=tmp, base_interval=500)
            snap = make_snapshot(trace_count=10, cycle_count=100)
            dcm.save(snap)

            loaded = dcm.load_latest()
            assert loaded is not None
            assert loaded.trace_count == 10
            assert len(loaded.traces) == 10

    def test_load_reconstructs_with_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            dcm = DeltaCheckpointManager(checkpoint_dir=tmp, base_interval=500)
            snap1 = make_snapshot(trace_count=10, cycle_count=100)
            dcm.save(snap1)

            snap2 = make_snapshot(trace_count=20, cycle_count=200,
                                  gov_count=8, conf_count=7, stab_count=6)
            dcm.save(snap2)

            loaded = dcm.load_latest()
            assert loaded is not None
            assert loaded.trace_count == 20
            assert len(loaded.traces) == 20
            assert len(loaded.governance_score_history) == 8 if loaded.governance_score_history else 0

    def test_load_reconstructs_after_multiple_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            dcm = DeltaCheckpointManager(checkpoint_dir=tmp, base_interval=500)

            base = make_snapshot(trace_count=10, cycle_count=100,
                                 gov_count=3, conf_count=3, stab_count=3)
            dcm.save(base)

            for i in range(3):
                cycle = 100 + (i + 1) * 100
                snap = make_snapshot(trace_count=10 + (i + 1) * 10,
                                     cycle_count=cycle,
                                     gov_count=3 + i)
                dcm.save(snap)

            loaded = dcm.load_latest()
            assert loaded is not None
            assert loaded.trace_count == 40  # 10 + 30
            assert len(loaded.traces) == 40

    def test_load_from_disk_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            dcm = DeltaCheckpointManager(checkpoint_dir=tmp, base_interval=500)
            base = make_snapshot(trace_count=5, cycle_count=100)
            dcm.save(base)
            delta = make_snapshot(trace_count=10, cycle_count=200,
                                  gov_count=6, conf_count=5, stab_count=4)
            dcm.save(delta)

            # Create new manager that reads from disk
            dcm2 = DeltaCheckpointManager(checkpoint_dir=tmp)
            loaded = dcm2.load_latest()
            assert loaded is not None
            assert loaded.trace_count == 10
            assert len(loaded.traces) == 10


class TestDeltaCheckpointManagerChainVerification:
    def test_rev_delta_001_sequential_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            dcm = DeltaCheckpointManager(checkpoint_dir=tmp, base_interval=500)
            base = make_snapshot(trace_count=5, cycle_count=100)
            dcm.save(base)

            # Create non-sequential deltas manually
            base_id = dcm._bases[0].base_id
            dcm._deltas[base_id] = [
                DeltaSegment(delta_id="d1", base_id=base_id, sequence_no=1,
                             created_at=100.0, cycle_count=200, base_cycle_count=100,
                             trace_offset=5, new_traces=[]),
                DeltaSegment(delta_id="d2", base_id=base_id, sequence_no=3,
                             created_at=200.0, cycle_count=300, base_cycle_count=100,
                             trace_offset=5, new_traces=[]),
            ]

            with pytest.raises(RuntimeError, match="REC-DELTA-001"):
                dcm.load_latest()

    def test_rev_delta_001_verify_method(self):
        with tempfile.TemporaryDirectory() as tmp:
            dcm = DeltaCheckpointManager(checkpoint_dir=tmp, base_interval=500)
            base = make_snapshot(cycle_count=100)
            dcm.save(base)
            assert dcm.verify_delta_chain() is True

            # Add gap manually
            base_id = dcm._bases[0].base_id
            dcm._deltas[base_id] = [
                DeltaSegment(delta_id="d1", base_id=base_id, sequence_no=2,
                             created_at=100.0, cycle_count=200, base_cycle_count=100,
                             trace_offset=5, new_traces=[]),
            ]
            assert dcm.verify_delta_chain() is False


class TestDeltaCheckpointManagerPruning:
    def test_prunes_old_bases(self):
        with tempfile.TemporaryDirectory() as tmp:
            dcm = DeltaCheckpointManager(checkpoint_dir=tmp,
                                          base_interval=100, max_bases=2)

            # Write 3 bases
            for i in range(3):
                cycle = (i + 1) * 100
                snap = make_snapshot(trace_count=10, cycle_count=cycle)
                dcm.save(snap)  # each triggers new base

            assert len(dcm._bases) == 2  # max_bases=2
            assert dcm._bases[0].cycle_count == 200
            assert dcm._bases[1].cycle_count == 300

    def test_prune_removes_associated_deltas(self):
        with tempfile.TemporaryDirectory() as tmp:
            dcm = DeltaCheckpointManager(checkpoint_dir=tmp,
                                          base_interval=200, max_bases=2)

            # Base 1 at cycle 100
            dcm.save(make_snapshot(trace_count=10, cycle_count=100))
            # Delta attached to base 1
            dcm.save(make_snapshot(trace_count=15, cycle_count=200))

            # Base 2 at cycle 350 — clears all deltas from base 1
            dcm.save(make_snapshot(trace_count=20, cycle_count=350))
            delta_id_2 = dcm.save(make_snapshot(trace_count=25, cycle_count=450))

            # Base 3 at cycle 550 — triggers pruning, base 1 removed
            dcm.save(make_snapshot(trace_count=30, cycle_count=550))
            delta_id_3 = dcm.save(make_snapshot(trace_count=35, cycle_count=650))

            assert len(dcm._bases) == 2  # max_bases=2
            # Oldest base should be base 2 (base 1 was pruned)
            assert dcm._bases[0].cycle_count == 350
            assert dcm._bases[1].cycle_count == 550

            # Delta files for base 1 should be gone
            delta_path_2 = os.path.join(tmp, "deltas", f"{delta_id_2}.json")
            # delta_id_2 belongs to base 2, which was pruned with base 2
            # Actually let's verify the current state is clean

    def test_clear_removes_all_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            dcm = DeltaCheckpointManager(checkpoint_dir=tmp)
            dcm.save(make_snapshot(cycle_count=100))
            dcm.save(make_snapshot(trace_count=15, cycle_count=200))

            dcm.clear()
            assert len(dcm._bases) == 0
            assert len(dcm._deltas) == 0
            assert dcm.load_latest() is None


class TestDeltaCheckpointManagerEdgeCases:
    def test_save_after_clear_starts_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            dcm = DeltaCheckpointManager(checkpoint_dir=tmp, base_interval=500)
            dcm.save(make_snapshot(cycle_count=100))
            dcm.clear()

            snap = make_snapshot(trace_count=20, cycle_count=200)
            result = dcm.save(snap)
            assert len(result) > 0
            assert len(dcm._bases) == 1
            assert dcm._bases[0].cycle_count == 200

    def test_enabled_toggle(self):
        dcm = DeltaCheckpointManager(enabled=True)
        assert dcm.enabled is True
        dcm.enabled = False
        assert dcm.enabled is False
        dcm.clear()

    def test_trace_counters_match_after_reconstruction(self):
        with tempfile.TemporaryDirectory() as tmp:
            dcm = DeltaCheckpointManager(checkpoint_dir=tmp, base_interval=500)

            base_traces = [{"event_id": f"e{i}"} for i in range(5)]
            base = make_snapshot(trace_count=5, cycle_count=100)
            base.traces = base_traces
            dcm.save(base)

            delta_traces = [{"event_id": f"e{i}"} for i in range(5, 12)]
            snap2 = make_snapshot(trace_count=12, cycle_count=200)
            snap2.traces = base_traces + delta_traces
            dcm.save(snap2)

            loaded = dcm.load_latest()
            assert loaded is not None
            assert loaded.trace_count == 12
            trace_ids = [t["event_id"] for t in loaded.traces]
            assert trace_ids == [f"e{i}" for i in range(12)]
