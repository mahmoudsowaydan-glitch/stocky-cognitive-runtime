"""
runtime_snapshot.py — Canonical runtime snapshot for checkpoint/restore.

Captures all runtime state needed for deterministic recovery:
  - RuntimeState fields
  - Execution traces
  - Governance state (score_history)
  - Confidence state (score_history, gradient, hysteresis)
  - Stability state (score_history)
  - Queue stats
  - Schema version + fingerprint
"""

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from ..contracts.execution_trace import ExecutionTrace
from ..contracts.frozen.schema_version import FROZEN_SCHEMA_VERSION, FROZEN_SCHEMA_VERSION_STR, fingerprint
from ..runtime.runtime_state import RuntimeState


@dataclass
class RuntimeSnapshot:
    snapshot_id: str
    created_at: float

    # State
    runtime_state_snapshot: Dict[str, Any]
    trace_count: int
    traces: List[Dict[str, Any]]

    # Sub-system state
    governance_score_history: List[float] = field(default_factory=list)
    confidence_score_history: List[float] = field(default_factory=list)
    confidence_gradient: str = "HIGH"

    stability_score_history: List[float] = field(default_factory=list)

    # Queue stats
    queue_depth: int = 0
    total_events_processed: int = 0

    # Schema
    schema_version: str = FROZEN_SCHEMA_VERSION_STR
    schema_fingerprint: str = ""

    # Metadata
    cycle_count: int = 0
    recovery_mode_enabled: bool = False

    @classmethod
    def capture(cls, runtime_loop: Any, snapshot_id: str = "") -> "RuntimeSnapshot":
        now = time.time()
        sid = snapshot_id or f"cp_{now}"

        # Traces → serializable dicts
        traces = []
        if hasattr(runtime_loop, "_traces"):
            source = runtime_loop._traces
            if hasattr(source, "all_traces"):
                source = source.all_traces
            for t in source:
                try:
                    traces.append(asdict(t))
                except Exception:
                    traces.append({
                        "event_id": getattr(t, "event_id", "unknown"),
                        "session_id": getattr(t, "session_id", ""),
                        "final_status": getattr(t, "final_status", "UNKNOWN"),
                    })

        # Sub-system state
        gov_history = []
        conf_history = []
        conf_gradient = "HIGH"
        stab_history = []

        if hasattr(runtime_loop, "_governance") and hasattr(runtime_loop._governance, "_score_history"):
            gov_history = list(runtime_loop._governance._score_history)
        if hasattr(runtime_loop, "_confidence"):
            conf = runtime_loop._confidence
            if hasattr(conf, "_score_history"):
                conf_history = list(conf._score_history)
            if hasattr(conf, "_guard") and hasattr(conf._guard, "_current_gradient") and conf._guard._current_gradient is not None:
                conf_gradient = str(conf._guard._current_gradient)
        if hasattr(runtime_loop, "_stability") and hasattr(runtime_loop._stability, "_score_history"):
            stab_history = list(runtime_loop._stability._score_history)

        state_snap = {}
        if hasattr(runtime_loop, "_state"):
            state_snap = runtime_loop._state.snapshot()

        qd = 0
        tep = 0
        if hasattr(runtime_loop, "_queue") and hasattr(runtime_loop._queue, "stats"):
            qs = runtime_loop._queue.stats
            qd = qs.queue_depth
            tep = runtime_loop.state.total_events_processed
        if hasattr(runtime_loop, "_state"):
            tep = runtime_loop._state.total_events_processed

        return cls(
            snapshot_id=sid,
            created_at=now,
            runtime_state_snapshot=state_snap,
            trace_count=len(traces),
            traces=traces,
            governance_score_history=gov_history,
            confidence_score_history=conf_history,
            confidence_gradient=conf_gradient,
            stability_score_history=stab_history,
            queue_depth=qd,
            total_events_processed=tep,
            schema_version=str(FROZEN_SCHEMA_VERSION),
            schema_fingerprint=fingerprint(cls.__name__),
            cycle_count=len(traces),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuntimeSnapshot":
        field_names = cls.__dataclass_fields__.keys()
        kwargs = {}
        for k in field_names:
            kwargs[k] = data.get(k, cls.__dataclass_fields__[k].default)
        return cls(**kwargs)

    @classmethod
    def from_json(cls, raw: str) -> "RuntimeSnapshot":
        return cls.from_dict(json.loads(raw))
