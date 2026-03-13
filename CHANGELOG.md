# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Skip symlinked files that resolve outside the requested directory tree.
- Enforce `--no-split` budgets against the final rendered payload and raise an error when the output still cannot fit after trimming.
- Use the non-deprecated `gitwildmatch` pathspec matcher for fallback `.gitignore` support.

## [0.1.0] - 2026-02-22

### Added
- Initial public release of `ctxclipper`.
- Clipboard-first CLI for flattening repositories into LLM-ready context.
- Git-aware file discovery with fallback `.gitignore` support.
- XML and legacy output formats with preamble/question sections.
- Chunk splitting and token/character budget controls.
