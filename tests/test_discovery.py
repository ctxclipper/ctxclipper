"""Tests for discovery module."""

import os
from pathlib import Path

import pytest

from ctxclipper.discovery import (
    in_git_worktree,
    is_binary,
    normalize_glob,
    should_ignore_path,
)


class TestIsBinary:
    """Tests for is_binary function."""

    def test_text_file_not_binary(self, temp_dir: Path) -> None:
        """Text files should not be detected as binary."""
        text_file = temp_dir / "test.txt"
        text_file.write_text("Hello, world!\n")
        assert is_binary(str(text_file)) is False

    def test_binary_file_detected(self, temp_dir: Path) -> None:
        """Binary files with NUL bytes should be detected."""
        binary_file = temp_dir / "test.bin"
        binary_file.write_bytes(b"Hello\x00World")
        assert is_binary(str(binary_file)) is True

    def test_png_detected_as_binary(self, temp_dir: Path) -> None:
        """PNG files should be detected as binary."""
        png_file = temp_dir / "test.png"
        png_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
        assert is_binary(str(png_file)) is True

    def test_nonexistent_file_returns_true(self) -> None:
        """Non-existent files should return True (fail-safe)."""
        assert is_binary("/nonexistent/path/file.txt") is True

    def test_empty_file_not_binary(self, temp_dir: Path) -> None:
        """Empty files should not be detected as binary."""
        empty_file = temp_dir / "empty.txt"
        empty_file.write_bytes(b"")
        assert is_binary(str(empty_file)) is False


class TestNormalizeGlob:
    """Tests for normalize_glob function."""

    def test_simple_pattern(self) -> None:
        """Simple patterns should pass through unchanged."""
        pattern, anchored = normalize_glob("*.py")
        assert pattern == "*.py"
        assert anchored is False

    def test_slash_anchored(self) -> None:
        """Leading slash should anchor pattern."""
        pattern, anchored = normalize_glob("/src/*.py")
        assert pattern == "src/*.py"
        assert anchored is True

    def test_dot_slash_anchored(self) -> None:
        """Leading ./ should anchor pattern."""
        pattern, anchored = normalize_glob("./src/*.py")
        assert pattern == "src/*.py"
        assert anchored is True

    def test_backslash_normalized(self) -> None:
        """Backslashes should be normalized to forward slashes."""
        pattern, anchored = normalize_glob("src\\utils\\*.py")
        assert pattern == "src/utils/*.py"
        assert anchored is False

    def test_multiple_leading_slashes(self) -> None:
        """Multiple leading slashes should be stripped."""
        pattern, anchored = normalize_glob("///src/*.py")
        assert pattern == "src/*.py"
        assert anchored is True


class TestShouldIgnorePath:
    """Tests for should_ignore_path function."""

    def test_ignore_by_name(self) -> None:
        """Paths containing ignored names should be ignored."""
        assert should_ignore_path(
            "src/node_modules/package.json",
            ignore_names={"node_modules"},
            ignore_globs=[],
            include_dotfiles=True,
        ) is True

    def test_ignore_dotfiles(self) -> None:
        """Dotfiles should be ignored when include_dotfiles is False."""
        assert should_ignore_path(
            ".hidden/file.txt",
            ignore_names=set(),
            ignore_globs=[],
            include_dotfiles=False,
        ) is True

    def test_include_dotfiles(self) -> None:
        """Dotfiles should be included when include_dotfiles is True."""
        assert should_ignore_path(
            ".hidden/file.txt",
            ignore_names=set(),
            ignore_globs=[],
            include_dotfiles=True,
        ) is False

    def test_ignore_glob_pattern(self) -> None:
        """Glob patterns should match correctly."""
        assert should_ignore_path(
            "package-lock.json",
            ignore_names=set(),
            ignore_globs=["*.json"],
            include_dotfiles=True,
        ) is True

    def test_ignore_glob_directory_pattern(self) -> None:
        """Directory glob patterns should match."""
        assert should_ignore_path(
            "dist/bundle.js",
            ignore_names=set(),
            ignore_globs=["dist/**"],
            include_dotfiles=True,
        ) is True

    def test_anchored_glob_pattern(self) -> None:
        """Anchored patterns should only match from root."""
        # Should match - pattern is anchored and matches from root
        assert should_ignore_path(
            "src/file.py",
            ignore_names=set(),
            ignore_globs=["/src/*.py"],
            include_dotfiles=True,
        ) is True

    def test_normal_file_not_ignored(self) -> None:
        """Normal files should not be ignored."""
        assert should_ignore_path(
            "src/main.py",
            ignore_names=set(),
            ignore_globs=[],
            include_dotfiles=True,
        ) is False


class TestInGitWorktree:
    """Tests for in_git_worktree function."""

    def test_git_repo_detected(self, git_repo: Path) -> None:
        """Git repositories should be detected."""
        assert in_git_worktree(str(git_repo)) is True

    def test_non_git_dir_not_detected(self, temp_dir: Path) -> None:
        """Non-git directories should not be detected."""
        assert in_git_worktree(str(temp_dir)) is False

    def test_nonexistent_dir(self) -> None:
        """Non-existent directories should return False."""
        assert in_git_worktree("/nonexistent/path") is False
