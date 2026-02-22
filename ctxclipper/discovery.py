"""File discovery: git integration and directory scanning."""

import fnmatch
import logging
import os
import subprocess
from typing import Any, List, Optional, Set, Tuple

from .constants import BINARY_DETECTION_BYTES

__all__ = [
    "discover_files",
    "git_list_files",
    "in_git_worktree",
    "is_binary",
    "load_gitignore_pathspec",
    "normalize_glob",
    "should_ignore_path",
]

logger = logging.getLogger(__name__)


def is_binary(file_path: str) -> bool:
    """
    Detect if a file is binary using NUL byte heuristic.

    Args:
        file_path: Path to the file to check.

    Returns:
        True if file appears to be binary, False otherwise.
        Returns True for unreadable files (fail-safe).
    """
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(BINARY_DETECTION_BYTES)
        return b"\0" in chunk
    except OSError as e:
        logger.debug("Cannot read file %s: %s", file_path, e)
        return True


def in_git_worktree(path: str) -> bool:
    """Check if path is inside a git worktree."""
    try:
        subprocess.check_call(
            ["git", "-C", path, "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def git_list_files(base_path: str) -> List[str]:
    """
    Get list of files tracked by git (including untracked but not ignored).

    Args:
        base_path: Root directory of the git repository.

    Returns:
        List of relative file paths.

    Raises:
        subprocess.CalledProcessError: If git command fails.
    """
    out = subprocess.check_output(
        ["git", "-C", base_path, "ls-files", "-z", "-c", "-o", "--exclude-standard"],
        stderr=subprocess.DEVNULL,
    )
    return [p.decode("utf-8", "replace") for p in out.split(b"\0") if p]


def load_gitignore_pathspec(base_path: str) -> Tuple[Optional[Any], Optional[str]]:
    """
    Load .gitignore patterns for non-git mode using pathspec library.

    Args:
        base_path: Directory containing .gitignore.

    Returns:
        Tuple of (PathSpec or None, error_message or None).
    """
    try:
        import pathspec
    except ImportError:
        return None, "pathspec not installed"

    patterns: List[str] = []
    gitignore_path = os.path.join(base_path, ".gitignore")

    if os.path.exists(gitignore_path):
        try:
            with open(gitignore_path, encoding="utf-8", errors="replace") as f:
                patterns.extend(line.rstrip("\n") for line in f)
        except OSError as e:
            logger.warning("Failed to read .gitignore: %s", e)

    spec = pathspec.PathSpec.from_lines("gitignore", patterns)
    return spec, None


def normalize_glob(pattern: str) -> Tuple[str, bool]:
    """
    Normalize a glob pattern to POSIX-style separators.

    Args:
        pattern: The glob pattern to normalize.

    Returns:
        Tuple of (normalized_pattern, anchored) where anchored means
        "match from repo root". Leading "/" or "./" anchors the pattern.
    """
    pattern = pattern.replace("\\", "/")
    anchored = False

    if pattern.startswith("./"):
        pattern = pattern[2:]
        anchored = True
    if pattern.startswith("/"):
        anchored = True
        pattern = pattern.lstrip("/")

    return pattern, anchored


def should_ignore_path(
    rel_path: str,
    ignore_names: Set[str],
    ignore_globs: List[str],
    include_dotfiles: bool,
) -> bool:
    """
    Determine if a path should be ignored based on configured rules.

    Args:
        rel_path: Relative path to check.
        ignore_names: Set of directory/file names to ignore.
        ignore_globs: List of glob patterns to ignore.
        include_dotfiles: If False, ignore paths with dot-prefixed components.

    Returns:
        True if path should be ignored.
    """
    parts = rel_path.split(os.sep)

    # Check dotfiles
    if not include_dotfiles and any(p.startswith(".") for p in parts):
        return True

    # Check ignore names
    if any(p in ignore_names for p in parts):
        return True

    # Check glob patterns
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

            # Unanchored: match against full path, basename, or as suffix
            if fnmatch.fnmatch(rel_posix, pat_norm):
                return True
            if fnmatch.fnmatch(base, pat_norm):
                return True
            if "/" in pat_norm and fnmatch.fnmatch(rel_posix, f"*/{pat_norm}"):
                return True

    return False


def discover_files(
    base_path: str,
    ignore_names: Set[str],
    ignore_globs: List[str],
    include_dotfiles: bool,
) -> Tuple[List[str], bool]:
    """
    Discover all relevant files in a directory.

    Uses git if available, falls back to directory scanning with .gitignore support.

    Args:
        base_path: Directory to scan.
        ignore_names: Names to ignore.
        ignore_globs: Glob patterns to ignore.
        include_dotfiles: Whether to include dotfiles.

    Returns:
        Tuple of (list of relative paths, used_git flag).
    """
    rel_paths: List[str] = []
    used_git = False

    if in_git_worktree(base_path):
        try:
            rel_paths = git_list_files(base_path)
            used_git = True
        except subprocess.CalledProcessError as e:
            logger.warning("git listing failed, falling back to scan: %s", e)

    if not used_git:
        gitignore_spec, gi_err = load_gitignore_pathspec(base_path)
        if gi_err:
            logger.warning(
                "Non-git mode: %s. .gitignore will NOT be applied without pathspec.",
                gi_err,
            )

        for root, dirs, files in os.walk(base_path):
            # Prune directories
            pruned = []
            for d in dirs:
                rel_d = os.path.relpath(os.path.join(root, d), base_path)
                if should_ignore_path(rel_d, ignore_names, ignore_globs, include_dotfiles):
                    continue
                if gitignore_spec and gitignore_spec.match_file(rel_d):
                    continue
                pruned.append(d)
            dirs[:] = pruned

            # Collect files
            for f in files:
                rel_f = os.path.relpath(os.path.join(root, f), base_path)
                if should_ignore_path(rel_f, ignore_names, ignore_globs, include_dotfiles):
                    continue
                if gitignore_spec and gitignore_spec.match_file(rel_f):
                    continue
                rel_paths.append(rel_f)

    # Apply ignores in git mode too (user-specified ignores)
    filtered: List[str] = []
    for rel in rel_paths:
        rel_norm = rel.replace("/", os.sep)  # git returns forward slashes
        if should_ignore_path(rel_norm, ignore_names, ignore_globs, include_dotfiles):
            continue
        filtered.append(rel_norm)

    filtered.sort()
    return filtered, used_git
