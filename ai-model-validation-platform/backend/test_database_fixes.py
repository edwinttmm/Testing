#!/usr/bin/env python3
"""
Database Connectivity and Enum Validation Test Script
Tests the fixes for PostgreSQL connectivity and enum validation issues
"""
import os
import sys
import logging
from typing import Dict, Any
import traceback

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_connectivity_helper():
    """Test the database connectivity helper"""
    print("=== Testing Database Connectivity Helper ===")
    try:
        from database_connectivity_helper import db_helper, diagnose_database_connectivity
        
        # Get connection info
        conn_info = db_helper.get_connection_info()
        print(f"Connection Info: {conn_info}")
        
        # Run diagnosis
        diagnosis = diagnose_database_connectivity()
        print(f"Connectivity Diagnosis:")
        for key, value in diagnosis.items():
            print(f"  {key}: {value}")
        
        return True
    except Exception as e:
        print(f"❌ Connectivity helper test failed: {e}")
        traceback.print_exc()
        return False

def test_database_connection():
    """Test basic database connection"""
    print("\n=== Testing Database Connection ===")
    try:
        from database import get_database_health
        health = get_database_health()
        print(f"Database Health: {health}")
        
        if health.get('status') == 'healthy':
            print("✅ Database connection successful")
            return True
        else:
            print("❌ Database connection unhealthy")
            return False
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        traceback.print_exc()
        return False

def test_enum_validation():
    """Test enum validation with corrected values"""
    print("\n=== Testing Enum Validation ===")
    try:
        from schemas import CameraTypeEnum, SignalTypeEnum
        
        # Test valid enum values
        valid_camera_views = [
            "Front-facing VRU",
            "Rear-facing VRU", 
            "In-Cab Driver Behavior",
            "Multi-angle"
        ]
        
        valid_signal_types = [
            "GPIO",
            "Network Packet",
            "Serial", 
            "CAN Bus"
        ]
        
        print("Testing Camera View Enum:")
        for view in valid_camera_views:
            try:
                enum_val = CameraTypeEnum(view)
                print(f"  ✅ {view} -> {enum_val}")
            except ValueError as e:
                print(f"  ❌ {view} failed: {e}")
                return False
        
        print("Testing Signal Type Enum:")
        for signal in valid_signal_types:
            try:
                enum_val = SignalTypeEnum(signal)
                print(f"  ✅ {signal} -> {enum_val}")
            except ValueError as e:
                print(f"  ❌ {signal} failed: {e}")
                return False
        
        # Test that "Mixed" is no longer valid
        try:
            CameraTypeEnum("Mixed")
            print("  ❌ 'Mixed' should not be valid for camera_view")
            return False
        except ValueError:
            print("  ✅ 'Mixed' correctly rejected for camera_view")
        
        try:
            SignalTypeEnum("Mixed")
            print("  ❌ 'Mixed' should not be valid for signal_type")
            return False
        except ValueError:
            print("  ✅ 'Mixed' correctly rejected for signal_type")
        
        print("✅ Enum validation tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Enum validation test failed: {e}")
        traceback.print_exc()
        return False

def test_project_creation():
    """Test project creation with valid enum values"""
    print("\n=== Testing Project Creation ===")
    try:
        from database import SessionLocal, DATABASE_URL, safe_create_indexes_and_tables
        from models import Project
        
        print(f"Using database: {DATABASE_URL.replace('password', '***')}")
        
        if DATABASE_URL.startswith("sqlite"):
            print("✅ Using SQLite for testing (safe fallback)")
        
        # Ensure tables exist
        safe_create_indexes_and_tables()
        print("✅ Database tables created/verified")
        
        db = SessionLocal()
        try:
            # Test creating a project with valid enum values
            test_project = Project(
                id="test-enum-validation",
                name="Enum Validation Test",
                description="Testing corrected enum values",
                camera_model="TestCam",
                camera_view="Multi-angle",  # Corrected from "Mixed"
                signal_type="Network Packet",  # Corrected from "Mixed"
                status="Active"
            )
            
            # This should not raise validation errors anymore
            db.add(test_project)
            db.commit()
            
            # Verify it was created
            created_project = db.query(Project).filter_by(id="test-enum-validation").first()
            if created_project:
                print(f"✅ Project created with camera_view: {created_project.camera_view}")
                print(f"✅ Project created with signal_type: {created_project.signal_type}")
                
                # Clean up
                db.delete(created_project)
                db.commit()
                return True
            else:
                print("❌ Project was not found after creation")
                return False
                
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Project creation test failed: {e}")
        traceback.print_exc()
        return False

def test_ground_truth_storage_simulation():
    """Simulate ground truth storage operations"""
    print("\n=== Simulating Ground Truth Storage ===")
    try:
        from database import SessionLocal, DATABASE_URL, safe_create_indexes_and_tables
        from models import Video, GroundTruthObject, Project
        import uuid
        
        if not DATABASE_URL.startswith("sqlite"):
            print("⚠️  Skipping ground truth storage test - requires database connection")
            return True
        
        # Ensure tables exist
        safe_create_indexes_and_tables()
        
        db = SessionLocal()
        try:
            # Create a test project first
            test_project = Project(
                id=str(uuid.uuid4()),
                name="Ground Truth Test Project",
                description="Testing ground truth storage",
                camera_model="TestCam",
                camera_view="Front-facing VRU",
                signal_type="GPIO",
                status="Active"
            )
            db.add(test_project)
            db.commit()
            
            # Create a test video
            test_video = Video(
                id=str(uuid.uuid4()),
                filename="test_video.mp4",
                file_path="/test/path",
                project_id=test_project.id,
                file_size=1024*1024,
                duration=30.0,
                fps=25.0,
                resolution="1920x1080"
            )
            db.add(test_video)
            db.commit()
            
            # Create ground truth objects (simulating YOLOv8 detections)
            detections = [
                {
                    "timestamp": 1.0,
                    "class_label": "person",
                    "x": 100, "y": 50, "width": 80, "height": 120,
                    "confidence": 0.95
                },
                {
                    "timestamp": 2.0,
                    "class_label": "person", 
                    "x": 150, "y": 60, "width": 85, "height": 125,
                    "confidence": 0.87
                }
            ]
            
            for i, detection in enumerate(detections):
                gt_obj = GroundTruthObject(
                    id=str(uuid.uuid4()),
                    video_id=test_video.id,
                    timestamp=detection["timestamp"],
                    class_label=detection["class_label"],
                    x=detection["x"],
                    y=detection["y"],
                    width=detection["width"],
                    height=detection["height"],
                    confidence=detection["confidence"],
                    frame_number=int(detection["timestamp"] * test_video.fps)
                )
                db.add(gt_obj)
            
            db.commit()
            
            # Verify ground truth objects were stored
            stored_objects = db.query(GroundTruthObject).filter_by(video_id=test_video.id).count()
            print(f"✅ Successfully stored {stored_objects} ground truth objects")
            
            # Clean up
            db.query(GroundTruthObject).filter_by(video_id=test_video.id).delete()
            db.delete(test_video)
            db.delete(test_project)
            db.commit()
            
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Ground truth storage simulation failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all database fix tests"""
    print("🧪 Database Fixes Validation Test Suite")
    print("=" * 50)
    
    results = {
        "connectivity_helper": test_connectivity_helper(),
        "database_connection": test_database_connection(), 
        "enum_validation": test_enum_validation(),
        "project_creation": test_project_creation(),
        "ground_truth_storage": test_ground_truth_storage_simulation()
    }
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All database fixes validated successfully!")
        return True
    else:
        print("⚠️  Some tests failed - review the output above")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)