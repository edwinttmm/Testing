from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Project, Video, TestSession, DetectionEvent
import json

logger = logging.getLogger(__name__)

class ProjectStatus(Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    TESTING = "testing"
    ANALYSIS = "analysis"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class TestVerdict(Enum):
    PASS = "pass"
    CONDITIONAL_PASS = "conditional_pass"
    FAIL = "fail"
    PENDING = "pending"
    ERROR = "error"

@dataclass
class PassFailCriteria:
    min_precision: float = 0.90
    min_recall: float = 0.85
    min_f1_score: float = 0.87
    max_latency_ms: float = 100.0
    max_false_positive_rate: float = 0.05
    min_detection_confidence: float = 0.70
    min_accuracy: float = 0.85
    required_detections: int = 10
    
    def to_dict(self) -> Dict:
        """Convert criteria to dictionary for storage"""
        return {
            "min_precision": self.min_precision,
            "min_recall": self.min_recall,
            "min_f1_score": self.min_f1_score,
            "max_latency_ms": self.max_latency_ms,
            "max_false_positive_rate": self.max_false_positive_rate,
            "min_detection_confidence": self.min_detection_confidence,
            "min_accuracy": self.min_accuracy,
            "required_detections": self.required_detections
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PassFailCriteria':
        """Create criteria from dictionary"""
        return cls(**data)

@dataclass
class TestResults:
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    average_latency_ms: float
    false_positive_rate: float
    average_confidence: float
    total_detections: int
    true_positives: int
    false_positives: int
    false_negatives: int

@dataclass
class Assignment:
    video_id: str
    project_id: str
    compatibility_score: float
    assigned_at: datetime
    assignment_reason: str

class VideoAssignmentSystem:
    """Intelligent video-to-project mapping system"""
    
    COMPATIBILITY_THRESHOLD = 0.7
    
    def __init__(self):
        self.assignment_history = []
    
    def smart_assign_videos(self, project_id: str, available_video_ids: List[str]) -> List[Assignment]:
        """Intelligently assign videos to project based on compatibility"""
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            videos = db.query(Video).filter(Video.id.in_(available_video_ids)).all()
            compatible_assignments = []
            
            for video in videos:
                compatibility_score = self.calculate_compatibility(project, video)
                
                if compatibility_score >= self.COMPATIBILITY_THRESHOLD:
                    assignment = Assignment(
                        video_id=video.id,
                        project_id=project_id,
                        compatibility_score=compatibility_score,
                        assigned_at=datetime.utcnow(),
                        assignment_reason=self._get_assignment_reason(project, video, compatibility_score)
                    )
                    compatible_assignments.append(assignment)
            
            # Sort by compatibility score (highest first)
            compatible_assignments.sort(key=lambda x: x.compatibility_score, reverse=True)
            
            # Limit to project's max videos if specified
            max_videos = getattr(project, 'max_videos', None)
            if max_videos:
                compatible_assignments = compatible_assignments[:max_videos]
            
            return compatible_assignments
            
        finally:
            db.close()
    
    def calculate_compatibility(self, project: Project, video: Video) -> float:
        """Calculate compatibility score between project and video"""
        score = 0.0
        max_score = 0.0
        
        # Camera view compatibility (40% weight)
        max_score += 0.4
        if self._is_camera_view_compatible(project.camera_view, video):
            score += 0.4
        elif self._is_camera_view_partially_compatible(project.camera_view, video):
            score += 0.2
        
        # Resolution compatibility (25% weight)
        max_score += 0.25
        if project.resolution and video.resolution:
            if project.resolution == video.resolution:
                score += 0.25
            elif self._is_resolution_similar(project.resolution, video.resolution):
                score += 0.15
        else:
            score += 0.1  # Partial score if one is missing
        
        # Frame rate compatibility (20% weight)
        max_score += 0.2
        if project.frame_rate and video.fps:
            fps_diff = abs(project.frame_rate - video.fps)
            if fps_diff <= 2:
                score += 0.2
            elif fps_diff <= 5:
                score += 0.1
        else:
            score += 0.05
        
        # Duration suitability (15% weight)
        max_score += 0.15
        if video.duration:
            if 10 <= video.duration <= 300:  # 10 seconds to 5 minutes is ideal
                score += 0.15
            elif 5 <= video.duration <= 600:  # 5 seconds to 10 minutes is acceptable
                score += 0.1
            else:
                score += 0.05
        
        return score / max_score if max_score > 0 else 0.0
    
    def _is_camera_view_compatible(self, project_view: str, video: Video) -> bool:
        """Check if camera view is fully compatible"""
        # This would be enhanced with video metadata analysis
        view_mapping = {
            "Front-facing VRU": ["front", "forward", "pedestrian", "cyclist"],
            "Rear-facing VRU": ["rear", "back", "backup", "parking"],
            "In-Cab Driver Behavior": ["cabin", "interior", "driver", "distraction"]
        }
        
        keywords = view_mapping.get(project_view, [])
        filename_lower = video.filename.lower()
        
        return any(keyword in filename_lower for keyword in keywords)
    
    def _is_camera_view_partially_compatible(self, project_view: str, video: Video) -> bool:
        """Check if camera view is partially compatible"""
        # More lenient matching for partial compatibility
        general_keywords = ["camera", "video", "detection", "test"]
        filename_lower = video.filename.lower()
        
        return any(keyword in filename_lower for keyword in general_keywords)
    
    def _is_resolution_similar(self, res1: str, res2: str) -> bool:
        """Check if resolutions are similar"""
        try:
            w1, h1 = map(int, res1.split('x'))
            w2, h2 = map(int, res2.split('x'))
            
            # Consider similar if within 20% difference
            w_diff = abs(w1 - w2) / max(w1, w2)
            h_diff = abs(h1 - h2) / max(h1, h2)
            
            return w_diff <= 0.2 and h_diff <= 0.2
        except:
            return False
    
    def _get_assignment_reason(self, project: Project, video: Video, score: float) -> str:
        """Get human-readable reason for assignment"""
        reasons = []
        
        if score >= 0.9:
            reasons.append("Excellent compatibility")
        elif score >= 0.8:
            reasons.append("High compatibility")
        elif score >= 0.7:
            reasons.append("Good compatibility")
        
        if project.camera_view and self._is_camera_view_compatible(project.camera_view, video):
            reasons.append(f"Matches {project.camera_view} camera type")
        
        if project.resolution and video.resolution and project.resolution == video.resolution:
            reasons.append(f"Matching resolution ({project.resolution})")
        
        return "; ".join(reasons) if reasons else "Basic compatibility"

class PassFailCriteriaEngine:
    """Engine for configurable pass/fail criteria evaluation"""
    
    def __init__(self):
        self.default_criteria = PassFailCriteria()
    
    def evaluate(self, results: TestResults, criteria: PassFailCriteria = None) -> TestVerdict:
        """Evaluate test results against pass/fail criteria"""
        if criteria is None:
            criteria = self.default_criteria
        
        criteria_checks = []
        failed_criteria = []
        
        # Precision check
        precision_pass = results.precision >= criteria.min_precision
        criteria_checks.append(precision_pass)
        if not precision_pass:
            failed_criteria.append(f"Precision {results.precision:.3f} < {criteria.min_precision}")
        
        # Recall check
        recall_pass = results.recall >= criteria.min_recall
        criteria_checks.append(recall_pass)
        if not recall_pass:
            failed_criteria.append(f"Recall {results.recall:.3f} < {criteria.min_recall}")
        
        # F1 score check
        f1_pass = results.f1_score >= criteria.min_f1_score
        criteria_checks.append(f1_pass)
        if not f1_pass:
            failed_criteria.append(f"F1-score {results.f1_score:.3f} < {criteria.min_f1_score}")
        
        # Latency check
        latency_pass = results.average_latency_ms <= criteria.max_latency_ms
        criteria_checks.append(latency_pass)
        if not latency_pass:
            failed_criteria.append(f"Latency {results.average_latency_ms:.1f}ms > {criteria.max_latency_ms}ms")
        
        # False positive rate check
        fp_rate_pass = results.false_positive_rate <= criteria.max_false_positive_rate
        criteria_checks.append(fp_rate_pass)
        if not fp_rate_pass:
            failed_criteria.append(f"FP rate {results.false_positive_rate:.3f} > {criteria.max_false_positive_rate}")
        
        # Confidence check
        confidence_pass = results.average_confidence >= criteria.min_detection_confidence
        criteria_checks.append(confidence_pass)
        if not confidence_pass:
            failed_criteria.append(f"Confidence {results.average_confidence:.3f} < {criteria.min_detection_confidence}")
        
        # Accuracy check
        accuracy_pass = results.accuracy >= criteria.min_accuracy
        criteria_checks.append(accuracy_pass)
        if not accuracy_pass:
            failed_criteria.append(f"Accuracy {results.accuracy:.3f} < {criteria.min_accuracy}")
        
        # Required detections check
        detections_pass = results.total_detections >= criteria.required_detections
        criteria_checks.append(detections_pass)
        if not detections_pass:
            failed_criteria.append(f"Detections {results.total_detections} < {criteria.required_detections}")
        
        # Determine verdict
        passed_criteria = sum(criteria_checks)
        total_criteria = len(criteria_checks)
        pass_rate = passed_criteria / total_criteria
        
        if pass_rate == 1.0:
            return TestVerdict.PASS
        elif pass_rate >= 0.8:  # 80% or more criteria passed
            return TestVerdict.CONDITIONAL_PASS
        else:
            return TestVerdict.FAIL
    
    def get_detailed_evaluation(self, results: TestResults, criteria: PassFailCriteria = None) -> Dict:
        """Get detailed evaluation with reasons"""
        if criteria is None:
            criteria = self.default_criteria
        
        verdict = self.evaluate(results, criteria)
        
        evaluation_details = {
            "verdict": verdict.value,
            "overall_score": self._calculate_overall_score(results, criteria),
            "criteria_evaluation": {
                "precision": {
                    "value": results.precision,
                    "threshold": criteria.min_precision,
                    "passed": results.precision >= criteria.min_precision
                },
                "recall": {
                    "value": results.recall,
                    "threshold": criteria.min_recall,
                    "passed": results.recall >= criteria.min_recall
                },
                "f1_score": {
                    "value": results.f1_score,
                    "threshold": criteria.min_f1_score,
                    "passed": results.f1_score >= criteria.min_f1_score
                },
                "latency": {
                    "value": results.average_latency_ms,
                    "threshold": criteria.max_latency_ms,
                    "passed": results.average_latency_ms <= criteria.max_latency_ms
                },
                "false_positive_rate": {
                    "value": results.false_positive_rate,
                    "threshold": criteria.max_false_positive_rate,
                    "passed": results.false_positive_rate <= criteria.max_false_positive_rate
                },
                "confidence": {
                    "value": results.average_confidence,
                    "threshold": criteria.min_detection_confidence,
                    "passed": results.average_confidence >= criteria.min_detection_confidence
                },
                "accuracy": {
                    "value": results.accuracy,
                    "threshold": criteria.min_accuracy,
                    "passed": results.accuracy >= criteria.min_accuracy
                },
                "detection_count": {
                    "value": results.total_detections,
                    "threshold": criteria.required_detections,
                    "passed": results.total_detections >= criteria.required_detections
                }
            }
        }
        
        return evaluation_details
    
    def _calculate_overall_score(self, results: TestResults, criteria: PassFailCriteria) -> float:
        """Calculate overall performance score (0-100)"""
        scores = []
        
        # Precision score
        scores.append(min(results.precision / criteria.min_precision * 100, 100))
        
        # Recall score
        scores.append(min(results.recall / criteria.min_recall * 100, 100))
        
        # F1 score
        scores.append(min(results.f1_score / criteria.min_f1_score * 100, 100))
        
        # Latency score (inverted - lower is better)
        latency_score = max(0, 100 - (results.average_latency_ms / criteria.max_latency_ms * 100))
        scores.append(latency_score)
        
        # False positive rate score (inverted - lower is better)
        fp_score = max(0, 100 - (results.false_positive_rate / criteria.max_false_positive_rate * 100))
        scores.append(fp_score)
        
        # Confidence score
        scores.append(min(results.average_confidence / criteria.min_detection_confidence * 100, 100))
        
        # Accuracy score
        scores.append(min(results.accuracy / criteria.min_accuracy * 100, 100))
        
        return sum(scores) / len(scores)

class ProjectManager:
    """Main project lifecycle management system"""
    
    def __init__(self):
        self.assignment_system = VideoAssignmentSystem()
        self.criteria_engine = PassFailCriteriaEngine()
    
    def create_project_with_criteria(self, project_data: Dict, criteria: PassFailCriteria = None) -> str:
        """Create project with custom pass/fail criteria"""
        db = SessionLocal()
        try:
            if criteria is None:
                criteria = self.criteria_engine.default_criteria
            
            project = Project(
                id=str(uuid.uuid4()),
                name=project_data["name"],
                description=project_data.get("description", ""),
                camera_model=project_data["camera_model"],
                camera_view=project_data["camera_view"],
                lens_type=project_data.get("lens_type"),
                resolution=project_data.get("resolution"),
                frame_rate=project_data.get("frame_rate"),
                signal_type=project_data["signal_type"],
                status=ProjectStatus.DRAFT.value,
                owner_id=project_data.get("owner_id", "anonymous")
            )
            
            # Store criteria as JSON in project metadata (would need to add field to model)
            # For now, we'll store it separately or extend the model
            
            db.add(project)
            db.commit()
            db.refresh(project)
            
            logger.info(f"Created project {project.id} with custom criteria")
            return project.id
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating project: {str(e)}")
            raise
        finally:
            db.close()
    
    def assign_videos_to_project(self, project_id: str, video_ids: Optional[List[str]] = None) -> List[Assignment]:
        """Assign videos to project using intelligent assignment"""
        db = SessionLocal()
        try:
            if video_ids is None:
                # Get all available videos
                videos = db.query(Video).filter(Video.project_id.is_(None)).all()
                video_ids = [v.id for v in videos]
            
            assignments = self.assignment_system.smart_assign_videos(project_id, video_ids)
            
            # Execute assignments
            for assignment in assignments:
                video = db.query(Video).filter(Video.id == assignment.video_id).first()
                if video:
                    video.project_id = project_id
                    db.add(video)
            
            db.commit()
            
            logger.info(f"Assigned {len(assignments)} videos to project {project_id}")
            return assignments
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error assigning videos: {str(e)}")
            raise
        finally:
            db.close()
    
    def update_project_status(self, project_id: str, new_status: ProjectStatus, user_id: str = "anonymous") -> bool:
        """Update project status with validation"""
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return False
            
            # Validate status transition
            if self._is_valid_status_transition(ProjectStatus(project.status), new_status):
                project.status = new_status.value
                project.updated_at = datetime.utcnow()
                db.commit()
                
                logger.info(f"Updated project {project_id} status: {project.status} -> {new_status.value}")
                return True
            else:
                logger.warning(f"Invalid status transition for project {project_id}: {project.status} -> {new_status.value}")
                return False
                
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating project status: {str(e)}")
            return False
        finally:
            db.close()
    
    def _is_valid_status_transition(self, current: ProjectStatus, new: ProjectStatus) -> bool:
        """Validate if status transition is allowed"""
        valid_transitions = {
            ProjectStatus.DRAFT: [ProjectStatus.ACTIVE, ProjectStatus.ARCHIVED],
            ProjectStatus.ACTIVE: [ProjectStatus.TESTING, ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED],
            ProjectStatus.TESTING: [ProjectStatus.ANALYSIS, ProjectStatus.ACTIVE],
            ProjectStatus.ANALYSIS: [ProjectStatus.COMPLETED, ProjectStatus.TESTING],
            ProjectStatus.COMPLETED: [ProjectStatus.ARCHIVED],
            ProjectStatus.ARCHIVED: []  # No transitions from archived
        }
        
        return new in valid_transitions.get(current, [])
    
    def get_project_progress(self, project_id: str) -> Dict:
        """Get comprehensive project progress information"""
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return None
            
            # Get associated videos
            videos = db.query(Video).filter(Video.project_id == project_id).all()
            
            # Get test sessions
            test_sessions = db.query(TestSession).filter(TestSession.project_id == project_id).all()
            
            # Calculate progress metrics
            total_videos = len(videos)
            processed_videos = len([v for v in videos if v.ground_truth_generated])
            
            total_tests = len(test_sessions)
            completed_tests = len([t for t in test_sessions if t.status == "completed"])
            
            progress = {
                "project_id": project_id,
                "project_name": project.name,
                "status": project.status,
                "created_at": project.created_at,
                "updated_at": project.updated_at,
                "videos": {
                    "total": total_videos,
                    "processed": processed_videos,
                    "progress_percent": (processed_videos / total_videos * 100) if total_videos > 0 else 0
                },
                "test_sessions": {
                    "total": total_tests,
                    "completed": completed_tests,
                    "progress_percent": (completed_tests / total_tests * 100) if total_tests > 0 else 0
                },
                "overall_progress": self._calculate_overall_progress(processed_videos, total_videos, completed_tests, total_tests)
            }
            
            return progress
            
        except Exception as e:
            logger.error(f"Error getting project progress: {str(e)}")
            return None
        finally:
            db.close()
    
    def _calculate_overall_progress(self, processed_videos: int, total_videos: int, 
                                  completed_tests: int, total_tests: int) -> float:
        """Calculate overall project progress percentage"""
        if total_videos == 0 and total_tests == 0:
            return 0.0
        
        video_weight = 0.4
        test_weight = 0.6
        
        video_progress = (processed_videos / total_videos) if total_videos > 0 else 0
        test_progress = (completed_tests / total_tests) if total_tests > 0 else 0
        
        overall_progress = (video_progress * video_weight + test_progress * test_weight) * 100
        
        return round(overall_progress, 1)

class ResourceAllocationManager:
    """Manage resource allocation for project execution"""
    
    def __init__(self):
        self.resource_limits = {
            "max_concurrent_projects": 5,
            "max_videos_per_project": 100,
            "max_test_sessions_per_project": 50
        }
    
    def check_resource_availability(self, project_id: str, requested_resources: Dict) -> Dict:
        """Check if requested resources are available"""
        db = SessionLocal()
        try:
            # Check current resource usage
            active_projects = db.query(Project).filter(
                Project.status.in_([ProjectStatus.ACTIVE.value, ProjectStatus.TESTING.value])
            ).count()
            
            project_videos = db.query(Video).filter(Video.project_id == project_id).count()
            project_tests = db.query(TestSession).filter(TestSession.project_id == project_id).count()
            
            availability = {
                "can_start_project": active_projects < self.resource_limits["max_concurrent_projects"],
                "can_add_videos": project_videos < self.resource_limits["max_videos_per_project"],
                "can_add_tests": project_tests < self.resource_limits["max_test_sessions_per_project"],
                "current_usage": {
                    "active_projects": active_projects,
                    "project_videos": project_videos,
                    "project_tests": project_tests
                },
                "limits": self.resource_limits
            }
            
            return availability
            
        except Exception as e:
            logger.error(f"Error checking resource availability: {str(e)}")
            return {"error": str(e)}
        finally:
            db.close()
    
    def allocate_resources(self, project_id: str, resource_type: str, amount: int) -> bool:
        """Allocate resources for project"""
        availability = self.check_resource_availability(project_id, {resource_type: amount})
        
        if availability.get(f"can_add_{resource_type}", False):
            logger.info(f"Allocated {amount} {resource_type} resources to project {project_id}")
            return True
        else:
            logger.warning(f"Cannot allocate {amount} {resource_type} resources to project {project_id}")
            return False