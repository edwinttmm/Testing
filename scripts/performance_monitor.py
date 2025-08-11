#!/usr/bin/env python3
"""
Performance Monitoring Script for AI Model Validation Platform
Monitors key performance metrics and generates alerts
"""

import asyncio
import time
import json
import logging
import psutil
import aiohttp
import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Performance metrics data structure"""
    timestamp: str
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    api_response_time: Optional[float]
    db_query_time: Optional[float]
    active_connections: int
    database_size_mb: float
    video_processing_queue: int

@dataclass
class PerformanceThresholds:
    """Performance alert thresholds"""
    cpu_usage_warning: float = 70.0
    cpu_usage_critical: float = 85.0
    memory_usage_warning: float = 80.0
    memory_usage_critical: float = 90.0
    api_response_warning: float = 1000.0  # ms
    api_response_critical: float = 3000.0  # ms
    db_query_warning: float = 100.0  # ms
    db_query_critical: float = 500.0  # ms

class PerformanceMonitor:
    def __init__(self, 
                 api_base_url: str = "http://localhost:8001",
                 db_path: str = "./test_database.db",
                 output_file: str = "performance_metrics.json"):
        self.api_base_url = api_base_url
        self.db_path = db_path
        self.output_file = output_file
        self.thresholds = PerformanceThresholds()
        self.metrics_history: List[PerformanceMetrics] = []

    async def collect_system_metrics(self) -> Dict:
        """Collect system-level performance metrics"""
        try:
            # CPU usage
            cpu_usage = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage = disk.percent
            
            # Network connections
            connections = len(psutil.net_connections())
            
            return {
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage,
                'disk_usage': disk_usage,
                'active_connections': connections
            }
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return {
                'cpu_usage': 0,
                'memory_usage': 0,
                'disk_usage': 0,
                'active_connections': 0
            }

    async def test_api_performance(self) -> Optional[float]:
        """Test API response time"""
        try:
            start_time = time.time()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_base_url}/health",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        response_time = (time.time() - start_time) * 1000  # ms
                        return response_time
                    else:
                        logger.warning(f"API health check failed: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"API performance test failed: {e}")
            return None

    def test_database_performance(self) -> Optional[float]:
        """Test database query performance"""
        try:
            start_time = time.time()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Test query
                cursor.execute("""
                    SELECT COUNT(*) FROM projects 
                    JOIN videos ON projects.id = videos.project_id
                """)
                cursor.fetchone()
                
                query_time = (time.time() - start_time) * 1000  # ms
                return query_time
                
        except Exception as e:
            logger.error(f"Database performance test failed: {e}")
            return None

    def get_database_size(self) -> float:
        """Get database file size in MB"""
        try:
            import os
            size_bytes = os.path.getsize(self.db_path)
            size_mb = size_bytes / (1024 * 1024)
            return size_mb
        except Exception as e:
            logger.error(f"Error getting database size: {e}")
            return 0.0

    def get_video_processing_queue(self) -> int:
        """Get number of videos in processing queue"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM videos 
                    WHERE status IN ('uploaded', 'processing')
                """)
                result = cursor.fetchone()
                return result[0] if result else 0
                
        except Exception as e:
            logger.error(f"Error getting video queue size: {e}")
            return 0

    async def collect_all_metrics(self) -> PerformanceMetrics:
        """Collect all performance metrics"""
        timestamp = datetime.now().isoformat()
        
        # Collect metrics
        system_metrics = await self.collect_system_metrics()
        api_response_time = await self.test_api_performance()
        db_query_time = self.test_database_performance()
        database_size = self.get_database_size()
        video_queue = self.get_video_processing_queue()
        
        metrics = PerformanceMetrics(
            timestamp=timestamp,
            cpu_usage=system_metrics['cpu_usage'],
            memory_usage=system_metrics['memory_usage'],
            disk_usage=system_metrics['disk_usage'],
            api_response_time=api_response_time,
            db_query_time=db_query_time,
            active_connections=system_metrics['active_connections'],
            database_size_mb=database_size,
            video_processing_queue=video_queue
        )
        
        return metrics

    def check_thresholds(self, metrics: PerformanceMetrics) -> List[str]:
        """Check metrics against thresholds and return alerts"""
        alerts = []
        
        # CPU usage alerts
        if metrics.cpu_usage >= self.thresholds.cpu_usage_critical:
            alerts.append(f"CRITICAL: CPU usage at {metrics.cpu_usage:.1f}%")
        elif metrics.cpu_usage >= self.thresholds.cpu_usage_warning:
            alerts.append(f"WARNING: CPU usage at {metrics.cpu_usage:.1f}%")
        
        # Memory usage alerts
        if metrics.memory_usage >= self.thresholds.memory_usage_critical:
            alerts.append(f"CRITICAL: Memory usage at {metrics.memory_usage:.1f}%")
        elif metrics.memory_usage >= self.thresholds.memory_usage_warning:
            alerts.append(f"WARNING: Memory usage at {metrics.memory_usage:.1f}%")
        
        # API response time alerts
        if metrics.api_response_time:
            if metrics.api_response_time >= self.thresholds.api_response_critical:
                alerts.append(f"CRITICAL: API response time {metrics.api_response_time:.1f}ms")
            elif metrics.api_response_time >= self.thresholds.api_response_warning:
                alerts.append(f"WARNING: API response time {metrics.api_response_time:.1f}ms")
        
        # Database query time alerts
        if metrics.db_query_time:
            if metrics.db_query_time >= self.thresholds.db_query_critical:
                alerts.append(f"CRITICAL: DB query time {metrics.db_query_time:.1f}ms")
            elif metrics.db_query_time >= self.thresholds.db_query_warning:
                alerts.append(f"WARNING: DB query time {metrics.db_query_time:.1f}ms")
        
        # Video processing queue alerts
        if metrics.video_processing_queue > 10:
            alerts.append(f"WARNING: {metrics.video_processing_queue} videos in processing queue")
        
        return alerts

    def save_metrics(self, metrics: PerformanceMetrics):
        """Save metrics to file"""
        try:
            # Load existing metrics
            try:
                with open(self.output_file, 'r') as f:
                    all_metrics = json.load(f)
            except FileNotFoundError:
                all_metrics = []
            
            # Add new metrics
            all_metrics.append(asdict(metrics))
            
            # Keep only last 1000 entries
            if len(all_metrics) > 1000:
                all_metrics = all_metrics[-1000:]
            
            # Save updated metrics
            with open(self.output_file, 'w') as f:
                json.dump(all_metrics, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving metrics: {e}")

    async def monitor_once(self) -> PerformanceMetrics:
        """Perform one monitoring cycle"""
        logger.info("Collecting performance metrics...")
        
        metrics = await self.collect_all_metrics()
        alerts = self.check_thresholds(metrics)
        
        # Log metrics
        logger.info(f"CPU: {metrics.cpu_usage:.1f}%, "
                   f"Memory: {metrics.memory_usage:.1f}%, "
                   f"API: {metrics.api_response_time:.1f}ms, "
                   f"DB: {metrics.db_query_time:.1f}ms")
        
        # Log alerts
        for alert in alerts:
            logger.warning(alert)
        
        # Save metrics
        self.save_metrics(metrics)
        self.metrics_history.append(metrics)
        
        return metrics

    async def monitor_continuous(self, interval: int = 60, duration: int = 3600):
        """Monitor continuously for specified duration"""
        logger.info(f"Starting continuous monitoring for {duration} seconds "
                   f"with {interval}s intervals")
        
        start_time = time.time()
        
        while time.time() - start_time < duration:
            await self.monitor_once()
            await asyncio.sleep(interval)
        
        logger.info("Monitoring completed")

    def generate_report(self) -> Dict:
        """Generate performance summary report"""
        if not self.metrics_history:
            return {"error": "No metrics collected"}
        
        # Calculate averages
        cpu_avg = sum(m.cpu_usage for m in self.metrics_history) / len(self.metrics_history)
        memory_avg = sum(m.memory_usage for m in self.metrics_history) / len(self.metrics_history)
        
        api_times = [m.api_response_time for m in self.metrics_history if m.api_response_time]
        api_avg = sum(api_times) / len(api_times) if api_times else 0
        
        db_times = [m.db_query_time for m in self.metrics_history if m.db_query_time]
        db_avg = sum(db_times) / len(db_times) if db_times else 0
        
        latest = self.metrics_history[-1]
        
        return {
            "monitoring_period": {
                "start_time": self.metrics_history[0].timestamp,
                "end_time": latest.timestamp,
                "total_samples": len(self.metrics_history)
            },
            "averages": {
                "cpu_usage": round(cpu_avg, 2),
                "memory_usage": round(memory_avg, 2),
                "api_response_time": round(api_avg, 2),
                "db_query_time": round(db_avg, 2)
            },
            "current_status": {
                "database_size_mb": latest.database_size_mb,
                "video_processing_queue": latest.video_processing_queue,
                "active_connections": latest.active_connections
            },
            "recommendations": self.generate_recommendations()
        }

    def generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations based on metrics"""
        recommendations = []
        
        if not self.metrics_history:
            return recommendations
        
        latest = self.metrics_history[-1]
        
        # CPU recommendations
        if latest.cpu_usage > 70:
            recommendations.append("Consider scaling horizontally or upgrading CPU")
        
        # Memory recommendations
        if latest.memory_usage > 80:
            recommendations.append("Memory usage is high - check for memory leaks")
        
        # API performance recommendations
        if latest.api_response_time and latest.api_response_time > 500:
            recommendations.append("API response time is high - implement caching")
        
        # Database recommendations
        if latest.db_query_time and latest.db_query_time > 100:
            recommendations.append("Database queries are slow - add indexes")
        
        # Video processing recommendations
        if latest.video_processing_queue > 5:
            recommendations.append("Video processing queue is building up - increase workers")
        
        # Database size recommendations
        if latest.database_size_mb > 1000:  # 1GB
            recommendations.append("Database is growing large - implement archival strategy")
        
        return recommendations

async def main():
    parser = argparse.ArgumentParser(description='Performance Monitor for AI Model Validation Platform')
    parser.add_argument('--api-url', default='http://localhost:8001', help='API base URL')
    parser.add_argument('--db-path', default='./test_database.db', help='Database file path')
    parser.add_argument('--output', default='performance_metrics.json', help='Output file')
    parser.add_argument('--interval', type=int, default=60, help='Monitoring interval in seconds')
    parser.add_argument('--duration', type=int, default=3600, help='Monitoring duration in seconds')
    parser.add_argument('--mode', choices=['once', 'continuous', 'report'], default='once', 
                       help='Monitoring mode')
    
    args = parser.parse_args()
    
    monitor = PerformanceMonitor(
        api_base_url=args.api_url,
        db_path=args.db_path,
        output_file=args.output
    )
    
    if args.mode == 'once':
        await monitor.monitor_once()
    elif args.mode == 'continuous':
        await monitor.monitor_continuous(args.interval, args.duration)
    elif args.mode == 'report':
        # Load existing metrics and generate report
        try:
            with open(args.output, 'r') as f:
                metrics_data = json.load(f)
                monitor.metrics_history = [
                    PerformanceMetrics(**data) for data in metrics_data
                ]
        except FileNotFoundError:
            logger.warning("No existing metrics file found")
        
        report = monitor.generate_report()
        print(json.dumps(report, indent=2))

if __name__ == "__main__":
    asyncio.run(main())