"""O(1) Log Scheduler for efficient terminal log monitoring.

This module implements an O(1) log scheduling algorithm that:
1. Tracks file positions for incremental reading
2. Maintains circular buffers for pattern matching
3. Minimizes system calls through position caching
4. Uses lazy evaluation for status detection

Key concept: Instead of reading the entire file or using tail, we track
our read position and only read new content. For pattern matching, we
maintain a fixed-size circular buffer of recent lines.
"""

import fcntl
import logging
import os
import re
import threading
from collections import deque
from pathlib import Path
from typing import Deque, Dict, Optional

from cli_agent_orchestrator.constants import TERMINAL_LOG_DIR

logger = logging.getLogger(__name__)


class LogBuffer:
    """Fixed-size circular buffer for log line pattern matching.

    This buffer maintains only the most recent N lines for efficient
    idle pattern detection. It's a true O(1) structure for:
    - Appending new lines: O(1)
    - Checking for patterns: O(K) where K is buffer size (constant)
    """

    def __init__(self, max_lines: int = 100):
        """Initialize circular buffer.

        Args:
            max_lines: Maximum number of lines to keep in buffer
        """
        self.max_lines = max_lines
        self.buffer: Deque[str] = deque(maxlen=max_lines)

    def append(self, line: str) -> None:
        """Append a line to the buffer.

        Args:
            line: Line to append
        """
        self.buffer.append(line)

    def join(self) -> str:
        """Join all buffered lines into a single string.

        Returns:
            Concatenated buffer content
        """
        return "\n".join(self.buffer)

    def matches_pattern(self, pattern: str) -> bool:
        """Check if buffer matches the given regex pattern.

        Args:
            pattern: Regex pattern to match against

        Returns:
            True if pattern matches any content in buffer
        """
        if not pattern:
            return False
        try:
            content = self.join()
            return bool(re.search(pattern, content))
        except re.error:
            return False

    def clear(self) -> None:
        """Clear the buffer."""
        self.buffer.clear()

    def __len__(self) -> int:
        """Return number of lines in buffer."""
        return len(self.buffer)


class FilePositionTracker:
    """Tracks read position for each log file with thread safety.

    This enables O(1) incremental reading by storing the offset where
    we last read from each file. Instead of reading the entire file
    or using tail, we seek directly to our last position.
    """

    def __init__(self):
        """Initialize position tracker."""
        self._positions: Dict[str, int] = {}
        self._lock = threading.RLock()

    def get_position(self, terminal_id: str) -> int:
        """Get current read position for terminal log.

        Args:
            terminal_id: Terminal identifier

        Returns:
            File offset in bytes
        """
        with self._lock:
            return self._positions.get(terminal_id, 0)

    def set_position(self, terminal_id: str, position: int) -> None:
        """Set read position for terminal log.

        Args:
            terminal_id: Terminal identifier
            position: File offset in bytes
        """
        with self._lock:
            self._positions[terminal_id] = position

    def reset_position(self, terminal_id: str) -> None:
        """Reset position for terminal (e.g., on log rotation).

        Args:
            terminal_id: Terminal identifier
        """
        with self._lock:
            self._positions.pop(terminal_id, None)

    def get_all_positions(self) -> Dict[str, int]:
        """Get all tracked positions (for persistence).

        Returns:
            Copy of positions dictionary
        """
        with self._lock:
            return self._positions.copy()

    def clear_all(self) -> None:
        """Clear all positions."""
        with self._lock:
            self._positions.clear()


class O1LogReader:
    """O(1) log reader using incremental file reading.

    Instead of using tail or reading entire files, this reader:
    1. Remembers the last read position
    2. Seeks directly to that position
    3. Reads only new content
    4. Updates position for next read

    This is true O(1) for the read operation regardless of file size.
    """

    def __init__(
        self,
        log_dir: Path = TERMINAL_LOG_DIR,
        buffer_lines: int = 100,
        tracker: Optional[FilePositionTracker] = None,
    ):
        """Initialize O(1) log reader.

        Args:
            log_dir: Directory containing terminal log files
            buffer_lines: Number of lines to keep in pattern buffer
            tracker: Position tracker (creates new if None)
        """
        self.log_dir = log_dir
        self.buffer_lines = buffer_lines
        self.position_tracker = tracker or FilePositionTracker()
        self._buffers: Dict[str, LogBuffer] = {}
        self._buffers_lock = threading.RLock()
        self._file_handles: Dict[str, int] = {}
        self._file_locks: Dict[str, threading.Lock] = {}

    def _get_buffer(self, terminal_id: str) -> LogBuffer:
        """Get or create log buffer for terminal.

        Args:
            terminal_id: Terminal identifier

        Returns:
            Log buffer instance
        """
        with self._buffers_lock:
            if terminal_id not in self._buffers:
                self._buffers[terminal_id] = LogBuffer(max_lines=self.buffer_lines)
            return self._buffers[terminal_id]

    def _get_file_lock(self, terminal_id: str) -> threading.Lock:
        """Get or create lock for file operations.

        Args:
            terminal_id: Terminal identifier

        Returns:
            Lock instance
        """
        if terminal_id not in self._file_locks:
            self._file_locks[terminal_id] = threading.Lock()
        return self._file_locks[terminal_id]

    def _get_log_path(self, terminal_id: str) -> Path:
        """Get log file path for terminal.

        Args:
            terminal_id: Terminal identifier

        Returns:
            Path to log file
        """
        return self.log_dir / f"{terminal_id}.log"

    def read_new_content(self, terminal_id: str) -> Optional[str]:
        """Read new content from log file since last read.

        This is the core O(1) operation:
        - Get stored position (O(1))
        - Seek to position (O(1) - direct file offset)
        - Read new content only (O(K) where K is new bytes)
        - Store new position (O(1))

        Args:
            terminal_id: Terminal identifier

        Returns:
            New content since last read, or None if file doesn't exist
            Returns empty string if file exists but no new content
        """
        log_path = self._get_log_path(terminal_id)

        if not log_path.exists():
            return None

        lock = self._get_file_lock(terminal_id)
        with lock:
            try:
                with open(log_path, "r") as f:
                    # Get current position
                    current_pos = self.position_tracker.get_position(terminal_id)

                    # Check if file was truncated (log rotation)
                    file_size = f.seek(0, os.SEEK_END)
                    if current_pos > file_size:
                        logger.info(f"Log file truncated for {terminal_id}, resetting position")
                        current_pos = 0

                    # Seek to last read position
                    f.seek(current_pos)

                    # Read new content
                    new_content = f.read()

                    # Update position
                    new_pos = f.tell()
                    self.position_tracker.set_position(terminal_id, new_pos)

                    return new_content

            except Exception as e:
                logger.error(f"Error reading log for {terminal_id}: {e}")
                return None

    def update_buffer(self, terminal_id: str, content: Optional[str]) -> None:
        """Update log buffer with new content.

        Args:
            terminal_id: Terminal identifier
            content: New content to add to buffer
        """
        if not content:
            return

        buffer = self._get_buffer(terminal_id)
        for line in content.split("\n"):
            if line:  # Skip empty lines
                buffer.append(line)

    def get_buffered_content(self, terminal_id: str) -> str:
        """Get current buffer content for pattern matching.

        Args:
            terminal_id: Terminal identifier

        Returns:
            Buffered content as string
        """
        buffer = self._get_buffer(terminal_id)
        return buffer.join()

    def matches_idle_pattern(self, terminal_id: str, pattern: str) -> bool:
        """Check if buffered content matches idle pattern.

        This is O(K) where K is the buffer size (constant).

        Args:
            terminal_id: Terminal identifier
            pattern: Regex pattern to match

        Returns:
            True if pattern matches
        """
        if not pattern:
            return False

        buffer = self._get_buffer(terminal_id)
        return buffer.matches_pattern(pattern)

    def sync_and_check(self, terminal_id: str, idle_pattern: str) -> Optional[str]:
        """Sync new content and check for idle pattern in one call.

        This is the primary interface for the inbox service.

        Args:
            terminal_id: Terminal identifier
            idle_pattern: Idle pattern to check for

        Returns:
            New content if any, None otherwise
        """
        new_content = self.read_new_content(terminal_id)
        if new_content:
            self.update_buffer(terminal_id, new_content)

        if self.matches_idle_pattern(terminal_id, idle_pattern):
            return self.get_buffered_content(terminal_id)

        return None

    def reset_terminal(self, terminal_id: str) -> None:
        """Reset tracking for a terminal (e.g., after restart).

        Args:
            terminal_id: Terminal identifier
        """
        self.position_tracker.reset_position(terminal_id)
        with self._buffers_lock:
            buffer = self._buffers.get(terminal_id)
            if buffer:
                buffer.clear()

    def clear_all(self) -> None:
        """Clear all tracking state."""
        self.position_tracker.clear_all()
        with self._buffers_lock:
            self._buffers.clear()


# Global singleton instance
_global_reader: Optional[O1LogReader] = None
_global_lock = threading.Lock()


def get_log_reader() -> O1LogReader:
    """Get global O(1) log reader singleton.

    Returns:
        Global log reader instance
    """
    global _global_reader

    if _global_reader is None:
        with _global_lock:
            if _global_reader is None:
                _global_reader = O1LogReader()

    return _global_reader


def reset_global_reader() -> None:
    """Reset global reader (for testing)."""
    global _global_reader

    with _global_lock:
        if _global_reader is not None:
            _global_reader.clear_all()
        _global_reader = None
