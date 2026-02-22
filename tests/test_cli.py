"""Tests for CLI argument parsing."""

import pytest

from ctxclipper.cli import parse_args
from ctxclipper.constants import (
    DEFAULT_MAX_CHARS,
    DEFAULT_MAX_FILE_BYTES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_RESERVE_CHARS,
    DEFAULT_RESERVE_TOKENS,
)


class TestParseArgs:
    """Tests for argument parsing."""

    def test_default_path(self) -> None:
        """Default path should be current directory."""
        args = parse_args([])
        assert args.path == "."

    def test_custom_path(self) -> None:
        """Custom path should be accepted."""
        args = parse_args(["/some/path"])
        assert args.path == "/some/path"

    def test_default_format(self) -> None:
        """Default format should be xml."""
        args = parse_args([])
        assert args.format == "xml"

    def test_legacy_format(self) -> None:
        """Legacy format should be accepted."""
        args = parse_args(["--format", "legacy"])
        assert args.format == "legacy"

    def test_default_budgets(self) -> None:
        """Default budgets should match constants."""
        args = parse_args([])
        assert args.max_tokens == DEFAULT_MAX_TOKENS
        assert args.reserve_tokens == DEFAULT_RESERVE_TOKENS
        assert args.max_chars == DEFAULT_MAX_CHARS
        assert args.reserve_chars == DEFAULT_RESERVE_CHARS
        assert args.max_file_bytes == DEFAULT_MAX_FILE_BYTES

    def test_custom_max_tokens(self) -> None:
        """Custom max tokens should be accepted."""
        args = parse_args(["--max-tokens", "50000"])
        assert args.max_tokens == 50000

    def test_custom_max_chars(self) -> None:
        """Custom max chars should be accepted."""
        args = parse_args(["--max-chars", "100000"])
        assert args.max_chars == 100000

    def test_no_copy_flag(self) -> None:
        """--no-copy flag should be recognized."""
        args = parse_args(["--no-copy"])
        assert args.no_copy is True

    def test_stdout_flag(self) -> None:
        """--stdout flag should be recognized."""
        args = parse_args(["--stdout"])
        assert args.stdout is True

    def test_split_enabled_by_default(self) -> None:
        """Split should be enabled by default."""
        args = parse_args([])
        assert args.split is True

    def test_no_split_flag(self) -> None:
        """--no-split should disable splitting."""
        args = parse_args(["--no-split"])
        assert args.split is False

    def test_interactive_by_default(self) -> None:
        """Interactive should be enabled by default."""
        args = parse_args([])
        assert args.interactive is True

    def test_non_interactive_flag(self) -> None:
        """--non-interactive should disable interactive mode."""
        args = parse_args(["--non-interactive"])
        assert args.interactive is False

    def test_ignore_patterns(self) -> None:
        """--ignore should accept patterns."""
        args = parse_args(["--ignore", "node_modules", ".git"])
        assert "node_modules" in args.ignore
        assert ".git" in args.ignore

    def test_ignore_glob_patterns(self) -> None:
        """--ignore-glob should accept glob patterns."""
        args = parse_args(["--ignore-glob", "*.lock", "dist/**"])
        assert "*.lock" in args.ignore_glob
        assert "dist/**" in args.ignore_glob

    def test_include_dotfiles(self) -> None:
        """--include-dotfiles should be recognized."""
        args = parse_args(["--include-dotfiles"])
        assert args.include_dotfiles is True

    def test_preamble_files(self) -> None:
        """--preamble should accept multiple files."""
        args = parse_args(["--preamble", "file1.txt", "--preamble", "file2.txt"])
        assert args.preamble == ["file1.txt", "file2.txt"]

    def test_question_file(self) -> None:
        """--question-file should store file type."""
        args = parse_args(["--question-file", "question.txt"])
        assert len(args.question_parts) == 1
        assert args.question_parts[0] == ("file", "question.txt")

    def test_question_text(self) -> None:
        """--question-text should store text type."""
        args = parse_args(["--question-text", "What does this do?"])
        assert len(args.question_parts) == 1
        assert args.question_parts[0] == ("text", "What does this do?")

    def test_model_option(self) -> None:
        """--model should accept model name."""
        args = parse_args(["--model", "gpt-4"])
        assert args.model == "gpt-4"

    def test_encoding_option(self) -> None:
        """--encoding should accept encoding name."""
        args = parse_args(["--encoding", "cl100k_base"])
        assert args.encoding == "cl100k_base"

    def test_trim_choices(self) -> None:
        """--trim should accept valid choices."""
        args = parse_args(["--trim", "none"])
        assert args.trim == "none"
        args = parse_args(["--trim", "largest"])
        assert args.trim == "largest"

    def test_chunk_wrap_choices(self) -> None:
        """--chunk-wrap should accept valid choices."""
        for choice in ["none", "xml", "legacy"]:
            args = parse_args(["--chunk-wrap", choice])
            assert args.chunk_wrap == choice

    def test_start_chunk(self) -> None:
        """--start-chunk should accept integer."""
        args = parse_args(["--start-chunk", "3"])
        assert args.start_chunk == 3

    def test_only_chunk(self) -> None:
        """--only-chunk should accept integer."""
        args = parse_args(["--only-chunk", "2"])
        assert args.only_chunk == 2

    def test_mutually_exclusive_split(self) -> None:
        """--split and --no-split should be mutually exclusive."""
        with pytest.raises(SystemExit):
            parse_args(["--split", "--no-split"])

    def test_mutually_exclusive_interactive(self) -> None:
        """--interactive and --non-interactive should be mutually exclusive."""
        with pytest.raises(SystemExit):
            parse_args(["--interactive", "--non-interactive"])
