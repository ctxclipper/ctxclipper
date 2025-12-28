# ctxclipper Improvement Plan

A comprehensive plan to make ctxclipper a best-in-class LLM context preparation tool.

---

## Executive Summary

The current implementation is functional but has significant room for improvement in:
- Code organization and maintainability
- Test coverage (currently none)
- DRY violations and code duplication
- Type safety and documentation
- Performance optimizations
- Developer experience

---

## 1. Critical Issues

### 1.1 No Test Suite
**Current State:** Zero tests exist.
**Impact:** High risk of regressions, difficult to refactor safely.

**Fix:**
- Add `pytest` as dev dependency
- Create `tests/` directory structure:
  ```
  tests/
  ├── __init__.py
  ├── conftest.py
  ├── test_helpers.py
  ├── test_rendering.py
  ├── test_chunking.py
  ├── test_tokenization.py
  └── test_cli.py
  ```
- Target: 80%+ code coverage
- Add integration tests for CLI behavior
- Add fixture repos for testing

### 1.2 Monolithic Single File (831 lines)
**Current State:** All code in `ctxclipper.py`
**Impact:** Hard to navigate, test, and maintain.

**Fix:** Refactor into proper package structure:
```
ctxclipper/
├── __init__.py          # Public API exports
├── __main__.py          # Entry point: python -m ctxclipper
├── cli.py               # Argument parsing only (~100 lines)
├── core.py              # Main orchestration logic
├── discovery.py         # File discovery (git, walk, gitignore)
├── rendering.py         # Output formatting (XML, legacy)
├── chunking.py          # Budget management, packing, splitting
├── tokenization.py      # tiktoken wrapper with caching
├── clipboard.py         # Cross-platform clipboard operations
├── constants.py         # Default values, magic numbers
└── types.py             # Dataclasses, type aliases
```

### 1.3 `main()` Function Too Long (300+ lines)
**Current State:** Lines 513-831 are one function mixing:
- CLI parsing
- File discovery
- Content processing
- Token counting
- Chunk management
- Clipboard operations
- Output formatting

**Fix:** Extract into focused functions:
```python
def main():
    args = parse_args()
    config = Config.from_args(args)
    files = discover_files(config)
    blocks = read_files(files, config)
    output = format_output(blocks, config)
    deliver_output(output, config)
```

---

## 2. Code Quality Issues

### 2.1 DRY Violations
**Location:** `ctxclipper.py:300-367`

`pack_chunks()` and `pack_chunks_with_entries()` are 95% identical code.

**Fix:** Consolidate into single function with parameter:
```python
def pack_chunks(
    blocks: List[FileBlock],
    fmt: str,
    *,
    max_chars: Optional[int],
    max_tokens: Optional[int],
    enc,
    include_entries: bool = False
) -> Union[List[str], List[Tuple[str, List[Tuple[str, str]]]]]:
    ...
```

### 2.2 Incomplete Type Hints
**Examples:**
- `enc` parameter is untyped everywhere (`ctxclipper.py:244,300,334,479`)
- Return types missing on several functions
- `Optional` not used where `None` is valid

**Fix:** Add proper type annotations:
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tiktoken import Encoding

def fits_budget(
    rendered: str,
    *,
    max_chars: Optional[int],
    max_tokens: Optional[int],
    enc: Optional["Encoding"]
) -> bool:
```

### 2.3 Missing Docstrings
**Functions lacking documentation:**
- `normalize_glob()` - unclear behavior for edge cases
- `should_ignore_path()` - parameter meanings unclear
- `join_texts()` - purpose not obvious
- `wrap_files_root()` - when to use vs `render_block()`

**Fix:** Add Google-style docstrings to all public functions.

### 2.4 Magic Numbers/Constants
**Scattered throughout code:**
```python
# Line 23: Binary detection chunk size
chunk = f.read(4096)

# Line 524-527: Default ignores (magic set)
default_ignore = {".git", ".DS_Store", "__pycache__", ...}

# Line 549-557: Default budgets
--max-tokens 160_000
--reserve-tokens 16_000
--max-chars 507_932  # Why this specific number?
--max-file-bytes 2_000_000
```

**Fix:** Create `constants.py`:
```python
# Well-documented constants
BINARY_DETECTION_BYTES = 4096
DEFAULT_MAX_TOKENS = 160_000
DEFAULT_MAX_CHARS = 500_000  # Round number, ~128K tokens
DEFAULT_RESERVE_TOKENS = 16_000
DEFAULT_MAX_FILE_BYTES = 2 * 1024 * 1024  # 2MB

DEFAULT_IGNORE_DIRS = frozenset({
    ".git", ".DS_Store", "__pycache__",
    "node_modules", ".venv", "venv",
    ".idea", ".vscode", "dist", "build",
    "target", "coverage", ".next",
})
```

---

## 3. Bug Fixes

### 3.1 Incorrect Regex Escaping
**Location:** `ctxclipper.py:449`

```python
# Current (WRONG - double backslashes in raw string)
is_o_family = re.match(r"^o(1|3|4)(?:[\\-\\.]|$)", model_norm) is not None

# Correct
is_o_family = re.match(r"^o[134](?:[-.]|$)", model_norm) is not None
```

### 3.2 Non-existent Default Model
**Location:** `ctxclipper.py:547`

```python
# Current - "gpt-5.2" doesn't exist in tiktoken
parser.add_argument("--model", default="gpt-5.2", ...)

# Fix - use a real model or just the encoding
parser.add_argument("--model", default=None, ...)
parser.add_argument("--encoding", default="o200k_base", ...)
```

### 3.3 Bare Exception Catches
**Locations:** Lines 28, 85, 106, 117, 445, 667

```python
# Current
except Exception:
    return True  # silent failure

# Better
except OSError as e:
    logger.debug("Failed to read %s: %s", file_path, e)
    return True
```

---

## 4. Performance Optimizations

### 4.1 Token Counting Redundancy
**Problem:** Same content tokenized multiple times:
- During `fits_budget()` checks (called many times per file)
- During final output
- During chunk info generation

**Fix:** Add memoization/caching:
```python
from functools import lru_cache

class TokenCounter:
    def __init__(self, enc):
        self.enc = enc
        self._cache = {}

    def count(self, text: str) -> int:
        # Use hash for large strings
        key = hash(text) if len(text) > 1000 else text
        if key not in self._cache:
            self._cache[key] = len(self.enc.encode(text))
        return self._cache[key]
```

### 4.2 Binary Search Efficiency
**Location:** `split_big_file()` at line 244

**Problem:** Binary search calls `render_block()` + `fits_budget()` on each iteration, re-encoding the same prefixes.

**Fix:**
- Cache intermediate results
- Use character-based heuristic for initial bounds
- Batch tokenization where possible

### 4.3 Lazy File Reading
**Problem:** All files read into memory before any budget checks.

**Fix:** Stream files and check budgets incrementally:
```python
def iter_file_blocks(files: List[Path], config: Config) -> Iterator[FileBlock]:
    for path in files:
        if should_skip(path):
            continue
        yield read_file_block(path, config)
```

---

## 5. Developer Experience

### 5.1 Replace argparse with click/typer
**Rationale:**
- Better help formatting
- Automatic shell completion
- Cleaner code for complex CLIs

```python
import typer
app = typer.Typer()

@app.command()
def main(
    path: Path = typer.Argument(".", help="Directory to process"),
    format: Format = typer.Option("xml", help="Output format"),
    max_tokens: int = typer.Option(160_000, help="Token budget"),
    ...
):
    ...
```

### 5.2 Add Logging
**Replace print statements with logging:**
```python
import logging
logger = logging.getLogger("ctxclipper")

# Replace
print(f"[WARN] ...", file=sys.stderr)

# With
logger.warning("...")

# Add --verbose/-v flag for debug output
```

### 5.3 Configuration File Support
**Add support for `.ctxclipperrc` or `pyproject.toml` config:**
```toml
# pyproject.toml
[tool.ctxclipper]
format = "xml"
max-tokens = 128000
ignore = [".git", "node_modules", "__pycache__"]
ignore-glob = ["*.lock", "*.min.js"]
```

### 5.4 Progress Indicators
**For large repositories:**
```python
from rich.progress import Progress

with Progress() as progress:
    task = progress.add_task("Scanning files...", total=len(files))
    for file in files:
        process(file)
        progress.advance(task)
```

---

## 6. New Features

### 6.1 Dry-Run Mode
```bash
ctxclipper . --dry-run
# Shows what would be copied without actually copying
```

### 6.2 File Type Filters
```bash
ctxclipper . --include-type py ts js  # Only these extensions
ctxclipper . --exclude-type md txt    # Exclude these
```

### 6.3 Output to File
```bash
ctxclipper . --output context.xml
```

### 6.4 Template Support
```bash
ctxclipper . --template summarize  # Uses built-in prompts
ctxclipper . --template ./my-template.txt
```

### 6.5 Watch Mode
```bash
ctxclipper . --watch  # Re-copy on file changes
```

---

## 7. Documentation

### 7.1 Missing Documentation
- API documentation for programmatic use
- Architecture overview
- Contributing guide
- Changelog

### 7.2 Improved README
- Add badges (PyPI version, Python versions, tests)
- Comparison with alternatives
- More examples
- Troubleshooting section

---

## 8. Packaging & CI

### 8.1 Add Development Dependencies
```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "mypy>=1.0",
    "ruff>=0.1",
    "pre-commit>=3.0",
]
```

### 8.2 Add GitHub Actions
```yaml
# .github/workflows/ci.yml
- Run tests on Python 3.8-3.12
- Type checking with mypy
- Linting with ruff
- Coverage reporting
- Automated PyPI release on tags
```

### 8.3 Add Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    hooks:
      - id: mypy
```

---

## 9. Implementation Priority

### Phase 1: Foundation (Critical)
1. Add basic test suite
2. Fix bugs (regex, model default)
3. Extract constants
4. Add proper logging

### Phase 2: Refactoring
1. Split into package structure
2. Break up `main()` function
3. Consolidate DRY violations
4. Complete type hints

### Phase 3: Polish
1. Add click/typer CLI
2. Configuration file support
3. Progress indicators
4. Improved error messages

### Phase 4: Features
1. Dry-run mode
2. File type filters
3. Watch mode
4. Template support

---

## 10. Metrics for Success

| Metric | Current | Target |
|--------|---------|--------|
| Test Coverage | 0% | 80%+ |
| Type Coverage | ~40% | 95%+ |
| Cyclomatic Complexity (main) | ~50 | <10 |
| Lines per function (max) | 300+ | <50 |
| Documentation coverage | ~20% | 100% |

---

## Appendix: Quick Wins

These can be done immediately with minimal risk:

1. **Fix regex bug** (line 449) - 1 line change
2. **Fix default model** (line 547) - 1 line change
3. **Add `__all__`** - Explicit public API
4. **Add `py.typed` marker** - Enable type checking for users
5. **Add basic pytest setup** - Foundation for testing
6. **Extract constants** - Improves readability immediately

---

*This plan prioritizes stability (tests, bug fixes) before adding features. Each phase builds on the previous, allowing incremental improvement without breaking existing functionality.*
