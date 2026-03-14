"""
ctxclipper - Clipboard-first, gitignore-first directory flattener for LLM context.

This tool gathers text files from a directory, respects .gitignore patterns,
formats output in XML or legacy text format, and manages token/character limits
for LLM context windows.
"""

import logging

from .cli import parse_args
from .core import run
from .exceptions import (
    BudgetError,
    ClipboardError,
    CtxclipperError,
    DirectoryError,
    FileReadError,
)
from .types import FileBlock

__version__ = "0.2.0"
__all__ = [
    "BudgetError",
    "ClipboardError",
    "CtxclipperError",
    "DirectoryError",
    "FileBlock",
    "FileReadError",
    "__version__",
    "main",
    "parse_args",
    "run",
]

# Configure null handler for library use
logging.getLogger(__name__).addHandler(logging.NullHandler())


def main() -> None:
    """Main entry point for the CLI."""
    import sys

    from .exceptions import ClipboardError, CtxclipperError, DirectoryError

    try:
        args = parse_args()
        exit_code = run(args)
        sys.exit(exit_code)
    except ClipboardError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(2)
    except DirectoryError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    except CtxclipperError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
