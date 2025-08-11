
import time
import psutil
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware

# Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total', 
    'Total HTTP requests', 
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'http_active_connections',
    'Number of active HTTP connections'
)

MEMORY_USAGE = Gauge(
    'system_memory_usage_bytes',
    'System memory usage in bytes'
)

CPU_USAGE = Gauge(
    'system_cpu_usage_percent',
    'System CPU usage percentage'
)

class PrometheusMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.active_requests = 0
    
    async def dispatch(self, request: Request, call_next):
        # Increment active connections
        self.active_requests += 1
        ACTIVE_CONNECTIONS.set(self.active_requests)
        
        # Start timing
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Record metrics
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=self._get_endpoint(request),
            status=response.status_code
        ).inc()
        
        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=self._get_endpoint(request)
        ).observe(duration)
        
        # Update system metrics
        self._update_system_metrics()
        
        # Decrement active connections
        self.active_requests -= 1
        ACTIVE_CONNECTIONS.set(self.active_requests)
        
        # Add timing header
        response.headers["X-Process-Time"] = str(duration)
        
        return response
    
    def _get_endpoint(self, request: Request) -> str:
        """Extract endpoint pattern from request"""
        if request.scope.get("route"):
            return request.scope["route"].path
        return request.url.path
    
    def _update_system_metrics(self):
        """Update system resource metrics"""
        # Memory usage
        memory = psutil.virtual_memory()
        MEMORY_USAGE.set(memory.used)
        
        # CPU usage
        cpu_percent = psutil.cpu_percent()
        CPU_USAGE.set(cpu_percent)

# Add to FastAPI app
app.add_middleware(PrometheusMiddleware)

@app.get("/metrics")
async def get_metrics():
    return Response(
        generate_latest(), 
        media_type="text/plain"
    )
