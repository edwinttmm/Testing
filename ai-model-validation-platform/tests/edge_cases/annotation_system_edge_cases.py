"""
📝 ANNOTATION SYSTEM EXTREME EDGE CASE TESTING
Tests all extreme annotation scenarios that could break the system
"""

import pytest
import asyncio
import json
import time
import requests
import random
from typing import Dict, Any, List
from datetime import datetime

class AnnotationSystemEdgeCases:
    """Extreme annotation system edge case tests"""
    
    def __init__(self, backend_url: str = "http://localhost:8000"):
        self.backend_url = backend_url
        self.test_results = []
        
    async def run_all_annotation_edge_cases(self):
        """Execute all annotation system edge case tests"""
        print("📝 Starting Annotation System Edge Case Tests")
        print("="*60)
        
        # First, create a test video for annotations
        self.test_video_id = await self.create_test_video_for_annotations()
        
        if not self.test_video_id:
            print("❌ Failed to create test video - cannot continue annotation tests")
            return
            
        print(f"✅ Created test video: {self.test_video_id}")
        
        # 1. Annotation Volume Edge Cases
        await self.test_massive_annotation_creation()
        
        # 2. Annotation Boundary Edge Cases
        await self.test_annotation_boundaries()
        
        # 3. Temporal Edge Cases
        await self.test_temporal_edge_cases()
        
        # 4. Data Validation Edge Cases
        await self.test_data_validation_edge_cases()
        
        # 5. Concurrent Annotation Tests
        await self.test_concurrent_annotations()
        
        # 6. Memory Stress Tests
        await self.test_annotation_memory_stress()
        
        # 7. Export Edge Cases
        await self.test_export_edge_cases()
        
        # Generate summary
        await self.generate_annotation_test_summary()
        
    async def create_test_video_for_annotations(self) -> str:
        """Create or get a test video for annotation testing"""
        try:
            # Try to get existing videos first
            response = requests.get(f"{self.backend_url}/api/videos")
            if response.status_code == 200:
                videos = response.json()
                if isinstance(videos, dict) and "videos" in videos:
                    video_list = videos["videos"]
                else:
                    video_list = videos if isinstance(videos, list) else []
                    
                if video_list:
                    return video_list[0]["id"]
                    
            # If no videos exist, we'll use a mock video ID for testing
            return "test-video-id-12345"
            
        except Exception as e:
            print(f"Error creating test video: {e}")
            return None
            
    async def test_massive_annotation_creation(self):
        """Test creating massive numbers of annotations"""
        print("🏗️  Testing Massive Annotation Creation...")
        
        volume_tests = [
            {"name": "High Volume", "count": 100},
            {"name": "Very High Volume", "count": 500},
            {"name": "Extreme Volume", "count": 1000},
            {"name": "Stress Test Volume", "count": 2000}
        ]
        
        for test in volume_tests:
            await self.test_single_volume_scenario(test)
            
    async def test_single_volume_scenario(self, test_config: Dict[str, Any]):
        """Test single annotation volume scenario"""
        start_time = time.time()
        successful_annotations = 0
        failed_annotations = 0
        
        try:
            print(f"  Creating {test_config['count']} annotations...")
            
            # Create annotations in batches to avoid overwhelming the system
            batch_size = 50
            total_count = test_config["count"]
            
            for batch_start in range(0, total_count, batch_size):
                batch_end = min(batch_start + batch_size, total_count)
                batch_results = await self.create_annotation_batch(batch_start, batch_end)
                
                successful_annotations += batch_results["success"]
                failed_annotations += batch_results["failed"]
                
                # Small delay between batches to prevent overload
                await asyncio.sleep(0.1)
                
            total_time = time.time() - start_time
            success_rate = (successful_annotations / total_count) * 100 if total_count > 0 else 0
            
            # Determine status
            if success_rate >= 95:
                status = "✅ PASS"
            elif success_rate >= 80:
                status = "⚠️ PARTIAL (Good)"
            elif success_rate >= 50:
                status = "⚠️ PARTIAL (Poor)"
            else:
                status = "❌ FAIL"
                
            await self.log_result(
                "Annotation Volume",
                f"{test_config['name']} ({test_config['count']} annotations)",
                status,
                {
                    "target_count": total_count,
                    "successful": successful_annotations,
                    "failed": failed_annotations,
                    "success_rate": f"{success_rate:.1f}%",
                    "total_time": total_time,
                    "annotations_per_second": successful_annotations / total_time if total_time > 0 else 0
                }
            )
            
        except Exception as e:
            await self.log_result(
                "Annotation Volume",
                f"{test_config['name']}",
                "❌ FAIL",
                {"error": str(e), "target_count": test_config["count"]}
            )
            
    async def create_annotation_batch(self, start_idx: int, end_idx: int) -> Dict[str, int]:
        """Create a batch of annotations"""
        success_count = 0
        fail_count = 0
        
        for i in range(start_idx, end_idx):
            try:
                annotation_data = self.generate_test_annotation_data(i)
                
                response = requests.post(
                    f"{self.backend_url}/api/videos/{self.test_video_id}/annotations",
                    json=annotation_data,
                    timeout=10
                )
                
                if response.status_code in [200, 201]:
                    success_count += 1
                else:
                    fail_count += 1
                    
            except Exception:
                fail_count += 1
                
        return {"success": success_count, "failed": fail_count}
        
    def generate_test_annotation_data(self, index: int) -> Dict[str, Any]:
        """Generate test annotation data"""
        # Vary annotation properties based on index
        vru_types = ["pedestrian", "cyclist", "vehicle", "animal"]
        
        return {
            "video_id": self.test_video_id,
            "detection_id": f"TEST_DET_{index:06d}",
            "frame_number": (index % 300) + 1,  # Spread across 300 frames
            "timestamp": (index % 300) * 0.033,  # 30fps
            "end_timestamp": ((index % 300) + 1) * 0.033,
            "vru_type": vru_types[index % len(vru_types)],
            "bounding_box": {
                "x": 100 + (index % 400),
                "y": 100 + ((index * 2) % 200),
                "width": 50 + (index % 100),
                "height": 100 + (index % 150)
            },
            "occluded": index % 5 == 0,
            "truncated": index % 7 == 0,
            "difficult": index % 10 == 0,
            "notes": f"Auto-generated test annotation {index}",
            "annotator": f"test_user_{index % 5}",
            "validated": index % 3 == 0
        }
        
    async def test_annotation_boundaries(self):
        """Test annotation boundary conditions"""
        print("🎯 Testing Annotation Boundaries...")
        
        boundary_tests = [
            {
                "name": "Zero Coordinates",
                "bounding_box": {"x": 0, "y": 0, "width": 1, "height": 1}
            },
            {
                "name": "Negative Coordinates", 
                "bounding_box": {"x": -10, "y": -10, "width": 50, "height": 50}
            },
            {
                "name": "Huge Coordinates",
                "bounding_box": {"x": 999999, "y": 999999, "width": 100, "height": 100}
            },
            {
                "name": "Zero Size",
                "bounding_box": {"x": 100, "y": 100, "width": 0, "height": 0}
            },
            {
                "name": "Negative Size",
                "bounding_box": {"x": 100, "y": 100, "width": -50, "height": -50}
            },
            {
                "name": "Fractional Coordinates",
                "bounding_box": {"x": 123.456, "y": 78.901, "width": 45.5, "height": 67.3}
            },
            {
                "name": "Extreme Aspect Ratio",
                "bounding_box": {"x": 100, "y": 100, "width": 1000, "height": 1}
            }
        ]
        
        for test in boundary_tests:
            await self.test_single_boundary_case(test)
            
    async def test_single_boundary_case(self, test_config: Dict[str, Any]):
        """Test single boundary case"""
        try:
            annotation_data = {
                "video_id": self.test_video_id,
                "detection_id": f"BOUNDARY_TEST_{int(time.time())}",
                "frame_number": 1,
                "timestamp": 1.0,
                "vru_type": "pedestrian",
                "bounding_box": test_config["bounding_box"],
                "occluded": False,
                "truncated": False,
                "difficult": False,
                "notes": f"Boundary test: {test_config['name']}",
                "annotator": "boundary_tester",
                "validated": True
            }
            
            response = requests.post(
                f"{self.backend_url}/api/videos/{self.test_video_id}/annotations",
                json=annotation_data,
                timeout=30
            )
            
            # Determine expected behavior
            bbox = test_config["bounding_box"]
            is_valid_bbox = (
                bbox["width"] > 0 and 
                bbox["height"] > 0 and 
                bbox["x"] >= 0 and 
                bbox["y"] >= 0
            )
            
            if response.status_code in [200, 201]:
                if is_valid_bbox:
                    status = "✅ PASS (Valid bbox accepted)"
                else:
                    status = "⚠️ PARTIAL (Invalid bbox accepted - check validation)"
            elif response.status_code in [400, 422]:
                if not is_valid_bbox:
                    status = "✅ PASS (Invalid bbox properly rejected)"
                else:
                    status = "❌ FAIL (Valid bbox improperly rejected)"
            else:
                status = "❌ FAIL (Unexpected response)"
                
            await self.log_result(
                "Annotation Boundaries",
                test_config["name"],
                status,
                {
                    "bounding_box": bbox,
                    "response_code": response.status_code,
                    "is_valid_bbox": is_valid_bbox,
                    "response_message": response.text[:200] if response.status_code != 200 else "OK"
                }
            )
            
        except Exception as e:
            await self.log_result(
                "Annotation Boundaries",
                test_config["name"],
                "❌ FAIL",
                {"error": str(e), "bounding_box": test_config["bounding_box"]}
            )
            
    async def test_temporal_edge_cases(self):
        """Test temporal annotation edge cases"""
        print("⏰ Testing Temporal Edge Cases...")
        
        temporal_tests = [
            {"name": "Zero Timestamp", "timestamp": 0.0},
            {"name": "Negative Timestamp", "timestamp": -1.0},
            {"name": "Huge Timestamp", "timestamp": 999999.0},
            {"name": "Fractional Precision", "timestamp": 1.23456789},
            {"name": "End Before Start", "timestamp": 10.0, "end_timestamp": 5.0},
            {"name": "Same Start/End", "timestamp": 5.0, "end_timestamp": 5.0},
            {"name": "Microsecond Duration", "timestamp": 1.0, "end_timestamp": 1.000001}
        ]
        
        for test in temporal_tests:
            await self.test_single_temporal_case(test)
            
    async def test_single_temporal_case(self, test_config: Dict[str, Any]):
        """Test single temporal edge case"""
        try:
            annotation_data = {
                "video_id": self.test_video_id,
                "detection_id": f"TEMPORAL_TEST_{int(time.time())}",
                "frame_number": 30,
                "timestamp": test_config["timestamp"],
                "end_timestamp": test_config.get("end_timestamp"),
                "vru_type": "pedestrian",
                "bounding_box": {"x": 100, "y": 100, "width": 50, "height": 100},
                "occluded": False,
                "truncated": False,
                "difficult": False,
                "notes": f"Temporal test: {test_config['name']}",
                "annotator": "temporal_tester",
                "validated": True
            }
            
            response = requests.post(
                f"{self.backend_url}/api/videos/{self.test_video_id}/annotations",
                json=annotation_data,
                timeout=30
            )
            
            # Determine if temporal data is valid
            timestamp = test_config["timestamp"]
            end_timestamp = test_config.get("end_timestamp")
            
            is_valid_temporal = (
                timestamp >= 0 and 
                (end_timestamp is None or end_timestamp > timestamp)
            )
            
            if response.status_code in [200, 201]:
                if is_valid_temporal:
                    status = "✅ PASS (Valid temporal data accepted)"
                else:
                    status = "⚠️ PARTIAL (Invalid temporal data accepted - check validation)"
            elif response.status_code in [400, 422]:
                if not is_valid_temporal:
                    status = "✅ PASS (Invalid temporal data properly rejected)"
                else:
                    status = "❌ FAIL (Valid temporal data improperly rejected)"
            else:
                status = "❌ FAIL (Unexpected response)"
                
            await self.log_result(
                "Temporal Edge Cases",
                test_config["name"],
                status,
                {
                    "timestamp": timestamp,
                    "end_timestamp": end_timestamp,
                    "response_code": response.status_code,
                    "is_valid_temporal": is_valid_temporal
                }
            )
            
        except Exception as e:
            await self.log_result(
                "Temporal Edge Cases",
                test_config["name"],
                "❌ FAIL",
                {"error": str(e), "timestamp": test_config["timestamp"]}
            )
            
    async def test_data_validation_edge_cases(self):
        """Test data validation edge cases"""
        print("🔍 Testing Data Validation Edge Cases...")
        
        validation_tests = [
            {
                "name": "Null Values",
                "modifications": {"vru_type": None, "notes": None}
            },
            {
                "name": "Empty Strings",
                "modifications": {"vru_type": "", "notes": "", "annotator": ""}
            },
            {
                "name": "Very Long Strings",
                "modifications": {
                    "notes": "A" * 10000,
                    "annotator": "B" * 1000,
                    "detection_id": "C" * 500
                }
            },
            {
                "name": "Special Characters",
                "modifications": {
                    "vru_type": "<script>alert('xss')</script>",
                    "notes": "'; DROP TABLE annotations; --",
                    "annotator": "user\x00\x01\x02"
                }
            },
            {
                "name": "Unicode Characters",
                "modifications": {
                    "vru_type": "行人👤",
                    "notes": "测试注释 🚶‍♂️🚴‍♀️🚗",
                    "annotator": "用户名"
                }
            },
            {
                "name": "Invalid JSON Structure",
                "modifications": {
                    "bounding_box": "not_an_object"
                }
            },
            {
                "name": "Missing Required Fields",
                "modifications": {},
                "remove_fields": ["video_id", "frame_number", "timestamp"]
            }
        ]
        
        for test in validation_tests:
            await self.test_single_validation_case(test)
            
    async def test_single_validation_case(self, test_config: Dict[str, Any]):
        """Test single data validation case"""
        try:
            # Start with base valid annotation
            annotation_data = {
                "video_id": self.test_video_id,
                "detection_id": f"VALIDATION_TEST_{int(time.time())}",
                "frame_number": 1,
                "timestamp": 1.0,
                "vru_type": "pedestrian",
                "bounding_box": {"x": 100, "y": 100, "width": 50, "height": 100},
                "occluded": False,
                "truncated": False,
                "difficult": False,
                "notes": "Validation test",
                "annotator": "validation_tester",
                "validated": True
            }
            
            # Apply modifications
            if "modifications" in test_config:
                annotation_data.update(test_config["modifications"])
                
            # Remove fields if specified
            if "remove_fields" in test_config:
                for field in test_config["remove_fields"]:
                    annotation_data.pop(field, None)
                    
            response = requests.post(
                f"{self.backend_url}/api/videos/{self.test_video_id}/annotations",
                json=annotation_data,
                timeout=30
            )
            
            # Determine if data should be valid
            has_required_fields = all(
                field in annotation_data 
                for field in ["video_id", "frame_number", "timestamp", "vru_type", "bounding_box"]
            )
            
            has_dangerous_content = any(
                dangerous in str(annotation_data).lower() 
                for dangerous in ["<script>", "drop table", "\x00"]
            )
            
            if response.status_code in [200, 201]:
                if has_required_fields and not has_dangerous_content:
                    status = "✅ PASS (Valid data accepted)"
                elif has_dangerous_content:
                    status = "❌ FAIL (Dangerous content accepted - security risk)"
                else:
                    status = "⚠️ PARTIAL (Invalid data accepted - check validation)"
            elif response.status_code in [400, 422]:
                if not has_required_fields or has_dangerous_content:
                    status = "✅ PASS (Invalid/dangerous data properly rejected)"
                else:
                    status = "❌ FAIL (Valid data improperly rejected)"
            else:
                status = "❌ FAIL (Unexpected response)"
                
            await self.log_result(
                "Data Validation",
                test_config["name"],
                status,
                {
                    "response_code": response.status_code,
                    "has_required_fields": has_required_fields,
                    "has_dangerous_content": has_dangerous_content,
                    "data_size": len(str(annotation_data)),
                    "response_message": response.text[:200] if response.status_code != 200 else "OK"
                }
            )
            
        except Exception as e:
            await self.log_result(
                "Data Validation",
                test_config["name"],
                "❌ FAIL",
                {"error": str(e)}
            )
            
    async def test_concurrent_annotations(self):
        """Test concurrent annotation operations"""
        print("🔄 Testing Concurrent Annotation Operations...")
        
        concurrency_tests = [
            {"name": "Low Concurrency", "concurrent_ops": 5},
            {"name": "Medium Concurrency", "concurrent_ops": 20},
            {"name": "High Concurrency", "concurrent_ops": 50},
            {"name": "Extreme Concurrency", "concurrent_ops": 100}
        ]
        
        for test in concurrency_tests:
            await self.test_single_concurrency_scenario(test)
            
    async def test_single_concurrency_scenario(self, test_config: Dict[str, Any]):
        """Test single concurrency scenario"""
        start_time = time.time()
        
        try:
            # Create multiple concurrent annotation tasks
            tasks = []
            for i in range(test_config["concurrent_ops"]):
                task = asyncio.create_task(self.create_single_concurrent_annotation(i))
                tasks.append(task)
                
            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Analyze results
            successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
            failed = len(results) - successful
            total_time = time.time() - start_time
            
            success_rate = (successful / len(results)) * 100 if results else 0
            
            # Determine status
            if success_rate >= 90:
                status = "✅ PASS"
            elif success_rate >= 70:
                status = "⚠️ PARTIAL (Good)"
            elif success_rate >= 50:
                status = "⚠️ PARTIAL (Poor)"
            else:
                status = "❌ FAIL"
                
            await self.log_result(
                "Concurrent Operations",
                f"{test_config['name']} ({test_config['concurrent_ops']} ops)",
                status,
                {
                    "concurrent_ops": test_config["concurrent_ops"],
                    "successful": successful,
                    "failed": failed,
                    "success_rate": f"{success_rate:.1f}%",
                    "total_time": total_time,
                    "ops_per_second": len(results) / total_time if total_time > 0 else 0
                }
            )
            
        except Exception as e:
            await self.log_result(
                "Concurrent Operations",
                f"{test_config['name']}",
                "❌ FAIL",
                {"error": str(e), "concurrent_ops": test_config["concurrent_ops"]}
            )
            
    async def create_single_concurrent_annotation(self, index: int) -> Dict[str, Any]:
        """Create a single annotation for concurrency testing"""
        try:
            annotation_data = {
                "video_id": self.test_video_id,
                "detection_id": f"CONCURRENT_TEST_{index}_{int(time.time())}",
                "frame_number": (index % 100) + 1,
                "timestamp": (index % 100) * 0.1,
                "vru_type": ["pedestrian", "cyclist", "vehicle"][index % 3],
                "bounding_box": {
                    "x": 100 + (index % 200),
                    "y": 100 + (index % 150),
                    "width": 50,
                    "height": 100
                },
                "occluded": False,
                "truncated": False,
                "difficult": False,
                "notes": f"Concurrent test annotation {index}",
                "annotator": f"concurrent_user_{index % 5}",
                "validated": True
            }
            
            response = requests.post(
                f"{self.backend_url}/api/videos/{self.test_video_id}/annotations",
                json=annotation_data,
                timeout=30
            )
            
            return {
                "success": response.status_code in [200, 201],
                "status_code": response.status_code,
                "index": index
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "index": index
            }
            
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
        elif "success_rate" in details:
            print(f"    Success Rate: {details['success_rate']}")
            
    async def generate_annotation_test_summary(self):
        """Generate summary of annotation system tests"""
        print("\n" + "="*60)
        print("📊 ANNOTATION SYSTEM EDGE CASE TEST SUMMARY")
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
            
        # Security analysis
        security_issues = [r for r in self.test_results 
                          if "security risk" in r["status"].lower() or 
                             "dangerous content accepted" in r["status"].lower()]
                             
        if security_issues:
            print(f"\n🚨 SECURITY ISSUES DETECTED: {len(security_issues)}")
            for issue in security_issues:
                print(f"  - {issue['test_case']}: {issue['status']}")
        else:
            print("\n🔒 No security issues detected")
            
        # Performance analysis
        volume_tests = [r for r in self.test_results if r["category"] == "Annotation Volume"]
        if volume_tests:
            best_performance = max(volume_tests, 
                                 key=lambda x: x["details"].get("annotations_per_second", 0))
            print(f"\nPerformance Metrics:")
            print(f"  Best Performance: {best_performance['details']['annotations_per_second']:.1f} annotations/sec")
            
        print("="*60)

# Main execution
async def main():
    """Execute annotation system edge case tests"""
    tester = AnnotationSystemEdgeCases()
    await tester.run_all_annotation_edge_cases()

if __name__ == "__main__":
    asyncio.run(main())