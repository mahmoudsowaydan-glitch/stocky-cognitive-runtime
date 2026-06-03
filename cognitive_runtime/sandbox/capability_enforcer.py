"""
capability_enforcer.py — Runtime Capability Gate.

Hierarchical capability checking.
Every action must pass through this gate before execution.
Fail-closed: unknown capability → BLOCK.
"""

from dataclasses import dataclass, field
from typing import Optional

from ..contracts.execution_contract import Capability


class EnforcementVerdict:
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


@dataclass
class EnforcementResult:
    verdict: str
    reason: str = ""
    capability: str = ""


class CapabilityEnforcer:
    def __init__(self):
        self._allowed: set[str] = {c.value for c in Capability}
        self._restricted: set[str] = set()

    def restrict(self, capability: Capability) -> None:
        self._restricted.add(capability.value)

    def allow(self, capability: Capability) -> None:
        self._restricted.discard(capability.value)

    def check(self, required_capabilities: list[Capability]) -> EnforcementResult:
        for cap in required_capabilities:
            cap_value = cap.value if isinstance(cap, Capability) else str(cap)
            if cap_value not in self._allowed:
                return EnforcementResult(
                    verdict=EnforcementVerdict.BLOCK,
                    reason=f"unknown_capability: {cap_value}",
                    capability=cap_value,
                )
            if cap_value in self._restricted:
                return EnforcementResult(
                    verdict=EnforcementVerdict.BLOCK,
                    reason=f"restricted_capability: {cap_value}",
                    capability=cap_value,
                )
        return EnforcementResult(
            verdict=EnforcementVerdict.ALLOW,
            reason="all_capabilities_allowed",
        )

    @property
    def allowed_capabilities(self) -> list[str]:
        return sorted(self._allowed - self._restricted)

    @property
    def restricted_capabilities(self) -> list[str]:
        return sorted(self._restricted)
