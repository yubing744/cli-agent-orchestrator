"""Droid CLI provider implementation."""

import re
import shlex
from typing import Optional

from cli_agent_orchestrator.clients.tmux import tmux_client
from cli_agent_orchestrator.models.terminal import TerminalStatus
from cli_agent_orchestrator.providers.base import BaseProvider
from cli_agent_orchestrator.utils.terminal import wait_for_shell, wait_until_status

# Regex patterns for Droid output analysis
ANSI_CODE_PATTERN = r"\x1b\[[0-9;]*m"
BOX_DRAWING_PATTERN = r"[\u2500-\u257F]"
PROMPT_PATTERN = r"^\s*>\s*$"
IDLE_PROMPT_PATTERN_LOG = r">\s*[\u2500-\u257F\s]*$"


class DroidProvider(BaseProvider):
    """Provider for Droid CLI tool integration."""

    def __init__(
        self,
        terminal_id: str,
        session_name: str,
        window_name: str,
        agent_profile: Optional[str] = None,
    ):
        super().__init__(terminal_id, session_name, window_name)
        self._initialized = False
        self._agent_profile = agent_profile

    def initialize(self) -> bool:
        """Initialize Droid provider by starting droid command."""
        if not wait_for_shell(tmux_client, self.session_name, self.window_name, timeout=10.0):
            raise TimeoutError("Shell initialization timed out after 10 seconds")

        command = "droid"
        if self._agent_profile:
            command = f"{command} {shlex.quote(self._agent_profile)}"

        tmux_client.send_keys(self.session_name, self.window_name, command)

        if not wait_until_status(self, TerminalStatus.IDLE, timeout=30.0, polling_interval=1.0):
            raise TimeoutError("Droid initialization timed out after 30 seconds")

        self._initialized = True
        return True

    def get_status(self, tail_lines: Optional[int] = None) -> TerminalStatus:
        """Get Droid status by analyzing terminal output."""
        output = tmux_client.get_history(self.session_name, self.window_name, tail_lines=tail_lines)

        if not output:
            return TerminalStatus.ERROR

        clean_output = self._normalize_output(output)

        prompts = list(re.finditer(PROMPT_PATTERN, clean_output, re.MULTILINE))

        if not prompts:
            return TerminalStatus.PROCESSING

        # If we have multiple prompts, assume last response completed
        if len(prompts) >= 2:
            return TerminalStatus.COMPLETED

        # Single prompt only -> ready but no prior response
        return TerminalStatus.IDLE

    def get_idle_pattern_for_log(self) -> str:
        """Return Droid IDLE prompt pattern for log files."""
        return IDLE_PROMPT_PATTERN_LOG

    def extract_last_message_from_script(self, script_output: str) -> str:
        """Extract the last Droid response using prompt delimiters."""
        clean_output = self._normalize_output(script_output)
        prompts = list(re.finditer(PROMPT_PATTERN, clean_output, re.MULTILINE))

        if len(prompts) < 2:
            raise ValueError("No complete Droid response found - insufficient prompts")

        last_prompt = prompts[-1]
        prev_prompt = prompts[-2]

        final_answer = clean_output[prev_prompt.end() : last_prompt.start()].strip()

        if not final_answer:
            raise ValueError("Empty Droid response - no content found")

        return final_answer

    def exit_cli(self) -> str:
        """Get the command to exit Droid CLI."""
        return "/quit"

    def cleanup(self) -> None:
        """Clean up Droid provider."""
        self._initialized = False

    def _normalize_output(self, output: str) -> str:
        """Remove ANSI codes and box-drawing characters for parsing."""
        no_ansi = re.sub(ANSI_CODE_PATTERN, "", output)
        return re.sub(BOX_DRAWING_PATTERN, "", no_ansi)
