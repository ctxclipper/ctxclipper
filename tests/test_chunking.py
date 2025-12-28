"""Tests for chunking module."""

import pytest

from ctxclipper.chunking import pack_chunks, trim_largest_first
from ctxclipper.types import FileBlock


class TestPackChunks:
    """Tests for pack_chunks function."""

    def test_single_small_file(self) -> None:
        """Single small file should produce one chunk."""
        blocks = [FileBlock(rel_path="test.py", raw="print('hello')")]
        chunks = pack_chunks(
            blocks,
            fmt="xml",
            max_chars=10000,
            max_tokens=None,
            enc=None,
            include_entries=False,
        )
        assert len(chunks) == 1
        assert "test.py" in chunks[0]

    def test_multiple_small_files(self) -> None:
        """Multiple small files should fit in one chunk."""
        blocks = [
            FileBlock(rel_path="a.py", raw="# a"),
            FileBlock(rel_path="b.py", raw="# b"),
            FileBlock(rel_path="c.py", raw="# c"),
        ]
        chunks = pack_chunks(
            blocks,
            fmt="xml",
            max_chars=10000,
            max_tokens=None,
            enc=None,
            include_entries=False,
        )
        assert len(chunks) == 1
        assert "a.py" in chunks[0]
        assert "b.py" in chunks[0]
        assert "c.py" in chunks[0]

    def test_files_split_by_char_budget(self) -> None:
        """Files should be split when exceeding char budget."""
        blocks = [
            FileBlock(rel_path="a.py", raw="x" * 100),
            FileBlock(rel_path="b.py", raw="y" * 100),
        ]
        chunks = pack_chunks(
            blocks,
            fmt="legacy",
            max_chars=150,  # Force split
            max_tokens=None,
            enc=None,
            include_entries=False,
        )
        assert len(chunks) >= 2

    def test_include_entries(self) -> None:
        """include_entries should return tuples with entries."""
        blocks = [FileBlock(rel_path="test.py", raw="content")]
        result = pack_chunks(
            blocks,
            fmt="xml",
            max_chars=10000,
            max_tokens=None,
            enc=None,
            include_entries=True,
        )
        assert isinstance(result, list)
        assert len(result) == 1
        chunk, entries = result[0]
        assert isinstance(chunk, str)
        assert isinstance(entries, list)
        assert len(entries) == 1
        assert entries[0][0] == "test.py"


class TestTrimLargestFirst:
    """Tests for trim_largest_first function."""

    def test_no_trim_needed(self) -> None:
        """Content within budget should not be trimmed."""
        blocks = [
            FileBlock(rel_path="a.py", raw="short"),
            FileBlock(rel_path="b.py", raw="also short"),
        ]
        result, total = trim_largest_first(blocks, max_chars=1000, keep_per_file=100)
        assert total == len("short") + len("also short")
        assert result[0].raw == "short"
        assert result[1].raw == "also short"

    def test_largest_file_trimmed(self) -> None:
        """Largest file should be trimmed first."""
        blocks = [
            FileBlock(rel_path="small.py", raw="x" * 10),
            FileBlock(rel_path="large.py", raw="y" * 1000),
        ]
        result, total = trim_largest_first(blocks, max_chars=100, keep_per_file=20)
        # Large file should be truncated
        assert "[TRUNCATED:" in result[1].raw or "[OMITTED:" in result[1].raw
        # Small file should be unchanged
        assert result[0].raw == "x" * 10

    def test_multiple_files_trimmed(self) -> None:
        """Multiple files should be trimmed if needed."""
        blocks = [
            FileBlock(rel_path="a.py", raw="x" * 500),
            FileBlock(rel_path="b.py", raw="y" * 500),
        ]
        result, total = trim_largest_first(blocks, max_chars=100, keep_per_file=30)
        # Both should be trimmed
        assert "[TRUNCATED:" in result[0].raw or "[OMITTED:" in result[0].raw
        assert "[TRUNCATED:" in result[1].raw or "[OMITTED:" in result[1].raw

    def test_empty_blocks(self) -> None:
        """Empty block list should return empty."""
        result, total = trim_largest_first([], max_chars=100, keep_per_file=10)
        assert result == []
        assert total == 0
