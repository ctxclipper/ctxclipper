"""Pytest fixtures for ctxclipper tests."""

import tempfile
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_repo(temp_dir: Path) -> Path:
    """Create a sample repository structure for testing."""
    # Create directory structure
    (temp_dir / "src").mkdir()
    (temp_dir / "src" / "utils").mkdir()
    (temp_dir / "tests").mkdir()
    (temp_dir / ".git").mkdir()  # Simulate git directory

    # Create sample files
    (temp_dir / "README.md").write_text("# Sample Project\n\nThis is a test.")
    (temp_dir / "src" / "main.py").write_text('def main():\n    print("Hello")\n')
    (temp_dir / "src" / "utils" / "helpers.py").write_text("def helper():\n    return 42\n")
    (temp_dir / "tests" / "test_main.py").write_text("def test_main():\n    assert True\n")

    # Create a .gitignore
    (temp_dir / ".gitignore").write_text("__pycache__/\n*.pyc\n.env\n")

    return temp_dir


@pytest.fixture
def sample_repo_with_binary(sample_repo: Path) -> Path:
    """Create a sample repo with a binary file."""
    # Add a binary file (PNG header)
    binary_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    (sample_repo / "image.png").write_bytes(binary_content)
    return sample_repo


@pytest.fixture
def git_repo(temp_dir: Path) -> Path:
    """Create an actual git repository for testing."""
    import subprocess

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=temp_dir, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=temp_dir,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=temp_dir,
        capture_output=True,
    )

    # Create files
    (temp_dir / "file1.py").write_text("# File 1\n")
    (temp_dir / "file2.py").write_text("# File 2\n")
    (temp_dir / ".gitignore").write_text("ignored.txt\n")
    (temp_dir / "ignored.txt").write_text("This should be ignored\n")

    # Add and commit
    subprocess.run(["git", "add", "."], cwd=temp_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=temp_dir,
        capture_output=True,
    )

    return temp_dir
