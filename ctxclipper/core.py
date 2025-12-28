"""Core orchestration logic for ctxclipper."""

import logging
import os
import sys
from typing import List, Optional, Tuple

from .chunking import pack_chunks, print_chunk_file_tokens, trim_largest_first
from .clipboard import copy_to_clipboard
from .discovery import discover_files, is_binary
from .rendering import (
    join_texts,
    read_text_file,
    render_block,
    render_section,
    wrap_chunk,
    wrap_files_root,
)
from .tokenization import (
    count_tokens_with_encoder,
    fits_budget,
    get_tokenizer,
    safe_token_len,
    token_len,
)
from .types import ChunkWithEntries, Encoder, FileBlock

__all__ = ["run"]

logger = logging.getLogger(__name__)


def read_file_blocks(
    base_path: str,
    rel_paths: List[str],
    max_file_bytes: int,
) -> Tuple[List[FileBlock], int, int, int]:
    """
    Read files and create FileBlocks.

    Args:
        base_path: Base directory path.
        rel_paths: List of relative file paths.
        max_file_bytes: Maximum bytes to read per file.

    Returns:
        Tuple of (blocks, skipped_binary, skipped_errors, truncated_files).
    """
    blocks: List[FileBlock] = []
    skipped_binary = 0
    skipped_errors = 0
    truncated_files = 0

    for rel in rel_paths:
        abs_path = os.path.join(base_path, rel)
        if not os.path.isfile(abs_path):
            continue

        if is_binary(abs_path):
            skipped_binary += 1
            continue

        try:
            with open(abs_path, "rb") as f:
                raw = f.read(max_file_bytes + 1)

            suffix = ""
            if len(raw) > max_file_bytes:
                truncated_files += 1
                raw = raw[:max_file_bytes]
                suffix = "\n\n[TRUNCATED: file exceeded max-file-bytes]\n"

            content = raw.decode("utf-8", errors="replace") + suffix
            blocks.append(FileBlock(rel_path=rel, raw=content))
        except Exception:
            skipped_errors += 1

    return blocks, skipped_binary, skipped_errors, truncated_files


def adjust_budget(
    base: Optional[int], overhead: int, label: str
) -> Tuple[Optional[int], bool]:
    """
    Adjust budget by subtracting overhead.

    Args:
        base: Base budget (can be None).
        overhead: Amount to subtract.
        label: Label for warning messages.

    Returns:
        Tuple of (adjusted_budget, was_adjusted).
    """
    if base is None or overhead <= 0:
        return base, False
    if overhead >= base:
        logger.warning(
            "%s overhead %d >= budget %d; cannot fully enforce budget.",
            label,
            overhead,
            base,
        )
        return base, False
    return base - overhead, True


def run(args) -> int:
    """
    Main execution logic for ctxclipper.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    base_path = os.path.abspath(args.path)
    if not os.path.isdir(base_path):
        logger.error("Not a directory: %s", base_path)
        return 1

    # Read preamble and question content
    preamble_parts = [read_text_file(p) for p in args.preamble]
    question_parts: List[str] = []
    for kind, val in args.question_parts:
        if kind == "file":
            question_parts.append(read_text_file(val))
        else:
            question_parts.append(val)

    preamble_text = join_texts(preamble_parts)
    question_text = join_texts(question_parts)
    preamble_rendered = render_section("preamble", preamble_text, args.format)
    question_rendered = render_section("question", question_text, args.format)

    # Discover files
    ignore_names = set(args.ignore)
    ignore_globs = list(args.ignore_glob)
    include_dotfiles = bool(args.include_dotfiles)

    rel_paths, used_git = discover_files(
        base_path, ignore_names, ignore_globs, include_dotfiles
    )

    # Read file contents
    blocks, skipped_binary, skipped_errors, truncated_files = read_file_blocks(
        base_path, rel_paths, args.max_file_bytes
    )

    # Initialize tokenizer
    tokenizer_result = get_tokenizer(args.model, args.encoding)
    enc = tokenizer_result.encoder
    enc_name = getattr(enc, "name", "none") if enc is not None else "none"
    model_label = args.model if args.model else "none"
    source_label = tokenizer_result.source

    print(
        f"[INFO] Tokenizer: model={model_label} encoding={enc_name} source={source_label}",
        file=sys.stderr,
    )

    if tokenizer_result.source == "override" and tokenizer_result.note:
        print(f"[INFO] {tokenizer_result.note}", file=sys.stderr)
    if tokenizer_result.source == "encoding" and args.model:
        if tokenizer_result.note:
            print(f"[WARN] {tokenizer_result.note}", file=sys.stderr)
    if tokenizer_result.source == "none":
        print(f"[WARN] Tokenizer unavailable: {tokenizer_result.note}", file=sys.stderr)
        if args.max_tokens is not None:
            print(
                "[WARN] max-tokens requested but tiktoken encoder unavailable; "
                "token budget will be ignored.",
                file=sys.stderr,
            )

    # Calculate budgets
    if args.max_chars == 0:
        max_chars_budget: Optional[int] = None
    else:
        max_chars_budget = (
            None if args.max_chars is None else max(0, args.max_chars - args.reserve_chars)
        )
    max_tokens_budget: Optional[int] = (
        None if args.max_tokens is None else max(0, args.max_tokens - args.reserve_tokens)
    )

    # Calculate overhead from preamble/question
    prefix_chars = len(preamble_rendered)
    suffix_chars = len(question_rendered)
    prefix_tokens = safe_token_len(enc, preamble_rendered)
    suffix_tokens = safe_token_len(enc, question_rendered)
    max_overhead_chars = max(prefix_chars, suffix_chars)
    max_overhead_tokens = max(prefix_tokens, suffix_tokens)

    adj_max_chars_budget, _ = adjust_budget(max_chars_budget, max_overhead_chars, "Char")
    adj_max_tokens_budget, _ = adjust_budget(max_tokens_budget, max_overhead_tokens, "Token")

    # Render full content for budget check
    files_rendered = wrap_files_root(
        "".join(render_block(b, args.format) for b in blocks), args.format
    )
    full_rendered = f"{preamble_rendered}{files_rendered}{question_rendered}"

    chunk_info: Optional[str] = None

    # Determine if splitting is needed
    need_split = args.split and not fits_budget(
        full_rendered, max_chars=max_chars_budget, max_tokens=max_tokens_budget, enc=enc
    )

    if need_split:
        total_chars, token_count, token_note, chunk_info = _handle_split_mode(
            args=args,
            blocks=blocks,
            preamble_rendered=preamble_rendered,
            question_rendered=question_rendered,
            enc=enc,
            max_chars_budget=max_chars_budget,
            max_tokens_budget=max_tokens_budget,
            adj_max_chars_budget=adj_max_chars_budget,
            adj_max_tokens_budget=adj_max_tokens_budget,
        )
    else:
        total_chars, token_count, token_note = _handle_single_mode(
            args=args,
            blocks=blocks,
            preamble_rendered=preamble_rendered,
            question_rendered=question_rendered,
            enc=enc,
            max_chars_budget=max_chars_budget,
            max_tokens_budget=max_tokens_budget,
            full_rendered=full_rendered,
        )

    # Print stats
    print(f"[INFO] Mode: {'git' if used_git else 'scan'}", file=sys.stderr)
    print(
        f"[INFO] Files included: {len(blocks)} | skipped binary: {skipped_binary} "
        f"| skipped errors: {skipped_errors}",
        file=sys.stderr,
    )
    print(f"[INFO] Truncated (max-file-bytes): {truncated_files}", file=sys.stderr)
    print(
        f"[INFO] Total chars: {total_chars} "
        f"(char_budget={max_chars_budget if max_chars_budget is not None else 'none'}, "
        f"max={args.max_chars}, reserve={args.reserve_chars})",
        file=sys.stderr,
    )

    if chunk_info:
        print(chunk_info, file=sys.stderr)

    if token_count is not None:
        msg = f"[INFO] Token estimate (tiktoken): {token_count}"
        if token_note:
            msg += f" | note: {token_note}"
        print(msg, file=sys.stderr)
    else:
        print(f"[WARN] Token estimate unavailable: {token_note}", file=sys.stderr)

    return 0


def _handle_split_mode(
    args,
    blocks: List[FileBlock],
    preamble_rendered: str,
    question_rendered: str,
    enc: Encoder,
    max_chars_budget: Optional[int],
    max_tokens_budget: Optional[int],
    adj_max_chars_budget: Optional[int],
    adj_max_tokens_budget: Optional[int],
) -> Tuple[int, Optional[int], Optional[str], str]:
    """Handle chunked output mode."""
    chunk_pairs: List[ChunkWithEntries] = pack_chunks(
        blocks,
        args.format,
        max_chars=adj_max_chars_budget,
        max_tokens=adj_max_tokens_budget,
        enc=enc,
        include_entries=True,
    )

    if not chunk_pairs:
        chunk_pairs = [(wrap_files_root("", args.format), [])]

    # Handle case where preamble+question don't fit in single chunk
    if preamble_rendered and question_rendered and len(chunk_pairs) == 1:
        combined = f"{preamble_rendered}{chunk_pairs[0][0]}{question_rendered}"
        if not fits_budget(
            combined, max_chars=max_chars_budget, max_tokens=max_tokens_budget, enc=enc
        ):
            chunk_pairs.append((wrap_files_root("", args.format), []))

    # Add preamble to first chunk
    if preamble_rendered:
        chunk_pairs[0] = (f"{preamble_rendered}{chunk_pairs[0][0]}", chunk_pairs[0][1])

    # Add question to last chunk
    if question_rendered:
        last_text, last_entries = chunk_pairs[-1]
        chunk_pairs[-1] = (f"{last_text}{question_rendered}", last_entries)

    # Apply optional chunk wrapper
    wrapped_chunks: List[str] = []
    wrapped_entries: List[List[Tuple[str, str]]] = []
    total_chunk_count = len(chunk_pairs)

    for idx, (chunk, entries) in enumerate(chunk_pairs, start=1):
        wrapped = wrap_chunk(chunk, idx, total_chunk_count, args.chunk_wrap, args.format)
        if (
            not fits_budget(
                wrapped, max_chars=max_chars_budget, max_tokens=max_tokens_budget, enc=enc
            )
            and args.chunk_wrap != "none"
        ):
            wrapped = chunk
        wrapped_chunks.append(wrapped)
        wrapped_entries.append(entries)

    # Warn about over-budget chunks
    for i, ch in enumerate(wrapped_chunks, start=1):
        if not fits_budget(
            ch, max_chars=max_chars_budget, max_tokens=max_tokens_budget, enc=enc
        ):
            print(
                f"[WARN] Chunk {i} exceeds budget after preamble/question; "
                "consider increasing limits.",
                file=sys.stderr,
            )
            break

    # Apply selection
    start_idx = max(1, args.start_chunk)
    total_chunks = len(wrapped_chunks)
    selected_indices = (
        [args.only_chunk]
        if args.only_chunk is not None
        else list(range(start_idx, total_chunks + 1))
    )
    selected_indices = [i for i in selected_indices if 1 <= i <= total_chunks]

    # Copy chunks
    for i_pos, global_idx in enumerate(selected_indices, start=1):
        chunk = wrapped_chunks[global_idx - 1]
        if not args.no_copy:
            if not copy_to_clipboard(chunk):
                sys.exit(2)
            tok, note = count_tokens_with_encoder(chunk, enc, args.model, args.encoding)
            tok_str = f"{tok} tokens" if tok is not None else f"tokens unavailable ({note})"
            print(
                f"[INFO] Copied chunk {global_idx}/{total_chunks} "
                f"({len(chunk)} chars, {tok_str})",
                file=sys.stderr,
            )

        print_chunk_file_tokens(
            wrapped_entries[global_idx - 1],
            enc,
            args.model,
            args.encoding,
            f"Chunk {global_idx}/{total_chunks}",
        )

        if not args.no_copy and args.interactive and i_pos < len(selected_indices):
            ans = input(
                "Paste it, then press Enter for next chunk (or 'q' to quit): "
            ).strip().lower()
            if ans == "q":
                break

    if args.stdout:
        separator = "\n\n" if args.chunk_wrap == "none" else ""
        selected_chunks = [wrapped_chunks[i - 1] for i in selected_indices]
        sys.stdout.write(separator.join(selected_chunks))

    # Calculate stats
    selected_chunks = [wrapped_chunks[i - 1] for i in selected_indices]
    total_chars = sum(len(c) for c in selected_chunks)
    token_count, token_note = count_tokens_with_encoder(
        "".join(selected_chunks), enc, args.model, args.encoding
    )
    max_len = max((len(c) for c in selected_chunks), default=0)
    max_tok = None
    if enc is not None:
        max_tok = max((token_len(enc, c) for c in selected_chunks), default=0)

    chunk_info = f"[INFO] Chunks: {len(selected_chunks)} (max_chunk_chars={max_len}"
    if max_tok is not None:
        chunk_info += f", max_chunk_tokens={max_tok}"
    chunk_info += f", char_budget={max_chars_budget if max_chars_budget is not None else 'none'}"
    if max_tokens_budget is not None:
        chunk_info += f", token_budget={max_tokens_budget}"
    chunk_info += ")"

    return total_chars, token_count, token_note, chunk_info


def _handle_single_mode(
    args,
    blocks: List[FileBlock],
    preamble_rendered: str,
    question_rendered: str,
    enc: Encoder,
    max_chars_budget: Optional[int],
    max_tokens_budget: Optional[int],
    full_rendered: str,
) -> Tuple[int, Optional[int], Optional[str]]:
    """Handle single-chunk output mode."""
    working_blocks = blocks

    # Optional trimming when split is off or not needed
    if (
        not fits_budget(
            full_rendered,
            max_chars=max_chars_budget,
            max_tokens=max_tokens_budget,
            enc=enc,
        )
        and args.trim == "largest"
        and not args.split
        and max_chars_budget is not None
    ):
        working_blocks, _ = trim_largest_first(
            blocks, max_chars_budget, args.keep_per_file
        )

    final_text = (
        f"{preamble_rendered}"
        f"{wrap_files_root(''.join(render_block(b, args.format) for b in working_blocks), args.format)}"
        f"{question_rendered}"
    )

    if not args.no_copy:
        if not copy_to_clipboard(final_text):
            sys.exit(2)

    entries = [(b.rel_path, render_block(b, args.format)) for b in working_blocks]
    print_chunk_file_tokens(entries, enc, args.model, args.encoding, "Chunk 1/1")

    if args.stdout:
        sys.stdout.write(final_text)

    total_chars = len(final_text)
    token_count, token_note = count_tokens_with_encoder(
        final_text, enc, args.model, args.encoding
    )

    return total_chars, token_count, token_note
