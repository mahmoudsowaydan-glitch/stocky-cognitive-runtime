"""
Federation Stage 1 — 2 Nodes, Same Schema, Shared Consensus

Purpose: First Federated Cognitive Organism run.
Measures cross-node consensus stability, inter-node governance effects,
and natural entropy velocity from merged multi-node traces.

Baseline reference: FED-BASELINE-001 (Alpha-2.5 pre-federation metrics)
"""

import random
import json

from cognitive_runtime.epoch import (
    EpochPhase,
    FederatedRuntime,
    LivingEpoch,
    PanicConfig,
)

PANIC_CONFIG = PanicConfig(
    oscillation_explosion_threshold=0.5,
    entropy_runaway_threshold=5.0,
    recovery_amplification_threshold=3.0,
    replay_divergence_threshold=5.0,
)


def main():
    print("=" * 60)
    print("  Federation Stage 1 — 2 Nodes, Same Schema, Shared Consensus")
    print("  8750 cycles — Cross-Node Governance + Consensus Stability")
    print("=" * 60)
    print()

    epoch = LivingEpoch(
        seed=42,
        runtime_factory=lambda: FederatedRuntime.factory(
            seed=42, capture_interval=25,
        ),
        capture_interval=25,
        panic_config=PANIC_CONFIG,
        phase_cycle_limits={
            EpochPhase.WARMUP: 500,
            EpochPhase.STABILIZATION: 1000,
            EpochPhase.CHAOS: 2000,
            EpochPhase.RECOVERY: 500,
            EpochPhase.OBSERVATION: 3000,
            EpochPhase.SHUTDOWN: 100,
            EpochPhase.RECOVERY_BOOT: 50,
            EpochPhase.REPLAY_VALIDATION: 100,
        },
        enable_chaos=True,
        replay_challenge_mode="none",
    )

    report = epoch.run()

    print("=" * 60)
    print("  FEDERATION RESULT")
    print("=" * 60)
    print(f"  Status : {'PASS' if report.passed else 'FAIL'}")
    print(f"  Message: {report.message}")
    print(f"  Seed   : {report.seed}")
    print()

    pm = report.postmortem
    if pm:
        print("  POSTMORTEM")
        print(f"    Total cycles      : {pm.cycle_count}")
        print(f"    Telemetry captures: {pm.telemetry_captures}")
        print(f"    Phase snapshots   : {len(pm.phase_snapshots)}")
        print(f"    Panics            : {len(pm.panics)}")
        print()

        print("  PHASE VELOCITIES")
        print(f"    {'Phase':<20} {'cycle':<8} {'eV':<12} {'gO':<12} {'cD':<12} {'rD':<12} {'rL':<12}")
        for ps in pm.phase_snapshots:
            m = ps.metrics
            pname = ps.phase.value if hasattr(ps.phase, 'value') else str(ps.phase)
            print(f"    [{pname:<18}] {ps.cycle:<8} {m.entropy_velocity:<12.6f} {m.governance_oscillation_velocity:<12.6f} {m.confidence_drift_velocity:<12.6f} {m.replay_divergence_velocity:<12.6f} {m.recovery_latency_slope:<12.6f}")

        print()
        print("  FINAL PHYSIOLOGY")
        phys = pm.final_physiology
        if phys:
            print(f"    entropy_slope       : {phys.entropy_slope}")
            print(f"    memory_plateau      : {phys.memory_plateau}")
            print(f"    stall_free_streak   : {phys.stall_free_streak}")

        if pm.replay_report:
            print()
            print("  REPLAY INTEGRITY")
            print(f"    divergence_velocity      : {pm.replay_report.divergence_velocity}")
            print(f"    passed                   : {pm.replay_report.passed}")

        print()
        print("  FED-BASELINE-001 COMPARISON")
        last_metrics = pm.phase_snapshots[-1].metrics if pm.phase_snapshots else None
        if last_metrics:
            print(f"    Entropy Velocity          : {last_metrics.entropy_velocity:.6f}  (Alpha-2.5: 0.000110)")
            print(f"    Governance Oscillation    : {last_metrics.governance_oscillation_velocity:.6f}  (Alpha-2.5: 0.027)")
            print(f"    Confidence Drift          : {last_metrics.confidence_drift_velocity:.6f}  (Alpha-2.5: 0.0017)")
            print(f"    Replay Divergence         : {last_metrics.replay_divergence_velocity:.6f}  (Alpha-2.5: -4.0)")
        print(f"    Panics                   : {len(pm.panics)}  (Alpha-2.5: 0)")
        print()

    # Extract federation-specific metrics from runtime
    runtime = epoch._runtime
    if hasattr(runtime, 'consensus_history'):
        strengths = [r.consensus_strength for r in runtime.consensus_history if r is not None]
        conflicts = [r.conflict_reasons for r in runtime.consensus_history if r is not None]
        print("  FEDERATION-SPECIFIC METRICS")
        if strengths:
            avg_strength = sum(strengths) / len(strengths)
            min_strength = min(strengths)
            max_strength = max(strengths)
            total_conflicts = sum(1 for c in conflicts if c)
            print(f"    Avg consensus strength    : {avg_strength:.4f}")
            print(f"    Min consensus strength    : {min_strength:.4f}")
            print(f"    Max consensus strength    : {max_strength:.4f}")
            print(f"    Consensus rounds          : {len(strengths)}")
            print(f"    Conflict events           : {total_conflicts}")
        print()

    print("=" * 60)


if __name__ == "__main__":
    main()
