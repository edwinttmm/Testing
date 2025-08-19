import json
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from models import Annotation

class AnnotationExportService:
    """Service for exporting annotations in various formats"""
    
    @staticmethod
    def export_to_json(annotations: List[Annotation], include_metadata: bool = True) -> Dict[str, Any]:
        """Export annotations to JSON format"""
        export_data = {
            "annotations": [],
            "metadata": {
                "export_timestamp": datetime.now().isoformat(),
                "total_annotations": len(annotations),
                "format": "json"
            } if include_metadata else None
        }
        
        for annotation in annotations:
            annotation_data = {
                "id": annotation.id,
                "video_id": annotation.video_id,
                "detection_id": annotation.detection_id,
                "frame_number": annotation.frame_number,
                "timestamp": annotation.timestamp,
                "end_timestamp": annotation.end_timestamp,
                "vru_type": annotation.vru_type,
                "bounding_box": annotation.bounding_box,
                "occluded": annotation.occluded,
                "truncated": annotation.truncated,
                "difficult": annotation.difficult,
                "notes": annotation.notes,
                "annotator": annotation.annotator,
                "validated": annotation.validated,
                "created_at": annotation.created_at.isoformat() if annotation.created_at else None,
                "updated_at": annotation.updated_at.isoformat() if annotation.updated_at else None
            }
            export_data["annotations"].append(annotation_data)
        
        return export_data
    
    @staticmethod
    def export_to_coco(annotations: List[Annotation], video_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Export annotations to COCO format"""
        
        # COCO format structure
        coco_data = {
            "info": {
                "description": "AI Model Validation Platform Annotations",
                "version": "1.0",
                "year": datetime.now().year,
                "date_created": datetime.now().isoformat()
            },
            "licenses": [
                {
                    "id": 1,
                    "name": "Unknown",
                    "url": ""
                }
            ],
            "images": [],
            "annotations": [],
            "categories": []
        }
        
        # Define VRU categories
        categories = [
            {"id": 1, "name": "pedestrian", "supercategory": "vru"},
            {"id": 2, "name": "cyclist", "supercategory": "vru"},
            {"id": 3, "name": "motorcyclist", "supercategory": "vru"},
            {"id": 4, "name": "wheelchair_user", "supercategory": "vru"},
            {"id": 5, "name": "scooter_rider", "supercategory": "vru"}
        ]
        coco_data["categories"] = categories
        
        # Category name to ID mapping
        category_map = {cat["name"]: cat["id"] for cat in categories}
        
        # Group annotations by video
        video_groups = {}
        for annotation in annotations:
            if annotation.video_id not in video_groups:
                video_groups[annotation.video_id] = []
            video_groups[annotation.video_id].append(annotation)
        
        annotation_id = 1
        for video_id, video_annotations in video_groups.items():
            # Add image info (using video frame as image)
            image_info = {
                "id": len(coco_data["images"]) + 1,
                "width": video_info.get("width", 1920) if video_info else 1920,
                "height": video_info.get("height", 1080) if video_info else 1080,
                "file_name": f"video_{video_id}_frame",
                "license": 1,
                "date_captured": datetime.now().isoformat()
            }
            coco_data["images"].append(image_info)
            
            # Add annotations for this video
            for annotation in video_annotations:
                bbox = annotation.bounding_box
                # COCO uses [x, y, width, height] format
                coco_bbox = [
                    bbox.get("x", 0),
                    bbox.get("y", 0),
                    bbox.get("width", 0),
                    bbox.get("height", 0)
                ]
                
                area = bbox.get("width", 0) * bbox.get("height", 0)
                
                coco_annotation = {
                    "id": annotation_id,
                    "image_id": image_info["id"],
                    "category_id": category_map.get(annotation.vru_type, 1),
                    "segmentation": [],  # Not using segmentation
                    "area": area,
                    "bbox": coco_bbox,
                    "iscrowd": 0,
                    "attributes": {
                        "occluded": annotation.occluded,
                        "truncated": annotation.truncated,
                        "difficult": annotation.difficult,
                        "frame_number": annotation.frame_number,
                        "timestamp": annotation.timestamp,
                        "detection_id": annotation.detection_id,
                        "validated": annotation.validated
                    }
                }
                coco_data["annotations"].append(coco_annotation)
                annotation_id += 1
        
        return coco_data
    
    @staticmethod
    def export_to_yolo(annotations: List[Annotation], video_width: int = 1920, video_height: int = 1080) -> Dict[str, str]:
        """Export annotations to YOLO format"""
        
        # YOLO class mapping
        class_map = {
            "pedestrian": 0,
            "cyclist": 1,
            "motorcyclist": 2,
            "wheelchair_user": 3,
            "scooter_rider": 4
        }
        
        # Group annotations by frame
        frame_groups = {}
        for annotation in annotations:
            frame_key = f"{annotation.video_id}_frame_{annotation.frame_number}"
            if frame_key not in frame_groups:
                frame_groups[frame_key] = []
            frame_groups[frame_key].append(annotation)
        
        yolo_files = {}
        
        for frame_key, frame_annotations in frame_groups.items():
            yolo_lines = []
            
            for annotation in frame_annotations:
                bbox = annotation.bounding_box
                
                # Convert to YOLO format (normalized center x, center y, width, height)
                x = bbox.get("x", 0)
                y = bbox.get("y", 0)
                width = bbox.get("width", 0)
                height = bbox.get("height", 0)
                
                # Calculate center coordinates
                center_x = (x + width / 2) / video_width
                center_y = (y + height / 2) / video_height
                norm_width = width / video_width
                norm_height = height / video_height
                
                # Get class ID
                class_id = class_map.get(annotation.vru_type, 0)
                
                yolo_line = f"{class_id} {center_x:.6f} {center_y:.6f} {norm_width:.6f} {norm_height:.6f}"
                yolo_lines.append(yolo_line)
            
            yolo_files[f"{frame_key}.txt"] = "\n".join(yolo_lines)
        
        # Add classes.txt file
        yolo_files["classes.txt"] = "\n".join([
            "pedestrian",
            "cyclist", 
            "motorcyclist",
            "wheelchair_user",
            "scooter_rider"
        ])
        
        return yolo_files
    
    @staticmethod
    def export_to_pascal_voc(annotations: List[Annotation], video_info: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """Export annotations to Pascal VOC XML format"""
        
        # Group annotations by frame
        frame_groups = {}
        for annotation in annotations:
            frame_key = f"{annotation.video_id}_frame_{annotation.frame_number}"
            if frame_key not in frame_groups:
                frame_groups[frame_key] = []
            frame_groups[frame_key].append(annotation)
        
        xml_files = {}
        
        for frame_key, frame_annotations in frame_groups.items():
            # Create XML root
            annotation_elem = ET.Element("annotation")
            
            # Add folder
            folder_elem = ET.SubElement(annotation_elem, "folder")
            folder_elem.text = "annotations"
            
            # Add filename
            filename_elem = ET.SubElement(annotation_elem, "filename")
            filename_elem.text = f"{frame_key}.jpg"
            
            # Add source
            source_elem = ET.SubElement(annotation_elem, "source")
            database_elem = ET.SubElement(source_elem, "database")
            database_elem.text = "AI Model Validation Platform"
            
            # Add size
            size_elem = ET.SubElement(annotation_elem, "size")
            width_elem = ET.SubElement(size_elem, "width")
            width_elem.text = str(video_info.get("width", 1920) if video_info else 1920)
            height_elem = ET.SubElement(size_elem, "height")
            height_elem.text = str(video_info.get("height", 1080) if video_info else 1080)
            depth_elem = ET.SubElement(size_elem, "depth")
            depth_elem.text = "3"
            
            # Add segmented
            segmented_elem = ET.SubElement(annotation_elem, "segmented")
            segmented_elem.text = "0"
            
            # Add objects
            for annotation in frame_annotations:
                object_elem = ET.SubElement(annotation_elem, "object")
                
                # Name
                name_elem = ET.SubElement(object_elem, "name")
                name_elem.text = annotation.vru_type
                
                # Pose
                pose_elem = ET.SubElement(object_elem, "pose")
                pose_elem.text = "Unspecified"
                
                # Truncated
                truncated_elem = ET.SubElement(object_elem, "truncated")
                truncated_elem.text = "1" if annotation.truncated else "0"
                
                # Occluded
                occluded_elem = ET.SubElement(object_elem, "occluded")
                occluded_elem.text = "1" if annotation.occluded else "0"
                
                # Difficult
                difficult_elem = ET.SubElement(object_elem, "difficult")
                difficult_elem.text = "1" if annotation.difficult else "0"
                
                # Bounding box
                bbox = annotation.bounding_box
                bndbox_elem = ET.SubElement(object_elem, "bndbox")
                
                xmin_elem = ET.SubElement(bndbox_elem, "xmin")
                xmin_elem.text = str(int(bbox.get("x", 0)))
                
                ymin_elem = ET.SubElement(bndbox_elem, "ymin")
                ymin_elem.text = str(int(bbox.get("y", 0)))
                
                xmax_elem = ET.SubElement(bndbox_elem, "xmax")
                xmax_elem.text = str(int(bbox.get("x", 0) + bbox.get("width", 0)))
                
                ymax_elem = ET.SubElement(bndbox_elem, "ymax")
                ymax_elem.text = str(int(bbox.get("y", 0) + bbox.get("height", 0)))
                
                # Additional attributes
                attributes_elem = ET.SubElement(object_elem, "attributes")
                
                detection_id_elem = ET.SubElement(attributes_elem, "detection_id")
                detection_id_elem.text = annotation.detection_id or ""
                
                timestamp_elem = ET.SubElement(attributes_elem, "timestamp")
                timestamp_elem.text = str(annotation.timestamp)
                
                validated_elem = ET.SubElement(attributes_elem, "validated")
                validated_elem.text = "true" if annotation.validated else "false"
            
            # Convert to string
            xml_string = ET.tostring(annotation_elem, encoding='unicode')
            xml_files[f"{frame_key}.xml"] = xml_string
        
        return xml_files

class AnnotationImportService:
    """Service for importing annotations from various formats"""
    
    @staticmethod
    def import_from_json(json_data: Dict[str, Any], video_id: str) -> List[Dict[str, Any]]:
        """Import annotations from JSON format"""
        annotations_data = []
        
        annotations = json_data.get("annotations", [])
        for ann_data in annotations:
            annotation = {
                "video_id": video_id,
                "detection_id": ann_data.get("detection_id"),
                "frame_number": ann_data.get("frame_number"),
                "timestamp": ann_data.get("timestamp"),
                "end_timestamp": ann_data.get("end_timestamp"),
                "vru_type": ann_data.get("vru_type"),
                "bounding_box": ann_data.get("bounding_box"),
                "occluded": ann_data.get("occluded", False),
                "truncated": ann_data.get("truncated", False),
                "difficult": ann_data.get("difficult", False),
                "notes": ann_data.get("notes"),
                "annotator": ann_data.get("annotator"),
                "validated": ann_data.get("validated", False)
            }
            annotations_data.append(annotation)
        
        return annotations_data
    
    # TODO: Implement import_from_coco, import_from_yolo, import_from_pascal_voc methods