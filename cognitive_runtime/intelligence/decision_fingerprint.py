import hashlib
import json
from collections import OrderedDict
from typing import Any, Dict, List

from .intelligence_store import DecisionFingerprint, IntelligenceStore
from ..contracts.execution_trace import ExecutionTrace


class DecisionFingerprintBuilder:
    MAX_SEEN_HASHES = 50000

    def __init__(self, store: IntelligenceStore):
        self._store = store
        self._seen_hashes: OrderedDict[str, None] = OrderedDict()
        self._fingerprints_created = 0

    def _prune_seen(self) -> None:
        while len(self._seen_hashes) > self.MAX_SEEN_HASHES:
            self._seen_hashes.popitem(last=False)

    def build(self, traces: List[ExecutionTrace]) -> int:
        new_count = 0

        for trace in traces:
            ctx_hash = self._context_hash(trace)
            if ctx_hash in self._seen_hashes:
                self._seen_hashes.move_to_end(ctx_hash)
                continue
            self._seen_hashes[ctx_hash] = None
            self._prune_seen()

            fp = DecisionFingerprint(
                fingerprint_id=f"fp_{self._fingerprints_created}",
                p4_verdict=trace.p4_verdict,
                context_hash=ctx_hash,
                capability_profile=sorted(trace.capabilities_checked),
            )
            self._store.upsert_fingerprint(fp)
            self._fingerprints_created += 1
            new_count += 1

        return new_count

    def _context_hash(self, trace: ExecutionTrace) -> str:
        raw = json.dumps({
            "verdict": trace.p4_verdict,
            "risk_score": round(trace.risk_score, 2),
            "capabilities": sorted(trace.capabilities_checked),
            "preflight_valid": trace.preflight_valid,
            "p4_risk_level": trace.p4_risk_level,
            "p4_rule_triggered": trace.p4_rule_triggered,
        }, sort_keys=True)
        return hashlib.md5(raw.encode()).hexdigest()
