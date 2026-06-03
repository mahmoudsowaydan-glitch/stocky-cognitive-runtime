from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .intelligence_store import IntelligenceStore
from .pattern_miner import PatternMiner
from .failure_signature import FailureSignatureDetector
from .decision_fingerprint import DecisionFingerprintBuilder
from ..contracts.causal_graph import CausalGraph
from ..contracts.execution_trace import ExecutionTrace


@dataclass
class CompressionReport:
    patterns_found: int = 0
    failures_detected: int = 0
    fingerprints_built: int = 0
    total_patterns: int = 0
    total_failures: int = 0
    total_fingerprints: int = 0


class CompressionEngine:
    def __init__(self):
        self._store = IntelligenceStore()
        self._miner = PatternMiner(self._store)
        self._failure_detector = FailureSignatureDetector(self._store)
        self._fingerprint_builder = DecisionFingerprintBuilder(self._store)
        self._total_cycles = 0

    def process(self, graph: CausalGraph, traces: List[ExecutionTrace]) -> CompressionReport:
        if not traces:
            return CompressionReport()

        self._total_cycles += 1

        new_patterns = self._miner.mine(graph, traces)
        new_failures = self._failure_detector.detect(graph, traces)
        new_fingerprints = self._fingerprint_builder.build(traces)

        return CompressionReport(
            patterns_found=new_patterns,
            failures_detected=new_failures,
            fingerprints_built=new_fingerprints,
            total_patterns=len(self._store.patterns),
            total_failures=len(self._store.failures),
            total_fingerprints=len(self._store.fingerprints),
        )

    @property
    def store(self) -> IntelligenceStore:
        return self._store

    @property
    def total_cycles(self) -> int:
        return self._total_cycles
