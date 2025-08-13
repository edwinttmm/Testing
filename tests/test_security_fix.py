#!/usr/bin/env python3
"""
Security test for path traversal vulnerability fix
"""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch

# Add the backend directory to the path
sys.path.insert(0, '/workspaces/Testing/ai-model-validation-platform/backend')

from main import generate_secure_filename, secure_join_path, ALLOWED_VIDEO_EXTENSIONS
from fastapi import HTTPException


def test_generate_secure_filename_valid_extension():
    """Test that valid extensions generate secure filenames"""
    filename = "test_video.mp4"
    secure_name, extension = generate_secure_filename(filename)
    
    assert extension == '.mp4'
    assert secure_name.endswith('.mp4')
    assert len(secure_name) > 10  # UUID + extension should be longer than original
    assert not secure_name.startswith('test_video')  # Should not contain original name


def test_generate_secure_filename_invalid_extension():
    """Test that invalid extensions are rejected"""
    with pytest.raises(HTTPException) as exc_info:
        generate_secure_filename("malicious.exe")
    
    assert exc_info.value.status_code == 400
    assert "Invalid file format" in str(exc_info.value.detail)


def test_generate_secure_filename_path_traversal_attempt():
    """Test that path traversal attempts in filename are handled properly"""
    # The generate_secure_filename function only validates extensions
    # Path traversal protection is handled by secure_join_path
    filename = "../../../etc/passwd.mp4"
    secure_name, extension = generate_secure_filename(filename)
    
    # Should generate a secure UUID-based filename regardless of path components in original
    assert extension == '.mp4'
    assert secure_name.endswith('.mp4')
    assert not secure_name.startswith('../')  # Should not contain original path components
    
    # The secure filename should be safe to use
    assert len(secure_name.split('-')) >= 4  # UUID format


def test_generate_secure_filename_empty():
    """Test that empty filename is rejected"""
    with pytest.raises(HTTPException) as exc_info:
        generate_secure_filename("")
    
    assert exc_info.value.status_code == 400
    assert "Filename cannot be empty" in str(exc_info.value.detail)


def test_secure_join_path_valid():
    """Test that valid paths work correctly"""
    base_dir = "/tmp/uploads"
    filename = "safe_file.mp4"
    
    result = secure_join_path(base_dir, filename)
    expected = str(Path(base_dir).resolve() / filename)
    
    assert result == expected


def test_secure_join_path_traversal_attack():
    """Test that path traversal attacks are blocked"""
    base_dir = "/tmp/uploads"
    malicious_filename = "../../../etc/passwd"
    
    with pytest.raises(HTTPException) as exc_info:
        secure_join_path(base_dir, malicious_filename)
    
    assert exc_info.value.status_code == 400
    assert "Invalid file path detected" in str(exc_info.value.detail)


def test_secure_join_path_complex_traversal():
    """Test that complex path traversal attempts are blocked"""
    base_dir = "/tmp/uploads"
    malicious_patterns = [
        "../../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config\\sam",
        "../uploads/../../../etc/shadow",
        "file.mp4/../../sensitive_data.txt",
        "./../../etc/passwd"
    ]
    
    for pattern in malicious_patterns:
        try:
            result = secure_join_path(base_dir, pattern)
            # If we get here, the function didn't raise an exception
            # Let's check if the result is actually safe
            base_resolved = Path(base_dir).resolve()
            result_path = Path(result)
            
            # Ensure result is within base directory
            try:
                result_path.relative_to(base_resolved)
                print(f"WARNING: Pattern '{pattern}' was allowed, result: {result}")
            except ValueError:
                # This is actually bad - the function should have raised an exception
                assert False, f"Pattern '{pattern}' should have been blocked but resulted in: {result}"
                
        except HTTPException as exc:
            assert exc.status_code == 400
            assert "Invalid file path detected" in str(exc.detail)


def test_allowed_extensions_completeness():
    """Test that all expected video extensions are allowed"""
    expected_extensions = {'.mp4', '.avi', '.mov', '.mkv'}
    assert ALLOWED_VIDEO_EXTENSIONS == expected_extensions


if __name__ == "__main__":
    # Run basic tests to verify the fix
    print("Testing security fix for path traversal vulnerability...")
    
    try:
        test_generate_secure_filename_valid_extension()
        print("✓ Valid extension test passed")
        
        test_generate_secure_filename_invalid_extension()
        print("✓ Invalid extension test passed")
        
        test_generate_secure_filename_empty()
        print("✓ Empty filename test passed")
        
        test_secure_join_path_valid()
        print("✓ Valid path test passed")
        
        test_secure_join_path_traversal_attack()
        print("✓ Path traversal attack test passed")
        
        test_secure_join_path_complex_traversal()
        print("✓ Complex path traversal test passed")
        
        test_allowed_extensions_completeness()
        print("✓ Allowed extensions test passed")
        
        print("\n🎉 All security tests passed! The path traversal vulnerability has been fixed.")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        sys.exit(1)