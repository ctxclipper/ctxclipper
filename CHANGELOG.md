# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-03-13

### Added
- Clearer CLI help output with grouped arguments, readable metavars, and the `ctxclipper` program name in usage text.
- Actionable no-split budget errors that explain the rendered size and suggest remediation.
- Exact token-budget chunk packing that accounts for wrapper overhead more accurately.
- A benchmark script for comparing discovery and tokenization behavior.

### Changed
- Skip symlinked files that resolve outside the requested directory tree.
- Enforce `--no-split` budgets against the final rendered payload and raise an error when the output still cannot fit after trimming.
- Use the non-deprecated `gitignore` pathspec matcher for fallback `.gitignore` support.
- Prefer the direct git discovery path without a separate worktree probe on the success path.
- Cache tokenizer resolution results to avoid repeated encoder setup work.

## [0.1.0] - 2026-02-22

### Added
- Initial public release of `ctxclipper`.
- Clipboard-first CLI for flattening repositories into LLM-ready context.
- Git-aware file discovery with fallback `.gitignore` support.
- XML and legacy output formats with preamble/question sections.
- Chunk splitting and token/character budget controls.
