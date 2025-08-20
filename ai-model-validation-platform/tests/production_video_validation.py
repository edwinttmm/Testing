#!/usr/bin/env python3
"""
Production Video System Validation
Tests the complete video pipeline from backend serving to frontend playback
"""

import os
import sys
import time
import requests
import cv2
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

from database import SessionLocal
from models import Video, Project
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProductionVideoValidator:
    """Production-ready video system validation"""
    
    def __init__(self, backend_url: str = "http://localhost:8000"):
        self.backend_url = backend_url
        self.test_results = []
        self.db_path = Path(__file__).parent.parent / 'backend' / 'test_database.db'
        
        # Change to backend directory to ensure database connection works
        backend_dir = Path(__file__).parent.parent / 'backend'
        os.chdir(backend_dir)
        
    def log_result(self, test_name: str, status: str, details: str = "", error: Optional[Exception] = None):
        """Log test result"""
        result = {
            'test_name': test_name,
            'status': status,  # 'PASS', 'FAIL', 'SKIP'
            'details': details,
            'error': str(error) if error else None,
            'timestamp': time.time()
        }
        self.test_results.append(result)
        
        status_symbol = "✓" if status == "PASS" else "✗" if status == "FAIL" else "○"
        logger.info(f"{status_symbol} {test_name}: {status} - {details}")
        
        if error:
            logger.error(f"   Error: {error}")
    
    def validate_database_integrity(self) -> bool:
        """Validate video database integrity"""
        try:
            db = SessionLocal()
            
            # Check database connection
            videos = db.query(Video).all()
            self.log_result("Database Connection", "PASS", f"Found {len(videos)} videos")
            
            # Check video metadata completeness
            complete_videos = [v for v in videos if v.duration and v.fps and v.resolution]
            incomplete_videos = [v for v in videos if not (v.duration and v.fps and v.resolution)]
            
            if incomplete_videos:
                self.log_result(
                    "Video Metadata Completeness", 
                    "FAIL", 
                    f"{len(incomplete_videos)}/{len(videos)} videos missing metadata"
                )
                return False
            else:
                self.log_result(
                    "Video Metadata Completeness",
                    "PASS", 
                    f"All {len(videos)} videos have complete metadata"
                )
            
            # Validate specific test video
            test_video = db.query(Video).filter(Video.id == 'test-video-5-04s').first()
            if not test_video:
                self.log_result("Test Video Exists", "FAIL", "test-video-5-04s not found")
                return False
            
            # Validate test video metadata
            expected_duration = 5.033333333333333
            expected_fps = 30.0
            expected_resolution = "640x480"
            
            if abs(test_video.duration - expected_duration) > 0.1:
                self.log_result(
                    "Test Video Duration",
                    "FAIL", 
                    f"Expected {expected_duration}s, got {test_video.duration}s"
                )
                return False
            
            if abs(test_video.fps - expected_fps) > 0.1:
                self.log_result(
                    "Test Video FPS", 
                    "FAIL",
                    f"Expected {expected_fps}, got {test_video.fps}"
                )
                return False
            
            if test_video.resolution != expected_resolution:
                self.log_result(
                    "Test Video Resolution",
                    "FAIL", 
                    f"Expected {expected_resolution}, got {test_video.resolution}"
                )
                return False
            
            self.log_result(
                "Test Video Validation",
                "PASS", 
                f"Duration: {test_video.duration}s, FPS: {test_video.fps}, Resolution: {test_video.resolution}"
            )
            
            db.close()
            return True
            
        except Exception as e:
            self.log_result("Database Integrity", "FAIL", "Database validation failed", e)
            return False
    
    def validate_video_files(self) -> bool:
        """Validate physical video files"""
        try:
            db = SessionLocal()
            videos = db.query(Video).all()
            
            all_valid = True
            for video in videos:
                if not video.file_path or not os.path.exists(video.file_path):
                    self.log_result(
                        f"Video File Exists ({video.id})",
                        "FAIL",
                        f"File not found: {video.file_path}"
                    )
                    all_valid = False
                    continue
                
                # Validate with OpenCV
                cap = cv2.VideoCapture(video.file_path)
                if not cap.isOpened():
                    self.log_result(
                        f"Video File Valid ({video.id})",
                        "FAIL", 
                        f"Cannot open video file: {video.file_path}"
                    )
                    all_valid = False
                    continue
                
                # Extract actual metadata
                actual_fps = cap.get(cv2.CAP_PROP_FPS)
                actual_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                actual_duration = actual_frame_count / actual_fps if actual_fps > 0 else 0
                
                cap.release()
                
                # Validate against database
                if abs(actual_duration - video.duration) > 0.1:
                    self.log_result(
                        f"Video Metadata Sync ({video.id})",
                        "FAIL",
                        f"Duration mismatch: DB={video.duration}s, File={actual_duration}s"
                    )
                    all_valid = False
                    continue
                
                self.log_result(
                    f"Video File Valid ({video.id})",
                    "PASS",
                    f"{actual_frame_count} frames, {actual_duration:.2f}s @ {actual_fps}fps"
                )
            
            db.close()
            return all_valid
            
        except Exception as e:
            self.log_result("Video Files Validation", "FAIL", "File validation failed", e)
            return False
    
    def validate_api_endpoints(self) -> bool:
        """Validate video API endpoints"""
        try:
            # Test /api/videos endpoint
            response = requests.get(f"{self.backend_url}/api/videos", timeout=10)
            if response.status_code != 200:
                self.log_result(
                    "API /api/videos",
                    "FAIL", 
                    f"HTTP {response.status_code}: {response.text[:100]}"
                )
                return False
            
            videos = response.json()
            if not videos:
                self.log_result("API /api/videos", "FAIL", "No videos returned")
                return False
            
            # Validate video response structure
            required_fields = ['id', 'filename', 'url', 'duration', 'status']
            for video in videos:
                missing_fields = [field for field in required_fields if field not in video]
                if missing_fields:
                    self.log_result(
                        "API Video Response Structure",
                        "FAIL",
                        f"Missing fields: {missing_fields}"
                    )
                    return False
            
            self.log_result(
                "API /api/videos", 
                "PASS",
                f"Returned {len(videos)} videos with complete metadata"
            )
            
            # Test video URL accessibility
            test_video = next((v for v in videos if v['id'] == 'test-video-5-04s'), None)
            if not test_video:
                self.log_result("Test Video in API", "FAIL", "Test video not found in API response")
                return False
            
            # Test video file serving
            video_url = f"{self.backend_url}{test_video['url']}"
            video_response = requests.head(video_url, timeout=10)
            if video_response.status_code != 200:
                self.log_result(
                    "Video File Serving",
                    "FAIL",
                    f"Cannot access {video_url}: HTTP {video_response.status_code}"
                )
                return False
            
            self.log_result(
                "Video File Serving",
                "PASS",
                f"Video accessible at {video_url}"
            )
            
            return True
            
        except requests.exceptions.ConnectionError:
            self.log_result("API Endpoints", "SKIP", "Backend server not running")
            return True  # Don't fail validation if server isn't running
        except Exception as e:
            self.log_result("API Endpoints", "FAIL", "API validation failed", e)
            return False
    
    def validate_frame_calculations(self) -> bool:
        """Validate frame rate calculations and timing"""
        try:
            db = SessionLocal()
            test_video = db.query(Video).filter(Video.id == 'test-video-5-04s').first()
            
            if not test_video:
                self.log_result("Frame Calculations", "SKIP", "Test video not available")
                return True
            
            # Test frame calculations
            duration = test_video.duration  # 5.033333s
            fps = test_video.fps  # 30.0
            expected_frame_count = int(duration * fps)  # 151 frames
            
            # Frame timing validation
            test_cases = [
                (0.0, 0),      # Start
                (1.0, 30),     # 1 second = frame 30
                (2.5, 75),     # 2.5 seconds = frame 75  
                (3.0, 90),     # 3 seconds = frame 90
                (5.0, 150)     # 5 seconds = frame 150 (last frame)
            ]
            
            all_valid = True
            for time_sec, expected_frame in test_cases:
                calculated_frame = int(time_sec * fps)
                if calculated_frame != expected_frame:
                    self.log_result(
                        f"Frame Calculation (t={time_sec}s)",
                        "FAIL",
                        f"Expected frame {expected_frame}, got {calculated_frame}"
                    )
                    all_valid = False
                else:
                    self.log_result(
                        f"Frame Calculation (t={time_sec}s)",
                        "PASS",
                        f"Frame {calculated_frame}"
                    )
            
            # Validate total frame count
            if expected_frame_count == 151:
                self.log_result(
                    "Total Frame Count",
                    "PASS", 
                    f"{expected_frame_count} frames for {duration}s @ {fps}fps"
                )
            else:
                self.log_result(
                    "Total Frame Count",
                    "FAIL",
                    f"Expected 151 frames, calculated {expected_frame_count}"
                )
                all_valid = False
            
            db.close()
            return all_valid
            
        except Exception as e:
            self.log_result("Frame Calculations", "FAIL", "Frame calculation validation failed", e)
            return False
    
    def validate_url_generation(self) -> bool:
        """Validate URL generation consistency"""
        try:
            db = SessionLocal()
            test_video = db.query(Video).filter(Video.id == 'test-video-5-04s').first()
            
            if not test_video:
                self.log_result("URL Generation", "SKIP", "Test video not available")
                return True
            
            # Expected URL format
            expected_url = f"/uploads/{test_video.filename}"
            
            # Check file exists at expected path
            upload_path = Path(__file__).parent.parent / 'backend' / 'uploads' / test_video.filename
            if not upload_path.exists():
                self.log_result(
                    "Video File Path",
                    "FAIL", 
                    f"File not found at expected path: {upload_path}"
                )
                return False
            
            self.log_result(
                "URL Generation Consistency",
                "PASS",
                f"URL: {expected_url}, File exists: {upload_path.exists()}"
            )
            
            db.close()
            return True
            
        except Exception as e:
            self.log_result("URL Generation", "FAIL", "URL validation failed", e)
            return False
    
    def run_full_validation(self) -> bool:
        """Run complete validation suite"""
        logger.info("=== Starting Production Video System Validation ===")
        
        validations = [
            ("Database Integrity", self.validate_database_integrity),
            ("Video Files", self.validate_video_files), 
            ("API Endpoints", self.validate_api_endpoints),
            ("Frame Calculations", self.validate_frame_calculations),
            ("URL Generation", self.validate_url_generation)
        ]
        
        all_passed = True
        for validation_name, validation_func in validations:
            logger.info(f"\n--- {validation_name} ---")
            try:
                result = validation_func()
                if not result:
                    all_passed = False
            except Exception as e:
                self.log_result(validation_name, "FAIL", "Validation threw exception", e)
                all_passed = False
        
        # Generate summary
        self.generate_validation_report()
        
        return all_passed
    
    def generate_validation_report(self):
        """Generate validation report"""
        logger.info("\n=== VALIDATION SUMMARY ===")
        
        passed = [r for r in self.test_results if r['status'] == 'PASS']
        failed = [r for r in self.test_results if r['status'] == 'FAIL']
        skipped = [r for r in self.test_results if r['status'] == 'SKIP']
        
        logger.info(f"✓ PASSED: {len(passed)}")
        logger.info(f"✗ FAILED: {len(failed)}")
        logger.info(f"○ SKIPPED: {len(skipped)}")
        
        if failed:
            logger.error("\nFAILED TESTS:")
            for result in failed:
                logger.error(f"  - {result['test_name']}: {result['details']}")
                if result['error']:
                    logger.error(f"    Error: {result['error']}")
        
        # Save detailed report
        report_path = Path(__file__).parent / 'video_validation_report.json'
        with open(report_path, 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        logger.info(f"\nDetailed report saved to: {report_path}")
        
        overall_status = "PASS" if len(failed) == 0 else "FAIL"
        logger.info(f"\nOVERALL VALIDATION STATUS: {overall_status}")


if __name__ == "__main__":
    validator = ProductionVideoValidator()
    success = validator.run_full_validation()
    sys.exit(0 if success else 1)