"""
Dashboard Router - Organized API Endpoints
========================================

Consolidated dashboard and statistics endpoints following FastAPI best practices.
Handles system health monitoring, performance metrics, and dashboard data.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from database import SessionLocal
from models import Project, Video, TestSession, DetectionEvent, AuthUser
from schemas import DashboardStats, EnhancedDashboardStats

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["Dashboard & Monitoring"])

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# DASHBOARD STATISTICS
# ============================================================================

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_statistics(db: Session = Depends(get_db)):
    """Get basic dashboard statistics"""
    try:
        # Get counts for main entities
        project_count = db.query(func.count(Project.id)).scalar() or 0
        video_count = db.query(func.count(Video.id)).scalar() or 0
        session_count = db.query(func.count(TestSession.id)).scalar() or 0
        detection_count = db.query(func.count(DetectionEvent.id)).scalar() or 0
        
        # Get active sessions
        active_sessions = db.query(func.count(TestSession.id)).filter(
            TestSession.status == "running"
        ).scalar() or 0
        
        # Get recent activity (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_sessions = db.query(func.count(TestSession.id)).filter(
            TestSession.created_at >= yesterday
        ).scalar() or 0
        
        # Calculate average accuracy (placeholder - should be computed from real data)
        average_accuracy = 0.87  # Default value, should be calculated from detection results
        
        return DashboardStats(
            project_count=project_count,
            video_count=video_count,
            test_session_count=session_count,
            detection_event_count=detection_count,
            average_accuracy=average_accuracy,
            active_tests=active_sessions
        )
        
    except Exception as e:
        logger.error(f"Error retrieving dashboard stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve dashboard stats: {str(e)}")

@router.get("/stats/enhanced", response_model=EnhancedDashboardStats)
async def get_enhanced_dashboard_statistics(
    time_range: str = Query("7d", description="Time range: 1d, 7d, 30d, 90d"),
    db: Session = Depends(get_db)
):
    """Get enhanced dashboard statistics with detailed breakdowns"""
    try:
        # Parse time range
        time_delta_map = {
            "1d": timedelta(days=1),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
            "90d": timedelta(days=90)
        }
        
        if time_range not in time_delta_map:
            raise HTTPException(status_code=400, detail="Invalid time range")
        
        start_date = datetime.utcnow() - time_delta_map[time_range]
        
        # Basic counts
        project_count = db.query(func.count(Project.id)).scalar() or 0
        video_count = db.query(func.count(Video.id)).scalar() or 0
        total_sessions = db.query(func.count(TestSession.id)).scalar() or 0
        total_detections = db.query(func.count(DetectionEvent.id)).scalar() or 0
        
        # Session status breakdown
        session_stats = dict(
            db.query(TestSession.status, func.count(TestSession.id))
            .filter(TestSession.created_at >= start_date)
            .group_by(TestSession.status)
            .all()
        )
        
        # Project type breakdown
        project_stats = dict(
            db.query(Project.camera_model, func.count(Project.id))
            .group_by(Project.camera_model)
            .all()
        )
        
        # Detection type breakdown
        detection_stats = dict(
            db.query(DetectionEvent.vru_type, func.count(DetectionEvent.id))
            .filter(DetectionEvent.created_at >= start_date)
            .group_by(DetectionEvent.vru_type)
            .all()
        )
        
        # Performance metrics
        avg_session_duration = db.query(
            func.avg(
                func.extract('epoch', TestSession.completed_at - TestSession.started_at)
            )
        ).filter(
            TestSession.started_at.isnot(None),
            TestSession.completed_at.isnot(None),
            TestSession.created_at >= start_date
        ).scalar() or 0
        
        # Success rate calculation
        completed_sessions = session_stats.get("completed", 0)
        failed_sessions = session_stats.get("failed", 0)
        total_finished = completed_sessions + failed_sessions
        success_rate = (completed_sessions / total_finished * 100) if total_finished > 0 else 0
        
        # Recent activity trends
        daily_sessions = db.query(
            func.date(TestSession.created_at).label('date'),
            func.count(TestSession.id).label('count')
        ).filter(
            TestSession.created_at >= start_date
        ).group_by(
            func.date(TestSession.created_at)
        ).order_by('date').all()
        
        activity_trend = [
            {
                "date": str(day.date),
                "sessions": day.count
            }
            for day in daily_sessions
        ]
        
        # System health indicators
        recent_errors = db.query(func.count(TestSession.id)).filter(
            TestSession.status == "failed",
            TestSession.created_at >= datetime.utcnow() - timedelta(hours=1)
        ).scalar() or 0
        
        # Return EnhancedDashboardStats with base fields + enhanced fields
        return EnhancedDashboardStats(
            # Base DashboardStats fields
            project_count=project_count,
            video_count=video_count,
            test_session_count=total_sessions,
            detection_event_count=total_detections,
            average_accuracy=87.5,  # Calculate from actual results
            active_tests=session_stats.get("running", 0),
            total_detections=total_detections,
            
            # Enhanced fields
            confidence_intervals={
                "precision": [0.85, 0.95],
                "recall": [0.82, 0.92], 
                "f1_score": [0.83, 0.93]
            },
            trend_analysis={
                "accuracy": "stable",
                "detectionRate": "improving",
                "performance": "stable"
            },
            signal_processing_metrics={
                "totalSignals": detection_count,
                "successRate": float(success_rate),
                "avgProcessingTime": float(avg_session_duration) if avg_session_duration else 0
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving enhanced dashboard stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve enhanced stats: {str(e)}")

# ============================================================================
# SYSTEM HEALTH AND MONITORING
# ============================================================================

@router.get("/health/system")
async def get_system_health(db: Session = Depends(get_db)):
    """Get comprehensive system health information"""
    try:
        # Database connectivity check
        try:
            db.execute(text("SELECT 1"))
            db_status = "healthy"
            db_message = "Database connection successful"
        except Exception as e:
            db_status = "error"
            db_message = f"Database error: {str(e)}"
        
        # Recent activity check
        recent_activity = db.query(func.count(TestSession.id)).filter(
            TestSession.created_at >= datetime.utcnow() - timedelta(minutes=5)
        ).scalar() or 0
        
        # Error rate check (last hour)
        recent_errors = db.query(func.count(TestSession.id)).filter(
            TestSession.status == "failed",
            TestSession.created_at >= datetime.utcnow() - timedelta(hours=1)
        ).scalar() or 0
        
        recent_total = db.query(func.count(TestSession.id)).filter(
            TestSession.created_at >= datetime.utcnow() - timedelta(hours=1)
        ).scalar() or 0
        
        error_rate = (recent_errors / recent_total * 100) if recent_total > 0 else 0
        
        # Active sessions check
        active_sessions = db.query(func.count(TestSession.id)).filter(
            TestSession.status == "running"
        ).scalar() or 0
        
        # Overall system status
        overall_status = "healthy"
        if db_status == "error":
            overall_status = "critical"
        elif error_rate > 10:
            overall_status = "warning"
        elif recent_activity == 0 and active_sessions == 0:
            overall_status = "idle"
        
        return {
            "overall_status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "database": {
                    "status": db_status,
                    "message": db_message
                },
                "sessions": {
                    "active_sessions": active_sessions,
                    "recent_activity": recent_activity,
                    "error_rate_percentage": round(error_rate, 2)
                }
            },
            "metrics": {
                "uptime_check": "operational",
                "last_health_check": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"System health check failed: {str(e)}")
        return {
            "overall_status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }

@router.get("/health/database")
async def get_database_health(db: Session = Depends(get_db)):
    """Get detailed database health information"""
    try:
        health_info = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {}
        }
        
        # Connection test
        try:
            db.execute(text("SELECT 1"))
            health_info["checks"]["connection"] = {
                "status": "ok",
                "message": "Database connection successful"
            }
        except Exception as e:
            health_info["status"] = "error"
            health_info["checks"]["connection"] = {
                "status": "error",
                "message": str(e)
            }
        
        # Table existence checks
        required_tables = ["projects", "videos", "test_sessions", "detection_events"]
        for table in required_tables:
            try:
                db.execute(text(f"SELECT COUNT(*) FROM {table} LIMIT 1"))
                health_info["checks"][f"table_{table}"] = {
                    "status": "ok",
                    "message": f"Table {table} accessible"
                }
            except Exception as e:
                health_info["status"] = "warning"
                health_info["checks"][f"table_{table}"] = {
                    "status": "error",
                    "message": f"Table {table} error: {str(e)}"
                }
        
        # Record counts
        try:
            counts = {
                "projects": db.query(func.count(Project.id)).scalar() or 0,
                "videos": db.query(func.count(Video.id)).scalar() or 0,
                "test_sessions": db.query(func.count(TestSession.id)).scalar() or 0,
                "detection_events": db.query(func.count(DetectionEvent.id)).scalar() or 0
            }
            health_info["record_counts"] = counts
        except Exception as e:
            health_info["checks"]["record_counts"] = {
                "status": "error",
                "message": f"Failed to get record counts: {str(e)}"
            }
        
        return health_info
        
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return {
            "status": "critical",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }

# ============================================================================
# PERFORMANCE METRICS
# ============================================================================

@router.get("/metrics/performance")
async def get_performance_metrics(
    hours: int = Query(24, description="Hours to look back for metrics"),
    db: Session = Depends(get_db)
):
    """Get detailed performance metrics"""
    try:
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Session performance metrics
        session_metrics = db.query(
            func.count(TestSession.id).label('total_sessions'),
            func.avg(
                func.extract('epoch', TestSession.completed_at - TestSession.started_at)
            ).label('avg_duration'),
            func.min(
                func.extract('epoch', TestSession.completed_at - TestSession.started_at)
            ).label('min_duration'),
            func.max(
                func.extract('epoch', TestSession.completed_at - TestSession.started_at)
            ).label('max_duration')
        ).filter(
            TestSession.created_at >= start_time,
            TestSession.started_at.isnot(None),
            TestSession.completed_at.isnot(None)
        ).first()
        
        # Detection rate metrics
        detection_rate = db.query(
            func.count(DetectionEvent.id).label('total_detections'),
            func.count(func.distinct(DetectionEvent.test_session_id)).label('sessions_with_detections')
        ).filter(
            DetectionEvent.created_at >= start_time
        ).first()
        
        # Error metrics
        error_metrics = db.query(
            TestSession.status,
            func.count(TestSession.id)
        ).filter(
            TestSession.created_at >= start_time
        ).group_by(TestSession.status).all()
        
        status_breakdown = dict(error_metrics)
        
        # Hourly activity breakdown
        hourly_activity = db.query(
            func.date_trunc('hour', TestSession.created_at).label('hour'),
            func.count(TestSession.id).label('session_count')
        ).filter(
            TestSession.created_at >= start_time
        ).group_by('hour').order_by('hour').all()
        
        activity_by_hour = [
            {
                "hour": hour.hour.isoformat(),
                "session_count": hour.session_count
            }
            for hour in hourly_activity
        ]
        
        return {
            "time_range_hours": hours,
            "generated_at": datetime.utcnow().isoformat(),
            "session_performance": {
                "total_sessions": session_metrics.total_sessions or 0,
                "average_duration_seconds": float(session_metrics.avg_duration or 0),
                "min_duration_seconds": float(session_metrics.min_duration or 0),
                "max_duration_seconds": float(session_metrics.max_duration or 0)
            },
            "detection_metrics": {
                "total_detections": detection_rate.total_detections or 0,
                "sessions_with_detections": detection_rate.sessions_with_detections or 0,
                "avg_detections_per_session": (
                    (detection_rate.total_detections / detection_rate.sessions_with_detections)
                    if detection_rate.sessions_with_detections and detection_rate.sessions_with_detections > 0
                    else 0
                )
            },
            "status_breakdown": status_breakdown,
            "activity_by_hour": activity_by_hour
        }
        
    except Exception as e:
        logger.error(f"Error retrieving performance metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve performance metrics: {str(e)}")

# ============================================================================
# REAL-TIME MONITORING
# ============================================================================

@router.get("/monitoring/live")
async def get_live_monitoring_data(db: Session = Depends(get_db)):
    """Get real-time monitoring data for live dashboard"""
    try:
        now = datetime.utcnow()
        
        # Current active sessions
        active_sessions = db.query(TestSession).filter(
            TestSession.status.in_(["running", "processing"])
        ).all()
        
        # Recent detections (last 5 minutes)
        recent_detections = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.created_at >= now - timedelta(minutes=5)
        ).scalar() or 0
        
        # System load indicators
        total_processing = len([s for s in active_sessions if s.status == "processing"])
        total_running = len([s for s in active_sessions if s.status == "running"])
        
        # Recent error count
        recent_errors = db.query(func.count(TestSession.id)).filter(
            TestSession.status == "failed",
            TestSession.created_at >= now - timedelta(minutes=10)
        ).scalar() or 0
        
        return {
            "timestamp": now.isoformat(),
            "active_sessions": {
                "total": len(active_sessions),
                "running": total_running,
                "processing": total_processing,
                "details": [
                    {
                        "id": session.id,
                        "name": session.name,
                        "status": session.status,
                        "started_at": session.started_at.isoformat() if session.started_at else None,
                        "duration_seconds": (
                            (now - session.started_at).total_seconds()
                            if session.started_at
                            else None
                        )
                    }
                    for session in active_sessions
                ]
            },
            "recent_activity": {
                "detections_last_5min": recent_detections,
                "errors_last_10min": recent_errors
            },
            "system_status": {
                "load_level": "high" if len(active_sessions) > 10 else "medium" if len(active_sessions) > 5 else "low",
                "health_status": "warning" if recent_errors > 0 else "healthy"
            }
        }
        
    except Exception as e:
        logger.error(f"Error retrieving live monitoring data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve live data: {str(e)}")

# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def dashboard_health_check():
    """Health check endpoint for dashboard service"""
    return {
        "status": "healthy",
        "service": "Dashboard Router",
        "version": "1.0.0",
        "endpoints": [
            "GET /api/dashboard/stats - Basic dashboard statistics",
            "GET /api/dashboard/stats/enhanced - Enhanced dashboard statistics",
            "GET /api/dashboard/health/system - System health check",
            "GET /api/dashboard/health/database - Database health check",
            "GET /api/dashboard/metrics/performance - Performance metrics",
            "GET /api/dashboard/monitoring/live - Real-time monitoring data"
        ]
    }