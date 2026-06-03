"""RepositoryCapability — scan, discover, and summarize source repositories."""

import os

from ..contracts.execution_contract import ExecutionProposal, PolicyDecision

NAME = "analyze_repository"


async def execute(proposal: ExecutionProposal, decision: PolicyDecision) -> dict:
    target = proposal.target or "."
    try:
        if not os.path.isdir(target):
            return {"error": f"Not a directory: {target}", "status": "FAILED"}

        all_entries = sorted(os.listdir(target))
        files = [e for e in all_entries if os.path.isfile(os.path.join(target, e))]
        dirs = [e for e in all_entries if os.path.isdir(os.path.join(target, e))]
        by_ext = {}
        for f in files:
            ext = os.path.splitext(f)[1] or "(no_ext)"
            by_ext[ext] = by_ext.get(ext, 0) + 1

        return {
            "path": os.path.abspath(target),
            "total_entries": len(all_entries),
            "files": len(files),
            "directories": len(dirs),
            "files_by_extension": by_ext,
            "entries": all_entries[:30],
            "status": "SUCCESS",
        }
    except Exception as e:
        return {"path": target, "error": str(e), "status": "FAILED"}
