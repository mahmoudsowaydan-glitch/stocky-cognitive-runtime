"""Tests for cognitive_runtime/schema_evolution/evolution_node.py."""

from cognitive_runtime.schema_evolution.evolution_node import SchemaVersionNode


def test_minimal_node():
    node = SchemaVersionNode(version="1.0.0")
    assert node.version == "1.0.0"
    assert node.parent_versions == ()
    assert node.is_frozen is True
    assert node.breaking_changes == ()
    assert node.compatibility_hash == ""


def test_node_with_parent():
    node = SchemaVersionNode(version="1.1.0", parent_versions=("1.0.0",))
    assert node.parent_versions == ("1.0.0",)


def test_node_frozen_false():
    node = SchemaVersionNode(version="2.0.0-dev", is_frozen=False)
    assert node.is_frozen is False


def test_node_breaking_changes():
    node = SchemaVersionNode(
        version="2.0.0",
        parent_versions=("1.1.0",),
        breaking_changes=("removed field X", "changed type Y"),
    )
    assert len(node.breaking_changes) == 2


def test_node_immutable():
    node = SchemaVersionNode(version="1.0.0")
    import dataclasses
    assert dataclasses.is_dataclass(node)
    assert node.is_frozen is True
