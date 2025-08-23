"""
🎥 VIDEO PROCESSING EXTREME EDGE CASE TESTING
Tests all extreme video processing scenarios that could break the system
"""

import pytest
import asyncio
import os
import cv2
import numpy as np
import tempfile
import time
from pathlib import Path
import requests
from typing import Dict, Any, List

class VideoProcessingEdgeCases:
    """Extreme video processing edge case tests"""
    
    def __init__(self, backend_url: str = "http://localhost:8000"):
        self.backend_url = backend_url
        self.test_results = []
        
    async def run_all_video_edge_cases(self):
        """Execute all video processing edge case tests"""
        print("🎥 Starting Video Processing Edge Case Tests")
        print("="*60)
        
        # 1. Video Duration Edge Cases
        await self.test_extreme_video_durations()
        
        # 2. Video Resolution Edge Cases
        await self.test_extreme_resolutions()
        
        # 3. Video Format Edge Cases
        await self.test_unusual_formats()
        
        # 4. Frame Rate Edge Cases
        await self.test_extreme_frame_rates()
        
        # 5. Corrupted Video Tests
        await self.test_corrupted_videos()
        
        # 6. Memory Stress Tests
        await self.test_memory_intensive_videos()
        
        # Generate summary
        await self.generate_video_test_summary()
        
    async def test_extreme_video_durations(self):
        """Test videos with extreme durations"""
        print("⏱️  Testing Extreme Video Durations...")
        
        duration_tests = [
            {"name": "Ultra Short", "duration": 0.1, "fps": 30},  # 3 frames
            {"name": "Extremely Short", "duration": 0.033, "fps": 30},  # 1 frame
            {"name": "Long Video", "duration": 120, "fps": 30},  # 2 minutes
            {"name": "Very Long Video", "duration": 600, "fps": 30}  # 10 minutes
        ]
        
        for test in duration_tests:
            await self.test_single_duration(test)
            
    async def test_single_duration(self, test_config: Dict[str, Any]):
        """Test single video duration scenario"""
        start_time = time.time()
        
        try:
            # Create test video with specific duration
            video_path = await self.create_duration_test_video(
                test_config["duration"], 
                test_config["fps"]
            )
            
            # Upload and process
            upload_result = await self.upload_and_process_video(video_path, test_config["name"])
            
            processing_time = time.time() - start_time
            
            # Determine result
            if upload_result["success"]:
                status = "✅ PASS"
                if processing_time > 60:  # More than 1 minute
                    status = "⚠️ PARTIAL (Slow)"
            else:
                status = "❌ FAIL"
                
            await self.log_result(
                "Video Duration Edge Cases",
                f"{test_config['name']} ({test_config['duration']}s)",
                status,
                {
                    "duration": test_config["duration"],
                    "fps": test_config["fps"],
                    "upload_success": upload_result["success"],
                    "processing_time": processing_time,
                    "error": upload_result.get("error")
                }
            )
            
            # Cleanup
            os.unlink(video_path)
            
        except Exception as e:
            await self.log_result(
                "Video Duration Edge Cases",
                f"{test_config['name']}",
                "❌ FAIL",
                {"error": str(e), "duration": test_config["duration"]}
            )
            
    async def create_duration_test_video(self, duration: float, fps: int) -> str:
        """Create test video with specific duration"""
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, f"duration_test_{duration}s.mp4")
        
        width, height = 640, 480
        total_frames = int(duration * fps)
        
        # Handle edge case of less than 1 frame
        if total_frames == 0:
            total_frames = 1
            
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
        
        for frame_num in range(total_frames):
            # Create frame with visual content
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Add moving rectangle
            x_pos = (frame_num * 5) % (width - 100)
            cv2.rectangle(frame, (x_pos, 100), (x_pos + 100, 200), (0, 255, 0), -1)
            
            # Add frame counter
            cv2.putText(frame, f"Frame {frame_num}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Add timestamp
            timestamp = frame_num / fps
            cv2.putText(frame, f"Time: {timestamp:.3f}s", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            out.write(frame)
            
        out.release()
        return video_path
        
    async def test_extreme_resolutions(self):
        """Test videos with extreme resolutions"""
        print("📺 Testing Extreme Resolutions...")
        
        resolution_tests = [
            {"name": "Tiny Resolution", "width": 160, "height": 120},  # QQVGA
            {"name": "Square Tiny", "width": 64, "height": 64},
            {"name": "Ultra Wide", "width": 3840, "height": 1080},  # 21:9
            {"name": "Vertical Video", "width": 1080, "height": 1920},  # 9:16
            {"name": "Extreme Aspect", "width": 1920, "height": 480},  # 4:1
            {"name": "4K Resolution", "width": 3840, "height": 2160},
            {"name": "8K Resolution", "width": 7680, "height": 4320}
        ]
        
        for test in resolution_tests:
            await self.test_single_resolution(test)
            
    async def test_single_resolution(self, test_config: Dict[str, Any]):
        """Test single resolution scenario"""
        start_time = time.time()
        
        try:
            # Create test video with specific resolution
            video_path = await self.create_resolution_test_video(
                test_config["width"], 
                test_config["height"]
            )
            
            file_size = os.path.getsize(video_path) / (1024 * 1024)  # MB
            
            # Upload and process
            upload_result = await self.upload_and_process_video(video_path, test_config["name"])
            
            processing_time = time.time() - start_time
            
            # Determine result based on success and performance
            if upload_result["success"]:
                if file_size > 50 and processing_time < 30:  # Large file processed quickly
                    status = "✅ PASS"
                elif processing_time > 120:  # Very slow processing
                    status = "⚠️ PARTIAL (Very Slow)"
                else:
                    status = "✅ PASS"
            else:
                # Check if failure is expected for extreme resolutions
                if test_config["width"] * test_config["height"] > 33177600:  # 8K pixels
                    status = "⚠️ PARTIAL (Expected Limitation)"
                else:
                    status = "❌ FAIL"
                    
            await self.log_result(
                "Video Resolution Edge Cases",
                f"{test_config['name']} ({test_config['width']}x{test_config['height']})",
                status,
                {
                    "resolution": f"{test_config['width']}x{test_config['height']}",
                    "file_size_mb": file_size,
                    "upload_success": upload_result["success"],
                    "processing_time": processing_time,
                    "pixels": test_config["width"] * test_config["height"],
                    "aspect_ratio": test_config["width"] / test_config["height"]
                }
            )
            
            # Cleanup
            os.unlink(video_path)
            
        except Exception as e:
            await self.log_result(
                "Video Resolution Edge Cases",
                f"{test_config['name']}",
                "❌ FAIL",
                {"error": str(e), "resolution": f"{test_config['width']}x{test_config['height']}"}
            )
            
    async def create_resolution_test_video(self, width: int, height: int) -> str:
        """Create test video with specific resolution"""
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, f"resolution_test_{width}x{height}.mp4")
        
        fps = 30
        duration = 3  # seconds
        total_frames = fps * duration
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
        
        for frame_num in range(total_frames):
            # Create frame with resolution-appropriate content
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Add gradient background
            for y in range(height):
                for x in range(width):
                    frame[y, x] = [
                        int(255 * x / width),  # Red gradient
                        int(255 * y / height),  # Green gradient
                        128  # Blue constant
                    ]
            
            # Add moving elements scaled to resolution
            circle_radius = min(width, height) // 20
            circle_x = int((frame_num % 60) * width / 60)
            circle_y = height // 2
            
            cv2.circle(frame, (circle_x, circle_y), circle_radius, (255, 255, 255), -1)
            
            # Add text if resolution allows
            if width > 200 and height > 100:
                font_scale = min(width, height) / 1000
                cv2.putText(frame, f"{width}x{height}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 255), 2)
            
            out.write(frame)
            
        out.release()
        return video_path
        
    async def test_extreme_frame_rates(self):
        """Test videos with extreme frame rates"""
        print("🎞️  Testing Extreme Frame Rates...")
        
        framerate_tests = [
            {"name": "Very Low FPS", "fps": 1},
            {"name": "Ultra Low FPS", "fps": 0.5},  # 1 frame every 2 seconds
            {"name": "High FPS", "fps": 120},
            {"name": "Very High FPS", "fps": 240},
            {"name": "Extreme High FPS", "fps": 480}
        ]
        
        for test in framerate_tests:
            await self.test_single_framerate(test)
            
    async def test_single_framerate(self, test_config: Dict[str, Any]):
        """Test single frame rate scenario"""
        start_time = time.time()
        
        try:
            # Create test video with specific frame rate
            video_path = await self.create_framerate_test_video(test_config["fps"])
            
            file_size = os.path.getsize(video_path) / (1024 * 1024)  # MB
            
            # Upload and process
            upload_result = await self.upload_and_process_video(video_path, test_config["name"])
            
            processing_time = time.time() - start_time
            
            # Determine result
            if upload_result["success"]:
                status = "✅ PASS"
                if processing_time > 60:
                    status = "⚠️ PARTIAL (Slow Processing)"
            else:
                # Very low frame rates might be rejected
                if test_config["fps"] < 1:
                    status = "⚠️ PARTIAL (Expected Limitation)"
                else:
                    status = "❌ FAIL"
                    
            await self.log_result(
                "Video Frame Rate Edge Cases",
                f"{test_config['name']} ({test_config['fps']} FPS)",
                status,
                {
                    "fps": test_config["fps"],
                    "file_size_mb": file_size,
                    "upload_success": upload_result["success"],
                    "processing_time": processing_time,
                    "error": upload_result.get("error")
                }
            )
            
            # Cleanup
            os.unlink(video_path)
            
        except Exception as e:
            await self.log_result(
                "Video Frame Rate Edge Cases",
                f"{test_config['name']}",
                "❌ FAIL",
                {"error": str(e), "fps": test_config["fps"]}
            )
            
    async def create_framerate_test_video(self, fps: float) -> str:
        """Create test video with specific frame rate"""
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, f"framerate_test_{fps}fps.mp4")
        
        width, height = 640, 480
        duration = 5  # seconds
        
        # Handle fractional frame rates
        if fps < 1:
            total_frames = int(duration * fps) or 1
            actual_fps = 1  # Write at 1 FPS but fewer frames for effect
        else:
            total_frames = int(duration * fps)
            actual_fps = fps
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(video_path, fourcc, actual_fps, (width, height))
        
        for frame_num in range(total_frames):
            # Create frame with frame rate visualization
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Background color changes with frame number
            bg_intensity = int(127 + 127 * np.sin(frame_num * 0.1))
            frame[:] = [bg_intensity, 50, 100]
            
            # Large frame counter
            cv2.putText(frame, f"Frame {frame_num}", (width//4, height//2), 
                       cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
            
            # FPS indicator
            cv2.putText(frame, f"FPS: {fps}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            
            # Timestamp
            timestamp = frame_num / fps if fps > 0 else frame_num * 2
            cv2.putText(frame, f"Time: {timestamp:.2f}s", (10, height - 20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            
            out.write(frame)
            
        out.release()
        return video_path
        
    async def test_corrupted_videos(self):
        """Test various types of corrupted video files"""
        print("💥 Testing Corrupted Videos...")
        
        corruption_tests = [
            {"name": "Missing Header", "corruption": "header"},
            {"name": "Truncated File", "corruption": "truncated"},
            {"name": "Random Corruption", "corruption": "random"},
            {"name": "Invalid Metadata", "corruption": "metadata"},
            {"name": "Mixed Formats", "corruption": "mixed"}
        ]
        
        for test in corruption_tests:
            await self.test_single_corruption(test)
            
    async def test_single_corruption(self, test_config: Dict[str, Any]):
        """Test single corruption scenario"""
        start_time = time.time()
        
        try:
            # Create corrupted video based on type
            video_path = await self.create_corrupted_video(test_config["corruption"])
            
            # Upload and process
            upload_result = await self.upload_and_process_video(video_path, test_config["name"])
            
            processing_time = time.time() - start_time
            
            # Corrupted videos should be handled gracefully
            if upload_result["success"]:
                # If accepted, it should process without crashing
                status = "✅ PASS (Accepted and Processed)"
            elif upload_result.get("status_code") in [400, 415, 422]:
                # Proper rejection with appropriate error code
                status = "✅ PASS (Properly Rejected)"
            else:
                # Unexpected failure or server error
                status = "❌ FAIL (Improper Error Handling)"
                
            await self.log_result(
                "Corrupted Video Handling",
                f"{test_config['name']} Corruption",
                status,
                {
                    "corruption_type": test_config["corruption"],
                    "upload_success": upload_result["success"],
                    "status_code": upload_result.get("status_code"),
                    "processing_time": processing_time,
                    "error_message": upload_result.get("error", "")[:100]
                }
            )
            
            # Cleanup
            os.unlink(video_path)
            
        except Exception as e:
            await self.log_result(
                "Corrupted Video Handling",
                f"{test_config['name']}",
                "❌ FAIL",
                {"error": str(e), "corruption_type": test_config["corruption"]}
            )
            
    async def create_corrupted_video(self, corruption_type: str) -> str:
        """Create corrupted video file of specified type"""
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, f"corrupted_{corruption_type}.mp4")
        
        if corruption_type == "header":
            # Missing/invalid header
            with open(video_path, 'wb') as f:
                f.write(b'INVALID_HEADER')
                f.write(os.urandom(1000))
                
        elif corruption_type == "truncated":
            # Create valid start then truncate
            valid_video = await self.create_duration_test_video(3.0, 30)
            with open(valid_video, 'rb') as src:
                data = src.read()
            with open(video_path, 'wb') as dst:
                dst.write(data[:len(data)//2])  # Write only half
            os.unlink(valid_video)
            
        elif corruption_type == "random":
            # Valid header then random corruption
            with open(video_path, 'wb') as f:
                f.write(b'\x00\x00\x00\x20ftypmp41')  # Valid MP4 header
                f.write(os.urandom(10000))  # Random data
                
        elif corruption_type == "metadata":
            # Corrupted metadata section
            valid_video = await self.create_duration_test_video(3.0, 30)
            with open(valid_video, 'rb') as src:
                data = bytearray(src.read())
            # Corrupt metadata (assuming it's near the beginning)
            for i in range(100, 200):
                if i < len(data):
                    data[i] = 0xFF
            with open(video_path, 'wb') as dst:
                dst.write(data)
            os.unlink(valid_video)
            
        elif corruption_type == "mixed":
            # Mix of different format data
            with open(video_path, 'wb') as f:
                f.write(b'\x00\x00\x00\x20ftypmp41')  # MP4 header
                f.write(b'RIFF')  # AVI header
                f.write(b'\xFF\xD8\xFF\xE0')  # JPEG header
                f.write(os.urandom(5000))
                
        return video_path
        
    async def upload_and_process_video(self, video_path: str, test_name: str) -> Dict[str, Any]:
        """Upload video and check processing result"""
        try:
            with open(video_path, 'rb') as video_file:
                files = {'file': (f"{test_name}.mp4", video_file)}
                response = requests.post(
                    f"{self.backend_url}/api/videos",
                    files=files,
                    timeout=120
                )
                
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else None,
                "error": response.text if response.status_code != 200 else None
            }
            
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Upload timeout", "status_code": 408}
        except Exception as e:
            return {"success": False, "error": str(e), "status_code": None}
            
    async def log_result(self, category: str, test_case: str, status: str, details: Dict[str, Any]):
        """Log test result with detailed information"""
        result = {
            "category": category,
            "test_case": test_case,
            "status": status,
            "details": details,
            "timestamp": time.time()
        }
        
        self.test_results.append(result)
        print(f"  {status} {test_case}")
        if status.startswith("❌"):
            print(f"    Error: {details.get('error', 'Unknown error')}")
        elif "processing_time" in details:
            print(f"    Processing Time: {details['processing_time']:.2f}s")
            
    async def generate_video_test_summary(self):
        """Generate summary of video processing tests"""
        print("\n" + "="*60)
        print("📊 VIDEO PROCESSING EDGE CASE TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["status"].startswith("✅")])
        partial_tests = len([r for r in self.test_results if r["status"].startswith("⚠️")])
        failed_tests = len([r for r in self.test_results if r["status"].startswith("❌")])
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} (✅)")
        print(f"Partial: {partial_tests} (⚠️)")
        print(f"Failed: {failed_tests} (❌)")
        print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        # Category breakdown
        categories = {}
        for result in self.test_results:
            category = result["category"]
            if category not in categories:
                categories[category] = {"pass": 0, "partial": 0, "fail": 0}
                
            if result["status"].startswith("✅"):
                categories[category]["pass"] += 1
            elif result["status"].startswith("⚠️"):
                categories[category]["partial"] += 1
            else:
                categories[category]["fail"] += 1
                
        print("\nCategory Breakdown:")
        for category, results in categories.items():
            total_cat = sum(results.values())
            success_rate = (results["pass"] / total_cat * 100) if total_cat > 0 else 0
            print(f"  {category}: {success_rate:.1f}% success ({results['pass']}/{total_cat})")
            
        # Performance analysis
        processing_times = [r["details"].get("processing_time", 0) 
                          for r in self.test_results if "processing_time" in r["details"]]
        
        if processing_times:
            avg_time = sum(processing_times) / len(processing_times)
            max_time = max(processing_times)
            print(f"\nPerformance Metrics:")
            print(f"  Average Processing Time: {avg_time:.2f}s")
            print(f"  Maximum Processing Time: {max_time:.2f}s")
            print(f"  Slow Tests (>30s): {len([t for t in processing_times if t > 30])}")
            
        # Critical failures
        critical_failures = [r for r in self.test_results 
                           if r["status"].startswith("❌") and "corruption" not in r["category"].lower()]
                           
        if critical_failures:
            print(f"\n🚨 CRITICAL FAILURES: {len(critical_failures)}")
            for failure in critical_failures:
                print(f"  - {failure['test_case']}: {failure['details'].get('error', 'Unknown')}")
                
        print("="*60)

# Main execution
async def main():
    """Execute video processing edge case tests"""
    tester = VideoProcessingEdgeCases()
    await tester.run_all_video_edge_cases()

if __name__ == "__main__":
    asyncio.run(main())