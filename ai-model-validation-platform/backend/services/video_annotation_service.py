from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Optional, Dict, Any
import uuid
import json
import logging
from datetime import datetime
from pathlib import Path
import csv
import xml.etree.ElementTree as ET

from models import Annotation, Video, AnnotationSession
from schemas_video_annotation import (
    AnnotationCreate, AnnotationUpdate, AnnotationResponse,
    ExportFormatEnum
)

logger = logging.getLogger(__name__)

class VideoAnnotationService:
    """Service for managing video annotations with comprehensive CRUD operations"""
    
    def __init__(self):
        self.export_directory = Path("exports/annotations")
        self.export_directory.mkdir(parents=True, exist_ok=True)
    
    async def create_annotation(
        self, 
        db: Session, 
        video_id: str, 
        annotation_data: AnnotationCreate
    ) -> Annotation:
        """Create a new annotation with validation"""
        try:
            # Generate detection ID if not provided
            detection_id = annotation_data.detection_id or self._generate_detection_id(
                annotation_data.vru_type, annotation_data.frame_number
            )
            
            # Create annotation record
            annotation = Annotation(
                id=str(uuid.uuid4()),
                video_id=video_id,
                detection_id=detection_id,
                frame_number=annotation_data.frame_number,
                timestamp=annotation_data.timestamp,
                end_timestamp=annotation_data.end_timestamp,
                vru_type=annotation_data.vru_type.value,
                bounding_box=annotation_data.bounding_box.dict(),
                occluded=annotation_data.occluded,
                truncated=annotation_data.truncated,
                difficult=annotation_data.difficult,
                notes=annotation_data.notes,
                annotator=annotation_data.annotator,
                validated=annotation_data.validated,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(annotation)
            db.commit()
            db.refresh(annotation)
            
            logger.info(f"Created annotation {annotation.id} for video {video_id}")
            return annotation
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating annotation: {str(e)}")
            raise
    
    async def create_bulk_annotations(
        self, 
        db: Session, 
        video_id: str, 
        annotations_data: List[AnnotationCreate]
    ) -> List[Annotation]:
        """Create multiple annotations in a single transaction"""
        try:
            annotations = []
            
            for annotation_data in annotations_data:
                # Generate detection ID if not provided
                detection_id = annotation_data.detection_id or self._generate_detection_id(
                    annotation_data.vru_type, annotation_data.frame_number
                )
                
                annotation = Annotation(
                    id=str(uuid.uuid4()),
                    video_id=video_id,
                    detection_id=detection_id,
                    frame_number=annotation_data.frame_number,
                    timestamp=annotation_data.timestamp,
                    end_timestamp=annotation_data.end_timestamp,
                    vru_type=annotation_data.vru_type.value,
                    bounding_box=annotation_data.bounding_box.dict(),
                    occluded=annotation_data.occluded,
                    truncated=annotation_data.truncated,
                    difficult=annotation_data.difficult,
                    notes=annotation_data.notes,
                    annotator=annotation_data.annotator,
                    validated=annotation_data.validated,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                annotations.append(annotation)
            
            # Add all annotations in batch
            db.add_all(annotations)
            db.commit()
            
            # Refresh all annotations
            for annotation in annotations:
                db.refresh(annotation)
            
            logger.info(f"Created {len(annotations)} annotations for video {video_id}")
            return annotations
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating bulk annotations: {str(e)}")
            raise
    
    async def update_annotation(
        self, 
        db: Session, 
        annotation_id: str, 
        update_data: AnnotationUpdate
    ) -> Optional[Annotation]:
        """Update an existing annotation"""
        try:
            # Get existing annotation
            annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
            if not annotation:
                return None
            
            # Update fields that are provided
            update_dict = update_data.dict(exclude_unset=True)
            
            for field, value in update_dict.items():
                if field == "vru_type" and value:
                    setattr(annotation, field, value.value)
                elif field == "bounding_box" and value:
                    setattr(annotation, field, value.dict())
                elif value is not None:
                    setattr(annotation, field, value)
            
            annotation.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(annotation)
            
            logger.info(f"Updated annotation {annotation_id}")
            return annotation
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating annotation: {str(e)}")
            raise
    
    async def delete_annotation(self, db: Session, annotation_id: str) -> bool:
        """Delete an annotation"""
        try:
            annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
            if not annotation:
                return False
            
            db.delete(annotation)
            db.commit()
            
            logger.info(f"Deleted annotation {annotation_id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting annotation: {str(e)}")
            raise
    
    async def get_video_annotations(
        self, 
        db: Session, 
        video_id: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Annotation]:
        """Get annotations for a video with optional filters"""
        try:
            query = db.query(Annotation).filter(Annotation.video_id == video_id)
            
            if filters:
                if filters.get("validated_only"):
                    query = query.filter(Annotation.validated == True)
                
                if filters.get("vru_type"):
                    query = query.filter(Annotation.vru_type == filters["vru_type"])
                
                if filters.get("frame_start"):
                    query = query.filter(Annotation.frame_number >= filters["frame_start"])
                
                if filters.get("frame_end"):
                    query = query.filter(Annotation.frame_number <= filters["frame_end"])
                
                if filters.get("annotator"):
                    query = query.filter(Annotation.annotator == filters["annotator"])
            
            annotations = query.order_by(Annotation.frame_number).all()
            
            logger.info(f"Retrieved {len(annotations)} annotations for video {video_id}")
            return annotations
            
        except Exception as e:
            logger.error(f"Error getting video annotations: {str(e)}")
            raise
    
    async def export_annotations(
        self, 
        db: Session, 
        video_id: str, 
        export_format: ExportFormatEnum,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """Export annotations in various formats"""
        try:
            # Get annotations
            annotations = await self.get_video_annotations(db, video_id)
            
            if not annotations:
                raise ValueError("No annotations found for export")
            
            # Get video info
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                raise ValueError("Video not found")
            
            # Generate export based on format
            if export_format == ExportFormatEnum.JSON:
                export_result = await self._export_json(annotations, video, include_metadata)
            elif export_format == ExportFormatEnum.CSV:
                export_result = await self._export_csv(annotations, video, include_metadata)
            elif export_format == ExportFormatEnum.XML:
                export_result = await self._export_xml(annotations, video, include_metadata)
            elif export_format == ExportFormatEnum.COCO:
                export_result = await self._export_coco(annotations, video, include_metadata)
            elif export_format == ExportFormatEnum.YOLO:
                export_result = await self._export_yolo(annotations, video, include_metadata)
            elif export_format == ExportFormatEnum.PASCAL_VOC:
                export_result = await self._export_pascal_voc(annotations, video, include_metadata)
            else:
                raise ValueError(f"Unsupported export format: {export_format}")
            
            logger.info(f"Exported {len(annotations)} annotations in {export_format} format")
            return export_result
            
        except Exception as e:
            logger.error(f"Error exporting annotations: {str(e)}")
            raise
    
    def _generate_detection_id(self, vru_type: str, frame_number: int) -> str:
        """Generate a unique detection ID"""
        prefix_map = {
            "pedestrian": "PED",
            "cyclist": "CYC", 
            "motorcyclist": "MOT",
            "wheelchair": "WHE",
            "scooter": "SCO",
            "animal": "ANI",
            "other": "OTH"
        }
        
        prefix = prefix_map.get(vru_type, "DET")
        return f"DET_{prefix}_{frame_number:06d}_{uuid.uuid4().hex[:8].upper()}"
    
    async def _export_json(
        self, 
        annotations: List[Annotation], 
        video: Video, 
        include_metadata: bool
    ) -> Dict[str, Any]:
        """Export annotations as JSON"""
        export_data = {
            "video": {
                "id": video.id,
                "filename": video.filename,
                "duration": video.duration,
                "fps": video.fps,
                "resolution": video.resolution
            } if include_metadata else {"id": video.id},
            "annotations": [
                {
                    "id": ann.id,
                    "detection_id": ann.detection_id,
                    "frame_number": ann.frame_number,
                    "timestamp": ann.timestamp,
                    "end_timestamp": ann.end_timestamp,
                    "vru_type": ann.vru_type,
                    "bounding_box": ann.bounding_box,
                    "occluded": ann.occluded,
                    "truncated": ann.truncated,
                    "difficult": ann.difficult,
                    "validated": ann.validated,
                    "notes": ann.notes,
                    "annotator": ann.annotator,
                    "created_at": ann.created_at.isoformat() if ann.created_at else None
                }
                for ann in annotations
            ],
            "export_metadata": {
                "total_annotations": len(annotations),
                "export_timestamp": datetime.utcnow().isoformat(),
                "format": "json"
            } if include_metadata else {}
        }
        
        # Save to file
        filename = f"annotations_{video.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        file_path = self.export_directory / filename
        
        with open(file_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        return {
            "url": str(file_path),
            "filename": filename,
            "file_size": file_path.stat().st_size,
            "annotation_count": len(annotations)
        }
    
    async def _export_csv(
        self, 
        annotations: List[Annotation], 
        video: Video, 
        include_metadata: bool
    ) -> Dict[str, Any]:
        """Export annotations as CSV"""
        filename = f"annotations_{video.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path = self.export_directory / filename
        
        with open(file_path, 'w', newline='') as csvfile:
            fieldnames = [
                'id', 'detection_id', 'frame_number', 'timestamp', 'end_timestamp',
                'vru_type', 'bbox_x', 'bbox_y', 'bbox_width', 'bbox_height',
                'occluded', 'truncated', 'difficult', 'validated', 'notes', 
                'annotator', 'created_at'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for ann in annotations:
                bbox = ann.bounding_box or {}
                writer.writerow({
                    'id': ann.id,
                    'detection_id': ann.detection_id,
                    'frame_number': ann.frame_number,
                    'timestamp': ann.timestamp,
                    'end_timestamp': ann.end_timestamp,
                    'vru_type': ann.vru_type,
                    'bbox_x': bbox.get('x', 0),
                    'bbox_y': bbox.get('y', 0),
                    'bbox_width': bbox.get('width', 0),
                    'bbox_height': bbox.get('height', 0),
                    'occluded': ann.occluded,
                    'truncated': ann.truncated,
                    'difficult': ann.difficult,
                    'validated': ann.validated,
                    'notes': ann.notes or '',
                    'annotator': ann.annotator or '',
                    'created_at': ann.created_at.isoformat() if ann.created_at else ''
                })
        
        return {
            "url": str(file_path),
            "filename": filename,
            "file_size": file_path.stat().st_size,
            "annotation_count": len(annotations)
        }
    
    async def _export_xml(
        self, 
        annotations: List[Annotation], 
        video: Video, 
        include_metadata: bool
    ) -> Dict[str, Any]:
        """Export annotations as XML"""
        root = ET.Element('annotations')
        
        if include_metadata:
            video_elem = ET.SubElement(root, 'video')
            ET.SubElement(video_elem, 'id').text = video.id
            ET.SubElement(video_elem, 'filename').text = video.filename
            if video.duration:
                ET.SubElement(video_elem, 'duration').text = str(video.duration)
            if video.fps:
                ET.SubElement(video_elem, 'fps').text = str(video.fps)
            if video.resolution:
                ET.SubElement(video_elem, 'resolution').text = video.resolution
        
        annotations_elem = ET.SubElement(root, 'annotation_list')
        
        for ann in annotations:
            ann_elem = ET.SubElement(annotations_elem, 'annotation')
            ET.SubElement(ann_elem, 'id').text = ann.id
            ET.SubElement(ann_elem, 'detection_id').text = ann.detection_id or ''
            ET.SubElement(ann_elem, 'frame_number').text = str(ann.frame_number)
            ET.SubElement(ann_elem, 'timestamp').text = str(ann.timestamp)
            if ann.end_timestamp:
                ET.SubElement(ann_elem, 'end_timestamp').text = str(ann.end_timestamp)
            ET.SubElement(ann_elem, 'vru_type').text = ann.vru_type
            
            bbox_elem = ET.SubElement(ann_elem, 'bounding_box')
            bbox = ann.bounding_box or {}
            ET.SubElement(bbox_elem, 'x').text = str(bbox.get('x', 0))
            ET.SubElement(bbox_elem, 'y').text = str(bbox.get('y', 0))
            ET.SubElement(bbox_elem, 'width').text = str(bbox.get('width', 0))
            ET.SubElement(bbox_elem, 'height').text = str(bbox.get('height', 0))
            
            ET.SubElement(ann_elem, 'occluded').text = str(ann.occluded)
            ET.SubElement(ann_elem, 'truncated').text = str(ann.truncated)
            ET.SubElement(ann_elem, 'difficult').text = str(ann.difficult)
            ET.SubElement(ann_elem, 'validated').text = str(ann.validated)
            
            if ann.notes:
                ET.SubElement(ann_elem, 'notes').text = ann.notes
            if ann.annotator:
                ET.SubElement(ann_elem, 'annotator').text = ann.annotator
        
        # Save to file
        filename = f"annotations_{video.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xml"
        file_path = self.export_directory / filename
        
        tree = ET.ElementTree(root)
        tree.write(file_path, encoding='utf-8', xml_declaration=True)
        
        return {
            "url": str(file_path),
            "filename": filename,
            "file_size": file_path.stat().st_size,
            "annotation_count": len(annotations)
        }
    
    async def _export_coco(
        self, 
        annotations: List[Annotation], 
        video: Video, 
        include_metadata: bool
    ) -> Dict[str, Any]:
        """Export annotations in COCO format"""
        # COCO format structure
        coco_data = {
            "info": {
                "description": "AI Model Validation Platform Annotations",
                "version": "1.0",
                "year": datetime.utcnow().year,
                "date_created": datetime.utcnow().isoformat()
            },
            "images": [{
                "id": 1,
                "file_name": video.filename,
                "width": int(video.resolution.split('x')[0]) if video.resolution and 'x' in video.resolution else 1920,
                "height": int(video.resolution.split('x')[1]) if video.resolution and 'x' in video.resolution else 1080
            }],
            "categories": [
                {"id": 1, "name": "pedestrian"},
                {"id": 2, "name": "cyclist"},
                {"id": 3, "name": "motorcyclist"},
                {"id": 4, "name": "wheelchair"},
                {"id": 5, "name": "scooter"},
                {"id": 6, "name": "animal"},
                {"id": 7, "name": "other"}
            ],
            "annotations": []
        }
        
        category_map = {
            "pedestrian": 1, "cyclist": 2, "motorcyclist": 3,
            "wheelchair": 4, "scooter": 5, "animal": 6, "other": 7
        }
        
        for i, ann in enumerate(annotations):
            bbox = ann.bounding_box or {}
            coco_annotation = {
                "id": i + 1,
                "image_id": 1,
                "category_id": category_map.get(ann.vru_type, 7),
                "bbox": [bbox.get('x', 0), bbox.get('y', 0), bbox.get('width', 0), bbox.get('height', 0)],
                "area": bbox.get('width', 0) * bbox.get('height', 0),
                "iscrowd": 0,
                "attributes": {
                    "occluded": ann.occluded,
                    "truncated": ann.truncated,
                    "difficult": ann.difficult,
                    "validated": ann.validated
                }
            }
            coco_data["annotations"].append(coco_annotation)
        
        # Save to file
        filename = f"annotations_{video.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_coco.json"
        file_path = self.export_directory / filename
        
        with open(file_path, 'w') as f:
            json.dump(coco_data, f, indent=2)
        
        return {
            "url": str(file_path),
            "filename": filename,
            "file_size": file_path.stat().st_size,
            "annotation_count": len(annotations)
        }
    
    async def _export_yolo(
        self, 
        annotations: List[Annotation], 
        video: Video, 
        include_metadata: bool
    ) -> Dict[str, Any]:
        """Export annotations in YOLO format"""
        # YOLO format: class x_center y_center width height (normalized)
        filename = f"annotations_{video.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_yolo.txt"
        file_path = self.export_directory / filename
        
        # Get image dimensions
        img_width = int(video.resolution.split('x')[0]) if video.resolution and 'x' in video.resolution else 1920
        img_height = int(video.resolution.split('x')[1]) if video.resolution and 'x' in video.resolution else 1080
        
        class_map = {
            "pedestrian": 0, "cyclist": 1, "motorcyclist": 2,
            "wheelchair": 3, "scooter": 4, "animal": 5, "other": 6
        }
        
        with open(file_path, 'w') as f:
            for ann in annotations:
                bbox = ann.bounding_box or {}
                
                # Convert to YOLO format (normalized coordinates)
                x = bbox.get('x', 0)
                y = bbox.get('y', 0)
                width = bbox.get('width', 0)
                height = bbox.get('height', 0)
                
                x_center = (x + width / 2) / img_width
                y_center = (y + height / 2) / img_height
                norm_width = width / img_width
                norm_height = height / img_height
                
                class_id = class_map.get(ann.vru_type, 6)
                
                f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {norm_width:.6f} {norm_height:.6f}\n")
        
        return {
            "url": str(file_path),
            "filename": filename,
            "file_size": file_path.stat().st_size,
            "annotation_count": len(annotations)
        }
    
    async def _export_pascal_voc(
        self, 
        annotations: List[Annotation], 
        video: Video, 
        include_metadata: bool
    ) -> Dict[str, Any]:
        """Export annotations in PASCAL VOC XML format"""
        root = ET.Element('annotation')
        
        # Add folder, filename, and source
        ET.SubElement(root, 'folder').text = 'video_annotations'
        ET.SubElement(root, 'filename').text = video.filename
        
        source = ET.SubElement(root, 'source')
        ET.SubElement(source, 'database').text = 'AI Model Validation Platform'
        
        # Add image size
        size = ET.SubElement(root, 'size')
        img_width = int(video.resolution.split('x')[0]) if video.resolution and 'x' in video.resolution else 1920
        img_height = int(video.resolution.split('x')[1]) if video.resolution and 'x' in video.resolution else 1080
        ET.SubElement(size, 'width').text = str(img_width)
        ET.SubElement(size, 'height').text = str(img_height)
        ET.SubElement(size, 'depth').text = '3'
        
        ET.SubElement(root, 'segmented').text = '0'
        
        # Add objects
        for ann in annotations:
            obj = ET.SubElement(root, 'object')
            ET.SubElement(obj, 'name').text = ann.vru_type
            ET.SubElement(obj, 'pose').text = 'Unspecified'
            ET.SubElement(obj, 'truncated').text = '1' if ann.truncated else '0'
            ET.SubElement(obj, 'difficult').text = '1' if ann.difficult else '0'
            
            bbox = ann.bounding_box or {}
            bndbox = ET.SubElement(obj, 'bndbox')
            ET.SubElement(bndbox, 'xmin').text = str(int(bbox.get('x', 0)))
            ET.SubElement(bndbox, 'ymin').text = str(int(bbox.get('y', 0)))
            ET.SubElement(bndbox, 'xmax').text = str(int(bbox.get('x', 0) + bbox.get('width', 0)))
            ET.SubElement(bndbox, 'ymax').text = str(int(bbox.get('y', 0) + bbox.get('height', 0)))
        
        # Save to file
        filename = f"annotations_{video.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_voc.xml"
        file_path = self.export_directory / filename
        
        tree = ET.ElementTree(root)
        tree.write(file_path, encoding='utf-8', xml_declaration=True)
        
        return {
            "url": str(file_path),
            "filename": filename,
            "file_size": file_path.stat().st_size,
            "annotation_count": len(annotations)
        }
