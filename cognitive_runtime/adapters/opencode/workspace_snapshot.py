import os
import time
from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class WorkspaceSnapshot:
    root_path: str = ""
    open_files: Tuple[str, ...] = ()
    selected_file: str = ""
    cursor_line: int = 0
    cursor_column: int = 0
    collected_at: float = 0.0

    @classmethod
    def capture(
        cls,
        root_path: str,
        open_files: Tuple[str, ...] = (),
        selected_file: str = "",
        cursor_line: int = 0,
        cursor_column: int = 0,
    ) -> "WorkspaceSnapshot":
        return cls(
            root_path=os.path.abspath(root_path),
            open_files=tuple(open_files),
            selected_file=selected_file,
            cursor_line=cursor_line,
            cursor_column=cursor_column,
            collected_at=time.time(),
        )
