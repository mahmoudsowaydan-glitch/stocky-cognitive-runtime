"""Federation Stage 1.5 — Asymmetric Observation.
Node A = Executor, Node B = Observer.
Measures Observer Drift: can one node observe another without corrupting reality?
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cognitive_runtime.epoch import (
    AsymmetricFederatedRuntime, LivingEpoch, EpochPhase, PanicConfig,
)


STAGE = "FED-1.5"
OUT_DIR = ".alpha"


def extract_phase_velocities(report):
    """Extract velocity metrics per phase from the epoch report postmortem."""
    if not report.postmortem:
        return {}
    snaps = getattr(report.postmortem, 'phase_snapshots', [])
    result = {}
    for ps in snaps:
        phase_name = ps.phase.value if hasattr(ps.phase, 'value') else str(ps.phase)
        result[phase_name] = {
            "entropy_velocity": getattr(ps.metrics, 'entropy_velocity', None),
            "confidence_velocity": getattr(ps.metrics, 'confidence_velocity', None),
            "stability_velocity": getattr(ps.metrics, 'stability_velocity', None),
        }
    return result


def main():
    # Run the asymmetric epoch
    epoch = LivingEpoch(
        seed=42,
        runtime_factory=lambda: AsymmetricFederatedRuntime.factory(
            seed=42, capture_interval=50,
        ),
        capture_interval=50,
        panic_config=PanicConfig(
            oscillation_explosion_threshold=0.5,
            entropy_runaway_threshold=5.0,
        ),
        phase_cycle_limits={
            EpochPhase.WARMUP: 200,
            EpochPhase.STABILIZATION: 300,
            EpochPhase.CHAOS: 500,
            EpochPhase.RECOVERY: 300,
            EpochPhase.OBSERVATION: 300,
            EpochPhase.SHUTDOWN: 10,
            EpochPhase.RECOVERY_BOOT: 10,
            EpochPhase.REPLAY_VALIDATION: 20,
        },
        enable_chaos=True,
        replay_challenge_mode="none",
    )
    report = epoch.run()

    # Extract drift metrics from the asymmetric runtime
    runtime = epoch._runtime
    drift_history = runtime.observer_drift_history if hasattr(runtime, 'observer_drift_history') else []
    consensus_history = runtime.consensus_history if hasattr(runtime, 'consensus_history') else []

    # Compute summary statistics
    gov_drifts = [d["governance_drift"] for d in drift_history]
    stab_drifts = [d["stability_drift"] for d in drift_history]
    conf_drifts = [d["confidence_drift"] for d in drift_history]
    strengths = [d["consensus_strength"] for d in drift_history]

    avg_gov_drift = sum(gov_drifts) / len(gov_drifts) if gov_drifts else 0
    avg_stab_drift = sum(stab_drifts) / len(stab_drifts) if stab_drifts else 0
    avg_conf_drift = sum(conf_drifts) / len(conf_drifts) if conf_drifts else 0
    max_gov_drift = max(gov_drifts) if gov_drifts else 0
    avg_strength = sum(strengths) / len(strengths) if strengths else 0

    # Determine pass/fail
    observer_drift_pass = avg_gov_drift < 0.15
    consensus_pass = avg_strength >= 0.70
    panic_pass = not report.postmortem or len(report.postmortem.panics) == 0
    overall_pass = observer_drift_pass and consensus_pass and panic_pass

    # Print results
    print("=" * 60)
    print(f"  FEDERATION STAGE 1.5 — ASYMMETRIC OBSERVATION")
    print("=" * 60)
    print(f"  Status: {'PASS' if overall_pass else 'FAIL'}")
    print(f"  Cycles: {report.message}")
    print(f"  Panics: {len(report.postmortem.panics) if report.postmortem else 'N/A'}")
    print()
    print("  OBSERVER DRIFT")
    print(f"    Governance drift (avg): {avg_gov_drift:.6f}  {'PASS' if observer_drift_pass else 'FAIL'}  (threshold < 0.15)")
    print(f"    Governance drift (max): {max_gov_drift:.6f}")
    print(f"    Stability drift (avg):  {avg_stab_drift:.6f}")
    print(f"    Confidence drift (avg): {avg_conf_drift:.6f}")
    print()
    print("  CONSENSUS")
    print(f"    Avg consensus strength:  {avg_strength:.6f}  {'PASS' if consensus_pass else 'FAIL'}  (threshold >= 0.70)")
    print()
    print(f"  PANICS: 0  {'PASS' if panic_pass else 'FAIL'}")
    print("=" * 60)

    # Build result dictionary
    result = {
        "stage": STAGE,
        "status": "PASS" if overall_pass else "FAIL",
        "cycles": len(drift_history),
        "panics": len(report.postmortem.panics) if report.postmortem else 0,
        "observer_drift": {
            "governance_avg": round(avg_gov_drift, 6),
            "governance_max": round(max_gov_drift, 6),
            "stability_avg": round(avg_stab_drift, 6),
            "confidence_avg": round(avg_conf_drift, 6),
        },
        "consensus": {
            "avg_strength": round(avg_strength, 6),
        },
        "phase_velocities": extract_phase_velocities(report),
        "message": report.message,
    }

    # Save result
    out_path = os.path.join(OUT_DIR, "fed_result_15.json")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"  Saved to: {out_path}")

    # Show phase velocities
    print()
    print("  PHASE VELOCITIES")
    for pname, pdata in result["phase_velocities"].items():
        print(f"    {pname}: {pdata}")
    print("=" * 60)

    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
