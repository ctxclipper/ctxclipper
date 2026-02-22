"""Tests for core orchestration module."""

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from ctxclipper.core import adjust_budget, read_file_blocks, run
from ctxclipper.exceptions import ClipboardError, DirectoryError


class TestReadFileBlocks:
    """Tests for read_file_blocks function."""

    def test_reads_text_files(self, sample_repo: Path) -> None:
        """Should read text files and create FileBlocks."""
        rel_paths = ["README.md", "src/main.py"]
        blocks, binary, errors, truncated = read_file_blocks(
            str(sample_repo), rel_paths, max_file_bytes=1_000_000
        )

        assert len(blocks) == 2
        assert blocks[0].rel_path == "README.md"
        assert "Sample Project" in blocks[0].raw
        assert blocks[1].rel_path == "src/main.py"
        assert binary == 0
        assert errors == 0
        assert truncated == 0

    def test_skips_binary_files(self, sample_repo_with_binary: Path) -> None:
        """Should skip binary files."""
        rel_paths = ["README.md", "image.png"]
        blocks, binary, errors, _truncated = read_file_blocks(
            str(sample_repo_with_binary), rel_paths, max_file_bytes=1_000_000
        )

        assert len(blocks) == 1
        assert blocks[0].rel_path == "README.md"
        assert binary == 1
        assert errors == 0

    def test_truncates_large_files(self, temp_dir: Path) -> None:
        """Should truncate files exceeding max_file_bytes."""
        large_file = temp_dir / "large.txt"
        large_file.write_text("x" * 1000)

        blocks, _binary, _errors, truncated = read_file_blocks(
            str(temp_dir), ["large.txt"], max_file_bytes=100
        )

        assert len(blocks) == 1
        assert "[TRUNCATED:" in blocks[0].raw
        assert truncated == 1

    def test_handles_unreadable_files(self, temp_dir: Path) -> None:
        """Should skip unreadable files and increment error count."""
        # Create a file then make it unreadable
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        rel_paths = ["test.txt", "nonexistent.txt"]
        blocks, _binary, _errors, _truncated = read_file_blocks(
            str(temp_dir), rel_paths, max_file_bytes=1_000_000
        )

        # Only the existing file should be read
        assert len(blocks) == 1
        # nonexistent.txt is skipped by isfile check, not counted as error

    def test_skips_directories(self, sample_repo: Path) -> None:
        """Should skip directories in rel_paths."""
        rel_paths = ["src", "README.md"]
        blocks, _binary, _errors, _truncated = read_file_blocks(
            str(sample_repo), rel_paths, max_file_bytes=1_000_000
        )

        assert len(blocks) == 1
        assert blocks[0].rel_path == "README.md"

    def test_empty_file_list(self, temp_dir: Path) -> None:
        """Should handle empty file list."""
        blocks, binary, errors, truncated = read_file_blocks(
            str(temp_dir), [], max_file_bytes=1_000_000
        )

        assert blocks == []
        assert binary == 0
        assert errors == 0
        assert truncated == 0


class TestAdjustBudget:
    """Tests for adjust_budget function."""

    def test_no_adjustment_needed(self) -> None:
        """Should return base when overhead is zero."""
        result, adjusted = adjust_budget(1000, 0, "Test")
        assert result == 1000
        assert adjusted is False

    def test_adjustment_applied(self) -> None:
        """Should subtract overhead from base."""
        result, adjusted = adjust_budget(1000, 100, "Test")
        assert result == 900
        assert adjusted is True

    def test_none_base(self) -> None:
        """Should return None when base is None."""
        result, adjusted = adjust_budget(None, 100, "Test")
        assert result is None
        assert adjusted is False

    def test_overhead_exceeds_base(self) -> None:
        """Should return base when overhead >= base."""
        result, adjusted = adjust_budget(100, 200, "Test")
        assert result == 100
        assert adjusted is False

    def test_overhead_equals_base(self) -> None:
        """Should return base when overhead == base."""
        result, adjusted = adjust_budget(100, 100, "Test")
        assert result == 100
        assert adjusted is False


class TestRun:
    """Tests for run function."""

    def _make_args(self, **kwargs) -> argparse.Namespace:
        """Create argument namespace with defaults."""
        defaults = {
            "path": ".",
            "preamble": [],
            "question_parts": [],
            "format": "xml",
            "ignore": [],
            "ignore_glob": [],
            "include_dotfiles": False,
            "model": None,
            "encoding": None,
            "max_tokens": 160000,
            "reserve_tokens": 16000,
            "max_chars": 500000,
            "reserve_chars": 2000,
            "max_file_bytes": 2000000,
            "split": True,
            "trim": "largest",
            "keep_per_file": 8000,
            "no_copy": True,
            "stdout": False,
            "chunk_wrap": "none",
            "start_chunk": 1,
            "only_chunk": None,
            "interactive": False,
        }
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_nonexistent_directory_raises(self) -> None:
        """Should raise DirectoryError for non-existent path."""
        args = self._make_args(path="/nonexistent/path")
        with pytest.raises(DirectoryError) as exc_info:
            run(args)
        assert "Not a directory" in str(exc_info.value)

    def test_file_path_raises(self, temp_dir: Path) -> None:
        """Should raise DirectoryError when path is a file."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        args = self._make_args(path=str(test_file))
        with pytest.raises(DirectoryError):
            run(args)

    def test_basic_directory_no_copy(self, sample_repo: Path) -> None:
        """Should process directory successfully in no-copy mode."""
        args = self._make_args(path=str(sample_repo), no_copy=True)
        exit_code = run(args)
        assert exit_code == 0

    def test_stdout_mode(self, sample_repo: Path, capsys) -> None:
        """Should output to stdout when requested."""
        args = self._make_args(path=str(sample_repo), no_copy=True, stdout=True)
        exit_code = run(args)

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "<files>" in captured.out
        assert "README.md" in captured.out

    def test_legacy_format(self, sample_repo: Path, capsys) -> None:
        """Should use legacy format when requested."""
        args = self._make_args(path=str(sample_repo), no_copy=True, stdout=True, format="legacy")
        exit_code = run(args)

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "=== FILE:" in captured.out

    @patch("ctxclipper.core.copy_to_clipboard")
    def test_clipboard_failure_raises(self, mock_clipboard, sample_repo: Path) -> None:
        """Should raise ClipboardError when clipboard fails."""
        mock_clipboard.return_value = False
        args = self._make_args(path=str(sample_repo), no_copy=False)

        with pytest.raises(ClipboardError):
            run(args)

    @patch("ctxclipper.core.copy_to_clipboard")
    def test_clipboard_success(self, mock_clipboard, sample_repo: Path) -> None:
        """Should succeed when clipboard works."""
        mock_clipboard.return_value = True
        args = self._make_args(path=str(sample_repo), no_copy=False)

        exit_code = run(args)
        assert exit_code == 0
        mock_clipboard.assert_called()

    def test_empty_directory(self, temp_dir: Path) -> None:
        """Should handle empty directory."""
        args = self._make_args(path=str(temp_dir), no_copy=True)
        exit_code = run(args)
        assert exit_code == 0

    def test_ignore_patterns(self, sample_repo: Path, capsys) -> None:
        """Should respect ignore patterns."""
        args = self._make_args(
            path=str(sample_repo),
            no_copy=True,
            stdout=True,
            ignore=["src"],
        )
        exit_code = run(args)

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "README.md" in captured.out
        # src/main.py should be excluded, check that src directory content is absent
        assert 'path="src/main.py"' not in captured.out

    def test_preamble_file(self, sample_repo: Path, capsys) -> None:
        """Should include preamble from file."""
        preamble = sample_repo / "preamble.txt"
        preamble.write_text("This is the preamble.")

        args = self._make_args(
            path=str(sample_repo),
            no_copy=True,
            stdout=True,
            preamble=[str(preamble)],
        )
        exit_code = run(args)

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "This is the preamble" in captured.out

    def test_question_text(self, sample_repo: Path, capsys) -> None:
        """Should include question text."""
        args = self._make_args(
            path=str(sample_repo),
            no_copy=True,
            stdout=True,
            question_parts=[("text", "What does this code do?")],
        )
        exit_code = run(args)

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "What does this code do?" in captured.out
