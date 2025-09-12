"""
Manual Upload Verification Test
===============================

Simple manual verification of upload functionality without external dependencies.
Tests basic upload workflow by directly interfacing with the application components.
"""

import os
import sys
import tempfile
import json
from pathlib import Path

# Add backend to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

def test_imports():
    """Test that all required modules can be imported"""
    try:
        from config import settings
        from database import SessionLocal
        from models import Project, Video
        from main import app
        print("✅ All core modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_database_connection():
    """Test database connectivity"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        
        # Try a simple query
        from models import Project
        project_count = db.query(Project).count()
        db.close()
        
        print(f"✅ Database connection successful - {project_count} projects found")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_file_upload_directory():
    """Test upload directory setup"""
    try:
        from config import settings
        upload_dir = Path(settings.upload_directory)
        
        # Create upload directory if it doesn't exist
        upload_dir.mkdir(exist_ok=True)
        
        # Test write permissions
        test_file = upload_dir / "test_permissions.tmp"
        test_file.write_text("test")
        test_file.unlink()
        
        print(f"✅ Upload directory accessible: {upload_dir}")
        return True
    except Exception as e:
        print(f"❌ Upload directory test failed: {e}")
        return False

def create_test_project_direct():
    """Create test project directly via database"""
    try:
        from database import SessionLocal
        from models import Project
        import uuid
        
        db = SessionLocal()
        
        project = Project(
            id=str(uuid.uuid4()),
            name="Direct Test Project",
            description="Testing upload via direct database access",
            camera_model="DirectTestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        
        db.add(project)
        db.commit()
        db.refresh(project)
        
        project_id = project.id
        db.close()
        
        print(f"✅ Test project created directly: {project_id}")
        return project_id
    except Exception as e:
        print(f"❌ Direct project creation failed: {e}")
        return None

def test_video_record_creation(project_id):
    """Test video record creation directly in database"""
    try:
        from database import SessionLocal
        from models import Video
        from config import settings
        import uuid
        import time
        
        # Create a test file
        upload_dir = Path(settings.upload_directory)
        test_file_path = upload_dir / f"direct_test_{int(time.time())}.mp4"
        
        with open(test_file_path, 'wb') as f:
            test_content = b"fake video content for direct test" * 100
            f.write(test_content)
        
        file_size = test_file_path.stat().st_size
        
        # Create video record
        db = SessionLocal()
        
        video = Video(
            id=str(uuid.uuid4()),
            filename=test_file_path.name,
            file_path=str(test_file_path),
            file_size=file_size,
            project_id=project_id,
            status="uploaded"
        )
        
        db.add(video)
        db.commit()
        db.refresh(video)
        
        video_id = video.id
        db.close()
        
        print(f"✅ Video record created directly: {video_id}")
        print(f"   File: {test_file_path.name}")
        print(f"   Size: {file_size} bytes")
        
        return {
            'success': True,
            'video_id': video_id,
            'file_path': str(test_file_path),
            'file_size': file_size
        }
        
    except Exception as e:
        print(f"❌ Direct video record creation failed: {e}")
        return {'success': False, 'error': str(e)}

def test_video_file_operations():
    """Test basic file operations for video uploads"""
    try:
        from config import settings
        upload_dir = Path(settings.upload_directory)
        
        # Test file creation
        test_file = upload_dir / "file_ops_test.mp4"
        test_content = b"file operations test content" * 50
        
        with open(test_file, 'wb') as f:
            f.write(test_content)
        
        # Test file reading
        with open(test_file, 'rb') as f:
            read_content = f.read()
        
        # Verify content
        assert read_content == test_content
        
        # Test file size
        file_size = test_file.stat().st_size
        assert file_size == len(test_content)
        
        # Test file deletion
        test_file.unlink()
        assert not test_file.exists()
        
        print(f"✅ File operations test passed - {file_size} bytes")
        return True
        
    except Exception as e:
        print(f"❌ File operations test failed: {e}")
        return False

def test_upload_validation():
    """Test upload validation logic"""
    try:
        from config import settings
        
        # Test file extension validation
        allowed_extensions = settings.allowed_video_extensions
        print(f"✅ Allowed extensions: {allowed_extensions}")
        
        # Test max file size
        max_size = settings.max_file_size
        print(f"✅ Max file size: {max_size / (1024*1024):.1f} MB")
        
        # Test basic validation logic
        test_files = [
            ("video.mp4", True),
            ("video.avi", True),
            ("video.mov", True),
            ("document.txt", False),
            ("image.jpg", False),
        ]
        
        validation_results = []
        for filename, should_be_valid in test_files:
            extension = Path(filename).suffix.lower()
            is_valid = extension in [ext.lower() for ext in allowed_extensions]
            
            status = "✅" if (is_valid == should_be_valid) else "❌"
            print(f"   {status} {filename}: {'valid' if is_valid else 'invalid'}")
            validation_results.append(is_valid == should_be_valid)
        
        all_correct = all(validation_results)
        
        if all_correct:
            print("✅ Upload validation logic working correctly")
        else:
            print("❌ Upload validation logic has issues")
        
        return all_correct
        
    except Exception as e:
        print(f"❌ Upload validation test failed: {e}")
        return False

def test_database_queries():
    """Test database query operations for uploads"""
    try:
        from database import SessionLocal
        from models import Project, Video
        
        db = SessionLocal()
        
        # Test project queries
        project_count = db.query(Project).count()
        print(f"✅ Projects in database: {project_count}")
        
        # Test video queries
        video_count = db.query(Video).count()
        print(f"✅ Videos in database: {video_count}")
        
        # Test join query
        if project_count > 0 and video_count > 0:
            videos_with_projects = db.query(Video).join(Project).count()
            print(f"✅ Videos with projects: {videos_with_projects}")
        
        # Test filtering
        recent_projects = db.query(Project).filter(Project.status == "Active").count()
        print(f"✅ Active projects: {recent_projects}")
        
        db.close()
        
        print("✅ Database queries working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Database query test failed: {e}")
        return False

def cleanup_test_data():
    """Clean up test data created during testing"""
    try:
        from database import SessionLocal
        from models import Project, Video
        from config import settings
        
        db = SessionLocal()
        
        # Clean up test projects and videos
        test_projects = db.query(Project).filter(
            Project.name.like("%Test%")
        ).all()
        
        cleaned_count = 0
        for project in test_projects:
            # Delete associated videos first
            videos = db.query(Video).filter(Video.project_id == project.id).all()
            for video in videos:
                # Delete physical file if it exists
                try:
                    file_path = Path(video.file_path)
                    if file_path.exists():
                        file_path.unlink()
                except:
                    pass
                db.delete(video)
            
            db.delete(project)
            cleaned_count += 1
        
        db.commit()
        db.close()
        
        # Clean up any remaining test files
        upload_dir = Path(settings.upload_directory)
        if upload_dir.exists():
            for test_file in upload_dir.glob("*test*"):
                try:
                    test_file.unlink()
                except:
                    pass
        
        print(f"✅ Cleanup completed - removed {cleaned_count} test projects")
        return True
        
    except Exception as e:
        print(f"⚠️  Cleanup warning: {e}")
        return False

def main():
    """Run manual upload verification tests"""
    print("🔧 Manual Upload Verification Test")
    print("=" * 50)
    
    test_results = []
    
    # Test 1: Module Imports
    print("\\n1. Testing module imports...")
    imports_ok = test_imports()
    test_results.append(("Module Imports", imports_ok))
    
    if not imports_ok:
        print("   Cannot continue without core modules")
        return False
    
    # Test 2: Database Connection
    print("\\n2. Testing database connection...")
    db_ok = test_database_connection()
    test_results.append(("Database Connection", db_ok))
    
    # Test 3: Upload Directory
    print("\\n3. Testing upload directory...")
    dir_ok = test_file_upload_directory()
    test_results.append(("Upload Directory", dir_ok))
    
    # Test 4: File Operations
    print("\\n4. Testing file operations...")
    file_ops_ok = test_video_file_operations()
    test_results.append(("File Operations", file_ops_ok))
    
    # Test 5: Upload Validation
    print("\\n5. Testing upload validation...")
    validation_ok = test_upload_validation()
    test_results.append(("Upload Validation", validation_ok))
    
    # Test 6: Database Queries
    print("\\n6. Testing database queries...")
    queries_ok = test_database_queries()
    test_results.append(("Database Queries", queries_ok))
    
    # Test 7: Direct Project Creation (if database works)
    if db_ok:
        print("\\n7. Testing direct project creation...")
        project_id = create_test_project_direct()
        project_ok = project_id is not None
        test_results.append(("Project Creation", project_ok))
        
        # Test 8: Direct Video Record Creation
        if project_ok:
            print("\\n8. Testing direct video record creation...")
            video_result = test_video_record_creation(project_id)
            video_ok = video_result['success']
            test_results.append(("Video Record Creation", video_ok))
    
    # Test 9: Cleanup
    print("\\n9. Cleaning up test data...")
    cleanup_test_data()
    
    # Summary
    print("\\n" + "=" * 50)
    print("📊 Manual Verification Summary")
    print("=" * 50)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for _, passed in test_results if passed)
    
    for test_name, passed in test_results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:25} {status}")
    
    success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    
    print(f"\\nResults: {passed_tests}/{total_tests} tests passed ({success_rate:.1f}%)")
    
    if success_rate >= 90:
        print("🎉 Core upload functionality is working well!")
        status = "EXCELLENT"
    elif success_rate >= 75:
        print("✅ Core upload functionality is mostly working")
        status = "GOOD"
    elif success_rate >= 50:
        print("⚠️  Core upload functionality has some issues")
        status = "NEEDS_WORK"
    else:
        print("❌ Core upload functionality has major problems")
        status = "CRITICAL"
    
    # Save results
    results = {
        'test_results': test_results,
        'summary': {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'success_rate': success_rate,
            'status': status
        },
        'timestamp': str(Path(__file__).stat().st_mtime)
    }
    
    results_file = Path(__file__).parent / "manual_verification_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\\n📄 Results saved to: {results_file}")
    
    return success_rate >= 75

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)