"""
Comprehensive Test Suite for Path Management System
Tests path resolution, error handling, and deployment context detection.
"""

import os
import sys
import tempfile
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import uuid

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.path_manager import (
    PathManager, PathType, DeploymentContext,
    ContainerPathResolver, DevelopmentPathResolver, ProductionPathResolver,
    PathResolutionResult
)
from src.utils.error_handling import (
    FileAccessErrorHandler, FileAccessErrorType, 
    handle_file_access_errors, safe_file_operation
)
from src.config.path_config import (
    PathConfigManager, PathConfiguration,
    get_path_config_manager
)


class TestPathManager:
    """Test suite for PathManager class"""
    
    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {"project_root": self.temp_dir}
        self.path_manager = PathManager(self.config)
    
    def teardown_method(self):
        """Cleanup test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_deployment_context_detection(self):
        """Test automatic deployment context detection"""
        # Test container detection
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = True  # Simulate /.dockerenv exists
            path_manager = PathManager()
            assert path_manager.context == DeploymentContext.CONTAINER
        
        # Test production detection
        with patch.dict(os.environ, {'ENVIRONMENT': 'production'}):
            path_manager = PathManager()
            assert path_manager.context == DeploymentContext.PRODUCTION
        
        # Test development detection (default)
        with patch.dict(os.environ, {}, clear=True):
            with patch('os.path.exists', return_value=False):
                path_manager = PathManager()
                assert path_manager.context == DeploymentContext.DEVELOPMENT
    
    def test_path_resolution_basic(self):
        """Test basic path resolution functionality"""
        # Test relative path resolution
        result = self.path_manager.resolve_path("test.txt", PathType.UPLOAD)
        
        assert isinstance(result, PathResolutionResult)
        assert result.absolute_path
        assert result.relative_path
        assert result.context == DeploymentContext.DEVELOPMENT
        
        # Path should be absolute
        assert Path(result.absolute_path).is_absolute()
        
        # Should contain upload directory
        assert "upload" in result.absolute_path.lower()
    
    def test_absolute_path_resolution(self):
        """Test resolution of absolute paths"""
        # Create a test file
        test_file = Path(self.temp_dir) / "test_absolute.txt"
        test_file.write_text("test content")
        
        result = self.path_manager.resolve_path(str(test_file), PathType.VIDEO)
        
        assert result.exists == True
        assert result.absolute_path == str(test_file)
    
    def test_directory_creation(self):
        """Test automatic directory creation"""
        # Test directory creation
        upload_dir = self.path_manager.ensure_directory_exists(PathType.UPLOAD)
        
        assert upload_dir.exists()
        assert upload_dir.is_dir()
    
    def test_path_validation(self):
        """Test path validation functionality"""
        # Create a test file
        test_file = Path(self.temp_dir) / "uploads" / "valid_test.mp4"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("test video content")
        
        validation = self.path_manager.validate_path_access(str(test_file), PathType.VIDEO)
        
        assert validation["valid"] == True
        assert validation["exists"] == True
        assert validation["writable"] == True
        assert validation["context"] == "development"
    
    def test_migration_functionality(self):
        """Test path migration for relative to absolute paths"""
        relative_paths = [
            "uploads/video1.mp4",
            "uploads/video2.avi",
            "screenshots/shot1.jpg"
        ]
        
        migrations = self.path_manager.migrate_relative_paths(relative_paths, PathType.UPLOAD)
        
        assert len(migrations) == 3
        for old_path, new_path in migrations.items():
            assert old_path in relative_paths
            if new_path:  # Successful migration
                assert Path(new_path).is_absolute()


class TestContainerPathResolver:
    """Test suite for ContainerPathResolver"""
    
    def setup_method(self):
        """Setup container resolver"""
        self.resolver = ContainerPathResolver("/app")
    
    def test_container_base_directories(self):
        """Test container base directory resolution"""
        upload_base = self.resolver.get_base_directory(PathType.UPLOAD)
        assert str(upload_base) == "/app/uploads"
        
        screenshot_base = self.resolver.get_base_directory(PathType.SCREENSHOT)
        assert str(screenshot_base) == "/app/screenshots"
    
    def test_container_path_resolution(self):
        """Test path resolution in container context"""
        result = self.resolver.resolve_path("test.jpg", PathType.SCREENSHOT)
        
        assert result.context == DeploymentContext.CONTAINER
        assert result.absolute_path.startswith("/app/screenshots")
        assert "test.jpg" in result.absolute_path
    
    def test_external_path_handling(self):
        """Test handling of external absolute paths"""
        external_path = "/home/user/external.mp4"
        result = self.resolver.resolve_path(external_path, PathType.VIDEO)
        
        # Should be moved to container structure
        assert result.absolute_path.startswith("/app/videos")
        assert len(result.errors) > 0  # Should have warning about external path


class TestDevelopmentPathResolver:
    """Test suite for DevelopmentPathResolver"""
    
    def setup_method(self):
        """Setup development resolver"""
        self.temp_dir = tempfile.mkdtemp()
        self.resolver = DevelopmentPathResolver(self.temp_dir)
    
    def teardown_method(self):
        """Cleanup"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_project_root_detection(self):
        """Test automatic project root detection"""
        # Create a git marker
        git_dir = Path(self.temp_dir) / ".git"
        git_dir.mkdir()
        
        resolver = DevelopmentPathResolver()
        # Should find a project root (may not be our temp dir in test environment)
        assert resolver.project_root.exists()
    
    def test_development_directory_structure(self):
        """Test development directory structure creation"""
        result = self.resolver.resolve_path("test.mp4", PathType.VIDEO)
        
        assert result.context == DeploymentContext.DEVELOPMENT
        assert str(self.temp_dir) in result.absolute_path
        
        # Parent directory should be created
        assert Path(result.absolute_path).parent.exists()


class TestProductionPathResolver:
    """Test suite for ProductionPathResolver"""
    
    def setup_method(self):
        """Setup production resolver"""
        self.resolver = ProductionPathResolver()
    
    def test_production_security(self):
        """Test production security restrictions"""
        # Test that external paths are secured
        malicious_path = "/etc/passwd"
        result = self.resolver.resolve_path(malicious_path, PathType.UPLOAD)
        
        # Should be moved to secure location
        assert result.absolute_path.startswith("/var/lib/ai-validation")
        assert len(result.errors) > 0  # Should have security warning
    
    def test_production_directory_permissions(self):
        """Test production directory structure"""
        upload_base = self.resolver.get_base_directory(PathType.UPLOAD)
        assert str(upload_base) == "/var/lib/ai-validation/uploads"


class TestFileAccessErrorHandler:
    """Test suite for FileAccessErrorHandler"""
    
    def setup_method(self):
        """Setup error handler"""
        self.handler = FileAccessErrorHandler()
    
    def test_error_classification(self):
        """Test error type classification"""
        # Test file not found
        error_info = self.handler.handle_file_access_error(
            FileNotFoundError("No such file"), 
            "/nonexistent/file.txt"
        )
        
        assert error_info.error_type == FileAccessErrorType.PATH_NOT_FOUND
        assert len(error_info.recovery_suggestions) > 0
    
    def test_permission_error_handling(self):
        """Test permission error handling"""
        error_info = self.handler.handle_file_access_error(
            PermissionError("Access denied"),
            "/restricted/file.txt"
        )
        
        assert error_info.error_type == FileAccessErrorType.PERMISSION_DENIED
        assert "permission" in error_info.recovery_suggestions[0].lower()
    
    def test_error_statistics(self):
        """Test error statistics tracking"""
        # Generate some errors
        for i in range(5):
            self.handler.handle_file_access_error(
                FileNotFoundError("Test error"), 
                f"/test{i}.txt"
            )
        
        stats = self.handler.get_error_statistics()
        
        assert stats["total_errors"] == 5
        assert "path_not_found" in stats["error_types"]
        assert stats["error_types"]["path_not_found"] == 5


class TestErrorHandlingDecorators:
    """Test error handling decorators and context managers"""
    
    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Cleanup"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_handle_file_access_errors_decorator(self):
        """Test the file access error decorator"""
        
        @handle_file_access_errors(return_none_on_error=True)
        def failing_function(path):
            with open(path, 'r') as f:
                return f.read()
        
        # Test with non-existent file
        result = failing_function("/nonexistent/file.txt")
        assert result is None  # Should return None on error
    
    def test_safe_file_operation_context_manager(self):
        """Test safe file operation context manager"""
        # Create a test file
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_text("test content")
        
        # Test successful operation
        with safe_file_operation(test_file, "read") as resolved_path:
            assert resolved_path.exists()
            content = resolved_path.read_text()
            assert content == "test content"


class TestPathConfiguration:
    """Test suite for PathConfigManager"""
    
    def setup_method(self):
        """Setup config manager"""
        self.config_manager = PathConfigManager()
    
    def test_default_configurations_loaded(self):
        """Test that default configurations are loaded"""
        dev_config = self.config_manager.get_configuration(
            DeploymentContext.DEVELOPMENT, 
            PathType.UPLOAD
        )
        
        assert dev_config is not None
        assert dev_config.path_type == PathType.UPLOAD
        assert dev_config.base_directory == "uploads"
        assert dev_config.max_size_mb == 1000
    
    def test_configuration_validation(self):
        """Test configuration validation"""
        errors = self.config_manager.validate_configuration(DeploymentContext.DEVELOPMENT)
        
        # Should have no critical errors for development
        critical_errors = [e for e in errors if "Missing configuration" in e]
        assert len(critical_errors) == 0
    
    def test_environment_override(self):
        """Test environment variable override"""
        with patch.dict(os.environ, {
            'AI_VALIDATION_PATH_DEVELOPMENT_UPLOAD_MAX_SIZE_MB': '2000'
        }):
            config_manager = PathConfigManager()
            dev_config = config_manager.get_configuration(
                DeploymentContext.DEVELOPMENT, 
                PathType.UPLOAD
            )
            
            assert dev_config.max_size_mb == 2000


class TestIntegration:
    """Integration tests for the complete path management system"""
    
    def setup_method(self):
        """Setup integration test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {"project_root": self.temp_dir}
    
    def teardown_method(self):
        """Cleanup"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_end_to_end_path_resolution(self):
        """Test complete path resolution workflow"""
        # Create path manager
        path_manager = PathManager(self.config)
        
        # Test file upload simulation
        uploaded_file = "user_video.mp4"
        result = path_manager.resolve_path(uploaded_file, PathType.UPLOAD)
        
        # Should resolve successfully
        assert result.errors == []
        assert Path(result.absolute_path).parent.exists()
        
        # Test screenshot generation
        screenshot_file = f"screenshot_{uuid.uuid4().hex[:8]}.jpg"
        screenshot_result = path_manager.resolve_path(screenshot_file, PathType.SCREENSHOT)
        
        assert screenshot_result.errors == []
        assert "screenshot" in screenshot_result.absolute_path.lower()
    
    def test_cross_deployment_compatibility(self):
        """Test that paths work across different deployment contexts"""
        # Test development context
        dev_manager = PathManager({"project_root": self.temp_dir})
        dev_result = dev_manager.resolve_path("test.mp4", PathType.VIDEO)
        
        # Test container context
        with patch('src.utils.path_manager.PathManager._detect_deployment_context') as mock_context:
            mock_context.return_value = DeploymentContext.CONTAINER
            container_manager = PathManager()
            container_result = container_manager.resolve_path("test.mp4", PathType.VIDEO)
        
        # Both should resolve successfully but to different absolute paths
        assert dev_result.errors == []
        assert container_result.errors == []
        assert dev_result.absolute_path != container_result.absolute_path
    
    def test_error_recovery_workflow(self):
        """Test error handling and recovery workflow"""
        path_manager = PathManager(self.config)
        
        # Simulate file access error
        nonexistent_path = "/definitely/does/not/exist/file.mp4"
        
        with pytest.raises(FileNotFoundError):
            with open(nonexistent_path, 'r'):
                pass
        
        # Test that path manager handles the error gracefully
        result = path_manager.resolve_path(nonexistent_path, PathType.VIDEO)
        
        # Should still provide a valid path (fallback)
        assert result.absolute_path
        assert Path(result.absolute_path).is_absolute()


@pytest.fixture
def temp_database():
    """Provide a temporary database for testing"""
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    
    yield temp_db.name
    
    # Cleanup
    try:
        os.unlink(temp_db.name)
    except OSError:
        pass


class TestDatabaseIntegration:
    """Test database integration with path management"""
    
    def test_path_storage_simulation(self, temp_database):
        """Test that absolute paths would be stored correctly in database"""
        path_manager = PathManager()
        
        # Simulate video upload
        video_path = "uploads/test_video.mp4"
        result = path_manager.resolve_path(video_path, PathType.VIDEO)
        
        # This would be stored in the database
        stored_absolute_path = result.absolute_path
        stored_relative_path = result.relative_path
        
        # Verify both paths are valid
        assert Path(stored_absolute_path).is_absolute()
        assert not Path(stored_relative_path).is_absolute()
        
        # Simulate retrieval and verification
        retrieved_result = path_manager.resolve_path(stored_absolute_path, PathType.VIDEO)
        assert retrieved_result.absolute_path == stored_absolute_path


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])