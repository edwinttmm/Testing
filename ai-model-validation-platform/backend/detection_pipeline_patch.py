
# PATCH FOR DETECTION PIPELINE SERVICE
# Add this to the detection pipeline to fix the videoId issue

import logging
from detection_annotation_service import detection_annotation_service, get_video_id_from_context

logger = logging.getLogger(__name__)

async def process_detections_with_annotations(detections: list, video_path: str, video_id: str = None):
    """Process detections and create corresponding annotations"""
    
    try:
        # Determine video ID from context
        if not video_id:
            import os
            video_filename = os.path.basename(video_path)
            video_id = get_video_id_from_context(video_path, video_filename)
        
        logger.info(f"🎯 Processing {len(detections)} detections for video {video_id}")
        
        # Create annotations from detections
        annotation_results = await detection_annotation_service.batch_create_annotations(detections, video_id)
        
        logger.info(f"✅ Successfully created {len(annotation_results)} annotations")
        return annotation_results
        
    except Exception as e:
        logger.error(f"❌ Error processing detections with annotations: {e}")
        return []

# Example integration in detection pipeline:
# 
# # After processing video and getting detections:
# detections = await self.process_video(video_path, config)
# 
# # Create annotations from detections:
# video_id = "e7bc7641-fc0f-4208-8563-eb488c281e24"  # Get from context
# annotations = await process_detections_with_annotations(detections, video_path, video_id)
