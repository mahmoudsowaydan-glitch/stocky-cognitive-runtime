"""
capabilities/count.py — Line/file counting provider.
Counts total lines and files matching a glob pattern.
"""

import glob
import os

from ..contracts.execution_contract import ExecutionProposal, PolicyDecision


async def count_worker(proposal: ExecutionProposal, decision: PolicyDecision) -> dict:
    target = proposal.target or "."
    pattern = proposal.params.get("pattern", "*")
    try:
        search_path = os.path.join(target, pattern) if not os.path.isabs(pattern) else pattern
        matches = sorted(glob.glob(search_path, recursive=True))
        files = [m for m in matches if os.path.isfile(m)]
        total_lines = 0
        total_bytes = 0
        per_file = []
        for f in files[:100]:
            try:
                with open(f, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                lines = content.count("\n") + 1
                size = len(content)
                total_lines += lines
                total_bytes += size
                per_file.append({"path": f, "lines": lines, "size": size})
            except Exception:
                per_file.append({"path": f, "lines": 0, "size": 0})
        return {
            "pattern": pattern,
            "search_root": os.path.abspath(target),
            "total_files_matched": len(files),
            "total_files_read": min(len(files), 100),
            "total_lines": total_lines,
            "total_bytes": total_bytes,
            "per_file": per_file,
            "status": "SUCCESS",
        }
    except Exception as e:
        return {"pattern": pattern, "search_root": target, "error": str(e), "status": "FAILED"}
