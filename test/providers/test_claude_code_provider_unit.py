"""Unit tests for Claude Code provider."""

from unittest.mock import patch

from cli_agent_orchestrator.models.agent_profile import AgentProfile
from cli_agent_orchestrator.providers.claude_code import ClaudeCodeProvider


class TestClaudeCodeProviderCommandBuilding:
    @patch("cli_agent_orchestrator.providers.claude_code.load_agent_profile")
    def test_build_command_default_launcher(self, mock_load):
        mock_load.return_value = AgentProfile(
            name="dev",
            description="Dev",
            system_prompt="hello",
            mcpServers=None,
        )

        provider = ClaudeCodeProvider("t1", "s", "w", agent_profile="dev")
        parts = provider._build_claude_command()

        assert parts[0] == "claude"
        assert "--append-system-prompt" in parts

    @patch("cli_agent_orchestrator.providers.claude_code.load_agent_profile")
    def test_build_command_with_custom_launcher(self, mock_load):
        mock_load.return_value = AgentProfile(
            name="dev",
            description="Dev",
            system_prompt="hello",
            mcpServers=None,
            claude_code_launcher="/tmp/ccc",
            claude_code_launcher_args=["cp", "--dangerously-skip-permissions"],
        )

        provider = ClaudeCodeProvider("t1", "s", "w", agent_profile="dev")
        parts = provider._build_claude_command()

        assert parts[:3] == ["/tmp/ccc", "cp", "--dangerously-skip-permissions"]
        assert "--append-system-prompt" in parts
