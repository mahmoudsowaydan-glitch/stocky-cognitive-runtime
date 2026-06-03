"""TestExecutionCapability — discover and inventory pytest tests (read-only)."""

import os

from ..contracts.execution_contract import ExecutionProposal, PolicyDecision

NAME = "discover_tests"


async def execute(proposal: ExecutionProposal, decision: PolicyDecision) -> dict:
    target = proposal.target or "."
    params = proposal.params
    match_pattern = params.get("test_pattern", "test_*.py")
    max_report = min(params.get("max_report", 200), 500)

    try:
        if not os.path.isdir(target):
            return {"error": f"Not a directory: {target}", "status": "FAILED"}

        test_files = []
        test_count = 0
        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for f in sorted(files):
                if f.startswith("test_") and f.endswith(".py"):
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, target)
                    func_count = 0
                    with open(full, "r", encoding="utf-8", errors="replace") as fh:
                        for line in fh:
                            if line.strip().startswith("async def test_") or line.strip().startswith("def test_"):
                                func_count += 1
                    test_files.append({"file": rel, "test_functions": func_count})
                    test_count += func_count

        test_files.sort(key=lambda x: x["file"])
        truncated = len(test_files) > max_report

        return {
            "target": os.path.abspath(target),
            "total_test_files": len(test_files),
            "total_test_functions": test_count,
            "test_files": test_files[:max_report],
            "truncated": truncated,
            "status": "SUCCESS",
        }
    except Exception as e:
        return {"target": target, "error": str(e), "status": "FAILED"}
