import math
from typing import Any, Dict, Optional

from ..liveness.liveness_monitor import NullLivenessMonitor
from .telemetry_snapshot import TelemetrySnapshot
from .telemetry_store import TelemetryStore


class NullTelemetryProbe:
    def capture(self, loop: Any) -> None:
        pass

    @property
    def store(self) -> TelemetryStore:
        return TelemetryStore()

    @property
    def enabled(self) -> bool:
        return False


class TelemetryProbe:
    def __init__(self, store: Optional[TelemetryStore] = None,
                 capture_interval: int = 10):
        self._store = store or TelemetryStore()
        self._capture_interval = capture_interval
        self._call_count: int = 0
        self._last_entropy: Optional[float] = None
        self._last_cycle: Optional[int] = None
        self._last_governance_score: Optional[float] = None
        self._oscillation_count: int = 0
        self._prev_governance_score: Optional[float] = None
        self._last_stability_score: Optional[float] = None
        self._last_confidence_score: Optional[float] = None

    @property
    def store(self) -> TelemetryStore:
        return self._store

    @property
    def enabled(self) -> bool:
        return True

    def capture(self, loop: Any) -> Optional[TelemetrySnapshot]:
        self._call_count += 1
        if self._call_count % self._capture_interval != 0:
            return None
        cycle = self._extract_cycle(loop)
        gov_score = self._extract_governance_score(loop)
        ent_score = self._extract_entropy_score(loop)
        drift_score = self._extract_drift_score(loop)
        stab_score = self._extract_stability_score(loop)
        conf_score = self._extract_confidence_score(loop)
        ent_vel = self._compute_entropy_velocity(ent_score, cycle)
        osc_count = self._compute_oscillation(gov_score)
        hysteresis = self._compute_hysteresis(gov_score)
        causal_density = self._extract_causal_density(loop)
        await_amp = self._extract_await_amplification(loop)
        ck_size = self._extract_checkpoint_size(loop)
        pending = self._extract_pending_tasks(loop)
        is_stalled = self._extract_is_stalled(loop)
        health = self._extract_health(loop)

        self._last_entropy = ent_score
        self._last_cycle = cycle
        self._last_stability_score = stab_score
        self._last_confidence_score = conf_score
        self._last_governance_score = gov_score

        snap = TelemetrySnapshot(
            cycle_no=cycle,
            governance_score=gov_score,
            entropy_score=ent_score,
            drift_score=drift_score,
            stability_score=stab_score,
            confidence_score=conf_score,
            entropy_velocity=ent_vel,
            governance_oscillation_count=osc_count,
            confidence_hysteresis=hysteresis,
            causal_density=causal_density,
            await_amplification=await_amp,
            checkpoint_size_kb=ck_size,
            pending_tasks=pending,
            is_stalled=is_stalled,
            health_status=health,
        )
        self._store.record(snap)
        return snap

    def _extract_cycle(self, loop: Any) -> int:
        if hasattr(loop, "state") and hasattr(loop.state, "total_events_processed"):
            return loop.state.total_events_processed
        if hasattr(loop, "_traces"):
            try:
                return len(loop._traces)
            except TypeError:
                pass
        return 0

    @staticmethod
    def _recent_traces(loop: Any) -> list:
        all_traces = getattr(loop, "traces", [])
        if not all_traces:
            return []
        cg = getattr(loop, "causal_graph", None)
        if cg is not None:
            n_nodes = len(getattr(cg, "nodes", []))
            if n_nodes > 0:
                window = min(n_nodes, len(all_traces))
                return all_traces[-window:]
        return all_traces[-200:]

    def _extract_governance_score(self, loop: Any) -> float:
        gov = getattr(loop, "governance", None)
        if gov is None:
            return 0.0
        history = getattr(gov, "score_history", None)
        if history and len(history) > 0:
            return history[-1]
        return self._last_governance_score or 0.0

    def _extract_entropy_score(self, loop: Any) -> float:
        gov = getattr(loop, "governance", None)
        if gov is None:
            return 0.0
        try:
            traces = self._recent_traces(loop)
            report = gov.assess(
                traces=traces,
                state=getattr(loop, "state", None),
                graph=getattr(loop, "causal_graph", None),
                store=getattr(getattr(loop, "compression", None), "store", None),
                coherence=getattr(loop, "coherence", None),
                stability=getattr(loop, "stability", None),
                confidence=getattr(loop, "confidence", None),
            )
            val = report.entropy.overall
            return float(val) if isinstance(val, (int, float)) else 0.0
        except Exception:
            return 0.0

    def _extract_drift_score(self, loop: Any) -> float:
        gov = getattr(loop, "governance", None)
        if gov is None:
            return 0.0
        try:
            traces = self._recent_traces(loop)
            report = gov.assess(
                traces=traces,
                state=getattr(loop, "state", None),
                graph=getattr(loop, "causal_graph", None),
                store=getattr(getattr(loop, "compression", None), "store", None),
                coherence=getattr(loop, "coherence", None),
                stability=getattr(loop, "stability", None),
                confidence=getattr(loop, "confidence", None),
            )
            val = report.drift.overall
            return float(val) if isinstance(val, (int, float)) else 0.0
        except Exception:
            return 0.0

    def _extract_stability_score(self, loop: Any) -> float:
        if hasattr(loop, "stability"):
            history = getattr(loop.stability, "score_history", None)
            if history and len(history) > 0:
                return history[-1]
        return self._last_stability_score or 0.0

    def _extract_confidence_score(self, loop: Any) -> float:
        if hasattr(loop, "confidence"):
            history = getattr(loop.confidence, "score_history", None)
            if history and len(history) > 0:
                return history[-1]
        return self._last_confidence_score or 0.0

    def _compute_entropy_velocity(self, current_entropy: float,
                                   current_cycle: int) -> float:
        if (self._last_entropy is not None and self._last_cycle is not None
                and current_cycle != self._last_cycle):
            return (current_entropy - self._last_entropy) / (
                current_cycle - self._last_cycle
            )
        return 0.0

    def _compute_oscillation(self, current_gov_score: float) -> int:
        if (self._prev_governance_score is not None
                and self._last_governance_score is not None):
            prev_delta = self._last_governance_score - self._prev_governance_score
            curr_delta = current_gov_score - self._last_governance_score
            if prev_delta * curr_delta < 0:
                self._oscillation_count += 1
        self._prev_governance_score = self._last_governance_score
        return self._oscillation_count

    def _compute_hysteresis(self, current_gov_score: float) -> float:
        if not hasattr(self, "_improvement_sum"):
            self._improvement_sum = 0.0
            self._degradation_sum = 0.0
            self._hysteresis_count = 0
        if (self._last_governance_score is not None
                and self._hysteresis_count < 100):
            delta = current_gov_score - self._last_governance_score
            if delta > 0:
                self._improvement_sum += delta
            else:
                self._degradation_sum += abs(delta)
            self._hysteresis_count += 1
        if self._hysteresis_count > 0:
            return abs(
                self._improvement_sum / max(1, self._hysteresis_count)
                - self._degradation_sum / max(1, self._hysteresis_count)
            )
        return 0.0

    def _extract_causal_density(self, loop: Any) -> float:
        cg = getattr(loop, "causal_graph", None)
        if cg is None:
            return 0.0
        nodes = len(getattr(cg, "nodes", []))
        edges = len(getattr(cg, "edges", []))
        if nodes == 0:
            return 0.0
        return edges / nodes

    def _extract_await_amplification(self, loop: Any) -> float:
        liveness = getattr(loop, "liveness", None)
        if liveness is None or isinstance(liveness, NullLivenessMonitor):
            return 0.0
        report = liveness.get_report()
        cycle_durs = getattr(report, "cycle_durations", None)
        phase_stats = getattr(report, "phase_await_stats", {})
        if cycle_durs is None or not phase_stats:
            return 0.0
        total_await_ms = sum(
            getattr(s, "max_ms", 0.0) for s in phase_stats.values()
        )
        p95_ms = getattr(cycle_durs, "p95_ms", 1.0)
        if p95_ms == 0:
            return 0.0
        return min(total_await_ms / p95_ms, 1.0)

    def _extract_checkpoint_size(self, loop: Any) -> float:
        cm = getattr(loop, "_checkpoint_manager", None)
        if cm is None:
            return 0.0
        if hasattr(cm, "latest"):
            meta = cm.latest
            if meta and hasattr(meta, "size_bytes") and meta.size_bytes:
                return meta.size_bytes / 1024.0
        if hasattr(cm, "_bases") and cm._bases:
            last_base = cm._bases[-1]
            if hasattr(last_base, "size_bytes") and last_base.size_bytes:
                return last_base.size_bytes / 1024.0
        return 0.0

    def _extract_pending_tasks(self, loop: Any) -> int:
        if hasattr(loop, "state") and hasattr(loop.state, "queue_depth"):
            return loop.state.queue_depth
        return 0

    def _extract_is_stalled(self, loop: Any) -> bool:
        liveness = getattr(loop, "liveness", None)
        if liveness is None or isinstance(liveness, NullLivenessMonitor):
            return False
        report = liveness.get_report()
        return getattr(report, "is_stalled", False)

    def _extract_health(self, loop: Any) -> str:
        if hasattr(loop, "state"):
            return getattr(loop.state, "health_status", "healthy")
        return "healthy"
