import os
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
import asyncio
from pathlib import Path
import base64
from io import BytesIO

from models import (
    TestSession, DetectionEvent, GroundTruthObject, Video, Project,
    TestResult, DetectionComparison
)
from schemas import (
    DetectionOutcomeEnum, VideoStatus, VRUType
)
from services.failure_snapshot_service import FailureSnapshotService
from services.test_report_generator import TestReportGenerator
from database import get_db

class ReportGenerationService:
    """
    PRD Module 4.2 - Report Generation Service
    
    Generates comprehensive test reports with:
    - Pass/fail rate summaries
    - Failure snapshots for HIGH_LATENCY and MISSED_DETECTION
    - Success summaries in text format
    - Multiple output formats (PDF, HTML, JSON)
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.snapshot_service = FailureSnapshotService()
        self.report_generator = TestReportGenerator()
        self.reports_dir = Path("reports")
        self.reports_dir.mkdir(exist_ok=True)
        
    async def generate_comprehensive_report(
        self, 
        test_session_id: str,
        include_snapshots: bool = True,
        formats: List[str] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive test report for a test session
        
        Args:
            test_session_id: Test session UUID
            include_snapshots: Whether to include failure snapshots
            formats: Output formats ['pdf', 'html', 'json']
            
        Returns:
            Dict with report data and file paths
        """
        if formats is None:
            formats = ['html', 'json']
            
        # Get test session data
        test_session = self.db.query(TestSession).filter(
            TestSession.id == test_session_id
        ).first()
        
        if not test_session:
            raise ValueError(f"Test session {test_session_id} not found")
        
        # Get all detection events for this session
        # QUALITY FILTER: Only include validated detections in reports
        detection_events = self.db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == test_session_id,
            DetectionEvent.usable_for_validation == True
        ).all()

        # Get quality statistics for the report
        total_detections = self.db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == test_session_id
        ).count()

        validated_count = len(detection_events)
        degraded_count = total_detections - validated_count

        quality_info = {
            'total_detections': total_detections,
            'validated_detections': validated_count,
            'degraded_detections': degraded_count,
            'validation_rate': (validated_count / total_detections * 100) if total_detections > 0 else 0
        }
        
        # Get project and video information
        project = self.db.query(Project).filter(
            Project.id == test_session.project_id
        ).first()
        
        videos = self.db.query(Video).filter(
            Video.project_id == test_session.project_id
        ).all()
        
        # Calculate pass/fail metrics
        metrics = self._calculate_test_metrics(detection_events, test_session)
        
        # Get failure events with details
        failure_events = self._get_failure_events(detection_events)
        
        # Generate failure snapshots if requested
        failure_snapshots = []
        if include_snapshots and failure_events:
            failure_snapshots = await self._generate_failure_snapshots(
                failure_events, videos
            )
        
        # Get success summary
        success_summary = self._generate_success_summary(detection_events, metrics)
        
        # Compile report data
        report_data = {
            "report_id": str(uuid.uuid4()),
            "test_session_id": test_session_id,
            "generated_at": datetime.now().isoformat(),
            "test_session": {
                "id": test_session.id,
                "name": test_session.name,
                "project_name": project.name if project else "Unknown",
                "started_at": test_session.started_at.isoformat() if test_session.started_at else None,
                "completed_at": test_session.completed_at.isoformat() if test_session.completed_at else None,
                "status": test_session.status,
                "latency_threshold_ms": test_session.latency_threshold_ms or 100
            },
            "metrics": metrics,
            "success_summary": success_summary,
            "failure_events": failure_events,
            "failure_snapshots": failure_snapshots,
            "videos_tested": len(videos),
            "total_events": len(detection_events)
        }
        
        # Generate reports in requested formats
        report_files = await self._generate_report_files(
            report_data, formats, test_session_id
        )
        
        # Store report metadata in database
        await self._store_report_metadata(report_data, report_files)
        
        return {
            "report_data": report_data,
            "report_files": report_files,
            "metrics": metrics
        }
    
    def _calculate_test_metrics(self, detection_events: List[DetectionEvent], test_session: TestSession) -> Dict[str, Any]:
        """
        Calculate comprehensive test metrics according to PRD Module 4.1
        
        Returns metrics for:
        - Pass/Fail rates
        - Average latency
        - High latency failures
        - Missed detections
        """
        total_events = len(detection_events)
        if total_events == 0:
            return self._empty_metrics()
        
        threshold_ms = test_session.latency_threshold_ms or 100
        
        # Categorize events by outcome
        passed_events = []
        high_latency_events = []
        missed_detection_events = []
        
        latencies = []
        
        for event in detection_events:
            # Determine event outcome based on PRD Module 4.1 criteria
            if event.actual_latency_ms is not None:
                latencies.append(event.actual_latency_ms)

                if event.actual_latency_ms <= threshold_ms:
                    passed_events.append(event)
                else:
                    high_latency_events.append(event)
            else:
                # No signal received = missed detection
                missed_detection_events.append(event)
        
        # Calculate metrics
        pass_count = len(passed_events)
        fail_count = len(high_latency_events) + len(missed_detection_events)
        
        pass_rate = (pass_count / total_events) * 100 if total_events > 0 else 0
        fail_rate = (fail_count / total_events) * 100 if total_events > 0 else 0
        
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        min_latency = min(latencies) if latencies else 0
        max_latency = max(latencies) if latencies else 0
        
        return {
            "total_events": total_events,
            "passed_events": pass_count,
            "failed_events": fail_count,
            "high_latency_failures": len(high_latency_events),
            "missed_detections": len(missed_detection_events),
            "pass_rate_percent": round(pass_rate, 2),
            "fail_rate_percent": round(fail_rate, 2),
            "average_latency_ms": round(avg_latency, 3),
            "min_latency_ms": round(min_latency, 3),
            "max_latency_ms": round(max_latency, 3),
            "latency_threshold_ms": threshold_ms,
            "latency_distribution": self._calculate_latency_distribution(latencies),
            "test_outcome": "PASS" if pass_rate >= 85 else "FAIL"  # PRD success criteria
        }
    
    def _calculate_latency_distribution(self, latencies: List[float]) -> Dict[str, int]:
        """Calculate latency distribution for histogram visualization"""
        if not latencies:
            return {}
        
        # Create histogram bins
        bins = {
            "0-50ms": 0,
            "51-100ms": 0,
            "101-200ms": 0,
            "201-500ms": 0,
            "500ms+": 0
        }
        
        for latency in latencies:
            if latency <= 50:
                bins["0-50ms"] += 1
            elif latency <= 100:
                bins["51-100ms"] += 1
            elif latency <= 200:
                bins["101-200ms"] += 1
            elif latency <= 500:
                bins["201-500ms"] += 1
            else:
                bins["500ms+"] += 1
        
        return bins
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure"""
        return {
            "total_events": 0,
            "passed_events": 0,
            "failed_events": 0,
            "high_latency_failures": 0,
            "missed_detections": 0,
            "pass_rate_percent": 0,
            "fail_rate_percent": 0,
            "average_latency_ms": 0,
            "min_latency_ms": 0,
            "max_latency_ms": 0,
            "latency_threshold_ms": 100,
            "latency_distribution": {},
            "test_outcome": "NO_DATA"
        }
    
    def _get_failure_events(self, detection_events: List[DetectionEvent]) -> List[Dict[str, Any]]:
        """
        Extract failure events with detailed information for snapshot generation
        
        PRD Requirement: Every failure (High Latency + Missed Detection) needs snapshot
        """
        failure_events = []
        
        for event in detection_events:
            failure_type = None

            # Determine failure type based on PRD Module 4.1
            if event.actual_latency_ms is None:
                failure_type = "MISSED_DETECTION"
            elif event.actual_latency_ms > (event.latency_threshold_ms or 100):
                failure_type = "HIGH_LATENCY"

            if failure_type:
                failure_events.append({
                    "event_id": event.id,
                    "video_id": event.video_id,
                    "timestamp": event.timestamp,
                    "failure_type": failure_type,
                    "latency_ms": event.actual_latency_ms,
                    "threshold_ms": event.latency_threshold_ms or 100,
                    "labjack_timestamp": event.labjack_timestamp,
                    "frame_number": event.frame_number,
                    "vru_type": event.vru_type,
                    "detection_channel": event.detection_channel,
                    "voltage_level": event.voltage_level,
                    "created_at": event.created_at.isoformat()
                })
        
        return failure_events
    
    async def _generate_failure_snapshots(
        self, 
        failure_events: List[Dict[str, Any]], 
        videos: List[Video]
    ) -> List[Dict[str, Any]]:
        """
        Generate video snapshots for each failure event at the exact timestamp
        
        PRD Requirement: Video snapshot for EVERY failure, timestamped to moment event occurred
        """
        snapshots = []
        video_lookup = {video.id: video for video in videos}
        
        for failure_event in failure_events:
            video_id = failure_event["video_id"]
            timestamp = failure_event["timestamp"]
            
            if video_id and video_id in video_lookup:
                video = video_lookup[video_id]
                
                try:
                    # Generate snapshot at failure timestamp
                    snapshot_data = await self.snapshot_service.capture_failure_snapshot(
                        video_path=video.file_path,
                        timestamp_ms=timestamp * 1000,  # Convert to milliseconds
                        failure_type=failure_event["failure_type"],
                        event_id=failure_event["event_id"]
                    )
                    
                    if snapshot_data:
                        snapshots.append({
                            "event_id": failure_event["event_id"],
                            "video_id": video_id,
                            "video_filename": video.filename,
                            "timestamp_ms": timestamp * 1000,
                            "failure_type": failure_event["failure_type"],
                            "snapshot_path": snapshot_data["snapshot_path"],
                            "snapshot_base64": snapshot_data.get("base64_data"),
                            "frame_number": snapshot_data.get("frame_number"),
                            "generated_at": datetime.now().isoformat()
                        })
                
                except Exception as e:
                    print(f"Failed to generate snapshot for event {failure_event['event_id']}: {str(e)}")
                    # Add placeholder for failed snapshot
                    snapshots.append({
                        "event_id": failure_event["event_id"],
                        "video_id": video_id,
                        "error": f"Snapshot generation failed: {str(e)}",
                        "failure_type": failure_event["failure_type"]
                    })
        
        return snapshots
    
    def _generate_success_summary(self, detection_events: List[DetectionEvent], metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate text summary for successful passes
        
        PRD Requirement: Summarize successful passes in text format (no visual review needed)
        """
        passed_events = [event for event in detection_events
                        if event.actual_latency_ms is not None and
                        event.actual_latency_ms <= (event.latency_threshold_ms or 100)]

        if not passed_events:
            return {
                "summary_text": "No successful detections recorded.",
                "passed_count": 0,
                "total_count": len(detection_events)
            }

        # Analyze successful detections
        latencies = [event.actual_latency_ms for event in passed_events if event.actual_latency_ms is not None]
        avg_success_latency = sum(latencies) / len(latencies) if latencies else 0
        
        # Group by VRU type
        vru_success_counts = {}
        for event in passed_events:
            vru_type = event.vru_type or "Unknown"
            vru_success_counts[vru_type] = vru_success_counts.get(vru_type, 0) + 1
        
        summary_text = f"{len(passed_events)}/{len(detection_events)} detections passed with average latency of {avg_success_latency:.1f}ms."
        
        if vru_success_counts:
            vru_breakdown = ", ".join([f"{count} {vru_type}" for vru_type, count in vru_success_counts.items()])
            summary_text += f" Successful detections: {vru_breakdown}."
        
        return {
            "summary_text": summary_text,
            "passed_count": len(passed_events),
            "total_count": len(detection_events),
            "average_success_latency_ms": round(avg_success_latency, 2),
            "vru_breakdown": vru_success_counts,
            "success_rate_percent": metrics["pass_rate_percent"]
        }
    
    async def _generate_report_files(
        self, 
        report_data: Dict[str, Any], 
        formats: List[str], 
        test_session_id: str
    ) -> Dict[str, str]:
        """
        Generate report files in requested formats
        """
        report_files = {}
        base_filename = f"test_report_{test_session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        for format_type in formats:
            try:
                if format_type.lower() == 'json':
                    file_path = self.reports_dir / f"{base_filename}.json"
                    with open(file_path, 'w') as f:
                        json.dump(report_data, f, indent=2, default=str)
                    report_files['json'] = str(file_path)
                
                elif format_type.lower() == 'html':
                    html_content = await self.report_generator.generate_html_report(report_data)
                    file_path = self.reports_dir / f"{base_filename}.html"
                    with open(file_path, 'w') as f:
                        f.write(html_content)
                    report_files['html'] = str(file_path)
                
                elif format_type.lower() == 'pdf':
                    pdf_content = await self.report_generator.generate_pdf_report(report_data)
                    file_path = self.reports_dir / f"{base_filename}.pdf"
                    with open(file_path, 'wb') as f:
                        f.write(pdf_content)
                    report_files['pdf'] = str(file_path)
            
            except Exception as e:
                print(f"Failed to generate {format_type} report: {str(e)}")
        
        return report_files
    
    async def _store_report_metadata(self, report_data: Dict[str, Any], report_files: Dict[str, str]):
        """
        Store report metadata in database for future retrieval
        """
        # This could be extended with a ReportMetadata model
        # For now, we'll store in the test session's metadata
        pass
    
    async def get_test_session_reports(self, test_session_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all reports generated for a test session
        """
        # Implementation would query a reports metadata table
        # For now, return empty list
        return []
    
    async def delete_report(self, report_id: str) -> bool:
        """
        Delete a report and its associated files
        """
        # Implementation would delete files and database records
        return True
