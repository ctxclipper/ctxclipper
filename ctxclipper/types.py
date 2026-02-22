"""Type definitions and dataclasses for ctxclipper."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:
    from tiktoken import Encoding

__all__ = [
    "ChunkEntry",
    "ChunkWithEntries",
    "Encoder",
    "FileBlock",
    "TokenizerResult",
]

# Type aliases
Encoder = Optional["Encoding"]
ChunkEntry = Tuple[str, str]  # (rel_path, rendered_text)
ChunkWithEntries = Tuple[str, List[ChunkEntry]]  # (chunk_text, entries)


@dataclass
class FileBlock:
    """Represents a file's content ready for rendering."""

    rel_path: str
    raw: str  # unwrapped content


@dataclass
class TokenizerResult:
    """Result of initializing a tokenizer."""

    encoder: Encoder
    note: Optional[str]
    source: str  # "model", "override", "encoding", or "none"
