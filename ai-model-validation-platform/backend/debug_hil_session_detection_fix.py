#!/usr/bin/env python3
"""
Debug script to fix the critical HIL detection duplication bug.

CRITICAL BUG IDENTIFIED:
- Each detection is being processed for ALL sessions (current + old)
- This causes database errors, transaction conflicts, and incorrect timing
- The actual timing synchronization is working correctly (0.931s vs 2.458s)

ROOT CAUSE:
- Detection handler is not properly filtering to only current session
- Video timing service is processing all sessions for each detection
- Database concurrency issues due to simultaneous writes for same detection
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging
from services.dedicated_labjack_monitor import DedicatedLabJackMonitor
from services.video_timing_service import VideoTimingService
from services.labjack_detection_service import LabJackDetectionService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_detection_bug():
    """Analyze the detection duplication bug from logs"""
    
    logger.info("🚨 CRITICAL BUG ANALYSIS: HIL Detection Duplication")
    logger.info("=" * 80)
    
    # From the logs, we can see the issue:
    logger.info("📊 BUG EVIDENCE FROM LOGS:")
    logger.info("1. Same detection timestamp (1758794843.119609) processed for MULTIPLE sessions:")
    logger.info("   - deaddf95-8c72-47b5-9da2-5d5587f8c771 (current) → 0.931s ✅ CORRECT")
    logger.info("   - 638e0b14-2d89-45a9-92da-891d6c63b70c (old) → 3143s → clamped to 5.041s")
    logger.info("   - a2c1f9cf-a2ef-45a3-b86e-c51253f35d78 (old) → 2133s → clamped to 5.041s")
    logger.info("   - 0b4b5a1b-7116-4773-842d-b8a3938ba794 (old) → 745s → clamped to 5.041s")
    logger.info("   - ca575668-b236-493d-bcbe-cb2b58327b88 (old) → 177s → clamped to 5.041s")
    logger.info("   - c11b1d5c-ae8a-4a88-b8de-4f15b2a1f1ef (old) → 34s → clamped to 5.041s")
    logger.info("")
    
    logger.info("🎯 GOOD NEWS:")
    logger.info("- Timing synchronization IS working correctly!")
    logger.info("- First detection at 0.931s (much better than previous 2.458s)")
    logger.info("- Subsequent detections: 0.990s, 1.061s, 1.133s, etc. ✅")
    logger.info("")
    
    logger.info("💥 CRITICAL PROBLEMS:")
    logger.info("1. Database Transaction Errors:")
    logger.info("   - 'cannot commit transaction - SQL statements in progress'")
    logger.info("   - 'cannot start a transaction within a transaction'")
    logger.info("   - 'UNIQUE constraint failed: detection_events.id'")
    logger.info("   - 'bad parameter or other API misuse'")
    logger.info("")
    logger.info("2. Multiple Session Processing:")
    logger.info("   - Each detection creates 6+ database entries")
    logger.info("   - Concurrent writes cause transaction conflicts")
    logger.info("   - Old sessions should NOT receive new detections")
    logger.info("")
    
    logger.info("🔧 REQUIRED FIXES:")
    logger.info("1. Filter detections to ONLY current/active session")
    logger.info("2. Add session validation before processing")
    logger.info("3. Fix database transaction concurrency")
    logger.info("4. Clean up old session data")
    logger.info("")

def show_fix_strategy():
    """Show the fix strategy"""
    
    logger.info("🛠️ FIX STRATEGY:")
    logger.info("=" * 80)
    
    logger.info("📍 PRIMARY FIX - Session Filtering:")
    logger.info("   Location: dedicated_labjack_monitor.py:307")
    logger.info("   Add: session_id validation before processing")
    logger.info("   Ensure: Only active sessions receive detections")
    logger.info("")
    
    logger.info("📍 SECONDARY FIX - Database Transactions:")
    logger.info("   Location: dedicated_labjack_monitor.py:417+")
    logger.info("   Fix: Proper database session management")
    logger.info("   Add: Retry logic for transaction conflicts")
    logger.info("")
    
    logger.info("📍 TERTIARY FIX - Session Cleanup:")
    logger.info("   Location: video_timing_service.py")
    logger.info("   Add: Old session cleanup mechanism")
    logger.info("   Remove: Stale timing data")

if __name__ == "__main__":
    analyze_detection_bug()
    show_fix_strategy()