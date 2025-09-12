"""
Annotation Export Service
SPARC Implementation - Export annotations to various formats (JSON, COCO, YOLO, etc.)
"""

import json
import csv
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from pathlib import Path
import zipfile
import io
import logging

from sqlalchemy.orm import Session
from models import Annotation, Video, Project

logger = logging.getLogger(__name__)


class AnnotationExportService:
    """Service for exporting annotations to various formats"""
    
    def __init__(self):
        self.supported_formats = [
            "json", "coco", "yolo", "csv", "pascal_voc", "kitti", "labelimg"
        ]
    
    def export_annotations(self, db: Session, video_id: str, 
                          export_format: str, 
                          export_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Export annotations in specified format
        
        Args:
            db: Database session
            video_id: Video ID to export annotations for
            export_format: Format to export (json, coco, yolo, etc.)
            export_options: Additional export options
            
        Returns:
            Dictionary with export result and file data
        """
        try:
            if export_format not in self.supported_formats:
                return {
                    "success": False,
                    "error": f"Unsupported format: {export_format}. Supported: {self.supported_formats}",
                    "code": "UNSUPPORTED_FORMAT"
                }
            
            # Get video and annotations
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                return {
                    "success": False,
                    "error": "Video not found",
                    "code": "VIDEO_NOT_FOUND"
                }
            
            annotations = db.query(Annotation).filter(
                Annotation.video_id == video_id
            ).order_by(Annotation.timestamp).all()
            
            if not annotations:
                return {
                    "success": False,
                    "error": "No annotations found for video",
                    "code": "NO_ANNOTATIONS"
                }
            
            # Get project info
            project = db.query(Project).filter(Project.id == video.project_id).first()
            
            # Export based on format
            export_method = getattr(self, f"_export_{export_format}")
            export_data = export_method(video, annotations, project, export_options or {})
            
            logger.info(f"Exported {len(annotations)} annotations for video {video_id} in {export_format} format")
            
            return {
                "success": True,
                "format": export_format,
                "annotation_count": len(annotations),
                "video_info": {
                    "id": video.id,
                    "filename": video.filename,
                    "resolution": video.resolution,
                    "duration": video.duration,
                    "fps": video.fps
                },
                "export_data": export_data,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error exporting annotations for video {video_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Export error: {str(e)}",
                "code": "EXPORT_ERROR"
            }
    
    def _export_json(self, video: Video, annotations: List[Annotation], 
                     project: Optional[Project], options: Dict[str, Any]) -> Dict[str, Any]:
        """Export annotations as JSON format"""
        
        # Video metadata
        video_info = {
            "id": video.id,
            "filename": video.filename,
            "resolution": video.resolution,
            "duration": video.duration,
            "fps": video.fps,
            "file_size": video.file_size
        }
        
        # Project metadata
        project_info = None
        if project:
            project_info = {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "camera_model": project.camera_model,
                "camera_view": project.camera_view
            }
        
        # Annotations
        annotation_data = []
        for ann in annotations:
            annotation_data.append({
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
                "notes": ann.notes,
                "annotator": ann.annotator,
                "validated": ann.validated,
                "created_at": ann.created_at.isoformat() if ann.created_at else None,
                "updated_at": ann.updated_at.isoformat() if ann.updated_at else None
            })
        
        export_data = {
            "format": "json",
            "version": "1.0",
            "exported_at": datetime.utcnow().isoformat(),
            "video": video_info,
            "project": project_info,
            "annotation_count": len(annotations),
            "annotations": annotation_data
        }
        
        return {
            "content_type": "application/json",
            "filename": f"{video.filename}_annotations.json",
            "data": json.dumps(export_data, indent=2)
        }
    
    def _export_coco(self, video: Video, annotations: List[Annotation], 
                     project: Optional[Project], options: Dict[str, Any]) -> Dict[str, Any]:
        """Export annotations in COCO format"""
        
        # COCO format structure
        coco_data = {
            "info": {
                "description": f"VRU Annotations for {video.filename}",
                "version": "1.0",
                "year": datetime.now().year,
                "contributor": project.name if project else "AI Model Validation Platform",
                "date_created": datetime.utcnow().isoformat()
            },
            "licenses": [
                {
                    "id": 1,
                    "name": "Custom License",
                    "url": ""
                }
            ],
            "images": [
                {
                    "id": 1,
                    "width": int(video.resolution.split("x")[0]) if video.resolution else 1920,
                    "height": int(video.resolution.split("x")[1]) if video.resolution else 1080,
                    "file_name": video.filename,
                    "license": 1,
                    "flickr_url": "",
                    "coco_url": "",
                    "date_captured": video.created_at.isoformat() if video.created_at else ""
                }
            ],
            "categories": [],
            "annotations": []
        }
        
        # Create categories from unique VRU types
        vru_types = list(set(ann.vru_type for ann in annotations))
        for i, vru_type in enumerate(vru_types, 1):
            coco_data["categories"].append({
                "id": i,
                "name": vru_type,
                "supercategory": "vru"
            })
        
        # Create category mapping
        category_map = {vru_type: i for i, vru_type in enumerate(vru_types, 1)}
        
        # Convert annotations
        for i, ann in enumerate(annotations, 1):
            bbox = ann.bounding_box
            # COCO format: [x, y, width, height]
            coco_bbox = [bbox["x"], bbox["y"], bbox["width"], bbox["height"]]
            area = bbox["width"] * bbox["height"]
            
            coco_annotation = {
                "id": i,
                "image_id": 1,
                "category_id": category_map[ann.vru_type],
                "segmentation": [],  # Not used for bounding boxes
                "area": area,
                "bbox": coco_bbox,
                "iscrowd": 0,
                "attributes": {
                    "occluded": ann.occluded,
                    "truncated": ann.truncated,
                    "difficult": ann.difficult,
                    "frame_number": ann.frame_number,
                    "timestamp": ann.timestamp,
                    "detection_id": ann.detection_id,
                    "validated": ann.validated
                }
            }
            coco_data["annotations"].append(coco_annotation)
        
        return {
            "content_type": "application/json",
            "filename": f"{video.filename}_coco_annotations.json",
            "data": json.dumps(coco_data, indent=2)
        }
    
    def _export_yolo(self, video: Video, annotations: List[Annotation], 
                     project: Optional[Project], options: Dict[str, Any]) -> Dict[str, Any]:
        """Export annotations in YOLO format"""
        
        # Get image dimensions
        if video.resolution:
            img_width, img_height = map(int, video.resolution.split("x"))
        else:
            img_width, img_height = 1920, 1080
        
        # Create class mapping
        vru_types = list(set(ann.vru_type for ann in annotations))
        class_map = {vru_type: i for i, vru_type in enumerate(vru_types)}
        
        # Generate YOLO format annotations
        yolo_lines = []
        for ann in annotations:
            bbox = ann.bounding_box
            
            # Convert to YOLO format (normalized center x, center y, width, height)
            center_x = (bbox["x"] + bbox["width"] / 2) / img_width
            center_y = (bbox["y"] + bbox["height"] / 2) / img_height
            norm_width = bbox["width"] / img_width
            norm_height = bbox["height"] / img_height
            
            class_id = class_map[ann.vru_type]
            
            yolo_line = f"{class_id} {center_x:.6f} {center_y:.6f} {norm_width:.6f} {norm_height:.6f}"
            yolo_lines.append(yolo_line)
        
        # Create classes file
        classes_content = "\n".join(vru_types)
        
        # Create archive with both files
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add annotation file
            zip_file.writestr(f"{Path(video.filename).stem}.txt", "\n".join(yolo_lines))
            # Add classes file
            zip_file.writestr("classes.txt", classes_content)
            # Add metadata
            metadata = {
                "format": "YOLO",
                "image_width": img_width,
                "image_height": img_height,
                "classes": class_map,
                "annotation_count": len(annotations)
            }
            zip_file.writestr("metadata.json", json.dumps(metadata, indent=2))
        
        zip_buffer.seek(0)
        
        return {
            "content_type": "application/zip",
            "filename": f"{video.filename}_yolo_annotations.zip",
            "data": zip_buffer.getvalue()
        }
    
    def _export_csv(self, video: Video, annotations: List[Annotation], 
                    project: Optional[Project], options: Dict[str, Any]) -> Dict[str, Any]:
        """Export annotations as CSV format"""
        
        csv_buffer = io.StringIO()
        fieldnames = [
            "id", "detection_id", "frame_number", "timestamp", "end_timestamp",
            "vru_type", "bbox_x", "bbox_y", "bbox_width", "bbox_height",
            "occluded", "truncated", "difficult", "notes", "annotator",
            "validated", "created_at", "updated_at"
        ]
        
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()
        
        for ann in annotations:
            bbox = ann.bounding_box
            writer.writerow({
                "id": ann.id,
                "detection_id": ann.detection_id,
                "frame_number": ann.frame_number,
                "timestamp": ann.timestamp,
                "end_timestamp": ann.end_timestamp,
                "vru_type": ann.vru_type,
                "bbox_x": bbox["x"],
                "bbox_y": bbox["y"],
                "bbox_width": bbox["width"],
                "bbox_height": bbox["height"],
                "occluded": ann.occluded,
                "truncated": ann.truncated,
                "difficult": ann.difficult,
                "notes": ann.notes,
                "annotator": ann.annotator,
                "validated": ann.validated,
                "created_at": ann.created_at.isoformat() if ann.created_at else "",
                "updated_at": ann.updated_at.isoformat() if ann.updated_at else ""
            })
        
        return {
            "content_type": "text/csv",
            "filename": f"{video.filename}_annotations.csv",
            "data": csv_buffer.getvalue()
        }
    
    def _export_pascal_voc(self, video: Video, annotations: List[Annotation], 
                          project: Optional[Project], options: Dict[str, Any]) -> Dict[str, Any]:
        """Export annotations in Pascal VOC XML format"""
        
        # Get image dimensions
        if video.resolution:
            img_width, img_height = map(int, video.resolution.split("x"))
        else:
            img_width, img_height = 1920, 1080
        
        # Create XML structure
        root = ET.Element("annotation")
        
        # Folder
        ET.SubElement(root, "folder").text = "videos"
        
        # Filename
        ET.SubElement(root, "filename").text = video.filename
        
        # Path
        ET.SubElement(root, "path").text = video.file_path or f"/uploads/{video.filename}"
        
        # Source
        source = ET.SubElement(root, "source")
        ET.SubElement(source, "database").text = "AI Model Validation Platform"
        
        # Size
        size = ET.SubElement(root, "size")
        ET.SubElement(size, "width").text = str(img_width)
        ET.SubElement(size, "height").text = str(img_height)
        ET.SubElement(size, "depth").text = "3"
        
        # Segmented
        ET.SubElement(root, "segmented").text = "0"
        
        # Objects (annotations)
        for ann in annotations:
            bbox = ann.bounding_box
            
            obj = ET.SubElement(root, "object")
            ET.SubElement(obj, "name").text = ann.vru_type
            ET.SubElement(obj, "pose").text = "Unspecified"
            ET.SubElement(obj, "truncated").text = "1" if ann.truncated else "0"
            ET.SubElement(obj, "difficult").text = "1" if ann.difficult else "0"
            
            # Bounding box
            bndbox = ET.SubElement(obj, "bndbox")
            ET.SubElement(bndbox, "xmin").text = str(int(bbox["x"]))
            ET.SubElement(bndbox, "ymin").text = str(int(bbox["y"]))
            ET.SubElement(bndbox, "xmax").text = str(int(bbox["x"] + bbox["width"]))
            ET.SubElement(bndbox, "ymax").text = str(int(bbox["y"] + bbox["height"]))
            
            # Additional attributes
            attributes = ET.SubElement(obj, "attributes")
            ET.SubElement(attributes, "occluded").text = "true" if ann.occluded else "false"
            ET.SubElement(attributes, "frame_number").text = str(ann.frame_number)
            ET.SubElement(attributes, "timestamp").text = str(ann.timestamp)
            ET.SubElement(attributes, "detection_id").text = ann.detection_id or ""
            ET.SubElement(attributes, "validated").text = "true" if ann.validated else "false"
        
        # Convert to string
        xml_string = ET.tostring(root, encoding="unicode", xml_declaration=True)
        
        return {
            "content_type": "application/xml",
            "filename": f"{Path(video.filename).stem}.xml",
            "data": xml_string
        }
    
    def _export_kitti(self, video: Video, annotations: List[Annotation], 
                      project: Optional[Project], options: Dict[str, Any]) -> Dict[str, Any]:
        """Export annotations in KITTI format"""
        
        kitti_lines = []
        for ann in annotations:
            bbox = ann.bounding_box
            
            # KITTI format: type truncated occluded alpha bbox_left bbox_top bbox_right bbox_bottom dimensions location rotation_y score
            # Simplified version for 2D bounding boxes
            kitti_line = (
                f"{ann.vru_type} "
                f"{1 if ann.truncated else 0} "
                f"{1 if ann.occluded else 0} "
                f"-1 "  # alpha (not used)
                f"{bbox['x']:.2f} {bbox['y']:.2f} "
                f"{bbox['x'] + bbox['width']:.2f} {bbox['y'] + bbox['height']:.2f} "
                f"-1 -1 -1 "  # 3D dimensions (not used)
                f"-1000 -1000 -1000 "  # 3D location (not used)
                f"-10 "  # rotation_y (not used)
                f"1.0"  # confidence score
            )
            kitti_lines.append(kitti_line)
        
        return {
            "content_type": "text/plain",
            "filename": f"{Path(video.filename).stem}.txt",
            "data": "\n".join(kitti_lines)
        }
    
    def _export_labelimg(self, video: Video, annotations: List[Annotation], 
                         project: Optional[Project], options: Dict[str, Any]) -> Dict[str, Any]:
        """Export annotations in LabelImg format (simplified Pascal VOC)"""
        
        # Similar to Pascal VOC but simplified
        return self._export_pascal_voc(video, annotations, project, options)
    
    def bulk_export_project(self, db: Session, project_id: str, 
                           export_format: str,
                           export_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Bulk export all annotations for a project
        
        Args:
            db: Database session
            project_id: Project ID to export annotations for
            export_format: Format to export
            export_options: Additional export options
            
        Returns:
            Dictionary with export result and archive data
        """
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return {
                    "success": False,
                    "error": "Project not found",
                    "code": "PROJECT_NOT_FOUND"
                }
            
            videos = db.query(Video).filter(Video.project_id == project_id).all()
            if not videos:
                return {
                    "success": False,
                    "error": "No videos found in project",
                    "code": "NO_VIDEOS"
                }
            
            # Create ZIP archive with all video exports
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                
                total_annotations = 0
                exported_videos = 0
                
                for video in videos:
                    # Export each video
                    export_result = self.export_annotations(db, video.id, export_format, export_options)
                    
                    if export_result["success"]:
                        export_data = export_result["export_data"]
                        
                        # Add to archive
                        folder_name = f"video_{Path(video.filename).stem}"
                        file_path = f"{folder_name}/{export_data['filename']}"
                        
                        if isinstance(export_data["data"], str):
                            zip_file.writestr(file_path, export_data["data"])
                        else:
                            zip_file.writestr(file_path, export_data["data"])
                        
                        total_annotations += export_result["annotation_count"]
                        exported_videos += 1
                
                # Add project summary
                project_summary = {
                    "project": {
                        "id": project.id,
                        "name": project.name,
                        "description": project.description
                    },
                    "export_summary": {
                        "format": export_format,
                        "exported_videos": exported_videos,
                        "total_videos": len(videos),
                        "total_annotations": total_annotations,
                        "exported_at": datetime.utcnow().isoformat()
                    }
                }
                zip_file.writestr("project_summary.json", json.dumps(project_summary, indent=2))
            
            zip_buffer.seek(0)
            
            logger.info(f"Bulk exported project {project_id}: {exported_videos} videos, {total_annotations} annotations")
            
            return {
                "success": True,
                "project_id": project_id,
                "project_name": project.name,
                "format": export_format,
                "exported_videos": exported_videos,
                "total_videos": len(videos),
                "total_annotations": total_annotations,
                "export_data": {
                    "content_type": "application/zip",
                    "filename": f"{project.name}_{export_format}_annotations.zip",
                    "data": zip_buffer.getvalue()
                }
            }
            
        except Exception as e:
            logger.error(f"Error bulk exporting project {project_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Bulk export error: {str(e)}",
                "code": "BULK_EXPORT_ERROR"
            }
    
    def get_export_summary(self, db: Session, video_id: str) -> Dict[str, Any]:
        """Get export summary for a video"""
        try:
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                return {
                    "success": False,
                    "error": "Video not found",
                    "code": "VIDEO_NOT_FOUND"
                }
            
            annotation_count = db.query(Annotation).filter(Annotation.video_id == video_id).count()
            
            # Get VRU type distribution
            vru_types = db.query(Annotation.vru_type, db.func.count(Annotation.id)).filter(
                Annotation.video_id == video_id
            ).group_by(Annotation.vru_type).all()
            
            return {
                "success": True,
                "video_id": video_id,
                "video_filename": video.filename,
                "annotation_count": annotation_count,
                "vru_type_distribution": {vru_type: count for vru_type, count in vru_types},
                "supported_formats": self.supported_formats,
                "estimated_file_sizes": self._estimate_export_sizes(annotation_count)
            }
            
        except Exception as e:
            logger.error(f"Error getting export summary for video {video_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Summary error: {str(e)}",
                "code": "SUMMARY_ERROR"
            }
    
    def _estimate_export_sizes(self, annotation_count: int) -> Dict[str, str]:
        """Estimate export file sizes for different formats"""
        # Rough estimates based on typical annotation data
        base_size_per_annotation = {
            "json": 500,    # bytes
            "coco": 400,
            "yolo": 50,
            "csv": 300,
            "pascal_voc": 800,
            "kitti": 100,
            "labelimg": 800
        }
        
        estimates = {}
        for format_name, size_per_ann in base_size_per_annotation.items():
            estimated_bytes = annotation_count * size_per_ann
            
            if estimated_bytes < 1024:
                estimates[format_name] = f"{estimated_bytes} bytes"
            elif estimated_bytes < 1024 * 1024:
                estimates[format_name] = f"{estimated_bytes / 1024:.1f} KB"
            else:
                estimates[format_name] = f"{estimated_bytes / (1024 * 1024):.1f} MB"
        
        return estimates