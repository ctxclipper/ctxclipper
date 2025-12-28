"""Command-line interface argument parsing."""

import argparse
from typing import List, Optional, Tuple

from .constants import (
    DEFAULT_IGNORE_NAMES,
    DEFAULT_KEEP_PER_FILE,
    DEFAULT_MAX_CHARS,
    DEFAULT_MAX_FILE_BYTES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_RESERVE_CHARS,
    DEFAULT_RESERVE_TOKENS,
)

__all__ = ["create_parser", "parse_args"]


def _question_file(arg: str) -> Tuple[str, str]:
    """Type converter for --question-file argument."""
    return ("file", arg)


def _question_text(arg: str) -> Tuple[str, str]:
    """Type converter for --question-text argument."""
    return ("text", arg)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="Clipboard-first, gitignore-first directory flattener for LLM context."
    )

    # Positional arguments
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory to process (default: .)",
    )

    # Version
    from . import __version__

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    # Ignore patterns
    parser.add_argument(
        "--ignore",
        nargs="*",
        default=sorted(DEFAULT_IGNORE_NAMES),
        help="Names to ignore (match any path component)",
    )
    parser.add_argument(
        "--ignore-glob",
        "--ignore-globs",
        nargs="*",
        default=[],
        dest="ignore_glob",
        help="Glob patterns to ignore (e.g. '*.lock' 'dist/**'); use leading '/' or './' to anchor",
    )
    parser.add_argument(
        "--include-dotfiles",
        action="store_true",
        help="Include dotfiles and dot-directories",
    )

    # Output control
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Do not copy to clipboard",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print output to stdout (default: clipboard only)",
    )
    parser.add_argument(
        "--format",
        choices=["xml", "legacy"],
        default="xml",
        help="Output format (default: xml)",
    )

    # Preamble and question
    parser.add_argument(
        "--preamble",
        action="append",
        default=[],
        help="File to prepend before files (can repeat)",
    )
    parser.add_argument(
        "--question-file",
        action="append",
        type=_question_file,
        dest="question_parts",
        default=[],
        help="File to append after files (can repeat)",
    )
    parser.add_argument(
        "--question-text",
        action="append",
        type=_question_text,
        dest="question_parts",
        default=[],
        help="Literal text to append after files (can repeat)",
    )

    # Token counting
    parser.add_argument(
        "--model",
        default=None,
        help="Model name for tiktoken.encoding_for_model (optional)",
    )
    parser.add_argument(
        "--encoding",
        default=None,
        help="Fallback encoding name (default: o200k_base)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"Max tokens per chunk (default: {DEFAULT_MAX_TOKENS})",
    )
    parser.add_argument(
        "--reserve-tokens",
        type=int,
        default=DEFAULT_RESERVE_TOKENS,
        help=f"Reserve tokens for instruction text (default: {DEFAULT_RESERVE_TOKENS})",
    )

    # Size / chunking guards
    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help=f"Max total chars; set 0 to disable (default: {DEFAULT_MAX_CHARS})",
    )
    parser.add_argument(
        "--reserve-chars",
        type=int,
        default=DEFAULT_RESERVE_CHARS,
        help=f"Reserve chars for instruction text (default: {DEFAULT_RESERVE_CHARS})",
    )
    parser.add_argument(
        "--trim",
        choices=["none", "largest"],
        default="largest",
        help="How to reduce if over max-chars (default: largest)",
    )
    parser.add_argument(
        "--keep-per-file",
        type=int,
        default=DEFAULT_KEEP_PER_FILE,
        help=f"Chars to keep per file when trimming (default: {DEFAULT_KEEP_PER_FILE})",
    )
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=DEFAULT_MAX_FILE_BYTES,
        help=f"Hard cap per file read in bytes (default: {DEFAULT_MAX_FILE_BYTES})",
    )

    # Split mode
    split_group = parser.add_mutually_exclusive_group()
    split_group.add_argument(
        "--split",
        dest="split",
        action="store_true",
        help="Enable chunk splitting if over budget",
    )
    split_group.add_argument(
        "--no-split",
        dest="split",
        action="store_false",
        help="Disable chunk splitting; use trim policy",
    )

    # Interactive mode
    inter_group = parser.add_mutually_exclusive_group()
    inter_group.add_argument(
        "--interactive",
        dest="interactive",
        action="store_true",
        help="Wait for Enter between chunk copies",
    )
    inter_group.add_argument(
        "--non-interactive",
        dest="interactive",
        action="store_false",
        help="Do not prompt between chunks",
    )

    parser.set_defaults(split=True, interactive=True)

    # Chunk control
    parser.add_argument(
        "--chunk-wrap",
        choices=["none", "xml", "legacy"],
        default="none",
        help="Optional chunk wrapper marking order (default: none)",
    )
    parser.add_argument(
        "--start-chunk",
        type=int,
        default=1,
        help="Start copying from this 1-based chunk index",
    )
    parser.add_argument(
        "--only-chunk",
        type=int,
        default=None,
        help="Copy only this 1-based chunk index",
    )

    return parser


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Command-line arguments (defaults to sys.argv).

    Returns:
        Parsed argument namespace.
    """
    parser = create_parser()
    return parser.parse_args(args)
