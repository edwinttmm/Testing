#!/usr/bin/env python3
"""
API Serialization System - Usage Examples
==========================================

This file demonstrates how to use the new serialization system to fix
snake_case/camelCase inconsistencies between backend and frontend.

Run this file to see examples of the serialization in action:
    python serializer_examples.py
"""

from datetime import datetime
from typing import Dict, Any, List
from serializers import (
    ProjectSerializer, VideoSerializer, AnnotationSerializer,
    BoundingBoxSerializer, serialize_for_frontend,
    create_paginated_response, create_list_response, 
    create_single_response, create_error_response
)

def example_project_serialization():
    """Example: Project serialization with snake_case to camelCase conversion"""
    print("\n🏗️  PROJECT SERIALIZATION EXAMPLE")
    print("=" * 50)
    
    # Simulate database model data (snake_case)
    project_data = {
        "id": "proj_12345",
        "name": "VRU Detection Project",
        "description": "Testing pedestrian detection accuracy",
        "camera_model": "FLIR Blackfly S",
        "camera_view": "Front-facing VRU", 
        "lens_type": "Wide-angle",
        "resolution": "1920x1080",
        "frame_rate": 30,
        "signal_type": "GPIO",
        "status": "active",
        "owner_id": "user_789",
        "created_at": datetime(2024, 1, 15, 10, 30, 0),
        "updated_at": datetime(2024, 1, 20, 14, 45, 0),
        "video_count": 15,
        "total_annotations": 1250,
        "average_accuracy": 0.94
    }
    
    # Serialize using Pydantic model (automatic camelCase conversion)
    serialized_project = ProjectSerializer.model_validate(project_data)
    frontend_data = serialized_project.model_dump(by_alias=True)
    
    print("📥 INPUT (snake_case from database):")
    for key, value in list(project_data.items())[:5]:  # Show first 5 fields
        print(f"   {key}: {value}")
    print("   ... (and more)")
    
    print("\n📤 OUTPUT (camelCase for frontend):")
    for key, value in list(frontend_data.items())[:5]:  # Show first 5 fields
        print(f"   {key}: {value}")
    print("   ... (and more)")
    
    return frontend_data

def example_video_serialization():
    """Example: Video serialization with processing status"""
    print("\n🎥 VIDEO SERIALIZATION EXAMPLE")
    print("=" * 50)
    
    # Simulate video model data
    video_data = {
        "id": "vid_67890",
        "project_id": "proj_12345",
        "filename": "vru_test_001.mp4",
        "original_name": "Traffic_Intersection_Recording.mp4",
        "file_size": 125829120,  # ~120MB
        "file_path": "/uploads/videos/vru_test_001.mp4",
        "duration": 300.5,  # 5 minutes
        "fps": 29.97,
        "resolution": "1920x1080",
        "frame_count": 9000,
        "status": "completed",
        "processing_status": "completed",
        "ground_truth_generated": True,
        "detection_count": 347,
        "annotation_count": 289,
        "validation_score": 0.89,
        "uploaded_at": datetime(2024, 1, 18, 9, 15, 0),
        "created_at": datetime(2024, 1, 18, 9, 15, 0),
        "processed_at": datetime(2024, 1, 18, 9, 45, 0)
    }
    
    # Serialize for frontend
    serialized_video = VideoSerializer.model_validate(video_data)
    frontend_data = serialized_video.model_dump(by_alias=True)
    
    print("📥 Key snake_case fields from database:")
    snake_fields = ['file_size', 'original_name', 'frame_count', 'processing_status', 'ground_truth_generated']
    for field in snake_fields:
        print(f"   {field}: {video_data[field]}")
    
    print("\n📤 Converted camelCase fields for frontend:")
    camel_fields = ['fileSize', 'originalName', 'frameCount', 'processingStatus', 'groundTruthGenerated']
    for field in camel_fields:
        print(f"   {field}: {frontend_data[field]}")
    
    return frontend_data

def example_annotation_serialization():
    """Example: Annotation with bounding box serialization"""
    print("\n📍 ANNOTATION SERIALIZATION EXAMPLE")
    print("=" * 50)
    
    # Simulate annotation with bounding box
    annotation_data = {
        "id": "ann_54321",
        "video_id": "vid_67890", 
        "detection_id": "det_001",
        "frame_number": 1500,
        "timestamp": 50.05,
        "vru_type": "pedestrian",
        "class_label": "person",
        "bounding_box": {
            "x": 245.7,
            "y": 180.3,
            "width": 85.2,
            "height": 210.8,
            "confidence": 0.92
        },
        "occluded": False,
        "truncated": True,
        "difficult": False,
        "validation_status": "validated", 
        "validated": True,
        "confidence": 0.89,
        "notes": "Pedestrian crossing street, partially visible",
        "annotator": "annotator_123",
        "created_at": datetime(2024, 1, 18, 10, 30, 0)
    }
    
    # Serialize annotation
    serialized_annotation = AnnotationSerializer.model_validate(annotation_data)
    frontend_data = serialized_annotation.model_dump(by_alias=True)
    
    print("📥 INPUT bounding box (snake_case):")
    bbox = annotation_data['bounding_box']
    print(f"   bounding_box: {bbox}")
    
    print("\n📤 OUTPUT bounding box (camelCase + computed fields):")
    bbox_output = frontend_data['boundingBox']
    print(f"   boundingBox: {bbox_output}")
    print(f"   Computed area: {bbox_output.get('area', 'N/A')}")
    print(f"   Computed centerX: {bbox_output.get('centerX', 'N/A')}")
    
    return frontend_data

def example_collection_responses():
    """Example: Collection responses with pagination"""
    print("\n📋 COLLECTION RESPONSE EXAMPLES")
    print("=" * 50)
    
    # Simulate list of projects
    projects_data = [
        {
            "id": f"proj_{i}",
            "name": f"Project {i}",
            "status": "active",
            "owner_id": "user_123",
            "created_at": datetime(2024, 1, i+1, 10, 0, 0),
            "camera_model": "FLIR Blackfly",
            "camera_view": "Front-facing VRU",
            "signal_type": "GPIO"
        }
        for i in range(1, 6)  # 5 projects
    ]
    
    # Create paginated response
    paginated_response = create_paginated_response(
        items=projects_data,
        model_class=ProjectSerializer,
        page=1,
        per_page=10,
        total=25
    )
    
    print("📤 PAGINATED RESPONSE:")
    print(f"   Total items in response: {len(paginated_response['data'])}")
    print(f"   First item keys: {list(paginated_response['data'][0].keys())[:5]}...")
    print(f"   Pagination meta: {paginated_response['meta']}")
    
    # Create simple list response
    list_response = create_list_response(
        items=projects_data,
        model_class=ProjectSerializer,
        message="Projects retrieved successfully"
    )
    
    print("\n📤 LIST RESPONSE:")
    print(f"   Count: {list_response['count']}")
    print(f"   Success: {list_response['success']}")
    print(f"   Message: {list_response['message']}")
    
    return paginated_response, list_response

def example_utility_functions():
    """Example: Utility functions for flexible serialization"""
    print("\n🛠️  UTILITY FUNCTION EXAMPLES")
    print("=" * 50)
    
    # Raw data with snake_case
    raw_data = {
        "project_id": "proj_123",
        "video_id": "vid_456", 
        "frame_number": 100,
        "detection_count": 5,
        "processing_status": "completed",
        "ground_truth_generated": True,
        "nested_data": {
            "camera_model": "FLIR",
            "lens_type": "wide_angle"
        }
    }
    
    print("📥 INPUT (raw snake_case data):")
    print(f"   {raw_data}")
    
    # Convert using utility function
    camel_data = serialize_for_frontend(raw_data)
    print("\n📤 OUTPUT (camelCase conversion):")
    print(f"   {camel_data}")
    
    # With backward compatibility
    compat_data = serialize_for_frontend(raw_data, include_snake_case=True)
    print("\n📤 WITH BACKWARD COMPATIBILITY (both formats):")
    print(f"   Keys: {list(compat_data.keys())}")
    print(f"   Contains both 'projectId' and 'project_id': {('projectId' in compat_data and 'project_id' in compat_data)}")
    
    # Wrapped response
    wrapped_data = serialize_for_frontend(raw_data, wrap_response=True)
    print("\n📤 WRAPPED RESPONSE:")
    print(f"   Success: {wrapped_data['success']}")
    print(f"   Message: {wrapped_data['message']}")
    print(f"   Data keys: {list(wrapped_data['data'].keys())}")
    
    return camel_data, compat_data, wrapped_data

def example_error_responses():
    """Example: Standardized error responses"""
    print("\n❌ ERROR RESPONSE EXAMPLES")
    print("=" * 50)
    
    # Validation error
    validation_error = create_error_response(
        error_type="ValidationError",
        message="Invalid bounding box coordinates",
        details={
            "field": "bounding_box.x",
            "provided_value": -10.5,
            "constraint": "must be >= 0"
        }
    )
    
    print("📤 VALIDATION ERROR:")
    print(f"   {validation_error}")
    
    # Not found error
    not_found_error = create_error_response(
        error_type="NotFoundError",
        message="Video not found",
        details={"video_id": "vid_nonexistent"}
    )
    
    print("\n📤 NOT FOUND ERROR:")
    print(f"   {not_found_error}")
    
    return validation_error, not_found_error

def example_integration_patterns():
    """Example: Common integration patterns for FastAPI endpoints"""
    print("\n🔗 INTEGRATION PATTERNS")
    print("=" * 50)
    
    print("✅ FastAPI Endpoint Pattern:")
    print("""
from fastapi import APIRouter, HTTPException
from serializers import VideoSerializer, create_single_response, create_error_response

router = APIRouter()

@router.get("/videos/{video_id}")
async def get_video(video_id: str):
    try:
        # Get video from database (returns snake_case model)
        video = await get_video_from_db(video_id)
        if not video:
            return create_error_response(
                error_type="NotFoundError", 
                message="Video not found"
            )
        
        # Serialize for frontend (automatic camelCase conversion)
        return create_single_response(
            item=video,
            model_class=VideoSerializer,
            message="Video retrieved successfully"
        )
    except Exception as e:
        return create_error_response(
            error_type="ServerError",
            message=str(e)
        )
    """)
    
    print("\n✅ Manual Serialization Pattern:")
    print("""
# For existing endpoints, you can manually convert:
from serializers import serialize_for_frontend

def legacy_endpoint():
    raw_data = get_data_from_db()  # snake_case
    
    # Option 1: Simple conversion
    frontend_data = serialize_for_frontend(raw_data)
    
    # Option 2: With validation
    frontend_data = serialize_for_frontend(
        raw_data, 
        model_class=VideoSerializer,
        include_snake_case=True  # For compatibility
    )
    
    return {"success": True, "data": frontend_data}
    """)

if __name__ == "__main__":
    print("🔄 API Serialization System - Live Examples")
    print("=" * 60)
    
    # Run all examples
    example_project_serialization()
    example_video_serialization()
    example_annotation_serialization()
    example_collection_responses()
    example_utility_functions()
    example_error_responses()
    example_integration_patterns()
    
    print("\n" + "=" * 60)
    print("🎉 All examples completed!")
    print("✅ snake_case to camelCase conversion working")
    print("✅ Backward compatibility maintained")
    print("✅ Type-safe serialization with validation")
    print("✅ Standardized response formats")
    print("=" * 60)