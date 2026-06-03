"""
resource_monitor.py — Pre-check + Runtime Enforce + Postflight Finalize.

Three-phase guard system:
  1. Pre-check: estimate before execution starts
  2. Runtime enforce: monitor during execution
  3. Postflight finalize: audit after execution completes
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ResourceLimits:
    max_time_ms: int = 30000
    max_operations: int = 100
    max_memory_mb: int = 128


@dataclass
class ResourceUsage:
    time_ms: float = 0.0
    operations: int = 0
    memory_mb: float = 0.0


@dataclass
class ResourceGuard:
    limits: ResourceLimits = field(default_factory=ResourceLimits)
    usage: ResourceUsage = field(default_factory=ResourceUsage)
    exceeded: bool = False
    violation: str = ""


class ResourceMonitor:
    def __init__(self, limits: Optional[ResourceLimits] = None):
        self._limits = limits or ResourceLimits()

    # ── Phase 1: Pre-check (observability only — never blocks execution) ──
    # INV-CONF-001: Confidence is observational, not authority.
    # Pre-check must never gate execution on confidence scores.

    def pre_check(self, proposal_data: dict[str, Any]) -> Optional[str]:
        return None

    # ── Phase 2: Runtime Enforcement ──

    def create_guard(self) -> ResourceGuard:
        return ResourceGuard(limits=self._limits)

    def check_operation(self, guard: ResourceGuard) -> Optional[str]:
        guard.usage.operations += 1
        if guard.usage.operations > guard.limits.max_operations:
            guard.exceeded = True
            guard.violation = f"max_operations_exceeded: {guard.limits.max_operations}"
            return guard.violation
        return None

    def check_time(self, guard: ResourceGuard, elapsed_ms: float) -> Optional[str]:
        guard.usage.time_ms = elapsed_ms
        if elapsed_ms > guard.limits.max_time_ms:
            guard.exceeded = True
            guard.violation = f"max_time_exceeded: {guard.limits.max_time_ms}ms"
            return guard.violation
        return None

    # ── Phase 3: Postflight Finalize ──

    def finalize(self, guard: ResourceGuard) -> dict[str, Any]:
        return {
            "limits": {
                "max_time_ms": guard.limits.max_time_ms,
                "max_operations": guard.limits.max_operations,
            },
            "usage": {
                "time_ms": guard.usage.time_ms,
                "operations": guard.usage.operations,
            },
            "exceeded": guard.exceeded,
            "violation": guard.violation,
        }

    @property
    def limits(self) -> ResourceLimits:
        return self._limits
