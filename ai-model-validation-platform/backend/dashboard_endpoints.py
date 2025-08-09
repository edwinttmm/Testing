# Dashboard endpoints to add to main.py

# Add this import at the top
from sqlalchemy import func

# Add these endpoints before the health check

# Dashboard endpoints
@app.get("/api/dashboard/stats")
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get dashboard statistics"""
    try:
        # Import models here to avoid circular imports
        from models import Project
        
        # Get counts from database
        project_count = db.query(func.count(Project.id)).filter(Project.user_id == current_user.id).scalar() or 0
        
        # For now, return basic stats - will be enhanced as more features are implemented
        return {
            "projectCount": project_count,
            "videoCount": 0,  # Will be implemented when video models are ready
            "testCount": 0,   # Will be implemented when test models are ready
            "averageAccuracy": 0.0,
            "activeTests": 0,
            "totalDetections": 0
        }
        
    except Exception as e:
        logger.error(f"Dashboard stats error: {str(e)}")
        # Return fallback data instead of error
        return {
            "projectCount": 0,
            "videoCount": 0,
            "testCount": 0,
            "averageAccuracy": 0.0,
            "activeTests": 0,
            "totalDetections": 0
        }

@app.get("/api/dashboard/charts")
async def get_chart_data(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get chart data for dashboard"""
    try:
        # Return sample chart data for now - will be enhanced with real data
        from datetime import datetime, timedelta
        
        # Generate sample dates for the last 7 days
        dates = []
        for i in range(7):
            date = datetime.utcnow() - timedelta(days=i)
            dates.append(date.strftime('%Y-%m-%d'))
        
        return {
            "accuracyTrend": [
                {"date": date, "accuracy": 0.0}
                for date in reversed(dates)
            ],
            "detectionsByType": [],
            "recentActivity": [
                {"date": date, "activity": "test_sessions", "count": 0}
                for date in reversed(dates)
            ]
        }
        
    except Exception as e:
        logger.error(f"Dashboard charts error: {str(e)}")
        return {
            "accuracyTrend": [],
            "detectionsByType": [],
            "recentActivity": []
        }