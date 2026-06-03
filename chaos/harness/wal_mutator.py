"""
wal_mutator.py — Checkpoint/WAL file mutation.

Operates on checkpoint JSON files on disk to simulate:
- Field corruption (null traces, missing fields)
- Schema version mismatch
- Half-written files (truncated JSON)
- Wrong trace counts
"""

import json
import os
import random
from typing import Any, Dict, List, Optional


class WALMutator:
    """Mutates checkpoint JSON files on disk within a given checkpoint directory."""

    def __init__(self, checkpoint_dir: str, seed: Optional[int] = None):
        self._dir = checkpoint_dir
        self._rng = random.Random(seed)

    def list_checkpoints(self) -> List[str]:
        if not os.path.isdir(self._dir):
            return []
        return sorted([
            f for f in os.listdir(self._dir)
            if f.startswith("cp_") and f.endswith(".json")
        ])

    def corrupt_traces(self, checkpoint_id: str):
        """Set traces field to empty list or None."""
        path = self._checkpoint_path(checkpoint_id)
        data = self._load(path)
        if data is None:
            return
        choice = self._rng.choice(["empty", "null", "partial"])
        if choice == "empty":
            data["traces"] = []
        elif choice == "null":
            data["traces"] = None
        elif choice == "partial":
            if data.get("traces"):
                half = len(data["traces"]) // 2
                data["traces"] = data["traces"][:half]
                data["trace_count"] = half
        self._save(path, data)

    def corrupt_schema_version(self, checkpoint_id: str):
        """Set schema_version to a different (incompatible) value."""
        path = self._checkpoint_path(checkpoint_id)
        data = self._load(path)
        if data is None:
            return
        bad_versions = ["0.0.0", "2.0.0", "1.1.0", "invalid"]
        data["schema_version"] = self._rng.choice(bad_versions)
        self._save(path, data)

    def truncate_file(self, checkpoint_id: str):
        """Truncate checkpoint file mid-JSON to simulate partial write."""
        path = self._checkpoint_path(checkpoint_id)
        if not os.path.isfile(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        trunc_point = max(len(content) // 3, len(content) // 2)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content[:trunc_point])

    def nullify_required_field(self, checkpoint_id: str, field: str):
        """Set a required field to None."""
        path = self._checkpoint_path(checkpoint_id)
        data = self._load(path)
        if data is None:
            return
        if field in data:
            data[field] = None
        self._save(path, data)

    def mutate_trace_fields(self, checkpoint_id: str):
        """Corrupt individual trace fields (final_status, event_id)."""
        path = self._checkpoint_path(checkpoint_id)
        data = self._load(path)
        if data is None or not data.get("traces"):
            return
        for trace in data["traces"]:
            if self._rng.random() < 0.3:
                trace["final_status"] = self._rng.choice(["UNKNOWN", "CORRUPTED", None])
            if self._rng.random() < 0.2:
                trace["event_id"] = f"chaos_{self._rng.randint(1, 999)}"
        self._save(path, data)

    def arbitrary_mutation(self, checkpoint_id: str):
        """Apply a random mutation to a random checkpoint."""
        mutators = [
            self.corrupt_traces,
            self.corrupt_schema_version,
            self.nullify_required_field,
            self.mutate_trace_fields,
        ]
        mutator = self._rng.choice(mutators)
        if mutator in (self.nullify_required_field,):
            field = self._rng.choice(["snapshot_id", "schema_version", "trace_count", "traces"])
            mutator(checkpoint_id, field)
        else:
            mutator(checkpoint_id)

    def _checkpoint_path(self, checkpoint_id: str) -> str:
        return os.path.join(self._dir, f"cp_{checkpoint_id}.json")

    def _load(self, path: str) -> Optional[Dict[str, Any]]:
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def _save(self, path: str, data: Dict[str, Any]):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
