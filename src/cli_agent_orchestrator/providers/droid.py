"""Droid CLI provider implementation."""

import re
import shlex
import time
from typing import Optional

from cli_agent_orchestrator.clients.tmux import tmux_client
from cli_agent_orchestrator.models.terminal import TerminalStatus
from cli_agent_orchestrator.providers.base import BaseProvider
from cli_agent_orchestrator.utils.agent_profiles import load_agent_profile
from cli_agent_orchestrator.utils.terminal import wait_for_shell

# Regex patterns for Droid output analysis
ANSI_CODE_PATTERN = r"\x1b\[[0-9;]*m"
BOX_DRAWING_PATTERN = r"[\u2500-\u257F]"

# Interactive chat prompt (after ANSI/box stripping)
CHAT_PROMPT_LINE_PATTERN = r"^\s*>\s*$"

# Auth / login UI markers (droid@0.41.0)
LOGIN_REQUIRED_PATTERN = r"(?i)Please login with your Factory account to continue\.?"
LOGIN_MENU_CURSOR_PATTERN = r"(?m)^\s*[>❯]\s*Login\s*$"
RETRY_CURSOR_PATTERN = r"(?m)^\s*[>❯]\s*Press Enter to try again\s*$"
AUTH_FAILED_PATTERN = r"Authentication failed:"

# Shell error marker
COMMAND_NOT_FOUND_PATTERN = r"(?i)(droid:.*not found|command not found.*droid)"

# Non-interactive error marker
NONINTERACTIVE_AUTH_FAILED_PATTERN = r"Error during droid execution: Authentication failed\."

# Used by the inbox service's log tail matcher. Keep this broad enough to trigger
# status evaluation whenever Droid is ready for user interaction.
IDLE_PROMPT_PATTERN_LOG = (
    r"(?m)(^[\u2500-\u257F\s]*>\s*[\u2500-\u257F\s]*$|"
    r"^\s*>\s*Login\s*$|^\s*>\s*Press Enter to try again\s*$|"
    r"Please login with your Factory account to continue\.)"
)


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
        # Track prompt count to detect new completions without relying on
        # "prompt count >= 2" (which becomes permanently true once history grows).
        self._last_seen_prompt_count = 0

    def initialize(self) -> bool:
        """Initialize Droid provider by starting droid command."""
        if not wait_for_shell(tmux_client, self.session_name, self.window_name, timeout=10.0):
            raise TimeoutError("Shell initialization timed out after 10 seconds")

        command = "droid"
        if self._agent_profile:
            initial_prompt = self._resolve_initial_prompt(self._agent_profile)
            if initial_prompt:
                command = f"{command} {shlex.quote(initial_prompt)}"

        tmux_client.send_keys(self.session_name, self.window_name, command)

        # Droid may land in an interactive login UI (WAITING_USER_ANSWER) rather
        # than a chat prompt (IDLE). Treat both as "initialized".
        start_time = time.time()
        while time.time() - start_time < 30.0:
            status = self.get_status()
            if status == TerminalStatus.ERROR:
                raise TimeoutError("Droid initialization failed")

            if status in (TerminalStatus.IDLE, TerminalStatus.WAITING_USER_ANSWER):
                self._initialized = True
                return True

            # Droid may take longer (e.g., interactive login); don't fail session
            # creation just because it hasn't reached a recognizable prompt yet.
            if status == TerminalStatus.PROCESSING and (time.time() - start_time) >= 3.0:
                self._initialized = True
                return True

            time.sleep(1.0)

        self._initialized = True
        return True

    def get_status(self, tail_lines: Optional[int] = None) -> TerminalStatus:
        """Get Droid status by analyzing terminal output."""
        output = tmux_client.get_history(self.session_name, self.window_name, tail_lines=tail_lines)

        if not output:
            return TerminalStatus.ERROR

        # Fast path: non-interactive auth failure
        if re.search(NONINTERACTIVE_AUTH_FAILED_PATTERN, output, re.IGNORECASE):
            return TerminalStatus.ERROR

        clean_output = self._normalize_output(output)

        if re.search(COMMAND_NOT_FOUND_PATTERN, clean_output):
            return TerminalStatus.ERROR

        # Login-required / auth UI should never be treated as ready-for-task.
        if re.search(LOGIN_REQUIRED_PATTERN, clean_output):
            return TerminalStatus.WAITING_USER_ANSWER
        if re.search(LOGIN_MENU_CURSOR_PATTERN, clean_output):
            return TerminalStatus.WAITING_USER_ANSWER
        if re.search(RETRY_CURSOR_PATTERN, clean_output):
            return TerminalStatus.WAITING_USER_ANSWER
        if AUTH_FAILED_PATTERN in clean_output:
            # Interactive auth failure screen (may allow retry)
            return TerminalStatus.WAITING_USER_ANSWER

        prompt_count = len(list(re.finditer(CHAT_PROMPT_LINE_PATTERN, clean_output, re.MULTILINE)))
        is_idle = self._ends_with_chat_prompt(clean_output)

        # If we can't see an idle prompt, assume Droid is still processing.
        if not is_idle:
            return TerminalStatus.PROCESSING

        # We see an idle prompt. Decide whether this is a new completion since the
        # last observation by tracking prompt count.
        if prompt_count < self._last_seen_prompt_count:
            # Tmux history may have truncated; resync.
            self._last_seen_prompt_count = prompt_count
            return TerminalStatus.IDLE

        if prompt_count >= 2 and prompt_count > self._last_seen_prompt_count:
            self._last_seen_prompt_count = prompt_count
            return TerminalStatus.COMPLETED

        self._last_seen_prompt_count = prompt_count
        return TerminalStatus.IDLE

    def get_idle_pattern_for_log(self) -> str:
        """Return Droid IDLE prompt pattern for log files."""
        return IDLE_PROMPT_PATTERN_LOG

    def extract_last_message_from_script(self, script_output: str) -> str:
        """Extract the last Droid response using prompt delimiters."""
        clean_output = self._normalize_output(script_output)
        prompts = list(re.finditer(CHAT_PROMPT_LINE_PATTERN, clean_output, re.MULTILINE))

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
        return "/exit"

    def cleanup(self) -> None:
        """Clean up Droid provider."""
        self._initialized = False

    def _normalize_output(self, output: str) -> str:
        """Remove ANSI codes and box-drawing characters for parsing."""
        no_ansi = re.sub(ANSI_CODE_PATTERN, "", output)
        return re.sub(BOX_DRAWING_PATTERN, "", no_ansi)

    def _ends_with_chat_prompt(self, normalized_output: str) -> bool:
        """Check if normalized output ends with a chat prompt line.

        This intentionally distinguishes the chat prompt (`>`) from menu cursor
        lines like `> Login`.
        """
        lines = [line.strip() for line in normalized_output.splitlines()]
        for line in reversed(lines):
            if not line:
                continue
            return bool(re.match(CHAT_PROMPT_LINE_PATTERN, line))
        return False

    def _resolve_initial_prompt(self, agent_profile: str) -> str:
        """Resolve the initial prompt passed to `droid`.

        For CAO, `agent_profile` is typically the name of an agent profile markdown.
        Droid CLI does not support loading system prompts directly, so we pass a
        condensed, single-line instruction.

        If profile loading fails, fall back to treating `agent_profile` as a raw
        prompt string.
        """
        try:
            profile = load_agent_profile(agent_profile)
            if profile.system_prompt:
                return self._condense_prompt(profile.system_prompt)
        except Exception:
            pass

        return self._condense_prompt(agent_profile)

    def _condense_prompt(self, prompt: str, max_chars: int = 2000) -> str:
        """Make a prompt safe to pass as a single CLI argument."""
        condensed = re.sub(r"\s+", " ", prompt).strip()
        if len(condensed) > max_chars:
            return condensed[: max_chars - 3] + "..."
        return condensed
