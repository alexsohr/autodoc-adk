"""Unit tests for cleanup_orphan_workspaces flow and cleanup_workspace task."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import pytest

from src.flows.tasks.cleanup import cleanup_orphan_workspaces, cleanup_workspace


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_temp_dir(prefix: str = "autodoc_", age_seconds: float = 0.0) -> Path:
    """Create a temporary directory and optionally back-date its mtime."""
    dir_path = tempfile.mkdtemp(prefix=prefix)
    if age_seconds > 0:
        old_time = time.time() - age_seconds
        os.utime(dir_path, (old_time, old_time))
    return Path(dir_path)


# ---------------------------------------------------------------------------
# cleanup_orphan_workspaces tests
# ---------------------------------------------------------------------------


class TestCleanupOrphanWorkspaces:
    """Tests for the cleanup_orphan_workspaces Prefect flow."""

    async def test_removes_old_directories(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Directories older than 1 hour should be removed."""
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

        old_dir = tmp_path / "autodoc_old_workspace"
        old_dir.mkdir()
        old_time = time.time() - 7200  # 2 hours ago
        os.utime(old_dir, (old_time, old_time))

        await cleanup_orphan_workspaces.fn()

        assert not old_dir.exists()

    async def test_skips_recent_directories(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Directories modified within the last hour should be preserved."""
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

        recent_dir = tmp_path / "autodoc_recent"
        recent_dir.mkdir()
        # mtime is current, so it should be skipped

        await cleanup_orphan_workspaces.fn()

        assert recent_dir.exists()

    async def test_skips_non_autodoc_dirs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Directories that don't match the autodoc_* pattern should be left alone."""
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

        non_autodoc_dir = tmp_path / "myproject_workspace"
        non_autodoc_dir.mkdir()
        old_time = time.time() - 7200
        os.utime(non_autodoc_dir, (old_time, old_time))

        await cleanup_orphan_workspaces.fn()

        assert non_autodoc_dir.exists()

    async def test_no_candidates(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """When no autodoc_* directories exist, the flow should complete without error."""
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

        await cleanup_orphan_workspaces.fn()
        # No assertion beyond "did not raise"

    async def test_handles_non_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Files (not directories) matching autodoc_* should be skipped."""
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

        file_path = tmp_path / "autodoc_not_a_dir"
        file_path.write_text("I am a file, not a directory")
        old_time = time.time() - 7200
        os.utime(file_path, (old_time, old_time))

        await cleanup_orphan_workspaces.fn()

        assert file_path.exists(), "Non-directory file should not be removed"

    async def test_mixed_old_and_recent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only old directories should be removed; recent ones should remain."""
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

        old_dir = tmp_path / "autodoc_old"
        old_dir.mkdir()
        old_time = time.time() - 7200
        os.utime(old_dir, (old_time, old_time))

        recent_dir = tmp_path / "autodoc_recent"
        recent_dir.mkdir()

        await cleanup_orphan_workspaces.fn()

        assert not old_dir.exists(), "Old directory should be removed"
        assert recent_dir.exists(), "Recent directory should be preserved"

    async def test_removes_multiple_old_directories(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Multiple old directories should all be removed."""
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

        old_dirs = []
        for i in range(3):
            d = tmp_path / f"autodoc_stale_{i}"
            d.mkdir()
            old_time = time.time() - 7200
            os.utime(d, (old_time, old_time))
            old_dirs.append(d)

        await cleanup_orphan_workspaces.fn()

        for d in old_dirs:
            assert not d.exists(), f"Directory {d.name} should have been removed"


# ---------------------------------------------------------------------------
# cleanup_workspace tests
# ---------------------------------------------------------------------------


class TestCleanupWorkspace:
    """Tests for the cleanup_workspace Prefect task."""

    async def test_removes_existing_workspace(self, tmp_path: Path) -> None:
        """An existing autodoc_* directory should be removed."""
        workspace = tmp_path / "autodoc_test_workspace"
        workspace.mkdir()
        (workspace / "somefile.txt").write_text("content")

        await cleanup_workspace.fn(repo_path=str(workspace))

        assert not workspace.exists()

    async def test_nonexistent_path(self) -> None:
        """A path that doesn't exist should be handled gracefully (no error)."""
        fake_path = "/tmp/autodoc_nonexistent_abc123"
        # Ensure it really doesn't exist
        assert not Path(fake_path).exists()

        await cleanup_workspace.fn(repo_path=fake_path)
        # No assertion beyond "did not raise"

    async def test_rejects_non_autodoc_path(self, tmp_path: Path) -> None:
        """A directory without the autodoc_ prefix should NOT be deleted."""
        workspace = tmp_path / "something_else"
        workspace.mkdir()
        (workspace / "important.txt").write_text("do not delete")

        await cleanup_workspace.fn(repo_path=str(workspace))

        assert workspace.exists(), "Non-autodoc directory must not be deleted"
        assert (workspace / "important.txt").exists()

    async def test_removes_nested_contents(self, tmp_path: Path) -> None:
        """rmtree should remove all nested files and subdirectories."""
        workspace = tmp_path / "autodoc_deep"
        workspace.mkdir()
        sub = workspace / "subdir"
        sub.mkdir()
        (sub / "nested.txt").write_text("nested content")

        await cleanup_workspace.fn(repo_path=str(workspace))

        assert not workspace.exists()

    async def test_idempotent_double_cleanup(self, tmp_path: Path) -> None:
        """Calling cleanup_workspace twice on the same path should not raise."""
        workspace = tmp_path / "autodoc_idem"
        workspace.mkdir()

        await cleanup_workspace.fn(repo_path=str(workspace))
        assert not workspace.exists()

        # Second call should succeed (path no longer exists)
        await cleanup_workspace.fn(repo_path=str(workspace))
