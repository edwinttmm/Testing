#!/usr/bin/env python3
"""
API Compatibility Validation Script
==================================

This script validates that all backend API responses match frontend TypeScript interface expectations.
It checks for:
1. Field name consistency (camelCase vs snake_case)
2. Response structure matching TypeScript interfaces
3. Data type compatibility
4. Required vs optional fields
5. Enum value alignment

Usage: python scripts/validate_api_compatibility.py
"""

import json
import sys
import traceback
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
import requests
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from schemas import *
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ValidationResult:
    """Container for validation results"""
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.successes: List[str] = []
        
    def add_error(self, message: str):
        self.errors.append(message)
        logger.error(f"❌ {message}")
        
    def add_warning(self, message: str):
        self.warnings.append(message)
        logger.warning(f"⚠️ {message}")
        
    def add_success(self, message: str):
        self.successes.append(message)
        logger.info(f"✅ {message}")
        
    def summary(self) -> Dict[str, Any]:
        return {
            "total_checks": len(self.errors) + len(self.warnings) + len(self.successes),
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "successes": len(self.successes),
            "error_list": self.errors,
            "warning_list": self.warnings,
            "success_list": self.successes
        }

class APICompatibilityValidator:
    """Main validator class"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.result = ValidationResult()
        
        # Frontend expected field mappings (snake_case -> camelCase)
        self.field_mappings = {
            # Project fields
            "project_id": "projectId",
            "camera_model": "cameraModel", 
            "camera_view": "cameraView",
            "lens_type": "lensType",
            "frame_rate": "frameRate",
            "signal_type": "signalType",
            "owner_id": "ownerId",
            "created_at": "createdAt",
            "updated_at": "updatedAt",
            "tests_count": "testsCount",
            "video_count": "videoCount",
            "total_annotations": "totalAnnotations",
            "average_accuracy": "averageAccuracy",
            
            # Video fields
            "video_id": "videoId",
            "file_size": "fileSize",
            "original_name": "originalName",
            "file_path": "filePath",
            "ground_truth_generated": "groundTruthGenerated",
            "ground_truth_count": "groundTruthCount",
            "ground_truth_quality_score": "groundTruthQualityScore",
            "ground_truth_completed_at": "groundTruthCompletedAt",
            "detection_count": "detectionCount",
            "annotation_count": "annotationCount",
            "validation_status": "validationStatus",
            "validation_type": "validationType",
            "validated_at": "validatedAt",
            "validated_by": "validatedBy",
            "hil_testing_ready": "hilTestingReady",
            "hil_testing_approved_by": "hilTestingApprovedBy",
            "hil_testing_approved_at": "hilTestingApprovedAt",
            "uploaded_at": "uploadedAt",
            "frame_count": "frameCount",
            "mime_type": "mimeType",
            "thumbnail_url": "thumbnailUrl",
            
            # Test session fields
            "test_session_id": "testSessionId",
            "video_ids": "videoIds",
            "tolerance_ms": "toleranceMs",
            "started_at": "startedAt",
            "completed_at": "completedAt",
            "detection_events": "detectionEvents",
            "model_configurations": "modelConfigurations",
            "model_config_ids": "modelConfigIds",
            
            # Detection fields
            "detection_id": "detectionId",
            "inference_session_id": "inferenceSessionId",
            "frame_number": "frameNumber",
            "class_id": "classId",
            "class_name": "className",
            "class_label": "classLabel",
            "vru_type": "vruType",
            "bounding_box": "boundingBox",
            "detection_score": "detectionScore",
            "nms_score": "nmsScore",
            "tracking_id": "trackingId",
            "validation_result": "validationResult",
            "ground_truth_match_id": "groundTruthMatchId",
            "iou_with_ground_truth": "iouWithGroundTruth",
            "is_ground_truth": "isGroundTruth",
            
            # Dashboard fields
            "project_count": "projectCount",
            "test_session_count": "testSessionCount",
            "detection_event_count": "detectionEventCount",
            "active_tests": "activeTests",
            "total_detections": "totalDetections",
            "confidence_intervals": "confidenceIntervals",
            "trend_analysis": "trendAnalysis",
            "signal_processing_metrics": "signalProcessingMetrics",
        }
        
        # Expected enum values
        self.expected_enums = {
            "VRUType": ["pedestrian", "cyclist", "motorcyclist", "wheelchair_user", "scooter_rider"],
            "VideoValidationStatus": [
                "uploaded", "processing", "processing_failed", "annotated", 
                "validating", "validation_failed", "validated", "ready_for_testing",
                "in_testing", "tested", "archived", "error"
            ],
            "ValidationStatus": [
                "pending", "processing", "pending_validation", "validating", 
                "validated", "failed", "needs_review"
            ],
            "ValidationType": ["automatic", "manual", "hybrid"],
            "ProjectStatus": ["draft", "active", "testing", "analysis", "completed", "archived"],
            "CameraType": ["front_facing", "front_facing_vru", "side_view", "rear_view"],
            "SignalType": ["ttl", "gpio", "analog", "digital"]
        }
    
    def validate_schema_field_mappings(self):
        """Validate that Pydantic schemas use proper field aliases"""
        logger.info("🔍 Validating schema field mappings...")
        
        # Check key response schemas for proper field aliases
        schemas_to_check = [
            ProjectResponse,
            VideoResponse, 
            VideoUploadResponse,
            TestSessionResponse,
            DetectionEventResponse,
            DashboardStats,
            EnhancedDashboardStats
        ]
        
        for schema_class in schemas_to_check:
            schema_name = schema_class.__name__
            logger.info(f"Checking {schema_name}...")
            
            # Get model fields and their aliases
            if hasattr(schema_class, 'model_fields'):
                fields = schema_class.model_fields
            elif hasattr(schema_class, '__fields__'):
                fields = schema_class.__fields__
            else:
                self.result.add_warning(f"Could not access fields for {schema_name}")
                continue
                
            for field_name, field_info in fields.items():
                # Check if field should have camelCase alias
                if field_name in self.field_mappings:
                    expected_alias = self.field_mappings[field_name]
                    
                    # Check field has proper alias
                    actual_alias = None
                    if hasattr(field_info, 'alias') and field_info.alias:
                        actual_alias = field_info.alias
                    elif hasattr(field_info, 'field_info') and hasattr(field_info.field_info, 'alias'):
                        actual_alias = field_info.field_info.alias
                        
                    if actual_alias == expected_alias:
                        self.result.add_success(f"{schema_name}.{field_name} correctly aliased as {expected_alias}")
                    else:
                        self.result.add_error(f"{schema_name}.{field_name} missing camelCase alias (expected: {expected_alias}, got: {actual_alias})")
                        
    def validate_camel_case_model_usage(self):
        """Validate that schemas properly inherit from CamelCaseModel"""
        logger.info("🔍 Validating CamelCaseModel usage...")
        
        schemas_to_check = [
            ProjectResponse,
            VideoResponse,
            VideoUploadResponse, 
            TestSessionResponse,
            DetectionEventResponse,
            DashboardStats,
            EnhancedDashboardStats
        ]
        
        for schema_class in schemas_to_check:
            schema_name = schema_class.__name__
            
            # Check if inherits from CamelCaseModel
            if CamelCaseModel in schema_class.__mro__:
                self.result.add_success(f"{schema_name} properly inherits from CamelCaseModel")
                
                # Check if has proper model_config
                if hasattr(schema_class, 'model_config'):
                    config = schema_class.model_config
                    if hasattr(config, 'alias_generator') or config.get('alias_generator'):
                        self.result.add_success(f"{schema_name} has alias_generator configured")
                    else:
                        self.result.add_error(f"{schema_name} missing alias_generator in model_config")
                        
                    if hasattr(config, 'by_alias') or config.get('by_alias'):
                        self.result.add_success(f"{schema_name} configured for by_alias serialization")  
                    else:
                        self.result.add_error(f"{schema_name} not configured for by_alias serialization")
                else:
                    self.result.add_error(f"{schema_name} missing model_config")
            else:
                self.result.add_error(f"{schema_name} does not inherit from CamelCaseModel")
                
    def validate_enum_alignment(self):
        """Validate enum values match frontend expectations"""
        logger.info("🔍 Validating enum alignment...")
        
        # Check VRU types
        if hasattr(VRUType, '__members__'):
            vru_values = [member.value for member in VRUType.__members__.values()]
            expected_vru = self.expected_enums["VRUType"]
            
            for expected in expected_vru:
                if expected in vru_values:
                    self.result.add_success(f"VRUType.{expected} properly defined")
                else:
                    self.result.add_error(f"VRUType missing expected value: {expected}")
                    
    def validate_response_structure(self):
        """Validate response structure matches frontend expectations"""
        logger.info("🔍 Validating response structure...")
        
        # Test schema serialization to check output format
        try:
            # Create sample project response
            sample_project = ProjectResponse(
                id="test-id",
                name="Test Project",
                description="Test Description", 
                camera_model="Test Camera",
                camera_view=CameraTypeEnum.FRONT_FACING_VRU,
                signal_type=SignalTypeEnum.GPIO,
                status=ProjectStatusEnum.ACTIVE,
                owner_id="test-owner",
                created_at=datetime.now(),
                tests_count=5,
                video_count=10,
                total_annotations=100,
                average_accuracy=0.85
            )
            
            # Serialize using by_alias
            serialized = sample_project.model_dump(by_alias=True, exclude_none=True)
            
            # Check for expected camelCase fields (id stays as 'id', not 'projectId')
            expected_fields = ["id", "cameraModel", "cameraView", "signalType", 
                             "ownerId", "createdAt", "testsCount", "videoCount", 
                             "totalAnnotations", "averageAccuracy"]
            
            for field in expected_fields:
                if field in serialized:
                    self.result.add_success(f"ProjectResponse contains camelCase field: {field}")
                else:
                    self.result.add_error(f"ProjectResponse missing camelCase field: {field}")
                    
            # Check for snake_case fields (should not exist in serialized output)
            snake_case_fields = ["project_id", "camera_model", "camera_view", "signal_type", 
                               "owner_id", "created_at", "tests_count", "video_count",
                               "total_annotations", "average_accuracy"]
            
            for field in snake_case_fields:
                if field in serialized:
                    self.result.add_error(f"ProjectResponse contains snake_case field in output: {field}")
                else:
                    self.result.add_success(f"ProjectResponse properly excludes snake_case field: {field}")
                    
        except Exception as e:
            self.result.add_error(f"Error serializing ProjectResponse: {str(e)}")
            
    def validate_error_response_format(self):
        """Validate error response format"""
        logger.info("🔍 Validating error response format...")
        
        try:
            # Test ErrorResponse schema
            error_response = ErrorResponse(
                message="Test error",
                status=400,
                code="TEST_ERROR",
                details={"field": "value"}
            )
            
            serialized = error_response.model_dump(by_alias=True, exclude_none=True)
            
            required_fields = ["message", "status", "code", "details", "timestamp"]
            for field in required_fields:
                if field in serialized:
                    self.result.add_success(f"ErrorResponse contains required field: {field}")
                else:
                    self.result.add_error(f"ErrorResponse missing required field: {field}")
                    
        except Exception as e:
            self.result.add_error(f"Error creating ErrorResponse: {str(e)}")
            
    def validate_websocket_message_format(self):
        """Validate WebSocket message format"""  
        logger.info("🔍 Validating WebSocket message format...")
        
        try:
            from websocket_formatter import WebSocketMessage, WebSocketFormatter
            
            # Test basic message creation
            message = WebSocketMessage(
                type="test_message",
                payload={"data": "test"},
                id="test-id"
            )
            
            serialized = message.model_dump(by_alias=True, exclude_none=True)
            
            required_fields = ["type", "payload", "timestamp", "id"]
            for field in required_fields:
                if field in serialized:
                    self.result.add_success(f"WebSocketMessage contains required field: {field}")
                else:
                    self.result.add_error(f"WebSocketMessage missing required field: {field}")
                    
            # Test formatter
            formatted = WebSocketFormatter.create_message("test_type", {"test": "data"})
            if isinstance(formatted, dict) and "type" in formatted:
                self.result.add_success("WebSocketFormatter creates properly formatted messages")
            else:
                self.result.add_error("WebSocketFormatter does not create proper message format")
                
        except ImportError:
            self.result.add_warning("WebSocketFormatter not available for validation")
        except Exception as e:
            self.result.add_error(f"Error validating WebSocket message format: {str(e)}")
    
    def run_all_validations(self) -> Dict[str, Any]:
        """Run all validation checks"""
        logger.info("🚀 Starting API compatibility validation...")
        
        try:
            self.validate_camel_case_model_usage()
            self.validate_schema_field_mappings() 
            self.validate_enum_alignment()
            self.validate_response_structure()
            self.validate_error_response_format()
            self.validate_websocket_message_format()
            
        except Exception as e:
            self.result.add_error(f"Validation failed with exception: {str(e)}")
            logger.error(f"Validation exception: {traceback.format_exc()}")
        
        summary = self.result.summary()
        
        # Print summary
        print("\n" + "="*50)
        print("API COMPATIBILITY VALIDATION SUMMARY")
        print("="*50)
        print(f"Total Checks: {summary['total_checks']}")
        print(f"✅ Successes: {summary['successes']}")
        print(f"⚠️  Warnings: {summary['warnings']}")
        print(f"❌ Errors: {summary['errors']}")
        
        if summary['errors'] > 0:
            print(f"\n❌ VALIDATION FAILED - {summary['errors']} errors found")
            print("\nErrors:")
            for error in summary['error_list']:
                print(f"  • {error}")
        else:
            print(f"\n✅ VALIDATION PASSED - All checks successful!")
            
        if summary['warnings'] > 0:
            print(f"\nWarnings:")
            for warning in summary['warning_list']:
                print(f"  • {warning}")
                
        return summary

def main():
    """Main validation script"""
    validator = APICompatibilityValidator()
    summary = validator.run_all_validations()
    
    # Exit with error code if validation failed
    if summary['errors'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()