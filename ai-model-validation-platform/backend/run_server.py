#!/usr/bin/env python3
"""
Optimized FastAPI server startup with concurrent request handling
Fixes backend responsiveness during ML operations
"""
import uvicorn
import multiprocessing
import os
from config import settings

def get_optimal_workers():
    """Calculate optimal number of worker processes"""
    cpu_count = multiprocessing.cpu_count()
    # For ML workloads, use fewer workers to avoid GPU contention
    # But ensure at least 2 workers for concurrent request handling
    return max(2, min(4, cpu_count // 2))

def get_uvicorn_config():
    """Get optimized Uvicorn configuration for ML workloads"""
    config = {
        "app": "main:socketio_app",
        "host": "0.0.0.0", 
        "port": settings.api_port,
        "workers": 1,  # Single worker mode for Socket.IO compatibility
        "worker_class": "uvicorn.workers.UvicornWorker",
        "loop": "asyncio",
        "http": "auto",
        "ws": "auto",
        "lifespan": "auto",
        "log_level": "info",
        "access_log": True,
        "use_colors": True,
        "server_header": False,
        "date_header": True,
        "forwarded_allow_ips": "*",
        "proxy_headers": True,
        "timeout_keep_alive": 30,
        "timeout_graceful_shutdown": 30,
        # Threading configuration for blocking operations
        "limit_max_requests": 1000,
        "limit_concurrency": 100,
    }
    
    # Development vs Production settings
    if os.getenv("ENVIRONMENT", "development") == "production":
        config.update({
            "reload": False,
            "log_level": "warning",
            "access_log": False,
        })
    else:
        config.update({
            "reload": True,
            "reload_dirs": [".", "services", "schemas"],
            "reload_excludes": ["uploads", "screenshots", "logs"],
        })
    
    return config

def main():
    """Start optimized FastAPI server"""
    print("🚀 Starting AI Model Validation Platform Backend")
    print("⚡ Optimized for concurrent ML operations")
    
    config = get_uvicorn_config()
    print(f"📊 Configuration:")
    print(f"   - Workers: {config['workers']}")
    print(f"   - Host: {config['host']}:{config['port']}")
    print(f"   - Concurrency limit: {config['limit_concurrency']}")
    print(f"   - Max requests: {config['limit_max_requests']}")
    
    # Start server with optimized configuration
    uvicorn.run(**config)

if __name__ == "__main__":
    main()