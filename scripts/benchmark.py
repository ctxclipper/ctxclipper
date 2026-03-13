#!/usr/bin/env python3
"""Repeatable performance harness for ctxclipper."""

import argparse
import cProfile
import io
import statistics
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from pstats import Stats
from typing import Callable, Dict, Iterable, List, Optional

from ctxclipper.core import run
from ctxclipper.discovery import discover_files

DEFAULT_IGNORE = [
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "dist",
    "build",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
]

CASE_NAMES = [
    "discover-git",
    "discover-scan",
    "cold-run",
    "warm-run",
    "split-tokens",
]


def _build_args(
    root: Path,
    *,
    max_chars: int = 500_000,
    max_tokens: int = 160_000,
) -> argparse.Namespace:
    return argparse.Namespace(
        path=str(root),
        preamble=[],
        question_parts=[],
        format="xml",
        ignore=DEFAULT_IGNORE,
        ignore_glob=[],
        include_dotfiles=False,
        model=None,
        encoding=None,
        max_tokens=max_tokens,
        reserve_tokens=16_000,
        max_chars=max_chars,
        reserve_chars=2_000,
        max_file_bytes=2_000_000,
        split=True,
        trim="largest",
        keep_per_file=8_000,
        no_copy=True,
        stdout=False,
        chunk_wrap="none",
        start_chunk=1,
        only_chunk=None,
        interactive=False,
    )


def _write_fixture(root: Path, *, file_count: int, lines_per_file: int, git_enabled: bool) -> None:
    directories = [root / "src", root / "docs", root / "tests"]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    for idx in range(file_count):
        directory = directories[idx % len(directories)]
        text = "".join(
            f"line {line} for file {idx}: the quick brown fox jumps over the lazy dog\n"
            for line in range(lines_per_file)
        )
        (directory / f"file_{idx:04d}.txt").write_text(text, encoding="utf-8")

    (root / ".gitignore").write_text("ignored/\n*.bin\n", encoding="utf-8")
    ignored_dir = root / "ignored"
    ignored_dir.mkdir(exist_ok=True)
    (ignored_dir / "skip.txt").write_text("ignored\n", encoding="utf-8")
    (root / "blob.bin").write_bytes(b"\x00binary\x00")

    if git_enabled:
        subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(
            ["git", "config", "user.email", "bench@example.com"],
            cwd=root,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            ["git", "config", "user.name", "Benchmark"],
            cwd=root,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(["git", "add", "."], cwd=root, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(
            ["git", "commit", "-m", "fixture"],
            cwd=root,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def _time_function(fn: Callable[[], None], *, repeats: int, warmups: int) -> List[float]:
    for _ in range(warmups):
        fn()

    samples: List[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return samples


def _run_quiet(args: argparse.Namespace) -> None:
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        run(args)


def _run_subprocess(root: Path, *, max_tokens: int = 160_000, max_chars: int = 500_000) -> None:
    cmd = [
        sys.executable,
        "-m",
        "ctxclipper",
        str(root),
        "--no-copy",
        "--non-interactive",
        "--max-tokens",
        str(max_tokens),
        "--max-chars",
        str(max_chars),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _profile_case(fn: Callable[[], None], *, limit: int) -> str:
    profile = cProfile.Profile()
    profile.enable()
    fn()
    profile.disable()

    output = io.StringIO()
    stats = Stats(profile, stream=output)
    stats.sort_stats("cumtime").print_stats(limit)
    return output.getvalue()


def _summarize(samples: Iterable[float]) -> str:
    values = list(samples)
    median = statistics.median(values)
    best = min(values)
    worst = max(values)
    return (
        f"median={median * 1000:.2f}ms "
        f"best={best * 1000:.2f}ms "
        f"worst={worst * 1000:.2f}ms"
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark ctxclipper performance hotspots.")
    parser.add_argument(
        "--case",
        choices=["all", *CASE_NAMES],
        default="all",
        help="Benchmark case to run",
    )
    parser.add_argument("--files", type=int, default=300, help="Synthetic file count")
    parser.add_argument("--lines-per-file", type=int, default=40, help="Lines per synthetic file")
    parser.add_argument("--repeats", type=int, default=5, help="Measured iterations per case")
    parser.add_argument("--warmups", type=int, default=1, help="Warmup iterations per case")
    parser.add_argument(
        "--profile-case",
        choices=CASE_NAMES,
        default=None,
        help="Optional case to profile with cProfile",
    )
    parser.add_argument(
        "--profile-limit",
        type=int,
        default=20,
        help="Number of cProfile rows to print",
    )
    args = parser.parse_args(argv)

    selected_cases = CASE_NAMES if args.case == "all" else [args.case]

    with tempfile.TemporaryDirectory(prefix="ctxclipper-bench-") as temp_dir:
        root = Path(temp_dir)
        git_root = root / "git-fixture"
        scan_root = root / "scan-fixture"
        git_root.mkdir()
        scan_root.mkdir()
        _write_fixture(
            git_root,
            file_count=args.files,
            lines_per_file=args.lines_per_file,
            git_enabled=True,
        )
        _write_fixture(
            scan_root,
            file_count=args.files,
            lines_per_file=args.lines_per_file,
            git_enabled=False,
        )

        warm_args = _build_args(git_root)
        split_args = _build_args(git_root, max_tokens=4_000, max_chars=500_000)

        cases: Dict[str, Callable[[], None]] = {
            "discover-git": lambda: discover_files(
                str(git_root),
                ignore_names=set(DEFAULT_IGNORE),
                ignore_globs=[],
                include_dotfiles=False,
            ),
            "discover-scan": lambda: discover_files(
                str(scan_root),
                ignore_names=set(DEFAULT_IGNORE),
                ignore_globs=[],
                include_dotfiles=False,
            ),
            "cold-run": lambda: _run_subprocess(git_root),
            "warm-run": lambda: _run_quiet(warm_args),
            "split-tokens": lambda: _run_quiet(split_args),
        }

        if args.profile_case:
            print(f"== cProfile: {args.profile_case} ==")
            print(_profile_case(cases[args.profile_case], limit=args.profile_limit).rstrip())
            print()

        for case_name in selected_cases:
            samples = _time_function(cases[case_name], repeats=args.repeats, warmups=args.warmups)
            print(f"{case_name:>13}: {_summarize(samples)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
