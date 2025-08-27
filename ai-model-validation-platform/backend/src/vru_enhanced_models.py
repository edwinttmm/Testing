#!/usr/bin/env python3
"""
VRU Enhanced Database Models - Extended Schema for ML Integration
Extends existing models.py with additional VRU-specific enhancements

SPARC Architecture:
- Specification: Complete VRU detection pipeline models
- Pseudocode: Optimized relationships and indexing
- Architecture: Enhanced schema for ML integration
- Refinement: Performance-optimized with comprehensive indexing
- Completion: Production-ready model extensions
"""

from sqlalchemy import Column, String, DateTime, Float, Integer, Boolean, Text, ForeignKey, JSON, Index, DECIMAL, BigInteger
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import json

# Import base models
import sys
from pathlib import Path
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

try:
    from models import Base, Video, Project, DetectionEvent, Annotation
    MODELS_AVAILABLE = True
except ImportError:
    # Create our own base if models not available
    Base = declarative_base()
    MODELS_AVAILABLE = False

class MLModel(Base):
    """ML Model registry and versioning"""
    __tablename__ = "ml_models"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)  # yolo11l, yolov8n, etc.
    version = Column(String, nullable=False, index=True)  # 1.0.0, 2.1.0, etc.
    model_type = Column(String, nullable=False, index=True)  # YOLO, SSD, RCNN, etc.
    architecture = Column(String)  # YOLOv8, YOLOv11, etc.
    input_size = Column(String)  # 640x640, 1280x1280
    model_path = Column(String, nullable=False)  # Path to model file
    config_path = Column(String)  # Path to config file
    class_mapping = Column(JSON)  # Class ID to VRU type mapping
    confidence_thresholds = Column(JSON)  # Per-class confidence thresholds
    performance_metrics = Column(JSON)  # mAP, precision, recall, etc.
    training_dataset = Column(String)  # Training dataset used
    training_date = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True, index=True)
    is_production = Column(Boolean, default=False, index=True)
    created_by = Column(String(36))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    inference_sessions = relationship("MLInferenceSession", back_populates="model")
    model_benchmarks = relationship("ModelBenchmark", back_populates="model")
    
    # Indexes for model management
    __table_args__ = (
        Index('idx_model_name_version', 'name', 'version'),
        Index('idx_model_type_active', 'model_type', 'is_active'),
        Index('idx_model_production_active', 'is_production', 'is_active'),
        Index('idx_model_created_training', 'created_at', 'training_date'),
    )

class MLInferenceSession(Base):
    """ML Inference session tracking"""
    __tablename__ = "ml_inference_sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    model_id = Column(String(36), ForeignKey("ml_models.id", ondelete="CASCADE"), nullable=False, index=True)
    session_name = Column(String, nullable=False, index=True)
    status = Column(String, default="pending", index=True)  # pending, running, completed, failed
    total_frames = Column(Integer)
    processed_frames = Column(Integer, default=0)
    total_detections = Column(Integer, default=0)
    processing_start_time = Column(DateTime(timezone=True), index=True)
    processing_end_time = Column(DateTime(timezone=True), index=True)
    processing_duration_ms = Column(BigInteger)  # Total processing time
    average_fps = Column(Float)  # Processing FPS
    peak_memory_usage_mb = Column(Float)  # Peak memory usage
    gpu_utilization_percent = Column(Float)  # Average GPU utilization
    configuration = Column(JSON)  # Inference configuration (confidence, NMS, etc.)
    error_message = Column(Text)  # Error details if failed
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True), index=True)
    
    # Relationships
    video = relationship("Video")
    model = relationship("MLModel", back_populates="inference_sessions")
    frame_detections = relationship("FrameDetection", back_populates="inference_session", cascade="all, delete-orphan")
    
    # Performance tracking indexes
    __table_args__ = (
        Index('idx_inference_video_model', 'video_id', 'model_id'),
        Index('idx_inference_status_created', 'status', 'created_at'),
        Index('idx_inference_processing_time', 'processing_start_time', 'processing_end_time'),
        Index('idx_inference_performance', 'average_fps', 'peak_memory_usage_mb'),
        Index('idx_inference_model_status', 'model_id', 'status'),
    )

class FrameDetection(Base):
    """Individual frame detection results with enhanced metadata"""
    __tablename__ = "frame_detections"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    inference_session_id = Column(String(36), ForeignKey("ml_inference_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    frame_number = Column(Integer, nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)  # Video timestamp
    detection_count = Column(Integer, default=0)  # Number of objects detected in this frame
    processing_time_ms = Column(Float)  # Time to process this frame
    frame_resolution = Column(String)  # Actual frame resolution
    
    # Frame-level metadata
    brightness = Column(Float)  # Average brightness
    contrast = Column(Float)  # Contrast level
    blur_score = Column(Float)  # Motion blur score
    noise_level = Column(Float)  # Image noise level
    weather_condition = Column(String)  # clear, rain, fog, etc.
    lighting_condition = Column(String)  # daylight, night, artificial, etc.
    
    # Storage paths
    frame_thumbnail_path = Column(String)  # Thumbnail for quick preview
    detection_overlay_path = Column(String)  # Frame with detection overlays
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    inference_session = relationship("MLInferenceSession", back_populates="frame_detections")
    object_detections = relationship("ObjectDetection", back_populates="frame_detection", cascade="all, delete-orphan")
    
    # Frame analysis indexes
    __table_args__ = (
        Index('idx_frame_session_frame', 'inference_session_id', 'frame_number'),
        Index('idx_frame_session_timestamp', 'inference_session_id', 'timestamp'),
        Index('idx_frame_detection_count', 'detection_count'),
        Index('idx_frame_processing_time', 'processing_time_ms'),
        Index('idx_frame_quality_metrics', 'brightness', 'contrast', 'blur_score'),
        Index('idx_frame_conditions', 'weather_condition', 'lighting_condition'),
        Index('idx_frame_session_quality', 'inference_session_id', 'blur_score', 'brightness'),
    )

class ObjectDetection(Base):
    """Individual object detection with comprehensive attributes"""
    __tablename__ = "object_detections"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    frame_detection_id = Column(String(36), ForeignKey("frame_detections.id", ondelete="CASCADE"), nullable=False, index=True)
    detection_id = Column(String, nullable=False, index=True)  # Unique detection identifier (DET_PED_0001)
    
    # Core detection attributes
    class_id = Column(Integer, nullable=False, index=True)  # COCO class ID
    class_name = Column(String, nullable=False, index=True)  # person, bicycle, etc.
    vru_type = Column(String, nullable=False, index=True)  # pedestrian, cyclist, motorcyclist
    confidence = Column(Float, nullable=False, index=True)
    
    # Spatial information (normalized 0-1 coordinates)
    bbox_x = Column(Float, nullable=False)  # Top-left X
    bbox_y = Column(Float, nullable=False)  # Top-left Y
    bbox_width = Column(Float, nullable=False)  # Width
    bbox_height = Column(Float, nullable=False)  # Height
    bbox_area = Column(Float, index=True)  # Calculated area
    
    # Pixel coordinates for quick access
    bbox_x_pixel = Column(Integer)
    bbox_y_pixel = Column(Integer)
    bbox_width_pixel = Column(Integer)
    bbox_height_pixel = Column(Integer)
    
    # Object attributes and pose estimation
    keypoints = Column(JSON)  # Human pose keypoints if available
    orientation = Column(Float)  # Object orientation in degrees
    velocity_x = Column(Float)  # Estimated velocity (if tracking enabled)
    velocity_y = Column(Float)
    velocity_magnitude = Column(Float, index=True)  # Speed for analysis
    
    # Visual attributes
    occlusion_level = Column(Float, default=0.0)  # 0-1 occlusion percentage
    truncation_level = Column(Float, default=0.0)  # 0-1 truncation percentage
    visibility_score = Column(Float)  # Overall visibility score
    
    # Detection quality metrics
    detection_score = Column(Float)  # Raw model score
    nms_score = Column(Float)  # Non-maximum suppression score
    tracking_id = Column(String, index=True)  # Multi-object tracking ID
    tracking_confidence = Column(Float)  # Tracking confidence
    
    # Temporal information
    first_appearance_frame = Column(Integer)  # First frame this object appeared
    last_appearance_frame = Column(Integer)  # Last frame this object appeared
    total_appearances = Column(Integer, default=1)  # Total frames object appeared
    
    # Validation and ground truth matching
    validation_status = Column(String, default="pending", index=True)  # pending, valid, invalid, uncertain
    ground_truth_match_id = Column(String(36), ForeignKey("annotations.id", ondelete="SET NULL"), index=True)
    iou_with_ground_truth = Column(Float)  # IoU score with matched ground truth
    match_confidence = Column(Float)  # Confidence of GT matching
    
    # Visual evidence
    detection_crop_path = Column(String)  # Cropped object image
    detection_context_path = Column(String)  # Object with context
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    frame_detection = relationship("FrameDetection", back_populates="object_detections")
    ground_truth_match = relationship("Annotation")
    detection_attributes = relationship("DetectionAttribute", back_populates="object_detection", cascade="all, delete-orphan")
    
    # Comprehensive indexing for complex queries
    __table_args__ = (
        Index('idx_object_frame_detection', 'frame_detection_id', 'detection_id'),
        Index('idx_object_class_confidence', 'class_name', 'confidence'),
        Index('idx_object_vru_confidence', 'vru_type', 'confidence'),
        Index('idx_object_bbox_area', 'bbox_area'),
        Index('idx_object_spatial', 'bbox_x', 'bbox_y'),
        Index('idx_object_validation', 'validation_status', 'confidence'),
        Index('idx_object_tracking', 'tracking_id', 'tracking_confidence'),
        Index('idx_object_temporal', 'first_appearance_frame', 'last_appearance_frame'),
        Index('idx_object_quality', 'visibility_score', 'occlusion_level'),
        Index('idx_object_velocity', 'velocity_magnitude'),
        Index('idx_object_ground_truth', 'ground_truth_match_id', 'iou_with_ground_truth'),
        Index('idx_object_frame_class_vru', 'frame_detection_id', 'class_name', 'vru_type'),
        Index('idx_object_validation_confidence', 'validation_status', 'confidence'),
        Index('idx_object_temporal_tracking', 'tracking_id', 'first_appearance_frame', 'last_appearance_frame'),
    )

class DetectionAttribute(Base):
    """Flexible attribute system for object detections"""
    __tablename__ = "detection_attributes"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    object_detection_id = Column(String(36), ForeignKey("object_detections.id", ondelete="CASCADE"), nullable=False, index=True)
    attribute_name = Column(String, nullable=False, index=True)  # age_group, clothing_color, etc.
    attribute_value = Column(String, nullable=False, index=True)  # adult, child, red, blue, etc.
    confidence = Column(Float)  # Attribute confidence score
    attribute_type = Column(String, index=True)  # demographic, appearance, behavior, etc.
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    object_detection = relationship("ObjectDetection", back_populates="detection_attributes")
    
    __table_args__ = (
        Index('idx_attribute_detection_name', 'object_detection_id', 'attribute_name'),
        Index('idx_attribute_name_value', 'attribute_name', 'attribute_value'),
        Index('idx_attribute_type_confidence', 'attribute_type', 'confidence'),
    )

class ModelBenchmark(Base):
    """Model performance benchmarking results"""
    __tablename__ = "model_benchmarks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model_id = Column(String(36), ForeignKey("ml_models.id", ondelete="CASCADE"), nullable=False, index=True)
    benchmark_name = Column(String, nullable=False, index=True)  # COCO_VRU, Custom_Dataset, etc.
    dataset_size = Column(Integer)  # Number of test images/videos
    
    # Performance metrics
    map_50 = Column(Float)  # mAP at IoU 0.5
    map_95 = Column(Float)  # mAP at IoU 0.5-0.95
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)
    
    # Per-class metrics (JSON storage)
    class_metrics = Column(JSON)  # Per-class precision, recall, mAP
    
    # Speed metrics
    inference_time_ms = Column(Float)  # Average inference time per image
    fps = Column(Float)  # Frames per second
    memory_usage_mb = Column(Float)  # Peak memory usage
    
    # Hardware configuration
    hardware_config = Column(JSON)  # GPU, CPU, memory specs
    
    benchmark_date = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_by = Column(String(36))
    
    # Relationships
    model = relationship("MLModel", back_populates="model_benchmarks")
    
    __table_args__ = (
        Index('idx_benchmark_model_date', 'model_id', 'benchmark_date'),
        Index('idx_benchmark_name_date', 'benchmark_name', 'benchmark_date'),
        Index('idx_benchmark_performance', 'map_50', 'fps'),
    )

class VideoQualityMetrics(Base):
    """Video quality assessment metrics"""
    __tablename__ = "video_quality_metrics"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Overall video quality scores
    overall_quality_score = Column(Float, index=True)  # 0-1 quality score
    brightness_score = Column(Float)  # Average brightness
    contrast_score = Column(Float)  # Average contrast
    sharpness_score = Column(Float)  # Overall sharpness
    noise_score = Column(Float)  # Noise level
    
    # Motion analysis
    motion_blur_percentage = Column(Float)  # Percentage of frames with motion blur
    camera_shake_score = Column(Float)  # Camera stability score
    average_optical_flow = Column(Float)  # Motion intensity
    
    # Lighting conditions
    overexposure_percentage = Column(Float)  # Overexposed pixels percentage
    underexposure_percentage = Column(Float)  # Underexposed pixels percentage
    dynamic_range = Column(Float)  # Dynamic range score
    
    # Weather and environmental conditions
    weather_classification = Column(JSON)  # Detected weather conditions with confidence
    lighting_classification = Column(JSON)  # Detected lighting conditions
    
    # Compression and encoding quality
    compression_artifacts_score = Column(Float)  # Compression quality
    bitrate_consistency = Column(Float)  # Bitrate variation
    
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    analysis_version = Column(String, default="1.0")
    
    # Relationships
    video = relationship("Video")
    
    __table_args__ = (
        Index('idx_quality_video_score', 'video_id', 'overall_quality_score'),
        Index('idx_quality_brightness_contrast', 'brightness_score', 'contrast_score'),
        Index('idx_quality_motion_blur', 'motion_blur_percentage'),
        Index('idx_quality_analyzed_date', 'analyzed_at'),
    )

class SystemPerformanceLog(Base):
    """System performance monitoring and logging"""
    __tablename__ = "system_performance_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    component = Column(String, nullable=False, index=True)  # ml_engine, database, api, etc.
    operation = Column(String, nullable=False, index=True)  # inference, query, upload, etc.
    
    # Performance metrics
    execution_time_ms = Column(BigInteger, index=True)
    memory_usage_mb = Column(Float)
    cpu_usage_percent = Column(Float)
    gpu_usage_percent = Column(Float)
    
    # Context information
    input_size = Column(BigInteger)  # Input data size
    output_size = Column(BigInteger)  # Output data size
    batch_size = Column(Integer)  # Batch size if applicable
    
    # Resource utilization
    thread_count = Column(Integer)
    process_count = Column(Integer)
    disk_io_mb = Column(Float)  # Disk I/O in MB
    network_io_mb = Column(Float)  # Network I/O in MB
    
    # Status and error tracking
    status = Column(String, index=True)  # success, error, timeout, etc.
    error_message = Column(Text)
    error_type = Column(String, index=True)
    
    # Additional metadata
    metadata = Column(JSON)  # Additional context-specific data
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Performance analysis indexes
    __table_args__ = (
        Index('idx_perf_component_operation', 'component', 'operation'),
        Index('idx_perf_timestamp_component', 'timestamp', 'component'),
        Index('idx_perf_execution_time', 'execution_time_ms'),
        Index('idx_perf_status_error', 'status', 'error_type'),
        Index('idx_perf_resource_usage', 'memory_usage_mb', 'cpu_usage_percent'),
        Index('idx_perf_operation_time_status', 'operation', 'execution_time_ms', 'status'),
    )

# =============================================================================
# UTILITY FUNCTIONS FOR MODEL MANAGEMENT
# =============================================================================

def create_enhanced_detection_from_yolo(yolo_result: Dict[str, Any], 
                                      inference_session_id: str,
                                      frame_number: int,
                                      timestamp: float) -> Dict[str, Any]:
    """Create enhanced detection record from YOLO result"""
    
    # Calculate derived metrics
    bbox_area = yolo_result['bbox_width'] * yolo_result['bbox_height']
    
    detection_data = {
        'inference_session_id': inference_session_id,
        'detection_id': yolo_result.get('detection_id', f"DET_{frame_number}_{uuid.uuid4().hex[:8]}"),
        'frame_number': frame_number,
        'timestamp': timestamp,
        'class_id': yolo_result['class_id'],
        'class_name': yolo_result['class_name'],
        'vru_type': yolo_result['vru_type'],
        'confidence': yolo_result['confidence'],
        'bbox_x': yolo_result['bbox_x'],
        'bbox_y': yolo_result['bbox_y'],
        'bbox_width': yolo_result['bbox_width'],
        'bbox_height': yolo_result['bbox_height'],
        'bbox_area': bbox_area,
        'detection_score': yolo_result.get('detection_score', yolo_result['confidence']),
        'visibility_score': yolo_result.get('visibility_score', 1.0),
        'validation_status': 'pending'
    }
    
    return detection_data

def get_model_performance_summary(model_id: str, session) -> Dict[str, Any]:
    """Get comprehensive model performance summary"""
    
    # Get model info
    model = session.query(MLModel).filter(MLModel.id == model_id).first()
    if not model:
        return {}
    
    # Get inference sessions stats
    session_stats = session.query(
        func.count(MLInferenceSession.id).label('total_sessions'),
        func.avg(MLInferenceSession.average_fps).label('avg_fps'),
        func.avg(MLInferenceSession.peak_memory_usage_mb).label('avg_memory'),
        func.sum(MLInferenceSession.total_detections).label('total_detections')
    ).filter(MLInferenceSession.model_id == model_id).first()
    
    # Get latest benchmark
    latest_benchmark = session.query(ModelBenchmark).filter(
        ModelBenchmark.model_id == model_id
    ).order_by(ModelBenchmark.benchmark_date.desc()).first()
    
    return {
        'model_info': {
            'id': model.id,
            'name': model.name,
            'version': model.version,
            'model_type': model.model_type,
            'is_active': model.is_active,
            'is_production': model.is_production
        },
        'usage_stats': {
            'total_sessions': session_stats.total_sessions or 0,
            'average_fps': float(session_stats.avg_fps or 0),
            'average_memory_mb': float(session_stats.avg_memory or 0),
            'total_detections': session_stats.total_detections or 0
        },
        'latest_benchmark': {
            'map_50': latest_benchmark.map_50 if latest_benchmark else None,
            'precision': latest_benchmark.precision if latest_benchmark else None,
            'recall': latest_benchmark.recall if latest_benchmark else None,
            'fps': latest_benchmark.fps if latest_benchmark else None,
            'benchmark_date': latest_benchmark.benchmark_date.isoformat() if latest_benchmark else None
        } if latest_benchmark else None
    }

if __name__ == "__main__":
    print("🏗️ VRU Enhanced Models - Schema Extensions")
    print("=" * 50)
    print("✅ MLModel - Model registry and versioning")
    print("✅ MLInferenceSession - Session tracking") 
    print("✅ FrameDetection - Frame-level analysis")
    print("✅ ObjectDetection - Individual object tracking")
    print("✅ DetectionAttribute - Flexible attributes")
    print("✅ ModelBenchmark - Performance benchmarking")
    print("✅ VideoQualityMetrics - Quality assessment")
    print("✅ SystemPerformanceLog - Performance monitoring")
    print("=" * 50)
    print("🚀 Ready for VRU ML integration!")