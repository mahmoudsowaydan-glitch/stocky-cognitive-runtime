"""Tests for cognitive_runtime/recovery/checkpoint_manager.py."""

import json
import os

import pytest

from cognitive_runtime.recovery.checkpoint_manager import CheckpointManager, CheckpointMetadata
from cognitive_runtime.recovery.runtime_snapshot import RuntimeSnapshot
from cognitive_runtime.contracts.frozen.schema_version import FROZEN_SCHEMA_VERSION


# ── Helpers ──


def make_snapshot(snapshot_id="cp_1", trace_count=0):
    traces = [] if trace_count == 0 else [
        {"event_id": f"e{i}", "final_status": "P4_ALLOW"}
        for i in range(trace_count)
    ]
    return RuntimeSnapshot(
        snapshot_id=snapshot_id,
        created_at=1000.0,
        runtime_state_snapshot={"status": "stopped"},
        trace_count=trace_count,
        traces=traces,
    )


# ── Init ──


def test_default_checkpoint_dir():
    cm = CheckpointManager()
    assert cm._dir.endswith("checkpoints")
    assert cm._max == 10


def test_enabled_default():
    cm = CheckpointManager()
    assert cm._enabled is True
    assert cm.enabled is True


def test_custom_dir(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    assert cm._dir == tmp_dir


def test_custom_max(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir, max_checkpoints=3)
    assert cm._max == 3


def test_disabled(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir, enabled=False)
    assert cm.enabled is False


def test_enabled_setter(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir, enabled=True)
    cm.enabled = False
    assert cm.enabled is False


def test_creates_directory(tmp_dir):
    path = os.path.join(tmp_dir, "my_cps")
    cm = CheckpointManager(checkpoint_dir=path)
    assert os.path.isdir(path)


def test_initial_metadata_empty(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    assert cm.metadata == []
    assert cm.latest is None
    assert cm.checkpoint_count == 0


# ── Save ──


def test_save_creates_json_file(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    snap = make_snapshot("cp_100")
    meta = cm.save(snap, health_status="healthy")
    assert meta is not None
    assert os.path.exists(meta.file_path)
    with open(meta.file_path) as f:
        data = json.load(f)
    assert data["snapshot_id"] == "cp_100"


def test_save_metadata_fields(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    snap = make_snapshot("cp_abc")
    meta = cm.save(snap, health_status="healthy", governance_status="stable")
    assert meta.checkpoint_id == "cp_abc"
    assert meta.created_at == 1000.0
    assert meta.health_status == "healthy"
    assert meta.governance_status == "stable"
    assert meta.file_path == os.path.join(tmp_dir, "cp_cp_abc.json")


def test_save_metadata_trace_count(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    snap = make_snapshot("cp_tr", trace_count=5)
    meta = cm.save(snap)
    assert meta.trace_count == 5


def test_save_disabled_returns_none(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir, enabled=False)
    assert cm.save(make_snapshot("cp_x")) is None


def test_save_increments_count(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    cm.save(make_snapshot("cp_1"))
    assert cm.checkpoint_count == 1
    cm.save(make_snapshot("cp_2"))
    assert cm.checkpoint_count == 2


def test_latest_returns_most_recent(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    cm.save(make_snapshot("cp_a"))
    cm.save(make_snapshot("cp_b"))
    assert cm.latest.checkpoint_id == "cp_b"


# ── Load ──


def test_load_latest_returns_snapshot(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    snap = make_snapshot("cp_load", trace_count=3)
    cm.save(snap)
    loaded = cm.load_latest()
    assert loaded is not None
    assert loaded.snapshot_id == "cp_load"
    assert loaded.trace_count == 3


def test_load_latest_none_when_empty(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    assert cm.load_latest() is None


def test_load_id(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    cm.save(make_snapshot("cp_a"))
    cm.save(make_snapshot("cp_b"))
    loaded = cm.load_id("cp_a")
    assert loaded is not None
    assert loaded.snapshot_id == "cp_a"


def test_load_id_missing(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    cm.save(make_snapshot("cp_1"))
    assert cm.load_id("cp_nonexistent") is None


def test_load_id_restores_traces(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    cm.save(make_snapshot("cp_restore", trace_count=7))
    loaded = cm.load_latest()
    assert len(loaded.traces) == 7
    assert loaded.traces[0]["event_id"] == "e0"
    assert loaded.traces[-1]["event_id"] == "e6"


def test_load_all_traces(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    cm.save(make_snapshot("cp_a", trace_count=2))
    cm.save(make_snapshot("cp_b", trace_count=3))
    all_traces = cm.load_all_traces()
    assert len(all_traces) == 5


def test_load_latest_returns_most_recent_after_multiple(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    cm.save(make_snapshot("cp_old", trace_count=1))
    cm.save(make_snapshot("cp_new", trace_count=5))
    loaded = cm.load_latest()
    assert loaded.snapshot_id == "cp_new"
    assert loaded.trace_count == 5


# ── Pruning ──


def test_prune_old_checkpoints(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir, max_checkpoints=3)
    for i in range(5):
        cm.save(make_snapshot(f"cp_{i}"))
    assert cm.checkpoint_count == 3
    assert cm.metadata[0].checkpoint_id == "cp_2"
    assert cm.metadata[-1].checkpoint_id == "cp_4"


def test_prune_removes_files(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir, max_checkpoints=2)
    paths = []
    for i in range(4):
        meta = cm.save(make_snapshot(f"cp_{i}"))
        paths.append(meta.file_path)
    assert not os.path.exists(paths[0])
    assert not os.path.exists(paths[1])
    assert os.path.exists(paths[2])
    assert os.path.exists(paths[3])


def test_no_prune_below_max(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir, max_checkpoints=5)
    for i in range(3):
        cm.save(make_snapshot(f"cp_{i}"))
    assert cm.checkpoint_count == 3


# ── Clear ──


def test_clear_removes_metadata(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    cm.save(make_snapshot("cp_a"))
    cm.save(make_snapshot("cp_b"))
    cm.clear()
    assert cm.checkpoint_count == 0
    assert cm.metadata == []
    assert cm.latest is None


def test_clear_removes_files(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    meta1 = cm.save(make_snapshot("cp_x"))
    meta2 = cm.save(make_snapshot("cp_y"))
    cm.clear()
    assert not os.path.exists(meta1.file_path)
    assert not os.path.exists(meta2.file_path)


def test_clear_removes_metadata_file(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    cm.save(make_snapshot("cp_z"))
    meta_path = os.path.join(tmp_dir, "metadata.json")
    assert os.path.exists(meta_path)
    cm.clear()
    assert not os.path.exists(meta_path)


def test_clear_empty(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    cm.clear()
    assert cm.checkpoint_count == 0


# ── List ──


def test_list_checkpoints(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    cm.save(make_snapshot("cp_1", trace_count=2))
    cm.save(make_snapshot("cp_2", trace_count=4))
    entries = cm.list_checkpoints()
    assert len(entries) == 2
    assert entries[0]["checkpoint_id"] == "cp_1"
    assert entries[1]["checkpoint_id"] == "cp_2"


def test_list_empty(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    assert cm.list_checkpoints() == []


# ── CheckpointMetadata ──


def test_metadata_to_dict():
    meta = CheckpointMetadata(
        checkpoint_id="cp_1", created_at=1.0, cycle_count=5,
        trace_count=10, schema_version=str(FROZEN_SCHEMA_VERSION),
        file_path="/tmp/cp_1.json",
        health_status="healthy", governance_status="stable",
        recovery_mode=False,
    )
    d = meta.to_dict()
    assert d["checkpoint_id"] == "cp_1"
    assert d["cycle_count"] == 5
    assert d["health_status"] == "healthy"


def test_metadata_from_dict():
    d = {
        "checkpoint_id": "cp_x", "created_at": 2.0, "cycle_count": 3,
        "trace_count": 7, "schema_version": str(FROZEN_SCHEMA_VERSION),
        "file_path": "/tmp/cp_x.json", "health_status": "",
        "governance_status": "", "recovery_mode": False,
    }
    meta = CheckpointMetadata.from_dict(d)
    assert meta.checkpoint_id == "cp_x"
    assert meta.trace_count == 7


def test_metadata_defaults():
    meta = CheckpointMetadata(
        checkpoint_id="cp_1", created_at=1.0, cycle_count=0,
        trace_count=0, schema_version=str(FROZEN_SCHEMA_VERSION), file_path="/tmp/x",
    )
    assert meta.health_status == ""
    assert meta.governance_status == ""
    assert meta.recovery_mode is False
