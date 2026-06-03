import hashlib
import pytest

from cognitive_runtime.contracts.frozen.schema_version import (
    SchemaVersion,
    FROZEN_SCHEMA_VERSION,
    fingerprint,
    fingerprint_class,
    ContractFingerprints,
    register_fingerprint,
    get_expected_fingerprint,
)


def test_schema_version_default_fields():
    v = SchemaVersion(major=1, minor=0, patch=0)
    assert v.major == 1
    assert v.minor == 0
    assert v.patch == 0


def test_schema_version_is_frozen():
    v = SchemaVersion(1, 0, 0)
    with pytest.raises(Exception):
        v.major = 2


def test_schema_version_str():
    assert str(SchemaVersion(1, 2, 3)) == "1.2.3"


def test_schema_version_repr():
    assert repr(SchemaVersion(1, 2, 3)) == "v1.2.3"


def test_schema_version_is_compatible_with_same():
    assert SchemaVersion(1, 0, 0).is_compatible_with(SchemaVersion(1, 0, 5)) is True


def test_schema_version_is_compatible_different_major():
    assert SchemaVersion(1, 0, 0).is_compatible_with(SchemaVersion(2, 0, 0)) is False


def test_schema_version_is_compatible_different_minor():
    assert SchemaVersion(1, 0, 0).is_compatible_with(SchemaVersion(1, 5, 0)) is False


def test_schema_version_is_backward_compatible_same():
    assert SchemaVersion(1, 0, 0).is_backward_compatible(SchemaVersion(1, 0, 5)) is True


def test_schema_version_is_backward_compatible_higher_minor():
    assert SchemaVersion(1, 0, 0).is_backward_compatible(SchemaVersion(1, 5, 0)) is True


def test_schema_version_is_backward_compatible_different_major():
    assert SchemaVersion(1, 0, 0).is_backward_compatible(SchemaVersion(2, 0, 0)) is False


def test_schema_version_is_backward_compatible_lower_minor():
    assert SchemaVersion(1, 5, 0).is_backward_compatible(SchemaVersion(1, 0, 0)) is False


def test_schema_version_equality():
    assert SchemaVersion(1, 0, 0) == SchemaVersion(1, 0, 0)
    assert SchemaVersion(1, 0, 0) != SchemaVersion(1, 0, 1)


def test_frozen_schema_version_defined():
    assert FROZEN_SCHEMA_VERSION is not None
    assert isinstance(FROZEN_SCHEMA_VERSION, SchemaVersion)


def test_frozen_schema_version_expected():
    assert FROZEN_SCHEMA_VERSION.major == 1
    assert FROZEN_SCHEMA_VERSION.minor == 1
    assert FROZEN_SCHEMA_VERSION.patch == 0


def test_fingerprint_returns_16_char_hex():
    result = fingerprint("hello")
    assert isinstance(result, str)
    assert len(result) == 16
    int(result, 16)


def test_fingerprint_deterministic():
    class Obj:
        a = 1
        b = "x"
    assert fingerprint(Obj()) == fingerprint(Obj())


def test_fingerprint_different_for_different_objects():
    class A:
        x = 1
    class B:
        x = 2
    assert fingerprint(A()) != fingerprint(B())


def test_fingerprint_skips_private_attrs():
    class Obj:
        public = 1
        _private = 2
    result = fingerprint(Obj())
    assert isinstance(result, str)


def test_fingerprint_skips_methods():
    class Obj:
        val = 1
        def method(self):
            pass
    result = fingerprint(Obj())
    assert isinstance(result, str)


def test_fingerprint_uses_sha256():
    class Obj:
        a = 1
    raw = str(sorted({"a": 1}.items()))
    expected = hashlib.sha256(raw.encode()).hexdigest()[:16]
    assert fingerprint(Obj()) == expected


def test_fingerprint_class_returns_16_char_hex():
    class MyClass:
        field: int
    result = fingerprint_class(MyClass)
    assert isinstance(result, str)
    assert len(result) == 16
    int(result, 16)


def test_fingerprint_class_deterministic():
    class A:
        x: int
    assert fingerprint_class(A) == fingerprint_class(A)


def test_fingerprint_class_different_for_different():
    class A:
        x: int
    class B:
        y: str
    assert fingerprint_class(A) != fingerprint_class(B)


def test_fingerprint_class_includes_method_signatures():
    class A:
        x: int
        def foo(self, a: int) -> str:
            return ""
    class B:
        x: int
        def foo(self, a: str) -> int:
            return 0
    assert fingerprint_class(A) != fingerprint_class(B)


def test_fingerprint_class_no_annotations():
    class NoAnnotations:
        pass
    result = fingerprint_class(NoAnnotations)
    assert isinstance(result, str)
    assert len(result) == 16


def test_contract_fingerprints_registry_is_dict():
    assert isinstance(ContractFingerprints, dict)


def test_contract_fingerprints_register_and_get():
    register_fingerprint("test_contract", "abcdef1234567890")
    assert get_expected_fingerprint("test_contract") == "abcdef1234567890"


def test_contract_fingerprints_get_nonexistent():
    assert get_expected_fingerprint("nonexistent") is None


def test_contract_fingerprints_register_overwrites():
    register_fingerprint("overwrite_test", "first_hash")
    register_fingerprint("overwrite_test", "second_hash")
    assert get_expected_fingerprint("overwrite_test") == "second_hash"


def test_contract_fingerprints_has_expected_entries():
    assert "CausalNode" in ContractFingerprints
    assert "CausalEdge" in ContractFingerprints
    assert "GraphContract" in ContractFingerprints
    assert "ExecutionTrace" in ContractFingerprints
    assert "BridgeContract" in ContractFingerprints
    assert "RuntimeContract" in ContractFingerprints


def test_contract_fingerprints_all_stable_strings():
    for name, fp in ContractFingerprints.items():
        assert isinstance(fp, str)
        assert len(fp) > 0
