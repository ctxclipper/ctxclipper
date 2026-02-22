"""Constants and default values for ctxclipper."""

from typing import FrozenSet

__all__ = [
    "BINARY_DETECTION_BYTES",
    "DEFAULT_ENCODING",
    "DEFAULT_IGNORE_NAMES",
    "DEFAULT_KEEP_PER_FILE",
    "DEFAULT_MAX_CHARS",
    "DEFAULT_MAX_FILE_BYTES",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_RESERVE_CHARS",
    "DEFAULT_RESERVE_TOKENS",
]

# Binary file detection: number of bytes to check for NUL
BINARY_DETECTION_BYTES: int = 4096

# Token budgets
DEFAULT_MAX_TOKENS: int = 160_000
DEFAULT_RESERVE_TOKENS: int = 16_000

# Character budgets (roughly 3.2 chars per token for English)
DEFAULT_MAX_CHARS: int = 500_000
DEFAULT_RESERVE_CHARS: int = 2_000

# File size limits
DEFAULT_MAX_FILE_BYTES: int = 2 * 1024 * 1024  # 2MB
DEFAULT_KEEP_PER_FILE: int = 8_000  # chars to keep when trimming

# Tokenization
DEFAULT_ENCODING: str = "o200k_base"

# Directories and files to ignore by default
DEFAULT_IGNORE_NAMES: FrozenSet[str] = frozenset(
    {
        ".git",
        ".DS_Store",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".idea",
        ".vscode",
        "dist",
        "build",
        "target",
        "coverage",
        ".next",
    }
)
