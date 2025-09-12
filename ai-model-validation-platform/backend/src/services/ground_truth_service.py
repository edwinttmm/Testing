"""
Ground Truth Service - Enhanced Business Logic
SPARC Implementation - Complete service layer for ground truth management
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import uuid
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc

from database import SessionLocal
from models import GroundTruthObject, Video, Project, Annotation
from src.models.ground_truth_models import (
    GroundTruthValidationWorkflow, ValidationHistory, GroundTruthBatch,
    GroundTruthBatchItem, GroundTruthExport, GroundTruthQualityMetrics,
    ValidationStatus, GenerationMethod, QualityLevel
)

logger = logging.getLogger(__name__)

class GroundTruthService:
    """
    Enhanced Ground Truth Service with validation workflows,
    batch processing, and quality management
    """
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.export_formats = {
            'json': self._export_json,
            'coco': self._export_coco,
            'yolo': self._export_yolo,
            'pascal_voc': self._export_pascal_voc
        }
    
    async def calculate_quality_metrics(self, ground_truth_id: str) -> Dict[str, Any]:
        """
        Calculate comprehensive quality metrics for a ground truth object
        """
        db = SessionLocal()
        try:
            gt = db.query(GroundTruthObject).filter(GroundTruthObject.id == ground_truth_id).first()
            if not gt:
                logger.error(f"Ground truth object {ground_truth_id} not found")
                return {}
            
            # Calculate various quality metrics
            annotation_quality = self._calculate_annotation_quality(gt)
            spatial_accuracy = self._calculate_spatial_accuracy(gt)
            temporal_consistency = await self._calculate_temporal_consistency(gt, db)
            complexity_metrics = self._calculate_complexity_metrics_single(gt)
            
            # Create or update quality metrics record
            existing_metrics = db.query(GroundTruthQualityMetrics).filter(
                GroundTruthQualityMetrics.ground_truth_id == ground_truth_id
            ).first()
            
            metrics_data = {
                "calculation_timestamp": datetime.utcnow().isoformat(),
                "method_version": "1.0",
                "additional_metrics": complexity_metrics
            }
            
            if existing_metrics:
                # Update existing metrics
                existing_metrics.annotation_quality_score = annotation_quality
                existing_metrics.spatial_accuracy = spatial_accuracy
                existing_metrics.temporal_consistency = temporal_consistency
                existing_metrics.object_size_score = complexity_metrics.get("object_size_score", 0.0)
                existing_metrics.occlusion_level = complexity_metrics.get("occlusion_level", 0.0)
                existing_metrics.motion_complexity = complexity_metrics.get("motion_complexity", 0.0)
                existing_metrics.background_complexity = complexity_metrics.get("background_complexity", 0.0)
                existing_metrics.metrics_data = metrics_data
                existing_metrics.updated_at = datetime.utcnow()
            else:
                # Create new metrics record
                quality_metrics = GroundTruthQualityMetrics(
                    id=str(uuid.uuid4()),
                    ground_truth_id=ground_truth_id,
                    video_id=gt.video_id,
                    annotation_quality_score=annotation_quality,
                    detection_confidence=gt.confidence,
                    spatial_accuracy=spatial_accuracy,
                    temporal_consistency=temporal_consistency,
                    object_size_score=complexity_metrics.get("object_size_score", 0.0),
                    occlusion_level=complexity_metrics.get("occlusion_level", 0.0),
                    motion_complexity=complexity_metrics.get("motion_complexity", 0.0),
                    background_complexity=complexity_metrics.get("background_complexity", 0.0),
                    metrics_data=metrics_data,
                    calculated_at=datetime.utcnow()
                )
                db.add(quality_metrics)
            
            db.commit()
            
            return {
                "ground_truth_id": ground_truth_id,
                "annotation_quality_score": annotation_quality,
                "spatial_accuracy": spatial_accuracy,
                "temporal_consistency": temporal_consistency,
                "complexity_metrics": complexity_metrics,
                "calculation_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error calculating quality metrics for {ground_truth_id}: {str(e)}")
            return {}
        finally:
            db.close()
    
    def _calculate_annotation_quality(self, gt: GroundTruthObject) -> float:
        """Calculate annotation quality score based on various factors"""
        quality_score = 0.0
        
        # Base quality from confidence if available
        if gt.confidence:
            quality_score += gt.confidence * 0.3
        else:
            quality_score += 0.5  # Default for manual annotations
        
        # Bounding box validity check
        if gt.width > 0 and gt.height > 0:
            quality_score += 0.3
            
            # Reasonable aspect ratio (not too thin or too wide)
            aspect_ratio = gt.width / gt.height
            if 0.1 <= aspect_ratio <= 10.0:
                quality_score += 0.2
        
        # Class label validity
        valid_classes = ['pedestrian', 'cyclist', 'motorcyclist', 'wheelchair', 'scooter', 'animal', 'other']
        if gt.class_label in valid_classes:
            quality_score += 0.2
        
        return min(quality_score, 1.0)
    
    def _calculate_spatial_accuracy(self, gt: GroundTruthObject) -> float:
        """Calculate spatial accuracy of bounding box"""
        # Basic spatial accuracy based on bounding box properties
        if gt.width <= 0 or gt.height <= 0:
            return 0.0
        
        # Area-based scoring (reasonable object sizes)
        area = gt.width * gt.height
        normalized_area = min(area / (640 * 480), 1.0)  # Normalize to typical video resolution
        
        # Position validity (within reasonable bounds)
        position_validity = 1.0
        if gt.x < 0 or gt.y < 0:
            position_validity -= 0.3
        
        # Aspect ratio reasonableness
        aspect_ratio = gt.width / gt.height
        aspect_score = 1.0
        if aspect_ratio > 5.0 or aspect_ratio < 0.2:
            aspect_score -= 0.2
        
        spatial_accuracy = (normalized_area * 0.4 + position_validity * 0.4 + aspect_score * 0.2)
        return min(spatial_accuracy, 1.0)
    
    async def _calculate_temporal_consistency(self, gt: GroundTruthObject, db: Session) -> float:
        """Calculate temporal consistency with nearby ground truth objects"""
        try:
            # Find nearby ground truth objects in time
            time_window = 2.0  # 2 second window
            nearby_objects = db.query(GroundTruthObject).filter(
                and_(
                    GroundTruthObject.video_id == gt.video_id,
                    GroundTruthObject.class_label == gt.class_label,
                    GroundTruthObject.timestamp >= gt.timestamp - time_window,
                    GroundTruthObject.timestamp <= gt.timestamp + time_window,
                    GroundTruthObject.id != gt.id
                )
            ).all()
            
            if not nearby_objects:
                return 0.8  # Default score when no nearby objects for comparison
            
            # Calculate spatial consistency with nearby objects
            consistency_scores = []
            for nearby in nearby_objects:
                # Calculate IoU-like metric
                time_diff = abs(gt.timestamp - nearby.timestamp)
                spatial_similarity = self._calculate_spatial_similarity(gt, nearby)
                
                # Weight by temporal distance
                temporal_weight = max(0, 1.0 - (time_diff / time_window))
                consistency_score = spatial_similarity * temporal_weight
                consistency_scores.append(consistency_score)
            
            if consistency_scores:
                return sum(consistency_scores) / len(consistency_scores)
            else:
                return 0.8
                
        except Exception as e:
            logger.error(f"Error calculating temporal consistency: {str(e)}")
            return 0.5
    
    def _calculate_spatial_similarity(self, gt1: GroundTruthObject, gt2: GroundTruthObject) -> float:
        """Calculate spatial similarity between two ground truth objects"""
        # Calculate intersection over union (IoU)
        x1_min, y1_min = gt1.x, gt1.y
        x1_max, y1_max = gt1.x + gt1.width, gt1.y + gt1.height
        
        x2_min, y2_min = gt2.x, gt2.y
        x2_max, y2_max = gt2.x + gt2.width, gt2.y + gt2.height
        
        # Calculate intersection
        intersect_x_min = max(x1_min, x2_min)
        intersect_y_min = max(y1_min, y2_min)
        intersect_x_max = min(x1_max, x2_max)
        intersect_y_max = min(y1_max, y2_max)
        
        if intersect_x_max <= intersect_x_min or intersect_y_max <= intersect_y_min:
            return 0.0
        
        intersect_area = (intersect_x_max - intersect_x_min) * (intersect_y_max - intersect_y_min)
        
        # Calculate union
        area1 = gt1.width * gt1.height
        area2 = gt2.width * gt2.height
        union_area = area1 + area2 - intersect_area
        
        if union_area <= 0:
            return 0.0
        
        iou = intersect_area / union_area
        return iou
    
    def _calculate_complexity_metrics_single(self, gt: GroundTruthObject) -> Dict[str, float]:
        """Calculate complexity metrics for a single ground truth object"""
        metrics = {}
        
        # Object size complexity
        area = gt.width * gt.height
        normalized_area = area / (640 * 480)  # Normalize to typical resolution
        
        # Smaller objects are more complex to detect
        size_complexity = max(0, 1.0 - normalized_area * 2.0)
        metrics["object_size_score"] = min(size_complexity, 1.0)
        
        # Aspect ratio complexity
        aspect_ratio = gt.width / gt.height if gt.height > 0 else 1.0
        aspect_complexity = 0.0
        if aspect_ratio > 3.0 or aspect_ratio < 0.33:
            aspect_complexity = 0.5
        metrics["aspect_ratio_complexity"] = aspect_complexity
        
        # Placeholder for other complexity metrics
        # (would need image data for actual calculation)
        metrics["occlusion_level"] = 0.0  # Would need image analysis
        metrics["motion_complexity"] = 0.0  # Would need temporal analysis
        metrics["background_complexity"] = 0.0  # Would need scene analysis
        
        return metrics
    
    async def process_batch(self, batch_id: str):
        """Process a batch of videos for ground truth generation"""
        db = SessionLocal()
        try:
            batch = db.query(GroundTruthBatch).options(
                joinedload(GroundTruthBatch.batch_items)
            ).filter(GroundTruthBatch.id == batch_id).first()
            
            if not batch:
                logger.error(f"Batch {batch_id} not found")
                return
            
            # Update batch status
            batch.status = "processing"
            batch.started_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Starting batch processing for {batch.batch_name} with {len(batch.batch_items)} items")
            
            successful_items = 0
            failed_items = 0
            
            # Process each batch item
            for item in batch.batch_items:
                try:
                    await self._process_batch_item(item, db)
                    successful_items += 1
                    batch.successful_videos = successful_items
                except Exception as e:
                    logger.error(f"Error processing batch item {item.id}: {str(e)}")
                    failed_items += 1
                    item.status = "failed"
                    item.error_message = str(e)
                    item.completed_at = datetime.utcnow()
                    batch.failed_videos = failed_items
                
                # Update progress
                batch.processed_videos = successful_items + failed_items
                db.commit()
            
            # Complete batch
            batch.status = "completed" if failed_items == 0 else "completed_with_errors"
            batch.completed_at = datetime.utcnow()
            batch.performance_metrics = {
                "total_processing_time": (batch.completed_at - batch.started_at).total_seconds(),
                "average_time_per_video": (batch.completed_at - batch.started_at).total_seconds() / len(batch.batch_items),
                "success_rate": successful_items / len(batch.batch_items) * 100
            }
            
            db.commit()
            logger.info(f"Batch processing completed: {successful_items} successful, {failed_items} failed")
            
        except Exception as e:
            logger.error(f"Error processing batch {batch_id}: {str(e)}")
            batch.status = "failed"
            batch.completed_at = datetime.utcnow()
            batch.error_log = {"error": str(e), "timestamp": datetime.utcnow().isoformat()}
            db.commit()
        finally:
            db.close()
    
    async def _process_batch_item(self, item: GroundTruthBatchItem, db: Session):
        """Process a single batch item"""
        from src.services.ml_generation_service import MLGenerationService
        
        item.status = "processing"
        item.started_at = datetime.utcnow()
        db.commit()
        
        # Get video
        video = db.query(Video).filter(Video.id == item.video_id).first()
        if not video:
            raise Exception(f"Video {item.video_id} not found")
        
        # Generate ground truth using ML service
        ml_service = MLGenerationService()
        detections_count = await ml_service.generate_ground_truth(
            item.video_id,
            confidence_threshold=item.processing_config.get("confidence_threshold", 0.5),
            method=GenerationMethod.AUTOMATED_ML
        )
        
        # Update item
        item.status = "completed"
        item.detections_generated = detections_count
        item.completed_at = datetime.utcnow()
        item.processing_time_seconds = (item.completed_at - item.started_at).total_seconds()
        
        db.commit()
    
    async def process_export(self, export_id: str):
        """Process ground truth export job"""
        db = SessionLocal()
        try:
            export = db.query(GroundTruthExport).filter(GroundTruthExport.id == export_id).first()
            if not export:
                logger.error(f"Export {export_id} not found")
                return
            
            # Update export status
            export.status = "processing"
            export.started_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Starting export processing for {export.export_name}")
            
            # Get ground truth objects based on filters
            ground_truth_objects = self._get_filtered_ground_truth(export, db)
            
            # Generate export file
            export_function = self.export_formats.get(export.format_type)
            if not export_function:
                raise Exception(f"Unsupported export format: {export.format_type}")
            
            file_path, file_size = await export_function(export, ground_truth_objects, db)
            
            # Update export record
            export.file_path = file_path
            export.file_size_bytes = file_size
            export.total_objects = len(ground_truth_objects)
            export.status = "completed"
            export.completed_at = datetime.utcnow()
            export.expires_at = datetime.utcnow() + timedelta(days=7)  # Expires in 7 days
            
            # Calculate statistics
            class_distribution = {}
            for gt in ground_truth_objects:
                class_distribution[gt.class_label] = class_distribution.get(gt.class_label, 0) + 1
            export.class_distribution = class_distribution
            
            db.commit()
            logger.info(f"Export completed: {file_path} ({file_size} bytes)")
            
        except Exception as e:
            logger.error(f"Error processing export {export_id}: {str(e)}")
            export.status = "failed"
            export.error_message = str(e)
            export.completed_at = datetime.utcnow()
            db.commit()
        finally:
            db.close()
    
    def _get_filtered_ground_truth(self, export: GroundTruthExport, db: Session) -> List[GroundTruthObject]:
        """Get ground truth objects based on export filters"""
        query = db.query(GroundTruthObject).options(joinedload(GroundTruthObject.video))
        
        # Apply video filter
        video_filter = export.video_filter
        if video_filter:
            if video_filter.get("project_ids"):
                query = query.join(Video).filter(Video.project_id.in_(video_filter["project_ids"]))
            if video_filter.get("video_ids"):
                query = query.filter(GroundTruthObject.video_id.in_(video_filter["video_ids"]))
        
        # Apply quality filter
        quality_filter = export.quality_filter
        if quality_filter:
            if quality_filter.get("min_confidence"):
                query = query.filter(GroundTruthObject.confidence >= quality_filter["min_confidence"])
            if quality_filter.get("validated_only"):
                query = query.filter(GroundTruthObject.validated == True)
            if quality_filter.get("exclude_difficult"):
                query = query.filter(GroundTruthObject.difficult == False)
        
        # Apply validation filter
        validation_filter = export.validation_filter
        if validation_filter:
            validation_statuses = validation_filter.get("validation_statuses")
            if validation_statuses:
                query = query.join(GroundTruthValidationWorkflow).filter(
                    GroundTruthValidationWorkflow.validation_status.in_(validation_statuses)
                )
        
        return query.all()
    
    async def _export_json(self, export: GroundTruthExport, objects: List[GroundTruthObject], db: Session) -> tuple:
        """Export ground truth in JSON format"""
        export_data = {
            "export_info": {
                "export_id": export.id,
                "export_name": export.export_name,
                "created_at": export.created_at.isoformat(),
                "format": "json",
                "total_objects": len(objects)
            },
            "ground_truth_objects": []
        }
        
        for gt in objects:
            export_data["ground_truth_objects"].append({
                "id": gt.id,
                "video_id": gt.video_id,
                "frame_number": gt.frame_number,
                "timestamp": gt.timestamp,
                "class_label": gt.class_label,
                "bounding_box": {
                    "x": gt.x,
                    "y": gt.y,
                    "width": gt.width,
                    "height": gt.height
                },
                "confidence": gt.confidence,
                "validated": gt.validated,
                "difficult": gt.difficult,
                "created_at": gt.created_at.isoformat() if gt.created_at else None
            })
        
        # Save to file
        export_dir = "/tmp/ground_truth_exports"
        os.makedirs(export_dir, exist_ok=True)
        
        file_path = os.path.join(export_dir, f"{export.id}.json")
        with open(file_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        file_size = os.path.getsize(file_path)
        return file_path, file_size
    
    async def _export_coco(self, export: GroundTruthExport, objects: List[GroundTruthObject], db: Session) -> tuple:
        """Export ground truth in COCO format"""
        # COCO format implementation
        categories = []
        class_names = list(set(gt.class_label for gt in objects))
        for i, class_name in enumerate(class_names):
            categories.append({
                "id": i + 1,
                "name": class_name,
                "supercategory": "vru"
            })
        
        images = []
        annotations = []
        video_info = {}
        
        # Group by video and get video info
        for gt in objects:
            if gt.video_id not in video_info:
                video = db.query(Video).filter(Video.id == gt.video_id).first()
                video_info[gt.video_id] = {
                    "id": len(video_info) + 1,
                    "video_id": gt.video_id,
                    "file_name": video.filename if video else f"video_{gt.video_id}",
                    "width": 1920,  # Default resolution
                    "height": 1080
                }
                images.append(video_info[gt.video_id])
            
            category_id = class_names.index(gt.class_label) + 1
            annotations.append({
                "id": len(annotations) + 1,
                "image_id": video_info[gt.video_id]["id"],
                "category_id": category_id,
                "bbox": [gt.x, gt.y, gt.width, gt.height],
                "area": gt.width * gt.height,
                "iscrowd": 0,
                "timestamp": gt.timestamp,
                "frame_number": gt.frame_number
            })
        
        coco_data = {
            "info": {
                "description": f"Ground Truth Export - {export.export_name}",
                "version": "1.0",
                "year": datetime.now().year,
                "contributor": "AI Model Validation Platform",
                "date_created": datetime.now().isoformat()
            },
            "licenses": [{"id": 1, "name": "Custom License", "url": ""}],
            "images": images,
            "annotations": annotations,
            "categories": categories
        }
        
        # Save to file
        export_dir = "/tmp/ground_truth_exports"
        os.makedirs(export_dir, exist_ok=True)
        
        file_path = os.path.join(export_dir, f"{export.id}_coco.json")
        with open(file_path, 'w') as f:
            json.dump(coco_data, f, indent=2)
        
        file_size = os.path.getsize(file_path)
        return file_path, file_size
    
    async def _export_yolo(self, export: GroundTruthExport, objects: List[GroundTruthObject], db: Session) -> tuple:
        """Export ground truth in YOLO format"""
        # YOLO format implementation
        export_dir = "/tmp/ground_truth_exports"
        yolo_dir = os.path.join(export_dir, f"{export.id}_yolo")
        os.makedirs(yolo_dir, exist_ok=True)
        
        # Create class mapping
        class_names = list(set(gt.class_label for gt in objects))
        with open(os.path.join(yolo_dir, "classes.txt"), 'w') as f:
            for class_name in class_names:
                f.write(f"{class_name}\n")
        
        # Group by video
        video_annotations = {}
        for gt in objects:
            if gt.video_id not in video_annotations:
                video_annotations[gt.video_id] = []
            video_annotations[gt.video_id].append(gt)
        
        # Create annotation files
        for video_id, annotations in video_annotations.items():
            annotation_file = os.path.join(yolo_dir, f"{video_id}.txt")
            with open(annotation_file, 'w') as f:
                for gt in annotations:
                    class_id = class_names.index(gt.class_label)
                    # Convert to YOLO format (normalized coordinates)
                    # Assuming 1920x1080 resolution for normalization
                    x_center = (gt.x + gt.width / 2) / 1920
                    y_center = (gt.y + gt.height / 2) / 1080
                    width_norm = gt.width / 1920
                    height_norm = gt.height / 1080
                    
                    f.write(f"{class_id} {x_center} {y_center} {width_norm} {height_norm}\n")
        
        # Create archive
        import shutil
        archive_path = f"{yolo_dir}.zip"
        shutil.make_archive(yolo_dir, 'zip', yolo_dir)
        
        file_size = os.path.getsize(archive_path)
        return archive_path, file_size
    
    async def _export_pascal_voc(self, export: GroundTruthExport, objects: List[GroundTruthObject], db: Session) -> tuple:
        """Export ground truth in Pascal VOC format"""
        # Pascal VOC format implementation placeholder
        # Would need XML generation for each video/frame
        export_dir = "/tmp/ground_truth_exports"
        os.makedirs(export_dir, exist_ok=True)
        
        file_path = os.path.join(export_dir, f"{export.id}_pascal_voc.xml")
        
        # Simplified Pascal VOC export (would need proper XML structure)
        with open(file_path, 'w') as f:
            f.write('<?xml version="1.0"?>\n')
            f.write('<dataset>\n')
            f.write(f'  <name>{export.export_name}</name>\n')
            f.write(f'  <total_objects>{len(objects)}</total_objects>\n')
            f.write('</dataset>\n')
        
        file_size = os.path.getsize(file_path)
        return file_path, file_size
    
    def calculate_quality_distribution(self, metrics: List[GroundTruthQualityMetrics]) -> Dict[str, int]:
        """Calculate quality distribution from metrics"""
        distribution = {"high": 0, "medium": 0, "low": 0}
        
        for metric in metrics:
            if metric.annotation_quality_score >= 0.8:
                distribution["high"] += 1
            elif metric.annotation_quality_score >= 0.5:
                distribution["medium"] += 1
            else:
                distribution["low"] += 1
        
        return distribution
    
    def calculate_complexity_metrics(self, metrics: List[GroundTruthQualityMetrics]) -> Dict[str, float]:
        """Calculate aggregated complexity metrics"""
        if not metrics:
            return {}
        
        total_objects = len(metrics)
        
        return {
            "average_object_size_complexity": sum(m.object_size_score or 0 for m in metrics) / total_objects,
            "average_occlusion_level": sum(m.occlusion_level or 0 for m in metrics) / total_objects,
            "average_motion_complexity": sum(m.motion_complexity or 0 for m in metrics) / total_objects,
            "average_background_complexity": sum(m.background_complexity or 0 for m in metrics) / total_objects,
            "complexity_distribution": self._calculate_complexity_distribution(metrics)
        }
    
    def _calculate_complexity_distribution(self, metrics: List[GroundTruthQualityMetrics]) -> Dict[str, int]:
        """Calculate complexity distribution"""
        distribution = {"simple": 0, "moderate": 0, "complex": 0}
        
        for metric in metrics:
            # Calculate overall complexity score
            complexity_score = (
                (metric.object_size_score or 0) +
                (metric.occlusion_level or 0) +
                (metric.motion_complexity or 0) +
                (metric.background_complexity or 0)
            ) / 4
            
            if complexity_score < 0.3:
                distribution["simple"] += 1
            elif complexity_score < 0.7:
                distribution["moderate"] += 1
            else:
                distribution["complex"] += 1
        
        return distribution