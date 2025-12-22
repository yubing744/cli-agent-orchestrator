"""Tests for O(1) Log Scheduler."""

import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from cli_agent_orchestrator.utils.log_scheduler import (
    FilePositionTracker,
    LogBuffer,
    O1LogReader,
    get_log_reader,
    reset_global_reader,
)


class TestLogBuffer:
    """Test cases for LogBuffer class."""

    def test_init_default(self):
        """Test buffer initialization with default size."""
        buffer = LogBuffer()
        assert buffer.max_lines == 100
        assert len(buffer) == 0

    def test_init_custom_size(self):
        """Test buffer initialization with custom size."""
        buffer = LogBuffer(max_lines=50)
        assert buffer.max_lines == 50

    def test_append_single_line(self):
        """Test appending a single line."""
        buffer = LogBuffer()
        buffer.append("test line")
        assert len(buffer) == 1

    def test_append_multiple_lines(self):
        """Test appending multiple lines."""
        buffer = LogBuffer()
        for i in range(5):
            buffer.append(f"line {i}")
        assert len(buffer) == 5

    def test_circular_buffer_overflow(self):
        """Test that buffer respects max_lines (circular behavior)."""
        buffer = LogBuffer(max_lines=3)
        for i in range(5):
            buffer.append(f"line {i}")
        # Should only keep last 3 lines
        assert len(buffer) == 3
        content = buffer.join()
        assert "line 2" in content
        assert "line 3" in content
        assert "line 4" in content
        assert "line 0" not in content
        assert "line 1" not in content

    def test_join_empty_buffer(self):
        """Test joining empty buffer."""
        buffer = LogBuffer()
        assert buffer.join() == ""

    def test_join_single_line(self):
        """Test joining buffer with one line."""
        buffer = LogBuffer()
        buffer.append("test line")
        assert buffer.join() == "test line"

    def test_join_multiple_lines(self):
        """Test joining buffer with multiple lines."""
        buffer = LogBuffer()
        buffer.append("line 1")
        buffer.append("line 2")
        buffer.append("line 3")
        assert buffer.join() == "line 1\nline 2\nline 3"

    def test_matches_pattern_simple(self):
        """Test simple pattern matching."""
        buffer = LogBuffer()
        buffer.append("Processing...")
        buffer.append("[agent] >")
        assert buffer.matches_pattern(r"\[agent\]")

    def test_matches_pattern_regex(self):
        """Test regex pattern matching."""
        buffer = LogBuffer()
        buffer.append("Some output")
        buffer.append("\x1b[38;5;13m>\x1b[39m")
        assert buffer.matches_pattern(r"\x1b\[38;5;13m>\x1b\[39m")

    def test_matches_pattern_no_match(self):
        """Test pattern matching when pattern doesn't exist."""
        buffer = LogBuffer()
        buffer.append("Some random text")
        assert not buffer.matches_pattern(r"\[agent\]")

    def test_matches_pattern_empty_buffer(self):
        """Test pattern matching on empty buffer."""
        buffer = LogBuffer()
        assert not buffer.matches_pattern(r"anything")

    def test_matches_pattern_invalid_regex(self):
        """Test pattern matching with invalid regex."""
        buffer = LogBuffer()
        buffer.append("test")
        # Invalid regex should return False, not raise
        assert not buffer.matches_pattern("[invalid(")

    def test_clear(self):
        """Test clearing buffer."""
        buffer = LogBuffer()
        buffer.append("line 1")
        buffer.append("line 2")
        assert len(buffer) == 2
        buffer.clear()
        assert len(buffer) == 0


class TestFilePositionTracker:
    """Test cases for FilePositionTracker class."""

    def test_init(self):
        """Test tracker initialization."""
        tracker = FilePositionTracker()
        assert tracker.get_position("terminal1") == 0

    def test_set_and_get_position(self):
        """Test setting and getting position."""
        tracker = FilePositionTracker()
        tracker.set_position("terminal1", 100)
        assert tracker.get_position("terminal1") == 100

    def test_multiple_terminals(self):
        """Test tracking positions for multiple terminals."""
        tracker = FilePositionTracker()
        tracker.set_position("terminal1", 100)
        tracker.set_position("terminal2", 200)
        tracker.set_position("terminal3", 300)
        assert tracker.get_position("terminal1") == 100
        assert tracker.get_position("terminal2") == 200
        assert tracker.get_position("terminal3") == 300

    def test_reset_position(self):
        """Test resetting position for a terminal."""
        tracker = FilePositionTracker()
        tracker.set_position("terminal1", 100)
        tracker.reset_position("terminal1")
        assert tracker.get_position("terminal1") == 0

    def test_get_all_positions(self):
        """Test getting all positions."""
        tracker = FilePositionTracker()
        tracker.set_position("terminal1", 100)
        tracker.set_position("terminal2", 200)
        positions = tracker.get_all_positions()
        assert positions == {"terminal1": 100, "terminal2": 200}

    def test_clear_all(self):
        """Test clearing all positions."""
        tracker = FilePositionTracker()
        tracker.set_position("terminal1", 100)
        tracker.set_position("terminal2", 200)
        tracker.clear_all()
        assert tracker.get_all_positions() == {}

    def test_thread_safety(self):
        """Test thread safety of position tracker."""
        tracker = FilePositionTracker()
        errors = []

        def set_positions(thread_id):
            try:
                for i in range(100):
                    tracker.set_position(f"terminal_{thread_id}_{i}", i)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=set_positions, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestO1LogReader:
    """Test cases for O1LogReader class."""

    def test_init(self):
        """Test reader initialization."""
        reader = O1LogReader()
        assert reader.log_dir is not None
        assert reader.buffer_lines == 100

    def test_init_custom_params(self, tmp_path):
        """Test reader initialization with custom parameters."""
        reader = O1LogReader(log_dir=tmp_path, buffer_lines=50)
        assert reader.log_dir == tmp_path
        assert reader.buffer_lines == 50

    def test_get_log_path(self, tmp_path):
        """Test getting log file path."""
        reader = O1LogReader(log_dir=tmp_path)
        path = reader._get_log_path("terminal123")
        assert path == tmp_path / "terminal123.log"

    def test_read_new_content_no_file(self, tmp_path):
        """Test reading when log file doesn't exist."""
        reader = O1LogReader(log_dir=tmp_path)
        content = reader.read_new_content("nonexistent")
        assert content is None

    def test_read_new_content_empty_file(self, tmp_path):
        """Test reading from an empty log file."""
        log_file = tmp_path / "terminal1.log"
        log_file.write_text("")

        reader = O1LogReader(log_dir=tmp_path)
        content = reader.read_new_content("terminal1")
        assert content == ""

    def test_read_new_content_incremental(self, tmp_path):
        """Test incremental reading - only new content is returned."""
        log_file = tmp_path / "terminal1.log"
        log_file.write_text("line 1\nline 2\n")

        reader = O1LogReader(log_dir=tmp_path)

        # First read should get all content
        content1 = reader.read_new_content("terminal1")
        assert "line 1" in content1
        assert "line 2" in content1

        # Append more content
        with open(log_file, "a") as f:
            f.write("line 3\nline 4\n")

        # Second read should only get new content
        content2 = reader.read_new_content("terminal1")
        assert "line 1" not in content2
        assert "line 2" not in content2
        assert "line 3" in content2
        assert "line 4" in content2

    def test_read_new_content_tracks_position(self, tmp_path):
        """Test that position is tracked correctly."""
        log_file = tmp_path / "terminal1.log"
        log_file.write_text("line 1\nline 2\nline 3\n")

        reader = O1LogReader(log_dir=tmp_path)
        tracker = reader.position_tracker

        # Initially position should be 0
        assert tracker.get_position("terminal1") == 0

        # After reading, position should advance
        reader.read_new_content("terminal1")
        position_after_first_read = tracker.get_position("terminal1")
        assert position_after_first_read > 0

        # No new content, position should stay the same
        reader.read_new_content("terminal1")
        assert tracker.get_position("terminal1") == position_after_first_read

    def test_update_buffer(self, tmp_path):
        """Test updating log buffer."""
        reader = O1LogReader(log_dir=tmp_path)
        reader.update_buffer("terminal1", "line 1\nline 2\nline 3\n")

        buffer = reader._get_buffer("terminal1")
        assert len(buffer) == 3
        assert buffer.join() == "line 1\nline 2\nline 3"

    def test_buffer_respects_max_lines(self, tmp_path):
        """Test that buffer doesn't grow beyond max_lines."""
        reader = O1LogReader(log_dir=tmp_path, buffer_lines=3)

        for i in range(10):
            reader.update_buffer("terminal1", f"line {i}\n")

        buffer = reader._get_buffer("terminal1")
        assert len(buffer) <= 3

    def test_matches_idle_pattern(self, tmp_path):
        """Test checking for idle pattern in buffer."""
        reader = O1LogReader(log_dir=tmp_path)
        reader.update_buffer("terminal1", "Processing...\n\x1b[38;5;13m>\x1b[39m")

        pattern = r"\x1b\[38;5;13m>\x1b\[39m"
        assert reader.matches_idle_pattern("terminal1", pattern)

    def test_sync_and_check(self, tmp_path):
        """Test sync_and_check combined operation."""
        log_file = tmp_path / "terminal1.log"
        log_file.write_text("Processing...\n\x1b[38;5;13m>\x1b[39m\n")

        reader = O1LogReader(log_dir=tmp_path)
        pattern = r"\x1b\[38;5;13m>\x1b\[39m"

        result = reader.sync_and_check("terminal1", pattern)
        assert result is not None
        assert "\x1b[38;5;13m>" in result

    def test_reset_terminal(self, tmp_path):
        """Test resetting terminal tracking."""
        log_file = tmp_path / "terminal1.log"
        log_file.write_text("line 1\n")

        reader = O1LogReader(log_dir=tmp_path)
        reader.read_new_content("terminal1")

        # Position should be non-zero
        assert reader.position_tracker.get_position("terminal1") > 0

        # Reset should clear position
        reader.reset_terminal("terminal1")
        assert reader.position_tracker.get_position("terminal1") == 0

    def test_clear_all(self, tmp_path):
        """Test clearing all tracking."""
        reader = O1LogReader(log_dir=tmp_path)

        for i in range(3):
            log_file = tmp_path / f"terminal{i}.log"
            log_file.write_text(f"content {i}\n")
            reader.read_new_content(f"terminal{i}")

        # Clear all
        reader.clear_all()

        # All positions should be reset
        assert reader.position_tracker.get_all_positions() == {}


class TestGlobalReader:
    """Test cases for global log reader singleton."""

    def test_get_log_reader_singleton(self):
        """Test that get_log_reader returns singleton."""
        reader1 = get_log_reader()
        reader2 = get_log_reader()
        assert reader1 is reader2

    def test_reset_global_reader(self):
        """Test resetting global reader."""
        reader1 = get_log_reader()
        reset_global_reader()
        reader2 = get_log_reader()
        assert reader1 is not reader2

    @pytest.fixture(autouse=True)
    def reset_reader_before_each_test(self):
        """Reset global reader before each test."""
        reset_global_reader()
        yield
        reset_global_reader()


class TestIntegration:
    """Integration tests for O(1) log scheduler."""

    def test_full_workflow(self, tmp_path):
        """Test complete workflow: write, read, update buffer, check pattern."""
        log_file = tmp_path / "terminal1.log"
        reader = O1LogReader(log_dir=tmp_path, buffer_lines=5)

        # Simulate agent starting
        log_file.write_text("Agent initializing...\n")
        result = reader.sync_and_check("terminal1", r"Agent ready")
        assert result is None  # Pattern not found yet

        # Simulate agent becoming idle
        with open(log_file, "a") as f:
            f.write("Processing complete\n")
            f.write("[agent] > Ready for input\n")

        result = reader.sync_and_check("terminal1", r"\[agent\]")
        assert result is not None
        assert "Ready for input" in result

    def test_log_rotation_handling(self, tmp_path):
        """Test handling of log rotation (file truncation)."""
        log_file = tmp_path / "terminal1.log"
        reader = O1LogReader(log_dir=tmp_path)

        # Write initial content
        log_file.write_text("Initial content\n" * 10)
        reader.read_new_content("terminal1")
        initial_position = reader.position_tracker.get_position("terminal1")
        assert initial_position > 0

        # Simulate log rotation (truncate file)
        log_file.write_text("Rotated content\n")

        # Should detect truncation and reset
        content = reader.read_new_content("terminal1")
        assert "Rotated content" in content

    def test_concurrent_terminal_monitoring(self, tmp_path):
        """Test monitoring multiple terminals concurrently."""
        reader = O1LogReader(log_dir=tmp_path)

        # Create logs for multiple terminals
        for i in range(5):
            log_file = tmp_path / f"terminal{i}.log"
            log_file.write_text(f"Terminal {i} content\n")

        # Read from all terminals
        for i in range(5):
            content = reader.read_new_content(f"terminal{i}")
            assert content is not None
            assert f"Terminal {i}" in content
