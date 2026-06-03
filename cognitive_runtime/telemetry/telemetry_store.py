import json
import os
from collections import deque
from math import sqrt
from typing import Deque, Dict, List, Optional, Tuple

from .telemetry_snapshot import PhysiologySummary, TelemetrySnapshot, WarmAggregate


class TelemetryStore:
    HOT_MAX = 1000
    WARM_INTERVAL = 1000
    WARM_MAX = 500

    def __init__(self):
        self._hot: Deque[TelemetrySnapshot] = deque(maxlen=self.HOT_MAX)
        self._warm: List[WarmAggregate] = []
        self._capture_count: int = 0
        self._last_health: str = "healthy"
        self._stall_free_streak: int = 0

    def record(self, snapshot: TelemetrySnapshot) -> None:
        self._hot.append(snapshot)
        self._capture_count += 1
        if snapshot.health_status != "stalled":
            self._stall_free_streak += 1
        else:
            self._stall_free_streak = 0
        if self._capture_count % self.WARM_INTERVAL == 0:
            self._compress()

    @property
    def hot(self) -> Deque[TelemetrySnapshot]:
        return self._hot

    @property
    def warm(self) -> List[WarmAggregate]:
        return list(self._warm)

    @property
    def stall_free_streak(self) -> int:
        return self._stall_free_streak

    @property
    def capture_count(self) -> int:
        return self._capture_count

    @property
    def hot_memory_bytes(self) -> int:
        return len(self._hot) * 200

    @property
    def warm_memory_bytes(self) -> int:
        return len(self._warm) * 400

    @property
    def cold_archive_count(self) -> int:
        return len(self._warm)

    @property
    def cpu_amplification(self) -> float:
        if self._capture_count == 0:
            return 0.0
        return float(self._capture_count) / max(1, self._capture_count * 10)

    @property
    def hot_maxlen(self) -> int:
        return self._hot.maxlen or 0

    def latest(self) -> Optional[TelemetrySnapshot]:
        if self._hot:
            return self._hot[-1]
        return None

    def _compress(self) -> WarmAggregate:
        window = list(self._hot)[-self.WARM_INTERVAL:]
        if not window:
            return self._compress_empty()
        n = len(window)
        gov_vals = [s.governance_score for s in window]
        stab_vals = [s.stability_score for s in window]
        conf_vals = [s.confidence_score for s in window]
        ent_vals = [s.entropy_score for s in window]
        drf_vals = [s.drift_score for s in window]
        ev_vals = [s.entropy_velocity for s in window]
        aa_vals = [s.await_amplification for s in window]
        cd_vals = [s.causal_density for s in window]
        ck_vals = [s.checkpoint_size_kb for s in window]

        def mean(vals: List[float]) -> float:
            return sum(vals) / n

        def std(vals: List[float], m: float) -> float:
            return sqrt(sum((v - m) ** 2 for v in vals) / n)

        def linear_trend(vals: List[float]) -> float:
            if n < 2:
                return 0.0
            xs = list(range(n))
            mx = (n - 1) / 2.0
            my = mean(vals)
            num = sum((x - mx) * (v - my) for x, v in zip(xs, vals))
            den = sum((x - mx) ** 2 for x in xs)
            return num / den if den != 0 else 0.0

        gov_mean = mean(gov_vals)
        ent_mean = mean(ent_vals)

        min_health = max((s.health_status for s in window),
                         key=lambda h: {"healthy": 0, "degraded": 1, "critical": 2, "stalled": 3}.get(h, 4))
        total_stalls = sum(1 for s in window if s.is_stalled)
        growth = (ck_vals[-1] - ck_vals[0]) if len(ck_vals) >= 2 else 0.0

        agg = WarmAggregate(
            cycle_range=(window[0].cycle_no, window[-1].cycle_no),
            count=n,
            mean_governance=gov_mean,
            mean_stability=mean(stab_vals),
            mean_confidence=mean(conf_vals),
            mean_entropy=ent_mean,
            mean_drift=mean(drf_vals),
            mean_entropy_velocity=mean(ev_vals),
            mean_await_amplification=mean(aa_vals),
            mean_causal_density=mean(cd_vals),
            std_entropy=std(ent_vals, ent_mean),
            std_stability=std(stab_vals, mean(stab_vals)),
            trend_governance=linear_trend(gov_vals),
            trend_stability=linear_trend(stab_vals),
            trend_confidence=linear_trend(conf_vals),
            min_health=min_health,
            max_pending=max(s.pending_tasks for s in window),
            total_checkpoint_growth_kb=growth,
            total_stalls=total_stalls,
        )
        self._warm.append(agg)
        while len(self._warm) > self.WARM_MAX:
            self._warm.pop(0)
        return agg

    def _compress_empty(self) -> WarmAggregate:
        agg = WarmAggregate(
            cycle_range=(0, 0), count=0, mean_governance=0.0,
            mean_stability=0.0, mean_confidence=0.0, mean_entropy=0.0,
            mean_drift=0.0, mean_entropy_velocity=0.0,
            mean_await_amplification=0.0, mean_causal_density=0.0,
            std_entropy=0.0, std_stability=0.0, trend_governance=0.0,
            trend_stability=0.0, trend_confidence=0.0,
            min_health="healthy", max_pending=0,
            total_checkpoint_growth_kb=0.0, total_stalls=0,
        )
        self._warm.append(agg)
        return agg

    def get_physiology(self) -> PhysiologySummary:
        if len(self._warm) < 3:
            return PhysiologySummary(
                entropy_slope=0.0, memory_plateau=False,
                recovery_cost_stable=False, governance_stable=False,
                confidence_stable=False, stability_stable=False,
                stall_free_streak=self._stall_free_streak,
                cycle_count=self._capture_count,
            )
        recent = self._warm[-3:]
        ent_slope = (recent[-1].mean_entropy - recent[0].mean_entropy) / max(1, len(recent) - 1)
        gov_stable = abs(recent[-1].trend_governance) < 0.01
        conf_stable = abs(recent[-1].trend_confidence) < 0.01
        stab_stable = abs(recent[-1].trend_stability) < 0.01
        mem_plateau = (recent[-1].std_entropy < 0.05 and
                       recent[-1].mean_causal_density < 0.8)
        rc_stable = (recent[-1].mean_await_amplification < 0.3 and
                     recent[-1].total_stalls == 0)
        return PhysiologySummary(
            entropy_slope=ent_slope,
            memory_plateau=mem_plateau,
            recovery_cost_stable=rc_stable,
            governance_stable=gov_stable,
            confidence_stable=conf_stable,
            stability_stable=stab_stable,
            stall_free_streak=self._stall_free_streak,
            cycle_count=self._capture_count,
        )

    def save_cold(self, archive_dir: str) -> None:
        os.makedirs(archive_dir, exist_ok=True)
        path = os.path.join(archive_dir, f"telemetry_warm_{self._capture_count}.json")
        data = []
        for agg in self._warm:
            data.append({
                "cycle_range": list(agg.cycle_range),
                "count": agg.count,
                "mean_governance": agg.mean_governance,
                "mean_stability": agg.mean_stability,
                "mean_confidence": agg.mean_confidence,
                "mean_entropy": agg.mean_entropy,
                "mean_drift": agg.mean_drift,
                "mean_entropy_velocity": agg.mean_entropy_velocity,
                "mean_await_amplification": agg.mean_await_amplification,
                "mean_causal_density": agg.mean_causal_density,
                "std_entropy": agg.std_entropy,
                "std_stability": agg.std_stability,
                "trend_governance": agg.trend_governance,
                "trend_stability": agg.trend_stability,
                "trend_confidence": agg.trend_confidence,
                "min_health": agg.min_health,
                "max_pending": agg.max_pending,
                "total_checkpoint_growth_kb": agg.total_checkpoint_growth_kb,
                "total_stalls": agg.total_stalls,
            })
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load_cold(self, archive_dir: str) -> int:
        loaded = 0
        if not os.path.isdir(archive_dir):
            return 0
        for fname in sorted(os.listdir(archive_dir)):
            if not fname.startswith("telemetry_warm_") or not fname.endswith(".json"):
                continue
            path = os.path.join(archive_dir, fname)
            with open(path) as f:
                data = json.load(f)
            for item in data:
                self._warm.append(WarmAggregate(
                    cycle_range=tuple(item["cycle_range"]),
                    count=item["count"],
                    mean_governance=item["mean_governance"],
                    mean_stability=item["mean_stability"],
                    mean_confidence=item["mean_confidence"],
                    mean_entropy=item["mean_entropy"],
                    mean_drift=item["mean_drift"],
                    mean_entropy_velocity=item["mean_entropy_velocity"],
                    mean_await_amplification=item["mean_await_amplification"],
                    mean_causal_density=item["mean_causal_density"],
                    std_entropy=item["std_entropy"],
                    std_stability=item["std_stability"],
                    trend_governance=item["trend_governance"],
                    trend_stability=item["trend_stability"],
                    trend_confidence=item["trend_confidence"],
                    min_health=item["min_health"],
                    max_pending=item["max_pending"],
                    total_checkpoint_growth_kb=item["total_checkpoint_growth_kb"],
                    total_stalls=item["total_stalls"],
                ))
                loaded += 1
        return loaded
