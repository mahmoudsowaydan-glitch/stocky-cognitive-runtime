"""Tests for cognitive_runtime/distributed_schema/schema_sync_registry.py."""

import pytest

from cognitive_runtime.distributed_schema import SchemaHandshake, SchemaSyncRegistry


@pytest.fixture
def registry():
    r = SchemaSyncRegistry()
    r.register_node(SchemaHandshake(node_id="n1", schema_version="1.1.0"))
    r.register_node(SchemaHandshake(node_id="n2", schema_version="1.0.0"))
    r.register_node(SchemaHandshake(node_id="n3", schema_version="1.0.0"))
    return r


# ── register / get ──


def test_register_node():
    r = SchemaSyncRegistry()
    r.register_node(SchemaHandshake(node_id="n1", schema_version="1.1.0"))
    assert r.node_count == 1


def test_get_node_schema(registry):
    h = registry.get_node_schema("n1")
    assert h is not None
    assert h.schema_version == "1.1.0"


def test_get_node_schema_unknown(registry):
    assert registry.get_node_schema("unknown") is None


def test_node_ids(registry):
    ids = registry.node_ids
    assert "n1" in ids
    assert len(ids) == 3


# ── update ──


def test_update_node_schema(registry):
    assert registry.update_node_schema("n1", "1.0.0") is True
    h = registry.get_node_schema("n1")
    assert h is not None
    assert h.schema_version == "1.0.0"


def test_update_unknown_node(registry):
    assert registry.update_node_schema("unknown", "1.1.0") is False


# ── detect_cluster_incompatibility (DSYNC-003) ──


def test_detect_incompatible_all_same(registry):
    bad = registry.detect_cluster_incompatibility("1.1.0")
    assert "n2" in bad or "n3" in bad
    assert "n1" not in bad


def test_detect_incompatible_unknown_version(registry):
    bad = registry.detect_cluster_incompatibility("99.0.0")
    assert len(bad) == 3


def test_detect_incompatible_with_supported():
    r = SchemaSyncRegistry()
    r.register_node(SchemaHandshake(
        node_id="n1", schema_version="1.1.0",
        supported_versions=["1.0.0", "1.1.0"],
    ))
    r.register_node(SchemaHandshake(
        node_id="n2", schema_version="1.0.0",
        supported_versions=["1.0.0"],
    ))
    bad = r.detect_cluster_incompatibility("1.1.0")
    assert "n2" in bad


# ── get_versions_in_cluster ──


def test_versions_in_cluster(registry):
    versions = registry.get_versions_in_cluster()
    assert "1.1.0" in versions
    assert "1.0.0" in versions
    assert len(versions["1.0.0"]) == 2


def test_empty_registry():
    r = SchemaSyncRegistry()
    assert r.node_count == 0
    assert r.get_versions_in_cluster() == {}
