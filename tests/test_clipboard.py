"""Tests for clipboard module."""

import platform
from unittest.mock import MagicMock, patch

import pytest

from ctxclipper.clipboard import copy_to_clipboard


class TestCopyToClipboard:
    """Tests for copy_to_clipboard function."""

    @patch("ctxclipper.clipboard.subprocess.Popen")
    def test_successful_copy_darwin(self, mock_popen: MagicMock) -> None:
        """Successful copy on macOS should return True."""
        with patch("ctxclipper.clipboard.platform.system", return_value="Darwin"):
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.communicate = MagicMock()
            mock_popen.return_value = mock_process

            result = copy_to_clipboard("test text")

            assert result is True
            mock_popen.assert_called_once()
            assert mock_popen.call_args[0][0] == ["pbcopy"]

    @patch("ctxclipper.clipboard.subprocess.Popen")
    def test_successful_copy_windows(self, mock_popen: MagicMock) -> None:
        """Successful copy on Windows should return True."""
        with patch("ctxclipper.clipboard.platform.system", return_value="Windows"):
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.communicate = MagicMock()
            mock_popen.return_value = mock_process

            result = copy_to_clipboard("test text")

            assert result is True
            assert mock_popen.call_args[0][0] == ["clip"]

    @patch("ctxclipper.clipboard.subprocess.Popen")
    def test_successful_copy_linux(self, mock_popen: MagicMock) -> None:
        """Successful copy on Linux should return True."""
        with patch("ctxclipper.clipboard.platform.system", return_value="Linux"):
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.communicate = MagicMock()
            mock_popen.return_value = mock_process

            result = copy_to_clipboard("test text")

            assert result is True
            assert mock_popen.call_args[0][0] == ["wl-copy"]

    @patch("ctxclipper.clipboard.subprocess.Popen")
    def test_fallback_on_failure(self, mock_popen: MagicMock) -> None:
        """Should try fallback commands on failure."""
        with patch("ctxclipper.clipboard.platform.system", return_value="Linux"):
            # First command fails, second succeeds
            mock_process_fail = MagicMock()
            mock_process_fail.returncode = 1
            mock_process_fail.communicate = MagicMock()

            mock_process_success = MagicMock()
            mock_process_success.returncode = 0
            mock_process_success.communicate = MagicMock()

            mock_popen.side_effect = [mock_process_fail, mock_process_success]

            result = copy_to_clipboard("test text")

            assert result is True
            assert mock_popen.call_count == 2

    @patch("ctxclipper.clipboard.subprocess.Popen")
    def test_all_commands_fail(self, mock_popen: MagicMock) -> None:
        """Should return False when all commands fail."""
        with patch("ctxclipper.clipboard.platform.system", return_value="Linux"):
            mock_popen.side_effect = FileNotFoundError()

            result = copy_to_clipboard("test text")

            assert result is False

    @patch("ctxclipper.clipboard.subprocess.Popen")
    def test_text_encoded_as_utf8(self, mock_popen: MagicMock) -> None:
        """Text should be encoded as UTF-8."""
        with patch("ctxclipper.clipboard.platform.system", return_value="Darwin"):
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.communicate = MagicMock()
            mock_popen.return_value = mock_process

            copy_to_clipboard("Hello 世界")

            # Check that communicate was called with UTF-8 encoded bytes
            call_args = mock_process.communicate.call_args
            assert call_args[0][0] == "Hello 世界".encode("utf-8")
