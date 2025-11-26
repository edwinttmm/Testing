#!/usr/bin/env python3
"""
Frame Skip Configuration Verifier

This script verifies the current frame skip configuration and provides
recommendations for HIL validation use cases.

Usage:
    python scripts/verify_frame_skip_config.py
"""

import os
import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def check_environment_variable():
    """Check DETECTION_FRAME_SKIP environment variable"""
    frame_skip_env = os.getenv('DETECTION_FRAME_SKIP')

    if frame_skip_env is None:
        return {
            "status": "warning",
            "value": None,
            "message": "DETECTION_FRAME_SKIP not set - using default (5)"
        }
    else:
        value = int(frame_skip_env)
        if value == 1:
            return {
                "status": "ok",
                "value": value,
                "message": f"Frame skip set to {value} (processing ALL frames) ✅"
            }
        else:
            return {
                "status": "warning",
                "value": value,
                "message": f"Frame skip set to {value} (processing 1 in {value} frames) ⚠️"
            }

def check_timeout_config():
    """Check timeout_config.py frame_skip_ratio"""
    try:
        from services.timeout_config import timeout_config

        frame_skip = timeout_config.frame_skip_ratio

        if frame_skip == 1:
            return {
                "status": "ok",
                "value": frame_skip,
                "message": f"TimeoutConfig frame_skip_ratio: {frame_skip} (ALL frames) ✅"
            }
        else:
            return {
                "status": "warning",
                "value": frame_skip,
                "message": f"TimeoutConfig frame_skip_ratio: {frame_skip} (1 in {frame_skip} frames) ⚠️"
            }
    except Exception as e:
        return {
            "status": "error",
            "value": None,
            "message": f"Cannot load TimeoutConfig: {e}"
        }

def check_optimized_pipeline_default():
    """Check OptimizedDetectionPipeline default frame_skip"""
    try:
        # Read the file to check default value
        file_path = Path(__file__).parent.parent / "services" / "optimized_detection_service.py"

        if not file_path.exists():
            return {
                "status": "error",
                "value": None,
                "message": "OptimizedDetectionPipeline file not found"
            }

        content = file_path.read_text()

        # Look for frame_skip default
        if "frame_skip: int = 5" in content:
            return {
                "status": "warning",
                "value": 5,
                "message": "OptimizedDetectionPipeline default frame_skip: 5 ⚠️"
            }
        elif "frame_skip: int = 1" in content:
            return {
                "status": "ok",
                "value": 1,
                "message": "OptimizedDetectionPipeline default frame_skip: 1 ✅"
            }
        else:
            return {
                "status": "unknown",
                "value": None,
                "message": "Cannot determine OptimizedDetectionPipeline default"
            }
    except Exception as e:
        return {
            "status": "error",
            "value": None,
            "message": f"Error checking pipeline: {e}"
        }

def calculate_detection_rate(frame_skip: int) -> dict:
    """Calculate expected detection rate based on frame skip"""
    if frame_skip == 1:
        return {
            "processing_rate": 100.0,
            "frames_processed_per_100": 100,
            "frames_skipped_per_100": 0,
            "use_case_recommendation": "✅ SUITABLE for HIL validation"
        }
    else:
        rate = (1.0 / frame_skip) * 100
        return {
            "processing_rate": rate,
            "frames_processed_per_100": int(100 / frame_skip),
            "frames_skipped_per_100": 100 - int(100 / frame_skip),
            "use_case_recommendation": f"⚠️ NOT RECOMMENDED for HIL validation (missing {100-rate:.1f}% of frames)"
        }

def main():
    print("=" * 80)
    print("FRAME SKIP CONFIGURATION VERIFICATION")
    print("=" * 80)
    print()

    # Check environment variable
    print("1. Environment Variable Check:")
    env_result = check_environment_variable()
    print(f"   Status: {env_result['status'].upper()}")
    print(f"   {env_result['message']}")
    print()

    # Check timeout config
    print("2. TimeoutConfig Check:")
    config_result = check_timeout_config()
    print(f"   Status: {config_result['status'].upper()}")
    print(f"   {config_result['message']}")
    print()

    # Check optimized pipeline
    print("3. OptimizedDetectionPipeline Check:")
    pipeline_result = check_optimized_pipeline_default()
    print(f"   Status: {pipeline_result['status'].upper()}")
    print(f"   {pipeline_result['message']}")
    print()

    # Determine effective frame skip
    print("=" * 80)
    print("EFFECTIVE CONFIGURATION")
    print("=" * 80)

    effective_frame_skip = env_result.get('value') or config_result.get('value') or pipeline_result.get('value') or 5

    print(f"\nEffective frame_skip: {effective_frame_skip}")
    print()

    # Calculate detection rate
    detection_info = calculate_detection_rate(effective_frame_skip)
    print("Expected Detection Performance:")
    print(f"  • Processing Rate: {detection_info['processing_rate']:.1f}%")
    print(f"  • Frames Processed (per 100): {detection_info['frames_processed_per_100']}")
    print(f"  • Frames Skipped (per 100): {detection_info['frames_skipped_per_100']}")
    print(f"  • Use Case: {detection_info['use_case_recommendation']}")
    print()

    # Recommendations
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print()

    if effective_frame_skip > 1:
        print("⚠️  WARNING: Current configuration skips frames!")
        print()
        print("For HIL validation and ground truth annotation, you should:")
        print()
        print("Option 1: Set environment variable")
        print("  export DETECTION_FRAME_SKIP=1")
        print()
        print("Option 2: Use BulletproofDetectionService")
        print("  from src.bulletproof_detection_service import BulletproofDetectionService")
        print("  service = BulletproofDetectionService()  # Processes ALL frames")
        print()
        print("Option 3: Modify timeout_config.py")
        print("  frame_skip_ratio: int = 1  # Change default from 5 to 1")
        print()
        print("Expected Improvement:")
        print(f"  Current:  {detection_info['processing_rate']:.1f}% detection rate")
        print(f"  After:    100.0% detection rate")
        print(f"  Gain:     +{100 - detection_info['processing_rate']:.1f}% more frames processed")
    else:
        print("✅ Configuration is OPTIMAL for HIL validation")
        print()
        print("Current settings will process ALL frames without skipping.")
        print("Expected detection rate: 100% (with constant voltage input)")

    print()
    print("=" * 80)
    print()

    # Exit code
    if effective_frame_skip > 1:
        sys.exit(1)  # Warning - frame skipping enabled
    else:
        sys.exit(0)  # OK - no frame skipping

if __name__ == "__main__":
    main()
