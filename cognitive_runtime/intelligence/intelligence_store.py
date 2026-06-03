from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .eviction import EvictionConfig, EvictionPolicy, EvictionStrategy, FIFOEviction


@dataclass(frozen=True)
class Pattern:
    pattern_id: str
    frequency: int
    structure_signature: str
    context_shape: Dict[str, Any]


@dataclass(frozen=True)
class FailureSignature:
    signature_id: str
    trigger_chain: List[str]
    frequency: int
    severity_distribution: Dict[str, int]


@dataclass(frozen=True)
class DecisionFingerprint:
    fingerprint_id: str
    p4_verdict: str
    context_hash: str
    capability_profile: List[str]


class IntelligenceStore:
    def __init__(self,
                 max_patterns: int = 500,
                 max_failures: int = 200,
                 max_fingerprints: int = 500,
                 eviction_config: Optional[EvictionConfig] = None):
        self._patterns: Dict[str, Pattern] = {}
        self._failures: Dict[str, FailureSignature] = {}
        self._fingerprints: Dict[str, DecisionFingerprint] = {}
        self._max_patterns = max_patterns
        self._max_failures = max_failures
        self._max_fingerprints = max_fingerprints
        self._eviction_config = eviction_config or EvictionConfig()
        self._eviction_strategies = {
            "patterns": self._build_strategy(),
            "failures": self._build_strategy(),
            "fingerprints": self._build_strategy(),
        }

    def _build_strategy(self) -> EvictionStrategy:
        if self._eviction_config.policy == EvictionPolicy.FAA:
            from .eviction.faa_strategy import FAAEviction
            return FAAEviction(current_cycle=self._eviction_config.faa_current_cycle)
        return FIFOEviction()

    def _get_strategy(self, store: Dict) -> EvictionStrategy:
        if store is self._patterns:
            return self._eviction_strategies["patterns"]
        if store is self._failures:
            return self._eviction_strategies["failures"]
        return self._eviction_strategies["fingerprints"]

    def upsert_pattern(self, pattern: Pattern) -> None:
        existing = self._patterns.get(pattern.structure_signature)
        if existing:
            self._patterns[pattern.structure_signature] = Pattern(
                pattern_id=existing.pattern_id,
                frequency=existing.frequency + 1,
                structure_signature=existing.structure_signature,
                context_shape=existing.context_shape,
            )
            strategy = self._get_strategy(self._patterns)
            strategy.record_access(pattern.structure_signature)
        else:
            if len(self._patterns) >= self._max_patterns:
                strategy = self._get_strategy(self._patterns)
                to_evict = strategy.select_for_eviction(self._patterns)
                if to_evict:
                    del self._patterns[to_evict]
            self._patterns[pattern.structure_signature] = pattern
            strategy = self._get_strategy(self._patterns)
            strategy.record_access(pattern.structure_signature)

    def upsert_failure(self, failure: FailureSignature) -> None:
        existing = self._failures.get(failure.signature_id)
        if existing:
            new_severity = dict(existing.severity_distribution)
            for k, v in failure.severity_distribution.items():
                new_severity[k] = new_severity.get(k, 0) + v
            self._failures[failure.signature_id] = FailureSignature(
                signature_id=existing.signature_id,
                trigger_chain=existing.trigger_chain,
                frequency=existing.frequency + 1,
                severity_distribution=new_severity,
            )
            strategy = self._get_strategy(self._failures)
            strategy.record_access(failure.signature_id)
        else:
            if len(self._failures) >= self._max_failures:
                strategy = self._get_strategy(self._failures)
                to_evict = strategy.select_for_eviction(self._failures)
                if to_evict:
                    del self._failures[to_evict]
            self._failures[failure.signature_id] = failure
            strategy = self._get_strategy(self._failures)
            strategy.record_access(failure.signature_id)

    def upsert_fingerprint(self, fp: DecisionFingerprint) -> None:
        existing = self._fingerprints.get(fp.context_hash)
        if not existing:
            if len(self._fingerprints) >= self._max_fingerprints:
                strategy = self._get_strategy(self._fingerprints)
                to_evict = strategy.select_for_eviction(self._fingerprints)
                if to_evict:
                    del self._fingerprints[to_evict]
            self._fingerprints[fp.context_hash] = fp
            strategy = self._get_strategy(self._fingerprints)
            strategy.record_access(fp.context_hash)

    def get_pattern(self, structure_signature: str) -> Optional[Pattern]:
        return self._patterns.get(structure_signature)

    def get_failure(self, signature_id: str) -> Optional[FailureSignature]:
        return self._failures.get(signature_id)

    def get_fingerprint(self, context_hash: str) -> Optional[DecisionFingerprint]:
        return self._fingerprints.get(context_hash)

    @property
    def patterns(self) -> Dict[str, Pattern]:
        return dict(self._patterns)

    @property
    def failures(self) -> Dict[str, FailureSignature]:
        return dict(self._failures)

    @property
    def fingerprints(self) -> Dict[str, DecisionFingerprint]:
        return dict(self._fingerprints)

    @property
    def top_patterns(self, n: int = 10) -> List[Pattern]:
        return sorted(self._patterns.values(), key=lambda p: p.frequency, reverse=True)[:n]

    @property
    def top_failures(self, n: int = 10) -> List[FailureSignature]:
        return sorted(self._failures.values(), key=lambda f: f.frequency, reverse=True)[:n]
