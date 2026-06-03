"""
preflight_rules.py — SOURCE OF TRUTH for preflight validation rules.

This file defines ALL rules used by PreflightAnalyzer.
Rules are deterministic, stateless, and versioned.
Changing a rule changes system behavior deterministically.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class RuleSeverity(Enum):
    BLOCK = "BLOCK"
    FLAG = "FLAG"


@dataclass(frozen=True)
class PreflightRule:
    name: str
    description: str
    severity: RuleSeverity
    check_fn: Callable[[dict[str, Any]], Optional[str]]

    def evaluate(self, proposal: dict[str, Any]) -> Optional[str]:
        try:
            return self.check_fn(proposal)
        except Exception as e:
            return f"rule_evaluation_error: {e}"


# ──────────────────────────────────────────────
#  Rule Definitions
# ──────────────────────────────────────────────

RULES: list[PreflightRule] = [
    PreflightRule(
        name="proposal_has_action",
        description="ExecutionProposal must have a non-empty action field",
        severity=RuleSeverity.BLOCK,
        check_fn=lambda p: None if p.get("action") else "missing_action",
    ),
    PreflightRule(
        name="proposal_has_event_id",
        description="ExecutionProposal must reference an event_id",
        severity=RuleSeverity.BLOCK,
        check_fn=lambda p: None if p.get("event_id") else "missing_event_id",
    ),
    PreflightRule(
        name="proposal_has_session_id",
        description="ExecutionProposal must belong to a session",
        severity=RuleSeverity.BLOCK,
        check_fn=lambda p: None if p.get("session_id") else "missing_session_id",
    ),
    PreflightRule(
        name="confidence_in_range",
        description="Confidence must be between 0.0 and 1.0",
        severity=RuleSeverity.BLOCK,
        check_fn=lambda p: (
            None if 0.0 <= p.get("confidence", 0.5) <= 1.0
            else "confidence_out_of_range"
        ),
    ),
    PreflightRule(
        name="risk_score_in_range",
        description="Risk score must be between 0.0 and 1.0",
        severity=RuleSeverity.BLOCK,
        check_fn=lambda p: (
            None if 0.0 <= p.get("risk_score", 0.0) <= 1.0
            else "risk_score_out_of_range"
        ),
    ),
    PreflightRule(
        name="capabilities_not_empty",
        description="At least one capability must be required",
        severity=RuleSeverity.BLOCK,
        check_fn=lambda p: (
            None if p.get("required_capabilities")
            else "no_required_capabilities"
        ),
    ),
    PreflightRule(
        name="capabilities_are_known",
        description="All required capabilities must be recognized",
        severity=RuleSeverity.BLOCK,
        check_fn=lambda p: _check_known_capabilities(p.get("required_capabilities", [])),
    ),
    PreflightRule(
        name="no_network_write_high_risk",
        description="NETWORK + WRITE at high risk must be flagged",
        severity=RuleSeverity.FLAG,
        check_fn=lambda p: _check_high_risk_combination(p),
    ),
    PreflightRule(
        name="target_present_for_write",
        description="WRITE action must have a target path",
        severity=RuleSeverity.BLOCK,
        check_fn=lambda p: _check_write_has_target(p),
    ),
]


def _check_known_capabilities(caps: list[str]) -> Optional[str]:
    from ..contracts.execution_contract import Capability
    known = {c.value for c in Capability}
    for cap in caps:
        if cap not in known:
            return f"unknown_capability: {cap}"
    return None


def _check_high_risk_combination(p: dict[str, Any]) -> Optional[str]:
    caps = p.get("required_capabilities", [])
    risk = p.get("risk_score", 0.0)
    network_write = ("network.http" in caps and "filesystem.write" in caps)
    if network_write and risk > 0.7:
        return "high_risk_network_write_combination"
    return None


def _check_write_has_target(p: dict[str, Any]) -> Optional[str]:
    caps = p.get("required_capabilities", [])
    if "filesystem.write" in caps and not p.get("target"):
        return "write_without_target"
    return None
