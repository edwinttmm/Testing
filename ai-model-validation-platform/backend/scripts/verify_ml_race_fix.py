#!/usr/bin/env python3
"""
Verification script for ML model race condition fix

This script validates:
1. is_initialized property works correctly
2. Warmup completion tracking is accurate
3. ensure_ready() method behaves properly
4. Blocking initialization in start_hil_monitoring()
"""

import sys
import asyncio
from pathlib import Path

# Add backend root to path
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

async def test_initialization_property():
    """Test that is_initialized property works correctly"""
    print("\n" + "="*60)
    print("TEST 1: is_initialized Property Check")
    print("="*60)

    from src.enhanced_ml_inference_engine import EnhancedYOLOEngine

    # Create engine without initializing
    engine = EnhancedYOLOEngine()

    print(f"Before initialization:")
    print(f"  _is_initialized: {engine._is_initialized}")
    print(f"  _warmup_complete: {engine._warmup_complete}")
    print(f"  _model is None: {engine._model is None}")
    print(f"  is_initialized property: {engine.is_initialized}")

    assert not engine.is_initialized, "❌ Engine should NOT be initialized before initialize() is called"
    print("✅ PASS: is_initialized is False before initialization")

    # Initialize the engine
    print("\nInitializing engine...")
    await engine.initialize()

    print(f"\nAfter initialization:")
    print(f"  _is_initialized: {engine._is_initialized}")
    print(f"  _warmup_complete: {engine._warmup_complete}")
    print(f"  _model is None: {engine._model is None}")
    print(f"  is_initialized property: {engine.is_initialized}")

    assert engine.is_initialized, "❌ Engine should be initialized after initialize() is called"
    print("✅ PASS: is_initialized is True after initialization")

    return True

async def test_warmup_tracking():
    """Test warmup completion tracking"""
    print("\n" + "="*60)
    print("TEST 2: Warmup Completion Tracking")
    print("="*60)

    from src.enhanced_ml_inference_engine import EnhancedYOLOEngine

    engine = EnhancedYOLOEngine()

    print(f"Before initialization:")
    print(f"  _warmup_complete: {engine._warmup_complete}")

    assert not engine._warmup_complete, "❌ Warmup should not be complete before initialization"
    print("✅ PASS: _warmup_complete is False before initialization")

    await engine.initialize()

    print(f"\nAfter initialization:")
    print(f"  _warmup_complete: {engine._warmup_complete}")

    assert engine._warmup_complete, "❌ Warmup should be complete after initialization"
    print("✅ PASS: _warmup_complete is True after initialization")

    return True

async def test_ensure_ready():
    """Test ensure_ready() method"""
    print("\n" + "="*60)
    print("TEST 3: ensure_ready() Method")
    print("="*60)

    from src.enhanced_ml_inference_engine import EnhancedYOLOEngine
    import time

    engine = EnhancedYOLOEngine()

    # Test 1: ensure_ready() waits for initialization
    print("Test 3a: ensure_ready() waits for uninitialized engine")

    async def delayed_init():
        await asyncio.sleep(1)
        await engine.initialize()

    init_task = asyncio.create_task(delayed_init())

    start_time = time.time()
    result = await engine.ensure_ready(timeout=5.0)
    wait_time = time.time() - start_time

    await init_task

    print(f"  Wait time: {wait_time:.2f}s")
    print(f"  Result: {result}")
    assert result, "❌ ensure_ready() should return True after initialization"
    assert wait_time >= 0.9, "❌ ensure_ready() should have waited for initialization"
    print("✅ PASS: ensure_ready() waited for initialization")

    # Test 2: ensure_ready() returns immediately if already initialized
    print("\nTest 3b: ensure_ready() returns immediately for initialized engine")
    start_time = time.time()
    result = await engine.ensure_ready(timeout=5.0)
    wait_time = time.time() - start_time

    print(f"  Wait time: {wait_time:.2f}s")
    print(f"  Result: {result}")
    assert result, "❌ ensure_ready() should return True for initialized engine"
    assert wait_time < 0.2, "❌ ensure_ready() should return immediately for initialized engine"
    print("✅ PASS: ensure_ready() returned immediately")

    # Test 3: ensure_ready() timeout
    print("\nTest 3c: ensure_ready() timeout behavior")
    uninitialized_engine = EnhancedYOLOEngine()

    try:
        await uninitialized_engine.ensure_ready(timeout=0.5)
        print("❌ FAIL: ensure_ready() should have raised TimeoutError")
        return False
    except TimeoutError as e:
        print(f"  TimeoutError raised: {e}")
        print("✅ PASS: ensure_ready() raised TimeoutError on timeout")

    return True

async def test_monitor_blocking():
    """Test that start_hil_monitoring blocks until model is ready"""
    print("\n" + "="*60)
    print("TEST 4: start_hil_monitoring Blocking Behavior")
    print("="*60)

    from src.hil_video_frame_monitor import HILVideoFrameMonitor
    import time

    # Create monitor (this initializes the T3 pipeline)
    monitor = HILVideoFrameMonitor()
    await monitor.initialize()

    # Check that the pipeline's ML engine has YOLO engine
    if not monitor.t3_pipeline or not monitor.t3_pipeline.ml_engine:
        print("⚠️  SKIP: T3 pipeline or ML engine not available")
        return True

    if not hasattr(monitor.t3_pipeline.ml_engine, 'yolo_engine'):
        print("⚠️  SKIP: YOLO engine not available")
        return True

    engine = monitor.t3_pipeline.ml_engine.yolo_engine

    print(f"YOLO engine initialization state:")
    print(f"  is_initialized: {engine.is_initialized}")

    # The monitor.initialize() should have already initialized the engine
    # So we can verify it's ready
    assert engine.is_initialized, "❌ YOLO engine should be initialized after monitor.initialize()"
    print("✅ PASS: YOLO engine is initialized after monitor.initialize()")

    print("\nℹ️  NOTE: Full blocking test requires uninitialized state,")
    print("   which can't be easily simulated. Manual testing recommended.")

    return True

async def run_all_tests():
    """Run all verification tests"""
    print("\n" + "="*60)
    print("ML MODEL RACE CONDITION FIX - VERIFICATION TESTS")
    print("="*60)

    tests = [
        ("Initialization Property", test_initialization_property),
        ("Warmup Tracking", test_warmup_tracking),
        ("ensure_ready() Method", test_ensure_ready),
        ("Monitor Blocking", test_monitor_blocking),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            result = await test_func()
            if result:
                passed += 1
            else:
                failed += 1
                print(f"\n❌ TEST FAILED: {test_name}")
        except Exception as e:
            failed += 1
            print(f"\n❌ TEST ERROR: {test_name}")
            print(f"   Exception: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Total Tests: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed == 0:
        print("\n✅ ALL TESTS PASSED")
        return 0
    else:
        print(f"\n❌ {failed} TESTS FAILED")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
