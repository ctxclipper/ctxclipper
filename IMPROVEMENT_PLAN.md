# ctxclipper Improvement Plan - Phase 2

A comprehensive plan to elevate ctxclipper to best-in-class quality after the initial refactoring.

---

## Executive Summary

The initial refactoring established a solid foundation. This phase focuses on:
- **Test coverage**: Critical gap in core.py (451 lines, 0% tested)
- **Type safety**: 10 mypy errors blocking strict typing
- **Error handling**: Replace silent failures with proper logging
- **Performance**: Fix O(n²) algorithms in chunking and discovery
- **Library code hygiene**: Remove sys.exit() calls from library functions

---

## 1. Critical Issues

### 1.1 Zero Test Coverage for core.py (451 lines)
**Location:** `ctxclipper/core.py`
**Impact:** Highest-risk module completely untested.

**Functions needing tests:**
- `read_file_blocks()` - File reading with truncation
- `adjust_budget()` - Budget calculation
- `run()` - Main orchestration (154 lines)
- `_handle_split_mode()` - Chunked output
- `_handle_single_mode()` - Single output

**Fix:** Create `tests/test_core.py`:
```python
class TestReadFileBlocks:
    def test_reads_text_files(self, sample_repo): ...
    def test_skips_binary_files(self, sample_repo_with_binary): ...
    def test_truncates_large_files(self, temp_dir): ...
    def test_handles_unreadable_files(self, temp_dir): ...

class TestRun:
    def test_basic_directory(self, sample_repo, capsys): ...
    def test_no_copy_mode(self, sample_repo): ...
    def test_stdout_mode(self, sample_repo, capsys): ...
    def test_split_mode(self, large_repo): ...
    def test_nonexistent_directory(self): ...
```

### 1.2 sys.exit() in Library Code
**Locations:**
- `core.py:350, 438` - `sys.exit(2)` on clipboard failure
- `rendering.py:136` - `sys.exit(1)` on file read failure

**Impact:** Library cannot be used programmatically; unmockable in tests.

**Fix:** Replace with exceptions:
```python
# Before (rendering.py:136)
sys.exit(1)

# After
class FileReadError(Exception):
    """Raised when a required file cannot be read."""
    pass

raise FileReadError(f"Failed to read file: {path} ({e})")
```

### 1.3 Type Hint Errors (10 mypy errors)
**Locations:**
- `core.py:108, 265, 401` - Missing `args: argparse.Namespace`
- `cli.py:226` - Missing `args: Optional[List[str]]`
- `discovery.py:100` - Return type `Tuple[Optional[object], ...]` should be typed
- `core.py:277` - Union return type assignment

**Fix:** Add missing type annotations:
```python
# core.py
def run(args: argparse.Namespace) -> int:
    ...

def _handle_split_mode(
    args: argparse.Namespace,
    blocks: List[FileBlock],
    ...
) -> Tuple[int, Optional[int], Optional[str], str]:
    ...

# cli.py
def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    ...
```

---

## 2. High Priority Issues

### 2.1 Silent Error Handling
**Location:** `core.py:75`

```python
# Current - silent failure
except Exception:
    skipped_errors += 1

# Fix - log which file failed
except OSError as e:
    logger.warning("Failed to read %s: %s", abs_path, e)
    skipped_errors += 1
```

### 2.2 Bare Exception Handlers
**Locations:** 8 instances across codebase

| File | Line | Current | Fix |
|------|------|---------|-----|
| core.py | 75 | `except Exception` | `except OSError` |
| clipboard.py | 63 | `except Exception as e` | Keep (fallback behavior) |
| discovery.py | 211 | `except Exception as e` | `except subprocess.CalledProcessError` |
| rendering.py | 134 | `except Exception as e` | `except (OSError, UnicodeDecodeError) as e` |
| tokenization.py | 72 | `except ImportError` | Already specific ✓ |
| tokenization.py | 86 | `except Exception as e` | `except tiktoken.TokenizerError as e` |

### 2.3 O(n²) Algorithm in trim_largest_first
**Location:** `chunking.py:237`

```python
# Current - O(n²)
while total > max_chars and blocks:
    i = max(range(len(blocks)), key=lambda k: len(blocks[k].raw))
    ...

# Fix - O(n log n) with heapq
import heapq

def trim_largest_first(...):
    heap = [(-len(b.raw), i, b) for i, b in enumerate(blocks)]
    heapq.heapify(heap)

    while total > max_chars and heap:
        neg_len, idx, block = heapq.heappop(heap)
        ...
```

### 2.4 O(n²) Linear Search in split_big_file
**Location:** `chunking.py:66-73`

```python
# Current - character-by-character O(n²)
for cut in range(len(tiny_rendered), 0, -1):
    if fits_budget(...):
        return [tiny_rendered[:cut]]

# Fix - binary search O(n log n)
lo, hi = 0, len(tiny_rendered)
while lo < hi:
    mid = (lo + hi + 1) // 2
    if fits_budget(tiny_rendered[:mid], ...):
        lo = mid
    else:
        hi = mid - 1
return [tiny_rendered[:lo]] if lo > 0 else [tiny_rendered]
```

### 2.5 Missing Test Coverage
**Priority functions to test:**

| Module | Function | Lines | Complexity |
|--------|----------|-------|------------|
| discovery.py | `discover_files()` | 50 | High |
| discovery.py | `git_list_files()` | 15 | Medium |
| chunking.py | `split_big_file()` | 60 | High |
| tokenization.py | `count_tokens()` | 25 | Medium |
| chunking.py | `print_chunk_file_tokens()` | 20 | Low |

---

## 3. Medium Priority Issues

### 3.1 DRY Violation: Glob Pattern Matching
**Location:** `discovery.py:163-179`

```python
# Current - repeated 3 times
if fnmatch.fnmatch(rel_posix, pat_norm):
    return True
if fnmatch.fnmatch(base, pat_norm):
    return True
if "/" in pat_norm and fnmatch.fnmatch(rel_posix, f"*/{pat_norm}"):
    return True

# Fix - extract helper
def _matches_glob(rel_posix: str, base: str, pat_norm: str) -> bool:
    """Check if path matches glob pattern using multiple strategies."""
    if fnmatch.fnmatch(rel_posix, pat_norm):
        return True
    if fnmatch.fnmatch(base, pat_norm):
        return True
    if "/" in pat_norm and fnmatch.fnmatch(rel_posix, f"*/{pat_norm}"):
        return True
    return False
```

### 3.2 Complexity in run() Function
**Location:** `core.py` - 154-line function with 48 branches

**Fix:** Extract logical sections:
```python
def run(args: argparse.Namespace) -> int:
    config = _validate_and_prepare(args)
    files = _discover_and_read_files(config)
    tokenizer = _initialize_tokenizer(config)
    output = _generate_output(files, tokenizer, config)
    return _deliver_output(output, config)
```

### 3.3 Use subprocess.run() Instead of Popen
**Location:** `clipboard.py:57-60`

```python
# Current
p = subprocess.Popen(cmd, env=env, stdin=subprocess.PIPE)
p.communicate(text.encode("utf-8"))

# Better
result = subprocess.run(
    cmd,
    input=text.encode("utf-8"),
    env=env,
    capture_output=True,
)
return result.returncode == 0
```

### 3.4 Add Caching to Tokenization
**Location:** `tokenization.py`

```python
from functools import lru_cache

@lru_cache(maxsize=256)
def _cached_token_count(text: str, encoding_name: str) -> int:
    """Cache token counts for repeated text."""
    enc = tiktoken.get_encoding(encoding_name)
    return len(enc.encode(text))
```

### 3.5 Missing Edge Case Tests

| Edge Case | Current Status | Priority |
|-----------|---------------|----------|
| Empty directory | Untested | Medium |
| All binary files | Untested | Medium |
| Unicode in paths | Untested | Medium |
| Very long paths | Untested | Low |
| Symlinks | Untested | Low |
| Exact budget fit | Untested | Medium |
| Multiple preambles | Untested | Medium |

---

## 4. Low Priority Improvements

### 4.1 Use pathlib.Path Consistently
**Current:** Mix of `os.path` and manual string operations

```python
# Before
abs_path = os.path.join(base_path, rel)
if not os.path.isfile(abs_path):
    continue

# After
from pathlib import Path
abs_path = Path(base_path) / rel
if not abs_path.is_file():
    continue
```

### 4.2 Add Enum Types for String Literals
**Current:** String literals throughout

```python
# Add to types.py
from enum import Enum

class OutputFormat(str, Enum):
    XML = "xml"
    LEGACY = "legacy"

class TokenizerSource(str, Enum):
    MODEL = "model"
    OVERRIDE = "override"
    ENCODING = "encoding"
    NONE = "none"
```

### 4.3 Consider click for CLI
**Current:** 229 lines of argparse

```python
# With click (~100 lines)
import click

@click.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--format", type=click.Choice(["xml", "legacy"]), default="xml")
@click.option("--max-tokens", type=int, default=160_000)
def main(path: str, format: str, max_tokens: int):
    ...
```

### 4.4 Add Protocol for PathSpec Type
**Location:** `discovery.py:100`

```python
from typing import Protocol

class GitIgnoreSpec(Protocol):
    def match_file(self, path: str) -> bool: ...

def load_gitignore_pathspec(base_path: str) -> Tuple[Optional[GitIgnoreSpec], Optional[str]]:
    ...
```

### 4.5 Configure Package-Level Logging
**Location:** `ctxclipper/__init__.py`

```python
import logging

# Null handler for library use
logging.getLogger(__name__).addHandler(logging.NullHandler())

def configure_logging(level: str = "INFO") -> None:
    """Configure logging for CLI use."""
    logging.basicConfig(
        level=getattr(logging, level),
        format="[%(levelname)s] %(message)s",
    )
```

---

## 5. Implementation Priority

### Phase 2A: Critical (This Sprint)
1. Add `tests/test_core.py` with comprehensive coverage
2. Replace `sys.exit()` with exceptions, create custom exception classes
3. Fix all 10 mypy type errors
4. Add error logging to silent failures

### Phase 2B: High (Next Sprint)
1. Fix O(n²) algorithms in chunking.py
2. Replace bare exception handlers with specific types
3. Add tests for `discover_files()`, `split_big_file()`, `count_tokens()`
4. Add edge case tests

### Phase 2C: Medium (Backlog)
1. Refactor `run()` function complexity
2. Extract glob matching helper
3. Use `subprocess.run()` instead of `Popen`
4. Add tokenization caching
5. Add more edge case tests

### Phase 2D: Low (Future)
1. Migrate to pathlib.Path
2. Add Enum types
3. Consider click migration
4. Add Protocol types
5. Package-level logging configuration

---

## 6. Metrics for Success

| Metric | Current | Target |
|--------|---------|--------|
| Test Coverage (core.py) | 0% | 80%+ |
| Test Coverage (overall) | ~51% | 85%+ |
| mypy Errors | 10 | 0 |
| Bare Exception Handlers | 8 | 2 (acceptable) |
| sys.exit() in Library | 3 | 0 |
| O(n²) Algorithms | 2 | 0 |
| Max Function Length | 154 lines | <50 lines |

---

## 7. New Files to Create

```
ctxclipper/
├── exceptions.py      # Custom exception classes
└── ...

tests/
├── test_core.py       # NEW: 200+ lines of core tests
├── test_integration.py # NEW: End-to-end tests
└── ...
```

---

*This plan builds on the solid foundation from Phase 1. Each item is independent and can be tackled incrementally without breaking existing functionality.*
