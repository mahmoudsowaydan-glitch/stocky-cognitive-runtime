"""
runtime_loop.py â€” Core Activation Engine.

Runs the full cognitive pipeline continuously:
  EventQueue -> P3 -> Preflight -> P4 -> Sandbox -> ExecutionTrace -> CausalGraph -> HAL

Invariants:
  - P4 is single authority (never overridden)
  - Sandbox is execution boundary only (no thinking)
  - CausalGraph is observational only
  - Feedback is advisory only (never influences execution)
  - Recovery replaces state, never re-executes side effects
  - No event processing during recovery/replay (INV-REC-001)
"""

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from ..contracts.causal_graph import CausalGraph, CausalGraphBuilder
from ..contracts.execution_contract import (
    Capability,
    ExecutionProposal,
    ExecutionResult,
    HostEvent,
    PolicyDecision,
)
from ..contracts.execution_trace import ExecutionTrace, ExecutionTraceNormalizer
from ..sandbox.preflight_analyzer import PreflightAnalyzer, PreflightResult
from ..sandbox.sandbox_pool import SandboxPool
from ..substrate.event_queue import EventQueue
from ..substrate.observation_tap import ObservationTap
from ..intelligence.compression_engine import CompressionEngine, CompressionReport
from ..stability.stability_analyzer import StabilityAnalyzer
from ..confidence.runtime_confidence import RuntimeConfidenceEngine
from ..governance.governance_engine import GovernanceEngine
from ..recovery.recovery_coordinator import RecoveryCoordinator
from ..recovery.checkpoint_manager import CheckpointManager
from ..recovery.delta_checkpoint import DeltaCheckpointManager
from ..recovery.runtime_snapshot import RuntimeSnapshot
from ..contracts.frozen.compatibility_guard import CompatibilityGuard
from ..contracts.frozen.schema_version import FROZEN_SCHEMA_VERSION
from .coherence_monitor import CoherenceMonitor, CoherenceReport
from .trace_window import TraceWindow
from .feedback_bridge import FeedbackBridge, FeedbackReport
from ..liveness.liveness_monitor import NullLivenessMonitor
from ..telemetry.telemetry_probe import NullTelemetryProbe
from .runtime_orchestrator import RuntimeOrchestrator, Heartbeat
from .runtime_state import RuntimeState


class RuntimeLoop:
    def __init__(self, queue: EventQueue, tap: ObservationTap,
                 p3_context_builder: Callable,
                 sandbox_pool: SandboxPool,
                 preflight: Optional[PreflightAnalyzer] = None,
                 p4_authority: Optional[Callable] = None,
                 causal_builder: Optional[CausalGraphBuilder] = None,
                 trace_normalizer: Optional[ExecutionTraceNormalizer] = None,
                 hal_observer: Optional[Callable] = None,
                  trace_window_size: int = 1000,
                  liveness_monitor: Optional[NullLivenessMonitor] = None,
                  telemetry_probe: Optional[NullTelemetryProbe] = None):
        self._queue = queue
        self._tap = tap
        self._p3 = p3_context_builder
        self._pool = sandbox_pool
        self._p4 = p4_authority
        self._preflight = preflight or PreflightAnalyzer()
        self._causal_builder = causal_builder or CausalGraphBuilder()
        self._trace_normalizer = trace_normalizer or ExecutionTraceNormalizer()
        self._hal = hal_observer
        self._liveness = liveness_monitor or NullLivenessMonitor()
        self._telemetry = telemetry_probe or NullTelemetryProbe()

        self._state = RuntimeState()
        self._orchestrator = RuntimeOrchestrator(
            self._state,
            on_heartbeat=self._on_heartbeat,
        )
        self._coherence = CoherenceMonitor()
        self._feedback = FeedbackBridge()
        self._traces: TraceWindow = TraceWindow(max_active=trace_window_size)
        self._causal_graph = CausalGraph({}, [])
        self._compression = CompressionEngine()
        self._stability = StabilityAnalyzer(self._compression.store)
        self._confidence = RuntimeConfidenceEngine()
        self._governance = GovernanceEngine()
        self._last_stability_score: Optional[float] = None

        # Phase 7.5 — Contract freezing verification at construction
        self._contract_guard = CompatibilityGuard(
            schema_version=FROZEN_SCHEMA_VERSION,
            hal_observer=self._hal,
        )
        self._verify_contracts()

        # Phase 8 — Persistence & Recovery
        self._checkpoint_manager = DeltaCheckpointManager(
            checkpoint_dir="",
            base_interval=500,
            delta_interval=100,
            max_bases=3,
            enabled=True,
        )
        self._recovery_coordinator = RecoveryCoordinator(
            checkpoint_manager=self._checkpoint_manager,
            compatibility_guard=self._contract_guard,
            hal_observer=self._hal,
        )
        self._last_checkpoint_cycle = 0
        self._recovery_completed = False

    # â”€â”€ Contract Verification â”€â”€

    def _verify_contracts(self) -> None:
        # Schema-level contract verification
        result = self._contract_guard.run_all(self)
        if not result["passed"]:
            if self._hal:
                self._hal({
                    "type": "contract.verification",
                    "schema_version": result["schema_version"],
                    "violations_found": result["violations_found"],
                    "total_violations": result["total_violations"],
                    "passed": result["passed"],
                })
            for v in self._contract_guard.violations:
                self._state.record_error(
                    f"contract.{v['component']}: {v['message']}"
                )

        # Doctrine runtime safety verification — FROZEN_RUNTIME_SAFETY failures refuse startup
        from ..contracts.frozen.doctrine_runtime_guard import DoctrineRuntimeGuard
        drg = DoctrineRuntimeGuard()
        dr_report = drg.verify_all(self)
        if dr_report.violations:
            safety_violations = [v for v in dr_report.violations
                                 if v.severity == "FROZEN_RUNTIME_SAFETY"]
            if safety_violations:
                msg = "; ".join(f"{v.invariant_id}: {v.details}" for v in safety_violations)
                raise RuntimeError(
                    f"STARTUP_REFUSED: {len(safety_violations)} FROZEN_RUNTIME_SAFETY "
                    f"violations: {msg}"
                )

    # â”€â”€ Lifecycle â”€â”€

    async def run(self) -> None:
        # Phase 8 — Crash recovery at startup
        if not self._recovery_completed:
            report = self._recovery_coordinator.recover(self)
            self._recovery_completed = True
            if self._hal:
                self._hal({
                    "type": "startup.recovery",
                    "recovery_mode": report.recovery_mode,
                    "restored_cycles": report.restored_cycles,
                    "replay_valid": report.replay_valid,
                    "corruption_detected": report.corruption_detected,
                })

        self._orchestrator.start()
        self._queue.open()

        while self._orchestrator.is_running:
            self._liveness.on_cycle_start(time.time())
            event = self._queue.pop()
            if event is None:
                self._liveness.on_idle()
                await asyncio.sleep(0.1)
                if self._orchestrator.state.total_events_processed % 10 == 0:
                    self._orchestrator.tick_heartbeat()
                self._liveness.on_cycle_end(time.time())
                continue

            self._liveness.on_event_received()
            start_time = time.time()
            success = False
            try:
                await self._process_event(event)
                success = True
            except Exception as e:
                self._state.record_error(str(e))
                if self._hal:
                    try:
                        self._hal({"type": "runtime.error", "event_id": getattr(event, 'event_id', 'unknown'), "error": str(e)})
                    except Exception:
                        pass
                await asyncio.sleep(0)

            duration_ms = (time.time() - start_time) * 1000
            self._state.record_cycle(duration_ms, success, self._queue.queue_depth)
            self._orchestrator.tick_heartbeat()
            self._liveness.on_cycle_end(time.time())

        self._queue.close()

    async def _process_event(self, event: HostEvent) -> None:
        # INV-REC-001: No event processing during recovery/replay
        if self._recovery_coordinator.recovery_in_progress:
            raise RuntimeError("Replay protection: event processing blocked during recovery")
        if self._hal:
            self._hal({"type": "event.received", "event_id": event.event_id})

        # â”€â”€ Stage 1: P3 Context Builder â”€â”€
        self._liveness.on_await_start("p3", event.event_id, time.time())
        proposal: ExecutionProposal = await self._p3(event)
        self._liveness.on_await_end("p3", event.event_id, time.time())
        self._tap.tap_event_received(event)
        self._tap.tap_p3_proposal(event.event_id, proposal)

        # â”€â”€ Stage 2: Preflight Analyzer â”€â”€
        preflight_result: PreflightResult = self._preflight.analyze(proposal)
        if not preflight_result.valid:
            self._tap.tap_blocked(event.event_id, preflight_result.reason)
            trace = self._build_trace(event, proposal, preflight_result, None, None, start_time=time.time())
            self._finalize_cycle(trace)
            return

        # â”€â”€ Stage 3: P4 Policy Authority (single authority) â”€â”€
        self._liveness.on_await_start("p4", proposal.proposal_id, time.time())
        decision: PolicyDecision = await self._p4(proposal)
        self._liveness.on_await_end("p4", proposal.proposal_id, time.time())
        self._queue.record_decision(decision)
        self._tap.tap_p4_decision(event.event_id, decision)

        # â”€â”€ Stage 4: Sandbox Execution â”€â”€
        if decision.verdict == "ALLOW":
            self._liveness.on_await_start("sandbox", decision.decision_id, time.time())
            result: ExecutionResult = await self._pool.execute(proposal, decision)
            self._liveness.on_await_end("sandbox", decision.decision_id, time.time())
            self._queue.ack(event.event_id, result)
            self._tap.tap_execution_result(event.event_id, result)
        else:
            reason = f"P4_blocked: {decision.verdict} - {decision.reason}"
            self._queue.nack(event.event_id, reason, proposal=proposal)
            self._tap.tap_blocked(event.event_id, reason)
            result = ExecutionResult(
                execution_id="", proposal_id=proposal.proposal_id,
                session_id=event.session_id, status="FAILED",
                output=None, error=reason,
                started_at=time.time(), finished_at=time.time(),
            )

        # â”€â”€ Stage 5: Build Canonical Trace â”€â”€
        trace = self._build_trace(event, proposal, preflight_result, decision, result, start_time=time.time())
        self._finalize_cycle(trace)

    # â”€â”€ Trace & Graph Building â”€â”€

    def _build_trace(self, event: HostEvent, proposal: ExecutionProposal,
                     preflight: PreflightResult,
                     decision: Optional[PolicyDecision],
                     result: Optional[ExecutionResult],
                     start_time: float) -> ExecutionTrace:
        now = time.time()
        raw = {
            "event_id": event.event_id,
            "session_id": event.session_id,
            "sequence_no": 1,
            "correlation_id": str(uuid.uuid4()),
            "risk_score": preflight.risk_score,
            "preflight": {
                "valid": preflight.valid,
                "reason": preflight.reason,
                "rules": preflight.triggered_rules,
            },
            "p4": {
                "verdict": decision.verdict if decision else "BLOCKED_BY_PREFLIGHT",
                "reason": decision.reason if decision else preflight.reason,
                "risk_level": decision.risk_level if decision else "",
                "rule_triggered": decision.rule_triggered if decision else None,
            },
            "sandbox": {
                "status": result.status if result else "",
                "error": result.error if result else None,
                "capabilities": [c.value if hasattr(c, 'value') else c for c in proposal.required_capabilities],
                "resource_usage": {},
            },
            "timing": {
                "preflight": now - start_time,
                "p4": now - start_time,
                "execution": (result.finished_at - result.started_at) if result and result.started_at else 0.0,
                "total": now - start_time,
            },
        }
        return self._trace_normalizer.normalize(raw)

    def _finalize_cycle(self, trace: ExecutionTrace) -> None:
        self._traces.append(trace)

        # Update state
        self._state.last_execution_trace_id = trace.event_id
        self._state.last_execution_status = trace.final_status
        self._state.last_execution_at = time.time()

        # Coherence check
        coherence = self._coherence.check_trace(trace)
        if coherence.drift_detected:
            self._state.drift_detected = True
            self._state.drift_count += coherence.drift_count

        # Only rebuild causal graph periodically to avoid O(n^2) on every cycle
        if len(self._traces) % 10 == 0 or len(self._traces) <= 5:
            self._causal_graph = self._causal_builder.build(self._traces.active_window)

        # Feedback analysis (advisory only)
        if len(self._traces) % 20 == 0:
            feedback = self._feedback.analyze(self._causal_graph)
            if feedback.insights and self._hal:
                self._hal({"type": "runtime.feedback", "insights": [
                    {"type": i.insight_type, "severity": i.severity,
                     "description": i.description} for i in feedback.insights
                ]})

        # Intelligence compression (read-only pattern/failure/fingerprint extraction)
        if len(self._traces) % 10 == 0 and self._traces:
            report = self._compression.process(self._causal_graph, self._traces[-10:])
            if self._hal and (report.patterns_found > 0 or report.failures_detected > 0):
                self._hal({"type": "intelligence.compression", "report": {
                    "patterns_found": report.patterns_found,
                    "failures_detected": report.failures_detected,
                    "fingerprints_built": report.fingerprints_built,
                    "total_patterns": report.total_patterns,
                    "total_failures": report.total_failures,
                    "total_fingerprints": report.total_fingerprints,
                }})

        # Stability analysis (read-only self-stability index, every 50 cycles)
        if len(self._traces) % 50 == 0 and self._traces:
            s_report = self._stability.analyze(self._traces.active_window, self._state)
            self._last_stability_score = s_report.score.overall
            if s_report.score.overall < 0.3:
                self._state.health_status = "degraded"
            if self._hal:
                self._hal({"type": "stability.report",
                           "score": s_report.score.overall,
                           "trend": s_report.trend.direction,
                           "anomalies": s_report.anomalies})

        # Confidence assessment (read-only operational confidence, every 75 cycles)
        if len(self._traces) % 75 == 0 and self._traces:
            qs = self._queue.stats
            conf_report = self._confidence.assess(
                traces=self._traces[-100:],
                state=self._state,
                queue_snapshot={
                    "queue_depth": qs.queue_depth,
                    "total_events": qs.total_events,
                    "dead_lettered": qs.dead_lettered,
                    "processed": qs.processed,
                    "failed": qs.failed,
                    "average_cycle_ms": self._state.average_cycle_ms,
                    "last_cycle_ms": self._state.last_cycle_ms,
                },
                stability_snapshot=self._last_stability_score,
            )
            if self._hal:
                self._hal({"type": "confidence.report",
                           "runtime_confidence": conf_report.score.overall,
                           "gradient": conf_report.gradient.value,
                           "decision_confidence": conf_report.score.decision_confidence,
                           "operational_confidence": conf_report.score.operational_confidence,
                           "execution_confidence": conf_report.score.execution_confidence,
                           "trend": conf_report.trend_direction,
                           "degradation_detected": conf_report.degradation_detected})

        # Governance & entropy assessment (read-only, every 100 cycles)
        if len(self._traces) % 100 == 0 and self._traces:
            try:
                gov_report = self._governance.assess(
                    traces=self._traces.active_window,
                    state=self._state,
                    graph=self._causal_graph,
                    store=self._compression.store,
                    coherence=self._coherence,
                    stability=self._stability,
                    confidence=self._confidence,
                )
                if self._hal:
                    self._hal({"type": "governance.report",
                               "governance_score": gov_report.score,
                               "status": gov_report.governance_status,
                               "entropy": gov_report.entropy.overall,
                               "drift": gov_report.drift.overall,
                               "pressure": gov_report.pressure.overall,
                               "decay_signals": [
                                   {"type": s.signal_type, "severity": s.severity,
                                    "description": s.description}
                                   for s in gov_report.decay_signals
                               ],
                               "trend": gov_report.trend_direction})
            except Exception as gov_err:
                if self._hal:
                    self._hal({"type": "governance.error",
                               "error": str(gov_err)})

        # Phase 8 — Checkpoint every 100 cycles
        if (len(self._traces) % 100 == 0 and self._traces
                and self._checkpoint_manager.enabled
                and not self._recovery_coordinator.recovery_in_progress):
            try:
                snap = RuntimeSnapshot.capture(self)
                gov_status = ""
                if hasattr(self._governance, "_score_history") and self._governance._score_history:
                    from ..governance.governance_engine import GovernanceEngine
                    last_score = self._governance._score_history[-1]
                    if last_score >= 0.7:
                        gov_status = "CRITICAL"
                    elif last_score >= 0.5:
                        gov_status = "ELEVATED"
                    elif last_score >= 0.3:
                        gov_status = "MONITORING"
                    else:
                        gov_status = "NOMINAL"
                self._checkpoint_manager.save(
                    snap,
                    health_status=self._state.health_status,
                    governance_status=gov_status,
                )
                self._last_checkpoint_cycle = len(self._traces)
            except Exception as cp_err:
                if self._hal:
                    self._hal({"type": "checkpoint.error",
                               "error": str(cp_err)})

        # Telemetry capture (every N cycles, probe handles interval)
        self._telemetry.capture(self)

        # HAL observation
        if self._hal:
            self._hal({
                "type": "cycle.completed",
                "trace_id": trace.event_id,
                "final_status": trace.final_status,
                "drift": coherence.drift_detected,
            })

    # â”€â”€ Control â”€â”€

    def stop(self) -> None:
        self._orchestrator.stop()

    def pause(self) -> None:
        self._orchestrator.pause()

    def resume(self) -> None:
        self._orchestrator.resume()

    # â”€â”€ Properties â”€â”€

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def orchestrator(self) -> RuntimeOrchestrator:
        return self._orchestrator

    @property
    def coherence(self) -> CoherenceMonitor:
        return self._coherence

    @property
    def feedback(self) -> FeedbackBridge:
        return self._feedback

    @property
    def causal_graph(self) -> CausalGraph:
        return self._causal_graph

    @property
    def stability(self) -> StabilityAnalyzer:
        return self._stability

    @property
    def compression(self) -> CompressionEngine:
        return self._compression

    @property
    def confidence(self) -> RuntimeConfidenceEngine:
        return self._confidence

    @property
    def governance(self) -> GovernanceEngine:
        return self._governance

    @property
    def traces(self) -> List[ExecutionTrace]:
        return self._traces.active_window

    @property
    def liveness(self) -> NullLivenessMonitor:
        return self._liveness

    @property
    def telemetry(self) -> NullTelemetryProbe:
        return self._telemetry

    def _on_heartbeat(self, hb: Heartbeat) -> None:
        self._liveness.on_heartbeat(time.time())

    @property
    def is_running(self) -> bool:
        return self._orchestrator.is_running

