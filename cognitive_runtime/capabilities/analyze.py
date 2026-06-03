"""
capabilities/analyze.py — Repository analyzer provider.
Walks directories or reads files, returns structured metadata.
"""

import os

from ..contracts.execution_contract import ExecutionProposal, PolicyDecision


async def analyze_worker(proposal: ExecutionProposal, decision: PolicyDecision) -> dict:
    target = proposal.target or "."
    try:
        if os.path.isdir(target):
            entries = sorted(os.listdir(target))
            file_count = sum(1 for e in entries if os.path.isfile(os.path.join(target, e)))
            dir_count = sum(1 for e in entries if os.path.isdir(os.path.join(target, e)))
            return {
                "path": os.path.abspath(target),
                "total_entries": len(entries),
                "files": file_count,
                "directories": dir_count,
                "entries": entries[:20],
                "status": "SUCCESS",
            }
        elif os.path.isfile(target):
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return {
                "path": os.path.abspath(target),
                "size": len(content),
                "lines": content.count("\n") + 1,
                "status": "SUCCESS",
            }
        else:
            return {"path": target, "error": "path_not_found", "status": "FAILED"}
    except Exception as e:
        return {"path": target, "error": str(e), "status": "FAILED"}
