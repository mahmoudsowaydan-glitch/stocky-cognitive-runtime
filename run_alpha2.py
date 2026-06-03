import json
import sys

from cognitive_runtime.epoch import (
    BenchmarkRuntime,
    EpochPhase,
    LivingEpoch,
    PanicConfig,
)


def main():
    epoch = LivingEpoch(
        seed=42,
        runtime_factory=lambda: BenchmarkRuntime(seed=42, capture_interval=50),
        telemetry_store=None,
        panic_config=PanicConfig(
            oscillation_explosion_threshold=0.1,
            entropy_runaway_threshold=0.01,
            recovery_amplification_threshold=5.0,
            replay_divergence_threshold=0.1,
            telemetry_memory_ratio_threshold=0.05,
        ),
        capture_interval=50,
        phase_cycle_limits={
            EpochPhase.WARMUP: 500,
            EpochPhase.STABILIZATION: 1000,
            EpochPhase.CHAOS: 2000,
            EpochPhase.RECOVERY: 500,
            EpochPhase.OBSERVATION: 4500,
            EpochPhase.SHUTDOWN: 100,
            EpochPhase.RECOVERY_BOOT: 50,
            EpochPhase.REPLAY_VALIDATION: 100,
        },
        enable_chaos=True,
    )

    print("=" * 60)
    print("  Living Epoch Alpha-2 — Reality Injection")
    print("  10k cycles · 8 Event Types · CausalGraph Active")
    print("=" * 60)
    print()
    sys.stdout.flush()

    report = epoch.run()

    print()
    print("=" * 60)
    print("  EPOCH RESULT")
    print("=" * 60)
    print(f"  Status : {'PASS' if report.passed else 'FAIL'}")
    print(f"  Message: {report.message}")
    print(f"  Seed   : {report.seed}")
    print()

    if report.postmortem:
        pm = report.postmortem
        print("  POSTMORTEM")
        print(f"    Total cycles      : {pm.cycle_count}")
        print(f"    Telemetry captures: {pm.telemetry_captures}")
        print(f"    Phase snapshots   : {len(pm.phase_snapshots)}")
        print(f"    Panics            : {len(pm.panics)}")

        print()
        print("  PHASE VELOCITIES")
        for i, ps in enumerate(pm.phase_snapshots):
            m = ps.metrics
            ph = ps.phase.value.ljust(18)
            print(f"    [{i}] {ph} cycle={ps.cycle}"
                  f"  eV={m.entropy_velocity:.6f}"
                  f"  gO={m.governance_oscillation_velocity:.6f}"
                  f"  cD={m.confidence_drift_velocity:.6f}"
                  f"  rD={m.replay_divergence_velocity:.6f}"
                  f"  rL={m.recovery_latency_slope:.6f}")

        if pm.panics:
            print()
            print("  PANIC EVENTS")
            for i, ev in enumerate(pm.panics):
                print(f"    [{i}] {ev.panic_type.value}: cycle={ev.cycle}"
                      f"  value={ev.value:.6f}  threshold={ev.threshold}"
                      f"  phase={ev.phase}")

        if pm.final_physiology:
            ph = pm.final_physiology
            print()
            print("  FINAL PHYSIOLOGY")
            print(f"    entropy_slope       : {ph.entropy_slope:.6f}")
            print(f"    memory_plateau      : {ph.memory_plateau}")
            print(f"    recovery_cost_stable: {ph.recovery_cost_stable}")
            print(f"    governance_stable   : {ph.governance_stable}")
            print(f"    confidence_stable   : {ph.confidence_stable}")
            print(f"    stability_stable    : {ph.stability_stable}")
            print(f"    stall_free_streak   : {ph.stall_free_streak}")

        if pm.replay_report:
            rr = pm.replay_report
            print()
            print("  REPLAY INTEGRITY")
            print(f"    divergence_velocity      : {rr.divergence_velocity:.6f}")
            print(f"    hash_stability           : {rr.hash_stability}")
            print(f"    deterministic_recon_rate : {rr.deterministic_reconstruction_rate}")
            print(f"    causal_alignment_score   : {rr.causal_alignment_score}")
            print(f"    passed                   : {rr.passed}")

        print()
        print("  ALPHA-2 SUCCESS CRITERIA")
        phases = pm.phase_snapshots
        if phases:
            max_ev = max(abs(m.entropy_velocity) for m in [p.metrics for p in phases])
            max_go = max(abs(m.governance_oscillation_velocity) for m in [p.metrics for p in phases])
            max_cd = max(abs(m.confidence_drift_velocity) for m in [p.metrics for p in phases])
            max_rd = max(abs(m.replay_divergence_velocity) for m in [p.metrics for p in phases])

            print(f"    max |entropy_velocity|          : {max_ev:.6f}  (target > 0.001)")
            print(f"    max |governance_oscillation|     : {max_go:.6f}  (target 0.01-0.15)")
            print(f"    max |confidence_drift|           : {max_cd:.6f}  (target > 0.001)")
            print(f"    max |replay_divergence|          : {max_rd:.6f}  (target challenged > 0)")

        print()
        print("  RAW POSTMORTEM JSON")
        print(f"  {json.dumps(pm.to_dict(), indent=4)}")
    else:
        print("  No postmortem available (epoch crashed before postmortem phase)")

    print()
    print("=" * 60)

    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
