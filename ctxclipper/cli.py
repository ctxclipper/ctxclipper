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
        prog="ctxclipper",
        description="Clipboard-first, gitignore-first directory flattener for LLM context."
    )

    input_group = parser.add_argument_group("Input selection")
    output_group = parser.add_argument_group("Output")
    context_group = parser.add_argument_group("Prompt context")
    budget_group = parser.add_argument_group("Budgets")
    chunk_group = parser.add_argument_group("Chunking")

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
    input_group.add_argument(
        "--ignore",
        nargs="*",
        metavar="NAME",
        default=sorted(DEFAULT_IGNORE_NAMES),
        help="Names to ignore (match any path component)",
    )
    input_group.add_argument(
        "--ignore-glob",
        "--ignore-globs",
        nargs="*",
        metavar="GLOB",
        default=[],
        dest="ignore_glob",
        help="Glob patterns to ignore (e.g. '*.lock' 'dist/**'); use leading '/' or './' to anchor",
    )
    input_group.add_argument(
        "--include-dotfiles",
        action="store_true",
        help="Include dotfiles and dot-directories",
    )

    # Output control
    output_group.add_argument(
        "--no-copy",
        action="store_true",
        help="Do not copy to clipboard",
    )
    output_group.add_argument(
        "--stdout",
        action="store_true",
        help="Also print rendered output to stdout (default: clipboard only)",
    )
    output_group.add_argument(
        "--format",
        choices=["xml", "legacy"],
        default="xml",
        help="Output format (default: xml)",
    )

    # Preamble and question
    context_group.add_argument(
        "--preamble",
        action="append",
        metavar="PATH",
        default=[],
        help="File to prepend before files (can repeat)",
    )
    context_group.add_argument(
        "--question-file",
        action="append",
        type=_question_file,
        dest="question_parts",
        metavar="PATH",
        default=[],
        help="File to append after files (can repeat)",
    )
    context_group.add_argument(
        "--question-text",
        action="append",
        type=_question_text,
        dest="question_parts",
        metavar="TEXT",
        default=[],
        help="Literal text to append after files (can repeat)",
    )

    # Token counting
    budget_group.add_argument(
        "--model",
        metavar="MODEL",
        default=None,
        help="Model name for tiktoken.encoding_for_model (optional)",
    )
    budget_group.add_argument(
        "--encoding",
        metavar="ENCODING",
        default=None,
        help="Fallback encoding name (default: o200k_base)",
    )
    budget_group.add_argument(
        "--max-tokens",
        type=int,
        metavar="N",
        default=DEFAULT_MAX_TOKENS,
        help=f"Max tokens per chunk (default: {DEFAULT_MAX_TOKENS})",
    )
    budget_group.add_argument(
        "--reserve-tokens",
        type=int,
        metavar="N",
        default=DEFAULT_RESERVE_TOKENS,
        help=f"Reserve tokens for instruction text (default: {DEFAULT_RESERVE_TOKENS})",
    )

    # Size / chunking guards
    budget_group.add_argument(
        "--max-chars",
        type=int,
        metavar="N",
        default=DEFAULT_MAX_CHARS,
        help=f"Max total chars; set 0 to disable (default: {DEFAULT_MAX_CHARS})",
    )
    budget_group.add_argument(
        "--reserve-chars",
        type=int,
        metavar="N",
        default=DEFAULT_RESERVE_CHARS,
        help=f"Reserve chars for instruction text (default: {DEFAULT_RESERVE_CHARS})",
    )
    budget_group.add_argument(
        "--trim",
        choices=["none", "largest"],
        default="largest",
        help="How to reduce output in no-split mode before failing (default: largest)",
    )
    budget_group.add_argument(
        "--keep-per-file",
        type=int,
        metavar="N",
        default=DEFAULT_KEEP_PER_FILE,
        help=f"Chars to keep per file when applying largest-file trimming (default: {DEFAULT_KEEP_PER_FILE})",
    )
    budget_group.add_argument(
        "--max-file-bytes",
        type=int,
        metavar="N",
        default=DEFAULT_MAX_FILE_BYTES,
        help=f"Hard cap per file read in bytes (default: {DEFAULT_MAX_FILE_BYTES})",
    )

    # Split mode
    split_group = chunk_group.add_mutually_exclusive_group()
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
        help="Disable chunk splitting; trim if configured, then error if the output still does not fit",
    )

    # Interactive mode
    inter_group = chunk_group.add_mutually_exclusive_group()
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
    chunk_group.add_argument(
        "--chunk-wrap",
        choices=["none", "xml", "legacy"],
        default="none",
        help="Optional chunk wrapper marking order (default: none)",
    )
    chunk_group.add_argument(
        "--start-chunk",
        type=int,
        metavar="N",
        default=1,
        help="Start copying from this 1-based chunk index",
    )
    chunk_group.add_argument(
        "--only-chunk",
        type=int,
        metavar="N",
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
