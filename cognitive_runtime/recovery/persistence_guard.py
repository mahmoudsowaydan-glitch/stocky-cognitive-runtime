"""
persistence_guard.py — Validates snapshot compatibility and frozen contract integrity.

Prevents recovery from incompatible snapshots (different schema version,
missing fields, contract violations).

Integration with SchemaEvolutionGuard:
  When schema_evolution_guard is provided, schema version validation
  uses graph-based compatibility (backward compat + migration path)
  instead of the simple exact-minor comparison.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..contracts.frozen.schema_version import FROZEN_SCHEMA_VERSION, SchemaVersion, fingerprint
from ..contracts.frozen.compatibility_guard import CompatibilityGuard
from ..contracts.frozen.graph_contract import GraphContract
from ..contracts.frozen.trace_contract import TraceContract
from ..contracts.frozen.bridge_contract import BridgeContract
from ..contracts.frozen.runtime_contract import RuntimeContract
from ..schema_evolution.schema_evolution_guard import SchemaEvolutionGuard
from .runtime_snapshot import RuntimeSnapshot


@dataclass
class PersistenceValidation:
    valid: bool
    schema_match: bool
    schema_snapshot: str
    schema_current: str
    has_required_fields: bool
    missing_fields: List[str]
    contract_violations: List[str]
    trace_count_positive: bool
    details: str = ""


class PersistenceGuard:
    def __init__(self, compatibility_guard: Optional[CompatibilityGuard] = None,
                 schema_evolution_guard: Optional[SchemaEvolutionGuard] = None):
        self._guard = compatibility_guard or CompatibilityGuard()
        self._schema_evolution_guard = schema_evolution_guard

    def validate_snapshot(self, snapshot: RuntimeSnapshot) -> PersistenceValidation:
        violations = []

        # 1. Schema version match
        snap_sv = snapshot.schema_version
        current_sv = str(FROZEN_SCHEMA_VERSION)

        if self._schema_evolution_guard is not None:
            try:
                self._schema_evolution_guard.validate_snapshot(snapshot, current_sv)
                schema_match = True
            except ValueError:
                schema_match = False
                violations.append(f"Schema mismatch: snapshot={snap_sv} current={current_sv}")
        else:
            try:
                parts = snap_sv.split(".")
                snap_ver = SchemaVersion(int(parts[0]), int(parts[1]), int(parts[2]))
                schema_match = snap_ver.is_compatible_with(FROZEN_SCHEMA_VERSION)
            except Exception:
                schema_match = False
                violations.append(f"Invalid schema version: {snap_sv}")
            if not schema_match:
                violations.append(f"Schema mismatch: snapshot={snap_sv} current={current_sv}")

        # 2. Required fields
        required = ["snapshot_id", "created_at", "runtime_state_snapshot",
                     "trace_count", "traces", "schema_version"]
        missing = [f for f in required if not hasattr(snapshot, f)
                   or getattr(snapshot, f) is None]
        if missing:
            violations.append(f"Missing required fields: {missing}")

        # 3. Trace count consistency
        tc = len(snapshot.traces) if (hasattr(snapshot, "traces") and snapshot.traces is not None) else 0
        trace_ok = tc == snapshot.trace_count
        if not trace_ok:
            violations.append(f"Trace count mismatch: reported={snapshot.trace_count} actual={tc}")

        # 4. Fingerprint match (if set)
        if snapshot.schema_fingerprint:
            expected_fp = fingerprint(snapshot.__class__.__name__)
            if snapshot.schema_fingerprint != expected_fp:
                violations.append(f"Fingerprint mismatch: snapshot={snapshot.schema_fingerprint} expected={expected_fp}")

        return PersistenceValidation(
            valid=len(violations) == 0,
            schema_match=schema_match,
            schema_snapshot=snap_sv,
            schema_current=current_sv,
            has_required_fields=len(missing) == 0,
            missing_fields=missing,
            contract_violations=violations,
            trace_count_positive=snapshot.trace_count >= 0,
            details="; ".join(violations) if violations else "valid",
        )

    def validate_runtime(self, runtime_loop: Any) -> List[str]:
        violations = []
        if hasattr(runtime_loop, "_contract_guard"):
            result = runtime_loop._contract_guard.run_all(runtime_loop)
            if not result["passed"]:
                for v in runtime_loop._contract_guard.violations:
                    violations.append(f"{v['component']}: {v['message']}")
        return violations
