"""Utilities for persisting provider preferences per agent profile."""

import json
import logging
from typing import Dict, Optional

from cli_agent_orchestrator.constants import AGENT_CONTEXT_DIR, PROVIDER_PREFS_FILE

logger = logging.getLogger(__name__)


def _load_preferences() -> Dict[str, str]:
    """Load provider preferences from disk."""
    if not PROVIDER_PREFS_FILE.exists():
        return {}

    try:
        data = json.loads(PROVIDER_PREFS_FILE.read_text())
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        logger.warning(
            "Failed to read provider preferences; falling back to defaults", exc_info=True
        )

    return {}


def set_installed_provider(agent_profile: str, provider: str) -> None:
    """Persist provider selection for an agent profile."""
    AGENT_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

    preferences = _load_preferences()
    preferences[agent_profile] = provider

    PROVIDER_PREFS_FILE.write_text(json.dumps(preferences, indent=2))


def get_installed_provider(agent_profile: str) -> Optional[str]:
    """Get the stored provider for an agent profile if present."""
    preferences = _load_preferences()
    return preferences.get(agent_profile)
