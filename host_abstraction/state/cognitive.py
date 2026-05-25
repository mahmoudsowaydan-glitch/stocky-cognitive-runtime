from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Dict, Iterable, List, Optional

from ..bridges import ExecutionArbitrationBridge
from ..core.contracts import HostEvent
from .session_state import HALSessionState, IntentHypothesis


class CognitiveRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ResolvedIntent:
    intent_type: str
    confidence: float
    confidence_by_intent: Dict[str, float] = field(default_factory=dict)
    conflict_intents: List[str] = field(default_factory=list)
    consistency_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    explanation: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "intent_type": self.intent_type,
            "confidence": self.confidence,
            "confidence_by_intent": self.confidence_by_intent,
            "conflict_intents": self.conflict_intents,
            "consistency_score": self.consistency_score,
            "created_at": self.created_at.isoformat(),
            "explanation": self.explanation,
        }


@dataclass
class CognitiveEvent:
    original_event: HostEvent
    interpreted_intent: ResolvedIntent
    confidence: float
    risk_level: CognitiveRiskLevel
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "original_event": {
                "source": self.original_event.source.value,
                "type": self.original_event.type,
                "payload": self.original_event.payload,
                "timestamp": self.original_event.timestamp.isoformat(),
                "session_id": self.original_event.session_id,
            },
            "interpreted_intent": self.interpreted_intent.to_dict(),
            "confidence": self.confidence,
            "risk_level": self.risk_level.value,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


EventListener = Callable[["ExecutionProposal"], None]


@dataclass
class ExecutionProposal:
    intent: ResolvedIntent
    confidence: float
    risk_level: CognitiveRiskLevel
    required_capabilities: List[str] = field(default_factory=list)
    suggested_runtime_path: Optional[str] = None
    proposed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, object]:
        return {
            "intent": self.intent.to_dict(),
            "confidence": self.confidence,
            "risk_level": self.risk_level.value,
            "required_capabilities": self.required_capabilities,
            "suggested_runtime_path": self.suggested_runtime_path,
            "proposed_at": self.proposed_at.isoformat(),
        }


class IntentResolutionEngine:
    def __init__(
        self,
        conflict_threshold: float = 0.15,
        temporal_window_seconds: int = 30,
        consistency_bonus: float = 0.1,
    ) -> None:
        self._conflict_threshold = conflict_threshold
        self._temporal_window = timedelta(seconds=temporal_window_seconds)
        self._consistency_bonus = consistency_bonus

    def resolve(
        self,
        hypotheses: Iterable[IntentHypothesis],
        recent_events: Iterable[HostEvent],
        previous_intent: Optional[ResolvedIntent] = None,
    ) -> ResolvedIntent:
        candidates = sorted(hypotheses, key=lambda h: h.confidence, reverse=True)

        if not candidates:
            return ResolvedIntent(
                intent_type="observe",
                confidence=0.0,
                explanation="no intent hypotheses available",
            )

        top = candidates[0]
        second = candidates[1] if len(candidates) > 1 else None

        conflict_penalty = self._detect_conflict(top, second)
        consistency_score = self._compute_temporal_consistency(top, previous_intent, recent_events)

        final_confidence = max(0.0, min(1.0, top.confidence + consistency_score - conflict_penalty))
        resolved_type = top.intent_type
        explanation = ""

        if second and abs(top.confidence - second.confidence) <= self._conflict_threshold:
            explanation = (
                f"near-tie between '{top.intent_type}' and '{second.intent_type}' "
                f"with confidence gap {abs(top.confidence - second.confidence):.2f}"
            )
            resolved_type = top.intent_type

            if final_confidence < 0.4:
                resolved_type = "ambiguous"
                explanation += "; choosing safe ambiguous intent"

        elif conflict_penalty > 0:
            explanation = f"conflict penalty applied ({conflict_penalty:.2f})"

        return ResolvedIntent(
            intent_type=resolved_type,
            confidence=final_confidence,
            confidence_by_intent={h.intent_type: h.confidence for h in candidates},
            conflict_intents=[second.intent_type] if second and conflict_penalty > 0 else [],
            consistency_score=consistency_score,
            explanation=explanation or "resolved single leading intent",
        )

    def assess_risk(self, resolved_intent: ResolvedIntent) -> CognitiveRiskLevel:
        if resolved_intent.confidence < 0.35:
            if resolved_intent.intent_type in {"execute", "terminate", "debug"}:
                return CognitiveRiskLevel.HIGH
            return CognitiveRiskLevel.MEDIUM

        if resolved_intent.confidence < 0.65:
            return CognitiveRiskLevel.MEDIUM

        return CognitiveRiskLevel.LOW

    def _detect_conflict(
        self,
        top: IntentHypothesis,
        second: Optional[IntentHypothesis],
    ) -> float:
        if not second:
            return 0.0

        gap = abs(top.confidence - second.confidence)
        if gap <= self._conflict_threshold:
            return 0.15

        if self._is_semantic_conflict(top.intent_type, second.intent_type):
            return 0.08

        return 0.0

    def _is_semantic_conflict(self, first: str, second: str) -> bool:
        conflict_pairs = {
            ("review", "execute"),
            ("review", "terminate"),
            ("edit", "review"),
            ("execute", "pause"),
            ("debug", "copy"),
        }
        return (first, second) in conflict_pairs or (second, first) in conflict_pairs

    def _compute_temporal_consistency(
        self,
        top: IntentHypothesis,
        previous_intent: Optional[ResolvedIntent],
        recent_events: Iterable[HostEvent],
    ) -> float:
        if previous_intent and previous_intent.intent_type == top.intent_type:
            return self._consistency_bonus

        return 0.0


class HALCognitiveLoop:
    def __init__(
        self,
        session_state: HALSessionState,
        intent_hypothesis_generator: IntentHypothesisGenerator,
        resolution_engine: Optional[IntentResolutionEngine] = None,
        arbitration_bridge: Optional[ExecutionArbitrationBridge] = None,
    ) -> None:
        self.session_state = session_state
        self.intent_hypothesis_generator = intent_hypothesis_generator
        self.resolution_engine = resolution_engine or IntentResolutionEngine()
        self.arbitration_bridge = arbitration_bridge or ExecutionArbitrationBridge()
        self._listeners: List[EventListener] = []
        self._previous_resolved_intent: Optional[ResolvedIntent] = None

    def register_listener(self, listener: EventListener) -> None:
        self._listeners.append(listener)

    def unregister_listener(self, listener: EventListener) -> None:
        self._listeners = [l for l in self._listeners if l is not listener]

    def _notify(self, proposal: ExecutionProposal) -> None:
        for listener in list(self._listeners):
            listener(proposal)

    def process_host_event(self, event: HostEvent):
        # record and generate hypotheses
        self.session_state.record_event(event)

        recent_events = self.session_state.get_recent_events(20)
        hypotheses = self.intent_hypothesis_generator.generate(recent_events)
        resolved_intent = self.resolution_engine.resolve(
            hypotheses,
            recent_events,
            previous_intent=self._previous_resolved_intent,
        )

        # internal cognitive event for logging/auditing (kept internal)
        cognitive_event = CognitiveEvent(
            original_event=event,
            interpreted_intent=resolved_intent,
            confidence=resolved_intent.confidence,
            risk_level=self.resolution_engine.assess_risk(resolved_intent),
            metadata={
                "recent_event_count": len(recent_events),
                "session_id": event.session_id,
            },
        )

        # Build non-binding execution proposal for arbitration
        proposal = ExecutionProposal(
            intent=resolved_intent,
            confidence=resolved_intent.confidence,
            risk_level=self.resolution_engine.assess_risk(resolved_intent),
            required_capabilities=self._infer_required_capabilities(resolved_intent),
            suggested_runtime_path=self._suggest_runtime_path(resolved_intent),
        )

        self._notify(proposal)
        ticket = self.arbitration_bridge.submit_proposal(proposal)
        self._previous_resolved_intent = resolved_intent
        return ticket

    def _infer_required_capabilities(self, resolved: ResolvedIntent) -> List[str]:
        mapping = {
            "execute": ["process.exec", "io.write"],
            "review": ["read.files", "analyze.syntax"],
            "edit": ["write.files", "format.code"],
            "debug": ["attach.debugger", "read.logs"],
            "copy": ["clipboard.write"],
            "terminate": ["process.terminate"],
        }
        return mapping.get(resolved.intent_type, [])

    def _suggest_runtime_path(self, resolved: ResolvedIntent) -> Optional[str]:
        if resolved.intent_type in {"execute", "terminate"}:
            return "runtime/command-runner"
        if resolved.intent_type == "debug":
            return "runtime/debug-agent"
        if resolved.intent_type == "review":
            return "runtime/read-only-analyzer"
        return None
