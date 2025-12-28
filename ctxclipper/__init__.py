"""
ctxclipper - Clipboard-first, gitignore-first directory flattener for LLM context.

This tool gathers text files from a directory, respects .gitignore patterns,
formats output in XML or legacy text format, and manages token/character limits
for LLM context windows.
"""

from .cli import parse_args
from .core import run
from .types import FileBlock

__version__ = "0.1.0"
__all__ = ["__version__", "main", "run", "parse_args", "FileBlock"]


def main() -> None:
    """Main entry point for the CLI."""
    import sys

    args = parse_args()
    exit_code = run(args)
    sys.exit(exit_code)
