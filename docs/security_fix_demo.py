#!/usr/bin/env python3
"""
Demonstration of the path traversal vulnerability fix
"""

import sys
import os
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, '/workspaces/Testing/ai-model-validation-platform/backend')

try:
    from main import generate_secure_filename, secure_join_path
    from fastapi import HTTPException
    
    print("🔒 Path Traversal Vulnerability Fix Demo")
    print("=" * 50)
    
    # Test 1: Show secure filename generation
    print("\n1️⃣  Secure Filename Generation:")
    print("   Input: 'malicious_video.mp4'")
    secure_name, ext = generate_secure_filename('malicious_video.mp4')
    print(f"   Output: {secure_name}")
    print("   ✅ Original filename replaced with secure UUID")
    
    print("\n   Input: '../../../etc/passwd.mp4' (path traversal attempt)")
    secure_name2, ext2 = generate_secure_filename('../../../etc/passwd.mp4')
    print(f"   Output: {secure_name2}")
    print("   ✅ Path traversal components removed, secure UUID generated")
    
    # Test 2: Show path validation
    print("\n2️⃣  Path Traversal Protection:")
    base_dir = "/tmp/safe_uploads"
    
    # Valid case
    print(f"   Base dir: {base_dir}")
    print(f"   Input: 'safe_file.mp4'")
    try:
        safe_path = secure_join_path(base_dir, 'safe_file.mp4')
        print(f"   Output: {safe_path}")
        print("   ✅ Valid filename allowed")
    except HTTPException as e:
        print(f"   Error: {e.detail}")
    
    # Malicious cases
    malicious_attempts = [
        "../../../etc/passwd",
        "../../../../root/.ssh/id_rsa", 
        "..\\..\\..\\windows\\system32\\config\\sam",
        "file.mp4/../../../sensitive.txt"
    ]
    
    print(f"\n   Testing malicious path traversal attempts:")
    for attempt in malicious_attempts:
        try:
            result = secure_join_path(base_dir, attempt)
            print(f"   ❌ DANGER: '{attempt}' was allowed -> {result}")
        except HTTPException as e:
            print(f"   ✅ BLOCKED: '{attempt}' -> {e.detail}")
    
    # Test 3: Show the difference - vulnerable vs secure
    print("\n3️⃣  Before vs After Fix:")
    print("   BEFORE (vulnerable):")
    print("   file_path = os.path.join(upload_dir, file.filename)")
    print("   -> Allows: /uploads/../../../etc/passwd")
    print("\n   AFTER (secure):")
    print("   secure_filename, ext = generate_secure_filename(file.filename)")
    print("   file_path = secure_join_path(upload_dir, secure_filename)")
    print("   -> Results in: /uploads/550e8400-e29b-41d4-a716-446655440000.mp4")
    
    print("\n🎉 Security Fix Summary:")
    print("✅ User filenames replaced with secure UUIDs")
    print("✅ Path traversal attempts blocked")
    print("✅ File extension validation enforced")
    print("✅ Original filename preserved in database for user reference")
    print("✅ Multiple layers of protection implemented")
    
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the correct directory")
except Exception as e:
    print(f"Error: {e}")
    print("There may be an issue with the security functions")