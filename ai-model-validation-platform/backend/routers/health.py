"""
Comprehensive Health Check and Monitoring Endpoints

Provides:
- Liveness check (is service running?)
- Readiness check (can service handle requests?)
- Health check (are all dependencies healthy?)
- Metrics endpoint (Prometheus scraping)
- System info endpoint
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, Any
import psutil
import os

from database import get_db
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from utils.logging_config import StructuredLogger

router = APIRouter(prefix="/health", tags=["health"])
logger = StructuredLogger(__name__)


@router.get("/live")
async def liveness_check() -> Dict[str, str]:
    """
    Liveness probe - is the service running?

    Returns 200 if the service process is alive.
    Used by Kubernetes/Docker to restart crashed containers.
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat() + 'Z'
    }


@router.get("/ready")
async def readiness_check(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Readiness probe - can the service handle requests?

    Checks:
    - Database connectivity
    - Critical dependencies

    Returns 200 if ready, 503 if not ready.
    Used by load balancers to route traffic.
    """
    checks = {
        'database': 'unknown',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }

    overall_status = 'ready'

    # Database check
    try:
        db.execute('SELECT 1')
        checks['database'] = 'ok'
        logger.debug("Readiness check: database OK")
    except Exception as e:
        checks['database'] = f'error: {str(e)}'
        overall_status = 'not_ready'
        logger.error(
            "Readiness check: database failed",
            exc_info=True,
            error=str(e)
        )

    # If any check failed, return 503
    if overall_status != 'ready':
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail={
                'status': overall_status,
                'checks': checks
            }
        )

    return {
        'status': overall_status,
        'checks': checks
    }


@router.get("/health")
async def health_check(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Comprehensive health check with detailed component status.

    Checks:
    - Database connectivity and query performance
    - WebSocket service availability
    - Disk space
    - Memory usage
    - System resources

    Returns detailed health status for monitoring dashboards.
    """
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'checks': {},
        'metrics': {}
    }

    # Database health check with timing
    try:
        import time
        start = time.time()
        db.execute('SELECT 1')
        query_time_ms = (time.time() - start) * 1000

        health_status['checks']['database'] = {
            'status': 'ok',
            'query_time_ms': round(query_time_ms, 2)
        }

        # Check database size
        try:
            result = db.execute(
                "SELECT pg_database_size(current_database()) as size"
            ).fetchone()
            if result:
                db_size_mb = result[0] / (1024 * 1024)
                health_status['metrics']['database_size_mb'] = round(db_size_mb, 2)
        except Exception:
            pass  # Non-critical

    except Exception as e:
        health_status['checks']['database'] = {
            'status': 'error',
            'error': str(e)
        }
        health_status['status'] = 'unhealthy'
        logger.error(
            "Health check: database error",
            exc_info=True,
            error=str(e)
        )

    # WebSocket service check
    try:
        # Simple check - verify socketio module is importable
        import socketio_server
        health_status['checks']['websocket'] = {'status': 'ok'}
    except Exception as e:
        health_status['checks']['websocket'] = {
            'status': 'degraded',
            'error': str(e)
        }
        # WebSocket failure is degraded, not unhealthy
        if health_status['status'] == 'healthy':
            health_status['status'] = 'degraded'

    # System resource checks
    try:
        # Memory usage
        memory = psutil.virtual_memory()
        health_status['metrics']['memory'] = {
            'total_mb': round(memory.total / (1024 * 1024), 2),
            'available_mb': round(memory.available / (1024 * 1024), 2),
            'percent_used': memory.percent
        }

        if memory.percent > 90:
            health_status['checks']['memory'] = {
                'status': 'warning',
                'message': f'Memory usage high: {memory.percent}%'
            }
            if health_status['status'] == 'healthy':
                health_status['status'] = 'degraded'
        else:
            health_status['checks']['memory'] = {'status': 'ok'}

        # Disk usage
        disk = psutil.disk_usage('/')
        health_status['metrics']['disk'] = {
            'total_gb': round(disk.total / (1024 ** 3), 2),
            'free_gb': round(disk.free / (1024 ** 3), 2),
            'percent_used': disk.percent
        }

        if disk.percent > 90:
            health_status['checks']['disk'] = {
                'status': 'warning',
                'message': f'Disk usage high: {disk.percent}%'
            }
            if health_status['status'] == 'healthy':
                health_status['status'] = 'degraded'
        else:
            health_status['checks']['disk'] = {'status': 'ok'}

        # CPU usage (5 second average)
        cpu_percent = psutil.cpu_percent(interval=0.1)
        health_status['metrics']['cpu_percent'] = cpu_percent

        if cpu_percent > 80:
            health_status['checks']['cpu'] = {
                'status': 'warning',
                'message': f'CPU usage high: {cpu_percent}%'
            }
        else:
            health_status['checks']['cpu'] = {'status': 'ok'}

    except Exception as e:
        logger.warning(
            "Health check: system metrics collection failed",
            exc_info=True,
            error=str(e)
        )
        # Non-critical failure

    # Process info
    try:
        process = psutil.Process(os.getpid())
        health_status['metrics']['process'] = {
            'pid': process.pid,
            'memory_mb': round(process.memory_info().rss / (1024 * 1024), 2),
            'cpu_percent': process.cpu_percent(interval=0.1),
            'threads': process.num_threads()
        }
    except Exception:
        pass  # Non-critical

    return health_status


@router.get("/metrics")
async def metrics_endpoint():
    """
    Prometheus metrics endpoint.

    Exposes all application metrics in Prometheus format for scraping.
    Configure Prometheus to scrape this endpoint at regular intervals.

    Example Prometheus config:
    ```yaml
    scrape_configs:
      - job_name: 'hil-backend'
        scrape_interval: 15s
        static_configs:
          - targets: ['localhost:8000']
        metrics_path: '/health/metrics'
    ```
    """
    metrics_output = generate_latest()
    return Response(
        content=metrics_output,
        media_type=CONTENT_TYPE_LATEST
    )


@router.get("/info")
async def system_info() -> Dict[str, Any]:
    """
    System information endpoint.

    Returns version, configuration, and runtime info.
    Useful for debugging and deployment verification.
    """
    import sys
    import platform

    info = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'python_version': sys.version,
        'platform': platform.platform(),
        'processor': platform.processor(),
        'hostname': platform.node(),
        'environment': os.getenv('ENVIRONMENT', 'unknown'),
    }

    # Add application version if available
    try:
        with open('VERSION', 'r') as f:
            info['app_version'] = f.read().strip()
    except:
        info['app_version'] = 'unknown'

    return info


# Example integration in main.py:
"""
from routers import health

app.include_router(health.router)

# Health check URLs:
# GET /health/live       - Liveness probe
# GET /health/ready      - Readiness probe
# GET /health/health     - Comprehensive health
# GET /health/metrics    - Prometheus metrics
# GET /health/info       - System information
"""
