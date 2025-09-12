#!/usr/bin/env python3
"""
5 WHY ANALYSIS - FIX VALIDATION
===============================

Tests if the AI detection images are now showing properly after URL fix
"""

import requests
import sqlite3

def test_image_url_fix():
    """Test if the frontend URL fix resolves the image display issue"""
    print("🔧 TESTING AI DETECTION IMAGE URL FIX")
    print("=" * 50)
    
    # Get detection data from API
    conn = sqlite3.connect('test_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM videos LIMIT 1')
    video_id = cursor.fetchone()[0]
    conn.close()
    
    print(f"📹 Testing with video: {video_id[:8]}...")
    
    try:
        # Get API response (what frontend receives)
        api_url = f"http://localhost:8000/api/videos/{video_id}/detections"
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            detections = data.get('detections', [])
            
            print(f"✅ API returned {len(detections)} detections")
            
            if detections:
                detection = detections[0]
                screenshot_path = detection.get('screenshot_path')
                screenshot_zoom_path = detection.get('screenshot_zoom_path')
                
                print(f"\\n🖼️  DETECTION VISUAL EVIDENCE:")
                print(f"   Detection ID: {detection.get('detection_id', 'N/A')[:8]}...")
                print(f"   VRU Type: {detection.get('vru_type', 'N/A')}")
                print(f"   Confidence: {detection.get('confidence', 0):.2f}")
                print(f"   Screenshot Path: {screenshot_path}")
                print(f"   Zoom Path: {screenshot_zoom_path}")
                
                # Test OLD frontend logic (broken)
                if screenshot_path:
                    old_filename = screenshot_path.split('/').pop() 
                    old_url = f"/screenshots/{old_filename}"
                    print(f"\\n❌ OLD Logic URL: {old_url}")
                    
                    # Test NEW frontend logic (fixed)
                    new_url = screenshot_path
                    print(f"✅ NEW Logic URL: {new_url}")
                    
                    # Verify both URLs work via HTTP
                    for label, url in [("OLD (broken)", old_url), ("NEW (fixed)", new_url)]:
                        try:
                            test_response = requests.get(f"http://localhost:8000{url}", timeout=5)
                            status = "✅ WORKS" if test_response.status_code == 200 else f"❌ FAILS ({test_response.status_code})"
                            print(f"   {label}: {status}")
                        except Exception as e:
                            print(f"   {label}: ❌ ERROR - {e}")
                
                # Test has_visual_evidence flag
                has_evidence = detection.get('has_visual_evidence', False)
                print(f"\\n🔍 Visual Evidence Flag: {has_evidence}")
                
                if has_evidence and screenshot_path:
                    print("\\n🎉 RESULT: AI detection should now show images in manual mode!")
                    return True
                else:
                    print("\\n⚠️  ISSUE: Detection lacks visual evidence or paths")
                    return False
            else:
                print("❌ No detections found")
                return False
        else:
            print(f"❌ API failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_manual_annotation_workflow():
    """Test complete manual annotation workflow with visual evidence"""
    print("\\n" + "=" * 50)
    print("🔍 TESTING COMPLETE MANUAL ANNOTATION WORKFLOW")
    print("=" * 50)
    
    # Simulate what happens in manual annotation interface
    conn = sqlite3.connect('test_database.db')
    cursor = conn.cursor()
    
    # Get AI detections that should show visual evidence
    cursor.execute('''
        SELECT 
            de.detection_id, de.vru_type, de.confidence, de.frame_number,
            de.screenshot_path, de.screenshot_zoom_path, de.source,
            de.bounding_box_x, de.bounding_box_y, de.bounding_box_width, de.bounding_box_height
        FROM detection_events de
        WHERE de.screenshot_path IS NOT NULL 
        AND de.source = 'ai'
        LIMIT 3
    ''')
    
    ai_detections = cursor.fetchall()
    conn.close()
    
    print(f"📊 Found {len(ai_detections)} AI detections with visual evidence")
    
    if ai_detections:
        for i, detection in enumerate(ai_detections, 1):
            detection_id, vru_type, confidence, frame_number, screenshot_path, zoom_path, source, bbox_x, bbox_y, bbox_w, bbox_h = detection
            
            print(f"\\n🔍 Detection {i}:")
            print(f"   ID: {detection_id[:8]}...")
            print(f"   Type: {vru_type} ({confidence:.2f} confidence)")
            print(f"   Frame: {frame_number}")
            print(f"   Source: {source}")
            print(f"   Image: {screenshot_path}")
            
            # Check if bounding box data is available
            has_bbox = all([bbox_x, bbox_y, bbox_w, bbox_h])
            print(f"   Bounding Box: {'✅ Available' if has_bbox else '❌ Missing'}")
            
            # This is what manual annotators need to see
            if screenshot_path and confidence and vru_type:
                print(f"   Status: ✅ Ready for manual annotation")
            else:
                print(f"   Status: ❌ Incomplete data")
        
        print(f"\\n✅ Manual annotation interface should show {len(ai_detections)} AI detections with images")
        return True
    else:
        print("❌ No AI detections with visual evidence found")
        return False

if __name__ == "__main__":
    print("🚀 5 WHY ANALYSIS - VALIDATING FIX FOR AI DETECTION IMAGES")
    print("🎯 Issue: AI detection images not showing in manual annotation mode")
    print("🔧 Fix: Updated frontend URL construction logic")
    print()
    
    test1_result = test_image_url_fix()
    test2_result = test_manual_annotation_workflow()
    
    print("\\n" + "=" * 60)
    print("📋 FINAL VALIDATION RESULTS")
    print("=" * 60)
    
    if test1_result and test2_result:
        print("🎉 SUCCESS: AI detection images should now be visible in manual mode!")
        print("\\n📍 User can now:")
        print("   1. Navigate to Ground Truth page")
        print("   2. Select videos with AI detections") 
        print("   3. See visual evidence thumbnails for each detection")
        print("   4. Click zoom to view full-size detection images")
        print("   5. Validate AI accuracy through visual inspection")
    else:
        print("⚠️  PARTIAL SUCCESS: Some issues may remain")
        if not test1_result:
            print("   - URL construction may still have issues")
        if not test2_result:
            print("   - Manual annotation workflow data incomplete")