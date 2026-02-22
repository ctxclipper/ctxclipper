# ctxclipper

[![PyPI version](https://badge.fury.io/py/ctxclipper.svg)](https://badge.fury.io/py/ctxclipper)
[![CI](https://github.com/ctxclipper/ctxclipper/actions/workflows/ci.yml/badge.svg)](https://github.com/ctxclipper/ctxclipper/actions/workflows/ci.yml)
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

## Quickstart

Copy a repo into your clipboard (default) and print to stdout:

```bash
ctxclipper . --stdout
```

Skip clipboard copy (useful in CI/headless environments):

```bash
ctxclipper . --no-copy --stdout
```

## Usage Examples

Use XML output and tune budgets:

```bash
ctxclipper . --format xml --max-tokens 160000 --reserve-tokens 16000
```

Include a preamble and append a prompt:

```bash
ctxclipper . --preamble preamble.txt --question-text "Summarize the codebase."
```

Non-interactive chunking:

```bash
ctxclipper . --split --non-interactive --stdout
```

Ignore specific patterns:

```bash
ctxclipper . --ignore-glob "*.lock" "*.min.js" --ignore node_modules dist
```

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--format` | Output format (`xml` or `legacy`) | `xml` |
| `--model` | Model name for tokenizer lookup | none |
| `--encoding` | Explicit tokenizer encoding | `o200k_base` |
| `--max-tokens` | Max tokens per chunk | 160000 |
| `--reserve-tokens` | Tokens reserved for instructions | 16000 |
| `--max-chars` | Max characters (0 to disable) | 500000 |
| `--reserve-chars` | Characters reserved for instructions | 2000 |
| `--split` / `--no-split` | Enable/disable chunk splitting | enabled |
| `--interactive` / `--non-interactive` | Prompt between chunks | interactive |
| `--trim` | Over-budget strategy in no-split mode | `largest` |
| `--keep-per-file` | Characters to keep per file when trimming | 8000 |
| `--max-file-bytes` | Hard read cap per file | 2000000 |
| `--ignore` | Names to ignore | common dirs |
| `--ignore-glob` | Glob patterns to ignore | none |
| `--include-dotfiles` | Include hidden files | false |
| `--preamble` | File(s) to prepend | none |
| `--question-text` | Text to append | none |
| `--question-file` | File(s) to append | none |
| `--chunk-wrap` | Add per-chunk wrapper (`none`, `xml`, `legacy`) | `none` |
| `--start-chunk` | Start from this 1-based chunk index | `1` |
| `--only-chunk` | Copy only this 1-based chunk index | none |
| `--no-copy` | Skip clipboard | false |
| `--stdout` | Print to stdout | false |

Run `ctxclipper --help` for full options.

## Clipboard Requirements

- macOS: `pbcopy` (built in)
- Windows: `clip` or PowerShell `Set-Clipboard`
- Linux: one of `wl-clipboard`, `xclip`, or `xsel`

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

Build and validate distribution artifacts:

```bash
python -m build
twine check dist/*
```

Contribution and release notes:

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CHANGELOG.md](CHANGELOG.md)
- [SECURITY.md](SECURITY.md)

## License

MIT License - see [LICENSE](LICENSE) for details.
