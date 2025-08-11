#!/usr/bin/env python3
"""
Performance Monitoring Setup Script
Configures comprehensive performance monitoring for the AI Model Validation Platform
"""

import json
import os
from typing import Dict, List, Any
import yaml

class PerformanceMonitoringSetup:
    """Setup comprehensive performance monitoring stack"""
    
    def __init__(self):
        self.config = {
            "monitoring": {
                "prometheus": {
                    "enabled": True,
                    "port": 9090,
                    "scrape_interval": "15s"
                },
                "grafana": {
                    "enabled": True,
                    "port": 3000,
                    "admin_password": "performance_admin"
                },
                "alertmanager": {
                    "enabled": True,
                    "port": 9093
                }
            }
        }
    
    def generate_prometheus_config(self) -> str:
        """Generate Prometheus configuration"""
        config = {
            "global": {
                "scrape_interval": "15s",
                "evaluation_interval": "15s"
            },
            "alerting": {
                "alertmanagers": [
                    {
                        "static_configs": [
                            {"targets": ["alertmanager:9093"]}
                        ]
                    }
                ]
            },
            "rule_files": [
                "alert_rules.yml"
            ],
            "scrape_configs": [
                {
                    "job_name": "api-server",
                    "static_configs": [
                        {"targets": ["api:8001"]}
                    ],
                    "metrics_path": "/metrics",
                    "scrape_interval": "5s"
                },
                {
                    "job_name": "frontend-vitals",
                    "static_configs": [
                        {"targets": ["frontend:3000"]}
                    ],
                    "metrics_path": "/api/metrics/vitals"
                },
                {
                    "job_name": "database",
                    "static_configs": [
                        {"targets": ["postgres-exporter:9187"]}
                    ]
                },
                {
                    "job_name": "system-metrics",
                    "static_configs": [
                        {"targets": ["node-exporter:9100"]}
                    ]
                }
            ]
        }
        return yaml.dump(config, default_flow_style=False)
    
    def generate_alert_rules(self) -> str:
        """Generate Prometheus alerting rules"""
        rules = {
            "groups": [
                {
                    "name": "api_performance_alerts",
                    "rules": [
                        {
                            "alert": "HighAPILatency",
                            "expr": "http_request_duration_seconds{quantile=\"0.95\"} > 1.0",
                            "for": "2m",
                            "labels": {"severity": "warning"},
                            "annotations": {
                                "summary": "API latency is high",
                                "description": "95th percentile latency is {{ $value }}s for {{ $labels.endpoint }}"
                            }
                        },
                        {
                            "alert": "HighErrorRate",
                            "expr": "rate(http_requests_total{status=~\"5..\"}[5m]) > 0.05",
                            "for": "1m",
                            "labels": {"severity": "critical"},
                            "annotations": {
                                "summary": "High error rate detected",
                                "description": "Error rate is {{ $value }} errors per second"
                            }
                        },
                        {
                            "alert": "APIDowntime",
                            "expr": "up{job=\"api-server\"} == 0",
                            "for": "30s",
                            "labels": {"severity": "critical"},
                            "annotations": {
                                "summary": "API server is down",
                                "description": "API server has been down for more than 30 seconds"
                            }
                        }
                    ]
                },
                {
                    "name": "database_performance_alerts",
                    "rules": [
                        {
                            "alert": "DatabaseConnectionsHigh",
                            "expr": "postgresql_connections_active / postgresql_connections_max > 0.8",
                            "for": "5m",
                            "labels": {"severity": "warning"},
                            "annotations": {
                                "summary": "Database connection pool nearly exhausted",
                                "description": "{{ $value }}% of database connections are in use"
                            }
                        },
                        {
                            "alert": "SlowDatabaseQueries",
                            "expr": "postgresql_slow_queries_total > 10",
                            "for": "2m",
                            "labels": {"severity": "warning"},
                            "annotations": {
                                "summary": "Multiple slow database queries detected",
                                "description": "{{ $value }} slow queries detected in the last 5 minutes"
                            }
                        }
                    ]
                },
                {
                    "name": "frontend_performance_alerts",
                    "rules": [
                        {
                            "alert": "HighPageLoadTime",
                            "expr": "web_vitals_lcp > 2500",
                            "for": "5m",
                            "labels": {"severity": "warning"},
                            "annotations": {
                                "summary": "Page load time is high",
                                "description": "Largest Contentful Paint is {{ $value }}ms"
                            }
                        },
                        {
                            "alert": "PoorUserExperience",
                            "expr": "web_vitals_cls > 0.25",
                            "for": "5m",
                            "labels": {"severity": "warning"},
                            "annotations": {
                                "summary": "Poor user experience detected",
                                "description": "Cumulative Layout Shift score is {{ $value }}"
                            }
                        }
                    ]
                },
                {
                    "name": "system_performance_alerts",
                    "rules": [
                        {
                            "alert": "HighCPUUsage",
                            "expr": "100 - (avg by (instance) (rate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100) > 80",
                            "for": "5m",
                            "labels": {"severity": "warning"},
                            "annotations": {
                                "summary": "High CPU usage detected",
                                "description": "CPU usage is {{ $value }}% on {{ $labels.instance }}"
                            }
                        },
                        {
                            "alert": "HighMemoryUsage",
                            "expr": "(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes > 0.9",
                            "for": "5m",
                            "labels": {"severity": "critical"},
                            "annotations": {
                                "summary": "High memory usage detected",
                                "description": "Memory usage is {{ $value }}% on {{ $labels.instance }}"
                            }
                        },
                        {
                            "alert": "DiskSpaceLow",
                            "expr": "(node_filesystem_avail_bytes / node_filesystem_size_bytes) * 100 < 10",
                            "for": "5m",
                            "labels": {"severity": "warning"},
                            "annotations": {
                                "summary": "Disk space is low",
                                "description": "Only {{ $value }}% disk space remaining on {{ $labels.instance }}"
                            }
                        }
                    ]
                }
            ]
        }
        return yaml.dump(rules, default_flow_style=False)
    
    def generate_alertmanager_config(self) -> str:
        """Generate Alertmanager configuration"""
        config = {
            "global": {
                "smtp_smarthost": "localhost:587",
                "smtp_from": "alerts@aivalidation.com"
            },
            "route": {
                "group_by": ["alertname"],
                "group_wait": "10s",
                "group_interval": "10s",
                "repeat_interval": "1h",
                "receiver": "web.hook"
            },
            "receivers": [
                {
                    "name": "web.hook",
                    "email_configs": [
                        {
                            "to": "performance-team@aivalidation.com",
                            "subject": "Performance Alert: {{ range .Alerts }}{{ .Annotations.summary }}{{ end }}",
                            "body": "{{ range .Alerts }}{{ .Annotations.description }}{{ end }}"
                        }
                    ],
                    "webhook_configs": [
                        {
                            "url": "http://api:8001/api/alerts/webhook",
                            "send_resolved": True
                        }
                    ]
                }
            ]
        }
        return yaml.dump(config, default_flow_style=False)
    
    def generate_docker_compose_monitoring(self) -> str:
        """Generate Docker Compose configuration for monitoring stack"""
        compose = {
            "version": "3.8",
            "services": {
                "prometheus": {
                    "image": "prom/prometheus:latest",
                    "container_name": "prometheus",
                    "ports": ["9090:9090"],
                    "volumes": [
                        "./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml",
                        "./monitoring/alert_rules.yml:/etc/prometheus/alert_rules.yml",
                        "prometheus_data:/prometheus"
                    ],
                    "command": [
                        "--config.file=/etc/prometheus/prometheus.yml",
                        "--storage.tsdb.path=/prometheus",
                        "--web.console.libraries=/etc/prometheus/console_libraries",
                        "--web.console.templates=/etc/prometheus/consoles",
                        "--storage.tsdb.retention.time=200h",
                        "--web.enable-lifecycle",
                        "--web.enable-admin-api"
                    ],
                    "restart": "unless-stopped"
                },
                "grafana": {
                    "image": "grafana/grafana:latest",
                    "container_name": "grafana",
                    "ports": ["3000:3000"],
                    "environment": [
                        "GF_SECURITY_ADMIN_USER=admin",
                        "GF_SECURITY_ADMIN_PASSWORD=performance_admin",
                        "GF_INSTALL_PLUGINS=grafana-piechart-panel"
                    ],
                    "volumes": [
                        "grafana_data:/var/lib/grafana",
                        "./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards",
                        "./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources"
                    ],
                    "restart": "unless-stopped"
                },
                "alertmanager": {
                    "image": "prom/alertmanager:latest",
                    "container_name": "alertmanager",
                    "ports": ["9093:9093"],
                    "volumes": [
                        "./monitoring/alertmanager.yml:/etc/alertmanager/alertmanager.yml",
                        "alertmanager_data:/alertmanager"
                    ],
                    "command": [
                        "--config.file=/etc/alertmanager/alertmanager.yml",
                        "--storage.path=/alertmanager",
                        "--web.external-url=http://localhost:9093"
                    ],
                    "restart": "unless-stopped"
                },
                "node-exporter": {
                    "image": "prom/node-exporter:latest",
                    "container_name": "node-exporter",
                    "ports": ["9100:9100"],
                    "volumes": [
                        "/proc:/host/proc:ro",
                        "/sys:/host/sys:ro",
                        "/:/rootfs:ro"
                    ],
                    "command": [
                        "--path.procfs=/host/proc",
                        "--path.rootfs=/rootfs",
                        "--path.sysfs=/host/sys",
                        "--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)"
                    ],
                    "restart": "unless-stopped"
                },
                "postgres-exporter": {
                    "image": "prometheuscommunity/postgres-exporter:latest",
                    "container_name": "postgres-exporter",
                    "ports": ["9187:9187"],
                    "environment": [
                        "DATA_SOURCE_NAME=postgresql://username:password@postgres:5432/database?sslmode=disable"
                    ],
                    "restart": "unless-stopped"
                }
            },
            "volumes": {
                "prometheus_data": {},
                "grafana_data": {},
                "alertmanager_data": {}
            }
        }
        return yaml.dump(compose, default_flow_style=False)
    
    def generate_grafana_dashboards(self) -> Dict[str, Dict]:
        """Generate Grafana dashboard configurations"""
        dashboards = {
            "api_performance": {
                "dashboard": {
                    "id": None,
                    "title": "API Performance Dashboard",
                    "panels": [
                        {
                            "title": "API Response Time",
                            "type": "graph",
                            "targets": [
                                {
                                    "expr": "http_request_duration_seconds{quantile=\"0.95\"}",
                                    "legendFormat": "95th percentile"
                                },
                                {
                                    "expr": "http_request_duration_seconds{quantile=\"0.50\"}",
                                    "legendFormat": "50th percentile"
                                }
                            ]
                        },
                        {
                            "title": "Request Rate",
                            "type": "graph",
                            "targets": [
                                {
                                    "expr": "rate(http_requests_total[5m])",
                                    "legendFormat": "Requests per second"
                                }
                            ]
                        },
                        {
                            "title": "Error Rate",
                            "type": "graph",
                            "targets": [
                                {
                                    "expr": "rate(http_requests_total{status=~\"4..|5..\"}[5m])",
                                    "legendFormat": "Error rate"
                                }
                            ]
                        }
                    ]
                }
            },
            "database_performance": {
                "dashboard": {
                    "id": None,
                    "title": "Database Performance Dashboard",
                    "panels": [
                        {
                            "title": "Database Connections",
                            "type": "graph",
                            "targets": [
                                {
                                    "expr": "postgresql_connections_active",
                                    "legendFormat": "Active connections"
                                },
                                {
                                    "expr": "postgresql_connections_max",
                                    "legendFormat": "Max connections"
                                }
                            ]
                        },
                        {
                            "title": "Query Performance",
                            "type": "graph",
                            "targets": [
                                {
                                    "expr": "postgresql_query_duration_seconds",
                                    "legendFormat": "Query duration"
                                }
                            ]
                        }
                    ]
                }
            },
            "system_performance": {
                "dashboard": {
                    "id": None,
                    "title": "System Performance Dashboard",
                    "panels": [
                        {
                            "title": "CPU Usage",
                            "type": "graph",
                            "targets": [
                                {
                                    "expr": "100 - (avg(rate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
                                    "legendFormat": "CPU usage %"
                                }
                            ]
                        },
                        {
                            "title": "Memory Usage",
                            "type": "graph",
                            "targets": [
                                {
                                    "expr": "(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100",
                                    "legendFormat": "Memory usage %"
                                }
                            ]
                        },
                        {
                            "title": "Disk Usage",
                            "type": "graph",
                            "targets": [
                                {
                                    "expr": "(node_filesystem_size_bytes - node_filesystem_avail_bytes) / node_filesystem_size_bytes * 100",
                                    "legendFormat": "Disk usage %"
                                }
                            ]
                        }
                    ]
                }
            }
        }
        return dashboards
    
    def generate_api_monitoring_middleware(self) -> str:
        """Generate FastAPI monitoring middleware code"""
        code = '''
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
'''
        return code
    
    def generate_frontend_monitoring_code(self) -> str:
        """Generate frontend performance monitoring code"""
        code = '''
// Frontend performance monitoring (React)
import { getCLS, getFID, getFCP, getLCP, getTTFB } from 'web-vitals';

class PerformanceMonitor {
  constructor() {
    this.metrics = [];
    this.setupWebVitalsTracking();
    this.setupCustomMetrics();
  }

  setupWebVitalsTracking() {
    const sendMetric = (metric) => {
      this.metrics.push({
        name: metric.name,
        value: metric.value,
        timestamp: Date.now(),
        id: metric.id
      });
      
      // Send to backend
      this.sendToBackend(metric);
    };

    getCLS(sendMetric);
    getFID(sendMetric);
    getFCP(sendMetric);
    getLCP(sendMetric);
    getTTFB(sendMetric);
  }

  setupCustomMetrics() {
    // Track component render times
    this.trackComponentPerformance();
    
    // Track API call times
    this.trackAPIPerformance();
    
    // Track resource loading
    this.trackResourceLoading();
  }

  trackComponentPerformance() {
    // React DevTools Profiler API
    const measureRender = (id, phase, actualDuration) => {
      if (actualDuration > 16) { // > 1 frame at 60fps
        this.sendMetric({
          name: 'component_render_time',
          value: actualDuration,
          metadata: { component: id, phase }
        });
      }
    };

    // Wrap components with Profiler
    return measureRender;
  }

  trackAPIPerformance() {
    const originalFetch = window.fetch;
    
    window.fetch = async (...args) => {
      const start = performance.now();
      
      try {
        const response = await originalFetch(...args);
        const duration = performance.now() - start;
        
        this.sendMetric({
          name: 'api_request_duration',
          value: duration,
          metadata: {
            url: args[0],
            status: response.status,
            method: args[1]?.method || 'GET'
          }
        });
        
        return response;
      } catch (error) {
        const duration = performance.now() - start;
        
        this.sendMetric({
          name: 'api_request_error',
          value: duration,
          metadata: {
            url: args[0],
            error: error.message
          }
        });
        
        throw error;
      }
    };
  }

  trackResourceLoading() {
    // Monitor resource loading performance
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.duration > 1000) { // Slow resource
          this.sendMetric({
            name: 'resource_loading_time',
            value: entry.duration,
            metadata: {
              resource: entry.name,
              type: entry.initiatorType
            }
          });
        }
      }
    });
    
    observer.observe({ entryTypes: ['resource'] });
  }

  sendMetric(metric) {
    // Send to monitoring endpoint
    fetch('/api/metrics/frontend', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        ...metric,
        timestamp: Date.now(),
        userAgent: navigator.userAgent,
        viewport: {
          width: window.innerWidth,
          height: window.innerHeight
        }
      })
    }).catch(console.error);
  }

  sendToBackend(metric) {
    // Send web vitals to backend
    this.sendMetric({
      name: `web_vitals_${metric.name.toLowerCase()}`,
      value: metric.value,
      metadata: {
        id: metric.id,
        rating: this.getRating(metric.name, metric.value)
      }
    });
  }

  getRating(name, value) {
    const thresholds = {
      CLS: [0.1, 0.25],
      FID: [100, 300],
      FCP: [1800, 3000],
      LCP: [2500, 4000],
      TTFB: [800, 1800]
    };
    
    const [good, poor] = thresholds[name] || [0, 0];
    
    if (value <= good) return 'good';
    if (value <= poor) return 'needs-improvement';
    return 'poor';
  }
}

// Initialize performance monitoring
const performanceMonitor = new PerformanceMonitor();
export default performanceMonitor;
'''
        return code
    
    def create_monitoring_files(self, output_dir: str = "./monitoring"):
        """Create all monitoring configuration files"""
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(f"{output_dir}/grafana/dashboards", exist_ok=True)
        os.makedirs(f"{output_dir}/grafana/datasources", exist_ok=True)
        
        # Prometheus configuration
        with open(f"{output_dir}/prometheus.yml", "w") as f:
            f.write(self.generate_prometheus_config())
        
        # Alert rules
        with open(f"{output_dir}/alert_rules.yml", "w") as f:
            f.write(self.generate_alert_rules())
        
        # Alertmanager configuration
        with open(f"{output_dir}/alertmanager.yml", "w") as f:
            f.write(self.generate_alertmanager_config())
        
        # Docker Compose for monitoring stack
        with open(f"{output_dir}/docker-compose.monitoring.yml", "w") as f:
            f.write(self.generate_docker_compose_monitoring())
        
        # Grafana dashboards
        dashboards = self.generate_grafana_dashboards()
        for name, dashboard in dashboards.items():
            with open(f"{output_dir}/grafana/dashboards/{name}.json", "w") as f:
                json.dump(dashboard, f, indent=2)
        
        # Grafana datasource configuration
        datasource_config = {
            "apiVersion": 1,
            "datasources": [
                {
                    "name": "Prometheus",
                    "type": "prometheus",
                    "url": "http://prometheus:9090",
                    "access": "proxy",
                    "isDefault": True
                }
            ]
        }
        with open(f"{output_dir}/grafana/datasources/prometheus.yml", "w") as f:
            yaml.dump(datasource_config, f)
        
        # API monitoring middleware
        with open(f"{output_dir}/api_monitoring.py", "w") as f:
            f.write(self.generate_api_monitoring_middleware())
        
        # Frontend monitoring code
        with open(f"{output_dir}/frontend_monitoring.js", "w") as f:
            f.write(self.generate_frontend_monitoring_code())
        
        print(f"Monitoring configuration files created in {output_dir}/")
        print("\nTo start the monitoring stack:")
        print(f"cd {output_dir}")
        print("docker-compose -f docker-compose.monitoring.yml up -d")
        print("\nAccess points:")
        print("- Prometheus: http://localhost:9090")
        print("- Grafana: http://localhost:3000 (admin/performance_admin)")
        print("- Alertmanager: http://localhost:9093")

def main():
    """Generate performance monitoring setup"""
    setup = PerformanceMonitoringSetup()
    setup.create_monitoring_files("/workspaces/Testing/monitoring")
    
    print("✅ Performance monitoring setup completed!")
    print("\nNext steps:")
    print("1. Review and customize the generated configurations")
    print("2. Start the monitoring stack with Docker Compose")
    print("3. Add the PrometheusMiddleware to your FastAPI app")
    print("4. Integrate frontend monitoring in your React app")
    print("5. Configure alert notification channels")

if __name__ == "__main__":
    main()