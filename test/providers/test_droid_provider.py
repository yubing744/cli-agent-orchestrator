"""Unit tests for Droid provider."""

from pathlib import Path
from unittest.mock import patch

import pytest

from cli_agent_orchestrator.models.terminal import TerminalStatus
from cli_agent_orchestrator.providers.droid import DroidProvider

# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> str:
    """Load a fixture file and return its contents."""
    with open(FIXTURES_DIR / filename, "r") as f:
        return f.read()


class TestDroidProviderInitialization:
    """Test Droid provider initialization."""

    @patch("cli_agent_orchestrator.providers.droid.wait_for_shell")
    @patch("cli_agent_orchestrator.providers.droid.wait_until_status")
    @patch("cli_agent_orchestrator.providers.droid.tmux_client")
    def test_initialize_success(self, mock_tmux, mock_wait_status, mock_wait_shell):
        mock_wait_shell.return_value = True
        mock_wait_status.return_value = True

        provider = DroidProvider("test1234", "test-session", "window-0", "review this repo")
        result = provider.initialize()

        assert result is True
        mock_wait_shell.assert_called_once()
        mock_tmux.send_keys.assert_called_once_with(
            "test-session", "window-0", "droid 'review this repo'"
        )
        mock_wait_status.assert_called_once()

    @patch("cli_agent_orchestrator.providers.droid.wait_for_shell")
    @patch("cli_agent_orchestrator.providers.droid.tmux_client")
    def test_initialize_shell_timeout(self, mock_tmux, mock_wait_shell):
        mock_wait_shell.return_value = False

        provider = DroidProvider("test1234", "test-session", "window-0", None)

        with pytest.raises(TimeoutError, match="Shell initialization timed out"):
            provider.initialize()

    @patch("cli_agent_orchestrator.providers.droid.wait_for_shell")
    @patch("cli_agent_orchestrator.providers.droid.wait_until_status")
    @patch("cli_agent_orchestrator.providers.droid.tmux_client")
    def test_initialize_droid_timeout(self, mock_tmux, mock_wait_status, mock_wait_shell):
        mock_wait_shell.return_value = True
        mock_wait_status.return_value = False

        provider = DroidProvider("test1234", "test-session", "window-0", None)

        with pytest.raises(TimeoutError, match="Droid initialization timed out"):
            provider.initialize()


class TestDroidProviderStatusDetection:
    """Test status detection logic."""

    @patch("cli_agent_orchestrator.providers.droid.tmux_client")
    def test_get_status_idle(self, mock_tmux):
        mock_tmux.get_history.return_value = load_fixture("droid_idle_output.txt")

        provider = DroidProvider("test1234", "test-session", "window-0")
        status = provider.get_status()

        assert status == TerminalStatus.IDLE

    @patch("cli_agent_orchestrator.providers.droid.tmux_client")
    def test_get_status_completed(self, mock_tmux):
        mock_tmux.get_history.return_value = load_fixture("droid_completed_output.txt")

        provider = DroidProvider("test1234", "test-session", "window-0")
        status = provider.get_status()

        assert status == TerminalStatus.COMPLETED

    @patch("cli_agent_orchestrator.providers.droid.tmux_client")
    def test_get_status_processing(self, mock_tmux):
        mock_tmux.get_history.return_value = load_fixture("droid_processing_output.txt")

        provider = DroidProvider("test1234", "test-session", "window-0")
        status = provider.get_status()

        assert status == TerminalStatus.PROCESSING

    @patch("cli_agent_orchestrator.providers.droid.tmux_client")
    def test_get_status_with_tail_lines(self, mock_tmux):
        mock_tmux.get_history.return_value = load_fixture("droid_idle_output.txt")

        provider = DroidProvider("test1234", "test-session", "window-0")
        status = provider.get_status(tail_lines=20)

        assert status == TerminalStatus.IDLE
        mock_tmux.get_history.assert_called_once_with("test-session", "window-0", tail_lines=20)


class TestDroidProviderMessageExtraction:
    """Test message extraction from terminal output."""

    def test_extract_last_message_success(self):
        output = load_fixture("droid_completed_output.txt")

        provider = DroidProvider("test1234", "test-session", "window-0")
        message = provider.extract_last_message_from_script(output)

        assert "assistant response" in message
        assert "multiple lines" in message

    def test_extract_message_insufficient_prompts(self):
        output = "> "

        provider = DroidProvider("test1234", "test-session", "window-0")

        with pytest.raises(ValueError, match="insufficient prompts"):
            provider.extract_last_message_from_script(output)

    def test_extract_message_empty_response(self):
        output = "> \n> "

        provider = DroidProvider("test1234", "test-session", "window-0")

        with pytest.raises(ValueError, match="Empty Droid response"):
            provider.extract_last_message_from_script(output)


class TestDroidProviderEdgeCases:
    """Test edge cases and helpers."""

    def test_exit_cli_command(self):
        provider = DroidProvider("test1234", "test-session", "window-0")
        assert provider.exit_cli() == "/exit"

    def test_get_idle_pattern_for_log(self):
        provider = DroidProvider("test1234", "test-session", "window-0")
        assert provider.get_idle_pattern_for_log() == r">\s*$"
