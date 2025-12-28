"""Tests for discovery module."""

import os
from pathlib import Path

import pytest

from ctxclipper.discovery import (
    discover_files,
    git_list_files,
    in_git_worktree,
    is_binary,
    load_gitignore_pathspec,
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


class TestGitListFiles:
    """Tests for git_list_files function."""

    def test_lists_tracked_files(self, git_repo: Path) -> None:
        """Should list tracked files."""
        files = git_list_files(str(git_repo))

        assert "file1.py" in files
        assert "file2.py" in files
        assert ".gitignore" in files

    def test_excludes_ignored_files(self, git_repo: Path) -> None:
        """Should exclude files in .gitignore."""
        files = git_list_files(str(git_repo))

        assert "ignored.txt" not in files

    def test_includes_untracked_files(self, git_repo: Path) -> None:
        """Should include untracked but not ignored files."""
        # Add an untracked file
        untracked = git_repo / "untracked.py"
        untracked.write_text("# untracked")

        files = git_list_files(str(git_repo))
        assert "untracked.py" in files


class TestLoadGitignorePathspec:
    """Tests for load_gitignore_pathspec function."""

    def test_loads_gitignore(self, temp_dir: Path) -> None:
        """Should load patterns from .gitignore."""
        gitignore = temp_dir / ".gitignore"
        gitignore.write_text("*.pyc\n__pycache__\n")

        spec, error = load_gitignore_pathspec(str(temp_dir))

        assert error is None
        assert spec is not None
        assert spec.match_file("test.pyc")
        assert spec.match_file("__pycache__")

    def test_no_gitignore(self, temp_dir: Path) -> None:
        """Should return empty spec when no .gitignore exists."""
        spec, error = load_gitignore_pathspec(str(temp_dir))

        assert error is None
        assert spec is not None
        # Empty spec shouldn't match anything
        assert not spec.match_file("anything.txt")


class TestDiscoverFiles:
    """Tests for discover_files function."""

    def test_discovers_all_files(self, sample_repo: Path) -> None:
        """Should discover all non-ignored files."""
        files, used_git = discover_files(
            str(sample_repo),
            ignore_names=set(),
            ignore_globs=[],
            include_dotfiles=True,
        )

        # Should find the sample files
        file_names = [os.path.basename(f) for f in files]
        assert "README.md" in file_names
        assert "main.py" in file_names

    def test_respects_ignore_names(self, sample_repo: Path) -> None:
        """Should respect ignore names."""
        files, _ = discover_files(
            str(sample_repo),
            ignore_names={"src"},
            ignore_globs=[],
            include_dotfiles=True,
        )

        # Should not find files in src directory
        for f in files:
            assert "src" not in f

    def test_respects_ignore_globs(self, sample_repo: Path) -> None:
        """Should respect ignore globs."""
        files, _ = discover_files(
            str(sample_repo),
            ignore_names=set(),
            ignore_globs=["*.md"],
            include_dotfiles=True,
        )

        # Should not find .md files
        for f in files:
            assert not f.endswith(".md")

    def test_excludes_dotfiles_by_default(self, sample_repo: Path) -> None:
        """Should exclude dotfiles when include_dotfiles is False."""
        files, _ = discover_files(
            str(sample_repo),
            ignore_names=set(),
            ignore_globs=[],
            include_dotfiles=False,
        )

        # Should not find .gitignore
        for f in files:
            assert not os.path.basename(f).startswith(".")

    def test_git_repo_uses_git(self, git_repo: Path) -> None:
        """Should use git when in git repo."""
        files, used_git = discover_files(
            str(git_repo),
            ignore_names=set(),
            ignore_globs=[],
            include_dotfiles=True,
        )

        assert used_git is True

    def test_non_git_uses_scan(self, temp_dir: Path) -> None:
        """Should use directory scan when not in git repo."""
        # Create a file
        (temp_dir / "test.py").write_text("# test")

        files, used_git = discover_files(
            str(temp_dir),
            ignore_names=set(),
            ignore_globs=[],
            include_dotfiles=True,
        )

        assert used_git is False
        assert "test.py" in files

    def test_empty_directory(self, temp_dir: Path) -> None:
        """Should handle empty directory."""
        files, _ = discover_files(
            str(temp_dir),
            ignore_names=set(),
            ignore_globs=[],
            include_dotfiles=True,
        )

        assert files == []

    def test_files_sorted(self, temp_dir: Path) -> None:
        """Should return sorted file list."""
        (temp_dir / "z.py").write_text("")
        (temp_dir / "a.py").write_text("")
        (temp_dir / "m.py").write_text("")

        files, _ = discover_files(
            str(temp_dir),
            ignore_names=set(),
            ignore_globs=[],
            include_dotfiles=True,
        )

        assert files == sorted(files)
