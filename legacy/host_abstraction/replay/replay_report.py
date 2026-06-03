from typing import Any, Dict


class ReplayReport:
    def generate(self, reconstructed: Dict[str, Any]) -> None:
        timeline = reconstructed.get("timeline", [])
        snapshots = reconstructed.get("snapshots", {})

        print("\n==============================")
        print("🧠 REPLAY REPORT")
        print("==============================")

        for idx, step in enumerate(timeline, start=1):
            print(f"\nSTEP {idx}")
            print(f"layer: {step.layer}")
            print(f"type: {step.event_type}")
            print(f"entity: {step.entity_id}")
            print(f"timestamp: {step.timestamp}")
            print(f"payload: {step.payload}")

        print("\n------------------------------")
        print("SUMMARY")
        for key in ["proposal", "arbitration", "policy_result", "gate_result", "runtime_dispatch"]:
            entry = snapshots.get(key)
            if entry is not None:
                print(f"{key}: {entry['payload']}")

        final_state = reconstructed.get("final_state")
        if final_state is not None:
            print("\nFINAL STATE")
            print(f"{final_state.layer} {final_state.event_type} {final_state.payload}")

        print("\nReplay completed successfully")
