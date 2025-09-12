#!/usr/bin/env python3
"""
Test AI Detection Image Serving - Manual Annotation Mode
=========================================================
5 WHY ANALYSIS VALIDATION

Tests if AI detection images are properly served for manual annotation
"""

import requests
import sqlite3
import os
from urllib.parse import urljoin

def test_api_detection_data():
    """Test API returns detection data with screenshot paths"""
    print("=== TESTING API DETECTION DATA ===")
    
    # Get video ID from database
    conn = sqlite3.connect('test_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM videos LIMIT 1')
    video_result = cursor.fetchone()
    
    if not video_result:
        print("❌ No videos found in database")
        return False
    
    video_id = video_result[0]
    print(f"✅ Testing with video ID: {video_id[:8]}...")
    
    # Test the API endpoint that RealDetectionPanel uses
    try:
        api_url = f"http://localhost:8000/api/videos/{video_id}/detections"
        response = requests.get(api_url, timeout=5)
        
        if response.status_code == 200:
            detections = response.json()
            print(f"✅ API returned {len(detections)} detections")
            
            # Check for visual evidence
            visual_evidence_count = 0
            for detection in detections[:3]:  # Check first 3
                if detection.get('screenshot_path') or detection.get('screenshot_zoom_path'):
                    visual_evidence_count += 1
                    print(f"   Detection {detection.get('detection_id', 'N/A')[:8]}... has screenshot: {detection.get('screenshot_path', 'None')}")
            
            print(f"✅ {visual_evidence_count} detections have visual evidence")
            return len(detections) > 0 and visual_evidence_count > 0
            
        else:
            print(f"❌ API request failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ API request error: {e}")
        return False
    
    finally:
        conn.close()

def test_screenshot_serving():
    """Test if screenshot files are accessible via HTTP"""
    print("\\n=== TESTING SCREENSHOT HTTP SERVING ===")
    
    # Get a few screenshot paths from database
    conn = sqlite3.connect('test_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT screenshot_path, screenshot_zoom_path 
        FROM detection_events 
        WHERE screenshot_path IS NOT NULL 
        LIMIT 3
    ''')
    
    screenshot_paths = cursor.fetchall()
    conn.close()
    
    if not screenshot_paths:
        print("❌ No screenshot paths found in database")
        return False
    
    successful_serves = 0
    
    for screenshot_path, zoom_path in screenshot_paths:
        for path_type, path in [("Regular", screenshot_path), ("Zoom", zoom_path)]:
            if path:
                # Extract filename from path
                filename = os.path.basename(path)
                url = f"http://localhost:8000/screenshots/{filename}"
                
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        print(f"✅ {path_type} screenshot served: {filename}")
                        successful_serves += 1
                    else:
                        print(f"❌ {path_type} screenshot failed ({response.status_code}): {filename}")
                        
                except Exception as e:
                    print(f"❌ {path_type} screenshot error: {e}")
    
    return successful_serves > 0

def test_frontend_accessibility():
    """Test if frontend can access the screenshot URLs"""
    print("\\n=== TESTING FRONTEND ACCESSIBILITY ===")
    
    # Test frontend server
    try:
        response = requests.get("http://localhost:3000", timeout=5)
        if response.status_code == 200:
            print("✅ Frontend server accessible")
            return True
        else:
            print(f"❌ Frontend server error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Frontend server not accessible: {e}")
        return False

def test_manual_annotation_data_flow():
    """Test complete data flow for manual annotation"""
    print("\\n=== TESTING MANUAL ANNOTATION DATA FLOW ===")
    
    # This simulates what RealDetectionPanel does
    conn = sqlite3.connect('test_database.db')
    cursor = conn.cursor()
    
    # Get detections with visual evidence (what the component needs)
    cursor.execute('''
        SELECT 
            d.detection_id, d.frame_number, d.confidence, d.vru_type,
            d.screenshot_path, d.screenshot_zoom_path,
            d.bounding_box_x, d.bounding_box_y, d.bounding_box_width, d.bounding_box_height,
            d.source, d.validation_result
        FROM detection_events d
        WHERE d.screenshot_path IS NOT NULL
        AND d.source = 'ai'
        LIMIT 5
    ''')
    
    detections = cursor.fetchall()
    conn.close()
    
    if not detections:
        print("❌ No AI detections with visual evidence found")
        return False
    
    print(f"✅ Found {len(detections)} AI detections for manual annotation")
    
    # Test each detection's data completeness
    complete_detections = 0
    for detection in detections:
        detection_id, frame_number, confidence, vru_type, screenshot_path, zoom_path, bbox_x, bbox_y, bbox_w, bbox_h, source, validation_result = detection
        
        # Check data completeness
        has_screenshot = bool(screenshot_path)
        has_zoom = bool(zoom_path)
        has_bbox = all([bbox_x is not None, bbox_y is not None, bbox_w is not None, bbox_h is not None])
        has_confidence = confidence is not None
        has_classification = bool(vru_type)
        
        if has_screenshot and has_confidence and has_classification:
            complete_detections += 1
            print(f"✅ Complete detection: Frame {frame_number}, {vru_type}, {confidence:.2f} confidence")
        else:
            print(f"⚠️  Incomplete detection: Frame {frame_number} (missing data)")
    
    print(f"✅ {complete_detections} detections ready for manual annotation")
    return complete_detections > 0

def run_comprehensive_test():
    """Run all tests to validate AI detection image serving"""
    print("🧪 AI DETECTION IMAGE SERVING - COMPREHENSIVE TEST")
    print("=" * 60)
    
    tests = [
        ("API Detection Data", test_api_detection_data),
        ("Screenshot HTTP Serving", test_screenshot_serving), 
        ("Frontend Accessibility", test_frontend_accessibility),
        ("Manual Annotation Data Flow", test_manual_annotation_data_flow)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\\n🔍 Running: {test_name}")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    print("\\n" + "=" * 60)
    print("🎯 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{status} - {test_name}")
        if passed_test:
            passed += 1
    
    print(f"\\n📊 Overall: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 ALL TESTS PASSED - AI detection images should be showing in manual mode!")
    else:
        print("⚠️  Some tests failed - manual annotation may have image display issues")
        print("\\n🔧 RECOMMENDED FIXES:")
        
        if not results.get("API Detection Data", False):
            print("   - Check backend API /api/videos/{id}/detections endpoint")
        
        if not results.get("Screenshot HTTP Serving", False):
            print("   - Check screenshot static file serving at /screenshots/")
        
        if not results.get("Frontend Accessibility", False):
            print("   - Check frontend server at http://localhost:3000")
        
        if not results.get("Manual Annotation Data Flow", False):
            print("   - Check detection data completeness in database")

if __name__ == "__main__":
    run_comprehensive_test()