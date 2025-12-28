"""Cross-platform clipboard operations."""

import logging
import os
import platform
import subprocess
from typing import List

__all__ = ["copy_to_clipboard"]

logger = logging.getLogger(__name__)


def copy_to_clipboard(text: str) -> bool:
    """
    Copy text to system clipboard.

    Supports:
    - macOS: pbcopy
    - Windows: clip (fallback to PowerShell Set-Clipboard)
    - Linux/BSD: wl-copy, xclip, or xsel

    Args:
        text: The text to copy to clipboard.

    Returns:
        True if copy succeeded, False otherwise.
    """
    system = platform.system()
    commands: List[List[str]] = []

    if system == "Darwin":
        commands = [["pbcopy"]]
    elif system == "Windows":
        commands = [
            ["clip"],
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Set-Clipboard -Value ([Console]::In.ReadToEnd())",
            ],
        ]
    else:
        # Linux, BSD, etc.
        commands = [
            ["wl-copy"],
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
        ]

    env = os.environ.copy()
    env["LANG"] = "en_US.UTF-8"

    for cmd in commands:
        try:
            proc = subprocess.Popen(cmd, env=env, stdin=subprocess.PIPE)
            proc.communicate(text.encode("utf-8"))
            if proc.returncode == 0:
                return True
        except FileNotFoundError:
            continue
        except Exception as e:
            logger.warning("Clipboard command %s failed: %s", " ".join(cmd), e)

    # Provide helpful error message
    if system == "Darwin":
        hint = "pbcopy should exist on macOS; check PATH / permissions."
    elif system == "Windows":
        hint = "Ensure clip/powershell is available in this shell."
    else:
        hint = "Install wl-clipboard, xclip, or xsel."

    logger.error("Clipboard copy unavailable. %s", hint)
    return False
