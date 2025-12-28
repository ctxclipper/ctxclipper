"""Output rendering: XML and legacy text formats."""

import os
from typing import List, Optional, Sequence

from .types import FileBlock

__all__ = [
    "xml_escape_attr",
    "cdata_wrap",
    "render_section",
    "render_block",
    "wrap_files_root",
    "wrap_chunk",
    "read_text_file",
    "join_texts",
]


def xml_escape_attr(s: str) -> str:
    """Escape a string for use in an XML attribute."""
    return (
        s.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def cdata_wrap(text: str) -> str:
    """
    Wrap text in CDATA section, escaping any embedded CDATA end markers.

    CDATA sections cannot contain the literal sequence "]]>", so we split
    and rejoin at those boundaries.
    """
    return "<![CDATA[" + text.replace("]]>", "]]]]><![CDATA[>") + "]]>"


def render_section(tag: str, text: Optional[str], fmt: str) -> str:
    """
    Render a section (preamble or question) in the specified format.

    Args:
        tag: Section name (e.g., "preamble", "question").
        text: Section content (can be None or empty).
        fmt: Output format ("xml" or "legacy").

    Returns:
        Formatted section string, or empty string if text is empty.
    """
    if text is None or text == "":
        return ""
    if fmt == "xml":
        return f"<{tag}>\n{cdata_wrap(text)}\n</{tag}>\n"
    return f"=== {tag.upper()} ===\n{text}\n"


def render_block(block: FileBlock, fmt: str) -> str:
    """
    Render a file block in the specified format.

    Args:
        block: FileBlock containing path and content.
        fmt: Output format ("xml" or "legacy").

    Returns:
        Formatted file block string.
    """
    if fmt == "xml":
        escaped = xml_escape_attr(block.rel_path)
        header = f'<file path="{escaped}">\n'
        footer = "\n</file>\n"
        return f"{header}{cdata_wrap(block.raw)}{footer}"
    # legacy format
    return f"=== FILE: {block.rel_path} ===\n{block.raw}\n"


def wrap_files_root(text: str, fmt: str) -> str:
    """
    Wrap file content in a root element.

    Args:
        text: Combined file content.
        fmt: Output format ("xml" or "legacy").

    Returns:
        Wrapped content.
    """
    if fmt == "xml":
        return f"<files>\n{text}\n</files>\n"
    return text


def wrap_chunk(chunk: str, idx: int, total: int, wrap: str, fmt: str) -> str:
    """
    Optionally wrap a chunk with ordering metadata.

    Args:
        chunk: Chunk content.
        idx: 1-based chunk index.
        total: Total number of chunks.
        wrap: Wrap style ("none", "xml", or "legacy").
        fmt: Output format (used for consistency with xml wrap).

    Returns:
        Wrapped chunk string.
    """
    if wrap == "xml":
        return f'<chunk index="{idx}" total="{total}">\n{chunk}\n</chunk>\n'
    if wrap == "legacy":
        return f"=== CHUNK {idx}/{total} ===\n{chunk}"
    return chunk


def read_text_file(path: str) -> str:
    """
    Read a text file with UTF-8 encoding.

    Args:
        path: Path to the file (supports ~ expansion).

    Returns:
        File contents as string.

    Raises:
        FileReadError: If file cannot be read.
    """
    from .exceptions import FileReadError

    try:
        with open(os.path.expanduser(path), "rb") as f:
            return f.read().decode("utf-8", errors="replace")
    except OSError as e:
        raise FileReadError(path, str(e)) from e


def join_texts(parts: Sequence[Optional[str]]) -> str:
    """
    Join text parts with double newlines, stripping trailing newlines.

    Args:
        parts: List of text parts (None values are filtered out).

    Returns:
        Joined text string.
    """
    cleaned = [p.rstrip("\n") for p in parts if p is not None]
    return "\n\n".join(cleaned)
