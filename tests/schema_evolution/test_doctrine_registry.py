"""Tests for cognitive_runtime/schema_evolution/doctrine_registry.py."""

from cognitive_runtime.schema_evolution.doctrine_registry import DoctrineRegistry
from cognitive_runtime.contracts.frozen.schema_version import FROZEN_SCHEMA_VERSION


def test_registry_bootstrap():
    reg = DoctrineRegistry()
    assert reg.graph.root_version == "1.0.0"
    assert reg.graph.node_count >= 2
    assert reg.graph.has_node("1.0.0")
    assert reg.graph.has_node("1.1.0")


def test_current_version_matches_frozen():
    reg = DoctrineRegistry()
    assert reg.current_version == str(FROZEN_SCHEMA_VERSION)


def test_allowed_versions_includes_current():
    reg = DoctrineRegistry()
    assert reg.current_version in reg.allowed_versions


def test_allowed_versions_limit():
    reg = DoctrineRegistry()
    assert len(reg.allowed_versions) <= 3


def test_allowed_versions_ordered():
    reg = DoctrineRegistry()
    versions = reg.allowed_versions
    for i in range(len(versions) - 1):
        v_parsed = tuple(int(x) for x in versions[i].split("."))
        next_parsed = tuple(int(x) for x in versions[i + 1].split("."))
        assert v_parsed >= next_parsed


def test_is_allowed_current():
    reg = DoctrineRegistry()
    assert reg.is_allowed(reg.current_version) is True


def test_is_allowed_unknown():
    reg = DoctrineRegistry()
    assert reg.is_allowed("99.0.0") is False


def test_is_supported_known():
    reg = DoctrineRegistry()
    assert reg.is_supported("1.0.0") is True
    assert reg.is_supported("1.1.0") is True


def test_is_supported_unknown():
    reg = DoctrineRegistry()
    assert reg.is_supported("2.0.0") is False


def test_frozen_versions():
    reg = DoctrineRegistry()
    frozen = reg.frozen_versions
    assert "1.0.0" in frozen
    assert "1.1.0" in frozen
    assert all(reg.graph.get_node(v).is_frozen for v in frozen)
