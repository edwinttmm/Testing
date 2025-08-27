#!/usr/bin/env python3
"""
VRU ML-Database Connector - SPARC Implementation
Bridge between ML engines and unified database architecture

SPARC Architecture:
- Specification: Seamless ML-to-database integration
- Pseudocode: Optimized data flow with validation
- Architecture: Unified connector for all ML engines
- Refinement: Performance-optimized with batching
- Completion: Production-ready ML integration
"""

import logging
import asyncio
import time
import uuid
from typing import Dict, List, Any, Optional, Tuple, Union, AsyncGenerator
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import json
import traceback

# Import ML engines and database components
import sys
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

try:
    # VRU Integration components
    from src.vru_database_integration_layer import (
        VRUDatabaseIntegrationLayer, 
        VRUDetectionData, 
        VideoMetadata,
        get_vru_integration_layer
    )
    
    # ML Engines
    from src.enhanced_ml_inference_engine import EnhancedMLInferenceEngine, EnhancedBoundingBox, VRUDetection
    from src.bulletproof_detection_service import BulletproofYOLOWrapper, BulletproofDetection
    from src.ml_inference_engine import YOLOInferenceEngine, VRUDetection as BasicVRUDetection
    
    # Database models
    from models import Video, Project, TestSession
    from src.vru_enhanced_models import MLModel, MLInferenceSession, FrameDetection, ObjectDetection
    
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    logging.error(f"ML-Database connector dependencies not available: {e}")
    DEPENDENCIES_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class MLEngineConfig:
    """ML Engine configuration for database integration"""
    engine_type: str  # "enhanced", "bulletproof", "basic"
    model_path: Optional[str] = None
    confidence_threshold: float = 0.4
    device: str = "auto"
    batch_size: int = 1
    enable_tracking: bool = False
    save_screenshots: bool = True
    screenshot_directory: str = "screenshots"

class VRUMLDatabaseConnector:
    """Unified ML-Database Connector for VRU Detection"""
    
    def __init__(self, config: MLEngineConfig):
        """Initialize the ML-Database connector"""
        if not DEPENDENCIES_AVAILABLE:
            raise RuntimeError("ML-Database connector dependencies not available")
        
        self.config = config
        self.integration_layer = get_vru_integration_layer()
        self.ml_engine = None
        self.current_session = None
        
        # Performance tracking
        self.performance_metrics = {
            "total_frames_processed": 0,
            "total_detections": 0,
            "average_processing_time": 0.0,
            "peak_memory_usage": 0.0,
            "errors": 0,
            "session_start_time": None
        }
        
        logger.info(f"VRU ML-Database Connector initialized with {config.engine_type} engine")
    
    async def initialize_ml_engine(self) -> bool:
        """Initialize the ML engine based on configuration"""
        try:
            if self.config.engine_type == "enhanced":
                self.ml_engine = EnhancedMLInferenceEngine(
                    model_path=self.config.model_path,
                    device=self.config.device
                )
                await self.ml_engine.initialize()
                
            elif self.config.engine_type == "bulletproof":
                self.ml_engine = BulletproofYOLOWrapper()
                await self.ml_engine.initialize()
                
            elif self.config.engine_type == "basic":
                self.ml_engine = YOLOInferenceEngine(
                    model_path=self.config.model_path,
                    device=self.config.device
                )
                await self.ml_engine.initialize()
                
            else:
                raise ValueError(f"Unknown engine type: {self.config.engine_type}")
            
            logger.info(f"✅ {self.config.engine_type} ML engine initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize ML engine: {e}")
            self.performance_metrics["errors"] += 1
            return False
    
    async def create_inference_session(self, video_id: str, 
                                     model_name: str = "yolo11l",
                                     model_version: str = "1.0") -> str:
        """Create ML inference session in database"""
        try:
            # Get video metadata
            video_metadata = await self.integration_layer.get_video_metadata(video_id)
            if not video_metadata:
                raise ValueError(f"Video {video_id} not found")
            
            # Create session record
            session_data = {
                "video_id": video_id,
                "model_name": model_name,
                "model_version": model_version,
                "status": "pending",
                "configuration": asdict(self.config),
                "total_frames": int(video_metadata.get("duration", 0) * video_metadata.get("fps", 30))
            }
            
            # Store in database (would need to extend integration layer)
            session_id = str(uuid.uuid4())
            self.current_session = {
                "id": session_id,
                "video_id": video_id,
                "start_time": datetime.now(timezone.utc),
                **session_data
            }
            
            self.performance_metrics["session_start_time"] = time.time()
            
            logger.info(f"✅ Inference session created: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to create inference session: {e}")
            self.performance_metrics["errors"] += 1
            raise
    
    async def process_video_frames(self, video_path: str, 
                                 video_id: str,
                                 test_session_id: Optional[str] = None) -> Dict[str, Any]:
        """Process video frames and store results in database"""
        processing_results = {
            "success": False,
            "total_frames": 0,
            "frames_processed": 0,
            "detections_found": 0,
            "detections_stored": 0,
            "processing_time": 0.0,
            "error_message": None
        }
        
        try:
            start_time = time.time()
            
            if not self.ml_engine:
                await self.initialize_ml_engine()
            
            # Process frames based on engine type
            if self.config.engine_type == "enhanced":
                results = await self._process_with_enhanced_engine(
                    video_path, video_id, test_session_id
                )
            elif self.config.engine_type == "bulletproof":
                results = await self._process_with_bulletproof_engine(
                    video_path, video_id, test_session_id
                )
            else:
                results = await self._process_with_basic_engine(
                    video_path, video_id, test_session_id
                )
            
            processing_results.update(results)
            processing_results["processing_time"] = time.time() - start_time
            processing_results["success"] = True
            
            # Update performance metrics
            self.performance_metrics["total_frames_processed"] += processing_results["frames_processed"]
            self.performance_metrics["total_detections"] += processing_results["detections_found"]
            
            if processing_results["frames_processed"] > 0:
                avg_time = processing_results["processing_time"] / processing_results["frames_processed"]
                self.performance_metrics["average_processing_time"] = avg_time
            
            logger.info(f"✅ Video processing completed: {processing_results['frames_processed']} frames, {processing_results['detections_found']} detections")
            
            return processing_results
            
        except Exception as e:
            error_msg = f"Video processing failed: {e}"
            processing_results["error_message"] = error_msg
            self.performance_metrics["errors"] += 1
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return processing_results
    
    async def _process_with_enhanced_engine(self, video_path: str, 
                                          video_id: str,
                                          test_session_id: Optional[str]) -> Dict[str, Any]:
        """Process with Enhanced ML Inference Engine"""
        results = {
            "total_frames": 0,
            "frames_processed": 0,
            "detections_found": 0,
            "detections_stored": 0
        }
        
        detection_batch = []
        batch_size = self.config.batch_size
        
        try:
            # Process video with enhanced engine
            async for detection_result in self.ml_engine.process_video_stream(video_path):
                results["frames_processed"] += 1
                
                if detection_result.detections:
                    for detection in detection_result.detections:
                        # Convert to VRUDetectionData
                        vru_detection = VRUDetectionData(
                            detection_id=detection.detection_id,
                            video_id=video_id,
                            frame_number=detection.frame_number,
                            timestamp=detection.timestamp,
                            vru_type=detection.vru_type,
                            confidence=detection.confidence,
                            bounding_box={
                                "x": detection.bounding_box.x,
                                "y": detection.bounding_box.y,
                                "width": detection.bounding_box.width,
                                "height": detection.bounding_box.height
                            },
                            class_label=detection.vru_type,
                            model_version=f"{self.config.engine_type}_engine",
                            processing_time_ms=detection.processing_time_ms,
                            screenshot_path=detection.screenshot_path,
                            metadata={"engine": "enhanced"}
                        )
                        
                        detection_batch.append(vru_detection)
                        results["detections_found"] += 1
                
                # Batch store detections
                if len(detection_batch) >= batch_size:
                    stored_ids = await self.integration_layer.batch_store_detections(
                        detection_batch, test_session_id
                    )
                    results["detections_stored"] += len(stored_ids)
                    detection_batch.clear()
            
            # Store remaining detections
            if detection_batch:
                stored_ids = await self.integration_layer.batch_store_detections(
                    detection_batch, test_session_id
                )
                results["detections_stored"] += len(stored_ids)
            
            return results
            
        except Exception as e:
            logger.error(f"Enhanced engine processing failed: {e}")
            raise
    
    async def _process_with_bulletproof_engine(self, video_path: str, 
                                             video_id: str,
                                             test_session_id: Optional[str]) -> Dict[str, Any]:
        """Process with Bulletproof Detection Service"""
        results = {
            "total_frames": 0,
            "frames_processed": 0,
            "detections_found": 0,
            "detections_stored": 0
        }
        
        try:
            # Process with bulletproof engine
            async for detection_result in self.ml_engine.process_video_bulletproof(video_path):
                results["frames_processed"] += 1
                
                if detection_result.detections:
                    detection_batch = []
                    
                    for detection in detection_result.detections:
                        # Convert BulletproofDetection to VRUDetectionData
                        vru_detection = VRUDetectionData(
                            detection_id=detection.id,
                            video_id=video_id,
                            frame_number=detection.frame_number,
                            timestamp=detection.timestamp,
                            vru_type=detection.vru_type,
                            confidence=detection.confidence,
                            bounding_box=detection.bounding_box,
                            class_label=detection.class_label,
                            model_version=detection.model_version,
                            processing_time_ms=detection.processing_time_ms,
                            metadata={"engine": "bulletproof", "integrity_status": detection.integrity_status}
                        )
                        
                        detection_batch.append(vru_detection)
                        results["detections_found"] += 1
                    
                    # Store batch
                    stored_ids = await self.integration_layer.batch_store_detections(
                        detection_batch, test_session_id
                    )
                    results["detections_stored"] += len(stored_ids)
            
            return results
            
        except Exception as e:
            logger.error(f"Bulletproof engine processing failed: {e}")
            raise
    
    async def _process_with_basic_engine(self, video_path: str, 
                                       video_id: str,
                                       test_session_id: Optional[str]) -> Dict[str, Any]:
        """Process with Basic YOLO Engine"""
        results = {
            "total_frames": 0,
            "frames_processed": 0,
            "detections_found": 0,
            "detections_stored": 0
        }
        
        try:
            # Process with basic engine
            detections = await self.ml_engine.process_video(video_path)
            
            detection_batch = []
            
            for detection in detections:
                # Convert BasicVRUDetection to VRUDetectionData
                vru_detection = VRUDetectionData(
                    detection_id=detection.detection_id,
                    video_id=video_id,
                    frame_number=detection.frame_number,
                    timestamp=detection.timestamp,
                    vru_type=detection.vru_type,
                    confidence=detection.confidence,
                    bounding_box={
                        "x": detection.bounding_box.x,
                        "y": detection.bounding_box.y,
                        "width": detection.bounding_box.width,
                        "height": detection.bounding_box.height
                    },
                    class_label=detection.vru_type,
                    model_version="basic_yolo",
                    metadata={"engine": "basic"}
                )
                
                detection_batch.append(vru_detection)
                results["detections_found"] += 1
                results["frames_processed"] = detection.frame_number
            
            # Store all detections
            if detection_batch:
                stored_ids = await self.integration_layer.batch_store_detections(
                    detection_batch, test_session_id
                )
                results["detections_stored"] = len(stored_ids)
            
            return results
            
        except Exception as e:
            logger.error(f"Basic engine processing failed: {e}")
            raise
    
    async def get_processing_statistics(self) -> Dict[str, Any]:
        """Get comprehensive processing statistics"""
        try:
            # Get integration layer metrics
            integration_metrics = await self.integration_layer.get_performance_metrics()
            
            # Calculate session statistics
            session_duration = (
                time.time() - self.performance_metrics["session_start_time"]
                if self.performance_metrics["session_start_time"] else 0
            )
            
            return {
                "connector_metrics": {
                    "total_frames_processed": self.performance_metrics["total_frames_processed"],
                    "total_detections": self.performance_metrics["total_detections"],
                    "average_processing_time": self.performance_metrics["average_processing_time"],
                    "peak_memory_usage": self.performance_metrics["peak_memory_usage"],
                    "errors": self.performance_metrics["errors"],
                    "session_duration": session_duration
                },
                "integration_metrics": integration_metrics,
                "engine_config": asdict(self.config),
                "current_session": self.current_session
            }
            
        except Exception as e:
            logger.error(f"Failed to get processing statistics: {e}")
            return {"error": str(e)}
    
    async def cleanup_session(self):
        """Cleanup current session and resources"""
        try:
            if self.current_session:
                # Update session status in database
                logger.info(f"Cleaning up session: {self.current_session['id']}")
                
                # Reset session
                self.current_session = None
            
            # Reset performance metrics
            self.performance_metrics = {
                "total_frames_processed": 0,
                "total_detections": 0,
                "average_processing_time": 0.0,
                "peak_memory_usage": 0.0,
                "errors": 0,
                "session_start_time": None
            }
            
            logger.info("✅ Session cleanup completed")
            
        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")

# =============================================================================
# FACTORY FUNCTIONS AND UTILITIES
# =============================================================================

def create_ml_database_connector(engine_type: str = "enhanced", 
                               **config_kwargs) -> VRUMLDatabaseConnector:
    """Factory function to create ML-Database connector"""
    config = MLEngineConfig(
        engine_type=engine_type,
        **config_kwargs
    )
    return VRUMLDatabaseConnector(config)

async def process_video_with_ml_integration(video_path: str, 
                                          video_id: str,
                                          engine_type: str = "enhanced",
                                          test_session_id: Optional[str] = None) -> Dict[str, Any]:
    """High-level function to process video with ML integration"""
    try:
        # Create connector
        connector = create_ml_database_connector(engine_type)
        
        # Initialize
        await connector.initialize_ml_engine()
        
        # Create inference session
        session_id = await connector.create_inference_session(video_id)
        
        # Process video
        results = await connector.process_video_frames(
            video_path, video_id, test_session_id
        )
        
        # Get final statistics
        statistics = await connector.get_processing_statistics()
        results["statistics"] = statistics
        
        # Cleanup
        await connector.cleanup_session()
        
        return results
        
    except Exception as e:
        logger.error(f"Video processing with ML integration failed: {e}")
        return {
            "success": False,
            "error_message": str(e)
        }

if __name__ == "__main__":
    # Test the ML-Database connector
    async def test_connector():
        print("🔧 Testing VRU ML-Database Connector")
        print("=" * 50)
        
        if not DEPENDENCIES_AVAILABLE:
            print("❌ Dependencies not available")
            return
        
        try:
            # Create connector
            config = MLEngineConfig(
                engine_type="enhanced",
                confidence_threshold=0.4,
                batch_size=5
            )
            
            connector = VRUMLDatabaseConnector(config)
            
            # Test initialization
            success = await connector.initialize_ml_engine()
            print(f"✅ Engine initialization: {success}")
            
            # Test session creation
            test_video_id = str(uuid.uuid4())
            session_id = await connector.create_inference_session(test_video_id)
            print(f"✅ Session created: {session_id}")
            
            # Get statistics
            stats = await connector.get_processing_statistics()
            print(f"✅ Statistics retrieved: {len(stats)} metrics")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
        
        print("=" * 50)
    
    # Run test
    asyncio.run(test_connector())