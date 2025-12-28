"""Chunking and budget management for output splitting."""

import heapq
import logging
from typing import List, Optional, Tuple, Union

from .rendering import render_block, wrap_files_root
from .tokenization import fits_budget
from .types import ChunkEntry, ChunkWithEntries, Encoder, FileBlock

__all__ = [
    "split_big_file",
    "pack_chunks",
    "trim_largest_first",
    "print_chunk_file_tokens",
]

logger = logging.getLogger(__name__)


def split_big_file(
    block: FileBlock,
    fmt: str,
    *,
    max_chars: Optional[int],
    max_tokens: Optional[int],
    enc: Encoder,
) -> List[str]:
    """
    Split a single file's content into multiple chunks that fit the budget.

    Uses binary search to find the maximum content that fits when rendered.

    Args:
        block: FileBlock to split.
        fmt: Output format ("xml" or "legacy").
        max_chars: Maximum characters per chunk.
        max_tokens: Maximum tokens per chunk.
        enc: Tiktoken encoder.

    Returns:
        List of rendered pieces that each fit within budget.
    """
    if (max_chars is not None and max_chars <= 0) and (max_tokens is None):
        return []

    # Check if even an empty wrapper won't fit
    empty_rendered = render_block(FileBlock(rel_path=block.rel_path, raw=""), fmt)
    if not fits_budget(
        wrap_files_root(empty_rendered, fmt),
        max_chars=max_chars,
        max_tokens=max_tokens,
        enc=enc,
    ):
        tiny_block = FileBlock(
            rel_path=block.rel_path,
            raw="[OMITTED: budget too small for wrapper]\n",
        )
        tiny_rendered = render_block(tiny_block, fmt)

        # Best-effort truncate by chars if available
        if max_chars is not None and max_chars > 0:
            return [tiny_rendered[:max_chars]]

        # Fallback: binary search for largest prefix that fits token budget
        if enc is not None and max_tokens is not None and max_tokens > 0:
            lo, hi = 0, len(tiny_rendered)
            best = 0
            while lo <= hi:
                mid = (lo + hi) // 2
                if fits_budget(
                    wrap_files_root(tiny_rendered[:mid], fmt),
                    max_chars=max_chars,
                    max_tokens=max_tokens,
                    enc=enc,
                ):
                    best = mid
                    lo = mid + 1
                else:
                    hi = mid - 1
            if best > 0:
                return [tiny_rendered[:best]]
        return [tiny_rendered]

    pieces: List[str] = []
    raw = block.raw

    while raw:
        lo, hi = 1, len(raw)
        best = 1

        # Binary search for maximum content that fits
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = FileBlock(rel_path=block.rel_path, raw=raw[:mid])
            rendered = render_block(candidate, fmt)

            if fits_budget(
                wrap_files_root(rendered, fmt),
                max_chars=max_chars,
                max_tokens=max_tokens,
                enc=enc,
            ):
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1

        piece_raw = raw[:best]
        raw = raw[best:]

        if raw:
            piece_raw += "\n\n[CONTINUES IN NEXT CHUNK]\n"

        rendered_piece = render_block(
            FileBlock(rel_path=block.rel_path, raw=piece_raw), fmt
        )

        # Safety: ensure rendered piece fits (may need trimming due to continuation marker)
        while (
            not fits_budget(
                wrap_files_root(rendered_piece, fmt),
                max_chars=max_chars,
                max_tokens=max_tokens,
                enc=enc,
            )
            and len(piece_raw) > 0
        ):
            piece_raw = piece_raw[:-1]
            rendered_piece = render_block(
                FileBlock(rel_path=block.rel_path, raw=piece_raw), fmt
            )

        pieces.append(rendered_piece)

    return pieces


def pack_chunks(
    blocks: List[FileBlock],
    fmt: str,
    *,
    max_chars: Optional[int],
    max_tokens: Optional[int],
    enc: Encoder,
    include_entries: bool = False,
) -> Union[List[str], List[ChunkWithEntries]]:
    """
    Pack rendered blocks into chunks respecting budgets, preferring file boundaries.

    Splits oversized single files as needed using split_big_file().

    Args:
        blocks: List of FileBlocks to pack.
        fmt: Output format ("xml" or "legacy").
        max_chars: Maximum characters per chunk.
        max_tokens: Maximum tokens per chunk.
        enc: Tiktoken encoder.
        include_entries: If True, return entries with each chunk for reporting.

    Returns:
        If include_entries is False: List of chunk strings.
        If include_entries is True: List of (chunk_string, entries) tuples.
    """
    chunks: List[str] = []
    chunk_entries: List[List[ChunkEntry]] = []
    cur: List[str] = []
    cur_entries: List[ChunkEntry] = []

    for b in blocks:
        rendered = render_block(b, fmt)

        if fits_budget(
            wrap_files_root(rendered, fmt),
            max_chars=max_chars,
            max_tokens=max_tokens,
            enc=enc,
        ):
            # File fits in a single chunk
            candidate = "".join(cur) + rendered
            if cur and not fits_budget(
                wrap_files_root(candidate, fmt),
                max_chars=max_chars,
                max_tokens=max_tokens,
                enc=enc,
            ):
                # Current chunk is full, start new one
                chunks.append(wrap_files_root("".join(cur), fmt))
                chunk_entries.append(cur_entries)
                cur = []
                cur_entries = []

            cur.append(rendered)
            cur_entries.append((b.rel_path, rendered))
        else:
            # File too big, need to split it
            if cur:
                chunks.append(wrap_files_root("".join(cur), fmt))
                chunk_entries.append(cur_entries)
                cur = []
                cur_entries = []

            pieces = split_big_file(
                b, fmt, max_chars=max_chars, max_tokens=max_tokens, enc=enc
            )
            for p in pieces:
                chunks.append(wrap_files_root(p, fmt))
                chunk_entries.append([(b.rel_path, p)])

    # Flush remaining content
    if cur:
        chunks.append(wrap_files_root("".join(cur), fmt))
        chunk_entries.append(cur_entries)

    if include_entries:
        return list(zip(chunks, chunk_entries))
    return chunks


def trim_largest_first(
    blocks: List[FileBlock], max_chars: int, keep_per_file: int
) -> Tuple[List[FileBlock], int]:
    """
    Trim content to fit within max_chars by truncating largest files first.

    Uses a heap-based approach for O(n log n) complexity instead of O(n²).

    Args:
        blocks: List of FileBlocks to trim (modified in place).
        max_chars: Maximum total characters.
        keep_per_file: Characters to keep per file when truncating.

    Returns:
        Tuple of (trimmed blocks, final total length).
    """
    total = sum(len(b.raw) for b in blocks)
    if total <= max_chars:
        return blocks, total

    # Build max-heap using negative lengths (heapq is min-heap)
    # Format: (-length, index) to get largest first
    heap: List[Tuple[int, int]] = [(-len(b.raw), i) for i, b in enumerate(blocks)]
    heapq.heapify(heap)

    while total > max_chars and heap:
        neg_len, i = heapq.heappop(heap)
        current_len = -neg_len
        b = blocks[i]

        # Skip if block was already processed (length changed)
        if len(b.raw) != current_len:
            continue

        content = b.raw
        truncation_marker = "\n\n[TRUNCATED: exceeded max-chars budget]\n"
        potential_len = keep_per_file + len(truncation_marker)

        # Only truncate if it would actually reduce size
        if len(content) > keep_per_file and potential_len < len(content):
            new_content = content[:keep_per_file] + truncation_marker
            blocks[i] = FileBlock(rel_path=b.rel_path, raw=new_content)
            total = total - current_len + len(new_content)
            # Push updated block back to heap
            heapq.heappush(heap, (-len(new_content), i))
        else:
            # Can't meaningfully trim further; drop the file content
            omit_msg = "[OMITTED: exceeded max-chars budget]\n"
            blocks[i] = FileBlock(rel_path=b.rel_path, raw=omit_msg)
            total = total - current_len + len(omit_msg)

        # Avoid infinite loop if all blocks are minimal
        if total > max_chars and all(len(block.raw) <= 64 for block in blocks):
            break

    return blocks, total


def print_chunk_file_tokens(
    entries: List[ChunkEntry],
    enc: Encoder,
    model: Optional[str],
    encoding_name: Optional[str],
    label: str,
) -> None:
    """
    Print per-file token counts for a chunk.

    Args:
        entries: List of (rel_path, rendered_text) tuples.
        enc: Tiktoken encoder.
        model: Model name for fallback counting.
        encoding_name: Encoding name for fallback counting.
        label: Label for the output (e.g., "Chunk 1/3").
    """
    import sys
    from .tokenization import count_tokens_with_encoder

    print(f"[INFO] {label} file tokens:", file=sys.stderr)
    if not entries:
        print("[INFO]   (no files)", file=sys.stderr)
        return

    rows: List[Tuple[int, int, str, Optional[str]]] = []
    for idx, (rel_path, rendered) in enumerate(entries):
        tok, note = count_tokens_with_encoder(rendered, enc, model, encoding_name)
        tok_val = tok if tok is not None else -1
        rows.append((tok_val, idx, rel_path, note))

    rows.sort(key=lambda r: (r[0], r[1]))

    for tok_val, _, rel_path, note in rows:
        tok_str = f"{tok_val}" if tok_val >= 0 else f"unavailable ({note})"
        print(f"[INFO]   {rel_path}: {tok_str}", file=sys.stderr)
