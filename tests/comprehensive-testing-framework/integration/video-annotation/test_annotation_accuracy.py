"""
Video Annotation Accuracy Testing Suite
Comprehensive testing for annotation accuracy, detection validation, and ground truth comparison
"""
import pytest
import numpy as np
import cv2
from typing import List, Dict, Any, Tuple, Optional
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json
import tempfile
import os

from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

# Import test configuration
import sys
sys.path.append('/home/user/Testing/tests/comprehensive-testing-framework/config')
from test_config import test_config, TEST_DATA_PATTERNS

# Import application models and services
sys.path.append('/home/user/Testing/ai-model-validation-platform/backend')
from models import Project, Video, GroundTruthObject, Annotation, AnnotationSession
from services.enhanced_detection_service import EnhancedDetectionService
from services.ground_truth_service import GroundTruthService
from database import SessionLocal
from main import app


class TestVideoAnnotationAccuracy:
    """Test suite for video annotation accuracy validation"""
    
    @pytest.fixture(autouse=True)
    def setup_test_environment(self, test_db_session: Session):
        """Set up test environment for each test"""
        self.db = test_db_session
        self.client = TestClient(app)
        self.detection_service = EnhancedDetectionService()
        self.ground_truth_service = GroundTruthService(db=test_db_session)
        
        # Create test project
        self.test_project = Project(
            name="Annotation Accuracy Test Project",
            description="Test project for annotation accuracy validation",
            camera_model="Test Camera",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        self.db.add(self.test_project)
        self.db.commit()
        
        # Create test video
        self.test_video = Video(
            filename="annotation_test_video.mp4",
            file_path="/test/path/annotation_test_video.mp4",
            file_size=20971520,  # 20MB
            duration=60.0,
            fps=30.0,
            resolution="1920x1080",
            project_id=self.test_project.id
        )
        self.db.add(self.test_video)
        self.db.commit()
        
        # Create annotation session
        self.annotation_session = AnnotationSession(
            name="Test Annotation Session",
            project_id=self.test_project.id,
            video_id=self.test_video.id,
            annotator_name="Test Annotator"
        )
        self.db.add(self.annotation_session)
        self.db.commit()
    
    def test_object_detection_accuracy_precision_recall(self):
        """Test object detection accuracy using precision and recall metrics"""
        # Ground truth annotations (known correct detections)
        ground_truth_objects = [
            {
                "frame_number": 100,
                "timestamp": 3.33,
                "class_label": "person",
                "bbox": {"x": 100, "y": 200, "width": 80, "height": 180},
                "confidence": 1.0,  # Ground truth has perfect confidence
                "validated": True
            },
            {
                "frame_number": 100,
                "timestamp": 3.33,
                "class_label": "vehicle",
                "bbox": {"x": 300, "y": 150, "width": 200, "height": 100},
                "confidence": 1.0,
                "validated": True
            },
            {
                "frame_number": 150,
                "timestamp": 5.0,
                "class_label": "bicycle",
                "bbox": {"x": 500, "y": 250, "width": 60, "height": 120},
                "confidence": 1.0,
                "validated": True
            }
        ]
        
        # AI model predictions (to be validated against ground truth)
        ai_predictions = [
            {
                "frame_number": 100,
                "timestamp": 3.33,
                "class_label": "person",
                "bbox": {"x": 105, "y": 205, "width": 75, "height": 175},
                "confidence": 0.92
            },
            {
                "frame_number": 100,
                "timestamp": 3.33,
                "class_label": "vehicle",
                "bbox": {"x": 295, "y": 155, "width": 205, "height": 95},
                "confidence": 0.88
            },
            {
                "frame_number": 100,
                "timestamp": 3.33,
                "class_label": "person",  # False positive
                "bbox": {"x": 600, "y": 300, "width": 70, "height": 160},
                "confidence": 0.65
            },
            {
                "frame_number": 150,
                "timestamp": 5.0,
                "class_label": "bicycle",
                "bbox": {"x": 502, "y": 248, "width": 58, "height": 118},
                "confidence": 0.78
            }
            # Note: Missing the bicycle detection (false negative)
        ]
        
        # Calculate accuracy metrics
        accuracy_metrics = self._calculate_detection_accuracy(
            ground_truth_objects, ai_predictions, iou_threshold=0.5
        )
        
        # Validate precision and recall
        assert "precision" in accuracy_metrics
        assert "recall" in accuracy_metrics
        assert "f1_score" in accuracy_metrics
        assert "iou_scores" in accuracy_metrics
        
        # Expected results:
        # True Positives: person, vehicle, bicycle (3)
        # False Positives: extra person detection (1)
        # False Negatives: none if bicycle is detected correctly (0)
        
        expected_precision = 3 / 4  # 3 TP / (3 TP + 1 FP) = 0.75
        expected_recall = 3 / 3     # 3 TP / (3 TP + 0 FN) = 1.0
        
        assert abs(accuracy_metrics["precision"] - expected_precision) < 0.05
        assert abs(accuracy_metrics["recall"] - expected_recall) < 0.05
        assert accuracy_metrics["f1_score"] > 0.8  # Should be high with good precision/recall
    
    def test_bounding_box_accuracy_iou(self):
        """Test bounding box accuracy using Intersection over Union (IoU)"""
        test_cases = [
            # Case 1: Perfect overlap
            {
                "ground_truth": {"x": 100, "y": 100, "width": 100, "height": 100},
                "prediction": {"x": 100, "y": 100, "width": 100, "height": 100},
                "expected_iou": 1.0
            },
            # Case 2: Good overlap
            {
                "ground_truth": {"x": 100, "y": 100, "width": 100, "height": 100},
                "prediction": {"x": 110, "y": 110, "width": 100, "height": 100},
                "expected_iou": 0.64  # Approximate
            },
            # Case 3: Poor overlap
            {
                "ground_truth": {"x": 100, "y": 100, "width": 100, "height": 100},
                "prediction": {"x": 150, "y": 150, "width": 100, "height": 100},
                "expected_iou": 0.14  # Approximate
            },
            # Case 4: No overlap
            {
                "ground_truth": {"x": 100, "y": 100, "width": 100, "height": 100},
                "prediction": {"x": 300, "y": 300, "width": 100, "height": 100},
                "expected_iou": 0.0
            }
        ]
        
        for i, case in enumerate(test_cases):
            calculated_iou = self._calculate_iou(
                case["ground_truth"], 
                case["prediction"]
            )
            
            assert abs(calculated_iou - case["expected_iou"]) < 0.05, \
                f"IoU calculation failed for case {i}: expected {case['expected_iou']}, got {calculated_iou}"
    
    def test_temporal_annotation_consistency(self):
        """Test temporal consistency of annotations across frames"""
        # Create annotations across multiple frames for tracking consistency
        temporal_annotations = [
            # Object 1: Moving person
            {"frame": 100, "timestamp": 3.33, "object_id": "person_1", "bbox": {"x": 100, "y": 200, "width": 80, "height": 180}},
            {"frame": 101, "timestamp": 3.36, "object_id": "person_1", "bbox": {"x": 105, "y": 200, "width": 80, "height": 180}},
            {"frame": 102, "timestamp": 3.40, "object_id": "person_1", "bbox": {"x": 110, "y": 200, "width": 80, "height": 180}},
            {"frame": 103, "timestamp": 3.43, "object_id": "person_1", "bbox": {"x": 115, "y": 200, "width": 80, "height": 180}},
            
            # Object 2: Stationary vehicle
            {"frame": 100, "timestamp": 3.33, "object_id": "vehicle_1", "bbox": {"x": 300, "y": 150, "width": 200, "height": 100}},
            {"frame": 101, "timestamp": 3.36, "object_id": "vehicle_1", "bbox": {"x": 300, "y": 150, "width": 200, "height": 100}},
            {"frame": 102, "timestamp": 3.40, "object_id": "vehicle_1", "bbox": {"x": 301, "y": 150, "width": 200, "height": 100}},
            {"frame": 103, "timestamp": 3.43, "object_id": "vehicle_1", "bbox": {"x": 300, "y": 151, "width": 200, "height": 100}},
        ]
        
        # Analyze temporal consistency
        consistency_metrics = self._analyze_temporal_consistency(temporal_annotations)
        
        # Validate consistency metrics
        assert "movement_smoothness" in consistency_metrics
        assert "size_consistency" in consistency_metrics
        assert "tracking_accuracy" in consistency_metrics
        
        # Person should show smooth movement
        person_metrics = consistency_metrics["objects"]["person_1"]
        assert person_metrics["movement_smoothness"] > 0.8  # Smooth movement
        assert person_metrics["size_consistency"] > 0.95    # Consistent size
        
        # Vehicle should be nearly stationary
        vehicle_metrics = consistency_metrics["objects"]["vehicle_1"]
        assert vehicle_metrics["movement_smoothness"] > 0.9  # Very smooth (minimal movement)
        assert vehicle_metrics["size_consistency"] > 0.98   # Very consistent size
    
    def test_class_label_accuracy(self):
        """Test accuracy of class label predictions"""
        # Test scenarios with various confidence levels
        classification_test_cases = [
            {
                "image_features": "person_walking_features",
                "ground_truth_label": "person",
                "predicted_labels": [
                    {"label": "person", "confidence": 0.95},
                    {"label": "bicycle", "confidence": 0.03},
                    {"label": "vehicle", "confidence": 0.02}
                ]
            },
            {
                "image_features": "car_parked_features",
                "ground_truth_label": "vehicle",
                "predicted_labels": [
                    {"label": "vehicle", "confidence": 0.88},
                    {"label": "truck", "confidence": 0.08},
                    {"label": "person", "confidence": 0.04}
                ]
            },
            {
                "image_features": "bicycle_moving_features",
                "ground_truth_label": "bicycle",
                "predicted_labels": [
                    {"label": "bicycle", "confidence": 0.75},
                    {"label": "person", "confidence": 0.20},
                    {"label": "motorcycle", "confidence": 0.05}
                ]
            },
            {
                "image_features": "ambiguous_object_features",
                "ground_truth_label": "person",
                "predicted_labels": [
                    {"label": "person", "confidence": 0.55},
                    {"label": "bicycle", "confidence": 0.45}  # Challenging case
                ]
            }
        ]
        
        correct_classifications = 0
        total_cases = len(classification_test_cases)
        confidence_threshold = 0.5
        
        for case in classification_test_cases:
            top_prediction = max(case["predicted_labels"], key=lambda x: x["confidence"])
            
            if (top_prediction["label"] == case["ground_truth_label"] and 
                top_prediction["confidence"] >= confidence_threshold):
                correct_classifications += 1
        
        classification_accuracy = correct_classifications / total_cases
        
        # Validate classification performance
        assert classification_accuracy >= 0.75, f"Classification accuracy too low: {classification_accuracy}"
        
        # Test confidence calibration
        high_confidence_cases = [
            case for case in classification_test_cases 
            if max(case["predicted_labels"], key=lambda x: x["confidence"])["confidence"] > 0.8
        ]
        
        # High confidence predictions should be more accurate
        high_conf_correct = sum(
            1 for case in high_confidence_cases
            if max(case["predicted_labels"], key=lambda x: x["confidence"])["label"] == case["ground_truth_label"]
        )
        
        if high_confidence_cases:
            high_conf_accuracy = high_conf_correct / len(high_confidence_cases)
            assert high_conf_accuracy >= 0.9, "High confidence predictions should be more accurate"
    
    def test_annotation_quality_assessment(self):
        """Test automated annotation quality assessment"""
        # Create annotations with various quality indicators
        annotation_samples = [
            {
                "annotator": "expert_1",
                "annotations": [
                    {"bbox": {"x": 100, "y": 100, "width": 80, "height": 180}, "class": "person", "confidence": 0.95},
                    {"bbox": {"x": 300, "y": 150, "width": 200, "height": 100}, "class": "vehicle", "confidence": 0.88}
                ],
                "quality_indicators": {
                    "bbox_precision": 0.95,
                    "labeling_accuracy": 0.98,
                    "consistency_score": 0.92
                }
            },
            {
                "annotator": "novice_1",
                "annotations": [
                    {"bbox": {"x": 95, "y": 105, "width": 90, "height": 170}, "class": "person", "confidence": 0.78},
                    {"bbox": {"x": 290, "y": 140, "width": 220, "height": 120}, "class": "vehicle", "confidence": 0.82}
                ],
                "quality_indicators": {
                    "bbox_precision": 0.78,
                    "labeling_accuracy": 0.85,
                    "consistency_score": 0.71
                }
            },
            {
                "annotator": "ai_model_v1",
                "annotations": [
                    {"bbox": {"x": 102, "y": 98, "width": 76, "height": 185}, "class": "person", "confidence": 0.89},
                    {"bbox": {"x": 305, "y": 155, "width": 195, "height": 95}, "class": "vehicle", "confidence": 0.91}
                ],
                "quality_indicators": {
                    "bbox_precision": 0.88,
                    "labeling_accuracy": 0.94,
                    "consistency_score": 0.89
                }
            }
        ]
        
        # Assess annotation quality
        quality_assessment = self._assess_annotation_quality(annotation_samples)
        
        # Validate quality metrics
        assert "overall_quality_score" in quality_assessment
        assert "annotator_rankings" in quality_assessment
        assert "quality_distribution" in quality_assessment
        
        # Expert should rank highest
        expert_rank = next(
            rank for rank in quality_assessment["annotator_rankings"]
            if rank["annotator"] == "expert_1"
        )["rank"]
        assert expert_rank == 1, "Expert annotator should rank highest"
        
        # Quality scores should be reasonable
        assert 0.7 <= quality_assessment["overall_quality_score"] <= 1.0
    
    def test_ground_truth_validation_workflow(self):
        """Test the complete ground truth validation workflow"""
        # Create ground truth objects in database
        ground_truth_objects = []
        for i in range(5):
            gt_obj = GroundTruthObject(
                video_id=self.test_video.id,
                frame_number=100 + i * 10,
                timestamp=3.33 + i * 0.33,
                class_label="person" if i % 2 == 0 else "vehicle",
                x=100 + i * 50,
                y=200,
                width=80,
                height=180,
                confidence=0.9 + i * 0.02,
                validated=False
            )
            ground_truth_objects.append(gt_obj)
            self.db.add(gt_obj)
        
        self.db.commit()
        
        # Run validation workflow
        validation_results = self.ground_truth_service.validate_ground_truth_batch(
            self.test_video.id,
            validation_criteria={
                "min_confidence": 0.8,
                "min_bbox_area": 1000,
                "max_objects_per_frame": 10,
                "class_consistency_check": True
            }
        )
        
        # Validate workflow results
        assert "validation_summary" in validation_results
        assert "validated_objects" in validation_results
        assert "rejected_objects" in validation_results
        assert "quality_metrics" in validation_results
        
        # Check validation logic
        validated_count = len(validation_results["validated_objects"])
        rejected_count = len(validation_results["rejected_objects"])
        
        assert validated_count + rejected_count == 5
        assert validated_count >= 3, "Most objects should pass validation"
    
    def test_multi_annotator_agreement(self):
        """Test agreement between multiple annotators"""
        # Simulate annotations from multiple annotators for the same frame
        multi_annotator_data = {
            "frame_100": {
                "annotator_1": [
                    {"bbox": {"x": 100, "y": 200, "width": 80, "height": 180}, "class": "person"},
                    {"bbox": {"x": 300, "y": 150, "width": 200, "height": 100}, "class": "vehicle"}
                ],
                "annotator_2": [
                    {"bbox": {"x": 105, "y": 205, "width": 75, "height": 175}, "class": "person"},
                    {"bbox": {"x": 295, "y": 155, "width": 205, "height": 95}, "class": "vehicle"}
                ],
                "annotator_3": [
                    {"bbox": {"x": 98, "y": 198, "width": 85, "height": 185}, "class": "person"},
                    {"bbox": {"x": 305, "y": 148, "width": 195, "height": 105}, "class": "vehicle"},
                    {"bbox": {"x": 500, "y": 250, "width": 60, "height": 120}, "class": "bicycle"}  # Only one annotator sees this
                ]
            }
        }
        
        # Calculate inter-annotator agreement
        agreement_metrics = self._calculate_inter_annotator_agreement(multi_annotator_data)
        
        # Validate agreement metrics
        assert "kappa_score" in agreement_metrics
        assert "iou_agreement" in agreement_metrics
        assert "class_agreement" in agreement_metrics
        assert "consensus_annotations" in agreement_metrics
        
        # Agreement should be reasonable for clear objects
        assert agreement_metrics["class_agreement"] >= 0.8
        assert agreement_metrics["iou_agreement"] >= 0.7
        
        # Consensus should identify common objects
        consensus = agreement_metrics["consensus_annotations"]
        assert len(consensus) >= 2  # Person and vehicle should have consensus
    
    def test_annotation_export_import_accuracy(self):
        """Test accuracy of annotation export and import processes"""
        # Create test annotations
        original_annotations = [
            {
                "id": "ann_1",
                "video_id": self.test_video.id,
                "frame_number": 100,
                "timestamp": 3.33,
                "class_label": "person",
                "bbox": {"x": 100, "y": 200, "width": 80, "height": 180},
                "confidence": 0.95,
                "metadata": {"annotator": "test_user", "validation_status": "approved"}
            },
            {
                "id": "ann_2", 
                "video_id": self.test_video.id,
                "frame_number": 150,
                "timestamp": 5.0,
                "class_label": "vehicle",
                "bbox": {"x": 300, "y": 150, "width": 200, "height": 100},
                "confidence": 0.88,
                "metadata": {"annotator": "test_user", "validation_status": "pending"}
            }
        ]
        
        # Export annotations to different formats
        export_formats = ["COCO", "YOLO", "Pascal VOC", "Custom JSON"]
        
        for export_format in export_formats:
            # Export
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
                exported_data = self._export_annotations(original_annotations, export_format)
                json.dump(exported_data, tmp_file)
                export_path = tmp_file.name
            
            # Import back
            imported_annotations = self._import_annotations(export_path, export_format)
            
            # Validate round-trip accuracy
            assert len(imported_annotations) == len(original_annotations)
            
            for orig, imported in zip(original_annotations, imported_annotations):
                # Check core data preservation
                assert orig["class_label"] == imported["class_label"]
                assert abs(orig["timestamp"] - imported["timestamp"]) < 0.01
                assert orig["frame_number"] == imported["frame_number"]
                
                # Check bounding box accuracy
                orig_bbox = orig["bbox"]
                imported_bbox = imported["bbox"]
                for coord in ["x", "y", "width", "height"]:
                    assert abs(orig_bbox[coord] - imported_bbox[coord]) < 1.0
            
            # Cleanup
            os.unlink(export_path)


    # Helper methods for calculation and analysis
    
    def _calculate_detection_accuracy(self, ground_truth: List[Dict], 
                                    predictions: List[Dict], 
                                    iou_threshold: float = 0.5) -> Dict[str, float]:
        """Calculate precision, recall, and F1 score for object detection"""
        true_positives = 0
        false_positives = 0
        false_negatives = 0
        iou_scores = []
        
        # Match predictions to ground truth
        matched_gt = set()
        
        for pred in predictions:
            best_iou = 0
            best_gt_idx = -1
            
            for gt_idx, gt in enumerate(ground_truth):
                if (gt_idx not in matched_gt and 
                    pred["class_label"] == gt["class_label"] and
                    abs(pred["timestamp"] - gt["timestamp"]) < 0.1):
                    
                    iou = self._calculate_iou(pred["bbox"], gt["bbox"])
                    if iou > best_iou:
                        best_iou = iou
                        best_gt_idx = gt_idx
            
            if best_iou >= iou_threshold:
                true_positives += 1
                matched_gt.add(best_gt_idx)
                iou_scores.append(best_iou)
            else:
                false_positives += 1
        
        false_negatives = len(ground_truth) - len(matched_gt)
        
        # Calculate metrics
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "iou_scores": iou_scores,
            "mean_iou": np.mean(iou_scores) if iou_scores else 0
        }
    
    def _calculate_iou(self, bbox1: Dict, bbox2: Dict) -> float:
        """Calculate Intersection over Union for two bounding boxes"""
        # Convert to coordinates
        x1_1, y1_1 = bbox1["x"], bbox1["y"]
        x2_1, y2_1 = x1_1 + bbox1["width"], y1_1 + bbox1["height"]
        
        x1_2, y1_2 = bbox2["x"], bbox2["y"]
        x2_2, y2_2 = x1_2 + bbox2["width"], y1_2 + bbox2["height"]
        
        # Calculate intersection
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)
        
        if x2_i <= x1_i or y2_i <= y1_i:
            return 0.0
        
        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        
        # Calculate union
        area1 = bbox1["width"] * bbox1["height"]
        area2 = bbox2["width"] * bbox2["height"]
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def _analyze_temporal_consistency(self, annotations: List[Dict]) -> Dict[str, Any]:
        """Analyze temporal consistency of object tracking"""
        objects = {}
        
        # Group annotations by object ID
        for ann in annotations:
            obj_id = ann["object_id"]
            if obj_id not in objects:
                objects[obj_id] = []
            objects[obj_id].append(ann)
        
        # Sort by frame number
        for obj_id in objects:
            objects[obj_id].sort(key=lambda x: x["frame"])
        
        consistency_metrics = {"objects": {}}
        
        for obj_id, obj_annotations in objects.items():
            if len(obj_annotations) < 2:
                continue
            
            # Calculate movement smoothness
            movements = []
            sizes = []
            
            for i in range(1, len(obj_annotations)):
                prev_ann = obj_annotations[i-1]
                curr_ann = obj_annotations[i]
                
                # Movement distance
                prev_center = (prev_ann["bbox"]["x"] + prev_ann["bbox"]["width"]/2,
                             prev_ann["bbox"]["y"] + prev_ann["bbox"]["height"]/2)
                curr_center = (curr_ann["bbox"]["x"] + curr_ann["bbox"]["width"]/2,
                             curr_ann["bbox"]["y"] + curr_ann["bbox"]["height"]/2)
                
                movement = np.sqrt((curr_center[0] - prev_center[0])**2 + 
                                 (curr_center[1] - prev_center[1])**2)
                movements.append(movement)
                
                # Size consistency
                prev_area = prev_ann["bbox"]["width"] * prev_ann["bbox"]["height"]
                curr_area = curr_ann["bbox"]["width"] * curr_ann["bbox"]["height"]
                sizes.append(abs(curr_area - prev_area) / prev_area)
            
            # Calculate metrics
            movement_variance = np.var(movements) if movements else 0
            movement_smoothness = 1 / (1 + movement_variance)  # Higher is smoother
            
            size_variance = np.var(sizes) if sizes else 0
            size_consistency = 1 / (1 + size_variance)  # Higher is more consistent
            
            consistency_metrics["objects"][obj_id] = {
                "movement_smoothness": movement_smoothness,
                "size_consistency": size_consistency,
                "tracking_accuracy": (movement_smoothness + size_consistency) / 2
            }
        
        return consistency_metrics
    
    def _assess_annotation_quality(self, annotation_samples: List[Dict]) -> Dict[str, Any]:
        """Assess overall annotation quality from multiple sources"""
        quality_scores = []
        annotator_scores = {}
        
        for sample in annotation_samples:
            annotator = sample["annotator"]
            indicators = sample["quality_indicators"]
            
            # Calculate composite quality score
            quality_score = (
                indicators["bbox_precision"] * 0.4 +
                indicators["labeling_accuracy"] * 0.4 +
                indicators["consistency_score"] * 0.2
            )
            
            quality_scores.append(quality_score)
            annotator_scores[annotator] = quality_score
        
        # Rank annotators
        ranked_annotators = sorted(
            annotator_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return {
            "overall_quality_score": np.mean(quality_scores),
            "annotator_rankings": [
                {"annotator": annotator, "score": score, "rank": i+1}
                for i, (annotator, score) in enumerate(ranked_annotators)
            ],
            "quality_distribution": {
                "mean": np.mean(quality_scores),
                "std": np.std(quality_scores),
                "min": min(quality_scores),
                "max": max(quality_scores)
            }
        }
    
    def _calculate_inter_annotator_agreement(self, multi_annotator_data: Dict) -> Dict[str, Any]:
        """Calculate agreement metrics between multiple annotators"""
        frame_agreements = []
        
        for frame_id, annotators in multi_annotator_data.items():
            annotator_names = list(annotators.keys())
            
            if len(annotator_names) < 2:
                continue
            
            # Compare each pair of annotators
            pairwise_agreements = []
            
            for i in range(len(annotator_names)):
                for j in range(i+1, len(annotator_names)):
                    ann1 = annotators[annotator_names[i]]
                    ann2 = annotators[annotator_names[j]]
                    
                    # Calculate agreement for this pair
                    agreement = self._calculate_pairwise_agreement(ann1, ann2)
                    pairwise_agreements.append(agreement)
            
            frame_agreements.append(np.mean(pairwise_agreements))
        
        # Generate consensus annotations
        consensus_annotations = self._generate_consensus_annotations(multi_annotator_data)
        
        return {
            "kappa_score": np.mean(frame_agreements),
            "iou_agreement": np.mean([fa for fa in frame_agreements]),
            "class_agreement": np.mean([fa for fa in frame_agreements]),
            "consensus_annotations": consensus_annotations
        }
    
    def _calculate_pairwise_agreement(self, ann1: List[Dict], ann2: List[Dict]) -> float:
        """Calculate agreement between two sets of annotations"""
        if not ann1 or not ann2:
            return 0.0
        
        # Find best matches between annotations
        matches = 0
        total_comparisons = max(len(ann1), len(ann2))
        
        used_ann2 = set()
        
        for a1 in ann1:
            best_iou = 0
            best_idx = -1
            
            for idx, a2 in enumerate(ann2):
                if idx in used_ann2:
                    continue
                
                if a1["class"] == a2["class"]:
                    iou = self._calculate_iou(a1["bbox"], a2["bbox"])
                    if iou > best_iou:
                        best_iou = iou
                        best_idx = idx
            
            if best_iou > 0.5:  # Threshold for considering a match
                matches += 1
                used_ann2.add(best_idx)
        
        return matches / total_comparisons if total_comparisons > 0 else 0.0
    
    def _generate_consensus_annotations(self, multi_annotator_data: Dict) -> List[Dict]:
        """Generate consensus annotations from multiple annotators"""
        consensus_annotations = []
        
        for frame_id, annotators in multi_annotator_data.items():
            # Find objects that appear in multiple annotations
            all_objects = []
            for annotator, annotations in annotators.items():
                for ann in annotations:
                    all_objects.append({
                        "annotator": annotator,
                        "annotation": ann
                    })
            
            # Group similar objects
            object_groups = []
            used_objects = set()
            
            for i, obj1 in enumerate(all_objects):
                if i in used_objects:
                    continue
                
                group = [obj1]
                used_objects.add(i)
                
                for j, obj2 in enumerate(all_objects[i+1:], i+1):
                    if j in used_objects:
                        continue
                    
                    if (obj1["annotation"]["class"] == obj2["annotation"]["class"] and
                        self._calculate_iou(obj1["annotation"]["bbox"], obj2["annotation"]["bbox"]) > 0.3):
                        group.append(obj2)
                        used_objects.add(j)
                
                if len(group) >= 2:  # Require at least 2 annotators to agree
                    object_groups.append(group)
            
            # Create consensus for each group
            for group in object_groups:
                consensus_bbox = self._average_bounding_boxes([obj["annotation"]["bbox"] for obj in group])
                consensus_class = group[0]["annotation"]["class"]  # All should be the same
                
                consensus_annotations.append({
                    "frame": frame_id,
                    "class": consensus_class,
                    "bbox": consensus_bbox,
                    "agreement_count": len(group),
                    "confidence": len(group) / len(list(multi_annotator_data[frame_id].keys()))
                })
        
        return consensus_annotations
    
    def _average_bounding_boxes(self, bboxes: List[Dict]) -> Dict:
        """Calculate average bounding box from multiple boxes"""
        if not bboxes:
            return {"x": 0, "y": 0, "width": 0, "height": 0}
        
        avg_x = sum(bbox["x"] for bbox in bboxes) / len(bboxes)
        avg_y = sum(bbox["y"] for bbox in bboxes) / len(bboxes)
        avg_width = sum(bbox["width"] for bbox in bboxes) / len(bboxes)
        avg_height = sum(bbox["height"] for bbox in bboxes) / len(bboxes)
        
        return {
            "x": int(avg_x),
            "y": int(avg_y),
            "width": int(avg_width),
            "height": int(avg_height)
        }
    
    def _export_annotations(self, annotations: List[Dict], export_format: str) -> Dict:
        """Export annotations to specified format"""
        if export_format == "COCO":
            return self._export_to_coco(annotations)
        elif export_format == "YOLO":
            return self._export_to_yolo(annotations)
        elif export_format == "Pascal VOC":
            return self._export_to_pascal_voc(annotations)
        else:  # Custom JSON
            return {"annotations": annotations, "format": "custom"}
    
    def _import_annotations(self, file_path: str, import_format: str) -> List[Dict]:
        """Import annotations from specified format"""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        if import_format == "COCO":
            return self._import_from_coco(data)
        elif import_format == "YOLO":
            return self._import_from_yolo(data)
        elif import_format == "Pascal VOC":
            return self._import_from_pascal_voc(data)
        else:  # Custom JSON
            return data.get("annotations", [])
    
    def _export_to_coco(self, annotations: List[Dict]) -> Dict:
        """Export to COCO format"""
        coco_data = {
            "images": [],
            "annotations": [],
            "categories": []
        }
        
        # Extract unique classes
        classes = list(set(ann["class_label"] for ann in annotations))
        for i, class_name in enumerate(classes):
            coco_data["categories"].append({
                "id": i + 1,
                "name": class_name
            })
        
        # Convert annotations
        for ann in annotations:
            coco_data["annotations"].append({
                "id": ann["id"],
                "image_id": ann["frame_number"],
                "category_id": classes.index(ann["class_label"]) + 1,
                "bbox": [ann["bbox"]["x"], ann["bbox"]["y"], ann["bbox"]["width"], ann["bbox"]["height"]],
                "area": ann["bbox"]["width"] * ann["bbox"]["height"]
            })
        
        return coco_data
    
    def _import_from_coco(self, coco_data: Dict) -> List[Dict]:
        """Import from COCO format"""
        # Create class mapping
        class_map = {cat["id"]: cat["name"] for cat in coco_data["categories"]}
        
        annotations = []
        for ann in coco_data["annotations"]:
            bbox = ann["bbox"]
            annotations.append({
                "id": ann["id"],
                "frame_number": ann["image_id"],
                "class_label": class_map[ann["category_id"]],
                "bbox": {
                    "x": bbox[0],
                    "y": bbox[1], 
                    "width": bbox[2],
                    "height": bbox[3]
                },
                "confidence": 1.0  # COCO doesn't store confidence
            })
        
        return annotations
    
    def _export_to_yolo(self, annotations: List[Dict]) -> Dict:
        """Export to YOLO format"""
        return {"annotations": annotations, "format": "yolo"}  # Simplified
    
    def _import_from_yolo(self, data: Dict) -> List[Dict]:
        """Import from YOLO format"""
        return data.get("annotations", [])  # Simplified
    
    def _export_to_pascal_voc(self, annotations: List[Dict]) -> Dict:
        """Export to Pascal VOC format"""
        return {"annotations": annotations, "format": "pascal_voc"}  # Simplified
    
    def _import_from_pascal_voc(self, data: Dict) -> List[Dict]:
        """Import from Pascal VOC format"""
        return data.get("annotations", [])  # Simplified


@pytest.fixture
def test_db_session():
    """Fixture providing test database session"""
    session = SessionLocal()
    yield session
    session.close()