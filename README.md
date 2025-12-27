# ctxclipper

Clipboard-first, gitignore-first directory flattener for LLM context.

It gathers text files in a directory (respecting `.gitignore`), wraps them in an easy-to-copy format, and optionally splits output to fit model token/character limits.

## Install

```bash
pip install ctxclipper
```

Optional token counting support:

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

## Notes

- Linux clipboard support requires one of: `wl-clipboard`, `xclip`, or `xsel`.
- Non-git mode uses `pathspec` to apply `.gitignore` patterns.
- Run `ctxclipper --help` for full options.
