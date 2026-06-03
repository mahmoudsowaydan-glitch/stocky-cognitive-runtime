"""Diagnostic: WAL corruption — tests PersistenceGuard detection of mutated checkpoints."""

from cognitive_runtime.recovery.persistence_guard import PersistenceGuard
from cognitive_runtime.recovery.runtime_snapshot import RuntimeSnapshot


def test_corrupted_traces_detected(checkpoint_manager):
    import json, os
    from tests.chaos.conftest import make_traces
    traces = make_traces(3)
    loop = type("Loop", (), {"_traces": traces})()
    snap = RuntimeSnapshot.capture(loop, snapshot_id="cp_test")
    assert snap.trace_count == 3
    checkpoint_manager.save(snap)
    # Directly corrupt traces without touching trace_count
    path = os.path.join(checkpoint_manager._dir, "cp_cp_test.json")
    with open(path) as f:
        data = json.load(f)
    data["traces"] = []
    with open(path, "w") as f:
        json.dump(data, f)
    loaded = checkpoint_manager.load_latest()
    guard = PersistenceGuard()
    result = guard.validate_snapshot(loaded)
    assert not result.valid


def test_schema_version_mismatch_detected(checkpoint_manager, wal_mutator):
    snap = RuntimeSnapshot.capture(object(), snapshot_id="cp_schema")
    checkpoint_manager.save(snap)
    wal_mutator.corrupt_schema_version("cp_schema")
    loaded = checkpoint_manager.load_latest()
    guard = PersistenceGuard()
    result = guard.validate_snapshot(loaded)
    assert not result.valid
    assert "schema" in result.details.lower() or "version" in result.details.lower()


def test_truncated_file_returns_none(checkpoint_manager, wal_mutator):
    snap = RuntimeSnapshot.capture(object(), snapshot_id="cp_trunc")
    checkpoint_manager.save(snap)
    wal_mutator.truncate_file("cp_trunc")
    loaded = checkpoint_manager.load_latest()
    assert loaded is None


def test_nullified_snapshot_id_detected(checkpoint_manager, wal_mutator):
    snap = RuntimeSnapshot.capture(object(), snapshot_id="cp_noid")
    checkpoint_manager.save(snap)
    wal_mutator.nullify_required_field("cp_noid", "snapshot_id")
    loaded = checkpoint_manager.load_latest()
    guard = PersistenceGuard()
    result = guard.validate_snapshot(loaded)
    assert not result.valid
    assert "snapshot_id" in result.details.lower() or "missing" in result.details.lower()


def test_mutated_trace_fields_detected(checkpoint_manager, wal_mutator):
    from tests.chaos.conftest import make_traces
    traces = make_traces(3)
    loop = type("Loop", (), {"_traces": traces})()
    snap = RuntimeSnapshot.capture(loop, snapshot_id="cp_mut")
    checkpoint_manager.save(snap)
    wal_mutator.mutate_trace_fields("cp_mut")
    loaded = checkpoint_manager.load_latest()
    if loaded and loaded.traces:
        corrupted = any(
            t.get("final_status") in ("UNKNOWN", "CORRUPTED", None)
            for t in loaded.traces if isinstance(t, dict)
        )
        assert corrupted, "Expected at least one corrupted trace"
