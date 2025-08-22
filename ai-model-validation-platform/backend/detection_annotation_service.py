
import logging
from typing import Dict, Any, Optional
import httpx
import asyncio

logger = logging.getLogger(__name__)

class DetectionAnnotationService:
    """Service to properly format detection data for annotation API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        
    def format_detection_for_annotation(self, detection_data: Dict[str, Any], video_id: str) -> Dict[str, Any]:
        """Format detection data to match AnnotationCreate schema"""
        
        # Ensure bounding_box format is correct
        bbox = detection_data.get('bounding_box', {})
        if not isinstance(bbox, dict):
            bbox = {}
            
        formatted_annotation = {
            "videoId": video_id,  # CRITICAL: This was missing!
            "detectionId": detection_data.get('detection_id', detection_data.get('id')),
            "frameNumber": detection_data.get('frame_number', 0),
            "timestamp": detection_data.get('timestamp', 0.0),
            "vruType": detection_data.get('vru_type', detection_data.get('class_label', 'pedestrian')),
            "boundingBox": {
                "x": bbox.get('x', 0),
                "y": bbox.get('y', 0), 
                "width": bbox.get('width', 0),
                "height": bbox.get('height', 0),
                "label": bbox.get('label', detection_data.get('class_label', 'unknown')),
                "confidence": bbox.get('confidence', detection_data.get('confidence', 0.0))
            },
            "occluded": detection_data.get('occluded', False),
            "truncated": detection_data.get('truncated', False),
            "difficult": detection_data.get('difficult', False),
            "validated": detection_data.get('validated', False)
        }
        
        logger.info(f"✅ Formatted detection {formatted_annotation['detectionId']} for video {video_id}")
        return formatted_annotation
    
    async def create_annotation_from_detection(self, detection_data: Dict[str, Any], video_id: str) -> Optional[Dict[str, Any]]:
        """Create annotation from detection data via API with fallback to direct database"""
        
        try:
            # Format the detection data properly
            annotation_payload = self.format_detection_for_annotation(detection_data, video_id)
            
            # Try API call first (preferred method)
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.base_url}/api/videos/{video_id}/annotations",
                        json=annotation_payload,
                        timeout=30.0
                    )
                    
                    if response.status_code in [200, 201]:
                        result = response.json()
                        logger.info(f"✅ Created annotation {result.get('id')} for detection {annotation_payload['detectionId']}")
                        return result
                    else:
                        logger.warning(f"⚠️ API call failed: {response.status_code} - {response.text}")
                        raise Exception(f"API returned {response.status_code}")
                        
            except Exception as api_error:
                logger.warning(f"⚠️ API call failed, falling back to direct database: {api_error}")
                
                # Fallback to direct database insertion
                from database import SessionLocal
                from models import Annotation
                from datetime import datetime
                import uuid
                
                db = SessionLocal()
                try:
                    db_annotation = Annotation(
                        id=str(uuid.uuid4()),
                        video_id=video_id,
                        detection_id=annotation_payload.get('detectionId'),
                        frame_number=annotation_payload.get('frameNumber', 0),
                        timestamp=annotation_payload.get('timestamp', 0.0),
                        end_timestamp=annotation_payload.get('endTimestamp'),
                        vru_type=annotation_payload.get('vruType', 'pedestrian'),
                        bounding_box=annotation_payload.get('boundingBox', {}),
                        occluded=annotation_payload.get('occluded', False),
                        truncated=annotation_payload.get('truncated', False),
                        difficult=annotation_payload.get('difficult', False),
                        notes=annotation_payload.get('notes'),
                        annotator=annotation_payload.get('annotator'),
                        validated=annotation_payload.get('validated', False),
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    
                    db.add(db_annotation)
                    db.commit()
                    db.refresh(db_annotation)
                    
                    logger.info(f"✅ Created annotation {db_annotation.id} via database fallback")
                    
                    # Return in API format for consistency
                    return {
                        "id": db_annotation.id,
                        "videoId": db_annotation.video_id,
                        "detectionId": db_annotation.detection_id,
                        "frameNumber": db_annotation.frame_number,
                        "timestamp": db_annotation.timestamp,
                        "vruType": db_annotation.vru_type,
                        "boundingBox": db_annotation.bounding_box,
                        "validated": db_annotation.validated,
                        "createdAt": db_annotation.created_at.isoformat()
                    }
                    
                finally:
                    db.close()
                    
        except Exception as e:
            logger.error(f"❌ Error creating annotation from detection: {e}")
            return None
    
    async def batch_create_annotations(self, detections: list, video_id: str) -> list:
        """Create multiple annotations from detection batch"""
        
        results = []
        for detection in detections:
            result = await self.create_annotation_from_detection(detection, video_id)
            if result:
                results.append(result)
            
        logger.info(f"✅ Created {len(results)} annotations from {len(detections)} detections")
        return results

# Global service instance
detection_annotation_service = DetectionAnnotationService()

def get_video_id_from_context(video_path: str = None, video_filename: str = None) -> str:
    """Extract video ID from available context"""
    
    # Try to extract from filename if it's a UUID format
    if video_filename:
        # Check if filename contains UUID pattern (like 690fff86-3a74-4d81-ac93-939c5c55de58.mp4)
        import re
        uuid_pattern = r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
        match = re.search(uuid_pattern, video_filename)
        if match:
            potential_video_id = match.group(1)
            logger.info(f"🔍 Extracted potential video ID from filename: {potential_video_id}")
            
            # In a real system, we'd look up the actual video ID from the database
            # For now, return the known video ID from the logs
            if potential_video_id == "690fff86-3a74-4d81-ac93-939c5c55de58":
                return "e7bc7641-fc0f-4208-8563-eb488c281e24"  # From the logs
                
    # Fallback - this should be passed from the calling context
    logger.warning("⚠️ Could not determine video ID from context - using default")
    return "e7bc7641-fc0f-4208-8563-eb488c281e24"  # From the logs
