import pytest

from cognitive_runtime.contracts.execution_contract import (
    Capability, ExecutionProposal, PolicyDecision,
)
from cognitive_runtime.sandbox.capability_enforcer import (
    CapabilityEnforcer, EnforcementVerdict,
)
from cognitive_runtime.sandbox.preflight_analyzer import PreflightAnalyzer
from cognitive_runtime.sandbox.resource_monitor import (
    ResourceMonitor, ResourceLimits,
)
from cognitive_runtime.sandbox.execution_cell import ExecutionCell


pytestmark = pytest.mark.stress


# ── (a) Capability exhaustion ──

def test_all_8_known_capabilities_allowed():
    enforcer = CapabilityEnforcer()
    for cap in Capability:
        result = enforcer.check([cap])
        assert result.verdict == EnforcementVerdict.ALLOW, (
            f"known capability {cap.value} was blocked"
        )


def test_each_capability_returns_allow():
    enforcer = CapabilityEnforcer()
    results = [enforcer.check([cap]).verdict for cap in Capability]
    assert all(v == EnforcementVerdict.ALLOW for v in results)
    assert len(results) == 8


# ── (b) Unknown capability injection ──

def test_20_unknown_capabilities_all_blocked():
    enforcer = CapabilityEnforcer()
    unknowns = [
        "system.shutdown", "network.dns.tunnel", "kernel.module_load",
        "memory.direct_physical_write", "bios.flash", "pci.config_write",
        "msr.write", "smbus.read", "tpm.nv_write", "sgx.enclave_load",
        "acpi.override", "efi.boot_var_write", "cpu.microcode_load",
        "io.port_write", "dma.buffer_write", "interrupt.redirect",
        "hypercall.vmcall", "vga.rom_write", "pcie.aer_inject",
        "memory.cache_snoop",
    ]
    assert len(unknowns) == 20

    for cap_str in unknowns:
        result = enforcer.check([cap_str])
        assert result.verdict == EnforcementVerdict.BLOCK, (
            f"unknown capability '{cap_str}' was allowed"
        )


def test_mixed_known_unknown_blocked():
    enforcer = CapabilityEnforcer()
    result = enforcer.check([Capability.FILESYSTEM_READ, "unknown.xyz"])
    assert result.verdict == EnforcementVerdict.BLOCK
    assert "unknown" in result.reason


# ── (c) All preflight rules ──

def test_rule_missing_action_blocked():
    analyzer = PreflightAnalyzer()
    proposal = ExecutionProposal(
        proposal_id="p1", session_id="s1", event_id="e1",
        action="", target="/tmp/f",
        params={}, required_capabilities=[Capability.FILESYSTEM_READ],
        confidence=0.8, risk_score=0.1, metadata={},
    )
    result = analyzer.analyze(proposal)
    assert result.valid is False
    assert "proposal_has_action" in result.triggered_rules


def test_rule_missing_event_id_blocked():
    analyzer = PreflightAnalyzer()
    proposal = ExecutionProposal(
        proposal_id="p2", session_id="s1", event_id="",
        action="read", target="/tmp/f",
        params={}, required_capabilities=[Capability.FILESYSTEM_READ],
        confidence=0.8, risk_score=0.1, metadata={},
    )
    result = analyzer.analyze(proposal)
    assert result.valid is False
    assert "proposal_has_event_id" in result.triggered_rules


def test_rule_missing_session_id_blocked():
    analyzer = PreflightAnalyzer()
    proposal = ExecutionProposal(
        proposal_id="p3", session_id="", event_id="e1",
        action="read", target="/tmp/f",
        params={}, required_capabilities=[Capability.FILESYSTEM_READ],
        confidence=0.8, risk_score=0.1, metadata={},
    )
    result = analyzer.analyze(proposal)
    assert result.valid is False
    assert "proposal_has_session_id" in result.triggered_rules


def test_rule_confidence_out_of_range_blocked():
    analyzer = PreflightAnalyzer()
    proposal = ExecutionProposal(
        proposal_id="p4", session_id="s1", event_id="e1",
        action="read", target="/tmp/f",
        params={}, required_capabilities=[Capability.FILESYSTEM_READ],
        confidence=1.5, risk_score=0.1, metadata={},
    )
    result = analyzer.analyze(proposal)
    assert result.valid is False
    assert "confidence_in_range" in result.triggered_rules


def test_rule_risk_score_out_of_range_blocked():
    analyzer = PreflightAnalyzer()
    proposal = ExecutionProposal(
        proposal_id="p5", session_id="s1", event_id="e1",
        action="read", target="/tmp/f",
        params={}, required_capabilities=[Capability.FILESYSTEM_READ],
        confidence=0.8, risk_score=-0.1, metadata={},
    )
    result = analyzer.analyze(proposal)
    assert result.valid is False
    assert "risk_score_in_range" in result.triggered_rules


def test_rule_empty_capabilities_blocked():
    analyzer = PreflightAnalyzer()
    proposal = ExecutionProposal(
        proposal_id="p6", session_id="s1", event_id="e1",
        action="read", target="/tmp/f",
        params={}, required_capabilities=[],
        confidence=0.8, risk_score=0.1, metadata={},
    )
    result = analyzer.analyze(proposal)
    assert result.valid is False
    assert "capabilities_not_empty" in result.triggered_rules


def test_rule_unknown_capability_blocked():
    analyzer = PreflightAnalyzer()
    proposal = ExecutionProposal(
        proposal_id="p7", session_id="s1", event_id="e1",
        action="read", target="/tmp/f",
        params={}, required_capabilities=["unknown.cap"],
        confidence=0.8, risk_score=0.1, metadata={},
    )
    result = analyzer.analyze(proposal)
    assert result.valid is False
    assert "capabilities_are_known" in result.triggered_rules


def test_rule_high_risk_network_write_flagged():
    analyzer = PreflightAnalyzer()
    proposal = ExecutionProposal(
        proposal_id="p8", session_id="s1", event_id="e1",
        action="write", target="/tmp/f",
        params={},
        required_capabilities=[Capability.FILESYSTEM_WRITE, Capability.NETWORK_HTTP],
        confidence=0.8, risk_score=0.85, metadata={},
    )
    result = analyzer.analyze(proposal)
    assert result.valid is True
    assert any("no_network_write_high_risk" in f for f in result.flags)


def test_rule_write_without_target_blocked():
    analyzer = PreflightAnalyzer()
    proposal = ExecutionProposal(
        proposal_id="p9", session_id="s1", event_id="e1",
        action="write", target=None,
        params={},
        required_capabilities=[Capability.FILESYSTEM_WRITE],
        confidence=0.8, risk_score=0.1, metadata={},
    )
    result = analyzer.analyze(proposal)
    assert result.valid is False
    assert "target_present_for_write" in result.triggered_rules


# ── (d) Resource limit edge cases ──

def test_resource_at_exact_limit_passes():
    monitor = ResourceMonitor(limits=ResourceLimits(
        max_time_ms=30000, max_operations=100, max_memory_mb=128,
    ))
    guard = monitor.create_guard()
    for _ in range(100):
        violation = monitor.check_operation(guard)
    assert violation is None
    assert guard.usage.operations == 100
    assert guard.exceeded is False


def test_resource_one_below_limit_passes():
    monitor = ResourceMonitor(limits=ResourceLimits(
        max_time_ms=30000, max_operations=100, max_memory_mb=128,
    ))
    guard = monitor.create_guard()
    for _ in range(99):
        violation = monitor.check_operation(guard)
    assert violation is None
    assert guard.usage.operations == 99
    assert guard.exceeded is False


def test_resource_one_above_limit_fails():
    monitor = ResourceMonitor(limits=ResourceLimits(
        max_time_ms=30000, max_operations=100, max_memory_mb=128,
    ))
    guard = monitor.create_guard()
    for _ in range(101):
        monitor.check_operation(guard)
    assert guard.exceeded is True
    assert "max_operations_exceeded" in guard.violation
    assert guard.usage.operations == 101


def test_resource_time_at_limit_passes():
    monitor = ResourceMonitor(limits=ResourceLimits(
        max_time_ms=100, max_operations=100, max_memory_mb=128,
    ))
    guard = monitor.create_guard()
    violation = monitor.check_time(guard, 100.0)
    assert violation is None


def test_resource_time_one_above_limit_fails():
    monitor = ResourceMonitor(limits=ResourceLimits(
        max_time_ms=100, max_operations=100, max_memory_mb=128,
    ))
    guard = monitor.create_guard()
    violation = monitor.check_time(guard, 100.001)
    assert violation is not None


def test_resource_finalize_reflects_state():
    monitor = ResourceMonitor(limits=ResourceLimits(
        max_time_ms=30000, max_operations=100, max_memory_mb=128,
    ))
    guard = monitor.create_guard()
    monitor.check_operation(guard)
    monitor.check_time(guard, 5.0)
    summary = monitor.finalize(guard)

    assert summary["usage"]["operations"] == 1
    assert summary["usage"]["time_ms"] == 5.0
    assert summary["exceeded"] is False


# ── (e) Concurrent execution simulation ──

async def test_5_execution_cells_no_cross_contamination():
    results = []

    async def worker(proposal, decision):
        return {"handler": proposal.metadata.get("handler"),
                "seq": proposal.proposal_id}

    handlers = ["alpha", "beta", "gamma", "delta", "epsilon"]

    for i in range(5):
        enforcer = CapabilityEnforcer()
        cell = ExecutionCell(enforcer, worker, max_time_ms=5000)

        proposal = ExecutionProposal(
            proposal_id=f"seq-{i:03d}",
            session_id="sandbox-stress",
            event_id=f"evt-{i:03d}",
            action="process",
            target=f"/data/{i}",
            params={"index": i},
            required_capabilities=[Capability.FILESYSTEM_READ],
            confidence=0.9,
            risk_score=0.1,
            metadata={"handler": handlers[i]},
        )
        decision = PolicyDecision(
            decision_id=f"dec-{i:03d}",
            proposal_id=proposal.proposal_id,
            session_id=proposal.session_id,
            verdict="ALLOW",
            reason="ok",
            risk_level="low",
            rule_triggered=None,
            confidence=0.95,
        )

        result = await cell.execute(proposal, decision)
        results.append(result)

    assert len(results) == 5
    for i, r in enumerate(results):
        assert r.status == "SUCCESS"
        assert r.error is None
        assert r.proposal_id == f"seq-{i:03d}"
