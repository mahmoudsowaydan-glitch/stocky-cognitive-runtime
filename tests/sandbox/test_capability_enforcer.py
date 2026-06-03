import pytest

from cognitive_runtime.sandbox.capability_enforcer import (
    CapabilityEnforcer,
    EnforcementResult,
    EnforcementVerdict,
)
from cognitive_runtime.contracts.execution_contract import Capability


class TestEnforcementVerdict:
    def test_constants(self):
        assert EnforcementVerdict.ALLOW == "ALLOW"
        assert EnforcementVerdict.BLOCK == "BLOCK"


class TestEnforcementResult:
    def test_defaults(self):
        result = EnforcementResult(verdict="ALLOW")
        assert result.verdict == "ALLOW"
        assert result.reason == ""
        assert result.capability == ""

    def test_full_construction(self):
        result = EnforcementResult(
            verdict="BLOCK", reason="unknown_capability: foo", capability="foo",
        )
        assert result.verdict == "BLOCK"
        assert result.reason == "unknown_capability: foo"
        assert result.capability == "foo"


class TestCapabilityEnforcer:
    def test_known_capability_returns_allow(self):
        enforcer = CapabilityEnforcer()
        result = enforcer.check([Capability.FILESYSTEM_READ])
        assert result.verdict == EnforcementVerdict.ALLOW
        assert result.reason == "all_capabilities_allowed"

    def test_multiple_known_capabilities_returns_allow(self):
        enforcer = CapabilityEnforcer()
        result = enforcer.check([
            Capability.FILESYSTEM_READ,
            Capability.NETWORK_HTTP,
            Capability.AUDIT_READ,
        ])
        assert result.verdict == EnforcementVerdict.ALLOW

    def test_unknown_capability_returns_block(self):
        enforcer = CapabilityEnforcer()
        result = enforcer.check(["unknown.cap"])
        assert result.verdict == EnforcementVerdict.BLOCK
        assert "unknown_capability" in result.reason
        assert result.capability == "unknown.cap"

    def test_unknown_capability_among_known_returns_block(self):
        enforcer = CapabilityEnforcer()
        result = enforcer.check([Capability.FILESYSTEM_READ, "unknown.cap"])
        assert result.verdict == EnforcementVerdict.BLOCK
        assert result.capability == "unknown.cap"

    def test_restrict_adds_to_restricted_set(self):
        enforcer = CapabilityEnforcer()
        enforcer.restrict(Capability.NETWORK_HTTP)
        result = enforcer.check([Capability.NETWORK_HTTP])
        assert result.verdict == EnforcementVerdict.BLOCK
        assert "restricted_capability" in result.reason

    def test_restricted_capability_still_allows_others(self):
        enforcer = CapabilityEnforcer()
        enforcer.restrict(Capability.NETWORK_HTTP)
        result = enforcer.check([Capability.FILESYSTEM_READ])
        assert result.verdict == EnforcementVerdict.ALLOW

    def test_allow_removes_from_restricted(self):
        enforcer = CapabilityEnforcer()
        enforcer.restrict(Capability.NETWORK_HTTP)
        assert Capability.NETWORK_HTTP.value in enforcer.restricted_capabilities
        enforcer.allow(Capability.NETWORK_HTTP)
        result = enforcer.check([Capability.NETWORK_HTTP])
        assert result.verdict == EnforcementVerdict.ALLOW

    def test_allow_nonexistent_restricted_does_not_error(self):
        enforcer = CapabilityEnforcer()
        enforcer.allow(Capability.NETWORK_HTTP)
        result = enforcer.check([Capability.NETWORK_HTTP])
        assert result.verdict == EnforcementVerdict.ALLOW

    def test_allowed_capabilities_property(self):
        enforcer = CapabilityEnforcer()
        allowed = enforcer.allowed_capabilities
        assert Capability.FILESYSTEM_READ.value in allowed
        assert Capability.NETWORK_HTTP.value in allowed

    def test_allowed_capabilities_excludes_restricted(self):
        enforcer = CapabilityEnforcer()
        enforcer.restrict(Capability.NETWORK_HTTP)
        allowed = enforcer.allowed_capabilities
        assert Capability.NETWORK_HTTP.value not in allowed
        assert Capability.FILESYSTEM_READ.value in allowed

    def test_restricted_capabilities_property(self):
        enforcer = CapabilityEnforcer()
        assert enforcer.restricted_capabilities == []
        enforcer.restrict(Capability.PROCESS_EXECUTE)
        assert Capability.PROCESS_EXECUTE.value in enforcer.restricted_capabilities

    def test_restricted_capabilities_sorted(self):
        enforcer = CapabilityEnforcer()
        enforcer.restrict(Capability.AUDIT_READ)
        enforcer.restrict(Capability.FILESYSTEM_WRITE)
        assert enforcer.restricted_capabilities == sorted([
            Capability.AUDIT_READ.value,
            Capability.FILESYSTEM_WRITE.value,
        ])

    def test_allowed_capabilities_sorted(self):
        enforcer = CapabilityEnforcer()
        allowed = enforcer.allowed_capabilities
        assert allowed == sorted(allowed)

    def test_case_sensitivity(self):
        enforcer = CapabilityEnforcer()
        upper_val = Capability.FILESYSTEM_READ.value.upper()
        result = enforcer.check([upper_val])
        assert result.verdict == EnforcementVerdict.BLOCK

    def test_empty_capability_list_returns_allow(self):
        enforcer = CapabilityEnforcer()
        result = enforcer.check([])
        assert result.verdict == EnforcementVerdict.ALLOW

    def test_all_known_capabilities_allowed_by_default(self):
        enforcer = CapabilityEnforcer()
        for cap in Capability:
            result = enforcer.check([cap])
            assert result.verdict == EnforcementVerdict.ALLOW, f"failed for {cap.value}"
