#!/usr/bin/env python3
"""
Quick Ground Truth API Test to identify the issue

The user reported "where is GT" - this simple test checks what's happening
with ground truth events in the enhanced HIL API.
"""

import requests
import json
import sys
import os

# Add backend path
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')

def test_ground_truth_api():
    """Test the enhanced HIL API for ground truth events"""
    
    print("🔍 Testing Ground Truth Display Issue")
    print("=" * 50)
    
    # Test the API endpoint
    base_url = "http://localhost:8000"
    session_id = "b7481a7d-b4d2-4425-afe1-235c7b29a8b5"  # From logs
    url = f"{base_url}/api/enhanced-hil/test-sessions/{session_id}/corrected-results"
    
    try:
        print(f"📡 Testing URL: {url}")
        response = requests.get(url, timeout=10)
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Check ground truth comparison
            gt_comparison = data.get("ground_truth_comparison", {})
            print(f"\n🎯 Ground Truth Comparison Found: {bool(gt_comparison)}")
            
            if gt_comparison:
                print(f"📈 GT Events Available: {gt_comparison.get('ground_truth_events_available', 0)}")
                print(f"📊 Total Detections: {gt_comparison.get('total_detections', 0)}")
                print(f"🔗 Events with Matches: {gt_comparison.get('events_with_matches', 0)}")
                
                # Check actual ground truth events array
                gt_events = gt_comparison.get("ground_truth_events", [])
                print(f"📋 GT Events Array Length: {len(gt_events)}")
                
                if len(gt_events) > 0:
                    print("✅ ISSUE FOUND: Ground truth events ARE in the API response!")
                    print("\n📋 Sample Ground Truth Event:")
                    sample_event = gt_events[0]
                    for key, value in sample_event.items():
                        print(f"   {key}: {value}")
                    
                    # Check if frontend should be able to see these
                    required_fields = ["frame_number", "video_timestamp", "event_type"]
                    missing_fields = [field for field in required_fields if field not in sample_event]
                    
                    if missing_fields:
                        print(f"\n❌ FRONTEND ISSUE: GT events missing required fields: {missing_fields}")
                    else:
                        print("\n✅ GT events have all required fields for frontend display")
                        
                else:
                    print("❌ ISSUE CONFIRMED: GT events array is empty despite claims of availability")
                    
            else:
                print("❌ ISSUE: No ground_truth_comparison section in API response")
                
        else:
            print(f"❌ API Error: HTTP {response.status_code}")
            print(f"Response: {response.text[:200]}")
            
    except Exception as e:
        print(f"❌ Test Error: {e}")
        return False
    
    return True

def check_database():
    """Check if ground truth data exists in database"""
    print("\n🗄️ Checking Database for Ground Truth Data")
    print("=" * 50)
    
    try:
        from database import get_db
        from models import GroundTruthObject, Video
        
        db = next(get_db())
        
        # Count ground truth objects
        gt_count = db.query(GroundTruthObject).count()
        print(f"📊 Total ground truth objects in DB: {gt_count}")
        
        if gt_count > 0:
            # Get sample ground truth object
            sample_gt = db.query(GroundTruthObject).first()
            print(f"📋 Sample GT object:")
            print(f"   Video ID: {sample_gt.video_id}")
            print(f"   Timestamp: {sample_gt.timestamp}")
            print(f"   Class Label: {sample_gt.class_label}")
            print(f"   Frame Number: {sample_gt.frame_number}")
            
            # Check if this video has a test session
            from models import TestSession
            session_with_video = db.query(TestSession).filter(
                TestSession.video_id == sample_gt.video_id
            ).first()
            
            if session_with_video:
                print(f"✅ Found test session {session_with_video.id} for this video")
                print(f"   Session name: {session_with_video.name}")
                
                # Test API for this specific session
                test_url = f"http://localhost:8000/api/enhanced-hil/test-sessions/{session_with_video.id}/corrected-results"
                print(f"\n🧪 Testing API for session with known GT data:")
                print(f"   URL: {test_url}")
                
                try:
                    response = requests.get(test_url, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        gt_comp = data.get("ground_truth_comparison", {})
                        gt_events = gt_comp.get("ground_truth_events", [])
                        print(f"   📊 GT events returned: {len(gt_events)}")
                        
                        if len(gt_events) == 0 and gt_count > 0:
                            print("   ❌ CRITICAL: DB has GT data but API returns empty array!")
                        elif len(gt_events) > 0:
                            print("   ✅ API correctly returns GT events")
                    else:
                        print(f"   ❌ API Error: HTTP {response.status_code}")
                        
                except Exception as e:
                    print(f"   ❌ API Test Error: {e}")
            else:
                print("⚠️ No test session found for video with ground truth data")
        else:
            print("❌ No ground truth data in database")
            
    except Exception as e:
        print(f"❌ Database check error: {e}")

def check_frontend_expectation():
    """Check what the frontend expects to receive"""
    print("\n🌐 Analyzing Frontend Expectations")
    print("=" * 50)
    
    # Based on the HILResults.tsx file analysis
    print("📋 Frontend expects ground truth events in:")
    print("   1. enhancedResults.ground_truth_comparison.ground_truth_events")
    print("   2. Each event should have: frame_number, video_timestamp, event_type")
    print("   3. Events are displayed in timeline visualization")
    
    print("\n🔍 Frontend code shows:")
    print("   - groundTruthEvents state variable")
    print("   - loadGroundTruthData() function")
    print("   - Timeline display with GT events")
    print("   - GT events are used in event timeline sorting")

def main():
    """Main test execution"""
    print("🚀 Ground Truth Timeline Display Diagnostic")
    print("Investigating user issue: 'where is GT'")
    print("=" * 60)
    
    # Run tests
    api_test_passed = test_ground_truth_api()
    check_database()
    check_frontend_expectation()
    
    print("\n" + "=" * 60)
    print("📊 DIAGNOSTIC SUMMARY")
    print("=" * 60)
    
    if api_test_passed:
        print("✅ Enhanced HIL API is accessible and returning data")
        print("🔍 Next steps: Check if frontend is properly parsing the response")
        print("💡 Recommendation: Verify frontend ground truth loading logic")
    else:
        print("❌ Enhanced HIL API has issues")
        print("🔧 Recommendation: Fix API endpoint first")
    
    print("\n🎯 To fix 'where is GT' issue:")
    print("1. Verify API returns ground_truth_events array with data")
    print("2. Check frontend parses the response correctly")
    print("3. Ensure timeline component displays the events")
    print("4. Validate event structure matches frontend expectations")

if __name__ == "__main__":
    main()