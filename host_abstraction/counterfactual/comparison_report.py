from typing import List, Dict, Any


class ComparisonReport:
    def compare(self, original: List[Dict[str, Any]], mutated: List[Dict[str, Any]]) -> Dict[str, Any]:
        print("\n==============================")
        print("🧠 COUNTERFACTUAL ANALYSIS")
        print("==============================")

        print("\n📌 ORIGINAL PATH:")
        for step in original:
            print(f"- {step.layer if hasattr(step, 'layer') else step.get('stage')} -> {step.payload if hasattr(step, 'payload') else step.get('payload')}")

        print("\n📌 COUNTERFACTUAL PATH:")
        for step in mutated:
            print(f"- {step['stage']} -> {step['payload']}")

        print("\n" + "=" * 30)
        print("Comparison complete")

        return {
            "original": original,
            "mutated": mutated,
        }
