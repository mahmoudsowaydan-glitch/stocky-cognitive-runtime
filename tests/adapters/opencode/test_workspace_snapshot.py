import os
import time
from cognitive_runtime.adapters.opencode.workspace_snapshot import (
    WorkspaceSnapshot,
)


class TestWorkspaceSnapshot:
    def test_default_construction(self):
        ws = WorkspaceSnapshot()
        assert ws.root_path == ""
        assert ws.open_files == ()
        assert ws.selected_file == ""
        assert ws.cursor_line == 0
        assert ws.cursor_column == 0
        assert ws.collected_at == 0.0

    def test_capture_creates_snapshot(self):
        ws = WorkspaceSnapshot.capture(".")
        assert ws.root_path == os.path.abspath(".")
        assert ws.collected_at > 0
        assert isinstance(ws.open_files, tuple)

    def test_capture_with_open_files(self):
        ws = WorkspaceSnapshot.capture(
            ".", open_files=("a.py", "b.py")
        )
        assert "a.py" in ws.open_files
        assert len(ws.open_files) == 2

    def test_capture_with_cursor(self):
        ws = WorkspaceSnapshot.capture(
            ".", cursor_line=10, cursor_column=5
        )
        assert ws.cursor_line == 10
        assert ws.cursor_column == 5

    def test_capture_pure_function(self):
        ws1 = WorkspaceSnapshot.capture(
            ".", open_files=("x.py",)
        )
        ws2 = WorkspaceSnapshot.capture(
            ".", open_files=("x.py",)
        )
        assert ws1.root_path == ws2.root_path
        assert ws1.open_files == ws2.open_files

    def test_no_git_branch(self):
        ws = WorkspaceSnapshot.capture(".")
        assert not hasattr(ws, "git_branch")

    def test_frozen_immutable(self):
        ws = WorkspaceSnapshot()
        import dataclasses
        assert dataclasses.is_dataclass(ws)
        assert ws.__dataclass_params__.frozen
