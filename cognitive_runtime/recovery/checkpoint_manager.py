"""
checkpoint_manager.py — Periodic runtime checkpointing.

Saves RuntimeSnapshot to JSON files with metadata.
Provides load_last() for crash recovery.
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..contracts.frozen.schema_version import FROZEN_SCHEMA_VERSION, fingerprint
from .runtime_snapshot import RuntimeSnapshot


@dataclass
class CheckpointMetadata:
    checkpoint_id: str
    created_at: float
    cycle_count: int
    trace_count: int
    schema_version: str
    file_path: str
    health_status: str = ""
    governance_status: str = ""
    recovery_mode: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "created_at": self.created_at,
            "cycle_count": self.cycle_count,
            "trace_count": self.trace_count,
            "schema_version": self.schema_version,
            "file_path": self.file_path,
            "health_status": self.health_status,
            "governance_status": self.governance_status,
            "recovery_mode": self.recovery_mode,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CheckpointMetadata":
        return cls(**{k: data.get(k) for k in cls.__dataclass_fields__.keys()})


class CheckpointManager:
    def __init__(self, checkpoint_dir: str = "",
                 max_checkpoints: int = 10,
                 enabled: bool = True):
        self._enabled = enabled
        self._max = max_checkpoints
        self._dir = checkpoint_dir or os.path.join(
            os.getcwd(), "checkpoints"
        )
        self._metadata: List[CheckpointMetadata] = []
        os.makedirs(self._dir, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, val: bool) -> None:
        self._enabled = val

    @property
    def metadata(self) -> List[CheckpointMetadata]:
        return list(self._metadata)

    @property
    def latest(self) -> Optional[CheckpointMetadata]:
        return self._metadata[-1] if self._metadata else None

    @property
    def checkpoint_count(self) -> int:
        return len(self._metadata)

    def _checkpoint_path(self, snapshot: RuntimeSnapshot) -> str:
        return os.path.join(self._dir, f"cp_{snapshot.snapshot_id}.json")

    def _meta_path(self) -> str:
        return os.path.join(self._dir, "metadata.json")

    def save(self, snapshot: RuntimeSnapshot,
             health_status: str = "",
             governance_status: str = "") -> Optional[CheckpointMetadata]:
        if not self._enabled:
            return None

        path = self._checkpoint_path(snapshot)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(snapshot.to_json())
        except Exception:
            return None

        meta = CheckpointMetadata(
            checkpoint_id=snapshot.snapshot_id,
            created_at=snapshot.created_at,
            cycle_count=snapshot.cycle_count,
            trace_count=snapshot.trace_count,
            schema_version=snapshot.schema_version,
            file_path=path,
            health_status=health_status,
            governance_status=governance_status,
        )
        self._metadata.append(meta)

        # Prune old checkpoints
        while len(self._metadata) > self._max:
            old = self._metadata.pop(0)
            try:
                if os.path.exists(old.file_path):
                    os.remove(old.file_path)
            except Exception:
                pass

        self._write_metadata()
        return meta

    def load_latest(self) -> Optional[RuntimeSnapshot]:
        meta = self.latest
        if not meta:
            return None
        return self._load_file(meta.file_path)

    def load_id(self, checkpoint_id: str) -> Optional[RuntimeSnapshot]:
        for m in self._metadata:
            if m.checkpoint_id == checkpoint_id:
                return self._load_file(m.file_path)
        return None

    def _load_file(self, path: str) -> Optional[RuntimeSnapshot]:
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return RuntimeSnapshot.from_json(f.read())
        except Exception:
            return None

    def load_all_traces(self) -> List[Dict[str, Any]]:
        all_traces = []
        for m in self._metadata:
            snap = self._load_file(m.file_path)
            if snap:
                all_traces.extend(snap.traces)
        return all_traces

    def _write_metadata(self) -> None:
        try:
            data = [m.to_dict() for m in self._metadata]
            with open(self._meta_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _read_metadata(self) -> None:
        path = self._meta_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._metadata = [CheckpointMetadata.from_dict(d) for d in data]
        except Exception:
            self._metadata = []

    def clear(self) -> None:
        for m in self._metadata:
            try:
                if os.path.exists(m.file_path):
                    os.remove(m.file_path)
            except Exception:
                pass
        self._metadata.clear()
        meta_path = self._meta_path()
        if os.path.exists(meta_path):
            try:
                os.remove(meta_path)
            except Exception:
                pass

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        return [m.to_dict() for m in self._metadata]
