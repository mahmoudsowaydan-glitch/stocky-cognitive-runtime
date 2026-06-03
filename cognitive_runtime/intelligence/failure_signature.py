import hashlib
from collections import OrderedDict
from typing import Any, Dict, List

from .intelligence_store import FailureSignature, IntelligenceStore
from ..contracts.causal_graph import CausalGraph
from ..contracts.execution_trace import ExecutionTrace


class FailureSignatureDetector:
    MAX_SEEN_CHAINS = 50000

    def __init__(self, store: IntelligenceStore):
        self._store = store
        self._seen_chains: OrderedDict[str, None] = OrderedDict()
        self._signatures_created = 0

    def _prune_seen(self) -> None:
        while len(self._seen_chains) > self.MAX_SEEN_CHAINS:
            self._seen_chains.popitem(last=False)

    def detect(self, graph: CausalGraph, traces: List[ExecutionTrace]) -> int:
        new_count = 0

        for trace in traces:
            if trace.final_status in ("SANDBOX_FAILED", "BLOCKED_BY_PREFLIGHT") or \
               trace.final_status.startswith("P4_BLOCK") or \
               trace.final_status == "P4_DEFER" or \
               trace.final_status == "P4_REVIEW":
                pass
            else:
                continue

            chain = self._extract_trigger_chain(trace)
            chain_key = self._chain_hash(chain)

            if chain_key in self._seen_chains:
                self._seen_chains.move_to_end(chain_key)
                existing = self._store.get_failure(chain_key)
                if existing:
                    self._store.upsert_failure(existing)
                continue
            self._seen_chains[chain_key] = None
            self._prune_seen()

            severity = self._classify_severity(trace)
            fs = FailureSignature(
                signature_id=chain_key,
                trigger_chain=chain,
                frequency=1,
                severity_distribution={severity: 1},
            )
            self._store.upsert_failure(fs)
            self._signatures_created += 1
            new_count += 1

        return new_count

    def _extract_trigger_chain(self, trace: ExecutionTrace) -> List[str]:
        chain = []
        if not trace.preflight_valid:
            chain.append("PREFLIGHT_BLOCK")
            chain.append(f"reason:{trace.preflight_reason or 'unknown'}")
            chain.append(f"rules:{','.join(trace.preflight_rules_triggered)}")
            return chain

        chain.append("PREFLIGHT_PASS")

        if trace.p4_verdict in ("BLOCK", "DEFER", "REVIEW"):
            chain.append(f"P4_{trace.p4_verdict}")
            chain.append(f"reason:{trace.p4_reason or 'unknown'}")
            chain.append(f"risk:{trace.p4_risk_level or 'unknown'}")
            return chain

        chain.append(f"P4_{trace.p4_verdict}")

        if trace.execution_status == "FAILED":
            chain.append("SANDBOX_FAILED")
            chain.append(f"error:{trace.execution_error or 'unknown'}")
            return chain

        return chain

    def _chain_hash(self, chain: List[str]) -> str:
        raw = "::".join(chain)
        return hashlib.md5(raw.encode()).hexdigest()

    def _classify_severity(self, trace: ExecutionTrace) -> str:
        if trace.final_status == "SANDBOX_FAILED":
            return "critical"
        if trace.p4_verdict in ("BLOCK",):
            return "high"
        if trace.p4_verdict in ("DEFER", "REVIEW"):
            return "medium"
        if not trace.preflight_valid:
            return "low"
        return "unknown"
