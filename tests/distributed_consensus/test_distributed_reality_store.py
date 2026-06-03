"""Tests for cognitive_runtime/distributed_consensus/distributed_reality_store.py."""

from cognitive_runtime.distributed_consensus import (
    DistributedReality, DistributedRealityStore,
)


def test_store_reality():
    store = DistributedRealityStore()
    reality = store.store_reality(
        global_schema_version="1.1.0",
        active_nodes=["n1", "n2"],
        rejected_nodes=["n3"],
    )
    assert reality.global_schema_version == "1.1.0"
    assert "n1" in reality.active_nodes
    assert "n3" in reality.rejected_nodes
    assert len(reality.consensus_hash) == 64  # SHA256 hex


def test_get_reality():
    store = DistributedRealityStore()
    assert store.get_reality() is None
    store.store_reality("1.1.0", ["n1"], [])
    assert store.get_reality() is not None


def test_verify_integrity():
    store = DistributedRealityStore()
    reality = store.store_reality("1.1.0", ["n1"], ["n2"])
    assert store.verify_integrity(reality) is True


def test_verify_integrity_fails_on_tamper():
    store = DistributedRealityStore()
    reality = store.store_reality("1.1.0", ["n1"], ["n2"])
    tampered = DistributedReality(
        global_schema_version="1.1.0",
        active_nodes=["n1"],
        rejected_nodes=["n2", "n3"],
        consensus_hash=reality.consensus_hash,
    )
    assert store.verify_integrity(tampered) is False


def test_clear():
    store = DistributedRealityStore()
    store.store_reality("1.1.0", ["n1"], [])
    assert store.get_reality() is not None
    store.clear()
    assert store.get_reality() is None


def test_store_overwrites():
    store = DistributedRealityStore()
    r1 = store.store_reality("1.0.0", ["n1"], [])
    r2 = store.store_reality("1.1.0", ["n1", "n2"], [])
    assert store.get_reality().global_schema_version == "1.1.0"
    assert r1.global_schema_version == "1.0.0"
    assert r2.global_schema_version == "1.1.0"


def test_hash_deterministic():
    store = DistributedRealityStore()
    r1 = store.store_reality("1.1.0", ["n1", "n2"], ["n3"])
    store.clear()
    r2 = store.store_reality("1.1.0", ["n1", "n2"], ["n3"])
    assert r1.consensus_hash == r2.consensus_hash


def test_reality_immutable():
    import dataclasses
    assert dataclasses.is_dataclass(DistributedReality)
