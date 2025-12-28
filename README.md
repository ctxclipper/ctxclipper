# ctxclipper

[![PyPI version](https://badge.fury.io/py/ctxclipper.svg)](https://badge.fury.io/py/ctxclipper)
[![Python versions](https://img.shields.io/pypi/pyversions/ctxclipper.svg)](https://pypi.org/project/ctxclipper/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Clipboard-first, gitignore-first directory flattener for LLM context.

It gathers text files in a directory (respecting `.gitignore`), wraps them in an easy-to-copy format, and optionally splits output to fit model token/character limits.

## Features

- **Clipboard-first**: Automatically copies formatted output to clipboard
- **Git-aware**: Respects `.gitignore` patterns automatically in git repositories
- **Token-aware**: Manages token/character budgets for LLM context windows
- **Multiple formats**: XML (default) or legacy text format
- **Smart chunking**: Splits large codebases into multiple chunks that fit your model's context
- **Cross-platform**: Works on macOS, Windows, and Linux

## Install

```bash
pip install ctxclipper
```

Optional token counting support (recommended):

```bash
pip install "ctxclipper[tokens]"
```

## Usage

Copy a repo into your clipboard (default behavior) and print to stdout:

```bash
ctxclipper . --stdout
```

Use XML output and adjust budgets:

```bash
ctxclipper . --format xml --max-tokens 160000 --reserve-tokens 16000
```

Include a preamble file and a question at the end:

```bash
ctxclipper . --preamble preamble.txt --question-text "Summarize the codebase."
```

Non-interactive chunking:

```bash
ctxclipper . --split --non-interactive --stdout
```

Skip clipboard copy (headless environments):

```bash
ctxclipper . --no-copy --stdout
```

Ignore specific patterns:

```bash
ctxclipper . --ignore-glob "*.lock" "*.min.js" --ignore node_modules dist
```

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--format` | Output format (`xml` or `legacy`) | `xml` |
| `--max-tokens` | Max tokens per chunk | 160000 |
| `--reserve-tokens` | Tokens reserved for instructions | 16000 |
| `--max-chars` | Max characters (0 to disable) | 500000 |
| `--split` / `--no-split` | Enable/disable chunk splitting | enabled |
| `--interactive` / `--non-interactive` | Prompt between chunks | interactive |
| `--ignore` | Names to ignore | common dirs |
| `--ignore-glob` | Glob patterns to ignore | none |
| `--include-dotfiles` | Include hidden files | false |
| `--preamble` | File(s) to prepend | none |
| `--question-text` | Text to append | none |
| `--question-file` | File(s) to append | none |
| `--no-copy` | Skip clipboard | false |
| `--stdout` | Print to stdout | false |

Run `ctxclipper --help` for full options.

## Development

Install development dependencies:

```bash
pip install -e ".[dev,tokens]"
```

Run tests:

```bash
pytest
```

Run linting and type checking:

```bash
ruff check ctxclipper tests
mypy ctxclipper
```

## Notes

- Linux clipboard support requires one of: `wl-clipboard`, `xclip`, or `xsel`
- Non-git mode uses `pathspec` to apply `.gitignore` patterns
- Token counting requires `tiktoken` (install with `ctxclipper[tokens]`)

## License

MIT License - see [LICENSE](LICENSE) for details.
