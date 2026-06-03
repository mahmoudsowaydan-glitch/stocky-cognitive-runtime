"""SearchCapability — search files by name, extension, and glob pattern."""

import glob
import os

from ..contracts.execution_contract import ExecutionProposal, PolicyDecision

NAME = "search_files"


async def _execute(proposal: ExecutionProposal, decision: PolicyDecision) -> dict:
    target = proposal.target or "."
    pattern = proposal.params.get("pattern", "*")
    max_results = min(proposal.params.get("max_results", 100), 500)
    try:
        search_path = os.path.join(target, pattern) if not os.path.isabs(pattern) else pattern
        matches = sorted(glob.glob(search_path, recursive=True))
        truncated = len(matches) > max_results
        return {
            "pattern": pattern,
            "search_root": os.path.abspath(target),
            "total_matches": len(matches),
            "matches": matches[:max_results],
            "truncated": truncated,
            "status": "SUCCESS",
        }
    except Exception as e:
        return {"pattern": pattern, "error": str(e), "status": "FAILED"}


# backward-compat alias
search_worker = _execute
execute = _execute
