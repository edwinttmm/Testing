#!/usr/bin/env python3
"""
Data Pipeline Integration - Wire Bulletproof System into Existing Codebase
Provides seamless integration with zero disruption to existing functionality.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timezone

# Import existing system components
from database import get_db, SessionLocal
from models import Annotation, Video, DetectionEvent, TestSession
from schemas_annotation import AnnotationCreate, AnnotationUpdate, AnnotationResponse

# Import our bulletproof system
from src.data_pipeline_integrity import (
    validate_and_repair_annotation,
    validate_db_to_api_response,
    run_pipeline_health_check,
    AutoRepairService,
    PipelineHealthDashboard
)

from src.bulletproof_detection_service import (
    BulletproofDetectionPipeline,
    process_video_with_bulletproof_protection
)

from src.bulletproof_annotation_endpoints import router as bulletproof_router

logger = logging.getLogger(__name__)

# ==================== SEAMLESS INTEGRATION MIDDLEWARE ====================

class PipelineIntegrationManager:
    """Manager for seamless integration with existing endpoints"""
    
    def __init__(self):
        self.bulletproof_enabled = True
        self.fallback_to_original = True
        self.auto_repair_enabled = True
        self.monitoring_enabled = True
        
        # Track integration metrics
        self.integration_metrics = {
            'bulletproof_calls': 0,
            'fallback_calls': 0,
            'repair_successes': 0,
            'integration_errors': 0
        }
    
    async def enhance_annotation_creation(
        self, 
        original_data: Dict[str, Any], 
        db: Session
    ) -> Dict[str, Any]:
        """Enhance existing annotation creation with bulletproof protection"""
        try:
            if not self.bulletproof_enabled:
                return original_data
            
            self.integration_metrics['bulletproof_calls'] += 1
            
            # Run through bulletproof validation
            validated_data = await validate_and_repair_annotation(original_data, db)
            
            if validated_data is None:
                if self.fallback_to_original:
                    logger.warning("🔄 Bulletproof validation failed, using original data")
                    self.integration_metrics['fallback_calls'] += 1
                    return original_data
                else:
                    raise ValueError("Data validation failed and fallback disabled")
            
            # Check if repair occurred
            if validated_data.get('integrityStatus') == 'repaired':
                self.integration_metrics['repair_successes'] += 1
                logger.info("✅ Auto-repaired annotation data during creation")
            
            return validated_data
            
        except Exception as e:
            self.integration_metrics['integration_errors'] += 1
            logger.error(f"❌ Integration error in annotation creation: {str(e)}")
            
            if self.fallback_to_original:
                return original_data
            else:
                raise
    
    async def enhance_annotation_response(
        self, 
        db_annotation: Annotation, 
        db: Session
    ) -> Dict[str, Any]:
        """Enhance existing annotation response with bulletproof serialization"""
        try:
            if not self.bulletproof_enabled:
                return self._original_serialization(db_annotation)
            
            # Generate bulletproof response
            response_data = await validate_db_to_api_response(db_annotation, db)
            
            if response_data.get('integrityStatus') == 'repaired':
                logger.info(f"🔧 Auto-repaired annotation {db_annotation.id} during serialization")
            
            return response_data
            
        except Exception as e:
            logger.error(f"❌ Integration error in response serialization: {str(e)}")
            
            if self.fallback_to_original:
                return self._original_serialization(db_annotation)
            else:
                raise
    
    def _original_serialization(self, db_annotation: Annotation) -> Dict[str, Any]:
        """Fallback to original serialization logic"""
        try:
            # Replicate original serialization logic
            bounding_box = db_annotation.bounding_box
            if isinstance(bounding_box, str):
                import json
                try:
                    bounding_box = json.loads(bounding_box)
                except:
                    bounding_box = {"x": 0, "y": 0, "width": 1, "height": 1}
            elif bounding_box is None:
                bounding_box = {"x": 0, "y": 0, "width": 1, "height": 1}
            
            return {
                "id": db_annotation.id,
                "videoId": db_annotation.video_id,
                "detectionId": db_annotation.detection_id,
                "frameNumber": db_annotation.frame_number,
                "timestamp": db_annotation.timestamp,
                "endTimestamp": db_annotation.end_timestamp,
                "vruType": db_annotation.vru_type,
                "boundingBox": bounding_box,
                "occluded": db_annotation.occluded or False,
                "truncated": db_annotation.truncated or False,
                "difficult": db_annotation.difficult or False,
                "notes": db_annotation.notes,
                "annotator": db_annotation.annotator,
                "validated": db_annotation.validated or False,
                "createdAt": db_annotation.created_at,
                "updatedAt": db_annotation.updated_at
            }
            
        except Exception as e:
            logger.error(f"❌ Original serialization failed: {str(e)}")
            raise
    
    async def enhance_video_processing(
        self, 
        video_path: str, 
        video_id: str, 
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Enhance existing video processing with bulletproof detection"""
        try:
            if not self.bulletproof_enabled:
                # Fall back to original video processing
                logger.info("🔄 Bulletproof disabled, using original video processing")
                return await self._original_video_processing(video_path, video_id, config)
            
            # Use bulletproof detection pipeline
            logger.info(f"🛡️ Processing video with bulletproof protection: {video_id}")
            
            result = await process_video_with_bulletproof_protection(
                video_path=video_path,
                video_id=video_id,
                db_session_factory=SessionLocal,
                config=config
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Bulletproof video processing failed: {str(e)}")
            
            if self.fallback_to_original:
                logger.info("🔄 Falling back to original video processing")
                return await self._original_video_processing(video_path, video_id, config)
            else:
                raise
    
    async def _original_video_processing(
        self, 
        video_path: str, 
        video_id: str, 
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Fallback to original video processing logic"""
        try:
            # Import original detection pipeline
            from services.detection_pipeline_service import DetectionPipeline
            
            pipeline = DetectionPipeline()
            await pipeline.initialize()
            
            detections = await pipeline.process_video(video_path, video_id, config)
            
            return {
                'video_id': video_id,
                'detections': detections,
                'processing_method': 'original',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Original video processing failed: {str(e)}")
            raise
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get integration status and metrics"""
        return {
            'bulletproof_enabled': self.bulletproof_enabled,
            'fallback_enabled': self.fallback_to_original,
            'auto_repair_enabled': self.auto_repair_enabled,
            'monitoring_enabled': self.monitoring_enabled,
            'metrics': self.integration_metrics,
            'status': 'active' if self.bulletproof_enabled else 'fallback_only',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

# Global integration manager instance
integration_manager = PipelineIntegrationManager()

# ==================== ENHANCED WRAPPER FUNCTIONS ====================

async def create_enhanced_annotation(
    video_id: str,
    annotation: AnnotationCreate,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Enhanced annotation creation that can replace existing endpoints
    Provides bulletproof protection with graceful fallback
    """
    try:
        # Convert Pydantic model to dict
        annotation_dict = annotation.dict()
        annotation_dict['video_id'] = video_id
        
        # Enhance with bulletproof protection
        validated_data = await integration_manager.enhance_annotation_creation(annotation_dict, db)
        
        # Create database record with validated data
        db_annotation = Annotation(
            id=validated_data.get('id', str(uuid.uuid4())),
            video_id=validated_data['video_id'],
            detection_id=validated_data.get('detection_id'),
            frame_number=validated_data['frame_number'],
            timestamp=validated_data['timestamp'],
            end_timestamp=validated_data.get('end_timestamp'),
            vru_type=validated_data['vru_type'],
            bounding_box=validated_data['bounding_box'],
            occluded=validated_data.get('occluded', False),
            truncated=validated_data.get('truncated', False),
            difficult=validated_data.get('difficult', False),
            notes=validated_data.get('notes'),
            annotator=validated_data.get('annotator'),
            validated=validated_data.get('validated', False),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        db.add(db_annotation)
        db.commit()
        db.refresh(db_annotation)
        
        # Generate enhanced response
        response_data = await integration_manager.enhance_annotation_response(db_annotation, db)
        
        logger.info(f"✅ Enhanced annotation created: {db_annotation.id}")
        return response_data
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Enhanced annotation creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Creation failed: {str(e)}")

async def get_enhanced_annotations(
    video_id: str,
    validated_only: Optional[bool] = False,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Enhanced annotation retrieval with bulletproof serialization
    Can replace existing get_annotations endpoints
    """
    try:
        # Query annotations using existing logic
        query = db.query(Annotation).filter(Annotation.video_id == video_id)
        if validated_only:
            query = query.filter(Annotation.validated == True)
        
        annotations = query.order_by(Annotation.timestamp).all()
        
        # Process each annotation with enhanced serialization
        response_annotations = []
        for annotation in annotations:
            try:
                response_data = await integration_manager.enhance_annotation_response(annotation, db)
                response_annotations.append(response_data)
            except Exception as e:
                logger.warning(f"⚠️ Failed to process annotation {annotation.id}: {str(e)}")
                # Continue with other annotations
                continue
        
        logger.info(f"✅ Retrieved {len(response_annotations)} enhanced annotations")
        return response_annotations
        
    except Exception as e:
        logger.error(f"❌ Enhanced annotation retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")

async def process_enhanced_video(
    video_path: str,
    video_id: str,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Enhanced video processing with bulletproof detection
    Can replace existing video processing functions
    """
    try:
        result = await integration_manager.enhance_video_processing(video_path, video_id, config)
        logger.info(f"✅ Enhanced video processing completed: {video_id}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Enhanced video processing failed: {str(e)}")
        raise

# ==================== HEALTH MONITORING INTEGRATION ====================

async def get_integrated_health_status(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get comprehensive health status including integration metrics"""
    try:
        # Get bulletproof system health
        health_report = await run_pipeline_health_check(db)
        
        # Get integration manager status
        integration_status = integration_manager.get_integration_status()
        
        # Get database statistics
        dashboard = PipelineHealthDashboard(db)
        dashboard_data = await dashboard.get_dashboard_data()
        
        return {
            'system_health': health_report,
            'integration_status': integration_status,
            'dashboard_data': dashboard_data,
            'overall_status': 'healthy' if health_report.get('success_rate', 0) > 0.95 else 'degraded',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Health status check failed: {str(e)}")
        return {
            'error': str(e),
            'overall_status': 'unhealthy',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

# ==================== MAINTENANCE OPERATIONS ====================

async def run_maintenance_repair(
    db: Session = Depends(get_db),
    force: bool = False
) -> Dict[str, Any]:
    """Run comprehensive database repair and maintenance"""
    try:
        logger.info("🔧 Starting maintenance repair...")
        
        # Run auto-repair service
        repair_service = AutoRepairService(db)
        repair_report = await repair_service.scan_and_repair_database()
        
        # Update integration metrics
        if repair_report.get('repaired', 0) > 0:
            integration_manager.integration_metrics['repair_successes'] += repair_report['repaired']
        
        logger.info(f"✅ Maintenance repair completed: {repair_report}")
        return repair_report
        
    except Exception as e:
        logger.error(f"❌ Maintenance repair failed: {str(e)}")
        return {'error': str(e), 'repair_success': False}

# ==================== CONFIGURATION MANAGEMENT ====================

class IntegrationConfig:
    """Configuration management for the integration system"""
    
    @staticmethod
    def enable_bulletproof_mode():
        """Enable full bulletproof protection"""
        integration_manager.bulletproof_enabled = True
        integration_manager.fallback_to_original = True
        integration_manager.auto_repair_enabled = True
        integration_manager.monitoring_enabled = True
        logger.info("🛡️ Bulletproof mode enabled with fallback protection")
    
    @staticmethod
    def enable_strict_mode():
        """Enable strict mode (no fallback)"""
        integration_manager.bulletproof_enabled = True
        integration_manager.fallback_to_original = False
        integration_manager.auto_repair_enabled = True
        integration_manager.monitoring_enabled = True
        logger.info("⚡ Strict bulletproof mode enabled (no fallback)")
    
    @staticmethod
    def enable_fallback_mode():
        """Disable bulletproof, use original system only"""
        integration_manager.bulletproof_enabled = False
        integration_manager.fallback_to_original = True
        logger.info("🔄 Fallback mode enabled (original system only)")
    
    @staticmethod
    def get_configuration() -> Dict[str, Any]:
        """Get current configuration"""
        return integration_manager.get_integration_status()

# ==================== FASTAPI ROUTER FOR INTEGRATION ====================

integration_router = APIRouter(prefix="/api/integration", tags=["pipeline-integration"])

@integration_router.get("/status")
async def get_integration_status(db: Session = Depends(get_db)):
    """Get integration system status"""
    return await get_integrated_health_status(db)

@integration_router.post("/maintenance/repair")
async def trigger_maintenance_repair(
    background_tasks: BackgroundTasks,
    force: bool = False,
    db: Session = Depends(get_db)
):
    """Trigger maintenance repair"""
    background_tasks.add_task(run_maintenance_repair, db, force)
    return {"message": "Maintenance repair started", "status": "initiated"}

@integration_router.post("/config/bulletproof")
async def enable_bulletproof_config():
    """Enable bulletproof mode"""
    IntegrationConfig.enable_bulletproof_mode()
    return {"message": "Bulletproof mode enabled", "config": IntegrationConfig.get_configuration()}

@integration_router.post("/config/strict")
async def enable_strict_config():
    """Enable strict mode"""
    IntegrationConfig.enable_strict_mode()
    return {"message": "Strict mode enabled", "config": IntegrationConfig.get_configuration()}

@integration_router.post("/config/fallback")
async def enable_fallback_config():
    """Enable fallback mode"""
    IntegrationConfig.enable_fallback_mode()
    return {"message": "Fallback mode enabled", "config": IntegrationConfig.get_configuration()}

@integration_router.get("/config")
async def get_current_config():
    """Get current configuration"""
    return IntegrationConfig.get_configuration()

# ==================== PATCH EXISTING ENDPOINTS ====================

def patch_existing_endpoints():
    """
    Monkey-patch existing endpoints to use enhanced functionality
    CALL THIS DURING APPLICATION STARTUP
    """
    try:
        logger.info("🔧 Patching existing endpoints with bulletproof integration...")
        
        # Patch annotation endpoints
        import endpoints_annotation
        
        # Store original functions
        endpoints_annotation._original_create_annotation = endpoints_annotation.create_annotation
        endpoints_annotation._original_get_annotations = endpoints_annotation.get_annotations
        
        # Replace with enhanced versions
        endpoints_annotation.create_annotation = create_enhanced_annotation
        endpoints_annotation.get_annotations = get_enhanced_annotations
        
        # Patch detection services
        try:
            from services.detection_pipeline_service import DetectionPipeline
            DetectionPipeline._original_process_video = DetectionPipeline.process_video
            
            async def enhanced_process_video(self, video_path, video_id=None, config=None):
                return await process_enhanced_video(video_path, video_id or str(uuid.uuid4()), config)
            
            DetectionPipeline.process_video = enhanced_process_video
            
        except ImportError:
            logger.warning("⚠️ Detection pipeline service not found, skipping patch")
        
        logger.info("✅ Endpoint patching completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Endpoint patching failed: {str(e)}")
        # Don't crash the application, just log the error

# ==================== STARTUP INITIALIZATION ====================

async def initialize_integration_system():
    """
    Initialize the integration system
    CALL THIS DURING APPLICATION STARTUP
    """
    try:
        logger.info("🚀 Initializing bulletproof integration system...")
        
        # Enable bulletproof mode by default
        IntegrationConfig.enable_bulletproof_mode()
        
        # Patch existing endpoints
        patch_existing_endpoints()
        
        # Run initial health check
        db = SessionLocal()
        try:
            health_status = await get_integrated_health_status(db)
            logger.info(f"📊 Initial health check: {health_status['overall_status']}")
        finally:
            db.close()
        
        logger.info("🎯 Bulletproof integration system initialized successfully!")
        
    except Exception as e:
        logger.error(f"❌ Integration system initialization failed: {str(e)}")
        # Don't crash the application
        IntegrationConfig.enable_fallback_mode()
        logger.info("🔄 Fell back to original system due to initialization failure")

if __name__ == "__main__":
    # Test the integration system
    import asyncio
    import uuid
    
    async def test_integration():
        logger.info("🧪 Testing integration system...")
        
        await initialize_integration_system()
        
        # Test configuration changes
        IntegrationConfig.enable_strict_mode()
        config = IntegrationConfig.get_configuration()
        print("Strict mode config:", config)
        
        IntegrationConfig.enable_bulletproof_mode()
        config = IntegrationConfig.get_configuration()
        print("Bulletproof mode config:", config)
        
        logger.info("✅ Integration system test completed")
    
    asyncio.run(test_integration())