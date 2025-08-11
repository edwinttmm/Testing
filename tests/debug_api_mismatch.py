#!/usr/bin/env python3

import sys
import os
import json

# Add the backend directory to Python path
backend_path = os.path.join(os.path.dirname(__file__), '..', 'ai-model-validation-platform', 'backend')
sys.path.insert(0, backend_path)

def compare_schemas():
    """Compare backend schema with frontend expectations"""
    
    print("=== Backend Schema Analysis ===")
    
    # Backend Project schema from schemas.py
    backend_project = {
        "name": "str",
        "description": "Optional[str]",
        "camera_model": "str", 
        "camera_view": "str",
        "lens_type": "Optional[str]",
        "resolution": "Optional[str]", 
        "frame_rate": "Optional[int]",
        "signal_type": "str"
    }
    
    # Frontend Project expected from types.ts
    frontend_project_create = {
        "name": "string",
        "description": "string", 
        "cameraModel": "string",  # Note: camelCase!
        "cameraView": "string",   # Note: camelCase!
        "signalType": "string"    # Note: camelCase!
    }
    
    print("Backend expects:")
    for key, type_val in backend_project.items():
        print(f"  {key}: {type_val}")
    
    print("\nFrontend sends:")
    for key, type_val in frontend_project_create.items():
        print(f"  {key}: {type_val}")
    
    print("\n=== MISMATCH FOUND ===")
    print("Frontend uses camelCase, Backend expects snake_case!")
    print("- cameraModel vs camera_model")
    print("- cameraView vs camera_view") 
    print("- signalType vs signal_type")
    
    print("\n=== Test Payload ===")
    test_payload = {
        "name": "Test Project",
        "description": "Test Description",
        "cameraModel": "Test Camera",  # Frontend format
        "cameraView": "front",
        "signalType": "video"
    }
    
    print("Frontend payload:")
    print(json.dumps(test_payload, indent=2))
    
    # Backend expects:
    backend_payload = {
        "name": "Test Project",
        "description": "Test Description", 
        "camera_model": "Test Camera",  # Backend format
        "camera_view": "front",
        "signal_type": "video"
    }
    
    print("\nBackend expects:")
    print(json.dumps(backend_payload, indent=2))

if __name__ == "__main__":
    compare_schemas()