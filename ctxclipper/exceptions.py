"""Custom exceptions for ctxclipper."""

__all__ = [
    "ClipboardError",
    "CtxclipperError",
    "DirectoryError",
    "FileReadError",
]


class CtxclipperError(Exception):
    """Base exception for all ctxclipper errors."""

    pass


class FileReadError(CtxclipperError):
    """Raised when a required file cannot be read."""

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"Failed to read file: {path} ({reason})")


class ClipboardError(CtxclipperError):
    """Raised when clipboard operations fail."""

    def __init__(self, message: str = "Clipboard copy failed") -> None:
        super().__init__(message)


class DirectoryError(CtxclipperError):
    """Raised when the target directory is invalid."""

    def __init__(self, path: str, reason: str = "Not a directory") -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"{reason}: {path}")
