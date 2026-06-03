from enum import Enum
from typing import Dict, List


class EpochPhase(Enum):
    WARMUP = "WARMUP"
    STABILIZATION = "STABILIZATION"
    CHAOS = "CHAOS"
    RECOVERY = "RECOVERY"
    OBSERVATION = "OBSERVATION"
    SHUTDOWN = "SHUTDOWN"
    RECOVERY_BOOT = "RECOVERY_BOOT"
    REPLAY_VALIDATION = "REPLAY_VALIDATION"
    POSTMORTEM = "POSTMORTEM"


PHASE_TRANSITIONS: Dict[EpochPhase, List[EpochPhase]] = {
    EpochPhase.WARMUP: [EpochPhase.STABILIZATION],
    EpochPhase.STABILIZATION: [EpochPhase.CHAOS, EpochPhase.OBSERVATION],
    EpochPhase.CHAOS: [EpochPhase.RECOVERY, EpochPhase.OBSERVATION],
    EpochPhase.RECOVERY: [EpochPhase.OBSERVATION, EpochPhase.CHAOS],
    EpochPhase.OBSERVATION: [EpochPhase.SHUTDOWN, EpochPhase.CHAOS, EpochPhase.RECOVERY],
    EpochPhase.SHUTDOWN: [EpochPhase.RECOVERY_BOOT, EpochPhase.POSTMORTEM],
    EpochPhase.RECOVERY_BOOT: [EpochPhase.REPLAY_VALIDATION, EpochPhase.POSTMORTEM],
    EpochPhase.REPLAY_VALIDATION: [EpochPhase.POSTMORTEM],
    EpochPhase.POSTMORTEM: [],
}
