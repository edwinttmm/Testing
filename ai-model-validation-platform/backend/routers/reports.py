from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import os
from pathlib import Path
import time

from database import get_db
from models import TestSession, TestReport, ReportSnapshot
from schemas import (
    ReportGenerationRequest, TestReportFileResponse, TestReportResponse,
    ReportListResponse, ReportListItem, TestReportMetrics, DetectionOutcomeEnum
)
from services.report_generation_service import ReportGenerationService

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

@router.post("/generate", response_model=TestReportFileResponse)
async def generate_test_report(
    report_request: ReportGenerationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Generate comprehensive test report according to PRD Module 4.2
    
    PRD Requirements:
    - Top-level summary of pass/fail rates and average latency  
    - Video snapshot for every failure (HIGH_LATENCY and MISSED_DETECTION)
    - Success summaries in text format (no visual review needed)
    - Multiple output formats (PDF, HTML, JSON)
    """
    start_time = time.time()
    
    # Validate test session exists
    test_session = db.query(TestSession).filter(
        TestSession.id == report_request.test_session_id
    ).first()
    
    if not test_session:
        raise HTTPException(
            status_code=404, 
            detail=f"Test session {report_request.test_session_id} not found"
        )
    
    try:
        # Initialize report generation service
        report_service = ReportGenerationService(db)
        
        # Generate comprehensive report
        report_result = await report_service.generate_comprehensive_report(
            test_session_id=report_request.test_session_id,
            include_snapshots=report_request.include_snapshots,
            formats=report_request.formats
        )
        
        generation_time_ms = (time.time() - start_time) * 1000
        
        # Store report metadata in database
        await _store_report_metadata(
            db, report_result, report_request, generation_time_ms
        )
        
        return TestReportFileResponse(**report_result)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Report generation failed: {str(e)}"
        )

@router.get("/test-sessions/{test_session_id}", response_model=List[ReportListItem])
async def get_test_session_reports(
    test_session_id: str,
    db: Session = Depends(get_db)
):
    """Get all reports generated for a specific test session"""
    
    # Validate test session exists
    test_session = db.query(TestSession).filter(
        TestSession.id == test_session_id
    ).first()
    
    if not test_session:
        raise HTTPException(
            status_code=404,
            detail=f"Test session {test_session_id} not found"
        )
    
    # Get reports for this test session
    reports = db.query(TestReport).filter(
        TestReport.test_session_id == test_session_id
    ).order_by(TestReport.generated_at.desc()).all()
    
    report_items = []
    for report in reports:
        report_items.append(ReportListItem(
            id=report.id,
            test_session_id=report.test_session_id,
            report_name=report.report_name,
            report_type=report.report_type,
            formats_generated=report.formats_generated or [],
            pass_rate_percent=report.pass_rate_percent or 0,
            test_outcome=report.test_outcome or "UNKNOWN",
            generated_at=report.generated_at.isoformat(),
            generated_by=report.generated_by or "system",
            failure_snapshots_count=report.failure_snapshots_count or 0
        ))
    
    return report_items

@router.get("/", response_model=ReportListResponse)
async def list_reports(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    report_type: Optional[str] = Query(default=None, description="Filter by report type"),
    test_outcome: Optional[str] = Query(default=None, description="Filter by test outcome"),
    db: Session = Depends(get_db)
):
    """List all generated reports with pagination and filtering"""
    
    query = db.query(TestReport)
    
    # Apply filters
    if report_type:
        query = query.filter(TestReport.report_type == report_type)
    
    if test_outcome:
        query = query.filter(TestReport.test_outcome == test_outcome)
    
    # Get total count for pagination
    total_count = query.count()
    
    # Apply pagination
    offset = (page - 1) * page_size
    reports = query.order_by(TestReport.generated_at.desc()).offset(offset).limit(page_size).all()
    
    # Convert to response items
    report_items = []
    for report in reports:
        report_items.append(ReportListItem(
            id=report.id,
            test_session_id=report.test_session_id,
            report_name=report.report_name,
            report_type=report.report_type,
            formats_generated=report.formats_generated or [],
            pass_rate_percent=report.pass_rate_percent or 0,
            test_outcome=report.test_outcome or "UNKNOWN",
            generated_at=report.generated_at.isoformat(),
            generated_by=report.generated_by or "system",
            failure_snapshots_count=report.failure_snapshots_count or 0
        ))
    
    return ReportListResponse(
        reports=report_items,
        total_count=total_count,
        page=page,
        page_size=page_size
    )

@router.get("/{report_id}/view/html", response_class=HTMLResponse)
async def view_html_report(
    report_id: str,
    db: Session = Depends(get_db)
):
    """View HTML report in browser"""
    
    report = db.query(TestReport).filter(TestReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if not report.html_report_path or not os.path.exists(report.html_report_path):
        raise HTTPException(status_code=404, detail="HTML report file not found")
    
    try:
        with open(report.html_report_path, 'r') as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read HTML report: {str(e)}")

@router.get("/{report_id}/download/{format}")
async def download_report(
    report_id: str,
    format: str,
    db: Session = Depends(get_db)
):
    """Download report in specified format (html, pdf, json, csv)"""
    
    report = db.query(TestReport).filter(TestReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Get file path based on format
    file_path = None
    media_type = "application/octet-stream"
    
    if format.lower() == "html":
        file_path = report.html_report_path
        media_type = "text/html"
    elif format.lower() == "pdf":
        file_path = report.pdf_report_path
        media_type = "application/pdf"
    elif format.lower() == "json":
        file_path = report.json_report_path
        media_type = "application/json"
    elif format.lower() == "csv":
        file_path = report.csv_summary_path
        media_type = "text/csv"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
    
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"{format.upper()} report file not found")
    
    filename = f"test_report_{report_id}.{format.lower()}"
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )

@router.get("/{report_id}/snapshots", response_model=List[dict])
async def get_report_snapshots(
    report_id: str,
    failure_type: Optional[str] = Query(default=None, description="Filter by failure type"),
    db: Session = Depends(get_db)
):
    """Get all failure snapshots for a report"""
    
    report = db.query(TestReport).filter(TestReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    query = db.query(ReportSnapshot).filter(ReportSnapshot.report_id == report_id)
    
    if failure_type:
        query = query.filter(ReportSnapshot.failure_type == failure_type.upper())
    
    snapshots = query.order_by(ReportSnapshot.timestamp_ms).all()
    
    snapshot_details = []
    for snapshot in snapshots:
        snapshot_details.append({
            "id": snapshot.id,
            "event_id": snapshot.detection_event_id,
            "video_id": snapshot.video_id,
            "failure_type": snapshot.failure_type,
            "timestamp_ms": snapshot.timestamp_ms,
            "frame_number": snapshot.frame_number,
            "filename": snapshot.snapshot_filename,
            "file_size_bytes": snapshot.file_size_bytes,
            "captured_at": snapshot.captured_at.isoformat(),
            "capture_success": snapshot.capture_success,
            "error_message": snapshot.error_message
        })
    
    return snapshot_details

@router.get("/{report_id}/snapshots/{snapshot_id}/image")
async def get_snapshot_image(
    report_id: str,
    snapshot_id: str,
    db: Session = Depends(get_db)
):
    """Get snapshot image file"""
    
    snapshot = db.query(ReportSnapshot).filter(
        ReportSnapshot.id == snapshot_id,
        ReportSnapshot.report_id == report_id
    ).first()
    
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    if not snapshot.capture_success:
        raise HTTPException(status_code=400, detail=f"Snapshot capture failed: {snapshot.error_message}")
    
    if not os.path.exists(snapshot.snapshot_path):
        raise HTTPException(status_code=404, detail="Snapshot file not found")
    
    return FileResponse(
        path=snapshot.snapshot_path,
        media_type="image/jpeg",
        filename=snapshot.snapshot_filename
    )

@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    db: Session = Depends(get_db)
):
    """Delete a report and all associated files"""
    
    report = db.query(TestReport).filter(TestReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    try:
        # Delete associated files
        file_paths = [
            report.html_report_path,
            report.pdf_report_path, 
            report.json_report_path,
            report.csv_summary_path
        ]
        
        for file_path in file_paths:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        
        # Delete snapshot files
        snapshots = db.query(ReportSnapshot).filter(ReportSnapshot.report_id == report_id).all()
        for snapshot in snapshots:
            if os.path.exists(snapshot.snapshot_path):
                os.remove(snapshot.snapshot_path)
        
        # Delete database records (cascading will handle snapshots)
        db.delete(report)
        db.commit()
        
        return {"message": "Report deleted successfully", "report_id": report_id}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete report: {str(e)}")

@router.get("/stats", response_model=dict)
async def get_report_statistics(db: Session = Depends(get_db)):
    """Get statistics about generated reports"""
    
    total_reports = db.query(TestReport).count()
    
    # Get report counts by outcome
    pass_reports = db.query(TestReport).filter(TestReport.test_outcome == "PASS").count()
    fail_reports = db.query(TestReport).filter(TestReport.test_outcome == "FAIL").count()
    
    # Get snapshot statistics
    total_snapshots = db.query(ReportSnapshot).count()
    successful_snapshots = db.query(ReportSnapshot).filter(ReportSnapshot.capture_success == True).count()
    
    # Get storage usage
    total_snapshot_size = db.query(func.sum(ReportSnapshot.file_size_bytes)).scalar() or 0
    
    return {
        "total_reports": total_reports,
        "pass_reports": pass_reports,
        "fail_reports": fail_reports,
        "pass_rate_percent": round((pass_reports / total_reports * 100) if total_reports > 0 else 0, 2),
        "total_snapshots": total_snapshots,
        "successful_snapshots": successful_snapshots,
        "snapshot_success_rate": round((successful_snapshots / total_snapshots * 100) if total_snapshots > 0 else 0, 2),
        "total_snapshot_storage_bytes": total_snapshot_size,
        "total_snapshot_storage_mb": round(total_snapshot_size / (1024 * 1024), 2)
    }

async def _store_report_metadata(
    db: Session, 
    report_result: dict, 
    report_request: ReportGenerationRequest,
    generation_time_ms: float
):
    """Store report metadata in database"""
    try:
        report_data = report_result["report_data"]
        report_files = report_result["report_files"]
        metrics = report_result["metrics"]
        
        # Create TestReport record
        test_report = TestReport(
            test_session_id=report_request.test_session_id,
            report_name=report_request.report_name or f"Test Report {report_data['test_session']['name']}",
            report_type=report_request.report_type,
            formats_generated=list(report_files.keys()),
            total_events=metrics["total_events"],
            passed_events=metrics["passed_events"],
            failed_events=metrics["failed_events"],
            pass_rate_percent=metrics["pass_rate_percent"],
            average_latency_ms=metrics["average_latency_ms"],
            test_outcome=metrics["test_outcome"],
            html_report_path=report_files.get("html"),
            pdf_report_path=report_files.get("pdf"),
            json_report_path=report_files.get("json"),
            csv_summary_path=report_files.get("csv"),
            failure_snapshots_count=len(report_data.get("failure_snapshots", [])),
            generation_time_ms=generation_time_ms,
            generated_by="api"
        )
        
        db.add(test_report)
        db.flush()  # Get the ID
        
        # Create ReportSnapshot records
        for snapshot in report_data.get("failure_snapshots", []):
            if not snapshot.get("error"):
                report_snapshot = ReportSnapshot(
                    report_id=test_report.id,
                    detection_event_id=snapshot["event_id"],
                    video_id=snapshot.get("video_id"),
                    failure_type=snapshot["failure_type"],
                    timestamp_ms=snapshot["timestamp_ms"],
                    frame_number=snapshot.get("frame_number"),
                    snapshot_filename=Path(snapshot["snapshot_path"]).name,
                    snapshot_path=snapshot["snapshot_path"],
                    file_size_bytes=os.path.getsize(snapshot["snapshot_path"]) if os.path.exists(snapshot["snapshot_path"]) else 0,
                    capture_success=True
                )
                db.add(report_snapshot)
            else:
                # Record failed snapshot
                report_snapshot = ReportSnapshot(
                    report_id=test_report.id,
                    detection_event_id=snapshot["event_id"],
                    failure_type=snapshot["failure_type"],
                    snapshot_filename="",
                    snapshot_path="",
                    capture_success=False,
                    error_message=snapshot["error"]
                )
                db.add(report_snapshot)
        
        db.commit()
        
    except Exception as e:
        db.rollback()
        print(f"Failed to store report metadata: {str(e)}")
        # Don't fail the whole report generation for metadata storage issues