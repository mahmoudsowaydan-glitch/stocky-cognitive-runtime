from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Literal


# =========================
# 🔐 CAPABILITY MODEL
# =========================

class Capability(str, Enum):
    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    PROCESS_EXECUTE = "process.execute"
    NETWORK_HTTP = "network.http"
    RUNTIME_SPAWN = "runtime.spawn"
    AUDIT_READ = "audit.read"
    REPLAY_READ = "replay.read"
    COUNTERFACTUAL_ANALYZE = "counterfactual.analyze"

    @classmethod
    def from_legacy(cls, name: str) -> "Capability":
        mapping = {
            "READ_FILE": cls.FILESYSTEM_READ,
            "WRITE_FILE": cls.FILESYSTEM_WRITE,
            "EXECUTE": cls.PROCESS_EXECUTE,
            "NETWORK": cls.NETWORK_HTTP,
            "AUDIT": cls.AUDIT_READ,
            "REPLAY": cls.REPLAY_READ,
            "COUNTERFACTUAL": cls.COUNTERFACTUAL_ANALYZE,
        }
        return mapping.get(name, cls.FILESYSTEM_READ)


# =========================
# 📦 HOST EVENT
# =========================

@dataclass(frozen=True)
class HostEvent:
    event_id: str
    session_id: str
    timestamp: float
    source: str
    payload: Dict[str, Any]


# =========================
# 🧠 P3 PROPOSAL (Context Builder Output)
# =========================

@dataclass(frozen=True)
class ExecutionProposal:
    proposal_id: str
    session_id: str
    event_id: str
    action: str
    target: Optional[str]
    params: Dict[str, Any]
    required_capabilities: list[Capability]
    confidence: float
    risk_score: float
    metadata: Dict[str, Any]
    correlation_id: str = ""


# =========================
# ⚖️ P4 DECISION (Authority Output)
# =========================

DecisionType = Literal["ALLOW", "BLOCK", "DEFER", "REVIEW"]


@dataclass(frozen=True)
class PolicyDecision:
    decision_id: str
    proposal_id: str
    session_id: str
    verdict: DecisionType
    reason: str
    risk_level: str
    rule_triggered: Optional[str]
    confidence: float
    correlation_id: str = ""


# =========================
# ⚙️ EXECUTION RESULT (Substrate Output)
# =========================

@dataclass(frozen=True)
class ExecutionResult:
    execution_id: str
    proposal_id: str
    session_id: str
    status: Literal["SUCCESS", "FAILED", "SKIPPED", "QUEUED"]
    output: Optional[Any]
    error: Optional[str]
    started_at: float
    finished_at: float
    correlation_id: str = ""


# =========================
# 🧾 DLQ EVENT
# =========================

@dataclass(frozen=True)
class DeadLetterEvent:
    event_id: str
    original_event: Dict[str, Any]
    failure_reason: str
    retry_count: int
