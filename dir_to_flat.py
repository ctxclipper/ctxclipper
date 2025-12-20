#!/usr/bin/env python3
import os
import re
import sys
import subprocess
import platform
import argparse
import fnmatch
from typing import List, Optional, Tuple, Set
from dataclasses import dataclass

# Optional imports are loaded lazily where needed


# ----------------------------
# Helpers
# ----------------------------

def is_binary(file_path: str) -> bool:
    """Heuristic: treat file as binary if first 4KB contains a NUL byte."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(4096)
        return b"\0" in chunk
    except Exception:
        return True  # unreadable -> skip


def copy_to_clipboard(text: str) -> bool:
    """
    Cross-platform clipboard copy.
    - macOS: pbcopy
    - Windows: clip (fallback to powershell Set-Clipboard)
    - Linux/BSD: wl-copy, then xclip, then xsel
    """
    system = platform.system()
    commands = []

    if system == "Darwin":
        commands = [["pbcopy"]]
    elif system == "Windows":
        commands = [
            ["clip"],
            ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value ([Console]::In.ReadToEnd())"],
        ]
    else:
        commands = [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]

    env = os.environ.copy()
    env["LANG"] = "en_US.UTF-8"

    for cmd in commands:
        try:
            p = subprocess.Popen(cmd, env=env, stdin=subprocess.PIPE)
            p.communicate(text.encode("utf-8"))
            if p.returncode == 0:
                return True
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"[WARN] Clipboard command {' '.join(cmd)} failed: {e}", file=sys.stderr)

    if system == "Darwin":
        hint = "pbcopy should exist on macOS; check PATH / permissions."
    elif system == "Windows":
        hint = "Ensure clip/powershell is available in this shell."
    else:
        hint = "Install wl-clipboard, xclip, or xsel."

    print(f"[ERROR] Clipboard copy unavailable. {hint}", file=sys.stderr)
    return False


def in_git_worktree(path: str) -> bool:
    try:
        subprocess.check_call(
            ["git", "-C", path, "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def git_list_files(base_path: str) -> List[str]:
    """
    Returns relative paths for tracked + untracked files,
    excluding ignored files (respects .gitignore + exclude-standard).
    """
    out = subprocess.check_output(
        ["git", "-C", base_path, "ls-files", "-z", "-c", "-o", "--exclude-standard"],
        stderr=subprocess.DEVNULL,
    )
    return [p.decode("utf-8", "replace") for p in out.split(b"\0") if p]


def load_gitignore_pathspec(base_path: str):
    """
    Best-effort .gitignore parsing for non-git mode using `pathspec`.
    Returns (spec, error_msg).
    """
    try:
        import pathspec
    except Exception:
        return None, "pathspec not installed"

    patterns = []
    gi = os.path.join(base_path, ".gitignore")
    if os.path.exists(gi):
        try:
            with open(gi, "r", encoding="utf-8", errors="replace") as f:
                patterns.extend([ln.rstrip("\n") for ln in f])
        except Exception:
            pass

    spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    return spec, None


def normalize_glob(pat: str) -> Tuple[str, bool]:
    """
    Normalize a glob pattern to POSIX-style separators.
    Returns (pattern, anchored) where anchored means "match from repo root".
    Leading "/" or "./" anchors the pattern.
    """
    pat = pat.replace("\\", "/")
    anchored = False
    if pat.startswith("./"):
        pat = pat[2:]
        anchored = True
    if pat.startswith("/"):
        anchored = True
        pat = pat.lstrip("/")
    return pat, anchored


def should_ignore_path(rel_path: str, ignore_names: Set[str], ignore_globs: List[str], include_dotfiles: bool) -> bool:
    parts = rel_path.split(os.sep)

    if not include_dotfiles and any(p.startswith(".") for p in parts):
        return True

    if any(p in ignore_names for p in parts):
        return True

    if ignore_globs:
        rel_posix = rel_path.replace(os.sep, "/")
        base = os.path.basename(rel_path)
        for pat in ignore_globs:
            pat_norm, anchored = normalize_glob(pat)
            if not pat_norm:
                continue
            if anchored:
                if fnmatch.fnmatch(rel_posix, pat_norm):
                    return True
                continue
            if fnmatch.fnmatch(rel_posix, pat_norm) or fnmatch.fnmatch(base, pat_norm):
                return True
            if "/" in pat_norm and fnmatch.fnmatch(rel_posix, f"*/{pat_norm}"):
                return True

    return False


# ----------------------------
# Output shaping / trimming
# ----------------------------

@dataclass
class FileBlock:
    rel_path: str
    raw: str  # unwrapped content


def xml_escape_attr(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace('"', "&quot;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


def cdata_wrap(text: str) -> str:
    # CDATA cannot contain the literal sequence "]]>"
    return "<![CDATA[" + text.replace("]]>", "]]]]><![CDATA[>") + "]]>"


def render_section(tag: str, text: str, fmt: str) -> str:
    if text is None or text == "":
        return ""
    if fmt == "xml":
        return f"<{tag}>\n{cdata_wrap(text)}\n</{tag}>\n"
    return f"=== {tag.upper()} ===\n{text}\n"


def read_text_file(path: str) -> str:
    try:
        with open(os.path.expanduser(path), "rb") as f:
            return f.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[ERROR] Failed to read file: {path} ({e})", file=sys.stderr)
        sys.exit(1)


def join_texts(parts: List[str]) -> str:
    cleaned = [p.rstrip("\n") for p in parts if p is not None]
    return "\n\n".join(cleaned)


def render_block(block: FileBlock, fmt: str) -> str:
    if fmt == "xml":
        escaped = xml_escape_attr(block.rel_path)
        header = f'<file path="{escaped}">\n'
        footer = "\n</file>\n"
        return f"{header}{cdata_wrap(block.raw)}{footer}"
    # legacy
    return f"=== FILE: {block.rel_path} ===\n{block.raw}\n"


def wrap_files_root(text: str, fmt: str) -> str:
    if fmt == "xml":
        return f"<files>\n{text}\n</files>\n"
    return text


def wrap_chunk(chunk: str, idx: int, total: int, wrap: str, fmt: str) -> str:
    """
    Optionally wrap a chunk to mark ordering.
    wrap: none|xml|legacy
    fmt is the file-level format; used only when wrap='xml' to stay consistent.
    """
    if wrap == "xml":
        return f'<chunk index="{idx}" total="{total}">\n{chunk}\n</chunk>\n'
    if wrap == "legacy":
        return f"=== CHUNK {idx}/{total} ===\n{chunk}"
    return chunk


def split_big_file(block: FileBlock, fmt: str, *, max_chars: Optional[int], max_tokens: Optional[int], enc) -> List[str]:
    """
    Split a single file's raw content into multiple rendered pieces, each <= budget.
    Uses binary search to find the largest prefix that fits when rendered.
    """
    if (max_chars is not None and max_chars <= 0) and (max_tokens is None):
        return []

    # If even an empty wrapper won't fit, emit a tiny omission marker slice
    empty_rendered = render_block(FileBlock(rel_path=block.rel_path, raw=""), fmt)
    if not fits_budget(wrap_files_root(empty_rendered, fmt), max_chars=max_chars, max_tokens=max_tokens, enc=enc):
        tiny_block = FileBlock(rel_path=block.rel_path, raw="[OMITTED: budget too small for wrapper]\n")
        tiny_rendered = render_block(tiny_block, fmt)
        # best-effort truncate by chars if available
        if max_chars is not None and max_chars > 0:
            return [tiny_rendered[:max_chars]]
        # fallback: try to find smallest prefix that fits token budget
        if enc is not None and max_tokens is not None and max_tokens > 0:
            for cut in range(len(tiny_rendered), 0, -1):
                if fits_budget(wrap_files_root(tiny_rendered[:cut], fmt), max_chars=max_chars, max_tokens=max_tokens, enc=enc):
                    return [tiny_rendered[:cut]]
        return [tiny_rendered]

    pieces: List[str] = []
    raw = block.raw

    while raw:
        lo, hi = 1, len(raw)
        best = 1

        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = FileBlock(rel_path=block.rel_path, raw=raw[:mid])
            rendered = render_block(candidate, fmt)

            if fits_budget(wrap_files_root(rendered, fmt), max_chars=max_chars, max_tokens=max_tokens, enc=enc):
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1

        piece_raw = raw[:best]
        raw = raw[best:]

        if raw:
            piece_raw += "\n\n[CONTINUES IN NEXT CHUNK]\n"

        rendered_piece = render_block(FileBlock(rel_path=block.rel_path, raw=piece_raw), fmt)
        while not fits_budget(wrap_files_root(rendered_piece, fmt), max_chars=max_chars, max_tokens=max_tokens, enc=enc) and len(piece_raw) > 0:
            piece_raw = piece_raw[:-1]
            rendered_piece = render_block(FileBlock(rel_path=block.rel_path, raw=piece_raw), fmt)
        pieces.append(rendered_piece)

    return pieces


def pack_chunks(blocks: List[FileBlock], fmt: str, *, max_chars: Optional[int], max_tokens: Optional[int], enc) -> List[str]:
    """
    Pack rendered blocks into chunks respecting budgets, preferring file boundaries.
    Splits oversized single files as needed.
    """
    chunks: List[str] = []
    cur: List[str] = []
    cur_len = 0

    for b in blocks:
        rendered = render_block(b, fmt)
        if fits_budget(wrap_files_root(rendered, fmt), max_chars=max_chars, max_tokens=max_tokens, enc=enc):
            candidate = "".join(cur) + rendered
            if cur and not fits_budget(wrap_files_root(candidate, fmt), max_chars=max_chars, max_tokens=max_tokens, enc=enc):
                chunks.append(wrap_files_root("".join(cur), fmt))
                cur = []
                cur_len = 0
            cur.append(rendered)
            cur_len += len(rendered)
        else:
            # flush current chunk, then split the big file
            if cur:
                chunks.append(wrap_files_root("".join(cur), fmt))
                cur = []
                cur_len = 0
            pieces = split_big_file(b, fmt, max_chars=max_chars, max_tokens=max_tokens, enc=enc)
            chunks.extend(wrap_files_root(p, fmt) for p in pieces)

    if cur:
        chunks.append(wrap_files_root("".join(cur), fmt))

    return chunks


def pack_chunks_with_entries(
    blocks: List[FileBlock], fmt: str, *, max_chars: Optional[int], max_tokens: Optional[int], enc
) -> List[Tuple[str, List[Tuple[str, str]]]]:
    """
    Pack rendered blocks into chunks respecting budgets, preferring file boundaries.
    Returns list of (chunk_text, [(rel_path, rendered_block_text), ...]) pairs.
    """
    chunks: List[Tuple[str, List[Tuple[str, str]]]] = []
    cur: List[str] = []
    cur_entries: List[Tuple[str, str]] = []

    for b in blocks:
        rendered = render_block(b, fmt)
        if fits_budget(wrap_files_root(rendered, fmt), max_chars=max_chars, max_tokens=max_tokens, enc=enc):
            candidate = "".join(cur) + rendered
            if cur_entries and not fits_budget(wrap_files_root(candidate, fmt), max_chars=max_chars, max_tokens=max_tokens, enc=enc):
                chunks.append((wrap_files_root("".join(cur), fmt), cur_entries))
                cur = []
                cur_entries = []
            cur.append(rendered)
            cur_entries.append((b.rel_path, rendered))
        else:
            if cur_entries:
                chunks.append((wrap_files_root("".join(cur), fmt), cur_entries))
                cur = []
                cur_entries = []
            pieces = split_big_file(b, fmt, max_chars=max_chars, max_tokens=max_tokens, enc=enc)
            for p in pieces:
                chunks.append((wrap_files_root(p, fmt), [(b.rel_path, p)]))

    if cur_entries:
        chunks.append((wrap_files_root("".join(cur), fmt), cur_entries))

    return chunks


def trim_largest_first(blocks: List[FileBlock], max_chars: int, keep_per_file: int) -> Tuple[List[FileBlock], int]:
    """
    If total exceeds max_chars, iteratively truncate the largest blocks.
    Greedy, good enough for staying under a char budget.
    """
    def total_len(bs): return sum(len(b.raw) for b in bs)

    total = total_len(blocks)
    if total <= max_chars:
        return blocks, total

    while total > max_chars and blocks:
        i = max(range(len(blocks)), key=lambda k: len(blocks[k].raw))
        b = blocks[i]
        content = b.raw

        if len(content) > keep_per_file:
            new_content = content[:keep_per_file] + "\n\n[TRUNCATED: exceeded max-chars budget]\n"
            blocks[i] = FileBlock(rel_path=b.rel_path, raw=new_content)
        else:
            # Can't meaningfully trim further; drop the file content
            blocks[i] = FileBlock(rel_path=b.rel_path, raw="[OMITTED: exceeded max-chars budget]\n")

        total = total_len(blocks)

        # Avoid infinite loop if headers dominate
        if total > max_chars and all(len(block.raw) <= 64 for block in blocks):
            break

    return blocks, total


def count_tokens(text: str, model: Optional[str], encoding_name: Optional[str]):
    """
    Prefer tiktoken encoding_for_model; fall back to explicit encoding.
    Returns (token_count or None, note or None).
    """
    try:
        import tiktoken
    except Exception:
        return None, "tiktoken not installed (pip install tiktoken)"

    try:
        if model:
            enc = tiktoken.encoding_for_model(model)
        else:
            enc = tiktoken.get_encoding(encoding_name or "o200k_base")
        return len(enc.encode(text)), None
    except KeyError:
        try:
            enc = tiktoken.get_encoding(encoding_name or "o200k_base")
            return len(enc.encode(text)), f"Unknown model '{model}', used encoding '{encoding_name or 'o200k_base'}'"
        except Exception as e:
            return None, f"Tokenization failed: {e}"
    except Exception as e:
        return None, f"Tokenization failed: {e}"


def get_tokenizer(model: Optional[str], encoding_name: Optional[str]):
    """
    Returns (encoder or None, note or None, source).
    source in {"model","override","encoding","none"}.
    """
    try:
        import tiktoken
    except Exception:
        return None, "tiktoken not installed (pip install tiktoken)", "none"

    model_raw = model or ""
    model_norm = model_raw.strip().lower()

    if model_norm:
        try:
            enc = tiktoken.encoding_for_model(model_raw)
            return enc, None, "model"
        except Exception:
            pass

        is_gpt5 = model_norm.startswith("gpt-5") or model_norm.startswith("gpt5")
        is_o_family = re.match(r"^o(1|3|4)(?:[\\-\\.]|$)", model_norm) is not None
        if is_gpt5 or is_o_family:
            try:
                enc = tiktoken.get_encoding("o200k_base")
                fam = "gpt-5.*" if is_gpt5 else "o-series"
                note = f"tiktoken lacks {fam} mapping; using o200k_base"
                return enc, note, "override"
            except Exception as e:
                return None, f"Tokenization failed: {e}", "none"

    try:
        enc = tiktoken.get_encoding(encoding_name or "o200k_base")
        note = None
        if model_norm:
            note = f"Unknown model '{model_raw}', used encoding '{enc.name}'"
        return enc, note, "encoding"
    except Exception as e:
        return None, f"Tokenization failed: {e}", "none"


def count_tokens_with_enc(text: str, enc, model: Optional[str], encoding_name: Optional[str]):
    if enc is not None:
        return len(enc.encode(text)), None
    return count_tokens(text, model, encoding_name)


def token_len(enc, text: str) -> int:
    return len(enc.encode(text))


def fits_budget(rendered: str, *, max_chars: Optional[int], max_tokens: Optional[int], enc) -> bool:
    if max_chars is not None and len(rendered) > max_chars:
        return False
    if max_tokens is not None and enc is not None and token_len(enc, rendered) > max_tokens:
        return False
    return True


def safe_token_len(enc, text: str) -> int:
    if enc is None or not text:
        return 0
    return len(enc.encode(text))


def print_chunk_file_tokens(entries: List[Tuple[str, str]], enc, model: Optional[str], encoding_name: Optional[str], label: str) -> None:
    print(f"[INFO] {label} file tokens:", file=sys.stderr)
    if not entries:
        print("[INFO]   (no files)", file=sys.stderr)
        return
    for rel_path, rendered in entries:
        tok, note = count_tokens_with_enc(rendered, enc, model, encoding_name)
        tok_str = f"{tok}" if tok is not None else f"unavailable ({note})"
        print(f"[INFO]   {rel_path}: {tok_str}", file=sys.stderr)


# ----------------------------
# Main
# ----------------------------

def main():
    parser = argparse.ArgumentParser(description="Clipboard-first, gitignore-first directory flattener for LLM context.")
    parser.add_argument("path", nargs="?", default=".", help="Directory to process (default: .)")

    def _question_file(arg: str):
        return ("file", arg)

    def _question_text(arg: str):
        return ("text", arg)

    default_ignore = {
        ".git", ".DS_Store", "__pycache__", "node_modules",
        ".venv", "venv", ".idea", ".vscode",
        "dist", "build", "target", "coverage", ".next"
    }

    parser.add_argument("--ignore", nargs="*", default=sorted(default_ignore), help="Extra names to ignore (match any path component)")
    parser.add_argument(
        "--ignore-glob",
        "--ignore-globs",
        nargs="*",
        default=[],
        help="Glob patterns to ignore (e.g. '*.lock' 'dist/**'); use leading '/' or './' to anchor to repo root",
    )
    parser.add_argument("--include-dotfiles", action="store_true", help="Include dotfiles and dot-directories")
    parser.add_argument("--no-copy", action="store_true", help="Do not copy to clipboard (escape hatch)")
    parser.add_argument("--stdout", action="store_true", help="Also print full output to stdout (default: clipboard only)")
    parser.add_argument("--format", choices=["xml", "legacy"], default="xml", help="Output format (default: xml)")
    parser.add_argument("--preamble", action="append", default=[], help="File to prepend before files (can repeat)")
    parser.add_argument("--question-file", action="append", type=_question_file, dest="question_parts", default=[], help="File to append after files (can repeat)")
    parser.add_argument("--question-text", action="append", type=_question_text, dest="question_parts", default=[], help="Literal text to append after files (can repeat)")

    # Token counting
    parser.add_argument("--model", default="gpt-5.2", help="Model name for tiktoken.encoding_for_model (default: gpt-5.2)")
    parser.add_argument("--encoding", default=None, help="Fallback encoding name (default: o200k_base)")
    parser.add_argument("--max-tokens", type=int, default=160_000, help="Max tokens per chunk (preferred split limit; default 160000)")
    parser.add_argument("--reserve-tokens", type=int, default=16_000, help="Reserve tokens for your own instruction text (default 16000)")

    # Size / chunking guards
    parser.add_argument("--max-chars", type=int, default=507_932, help="Max total chars to fit chat input; set 0 to disable (default: 507932)")
    parser.add_argument("--reserve-chars", type=int, default=2_000, help="Reserve chars for your own instruction text")
    parser.add_argument("--trim", choices=["none", "largest"], default="largest", help="How to reduce if over max-chars")
    parser.add_argument("--keep-per-file", type=int, default=8_000, help="When trimming, keep this many chars per large file")
    parser.add_argument("--max-file-bytes", type=int, default=2_000_000, help="Hard cap per file read (bytes)")

    split_group = parser.add_mutually_exclusive_group()
    split_group.add_argument("--split", dest="split", action="store_true", help="Enable chunk splitting if over budget")
    split_group.add_argument("--no-split", dest="split", action="store_false", help="Disable chunk splitting; use trim policy")

    inter_group = parser.add_mutually_exclusive_group()
    inter_group.add_argument("--interactive", dest="interactive", action="store_true", help="Wait for Enter between chunk copies")
    inter_group.add_argument("--non-interactive", dest="interactive", action="store_false", help="Do not prompt between chunks")

    parser.set_defaults(split=True, interactive=True)

    parser.add_argument("--chunk-wrap", choices=["none", "xml", "legacy"], default="none", help="Optional chunk wrapper marking order (default: none)")
    parser.add_argument("--start-chunk", type=int, default=1, help="Start copying from this 1-based chunk index")
    parser.add_argument("--only-chunk", type=int, default=None, help="Copy only this 1-based chunk index")

    args = parser.parse_args()

    base_path = os.path.abspath(args.path)
    if not os.path.isdir(base_path):
        print(f"[ERROR] Not a directory: {base_path}", file=sys.stderr)
        sys.exit(1)

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

    ignore_names = set(args.ignore)
    ignore_globs = list(args.ignore_glob)
    include_dotfiles = bool(args.include_dotfiles)

    rel_paths: List[str] = []
    used_git = False

    if in_git_worktree(base_path):
        try:
            rel_paths = git_list_files(base_path)
            used_git = True
        except Exception as e:
            print(f"[WARN] git listing failed, falling back to scan: {e}", file=sys.stderr)

    gitignore_spec = None
    if not used_git:
        gitignore_spec, gi_err = load_gitignore_pathspec(base_path)
        if gi_err:
            print(f"[WARN] Non-git mode: {gi_err}. .gitignore will NOT be applied without pathspec.", file=sys.stderr)

        for root, dirs, files in os.walk(base_path):
            pruned = []
            for d in dirs:
                rel_d = os.path.relpath(os.path.join(root, d), base_path)
                if should_ignore_path(rel_d, ignore_names, ignore_globs, include_dotfiles):
                    continue
                if gitignore_spec and gitignore_spec.match_file(rel_d):
                    continue
                pruned.append(d)
            dirs[:] = pruned

            for f in files:
                rel_f = os.path.relpath(os.path.join(root, f), base_path)
                if should_ignore_path(rel_f, ignore_names, ignore_globs, include_dotfiles):
                    continue
                if gitignore_spec and gitignore_spec.match_file(rel_f):
                    continue
                rel_paths.append(rel_f)

    # Apply ignores in git mode too
    filtered: List[str] = []
    for rel in rel_paths:
        rel_norm = rel.replace("/", os.sep)  # git returns /
        if should_ignore_path(rel_norm, ignore_names, ignore_globs, include_dotfiles):
            continue
        filtered.append(rel_norm)

    filtered.sort()

    blocks: List[FileBlock] = []
    skipped_binary = 0
    skipped_errors = 0
    truncated_files = 0

    for rel in filtered:
        abs_path = os.path.join(base_path, rel)
        if not os.path.isfile(abs_path):
            continue

        if is_binary(abs_path):
            skipped_binary += 1
            continue

        try:
            with open(abs_path, "rb") as f:
                raw = f.read(args.max_file_bytes + 1)

            suffix = ""
            if len(raw) > args.max_file_bytes:
                truncated_files += 1
                raw = raw[: args.max_file_bytes]
                suffix = "\n\n[TRUNCATED: file exceeded max-file-bytes]\n"

            content = raw.decode("utf-8", errors="replace") + suffix
            blocks.append(FileBlock(rel_path=rel, raw=content))
        except Exception:
            skipped_errors += 1

    enc, enc_note, enc_source = get_tokenizer(args.model, args.encoding)
    enc_name = getattr(enc, "name", "none") if enc is not None else "none"
    model_label = args.model if args.model else "none"
    source_label = enc_source or "none"
    print(f"[INFO] Tokenizer: model={model_label} encoding={enc_name} source={source_label}", file=sys.stderr)
    if enc_source == "override" and enc_note:
        print(f"[INFO] {enc_note}", file=sys.stderr)
    if enc_source == "encoding" and args.model:
        if enc_note:
            print(f"[WARN] {enc_note}", file=sys.stderr)
    if enc_source == "none":
        print(f"[WARN] Tokenizer unavailable: {enc_note}", file=sys.stderr)
        if args.max_tokens is not None:
            print("[WARN] max-tokens requested but tiktoken encoder unavailable; token budget will be ignored.", file=sys.stderr)

    if args.max_chars == 0:
        max_chars_budget = None
    else:
        max_chars_budget = None if args.max_chars is None else max(0, args.max_chars - args.reserve_chars)
    max_tokens_budget = None if args.max_tokens is None else max(0, args.max_tokens - args.reserve_tokens)

    def adjust_budget(base: Optional[int], overhead: int, label: str) -> Tuple[Optional[int], bool]:
        if base is None or overhead <= 0:
            return base, False
        if overhead >= base:
            print(f"[WARN] {label} overhead {overhead} >= budget {base}; cannot fully enforce budget.", file=sys.stderr)
            return base, False
        return base - overhead, True

    files_rendered = wrap_files_root("".join(render_block(b, args.format) for b in blocks), args.format)
    full_rendered = f"{preamble_rendered}{files_rendered}{question_rendered}"

    prefix_chars = len(preamble_rendered)
    suffix_chars = len(question_rendered)
    prefix_tokens = safe_token_len(enc, preamble_rendered)
    suffix_tokens = safe_token_len(enc, question_rendered)

    full_tokens_est = None
    if enc is not None:
        full_tokens_est = token_len(enc, full_rendered)

    chunk_info = None

    max_overhead_chars = max(prefix_chars, suffix_chars)
    max_overhead_tokens = max(prefix_tokens, suffix_tokens)
    adj_max_chars_budget, _ = adjust_budget(max_chars_budget, max_overhead_chars, "Char")
    adj_max_tokens_budget, _ = adjust_budget(max_tokens_budget, max_overhead_tokens, "Token")

    need_split = args.split and not fits_budget(
        full_rendered, max_chars=max_chars_budget, max_tokens=max_tokens_budget, enc=enc
    )

    if need_split:
        chunk_pairs = pack_chunks_with_entries(
            blocks, args.format, max_chars=adj_max_chars_budget, max_tokens=adj_max_tokens_budget, enc=enc
        )
        if not chunk_pairs:
            chunk_pairs = [(wrap_files_root("", args.format), [])]

        if preamble_rendered and question_rendered and len(chunk_pairs) == 1:
            combined = f"{preamble_rendered}{chunk_pairs[0][0]}{question_rendered}"
            if not fits_budget(combined, max_chars=max_chars_budget, max_tokens=max_tokens_budget, enc=enc):
                chunk_pairs.append((wrap_files_root("", args.format), []))

        if preamble_rendered:
            chunk_pairs[0] = (f"{preamble_rendered}{chunk_pairs[0][0]}", chunk_pairs[0][1])
        if question_rendered:
            last_text, last_entries = chunk_pairs[-1]
            chunk_pairs[-1] = (f"{last_text}{question_rendered}", last_entries)

        # Apply optional chunk wrapper, with a safeguard if wrapper would overflow budget
        wrapped_chunks: List[str] = []
        wrapped_entries: List[List[Tuple[str, str]]] = []
        total_chunk_count = len(chunk_pairs)
        for idx, (chunk, entries) in enumerate(chunk_pairs, start=1):
            wrapped = wrap_chunk(chunk, idx, total_chunk_count, args.chunk_wrap, args.format)
            if not fits_budget(wrapped, max_chars=max_chars_budget, max_tokens=max_tokens_budget, enc=enc) and args.chunk_wrap != "none":
                wrapped = chunk
            wrapped_chunks.append(wrapped)
            wrapped_entries.append(entries)
        for i, ch in enumerate(wrapped_chunks, start=1):
            if not fits_budget(ch, max_chars=max_chars_budget, max_tokens=max_tokens_budget, enc=enc):
                print(f"[WARN] Chunk {i} exceeds budget after preamble/question; consider increasing limits.", file=sys.stderr)
                break

        # Apply selection (only-chunk / start-chunk)
        start_idx = max(1, args.start_chunk)
        total_chunks = len(wrapped_chunks)
        selected_indices = (
            [args.only_chunk] if args.only_chunk is not None else list(range(start_idx, total_chunks + 1))
        )
        selected_indices = [i for i in selected_indices if 1 <= i <= total_chunks]

        selected_chunks = [wrapped_chunks[i - 1] for i in selected_indices]
        selected_entries = [wrapped_entries[i - 1] for i in selected_indices]

        for i_pos, global_idx in enumerate(selected_indices, start=1):
            chunk = wrapped_chunks[global_idx - 1]
            if not args.no_copy:
                if not copy_to_clipboard(chunk):
                    sys.exit(2)
                tok, note = count_tokens_with_enc(chunk, enc, args.model, args.encoding)
                tok_str = f"{tok} tokens" if tok is not None else f"tokens unavailable ({note})"
                print(f"[INFO] Copied chunk {global_idx}/{total_chunks} ({len(chunk)} chars, {tok_str})", file=sys.stderr)
            print_chunk_file_tokens(wrapped_entries[global_idx - 1], enc, args.model, args.encoding, f"Chunk {global_idx}/{total_chunks}")
            if not args.no_copy and args.interactive and i_pos < len(selected_indices):
                ans = input("Paste it, then press Enter for next chunk (or 'q' to quit): ").strip().lower()
                if ans == "q":
                    break
        if args.stdout:
            separator = "\n\n" if args.chunk_wrap == "none" else ""
            sys.stdout.write(separator.join(selected_chunks))

        total_chars = sum(len(c) for c in selected_chunks)
        token_count, token_note = count_tokens_with_enc("".join(selected_chunks), enc, args.model, args.encoding)
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
    else:
        # Optional trimming when split is off or not needed
        working_blocks = blocks
        if not fits_budget(full_rendered, max_chars=max_chars_budget, max_tokens=max_tokens_budget, enc=enc) and args.trim == "largest" and not args.split and max_chars_budget is not None:
            working_blocks, _ = trim_largest_first(blocks, max_chars_budget, args.keep_per_file)
        final_text = f"{preamble_rendered}{wrap_files_root(''.join(render_block(b, args.format) for b in working_blocks), args.format)}{question_rendered}"

        if not args.no_copy:
            if not copy_to_clipboard(final_text):
                sys.exit(2)
        entries = [(b.rel_path, render_block(b, args.format)) for b in working_blocks]
        print_chunk_file_tokens(entries, enc, args.model, args.encoding, "Chunk 1/1")
        if args.stdout:
            sys.stdout.write(final_text)

        total_chars = len(final_text)
        token_count, token_note = count_tokens_with_enc(final_text, enc, args.model, args.encoding)

    # Stats to stderr (clipboard content remains clean)
    print(f"[INFO] Mode: {'git' if used_git else 'scan'}", file=sys.stderr)
    print(f"[INFO] Files included: {len(blocks)} | skipped binary: {skipped_binary} | skipped errors: {skipped_errors}", file=sys.stderr)
    print(f"[INFO] Truncated (max-file-bytes): {truncated_files}", file=sys.stderr)
    print(f"[INFO] Total chars: {total_chars} (char_budget={max_chars_budget if max_chars_budget is not None else 'none'}, max={args.max_chars}, reserve={args.reserve_chars})", file=sys.stderr)
    if chunk_info:
        print(chunk_info, file=sys.stderr)
    if token_count is not None:
        msg = f"[INFO] Token estimate (tiktoken): {token_count}"
        if token_note:
            msg += f" | note: {token_note}"
        print(msg, file=sys.stderr)
    else:
        print(f"[WARN] Token estimate unavailable: {token_note}", file=sys.stderr)


if __name__ == "__main__":
    main()
