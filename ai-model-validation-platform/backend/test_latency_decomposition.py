#!/usr/bin/env python3
"""
Test script for latency decomposition functionality.

This script demonstrates how the latency decomposition service separates
camera-specific latency from system overhead to provide accurate camera validation.
"""

import sys
import os
import asyncio
import time
import statistics
from typing import Dict, Any

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.latency_decomposition_service import (
    get_latency_decomposition_service,
    LatencyComponent,
    LatencyDecomposition
)
from services.timing_synchronization_calculator import (
    get_timing_synchronization_calculator,
    VideoTimingMetadata
)

def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'=' * 80}")
    print(f" {title}")
    print(f"{'=' * 80}")

def print_subsection(title: str):
    """Print a formatted subsection header"""
    print(f"\n{'-' * 60}")
    print(f" {title}")
    print(f"{'-' * 60}")

async def test_system_baseline_calibration():
    """Test system baseline calibration"""
    print_section("SYSTEM BASELINE CALIBRATION")
    
    decomposition_service = get_latency_decomposition_service()
    
    print("Calibrating system baseline (measuring hardware/software overhead)...")
    start_time = time.time()
    
    baseline_profile = decomposition_service.calibrate_system_baseline()
    
    calibration_time = time.time() - start_time
    
    print(f"✅ System baseline calibrated in {calibration_time:.2f} seconds")
    print(f"\nBaseline Profile:")
    print(f"  • Total Baseline Overhead: {baseline_profile.total_baseline_ns/1e6:.3f} ms")
    print(f"  • OS Overhead: {baseline_profile.os_overhead_ns/1e6:.3f} ms")
    print(f"  • Hardware Overhead: {baseline_profile.hardware_overhead_ns/1e6:.3f} ms")
    print(f"  • Context Switch Overhead: {baseline_profile.context_switch_ns/1e6:.3f} ms")
    print(f"  • Memory Access Overhead: {baseline_profile.memory_access_ns/1e6:.3f} ms")
    print(f"  • Timing Precision: {baseline_profile.timing_precision_ns/1e3:.1f} μs")
    print(f"  • Measurement Confidence: {baseline_profile.measurement_confidence:.2f}")
    
    # Validate baseline reasonableness
    total_baseline_ms = baseline_profile.total_baseline_ns / 1e6
    if total_baseline_ms < 50:
        print(f"✅ System baseline ({total_baseline_ms:.3f}ms) is within expected range")
    else:
        print(f"⚠️ System baseline ({total_baseline_ms:.3f}ms) is higher than expected")
    
    return baseline_profile

async def test_latency_decomposition():
    """Test latency decomposition on simulated camera measurements"""
    print_section("LATENCY DECOMPOSITION TESTING")
    
    decomposition_service = get_latency_decomposition_service()
    
    # Simulate various camera latency scenarios
    test_scenarios = [
        {
            "name": "Excellent Camera Performance",
            "total_latency_ms": 45.5,
            "metadata": {
                'detection_algorithm': 'YOLO',
                'image_resolution': '640x480',
                'communication_method': 'local',
                'preprocessing_enabled': False
            }
        },
        {
            "name": "Good Camera Performance with Processing",
            "total_latency_ms": 89.2,
            "metadata": {
                'detection_algorithm': 'YOLO',
                'image_resolution': '1920x1080',
                'communication_method': 'tcp',
                'preprocessing_enabled': True
            }
        },
        {
            "name": "High Latency Scenario",
            "total_latency_ms": 156.8,
            "metadata": {
                'detection_algorithm': 'YOLO',
                'image_resolution': '4K',
                'communication_method': 'tcp',
                'preprocessing_enabled': True,
                'multi_threaded': True
            }
        },
        {
            "name": "Minimal Overhead Scenario",
            "total_latency_ms": 22.1,
            "metadata": {
                'detection_algorithm': 'SSD',
                'image_resolution': '320x240',
                'communication_method': 'local',
                'preprocessing_enabled': False
            }
        }
    ]
    
    decomposition_results = []
    
    for i, scenario in enumerate(test_scenarios, 1):
        print_subsection(f"Scenario {i}: {scenario['name']}")
        
        # Decompose the latency
        decomposition = decomposition_service.decompose_latency(
            session_id="test_session",
            detection_id=f"detection_{i:03d}",
            total_latency_ms=scenario["total_latency_ms"],
            detection_metadata=scenario["metadata"]
        )
        
        decomposition_results.append(decomposition)
        
        # Display results
        print(f"📊 Total Latency: {decomposition.total_latency_ms:.3f} ms")
        print(f"   🎥 Camera-Only Latency: {decomposition.camera_latency_ms:.3f} ms ({decomposition.camera_latency_ms/decomposition.total_latency_ms*100:.1f}%)")
        print(f"   💻 System Baseline: {decomposition.system_baseline_ms:.3f} ms ({decomposition.system_baseline_ms/decomposition.total_latency_ms*100:.1f}%)")
        print(f"   ⚙️ Processing Overhead: {decomposition.processing_overhead_ms:.3f} ms ({decomposition.processing_overhead_ms/decomposition.total_latency_ms*100:.1f}%)")
        print(f"   🌐 Network Overhead: {decomposition.network_overhead_ms:.3f} ms ({decomposition.network_overhead_ms/decomposition.total_latency_ms*100:.1f}%)")
        print(f"   🔄 Sync Overhead: {decomposition.sync_overhead_ms:.3f} ms ({decomposition.sync_overhead_ms/decomposition.total_latency_ms*100:.1f}%)")
        
        if decomposition.unknown_overhead_ms > 0:
            print(f"   ❓ Unknown Overhead: {decomposition.unknown_overhead_ms:.3f} ms ({decomposition.unknown_overhead_ms/decomposition.total_latency_ms*100:.1f}%)")
        
        print(f"   📈 Total Overhead: {decomposition.get_overhead_percentage():.1f}%")
        print(f"   ✅ Validation Status: {decomposition.validation_status}")
        print(f"   🎯 Decomposition Confidence: {decomposition.decomposition_confidence:.2f}")
        
        # Validate camera performance
        camera_latency = decomposition.get_pure_camera_latency()
        if camera_latency < 50:
            print(f"   🏆 Excellent camera performance: {camera_latency:.1f}ms")
        elif camera_latency < 100:
            print(f"   👍 Good camera performance: {camera_latency:.1f}ms")
        else:
            print(f"   ⚠️ Camera performance needs improvement: {camera_latency:.1f}ms")
    
    return decomposition_results

async def test_timing_integration():
    """Test integration with timing synchronization calculator"""
    print_section("TIMING SYNCHRONIZATION INTEGRATION")
    
    timing_calc = get_timing_synchronization_calculator()
    
    # Simulate timing calculation with decomposition
    video_metadata = VideoTimingMetadata(
        startup_delay_ms=1500.0,
        fps=30.0,
        duration=10.0,
        timing_sync_status="synced",
        timing_accuracy_ns=1000
    )
    
    print("Simulating timing synchronization calculation with automatic latency decomposition...")
    
    result = timing_calc.calculate_corrected_latency(
        session_id="integration_test",
        detection_id="detection_integrated_001",
        detection_system_time=1234567890.125,  # Detection occurred
        ground_truth_frame=150,  # Frame 150 at 30fps = 5 seconds
        ground_truth_video_time=5.0,  # 5 seconds into video
        video_timing_metadata=video_metadata,
        labjack_start_time=1234567880.0  # LabJack started 10 seconds earlier
    )
    
    print(f"\n📊 Enhanced Timing Results:")
    print(f"   🕐 Apparent Latency (old method): {result.apparent_latency_ms:.3f} ms")
    print(f"   ⏱️ Real Latency (corrected): {result.real_latency_ms:.3f} ms")
    print(f"   🎥 Camera-Only Latency: {result.camera_only_latency_ms:.3f} ms")
    print(f"   💻 System Overhead: {result.system_overhead_ms:.3f} ms")
    print(f"   ⚙️ Processing Overhead: {result.processing_overhead_ms:.3f} ms")
    print(f"   🔧 Timing Correction: {result.latency_correction_ms:.3f} ms")
    print(f"   📈 Decomposition Confidence: {result.decomposition_confidence:.2f}")
    print(f"   ✅ Timing Quality: {result.timing_quality}")
    
    # Show the benefit of decomposition
    overhead_ms = result.system_overhead_ms + result.processing_overhead_ms
    overhead_percentage = (overhead_ms / result.real_latency_ms) * 100
    
    print(f"\n🎯 Decomposition Benefits:")
    print(f"   • Total overhead removed: {overhead_ms:.3f} ms ({overhead_percentage:.1f}%)")
    print(f"   • Camera validation now based on {result.camera_only_latency_ms:.3f} ms instead of {result.real_latency_ms:.3f} ms")
    print(f"   • This ensures fair camera assessment independent of system performance")
    
    return result

async def analyze_decomposition_statistics(decomposition_results):
    """Analyze statistics across multiple decomposition results"""
    print_section("DECOMPOSITION STATISTICS ANALYSIS")
    
    if not decomposition_results:
        print("No decomposition results to analyze")
        return
    
    # Extract metrics
    camera_latencies = [d.camera_latency_ms for d in decomposition_results]
    system_overheads = [d.system_baseline_ms for d in decomposition_results]
    processing_overheads = [d.processing_overhead_ms for d in decomposition_results]
    overhead_percentages = [d.get_overhead_percentage() for d in decomposition_results]
    confidence_scores = [d.decomposition_confidence for d in decomposition_results]
    
    print(f"📈 Analysis of {len(decomposition_results)} decomposition results:")
    
    print(f"\n🎥 Camera-Only Latencies:")
    print(f"   • Mean: {statistics.mean(camera_latencies):.3f} ms")
    print(f"   • Median: {statistics.median(camera_latencies):.3f} ms")
    print(f"   • Range: {min(camera_latencies):.3f} - {max(camera_latencies):.3f} ms")
    print(f"   • Std Dev: {statistics.stdev(camera_latencies):.3f} ms")
    
    print(f"\n💻 System Overhead Analysis:")
    print(f"   • Mean Overhead: {statistics.mean(system_overheads):.3f} ms")
    print(f"   • Mean Processing: {statistics.mean(processing_overheads):.3f} ms")
    print(f"   • Mean Total Overhead: {statistics.mean(overhead_percentages):.1f}%")
    
    print(f"\n🎯 Decomposition Quality:")
    print(f"   • Mean Confidence: {statistics.mean(confidence_scores):.2f}")
    print(f"   • High Confidence (>0.8): {sum(1 for c in confidence_scores if c > 0.8)}/{len(confidence_scores)}")
    
    # Validation status summary
    validation_statuses = [d.validation_status for d in decomposition_results]
    status_counts = {}
    for status in validation_statuses:
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print(f"\n✅ Validation Status Distribution:")
    for status, count in status_counts.items():
        print(f"   • {status}: {count}/{len(decomposition_results)} ({count/len(decomposition_results)*100:.1f}%)")

async def demonstrate_api_usage():
    """Demonstrate how to use the API endpoints"""
    print_section("API ENDPOINT USAGE DEMONSTRATION")
    
    print("The following API endpoints are available for latency decomposition:")
    
    endpoints = [
        {
            "method": "GET",
            "path": "/api/latency-analysis/baseline/calibrate",
            "description": "Calibrate system baseline latency"
        },
        {
            "method": "GET", 
            "path": "/api/latency-analysis/baseline/status",
            "description": "Get baseline calibration status"
        },
        {
            "method": "POST",
            "path": "/api/latency-analysis/decompose/{session_id}",
            "description": "Decompose all latencies for a session"
        },
        {
            "method": "GET",
            "path": "/api/latency-analysis/decomposition/{session_id}",
            "description": "Get decomposition results for a session"
        },
        {
            "method": "GET",
            "path": "/api/latency-analysis/analysis/{session_id}/camera-only",
            "description": "Get camera-only latencies (excluding overhead)"
        },
        {
            "method": "GET",
            "path": "/api/latency-analysis/comparison/{session_id}",
            "description": "Compare total vs camera-only latencies"
        }
    ]
    
    for endpoint in endpoints:
        print(f"   {endpoint['method']:>4} {endpoint['path']:<50} - {endpoint['description']}")
    
    print(f"\n💡 Example Usage:")
    print(f"   1. First calibrate system baseline:")
    print(f"      curl -X GET http://localhost:8000/api/latency-analysis/baseline/calibrate")
    print(f"   ")
    print(f"   2. Run your HIL test session to generate latency data")
    print(f"   ")
    print(f"   3. Get camera-only latencies:")
    print(f"      curl -X GET http://localhost:8000/api/latency-analysis/analysis/your_session_id/camera-only")
    print(f"   ")
    print(f"   4. Compare total vs camera latencies:")
    print(f"      curl -X GET http://localhost:8000/api/latency-analysis/comparison/your_session_id")

async def main():
    """Main test function"""
    print_section("LATENCY DECOMPOSITION SERVICE TEST")
    print("This test demonstrates separating camera latency from system overhead")
    print("to ensure accurate camera validation independent of system performance.")
    
    try:
        # Test 1: System baseline calibration
        baseline_profile = await test_system_baseline_calibration()
        
        # Test 2: Latency decomposition scenarios
        decomposition_results = await test_latency_decomposition()
        
        # Test 3: Integration with timing synchronization
        timing_result = await test_timing_integration()
        
        # Test 4: Statistical analysis
        await analyze_decomposition_statistics(decomposition_results)
        
        # Test 5: API usage demonstration
        await demonstrate_api_usage()
        
        print_section("TEST SUMMARY")
        print("✅ All latency decomposition tests completed successfully!")
        print("\n🎯 Key Benefits Demonstrated:")
        print("   • System overhead measurement and separation")
        print("   • Camera-specific latency isolation")
        print("   • Fair camera performance assessment")
        print("   • Integration with existing timing systems")
        print("   • Comprehensive validation methodology")
        print("\n🚀 The system can now distinguish between:")
        print("   • Camera performance issues (slow sensor response)")
        print("   • System limitations (hardware/software overhead)")
        print("   • Processing bottlenecks (algorithm performance)")
        print("   • Communication delays (network/driver overhead)")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)