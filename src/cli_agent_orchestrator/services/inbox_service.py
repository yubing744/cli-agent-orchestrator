"""Inbox service with O(1) log scheduling for automatic message delivery."""

import logging
from pathlib import Path

from watchdog.events import FileModifiedEvent, FileSystemEventHandler

from cli_agent_orchestrator.clients.database import get_pending_messages, update_message_status
from cli_agent_orchestrator.constants import INBOX_SERVICE_TAIL_LINES, TERMINAL_LOG_DIR
from cli_agent_orchestrator.models.inbox import MessageStatus
from cli_agent_orchestrator.models.terminal import TerminalStatus
from cli_agent_orchestrator.providers.manager import provider_manager
from cli_agent_orchestrator.services import terminal_service
from cli_agent_orchestrator.utils.log_scheduler import get_log_reader

logger = logging.getLogger(__name__)

# Global O(1) log reader
_log_reader = get_log_reader()


def _has_idle_pattern(terminal_id: str) -> bool:
    """Check if log tail contains idle pattern using O(1) incremental reading.

    This replaces the O(N) subprocess tail approach with O(1) position tracking.
    """
    try:
        provider = provider_manager.get_provider(terminal_id)
        if provider is None:
            return False
        idle_pattern = provider.get_idle_pattern_for_log()

        # Use O(1) log reader to check for idle pattern
        content = _log_reader.sync_and_check(terminal_id, idle_pattern)
        return content is not None

    except Exception as e:
        logger.debug(f"Error checking idle pattern for {terminal_id}: {e}")
        return False


def check_and_send_pending_messages(terminal_id: str) -> bool:
    """Check for pending messages and send if terminal is ready.

    Args:
        terminal_id: Terminal ID to check messages for

    Returns:
        bool: True if a message was sent, False otherwise

    Raises:
        ValueError: If provider not found for terminal
    """
    # Check for pending messages
    messages = get_pending_messages(terminal_id, limit=1)
    if not messages:
        return False

    message = messages[0]

    # Get provider and check status
    provider = provider_manager.get_provider(terminal_id)
    if provider is None:
        raise ValueError(f"Provider not found for terminal {terminal_id}")
    status = provider.get_status(tail_lines=INBOX_SERVICE_TAIL_LINES)

    if status not in (TerminalStatus.IDLE, TerminalStatus.COMPLETED):
        logger.debug(f"Terminal {terminal_id} not ready (status={status})")
        return False

    # Send message
    try:
        terminal_service.send_input(terminal_id, message.message)
        update_message_status(message.id, MessageStatus.DELIVERED)
        logger.info(f"Delivered message {message.id} to terminal {terminal_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send message {message.id} to {terminal_id}: {e}")
        update_message_status(message.id, MessageStatus.FAILED)
        raise


class LogFileHandler(FileSystemEventHandler):
    """Handler for terminal log file changes with O(1) scheduling.

    This handler uses the O(1) log reader to efficiently detect when
    terminals become idle and deliver pending messages.
    """

    def __init__(self):
        """Initialize handler with O(1) log reader."""
        self.log_reader = _log_reader

    def on_modified(self, event):
        """Handle file modification events with O(1) incremental processing."""
        if isinstance(event, FileModifiedEvent) and event.src_path.endswith(".log"):
            log_path = Path(event.src_path)
            terminal_id = log_path.stem
            logger.debug(f"Log file modified: {terminal_id}.log")
            self._handle_log_change(terminal_id)

    def _handle_log_change(self, terminal_id: str):
        """Handle log file change and attempt message delivery using O(1) scheduling."""
        try:
            # Check for pending messages first (fast DB query)
            messages = get_pending_messages(terminal_id, limit=1)
            if not messages:
                logger.debug(f"No pending messages for {terminal_id}, skipping")
                return

            # O(1) check: sync new content and check for idle pattern
            # This is efficient because:
            # 1. Only reads new content (not entire file)
            # 2. Uses in-memory buffer for pattern matching
            # 3. No subprocess calls to tail
            if not _has_idle_pattern(terminal_id):
                logger.debug(
                    f"Terminal {terminal_id} not idle (no idle pattern in log tail), skipping"
                )
                return

            # Attempt delivery
            check_and_send_pending_messages(terminal_id)

        except Exception as e:
            logger.error(f"Error handling log change for {terminal_id}: {e}")
