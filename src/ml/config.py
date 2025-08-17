"""
ML Pipeline Configuration
"""
from typing import Dict, List, Optional
from pydantic import BaseSettings, Field
import torch
import os

class MLConfig(BaseSettings):
    """ML Pipeline Configuration Settings"""
    
    # Model Configuration
    model_name: str = Field(default="yolov8n.pt", description="YOLOv8 model file")
    model_path: str = Field(default="/home/user/Testing/ai-model-validation-platform/backend/yolov8n.pt")
    confidence_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
    iou_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    
    # VRU Class Configuration (COCO class IDs)
    vru_classes: Dict[int, str] = Field(default={
        0: "person",        # Pedestrians, wheelchair users
        1: "bicycle",       # Cyclists
        3: "motorcycle",    # Motorcyclists
        # Additional classes for specialized VRUs
        # Can be extended with custom trained models
    })
    
    # Performance Settings
    max_inference_time_ms: int = Field(default=50, description="Maximum inference latency")
    batch_size: int = Field(default=1, description="Batch processing size")
    max_concurrent_requests: int = Field(default=4)
    
    # Hardware Configuration
    device: str = Field(default="auto", description="Device: auto, cpu, cuda, mps")
    use_gpu: bool = Field(default=True)
    gpu_memory_limit: Optional[float] = Field(default=None, description="GPU memory limit in GB")
    
    # Tracking Configuration
    tracking_enabled: bool = Field(default=True)
    tracking_max_age: int = Field(default=30, description="Max frames to track without detection")
    tracking_min_hits: int = Field(default=3, description="Min detections before track confirmation")
    tracking_iou_threshold: float = Field(default=0.3)
    
    # Processing Configuration  
    input_size: tuple = Field(default=(640, 640))
    preprocessing_threads: int = Field(default=2)
    postprocessing_threads: int = Field(default=2)
    
    # Output Configuration
    save_screenshots: bool = Field(default=True)
    screenshot_quality: int = Field(default=95, ge=50, le=100)
    annotation_thickness: int = Field(default=2)
    
    # Monitoring
    enable_performance_monitoring: bool = Field(default=True)
    metrics_collection_interval: float = Field(default=1.0, description="Seconds")
    
    class Config:
        env_prefix = "ML_"
        case_sensitive = False

    def get_device(self) -> str:
        """Get the optimal device for inference"""
        if self.device == "auto":
            if torch.cuda.is_available() and self.use_gpu:
                return "cuda"
            elif torch.backends.mps.is_available() and self.use_gpu:
                return "mps"
            else:
                return "cpu"
        return self.device
    
    def get_vru_class_names(self) -> List[str]:
        """Get list of VRU class names"""
        return list(self.vru_classes.values())
    
    def is_vru_class(self, class_id: int) -> bool:
        """Check if class ID corresponds to a VRU"""
        return class_id in self.vru_classes

# Global configuration instance
ml_config = MLConfig()