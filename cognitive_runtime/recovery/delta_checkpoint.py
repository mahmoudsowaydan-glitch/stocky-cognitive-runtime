"""
delta_checkpoint.py — Base + delta-segment checkpoint system.

Architecture:
  - Full base snapshot every `base_interval` cycles (default 500)
  - Delta segments every `checkpoint_interval` cycles (default 100)
  - Reconstruction: base snapshot + ordered delta segments = full state
  - Invariant REC-DELTA-001: delta chain must be sequential, no gaps
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..contracts.frozen.schema_version import FROZEN_SCHEMA_VERSION, fingerprint
from .runtime_snapshot import RuntimeSnapshot


@dataclass
class DeltaSegment:
    delta_id: str
    base_id: str
    sequence_no: int
    created_at: float
    cycle_count: int
    base_cycle_count: int
    trace_offset: int
    new_traces: List[Dict[str, Any]] = field(default_factory=list)
    new_governance_scores: List[float] = field(default_factory=list)
    new_confidence_scores: List[float] = field(default_factory=list)
    new_stability_scores: List[float] = field(default_factory=list)
    runtime_state_snapshot: Dict[str, Any] = field(default_factory=dict)
    queue_depth: int = 0
    total_events_processed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delta_id": self.delta_id,
            "base_id": self.base_id,
            "sequence_no": self.sequence_no,
            "created_at": self.created_at,
            "cycle_count": self.cycle_count,
            "base_cycle_count": self.base_cycle_count,
            "trace_offset": self.trace_offset,
            "new_traces": self.new_traces,
            "new_governance_scores": self.new_governance_scores,
            "new_confidence_scores": self.new_confidence_scores,
            "new_stability_scores": self.new_stability_scores,
            "runtime_state_snapshot": self.runtime_state_snapshot,
            "queue_depth": self.queue_depth,
            "total_events_processed": self.total_events_processed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeltaSegment":
        return cls(**{k: data.get(k, v.default if hasattr(v, 'default') else None)
                      for k, v in cls.__dataclass_fields__.items()})

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_json(cls, raw: str) -> "DeltaSegment":
        return cls.from_dict(json.loads(raw))


class DeltaCheckpointManager:
    """Base + delta checkpoint manager.

    Extends full-snapshot checkpointing with delta segments between bases.
    Every `delta_interval` cycles a delta is written; every `base_interval`
    cycles a full base snapshot resets the chain.
    """

    def __init__(self, checkpoint_dir: str = "",
                 base_interval: int = 500,
                 delta_interval: int = 100,
                 max_bases: int = 3,
                 enabled: bool = True):
        self._enabled = enabled
        self._base_interval = base_interval
        self._delta_interval = delta_interval
        self._max_bases = max_bases
        self._dir = checkpoint_dir or os.path.join(os.getcwd(), "checkpoints")
        self._delta_dir = os.path.join(self._dir, "deltas")
        self._bases: List[CheckpointBaseMeta] = []
        self._deltas: Dict[str, List[DeltaSegment]] = {}
        self._last_saved_trace_count: int = 0
        os.makedirs(self._dir, exist_ok=True)
        os.makedirs(self._delta_dir, exist_ok=True)
        self._read_metadata()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, val: bool) -> None:
        self._enabled = val

    @property
    def latest(self) -> Optional[CheckpointBaseMeta]:
        """Compatibility with CheckpointManager.latest."""
        return self._latest_base()

    @property
    def checkpoint_count(self) -> int:
        """Compatibility with CheckpointManager.checkpoint_count."""
        return len(self._bases)

    def save(self, snapshot: RuntimeSnapshot,
             health_status: str = "",
             governance_status: str = "") -> Optional[str]:
        if not self._enabled:
            return None

        cycle = snapshot.cycle_count
        is_base = self._should_write_base(cycle)

        if is_base:
            return self._save_base(snapshot, health_status, governance_status)
        else:
            return self._save_delta(snapshot)

    def _should_write_base(self, cycle: int) -> bool:
        if not self._bases:
            return True
        last_base_cycle = self._bases[-1].cycle_count
        return (cycle - last_base_cycle) >= self._base_interval

    def _save_base(self, snapshot: RuntimeSnapshot,
                   health_status: str,
                   governance_status: str) -> str:
        base_id = snapshot.snapshot_id
        path = os.path.join(self._dir, f"base_{base_id}.json")

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(snapshot.to_json())
        except Exception:
            return ""

        # Clear old delta chain — new base resets the sequence
        self._deltas.clear()

        meta = CheckpointBaseMeta(
            base_id=base_id,
            created_at=snapshot.created_at,
            cycle_count=snapshot.cycle_count,
            trace_count=snapshot.trace_count,
            schema_version=snapshot.schema_version,
            file_path=path,
            health_status=health_status,
            governance_status=governance_status,
            governance_score_count=len(snapshot.governance_score_history) if snapshot.governance_score_history else 0,
            confidence_score_count=len(snapshot.confidence_score_history) if snapshot.confidence_score_history else 0,
            stability_score_count=len(snapshot.stability_score_history) if snapshot.stability_score_history else 0,
        )
        self._bases.append(meta)
        self._last_saved_trace_count = snapshot.trace_count
        self._prune_old_bases()
        self._write_metadata()
        return base_id

    def _save_delta(self, snapshot: RuntimeSnapshot) -> str:
        base = self._latest_base()
        if not base:
            return self._save_base(snapshot, "", "")

        deltas = self._deltas.get(base.base_id, [])
        seq = len(deltas) + 1

        delta = DeltaSegment(
            delta_id=f"delta_{snapshot.snapshot_id}",
            base_id=base.base_id,
            sequence_no=seq,
            created_at=snapshot.created_at,
            cycle_count=snapshot.cycle_count,
            base_cycle_count=base.cycle_count,
            trace_offset=self._last_saved_trace_count,
            new_traces=snapshot.traces[self._last_saved_trace_count:],
            new_governance_scores=snapshot.governance_score_history[base.governance_score_count:],
            new_confidence_scores=snapshot.confidence_score_history[base.confidence_score_count:],
            new_stability_scores=snapshot.stability_score_history[base.stability_score_count:],
            runtime_state_snapshot=snapshot.runtime_state_snapshot,
            queue_depth=snapshot.queue_depth,
            total_events_processed=snapshot.total_events_processed,
        )

        path = os.path.join(self._delta_dir, f"{delta.delta_id}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(delta.to_json())
        except Exception:
            return ""

        deltas.append(delta)
        self._deltas[base.base_id] = deltas
        self._last_saved_trace_count = snapshot.trace_count
        self._write_metadata()
        return delta.delta_id

    def load_latest(self) -> Optional[RuntimeSnapshot]:
        base = self._latest_base()
        if not base:
            return None
        snap = self._load_base_snapshot(base)
        if not snap:
            return None
        deltas = self._deltas.get(base.base_id, [])
        if not deltas:
            return snap
        return self._apply_deltas(snap, deltas)

    def load_latest_base(self) -> Optional[RuntimeSnapshot]:
        base = self._latest_base()
        if not base:
            return None
        return self._load_base_snapshot(base)

    def _latest_base(self) -> Optional["CheckpointBaseMeta"]:
        return self._bases[-1] if self._bases else None

    def _load_base_snapshot(self, meta: "CheckpointBaseMeta") -> Optional[RuntimeSnapshot]:
        if not os.path.exists(meta.file_path):
            return None
        try:
            with open(meta.file_path, "r", encoding="utf-8") as f:
                return RuntimeSnapshot.from_json(f.read())
        except Exception:
            return None

    def _apply_deltas(self, base: RuntimeSnapshot,
                      deltas: List[DeltaSegment]) -> RuntimeSnapshot:
        # Sort deltas by sequence_no
        sorted_deltas = sorted(deltas, key=lambda d: d.sequence_no)

        # Verify chain sequential (REC-DELTA-001)
        for i, d in enumerate(sorted_deltas):
            expected_seq = i + 1
            if d.sequence_no != expected_seq:
                raise RuntimeError(
                    f"REC-DELTA-001 violation: delta chain gap at sequence {expected_seq}, "
                    f"got delta {d.delta_id} with seq {d.sequence_no}"
                )

        all_traces = list(base.traces)
        gov_scores = list(base.governance_score_history) if base.governance_score_history else []
        conf_scores = list(base.confidence_score_history) if base.confidence_score_history else []
        stab_scores = list(base.stability_score_history) if base.stability_score_history else []
        state = dict(base.runtime_state_snapshot) if base.runtime_state_snapshot else {}

        for d in sorted_deltas:
            all_traces.extend(d.new_traces)
            gov_scores.extend(d.new_governance_scores)
            conf_scores.extend(d.new_confidence_scores)
            stab_scores.extend(d.new_stability_scores)
            if d.runtime_state_snapshot:
                state.update(d.runtime_state_snapshot)

        return RuntimeSnapshot(
            snapshot_id=base.snapshot_id,
            created_at=sorted_deltas[-1].created_at,
            runtime_state_snapshot=state,
            trace_count=len(all_traces),
            traces=all_traces,
            governance_score_history=gov_scores,
            confidence_score_history=conf_scores,
            confidence_gradient=base.confidence_gradient,
            stability_score_history=stab_scores,
            queue_depth=sorted_deltas[-1].queue_depth,
            total_events_processed=sorted_deltas[-1].total_events_processed,
            schema_version=base.schema_version,
            schema_fingerprint=base.schema_fingerprint,
            cycle_count=sorted_deltas[-1].cycle_count,
            recovery_mode_enabled=base.recovery_mode_enabled,
        )

    def verify_delta_chain(self) -> bool:
        """REC-DELTA-001: Verify all delta chains are sequential with no gaps."""
        for base_id, deltas in self._deltas.items():
            sorted_deltas = sorted(deltas, key=lambda d: d.sequence_no)
            for i, d in enumerate(sorted_deltas):
                if d.sequence_no != i + 1:
                    return False
        return True

    @property
    def checkpoints(self) -> List[Dict[str, Any]]:
        return [b.to_dict() for b in self._bases]

    def clear(self) -> None:
        for b in self._bases:
            try:
                if os.path.exists(b.file_path):
                    os.remove(b.file_path)
            except Exception:
                pass
        for base_id, deltas in self._deltas.items():
            for d in deltas:
                path = os.path.join(self._delta_dir, f"{d.delta_id}.json")
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception:
                    pass
        self._bases.clear()
        self._deltas.clear()
        self._write_metadata()

    def _prune_old_bases(self) -> None:
        while len(self._bases) > self._max_bases:
            old = self._bases.pop(0)
            try:
                if os.path.exists(old.file_path):
                    os.remove(old.file_path)
            except Exception:
                pass
            # Remove associated deltas
            if old.base_id in self._deltas:
                for d in self._deltas[old.base_id]:
                    dpath = os.path.join(self._delta_dir, f"{d.delta_id}.json")
                    try:
                        if os.path.exists(dpath):
                            os.remove(dpath)
                    except Exception:
                        pass
                del self._deltas[old.base_id]

    def _bases_path(self) -> str:
        return os.path.join(self._dir, "bases.json")

    def _write_metadata(self) -> None:
        try:
            data = {
                "bases": [b.to_dict() for b in self._bases],
                "deltas": {
                    bid: [d.to_dict() for d in ds]
                    for bid, ds in self._deltas.items()
                },
            }
            with open(self._bases_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _read_metadata(self) -> None:
        path = self._bases_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._bases = [CheckpointBaseMeta.from_dict(b) for b in data.get("bases", [])]
            self._deltas = {
                bid: [DeltaSegment.from_dict(d) for d in ds]
                for bid, ds in data.get("deltas", {}).items()
            }
        except Exception:
            self._bases = []
            self._deltas = {}


@dataclass
class CheckpointBaseMeta:
    base_id: str
    created_at: float
    cycle_count: int
    trace_count: int
    schema_version: str
    file_path: str
    health_status: str = ""
    governance_status: str = ""
    recovery_mode: bool = False
    governance_score_count: int = 0
    confidence_score_count: int = 0
    stability_score_count: int = 0
    schema_fingerprint: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_id": self.base_id,
            "created_at": self.created_at,
            "cycle_count": self.cycle_count,
            "trace_count": self.trace_count,
            "schema_version": self.schema_version,
            "file_path": self.file_path,
            "health_status": self.health_status,
            "governance_status": self.governance_status,
            "recovery_mode": self.recovery_mode,
            "governance_score_count": self.governance_score_count,
            "confidence_score_count": self.confidence_score_count,
            "stability_score_count": self.stability_score_count,
            "schema_fingerprint": self.schema_fingerprint,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CheckpointBaseMeta":
        return cls(**{k: data.get(k, v.default if hasattr(v, 'default') else None)
                      for k, v in cls.__dataclass_fields__.items()})
