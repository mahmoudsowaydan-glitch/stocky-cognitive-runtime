"""ArchitectureReportCapability — inspect repo structure and summarize modules."""

import os

from ..contracts.execution_contract import ExecutionProposal, PolicyDecision

NAME = "generate_architecture_report"


async def execute(proposal: ExecutionProposal, decision: PolicyDecision) -> dict:
    target = proposal.target or "."
    max_depth = min(proposal.params.get("max_depth", 3), 5)

    try:
        if not os.path.isdir(target):
            return {"error": f"Not a directory: {target}", "status": "FAILED"}

        layout = _walk(target, max_depth)

        py_files = sum(1 for root, _, files in os.walk(target) for f in files if f.endswith(".py"))
        md_files = sum(1 for root, _, files in os.walk(target) for f in files if f.endswith(".md"))
        total_dirs = sum(1 for root, _, _ in os.walk(target))

        return {
            "target": os.path.abspath(target),
            "total_python_modules": py_files,
            "total_document_files": md_files,
            "total_directories": total_dirs,
            "layout": layout,
            "status": "SUCCESS",
        }
    except Exception as e:
        return {"target": target, "error": str(e), "status": "FAILED"}


def _walk(path: str, depth: int) -> list:
    if depth <= 0:
        return []
    try:
        entries = sorted(os.listdir(path))
    except PermissionError:
        return [{"path": path, "error": "permission_denied"}]

    nodes = []
    for e in entries:
        if e.startswith(".") or e == "__pycache__":
            continue
        full = os.path.join(path, e)
        if os.path.isdir(full):
            children = _walk(full, depth - 1)
            nodes.append({"name": e, "type": "directory", "children": children})
        elif e.endswith(".py") or e.endswith(".md"):
            nodes.append({"name": e, "type": "file"})
    return nodes
