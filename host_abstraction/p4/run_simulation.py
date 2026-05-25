"""Run a small simulation of ExecutionArbitrationBridge + PolicyEngine
Produces human-readable output matching the requested format.
"""
from dataclasses import dataclass
import sys
import pathlib

# Ensure project root is on sys.path so local packages can be imported when
# running this script directly.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from host_abstraction.bridges.execution_bridge import ExecutionArbitrationBridge
from host_abstraction.audit import AuditLogger, AuditQueryEngine, AuditStore, AuditTracer
from host_abstraction.p4.decision_ledger import DecisionLedger
from host_abstraction.p4.execution_gate import ExecutionGate
from host_abstraction.p4.policy_engine import PolicyEngine
from host_abstraction.replay import ReplayEngine, ScenarioRunner
from host_abstraction.counterfactual import CounterfactualEngine, Intervention
from host_abstraction.runtime.action_dispatcher import ActionDispatcher
from host_abstraction.stability import StabilityEngine, StressTester


class RiskLevel:
    def __init__(self, value: str):
        self.value = value


@dataclass
class MockProposal:
    intent: str
    confidence: float
    risk_level: object


def pretty_print_ticket(ticket):
    print("==============================")
    print("EXECUTION PROPOSAL")
    print("==============================")
    print(f"intent: {ticket.proposal.intent}")
    print(f"confidence: {ticket.proposal.confidence}")
    print(f"risk: {getattr(ticket.proposal.risk_level, 'value', ticket.proposal.risk_level)}")
    print("\n------------------------------")
    print("BRIDGE VERDICT")
    print("------------------------------")
    print(ticket.bridge_verdict)
    print("\n------------------------------")
    print("P4 FINAL VERDICT")
    print("------------------------------")
    print(ticket.final_verdict.value if ticket.final_verdict is not None else ticket.final_verdict)
    print("\n------------------------------")
    print("RULE TRIGGERED")
    print("------------------------------")
    print(ticket.p4_rule)
    print("\n------------------------------")
    print("REASON")
    print("------------------------------")
    print(ticket.p4_reason)
    print()


def pretty_print_gate(record):
    print("==============================")
    print("EXECUTION GATE")
    print("==============================")
    print(f"action: {record['action']}")
    print(f"risk: {record['risk']}")
    print(f"rule: {record['rule']}")
    print(f"reason: {record['reason']}")
    print()


def run_cases():
    ledger = DecisionLedger(path=str(pathlib.Path(__file__).resolve().parents[3] / "p4_ledger.log"))
    engine = PolicyEngine()
    gate = ExecutionGate()
    bridge = ExecutionArbitrationBridge(policy_engine=engine, ledger=ledger)

    audit_store = AuditStore()
    tracer = AuditTracer()
    audit_logger = AuditLogger(store=audit_store, printer=print)
    audit_query = AuditQueryEngine(audit_store)

    cases = [
        MockProposal(intent="analyze_code", confidence=0.62, risk_level=RiskLevel('medium')),
        MockProposal(intent="deploy_prod", confidence=0.92, risk_level=RiskLevel('critical')),
        MockProposal(intent="refactor_module", confidence=0.30, risk_level=RiskLevel('low')),
        MockProposal(intent="run_tests", confidence=0.50, risk_level=RiskLevel('high')),
    ]

    dispatcher = ActionDispatcher(logger=print)

    for p in cases:
        trace_id = tracer.start_trace()
        audit_logger.log(tracer.create_event(
            layer="HAL",
            event_type="proposal",
            entity_id="intent_engine",
            payload={
                "intent": p.intent,
                "confidence": p.confidence,
                "risk_level": getattr(p.risk_level, 'value', p.risk_level),
            },
        ))

        ticket = bridge.submit_proposal(p)
        audit_logger.log(tracer.create_event(
            layer="Bridge",
            event_type="observation",
            entity_id="execution_bridge",
            payload={
                "bridge_verdict": ticket.bridge_verdict,
                "final_verdict": ticket.final_verdict.value if ticket.final_verdict is not None else None,
                "rule_triggered": ticket.p4_rule,
            },
        ))

        policy_result = engine.evaluate(ticket)
        audit_logger.log(tracer.create_event(
            layer="P4",
            event_type="decision",
            entity_id="policy_engine",
            payload={
                "verdict": policy_result.final_verdict.value,
                "risk": policy_result.risk_score,
                "rule": policy_result.rule_triggered,
                "override_bridge": policy_result.override_bridge,
            },
        ))

        gate_result = gate.apply(ticket, policy_result)
        audit_logger.log(tracer.create_event(
            layer="Gate",
            event_type="evaluation",
            entity_id="execution_gate",
            payload={
                "action": gate_result["action"],
                "risk": gate_result["risk"],
                "rule": gate_result["rule"],
            },
        ))

        pretty_print_ticket(ticket)
        pretty_print_gate(gate_result)

        runtime_action = dispatcher.dispatch(ticket, policy_result, gate_result)
        audit_logger.log(tracer.create_event(
            layer="Runtime",
            event_type="dispatch",
            entity_id="dispatcher",
            payload={
                "action": runtime_action.value,
            },
        ))

        print("==============================")
        print("RUNTIME DISPATCH RESULT")
        print("==============================")
        print(runtime_action)
        print()

    # show ledger entries written
    print("Ledger entries:")
    for entry in ledger.load_all():
        print(entry)

    # show one trace summary for the last trace
    if audit_store.events:
        trace_id = audit_store.events[-1].correlation_id
        summary = audit_query.summary(trace_id)
        print("\nAudit trace summary:")
        for event in summary["events"]:
            print(event)

        anomalies = audit_query.detect_anomalies()
        print("\nDetected high-risk anomalies:")
        for anomaly in anomalies:
            print(f"{anomaly.layer} {anomaly.event_type} {anomaly.payload}")

        replay_engine = ReplayEngine(audit_store)
        scenario_runner = ScenarioRunner()
        counterfactual = CounterfactualEngine()
        stability_engine = StabilityEngine()
        stress_tester = StressTester()

        print("\nReplaying the last trace from audit store...")
        replay_data = replay_engine.replay(trace_id)

        def pipeline_executor(payload):
            replay_proposal = MockProposal(
                intent=payload.get("intent"),
                confidence=payload.get("confidence", 0.0),
                risk_level=RiskLevel(payload.get("risk_level", "low")),
            )
            local_engine = PolicyEngine()
            local_gate = ExecutionGate()
            local_bridge = ExecutionArbitrationBridge(policy_engine=local_engine)
            local_dispatcher = ActionDispatcher(logger=print)

            local_ticket = local_bridge.submit_proposal(replay_proposal)
            local_policy_result = local_engine.evaluate(local_ticket)
            local_gate_result = local_gate.apply(local_ticket, local_policy_result)
            local_runtime_action = local_dispatcher.dispatch(local_ticket, local_policy_result, local_gate_result)

            return {
                "proposal_intent": replay_proposal.intent,
                "confidence": replay_proposal.confidence,
                "risk_level": getattr(replay_proposal.risk_level, "value", replay_proposal.risk_level),
                "final_verdict": local_ticket.final_verdict.value if local_ticket.final_verdict is not None else None,
                "gate_action": local_gate_result.get("action"),
                "runtime_action": local_runtime_action.value,
            }

        what_if = scenario_runner.run_what_if(
            replay_data,
            {"confidence": 0.20},
            pipeline_executor=pipeline_executor,
        )

        print("\nWhat-if scenario: confidence=0.20")
        modified_step = what_if["modified_timeline"][0] if what_if["modified_timeline"] else None
        if modified_step is not None:
            print(f"Modified HAL payload: {modified_step.payload}")
        print(f"Replay pipeline result: {what_if.get('pipeline_result')}")

        print("\nRunning counterfactual engine on the same trace...")
        counterfactual_result = counterfactual.run(
            replay_data["timeline"],
            Intervention(
                confidence=0.25,
                risk_level="HIGH",
                description="simulate uncertainty spike",
            ),
        )

        def extract_verdicts(timeline):
            verdicts = []
            for step in timeline:
                layer = getattr(step, "layer", None) or step.get("stage")
                event_type = getattr(step, "event_type", None) or step.get("event_type")
                if layer == "P4" and event_type == "decision":
                    payload = getattr(step, "payload", None) or step.get("payload", {})
                    if isinstance(payload, dict) and payload.get("verdict"):
                        verdicts.append(payload["verdict"])
            return verdicts

        baseline_verdicts = extract_verdicts(replay_data["timeline"])
        counterfactual_verdicts = extract_verdicts(counterfactual_result["mutated"])

        stability_score = stability_engine.assess(baseline_verdicts, counterfactual_verdicts)
        print("\nStability assessment:")
        print(f"score: {stability_score.score:.3f}")
        print(f"variance: {stability_score.variance:.3f}")
        print(f"confidence: {stability_score.confidence:.3f}")
        print(f"interpretation: {stability_score.interpretation}")

        print("\nStress testing the counterfactual pipeline...")
        stress_results = stress_tester.run(counterfactual, replay_data["timeline"], pipeline_executor=pipeline_executor)
        for result in stress_results:
            summary = result["pipeline_result"] or {}
            print(f"- intervention={result['intervention']}, verdict={summary.get('final_verdict')}")


if __name__ == '__main__':
    run_cases()
