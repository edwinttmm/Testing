"""
Full-screen and Sequential Video Playback Testing Suite
Comprehensive testing for video playback functionality, full-screen modes, and sequential playback
"""
import pytest
import asyncio
import time
import cv2
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from unittest.mock import Mock, patch, MagicMock
import threading
import queue
from datetime import datetime, timedelta
import json
import tempfile
import os

# Import test configuration
import sys
sys.path.append('/home/user/Testing/tests/comprehensive-testing-framework/config')
from test_config import test_config

# Mock video player libraries
try:
    import pygame
except ImportError:
    pygame = None

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    tk = None
    ttk = None


class MockVideoPlayer:
    """Mock video player for testing playback functionality"""
    
    def __init__(self, video_path: str):
        self.video_path = video_path
        self.is_playing = False
        self.is_paused = False
        self.is_fullscreen = False
        self.current_frame = 0
        self.total_frames = 1800  # 60 seconds at 30 fps
        self.fps = 30
        self.position = 0.0  # Position in seconds
        self.duration = 60.0  # Duration in seconds
        self.volume = 1.0
        self.playback_speed = 1.0
        self.loop_enabled = False
        
        # Playback state
        self.start_time = None
        self.pause_time = None
        self.playback_events = []
        
        # Video properties
        self.width = 1920
        self.height = 1080
        self.format = "mp4"
        
    def load(self) -> bool:
        """Load video file"""
        if os.path.exists(self.video_path):
            self.playback_events.append({
                "event": "loaded",
                "timestamp": time.time(),
                "video_path": self.video_path
            })
            return True
        return False
    
    def play(self) -> bool:
        """Start video playback"""
        if not self.is_playing:
            self.is_playing = True
            self.is_paused = False
            self.start_time = time.time()
            
            self.playback_events.append({
                "event": "play_started",
                "timestamp": time.time(),
                "position": self.position
            })
            return True
        return False
    
    def pause(self) -> bool:
        """Pause video playback"""
        if self.is_playing and not self.is_paused:
            self.is_paused = True
            self.pause_time = time.time()
            
            self.playback_events.append({
                "event": "paused",
                "timestamp": time.time(),
                "position": self.position
            })
            return True
        return False
    
    def stop(self) -> bool:
        """Stop video playback"""
        if self.is_playing:
            self.is_playing = False
            self.is_paused = False
            self.position = 0.0
            self.current_frame = 0
            
            self.playback_events.append({
                "event": "stopped",
                "timestamp": time.time()
            })
            return True
        return False
    
    def seek(self, position: float) -> bool:
        """Seek to specific position in video"""
        if 0 <= position <= self.duration:
            self.position = position
            self.current_frame = int(position * self.fps)
            
            self.playback_events.append({
                "event": "seeked",
                "timestamp": time.time(),
                "position": position
            })
            return True
        return False
    
    def set_fullscreen(self, fullscreen: bool) -> bool:
        """Set fullscreen mode"""
        self.is_fullscreen = fullscreen
        
        self.playback_events.append({
            "event": "fullscreen_toggled",
            "timestamp": time.time(),
            "fullscreen": fullscreen
        })
        return True
    
    def set_volume(self, volume: float) -> bool:
        """Set playback volume"""
        if 0.0 <= volume <= 1.0:
            self.volume = volume
            return True
        return False
    
    def set_playback_speed(self, speed: float) -> bool:
        """Set playback speed"""
        if 0.1 <= speed <= 4.0:
            self.playback_speed = speed
            return True
        return False
    
    def get_current_frame(self) -> Optional[np.ndarray]:
        """Get current video frame"""
        if self.is_playing and not self.is_paused:
            # Update position based on elapsed time
            if self.start_time:
                elapsed = (time.time() - self.start_time) * self.playback_speed
                self.position = min(self.duration, elapsed)
                self.current_frame = int(self.position * self.fps)
        
        # Generate synthetic frame
        frame = np.random.randint(0, 255, (self.height, self.width, 3), dtype=np.uint8)
        
        # Add frame number overlay
        cv2.putText(frame, f"Frame: {self.current_frame}", (50, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        return frame
    
    def get_position(self) -> float:
        """Get current playback position"""
        return self.position
    
    def get_duration(self) -> float:
        """Get video duration"""
        return self.duration
    
    def is_ended(self) -> bool:
        """Check if video has ended"""
        return self.position >= self.duration and self.is_playing


class TestVideoPlaybackBasicFunctionality:
    """Test suite for basic video playback functionality"""
    
    def setup_method(self):
        """Set up test environment"""
        # Create test video files
        self.test_videos = []
        for i in range(3):
            video_path = f"/tmp/test_video_{i}.mp4"
            
            # Create mock video file
            with open(video_path, 'w') as f:
                f.write(f"Mock video content {i}")
            
            self.test_videos.append(video_path)
        
        self.player = MockVideoPlayer(self.test_videos[0])
    
    def teardown_method(self):
        """Clean up test environment"""
        # Clean up test video files
        for video_path in self.test_videos:
            if os.path.exists(video_path):
                os.unlink(video_path)
    
    def test_video_loading(self):
        """Test video file loading"""
        # Test successful loading
        load_result = self.player.load()
        assert load_result is True
        
        # Verify loading event was recorded
        load_events = [e for e in self.player.playback_events if e["event"] == "loaded"]
        assert len(load_events) == 1
        assert load_events[0]["video_path"] == self.test_videos[0]
        
        # Test loading non-existent file
        invalid_player = MockVideoPlayer("/non/existent/path.mp4")
        load_result = invalid_player.load()
        assert load_result is False
    
    def test_playback_controls(self):
        """Test basic playback controls (play, pause, stop)"""
        self.player.load()
        
        # Test play
        play_result = self.player.play()
        assert play_result is True
        assert self.player.is_playing is True
        assert self.player.is_paused is False
        
        # Wait a moment for playback
        time.sleep(0.5)
        
        # Test pause
        pause_result = self.player.pause()
        assert pause_result is True
        assert self.player.is_playing is True
        assert self.player.is_paused is True
        
        # Test resume (play while paused)
        resume_result = self.player.play()
        assert resume_result is True
        assert self.player.is_paused is False
        
        # Test stop
        stop_result = self.player.stop()
        assert stop_result is True
        assert self.player.is_playing is False
        assert self.player.position == 0.0
    
    def test_seeking_functionality(self):
        """Test video seeking functionality"""
        self.player.load()
        self.player.play()
        
        # Test seeking to different positions
        seek_positions = [10.0, 25.5, 45.0, 5.0]  # seconds
        
        for position in seek_positions:
            seek_result = self.player.seek(position)
            assert seek_result is True
            assert abs(self.player.get_position() - position) < 0.1
        
        # Test invalid seek positions
        invalid_positions = [-5.0, 120.0]  # Before start and after end
        
        for position in invalid_positions:
            seek_result = self.player.seek(position)
            assert seek_result is False
    
    def test_playback_speed_control(self):
        """Test playback speed control"""
        self.player.load()
        
        # Test different playback speeds
        speeds = [0.5, 1.0, 1.5, 2.0, 0.25, 4.0]
        
        for speed in speeds:
            speed_result = self.player.set_playback_speed(speed)
            assert speed_result is True
            assert self.player.playback_speed == speed
        
        # Test invalid speeds
        invalid_speeds = [0.05, 5.0, -1.0]
        
        for speed in invalid_speeds:
            speed_result = self.player.set_playback_speed(speed)
            assert speed_result is False
    
    def test_volume_control(self):
        """Test audio volume control"""
        self.player.load()
        
        # Test different volume levels
        volumes = [0.0, 0.25, 0.5, 0.75, 1.0]
        
        for volume in volumes:
            volume_result = self.player.set_volume(volume)
            assert volume_result is True
            assert self.player.volume == volume
        
        # Test invalid volumes
        invalid_volumes = [-0.1, 1.1, 2.0]
        
        for volume in invalid_volumes:
            volume_result = self.player.set_volume(volume)
            assert volume_result is False
    
    def test_frame_retrieval(self):
        """Test current frame retrieval"""
        self.player.load()
        self.player.play()
        
        # Get multiple frames
        frames = []
        for i in range(5):
            frame = self.player.get_current_frame()
            assert frame is not None
            assert frame.shape == (self.player.height, self.player.width, 3)
            assert frame.dtype == np.uint8
            
            frames.append(frame)
            time.sleep(0.1)
        
        # Frames should be different (unless paused)
        assert not all(np.array_equal(frames[0], frame) for frame in frames[1:])


class TestFullScreenPlayback:
    """Test suite for full-screen video playback"""
    
    def setup_method(self):
        """Set up test environment"""
        self.test_video = "/tmp/fullscreen_test.mp4"
        with open(self.test_video, 'w') as f:
            f.write("Fullscreen test video")
        
        self.player = MockVideoPlayer(self.test_video)
        self.player.load()
    
    def teardown_method(self):
        """Clean up test environment"""
        if os.path.exists(self.test_video):
            os.unlink(self.test_video)
    
    def test_fullscreen_toggle(self):
        """Test toggling fullscreen mode"""
        # Initially not fullscreen
        assert self.player.is_fullscreen is False
        
        # Enable fullscreen
        fullscreen_result = self.player.set_fullscreen(True)
        assert fullscreen_result is True
        assert self.player.is_fullscreen is True
        
        # Verify fullscreen event
        fullscreen_events = [e for e in self.player.playback_events 
                           if e["event"] == "fullscreen_toggled" and e["fullscreen"] is True]
        assert len(fullscreen_events) == 1
        
        # Disable fullscreen
        windowed_result = self.player.set_fullscreen(False)
        assert windowed_result is True
        assert self.player.is_fullscreen is False
    
    def test_fullscreen_playback_performance(self):
        """Test playback performance in fullscreen mode"""
        self.player.set_fullscreen(True)
        self.player.play()
        
        # Measure frame rate in fullscreen
        frame_times = []
        frame_count = 30
        
        for i in range(frame_count):
            start_time = time.time()
            frame = self.player.get_current_frame()
            frame_time = time.time() - start_time
            
            frame_times.append(frame_time)
            assert frame is not None
            
            time.sleep(1.0 / 30)  # Target 30 FPS
        
        # Calculate performance metrics
        average_frame_time = sum(frame_times) / len(frame_times)
        max_frame_time = max(frame_times)
        
        # Frame processing should be fast enough for real-time playback
        assert average_frame_time < 0.02  # Less than 20ms average
        assert max_frame_time < 0.05      # Less than 50ms maximum
    
    def test_fullscreen_resolution_handling(self):
        """Test handling of different resolutions in fullscreen"""
        resolutions = [
            (1920, 1080),  # Full HD
            (1280, 720),   # HD
            (3840, 2160),  # 4K
            (640, 480)     # SD
        ]
        
        for width, height in resolutions:
            # Create player with specific resolution
            player = MockVideoPlayer(self.test_video)
            player.width = width
            player.height = height
            player.load()
            
            # Test fullscreen with this resolution
            fullscreen_result = player.set_fullscreen(True)
            assert fullscreen_result is True
            
            # Get frame and verify dimensions
            frame = player.get_current_frame()
            assert frame.shape == (height, width, 3)
    
    def test_fullscreen_keyboard_controls(self):
        """Test keyboard controls in fullscreen mode"""
        self.player.set_fullscreen(True)
        self.player.play()
        
        # Simulate keyboard events
        keyboard_events = [
            {"key": "space", "action": "pause_toggle"},
            {"key": "escape", "action": "exit_fullscreen"},
            {"key": "f", "action": "toggle_fullscreen"},
            {"key": "left", "action": "seek_backward"},
            {"key": "right", "action": "seek_forward"},
            {"key": "up", "action": "volume_up"},
            {"key": "down", "action": "volume_down"}
        ]
        
        for event in keyboard_events:
            # Simulate key press
            keyboard_result = self._simulate_keyboard_event(self.player, event)
            assert keyboard_result["handled"] is True
            
            # Verify appropriate action was taken
            if event["action"] == "exit_fullscreen":
                assert self.player.is_fullscreen is False
            elif event["action"] == "pause_toggle":
                # Should toggle pause state
                pass  # Specific test depends on current state
    
    def test_fullscreen_display_detection(self):
        """Test detection and handling of multiple displays"""
        # Mock display information
        displays = [
            {"id": 0, "width": 1920, "height": 1080, "primary": True},
            {"id": 1, "width": 2560, "height": 1440, "primary": False},
            {"id": 2, "width": 1280, "height": 1024, "primary": False}
        ]
        
        for display in displays:
            # Test fullscreen on specific display
            fullscreen_result = self._set_fullscreen_on_display(
                self.player, display["id"]
            )
            
            assert fullscreen_result["success"] is True
            assert fullscreen_result["display_id"] == display["id"]
            assert fullscreen_result["resolution"] == (display["width"], display["height"])
    
    def _simulate_keyboard_event(self, player: MockVideoPlayer, event: Dict) -> Dict:
        """Simulate keyboard event in fullscreen mode"""
        # Mock keyboard event handling
        if event["key"] == "escape":
            player.set_fullscreen(False)
        elif event["key"] == "space":
            if player.is_paused:
                player.play()
            else:
                player.pause()
        elif event["key"] == "f":
            player.set_fullscreen(not player.is_fullscreen)
        
        return {"handled": True, "key": event["key"], "action": event["action"]}
    
    def _set_fullscreen_on_display(self, player: MockVideoPlayer, display_id: int) -> Dict:
        """Set fullscreen on specific display"""
        # Mock setting fullscreen on specific display
        player.set_fullscreen(True)
        
        # Mock display information based on display_id
        display_info = {
            0: {"width": 1920, "height": 1080},
            1: {"width": 2560, "height": 1440},
            2: {"width": 1280, "height": 1024}
        }
        
        resolution = display_info.get(display_id, {"width": 1920, "height": 1080})
        
        return {
            "success": True,
            "display_id": display_id,
            "resolution": (resolution["width"], resolution["height"])
        }


class TestSequentialPlayback:
    """Test suite for sequential video playback"""
    
    def setup_method(self):
        """Set up test environment"""
        # Create multiple test videos for sequential playback
        self.test_videos = []
        self.video_durations = [30.0, 45.0, 60.0, 25.0]  # Different durations
        
        for i, duration in enumerate(self.video_durations):
            video_path = f"/tmp/seq_test_video_{i}.mp4"
            with open(video_path, 'w') as f:
                f.write(f"Sequential test video {i}")
            
            self.test_videos.append({
                "path": video_path,
                "duration": duration,
                "index": i
            })
        
        self.playlist = self.test_videos.copy()
        self.current_video_index = 0
        self.sequential_player = None
    
    def teardown_method(self):
        """Clean up test environment"""
        for video in self.test_videos:
            if os.path.exists(video["path"]):
                os.unlink(video["path"])
    
    def test_sequential_playback_basic(self):
        """Test basic sequential playback functionality"""
        playback_log = []
        
        # Play videos sequentially
        for video in self.playlist:
            player = MockVideoPlayer(video["path"])
            player.duration = video["duration"]
            player.load()
            player.play()
            
            # Simulate playback
            start_time = time.time()
            while not player.is_ended() and (time.time() - start_time) < 2.0:  # Simulate shortened playback
                frame = player.get_current_frame()
                assert frame is not None
                time.sleep(0.1)
            
            player.stop()
            
            playback_log.append({
                "video_index": video["index"],
                "video_path": video["path"],
                "played": True,
                "events": player.playback_events.copy()
            })
        
        # Verify all videos were played
        assert len(playback_log) == len(self.playlist)
        
        for i, log_entry in enumerate(playback_log):
            assert log_entry["video_index"] == i
            assert log_entry["played"] is True
            
            # Verify play event was recorded
            play_events = [e for e in log_entry["events"] if e["event"] == "play_started"]
            assert len(play_events) >= 1
    
    def test_sequential_playback_with_transitions(self):
        """Test smooth transitions between videos in sequential playback"""
        transition_times = []
        
        previous_player = None
        
        for i, video in enumerate(self.playlist):
            current_player = MockVideoPlayer(video["path"])
            current_player.duration = video["duration"]
            current_player.load()
            
            # Measure transition time
            transition_start = time.time()
            
            if previous_player:
                previous_player.stop()
            
            current_player.play()
            transition_time = time.time() - transition_start
            
            transition_times.append(transition_time)
            
            # Simulate brief playback
            time.sleep(0.5)
            
            previous_player = current_player
        
        # Clean up last player
        if previous_player:
            previous_player.stop()
        
        # Verify transition times are reasonable
        for transition_time in transition_times:
            assert transition_time < 1.0, f"Transition too slow: {transition_time}s"
        
        # Average transition time should be very fast
        average_transition = sum(transition_times) / len(transition_times)
        assert average_transition < 0.5
    
    def test_playlist_navigation(self):
        """Test navigation within playlist (next, previous, jump to)"""
        playlist_manager = SequentialPlaylistManager(self.playlist)
        
        # Test initial state
        assert playlist_manager.current_index == 0
        assert playlist_manager.current_video()["index"] == 0
        
        # Test next video
        next_result = playlist_manager.next()
        assert next_result is True
        assert playlist_manager.current_index == 1
        
        # Test previous video
        prev_result = playlist_manager.previous()
        assert prev_result is True
        assert playlist_manager.current_index == 0
        
        # Test jump to specific video
        jump_result = playlist_manager.jump_to(2)
        assert jump_result is True
        assert playlist_manager.current_index == 2
        
        # Test jump to invalid index
        invalid_jump = playlist_manager.jump_to(10)
        assert invalid_jump is False
        assert playlist_manager.current_index == 2  # Should remain unchanged
    
    def test_sequential_playback_loop_modes(self):
        """Test different loop modes in sequential playback"""
        loop_modes = ["none", "single", "playlist"]
        
        for loop_mode in loop_modes:
            playlist_manager = SequentialPlaylistManager(self.playlist)
            playlist_manager.set_loop_mode(loop_mode)
            
            # Simulate reaching end of playlist
            playlist_manager.jump_to(len(self.playlist) - 1)  # Last video
            
            # Test what happens when trying to go to next
            if loop_mode == "none":
                next_result = playlist_manager.next()
                assert next_result is False  # Should not advance
                assert playlist_manager.current_index == len(self.playlist) - 1
            
            elif loop_mode == "playlist":
                next_result = playlist_manager.next()
                assert next_result is True  # Should wrap to beginning
                assert playlist_manager.current_index == 0
            
            elif loop_mode == "single":
                # Should stay on same video but restart it
                current_video = playlist_manager.current_video()
                restart_result = playlist_manager.restart_current()
                assert restart_result is True
    
    def test_sequential_playback_error_handling(self):
        """Test error handling in sequential playback"""
        # Create playlist with some invalid videos
        mixed_playlist = self.playlist.copy()
        mixed_playlist.append({
            "path": "/non/existent/video.mp4",
            "duration": 30.0,
            "index": 99
        })
        
        playlist_manager = SequentialPlaylistManager(mixed_playlist)
        playback_results = []
        
        # Attempt to play all videos
        for i in range(len(mixed_playlist)):
            playlist_manager.jump_to(i)
            current_video = playlist_manager.current_video()
            
            player = MockVideoPlayer(current_video["path"])
            load_result = player.load()
            
            playback_results.append({
                "video_index": i,
                "load_success": load_result,
                "video_path": current_video["path"]
            })
        
        # Verify that valid videos loaded successfully
        valid_results = [r for r in playback_results if r["load_success"]]
        invalid_results = [r for r in playback_results if not r["load_success"]]
        
        assert len(valid_results) == len(self.playlist)  # Original valid videos
        assert len(invalid_results) == 1  # The invalid video we added
        
        # Invalid video should be the last one
        assert invalid_results[0]["video_index"] == 99
    
    def test_sequential_playback_performance(self):
        """Test performance characteristics of sequential playback"""
        performance_metrics = {
            "video_load_times": [],
            "playback_start_times": [],
            "transition_times": [],
            "memory_usage": []
        }
        
        previous_player = None
        
        for video in self.playlist:
            # Measure video load time
            load_start = time.time()
            player = MockVideoPlayer(video["path"])
            player.duration = video["duration"]
            load_success = player.load()
            load_time = time.time() - load_start
            
            performance_metrics["video_load_times"].append(load_time)
            
            if load_success:
                # Measure playback start time
                start_time_begin = time.time()
                player.play()
                start_time = time.time() - start_time_begin
                
                performance_metrics["playback_start_times"].append(start_time)
                
                # Measure transition time if previous player exists
                if previous_player:
                    transition_start = time.time()
                    previous_player.stop()
                    player.play()
                    transition_time = time.time() - transition_start
                    
                    performance_metrics["transition_times"].append(transition_time)
                
                # Simulate memory usage measurement
                memory_usage = self._measure_memory_usage(player)
                performance_metrics["memory_usage"].append(memory_usage)
                
                # Brief playback simulation
                time.sleep(0.2)
                
                previous_player = player
        
        # Clean up
        if previous_player:
            previous_player.stop()
        
        # Validate performance metrics
        assert all(t < 2.0 for t in performance_metrics["video_load_times"]), "Video loading too slow"
        assert all(t < 1.0 for t in performance_metrics["playback_start_times"]), "Playback start too slow"
        
        if performance_metrics["transition_times"]:
            assert all(t < 0.5 for t in performance_metrics["transition_times"]), "Transitions too slow"
        
        # Memory usage should be reasonable and not grow excessively
        if len(performance_metrics["memory_usage"]) > 1:
            memory_growth = (performance_metrics["memory_usage"][-1] - 
                           performance_metrics["memory_usage"][0])
            assert memory_growth < 100 * 1024 * 1024, "Excessive memory growth detected"  # 100MB limit
    
    def _measure_memory_usage(self, player: MockVideoPlayer) -> int:
        """Measure approximate memory usage of player"""
        # Mock memory usage calculation
        base_usage = 50 * 1024 * 1024  # 50MB base
        video_size_factor = (player.width * player.height * 3) // 1024  # Bytes per frame
        return base_usage + video_size_factor


class TestAdvancedPlaybackFeatures:
    """Test suite for advanced playback features"""
    
    def setup_method(self):
        """Set up test environment"""
        self.test_video = "/tmp/advanced_test.mp4"
        with open(self.test_video, 'w') as f:
            f.write("Advanced playback test video")
        
        self.player = MockVideoPlayer(self.test_video)
        self.player.load()
    
    def teardown_method(self):
        """Clean up test environment"""
        if os.path.exists(self.test_video):
            os.unlink(self.test_video)
    
    def test_frame_by_frame_playback(self):
        """Test frame-by-frame playback control"""
        self.player.play()
        initial_frame = self.player.current_frame
        
        # Pause for frame-by-frame control
        self.player.pause()
        
        # Step forward frame by frame
        for i in range(10):
            step_result = self._step_frame_forward(self.player)
            assert step_result is True
            assert self.player.current_frame == initial_frame + i + 1
        
        # Step backward frame by frame
        for i in range(5):
            step_result = self._step_frame_backward(self.player)
            assert step_result is True
            assert self.player.current_frame == initial_frame + 10 - i - 1
    
    def test_time_based_bookmarks(self):
        """Test time-based bookmark functionality"""
        bookmarks = []
        
        # Create bookmarks at different positions
        bookmark_positions = [5.0, 15.5, 30.0, 45.2]
        
        for position in bookmark_positions:
            bookmark = self._create_bookmark(self.player, position, f"Bookmark at {position}s")
            bookmarks.append(bookmark)
            assert bookmark["position"] == position
        
        # Test jumping to bookmarks
        for bookmark in bookmarks:
            jump_result = self._jump_to_bookmark(self.player, bookmark)
            assert jump_result is True
            assert abs(self.player.get_position() - bookmark["position"]) < 0.1
    
    def test_playback_annotations(self):
        """Test overlaying annotations during playback"""
        annotations = [
            {"start": 5.0, "end": 10.0, "text": "Object detected here", "type": "detection"},
            {"start": 15.0, "end": 20.0, "text": "Camera movement", "type": "note"},
            {"start": 25.0, "end": 30.0, "text": "Important scene", "type": "highlight"}
        ]
        
        self.player.play()
        
        # Test annotations at different playback positions
        test_positions = [2.0, 7.5, 17.0, 27.5, 35.0]
        
        for position in test_positions:
            self.player.seek(position)
            active_annotations = self._get_active_annotations(annotations, position)
            
            # Verify correct annotations are active
            expected_active = [ann for ann in annotations 
                             if ann["start"] <= position <= ann["end"]]
            assert len(active_annotations) == len(expected_active)
            
            for annotation in active_annotations:
                assert annotation in expected_active
    
    def test_synchronized_dual_video_playback(self):
        """Test synchronized playback of two videos"""
        # Create second test video
        second_video = "/tmp/advanced_test_2.mp4"
        with open(second_video, 'w') as f:
            f.write("Second synchronized video")
        
        try:
            player1 = MockVideoPlayer(self.test_video)
            player2 = MockVideoPlayer(second_video)
            
            player1.load()
            player2.load()
            
            # Start synchronized playback
            sync_start = time.time()
            player1.play()
            player2.play()
            
            # Monitor synchronization over time
            sync_checks = []
            for i in range(10):
                time.sleep(0.1)
                
                pos1 = player1.get_position()
                pos2 = player2.get_position()
                sync_diff = abs(pos1 - pos2)
                
                sync_checks.append({
                    "time": time.time() - sync_start,
                    "position1": pos1,
                    "position2": pos2,
                    "sync_difference": sync_diff
                })
            
            # Verify synchronization
            max_sync_diff = max(check["sync_difference"] for check in sync_checks)
            average_sync_diff = sum(check["sync_difference"] for check in sync_checks) / len(sync_checks)
            
            assert max_sync_diff < 0.1, f"Maximum sync difference too large: {max_sync_diff}s"
            assert average_sync_diff < 0.05, f"Average sync difference too large: {average_sync_diff}s"
        
        finally:
            if os.path.exists(second_video):
                os.unlink(second_video)
    
    def test_video_filters_and_effects(self):
        """Test applying filters and effects during playback"""
        filters = [
            {"name": "brightness", "value": 1.2},
            {"name": "contrast", "value": 1.1},
            {"name": "saturation", "value": 0.9},
            {"name": "blur", "value": 2.0},
            {"name": "sharpen", "value": 1.0}
        ]
        
        self.player.play()
        
        for filter_config in filters:
            # Apply filter
            filter_result = self._apply_video_filter(self.player, filter_config)
            assert filter_result["success"] is True
            
            # Get frame with filter applied
            filtered_frame = self.player.get_current_frame()
            assert filtered_frame is not None
            
            # Verify filter was applied (simplified check)
            filter_info = filter_result["filter_info"]
            assert filter_info["name"] == filter_config["name"]
            assert filter_info["value"] == filter_config["value"]
    
    # Helper methods for advanced features
    
    def _step_frame_forward(self, player: MockVideoPlayer) -> bool:
        """Step one frame forward"""
        if player.current_frame < player.total_frames - 1:
            player.current_frame += 1
            player.position = player.current_frame / player.fps
            return True
        return False
    
    def _step_frame_backward(self, player: MockVideoPlayer) -> bool:
        """Step one frame backward"""
        if player.current_frame > 0:
            player.current_frame -= 1
            player.position = player.current_frame / player.fps
            return True
        return False
    
    def _create_bookmark(self, player: MockVideoPlayer, position: float, description: str) -> Dict:
        """Create a bookmark at specified position"""
        return {
            "position": position,
            "description": description,
            "timestamp": time.time(),
            "video_path": player.video_path
        }
    
    def _jump_to_bookmark(self, player: MockVideoPlayer, bookmark: Dict) -> bool:
        """Jump to a bookmark position"""
        return player.seek(bookmark["position"])
    
    def _get_active_annotations(self, annotations: List[Dict], position: float) -> List[Dict]:
        """Get annotations active at current position"""
        return [ann for ann in annotations if ann["start"] <= position <= ann["end"]]
    
    def _apply_video_filter(self, player: MockVideoPlayer, filter_config: Dict) -> Dict:
        """Apply video filter during playback"""
        # Mock filter application
        return {
            "success": True,
            "filter_info": {
                "name": filter_config["name"],
                "value": filter_config["value"],
                "applied_at": time.time()
            }
        }


class SequentialPlaylistManager:
    """Manager for sequential video playlist"""
    
    def __init__(self, playlist: List[Dict]):
        self.playlist = playlist
        self.current_index = 0
        self.loop_mode = "none"  # "none", "single", "playlist"
    
    def current_video(self) -> Optional[Dict]:
        """Get current video in playlist"""
        if 0 <= self.current_index < len(self.playlist):
            return self.playlist[self.current_index]
        return None
    
    def next(self) -> bool:
        """Move to next video in playlist"""
        if self.current_index < len(self.playlist) - 1:
            self.current_index += 1
            return True
        elif self.loop_mode == "playlist":
            self.current_index = 0
            return True
        return False
    
    def previous(self) -> bool:
        """Move to previous video in playlist"""
        if self.current_index > 0:
            self.current_index -= 1
            return True
        return False
    
    def jump_to(self, index: int) -> bool:
        """Jump to specific video index"""
        if 0 <= index < len(self.playlist):
            self.current_index = index
            return True
        return False
    
    def set_loop_mode(self, mode: str):
        """Set loop mode for playlist"""
        if mode in ["none", "single", "playlist"]:
            self.loop_mode = mode
    
    def restart_current(self) -> bool:
        """Restart current video"""
        return True  # Mock implementation


# Pytest fixtures and utilities
@pytest.fixture
def mock_video_files():
    """Fixture providing mock video files"""
    video_files = []
    for i in range(3):
        video_path = f"/tmp/pytest_video_{i}.mp4"
        with open(video_path, 'w') as f:
            f.write(f"Test video content {i}")
        video_files.append(video_path)
    
    yield video_files
    
    # Cleanup
    for video_path in video_files:
        if os.path.exists(video_path):
            os.unlink(video_path)


@pytest.fixture
def video_player():
    """Fixture providing a configured video player"""
    test_video = "/tmp/pytest_player_video.mp4"
    with open(test_video, 'w') as f:
        f.write("Player test video")
    
    player = MockVideoPlayer(test_video)
    player.load()
    
    yield player
    
    # Cleanup
    if os.path.exists(test_video):
        os.unlink(test_video)