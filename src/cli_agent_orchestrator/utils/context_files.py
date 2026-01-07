"""Utilities for agent context files (frontmatter-backed)."""

import os
from pathlib import Path
from typing import Dict, Optional

import frontmatter

from cli_agent_orchestrator.constants import AGENT_CONTEXT_DIR


def write_context_with_provider(source_file: Path, provider: str, dest_file: Path) -> None:
    """Copy a context file to destination and set provider in frontmatter."""
    post = frontmatter.loads(source_file.read_text())
    post.metadata["provider"] = provider
    dest_file.write_text(frontmatter.dumps(post))


def get_context_provider(agent_profile: str) -> Optional[str]:
    """Return provider from agent context frontmatter if present."""
    file_path = AGENT_CONTEXT_DIR / f"{agent_profile}.md"
    if not file_path.exists():
        return None

    try:
        post = frontmatter.loads(file_path.read_text())
        provider = post.metadata.get("provider")
        if isinstance(provider, str):
            return provider
    except Exception:
        return None

    return None


def get_context_working_directory(agent_profile: str) -> Optional[str]:
    """Return working_directory from agent context frontmatter if present."""
    file_path = AGENT_CONTEXT_DIR / f"{agent_profile}.md"
    if not file_path.exists():
        return None

    try:
        post = frontmatter.loads(file_path.read_text())
        working_directory = post.metadata.get("working_directory")
        if isinstance(working_directory, str) and working_directory.strip():
            raw = working_directory.strip()
            return os.path.expandvars(os.path.expanduser(raw))
    except Exception:
        return None

    return None


def get_context_environment(agent_profile: str) -> Dict[str, str]:
    """Return environment variables from agent context frontmatter if present.

    Expected frontmatter format:

    env:
      KEY: value
      OTHER_KEY: other
    """
    file_path = AGENT_CONTEXT_DIR / f"{agent_profile}.md"
    if not file_path.exists():
        return {}

    try:
        post = frontmatter.loads(file_path.read_text())
        env = post.metadata.get("env")
        if not isinstance(env, dict):
            return {}

        result: Dict[str, str] = {}
        for key, value in env.items():
            if isinstance(key, str) and isinstance(value, str) and key.strip():
                result[key.strip()] = value
        return result
    except Exception:
        return {}
