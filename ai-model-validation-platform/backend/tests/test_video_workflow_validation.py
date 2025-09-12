#!/usr/bin/env python3
"""
Video Workflow Validation Test
=============================

This test validates existing video functionality and workflow fixes.
It focuses on testing what's already working rather than trying to upload new content.

Test Coverage:
1. Verify API health and endpoint availability
2. Test existing video retrieval and display
3. Validate video URL accessibility
4. Test annotation system functionality  
5. Verify database consistency
6. Check frontend integration capabilities

Author: Testing and Quality Assurance Agent
Date: 2025-09-10
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests

BASE_URL = "http://localhost:8000"

def test_health_endpoint() -> Dict:
    """Test API health endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            return {
                "test": "API Health Check",
                "status": "PASS",
                "details": f"API is healthy: {response.json()}",
                "response_time": response.elapsed.total_seconds()
            }
        else:
            return {
                "test": "API Health Check",
                "status": "FAIL",
                "details": f"Health check failed with status {response.status_code}"
            }
    except Exception as e:
        return {
            "test": "API Health Check",
            "status": "FAIL",
            "details": f"Health check error: {str(e)}"
        }

def test_video_list_retrieval() -> Dict:
    """Test retrieving video list from API."""
    try:
        response = requests.get(f"{BASE_URL}/api/videos", timeout=10)
        if response.status_code == 200:
            data = response.json()
            videos = data.get('videos', [])
            total = data.get('total', 0)
            
            return {
                "test": "Video List Retrieval",
                "status": "PASS",
                "details": f"Retrieved {len(videos)} videos out of {total} total",
                "video_count": len(videos),
                "total_videos": total,
                "videos": videos[:3] if videos else []  # Show first 3 videos
            }
        else:
            return {
                "test": "Video List Retrieval", 
                "status": "FAIL",
                "details": f"Video list retrieval failed with status {response.status_code}"
            }
    except Exception as e:
        return {
            "test": "Video List Retrieval",
            "status": "FAIL", 
            "details": f"Video list error: {str(e)}"
        }

def test_video_accessibility(video_list: List[Dict]) -> List[Dict]:
    """Test accessibility of existing video files."""
    results = []
    
    if not video_list:
        return [{
            "test": "Video File Accessibility",
            "status": "SKIP",
            "details": "No videos available to test"
        }]
    
    for video in video_list[:3]:  # Test first 3 videos
        video_id = video.get('id')
        url = video.get('url')
        filename = video.get('filename')
        
        try:
            # Test video metadata endpoint
            metadata_response = requests.get(f"{BASE_URL}/api/videos/{video_id}", timeout=10)
            
            # Test direct file access
            if url:
                file_response = requests.head(url, timeout=10)
                
                if metadata_response.status_code == 200 and file_response.status_code == 200:
                    content_length = file_response.headers.get('Content-Length', '0')
                    results.append({
                        "test": f"Video Access - {filename}",
                        "status": "PASS",
                        "details": f"Video {video_id} accessible at {url}, Size: {content_length} bytes",
                        "video_id": video_id,
                        "url": url,
                        "size": content_length
                    })
                else:
                    results.append({
                        "test": f"Video Access - {filename}",
                        "status": "FAIL", 
                        "details": f"Video not accessible. Metadata: {metadata_response.status_code}, File: {file_response.status_code}"
                    })
            else:
                results.append({
                    "test": f"Video Access - {filename}",
                    "status": "FAIL",
                    "details": "No URL provided in video metadata"
                })
                
        except Exception as e:
            results.append({
                "test": f"Video Access - {filename}",
                "status": "FAIL",
                "details": f"Error accessing video {video_id}: {str(e)}"
            })
    
    return results

def test_annotation_system(video_list: List[Dict]) -> List[Dict]:
    """Test annotation system functionality."""
    results = []
    
    if not video_list:
        return [{
            "test": "Annotation System",
            "status": "SKIP",
            "details": "No videos available to test annotations"
        }]
    
    for video in video_list[:2]:  # Test annotations for first 2 videos
        video_id = video.get('id')
        filename = video.get('filename')
        
        try:
            # Test getting existing annotations
            response = requests.get(f"{BASE_URL}/api/videos/{video_id}/annotations", timeout=10)
            
            if response.status_code == 200:
                annotations = response.json()
                results.append({
                    "test": f"Annotations - {filename}",
                    "status": "PASS",
                    "details": f"Successfully retrieved {len(annotations)} annotations for video {video_id}",
                    "video_id": video_id,
                    "annotation_count": len(annotations)
                })
            elif response.status_code == 404:
                results.append({
                    "test": f"Annotations - {filename}",
                    "status": "PASS",
                    "details": f"No annotations found for video {video_id} (expected for new videos)",
                    "video_id": video_id,
                    "annotation_count": 0
                })
            else:
                results.append({
                    "test": f"Annotations - {filename}",
                    "status": "FAIL",
                    "details": f"Annotation retrieval failed with status {response.status_code}"
                })
                
        except Exception as e:
            results.append({
                "test": f"Annotations - {filename}",
                "status": "FAIL",
                "details": f"Error testing annotations for video {video_id}: {str(e)}"
            })
    
    return results

def test_project_system() -> Dict:
    """Test project system functionality."""
    try:
        response = requests.get(f"{BASE_URL}/api/projects", timeout=10)
        if response.status_code == 200:
            projects = response.json()
            return {
                "test": "Project System",
                "status": "PASS",
                "details": f"Retrieved {len(projects)} projects",
                "project_count": len(projects),
                "projects": [{"id": p.get("id"), "name": p.get("name")} for p in projects[:3]]
            }
        else:
            return {
                "test": "Project System", 
                "status": "FAIL",
                "details": f"Project retrieval failed with status {response.status_code}"
            }
    except Exception as e:
        return {
            "test": "Project System",
            "status": "FAIL",
            "details": f"Project system error: {str(e)}"
        }

def test_database_consistency(video_list: List[Dict]) -> Dict:
    """Test database consistency by checking video metadata."""
    try:
        consistent_videos = 0
        total_videos = len(video_list)
        issues = []
        
        for video in video_list:
            video_id = video.get('id')
            filename = video.get('filename')
            url = video.get('url')
            status = video.get('status')
            
            # Check required fields
            if not video_id or not filename:
                issues.append(f"Missing required fields for video: {video}")
                continue
                
            # Check filename consistency
            if url and filename not in url:
                issues.append(f"Filename {filename} not consistent with URL {url}")
                continue
                
            consistent_videos += 1
        
        consistency_rate = (consistent_videos / total_videos) * 100 if total_videos > 0 else 0
        
        if consistency_rate >= 90:
            return {
                "test": "Database Consistency",
                "status": "PASS", 
                "details": f"Database consistency: {consistency_rate:.1f}% ({consistent_videos}/{total_videos})",
                "consistency_rate": consistency_rate,
                "issues": issues[:5]  # Show first 5 issues
            }
        else:
            return {
                "test": "Database Consistency",
                "status": "FAIL",
                "details": f"Low database consistency: {consistency_rate:.1f}% ({consistent_videos}/{total_videos})",
                "consistency_rate": consistency_rate,
                "issues": issues[:5]
            }
            
    except Exception as e:
        return {
            "test": "Database Consistency",
            "status": "FAIL",
            "details": f"Database consistency error: {str(e)}"
        }

def run_comprehensive_validation():
    """Run all validation tests and generate report."""
    print("=" * 80)
    print("🚀 VIDEO WORKFLOW VALIDATION TEST")
    print("=" * 80)
    
    all_results = []
    start_time = datetime.now()
    
    # 1. Health check
    print("\n🏥 Testing API Health...")
    health_result = test_health_endpoint()
    all_results.append(health_result)
    
    if health_result['status'] != 'PASS':
        print("❌ Backend API not accessible, stopping tests")
        return generate_report(all_results, start_time)
    
    # 2. Video list retrieval
    print("📹 Testing Video List Retrieval...")
    video_result = test_video_list_retrieval()
    all_results.append(video_result)
    
    video_list = video_result.get('videos', [])
    
    # 3. Video accessibility
    print("🌐 Testing Video Accessibility...")
    accessibility_results = test_video_accessibility(video_list)
    all_results.extend(accessibility_results)
    
    # 4. Annotation system
    print("✏️ Testing Annotation System...")
    annotation_results = test_annotation_system(video_list)
    all_results.extend(annotation_results)
    
    # 5. Project system
    print("📋 Testing Project System...")
    project_result = test_project_system()
    all_results.append(project_result)
    
    # 6. Database consistency
    print("🗃️ Testing Database Consistency...")
    consistency_result = test_database_consistency(video_list)
    all_results.append(consistency_result)
    
    return generate_report(all_results, start_time)

def generate_report(results: List[Dict], start_time: datetime) -> Dict:
    """Generate comprehensive test report."""
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = sum(1 for r in results if r['status'] == 'FAIL')
    skipped = sum(1 for r in results if r['status'] == 'SKIP')
    
    total = len(results)
    success_rate = (passed / (total - skipped)) * 100 if (total - skipped) > 0 else 0
    
    report = {
        "timestamp": start_time.isoformat(),
        "duration": f"{duration:.2f}s",
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "success_rate": f"{success_rate:.1f}%"
        },
        "tests": results
    }
    
    # Print summary
    print("\n" + "=" * 80)
    print("📊 VALIDATION RESULTS")
    print("=" * 80)
    print(f"⏱️  Duration: {duration:.2f}s")
    print(f"📈 Success Rate: {success_rate:.1f}%")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⏭️  Skipped: {skipped}")
    print(f"📊 Total: {total}")
    
    print("\n📋 DETAILED RESULTS:")
    print("-" * 80)
    
    for i, test in enumerate(results, 1):
        status_emoji = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}
        emoji = status_emoji.get(test['status'], "❓")
        print(f"{i:2d}. {emoji} {test['test']}")
        print(f"    {test['details']}")
        
        # Show additional info
        if test.get('video_count'):
            print(f"    📹 Videos: {test['video_count']}")
        if test.get('annotation_count') is not None:
            print(f"    📝 Annotations: {test['annotation_count']}")
        if test.get('consistency_rate'):
            print(f"    📊 Consistency: {test['consistency_rate']:.1f}%")
        print()
    
    return report

def main():
    """Main test execution."""
    try:
        print("🧪 Starting Video Workflow Validation Test")
        
        report = run_comprehensive_validation()
        
        # Save report
        results_file = Path("tests/video_workflow_validation_results.json")
        results_file.parent.mkdir(exist_ok=True)
        
        with open(results_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📁 Full results saved to: {results_file}")
        
        # Exit based on results
        if report['summary']['failed'] > 0:
            print("\n❌ SOME VALIDATIONS FAILED")
            sys.exit(1)
        else:
            print("\n✅ ALL VALIDATIONS PASSED")
            sys.exit(0)
            
    except Exception as e:
        print(f"\n💥 FATAL ERROR: {str(e)}")
        sys.exit(2)

if __name__ == "__main__":
    main()