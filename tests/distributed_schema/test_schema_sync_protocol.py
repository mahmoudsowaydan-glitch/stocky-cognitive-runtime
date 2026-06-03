"""Tests for cognitive_runtime/distributed_schema/schema_sync_protocol.py."""

from cognitive_runtime.distributed_schema import SchemaHandshake, SchemaSyncResponse


def test_handshake_minimal():
    h = SchemaHandshake(node_id="node_a", schema_version="1.0.0")
    assert h.node_id == "node_a"
    assert h.schema_version == "1.0.0"
    assert h.supported_versions == []


def test_handshake_with_supported():
    h = SchemaHandshake(
        node_id="node_b", schema_version="1.1.0",
        supported_versions=["1.0.0", "1.1.0"],
    )
    assert "1.0.0" in h.supported_versions


def test_response_accept():
    r = SchemaSyncResponse(status="ACCEPT", target_version="1.1.0")
    assert r.status == "ACCEPT"
    assert r.migration_required is False


def test_response_migrate():
    r = SchemaSyncResponse(
        status="MIGRATE", target_version="1.1.0",
        migration_required=True, reason="migration_path_available",
    )
    assert r.migration_required is True
    assert r.reason == "migration_path_available"


def test_response_reject():
    r = SchemaSyncResponse(
        status="REJECT", reason="NO_COMPATIBLE_SCHEMA_PATH",
    )
    assert r.status == "REJECT"
    assert r.target_version is None


def test_handshake_immutable():
    import dataclasses
    assert dataclasses.is_dataclass(SchemaHandshake)


def test_response_immutable():
    import dataclasses
    assert dataclasses.is_dataclass(SchemaSyncResponse)
