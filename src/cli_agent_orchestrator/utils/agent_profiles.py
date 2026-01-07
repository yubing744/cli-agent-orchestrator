"""Agent profile utilities."""

import os
from importlib import resources
from pathlib import Path
from typing import Optional

import frontmatter

from cli_agent_orchestrator.constants import AGENT_CONTEXT_DIR, LOCAL_AGENT_STORE_DIR
from cli_agent_orchestrator.models.agent_profile import AgentProfile


def _find_repo_root(start: Path) -> Optional[Path]:
    """Find repo root by looking for pyproject.toml in parent directories."""
    for parent in [start, *start.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return None


def _load_profile_from_markdown(file_path: Path) -> AgentProfile:
    profile_data = frontmatter.loads(file_path.read_text())
    profile_data.metadata["system_prompt"] = profile_data.content.strip()
    launcher = profile_data.metadata.get("claude_code_launcher")
    if isinstance(launcher, str) and launcher.strip():
        profile_data.metadata["claude_code_launcher"] = os.path.expandvars(
            os.path.expanduser(launcher.strip())
        )
    return AgentProfile(**profile_data.metadata)


def _load_profile_from_text(markdown: str) -> AgentProfile:
    profile_data = frontmatter.loads(markdown)
    profile_data.metadata["system_prompt"] = profile_data.content.strip()
    launcher = profile_data.metadata.get("claude_code_launcher")
    if isinstance(launcher, str) and launcher.strip():
        profile_data.metadata["claude_code_launcher"] = os.path.expandvars(
            os.path.expanduser(launcher.strip())
        )
    return AgentProfile(**profile_data.metadata)


def load_agent_profile(agent_name: str) -> AgentProfile:
    """Load agent profile from local or built-in agent store."""
    try:
        # Check local store first
        local_profile = LOCAL_AGENT_STORE_DIR / f"{agent_name}.md"
        if local_profile.exists():
            return _load_profile_from_markdown(local_profile)

        # Then check installed agent-context (so providers can load effective config by name)
        context_profile = AGENT_CONTEXT_DIR / f"{agent_name}.md"
        if context_profile.exists():
            return _load_profile_from_markdown(context_profile)

        # Then check repo-local agents directory
        repo_root = _find_repo_root(Path.cwd())
        if repo_root is not None:
            repo_profile = repo_root / "agents" / f"{agent_name}.md"
            if repo_profile.exists():
                return _load_profile_from_markdown(repo_profile)

        # Fall back to built-in store
        agent_store = resources.files("cli_agent_orchestrator.agent_store")
        profile_file = agent_store / f"{agent_name}.md"

        if not profile_file.is_file():
            raise FileNotFoundError(f"Agent profile not found: {agent_name}")

        return _load_profile_from_text(profile_file.read_text())

    except Exception as e:
        raise RuntimeError(f"Failed to load agent profile '{agent_name}': {e}")
