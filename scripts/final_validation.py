#!/usr/bin/env python3
"""
Final Production Readiness Validation
Comprehensive check of all platform components
"""
import sys
import os
from pathlib import Path

def check_database_schema():
    """Check database schema is correct"""
    print("🔍 Checking Database Schema...")
    
    backend_path = Path(__file__).parent.parent / "ai-model-validation-platform" / "backend"
    sys.path.append(str(backend_path))
    
    try:
        from sqlalchemy import inspect
        from database import engine
        
        inspector = inspect(engine)
        
        # Check videos table
        if 'videos' not in inspector.get_table_names():
            print("❌ Videos table missing")
            return False
        
        columns = [col['name'] for col in inspector.get_columns('videos')]
        required_columns = ['id', 'filename', 'processing_status', 'ground_truth_generated', 'project_id']
        
        missing = [col for col in required_columns if col not in columns]
        if missing:
            print(f"❌ Missing columns in videos table: {missing}")
            return False
        
        print("✅ Database schema validated")
        return True
        
    except Exception as e:
        print(f"❌ Database validation failed: {e}")
        return False

def check_models():
    """Check models are importable and have required attributes"""
    print("📦 Checking Models...")
    
    try:
        backend_path = Path(__file__).parent.parent / "ai-model-validation-platform" / "backend"
        sys.path.append(str(backend_path))
        
        from models import Video, Project, GroundTruthObject
        
        # Check Video model has required attributes
        required_attrs = ['id', 'filename', 'processing_status', 'ground_truth_generated']
        for attr in required_attrs:
            if not hasattr(Video, attr):
                print(f"❌ Video model missing attribute: {attr}")
                return False
        
        print("✅ Models validated")
        return True
        
    except Exception as e:
        print(f"❌ Model validation failed: {e}")
        return False

def check_services():
    """Check services are working"""
    print("⚙️ Checking Services...")
    
    try:
        from services.video_processing_workflow import VideoProcessingWorkflow
        from database import SessionLocal
        
        db = SessionLocal()
        workflow = VideoProcessingWorkflow(db)
        
        if not hasattr(workflow, 'update_processing_status'):
            print("❌ Video processing workflow missing required methods")
            return False
        
        db.close()
        print("✅ Services validated")
        return True
        
    except Exception as e:
        print(f"❌ Service validation failed: {e}")
        return False

def check_schemas():
    """Check enhanced schemas"""
    print("📋 Checking Schemas...")
    
    try:
        from schemas_enhanced import ProcessingStatusEnum, VideoResponse
        
        # Check enum values
        expected_statuses = ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']
        actual_statuses = [status.name for status in ProcessingStatusEnum]
        
        missing = [s for s in expected_statuses if s not in actual_statuses]
        if missing:
            print(f"❌ Missing status enum values: {missing}")
            return False
        
        print("✅ Schemas validated")
        return True
        
    except Exception as e:
        print(f"❌ Schema validation failed: {e}")
        return False

def check_file_structure():
    """Check all required files exist"""
    print("📁 Checking File Structure...")
    
    base_path = Path(__file__).parent.parent
    
    required_files = [
        "ai-model-validation-platform/backend/main.py",
        "ai-model-validation-platform/backend/models.py", 
        "ai-model-validation-platform/backend/database.py",
        "ai-model-validation-platform/backend/schemas_enhanced.py",
        "ai-model-validation-platform/backend/services/video_processing_workflow.py",
        "scripts/database_migration.py",
        "scripts/fix_video_upload.py",
        "docs/COMPREHENSIVE_FIX_SUMMARY.md"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not (base_path / file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    
    print("✅ File structure validated")
    return True

def main():
    """Run final validation"""
    print("🚀 Final Production Readiness Validation")
    print("=" * 50)
    
    checks = [
        check_file_structure,
        check_models,
        check_schemas, 
        check_database_schema,
        check_services
    ]
    
    passed = 0
    total = len(checks)
    
    for check in checks:
        if check():
            passed += 1
        print()  # Add spacing
    
    print("=" * 50)
    print(f"📊 FINAL VALIDATION RESULTS")
    print("=" * 50)
    print(f"Tests Passed: {passed}/{total}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("\n🎉 ALL VALIDATIONS PASSED!")
        print("✅ Platform is PRODUCTION READY")
        print("\n🚀 Ready for deployment!")
        return 0
    else:
        print(f"\n⚠️ {total-passed} validations failed")
        print("❌ Platform needs fixes before production")
        return 1

if __name__ == "__main__":
    sys.exit(main())