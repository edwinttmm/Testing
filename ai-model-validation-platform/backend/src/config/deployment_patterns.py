"""
Deployment Configuration Patterns
Provides standard deployment patterns and configurations for different environments.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import yaml
import json

from src.utils.path_manager import PathType, DeploymentContext
from src.config.path_config import PathConfiguration

logger = logging.getLogger(__name__)


@dataclass
class DeploymentPattern:
    """Standard deployment configuration pattern"""
    name: str
    description: str
    context: DeploymentContext
    environment_variables: Dict[str, str]
    path_configurations: Dict[PathType, PathConfiguration]
    volume_mappings: Dict[str, str]
    security_settings: Dict[str, Any]
    performance_settings: Dict[str, Any]
    monitoring_settings: Dict[str, Any]
    metadata: Dict[str, Any]


class StandardDeploymentPatterns:
    """Collection of standard deployment patterns"""
    
    @staticmethod
    def get_docker_compose_development() -> DeploymentPattern:
        """Development pattern using Docker Compose"""
        return DeploymentPattern(
            name="docker-compose-development",
            description="Development setup using Docker Compose with local volumes",
            context=DeploymentContext.DEVELOPMENT,
            environment_variables={
                "AI_VALIDATION_APP_ENVIRONMENT": "development",
                "AI_VALIDATION_DATABASE_URL": "postgresql://user:password@postgres:5432/ai_validation_dev",
                "AI_VALIDATION_REDIS_URL": "redis://redis:6379/0",
                "AI_VALIDATION_API_HOST": "0.0.0.0",
                "AI_VALIDATION_API_PORT": "8000",
                "AI_VALIDATION_CORS_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000",
                "AI_VALIDATION_LOG_LEVEL": "DEBUG"
            },
            path_configurations={
                PathType.UPLOAD: PathConfiguration(
                    path_type=PathType.UPLOAD,
                    base_directory="/app/uploads",
                    absolute_base_path="/app/uploads",
                    max_size_mb=1000,
                    allowed_extensions=['.mp4', '.avi', '.mov', '.mkv', '.webm']
                ),
                PathType.SCREENSHOT: PathConfiguration(
                    path_type=PathType.SCREENSHOT,
                    base_directory="/app/screenshots",
                    absolute_base_path="/app/screenshots",
                    max_size_mb=500,
                    allowed_extensions=['.jpg', '.jpeg', '.png']
                )
            },
            volume_mappings={
                "./uploads": "/app/uploads",
                "./screenshots": "/app/screenshots",
                "./videos": "/app/videos",
                "./reports": "/app/reports",
                "./logs": "/app/logs"
            },
            security_settings={
                "enable_cors": True,
                "enable_ssl": False,
                "enable_authentication": False,
                "debug_mode": True
            },
            performance_settings={
                "worker_processes": 1,
                "max_connections": 100,
                "timeout_seconds": 30
            },
            monitoring_settings={
                "health_checks": True,
                "metrics": False,
                "logging_level": "DEBUG"
            },
            metadata={
                "suitable_for": ["local development", "testing", "debugging"],
                "docker_compose_version": "3.8",
                "requires_gpu": False
            }
        )
    
    @staticmethod
    def get_docker_compose_production() -> DeploymentPattern:
        """Production pattern using Docker Compose"""
        return DeploymentPattern(
            name="docker-compose-production",
            description="Production setup using Docker Compose with named volumes",
            context=DeploymentContext.PRODUCTION,
            environment_variables={
                "AI_VALIDATION_APP_ENVIRONMENT": "production",
                "AI_VALIDATION_DATABASE_URL": "${DATABASE_URL}",
                "AI_VALIDATION_REDIS_URL": "${REDIS_URL}",
                "AI_VALIDATION_SECRET_KEY": "${SECRET_KEY}",
                "AI_VALIDATION_JWT_SECRET_KEY": "${JWT_SECRET_KEY}",
                "AI_VALIDATION_API_HOST": "0.0.0.0",
                "AI_VALIDATION_API_PORT": "8000",
                "AI_VALIDATION_CORS_ORIGINS": "${FRONTEND_URLS}",
                "AI_VALIDATION_LOG_LEVEL": "INFO",
                "AI_VALIDATION_SSL_ENABLED": "true"
            },
            path_configurations={
                PathType.UPLOAD: PathConfiguration(
                    path_type=PathType.UPLOAD,
                    base_directory="/app/uploads",
                    absolute_base_path="/app/uploads",
                    permissions=0o750,
                    max_size_mb=10000,
                    allowed_extensions=['.mp4', '.avi', '.mov', '.mkv', '.webm']
                ),
                PathType.SCREENSHOT: PathConfiguration(
                    path_type=PathType.SCREENSHOT,
                    base_directory="/app/screenshots",
                    absolute_base_path="/app/screenshots",
                    permissions=0o750,
                    max_size_mb=5000,
                    allowed_extensions=['.jpg', '.jpeg', '.png'],
                    cleanup_policy={'max_age_days': 30}
                )
            },
            volume_mappings={
                "ai_validation_uploads": "/app/uploads",
                "ai_validation_screenshots": "/app/screenshots",
                "ai_validation_videos": "/app/videos",
                "ai_validation_reports": "/app/reports",
                "ai_validation_logs": "/app/logs"
            },
            security_settings={
                "enable_cors": True,
                "enable_ssl": True,
                "enable_authentication": True,
                "debug_mode": False,
                "security_headers": True,
                "rate_limiting": True
            },
            performance_settings={
                "worker_processes": 4,
                "max_connections": 1000,
                "timeout_seconds": 60,
                "enable_caching": True
            },
            monitoring_settings={
                "health_checks": True,
                "metrics": True,
                "logging_level": "INFO",
                "log_retention_days": 30
            },
            metadata={
                "suitable_for": ["production deployment", "staging environment"],
                "docker_compose_version": "3.8",
                "requires_gpu": True,
                "backup_strategy": "automated_daily"
            }
        )
    
    @staticmethod
    def get_kubernetes_production() -> DeploymentPattern:
        """Production pattern for Kubernetes deployment"""
        return DeploymentPattern(
            name="kubernetes-production",
            description="Production Kubernetes deployment with persistent volumes",
            context=DeploymentContext.PRODUCTION,
            environment_variables={
                "AI_VALIDATION_APP_ENVIRONMENT": "production",
                "AI_VALIDATION_DATABASE_URL": "postgresql://$(DB_USER):$(DB_PASSWORD)@postgres-service:5432/$(DB_NAME)",
                "AI_VALIDATION_REDIS_URL": "redis://redis-service:6379/0",
                "AI_VALIDATION_SECRET_KEY": "$(SECRET_KEY)",
                "AI_VALIDATION_JWT_SECRET_KEY": "$(JWT_SECRET_KEY)",
                "AI_VALIDATION_API_HOST": "0.0.0.0",
                "AI_VALIDATION_API_PORT": "8000",
                "AI_VALIDATION_LOG_LEVEL": "INFO"
            },
            path_configurations={
                PathType.UPLOAD: PathConfiguration(
                    path_type=PathType.UPLOAD,
                    base_directory="/app/uploads",
                    absolute_base_path="/app/uploads",
                    permissions=0o750,
                    max_size_mb=20000,
                    allowed_extensions=['.mp4', '.avi', '.mov', '.mkv', '.webm']
                ),
                PathType.SCREENSHOT: PathConfiguration(
                    path_type=PathType.SCREENSHOT,
                    base_directory="/app/screenshots",
                    absolute_base_path="/app/screenshots",
                    permissions=0o750,
                    max_size_mb=10000,
                    allowed_extensions=['.jpg', '.jpeg', '.png'],
                    cleanup_policy={'max_age_days': 30}
                )
            },
            volume_mappings={
                "ai-validation-uploads-pvc": "/app/uploads",
                "ai-validation-screenshots-pvc": "/app/screenshots",
                "ai-validation-videos-pvc": "/app/videos",
                "ai-validation-reports-pvc": "/app/reports"
            },
            security_settings={
                "enable_cors": True,
                "enable_ssl": True,
                "enable_authentication": True,
                "debug_mode": False,
                "pod_security_policy": True,
                "network_policies": True,
                "service_mesh": True
            },
            performance_settings={
                "replicas": 3,
                "cpu_request": "500m",
                "memory_request": "1Gi",
                "cpu_limit": "2000m",
                "memory_limit": "4Gi",
                "horizontal_pod_autoscaler": True
            },
            monitoring_settings={
                "prometheus_metrics": True,
                "grafana_dashboards": True,
                "alertmanager": True,
                "jaeger_tracing": True,
                "logging_level": "INFO"
            },
            metadata={
                "suitable_for": ["enterprise production", "high availability"],
                "kubernetes_version": ">=1.20",
                "requires_gpu": True,
                "backup_strategy": "automated_hourly",
                "disaster_recovery": True
            }
        )
    
    @staticmethod
    def get_single_container_deployment() -> DeploymentPattern:
        """Simple single container deployment pattern"""
        return DeploymentPattern(
            name="single-container",
            description="Simple single container deployment for small deployments",
            context=DeploymentContext.CONTAINER,
            environment_variables={
                "AI_VALIDATION_APP_ENVIRONMENT": "production",
                "AI_VALIDATION_DATABASE_URL": "sqlite:////app/data/database.db",
                "AI_VALIDATION_API_HOST": "0.0.0.0",
                "AI_VALIDATION_API_PORT": "8000",
                "AI_VALIDATION_LOG_LEVEL": "INFO"
            },
            path_configurations={
                PathType.UPLOAD: PathConfiguration(
                    path_type=PathType.UPLOAD,
                    base_directory="/app/uploads",
                    absolute_base_path="/app/uploads",
                    max_size_mb=2000,
                    allowed_extensions=['.mp4', '.avi', '.mov', '.mkv', '.webm']
                ),
                PathType.SCREENSHOT: PathConfiguration(
                    path_type=PathType.SCREENSHOT,
                    base_directory="/app/screenshots",
                    absolute_base_path="/app/screenshots",
                    max_size_mb=1000,
                    allowed_extensions=['.jpg', '.jpeg', '.png']
                )
            },
            volume_mappings={
                "/host/ai-validation/data": "/app/data",
                "/host/ai-validation/uploads": "/app/uploads",
                "/host/ai-validation/screenshots": "/app/screenshots"
            },
            security_settings={
                "enable_cors": True,
                "enable_ssl": False,
                "enable_authentication": True,
                "debug_mode": False
            },
            performance_settings={
                "worker_processes": 1,
                "max_connections": 100,
                "timeout_seconds": 30
            },
            monitoring_settings={
                "health_checks": True,
                "metrics": False,
                "logging_level": "INFO"
            },
            metadata={
                "suitable_for": ["small deployments", "single server", "edge computing"],
                "requires_gpu": False,
                "lightweight": True
            }
        )


class DeploymentConfigGenerator:
    """Generates deployment configurations based on patterns"""
    
    def __init__(self):
        self.patterns = {
            "docker-compose-development": StandardDeploymentPatterns.get_docker_compose_development(),
            "docker-compose-production": StandardDeploymentPatterns.get_docker_compose_production(),
            "kubernetes-production": StandardDeploymentPatterns.get_kubernetes_production(),
            "single-container": StandardDeploymentPatterns.get_single_container_deployment()
        }
    
    def generate_docker_compose(self, pattern_name: str, output_path: Optional[str] = None) -> str:
        """Generate Docker Compose configuration"""
        if pattern_name not in self.patterns:
            raise ValueError(f"Unknown pattern: {pattern_name}")
        
        pattern = self.patterns[pattern_name]
        
        # Build Docker Compose configuration
        compose_config = {
            "version": pattern.metadata.get("docker_compose_version", "3.8"),
            "services": {
                "ai-validation-backend": {
                    "build": ".",
                    "ports": [f"{pattern.environment_variables['AI_VALIDATION_API_PORT']}:{pattern.environment_variables['AI_VALIDATION_API_PORT']}"],
                    "environment": pattern.environment_variables,
                    "volumes": [f"{host}:{container}" for host, container in pattern.volume_mappings.items()],
                    "restart": "unless-stopped",
                    "healthcheck": {
                        "test": ["CMD", "curl", "-f", f"http://localhost:{pattern.environment_variables['AI_VALIDATION_API_PORT']}/health"],
                        "interval": "30s",
                        "timeout": "10s",
                        "retries": 3
                    }
                }
            }
        }
        
        # Add database service for development
        if pattern.context == DeploymentContext.DEVELOPMENT:
            if "postgresql" in pattern.environment_variables.get("AI_VALIDATION_DATABASE_URL", ""):
                compose_config["services"]["postgres"] = {
                    "image": "postgres:15",
                    "environment": {
                        "POSTGRES_DB": "ai_validation_dev",
                        "POSTGRES_USER": "user",
                        "POSTGRES_PASSWORD": "password"
                    },
                    "volumes": ["postgres_data:/var/lib/postgresql/data"],
                    "ports": ["5432:5432"]
                }
                compose_config["volumes"] = {"postgres_data": None}
            
            if "redis" in pattern.environment_variables.get("AI_VALIDATION_REDIS_URL", ""):
                compose_config["services"]["redis"] = {
                    "image": "redis:7-alpine",
                    "ports": ["6379:6379"]
                }
        
        # Add named volumes for production
        if pattern.context == DeploymentContext.PRODUCTION:
            volume_names = [vol for vol in pattern.volume_mappings.keys() if not vol.startswith("./")]
            if volume_names:
                compose_config["volumes"] = {vol: None for vol in volume_names}
        
        # Convert to YAML
        yaml_content = yaml.dump(compose_config, default_flow_style=False, sort_keys=False)
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(yaml_content)
        
        return yaml_content
    
    def generate_kubernetes_manifests(self, pattern_name: str, output_dir: Optional[str] = None) -> Dict[str, str]:
        """Generate Kubernetes manifests"""
        if pattern_name not in self.patterns:
            raise ValueError(f"Unknown pattern: {pattern_name}")
        
        pattern = self.patterns[pattern_name]
        manifests = {}
        
        # Deployment manifest
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "ai-validation-backend",
                "labels": {"app": "ai-validation-backend"}
            },
            "spec": {
                "replicas": pattern.performance_settings.get("replicas", 1),
                "selector": {"matchLabels": {"app": "ai-validation-backend"}},
                "template": {
                    "metadata": {"labels": {"app": "ai-validation-backend"}},
                    "spec": {
                        "containers": [{
                            "name": "ai-validation-backend",
                            "image": "ai-validation-backend:latest",
                            "ports": [{"containerPort": int(pattern.environment_variables["AI_VALIDATION_API_PORT"])}],
                            "env": [
                                {"name": k, "value": v} for k, v in pattern.environment_variables.items()
                            ],
                            "volumeMounts": [
                                {"name": vol.replace("-", "_"), "mountPath": path} 
                                for vol, path in pattern.volume_mappings.items()
                            ],
                            "resources": {
                                "requests": {
                                    "cpu": pattern.performance_settings.get("cpu_request", "100m"),
                                    "memory": pattern.performance_settings.get("memory_request", "256Mi")
                                },
                                "limits": {
                                    "cpu": pattern.performance_settings.get("cpu_limit", "500m"),
                                    "memory": pattern.performance_settings.get("memory_limit", "1Gi")
                                }
                            },
                            "livenessProbe": {
                                "httpGet": {"path": "/health", "port": int(pattern.environment_variables["AI_VALIDATION_API_PORT"])},
                                "initialDelaySeconds": 30,
                                "periodSeconds": 10
                            },
                            "readinessProbe": {
                                "httpGet": {"path": "/health", "port": int(pattern.environment_variables["AI_VALIDATION_API_PORT"])},
                                "initialDelaySeconds": 10,
                                "periodSeconds": 5
                            }
                        }],
                        "volumes": [
                            {"name": vol.replace("-", "_"), "persistentVolumeClaim": {"claimName": vol}}
                            for vol in pattern.volume_mappings.keys()
                        ]
                    }
                }
            }
        }
        
        manifests["deployment.yaml"] = yaml.dump(deployment, default_flow_style=False)
        
        # Service manifest
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "ai-validation-backend-service",
                "labels": {"app": "ai-validation-backend"}
            },
            "spec": {
                "selector": {"app": "ai-validation-backend"},
                "ports": [{
                    "port": 80,
                    "targetPort": int(pattern.environment_variables["AI_VALIDATION_API_PORT"]),
                    "protocol": "TCP"
                }],
                "type": "ClusterIP"
            }
        }
        
        manifests["service.yaml"] = yaml.dump(service, default_flow_style=False)
        
        # PVC manifests
        for vol_name in pattern.volume_mappings.keys():
            pvc = {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": {"name": vol_name},
                "spec": {
                    "accessModes": ["ReadWriteOnce"],
                    "resources": {"requests": {"storage": "10Gi"}},
                    "storageClassName": "standard"
                }
            }
            manifests[f"pvc-{vol_name}.yaml"] = yaml.dump(pvc, default_flow_style=False)
        
        # Save to files if output directory specified
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            for filename, content in manifests.items():
                with open(output_path / filename, 'w') as f:
                    f.write(content)
        
        return manifests
    
    def generate_environment_file(self, pattern_name: str, output_path: Optional[str] = None) -> str:
        """Generate environment file (.env)"""
        if pattern_name not in self.patterns:
            raise ValueError(f"Unknown pattern: {pattern_name}")
        
        pattern = self.patterns[pattern_name]
        
        env_lines = [
            f"# AI Model Validation Platform - {pattern.name}",
            f"# {pattern.description}",
            "",
        ]
        
        for key, value in pattern.environment_variables.items():
            env_lines.append(f"{key}={value}")
        
        env_content = "\n".join(env_lines)
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(env_content)
        
        return env_content
    
    def generate_documentation(self, pattern_name: str, output_path: Optional[str] = None) -> str:
        """Generate deployment documentation"""
        if pattern_name not in self.patterns:
            raise ValueError(f"Unknown pattern: {pattern_name}")
        
        pattern = self.patterns[pattern_name]
        
        doc_content = f"""# {pattern.name} Deployment Pattern

## Description
{pattern.description}

## Deployment Context
- **Context**: {pattern.context.value}
- **Suitable for**: {', '.join(pattern.metadata.get('suitable_for', []))}

## Environment Variables
```bash
{chr(10).join(f'{k}={v}' for k, v in pattern.environment_variables.items())}
```

## Volume Mappings
{chr(10).join(f'- `{host}` → `{container}`' for host, container in pattern.volume_mappings.items())}

## Path Configurations
{chr(10).join(f'- **{pt.value}**: `{pc.absolute_base_path}` (max {pc.max_size_mb}MB)' for pt, pc in pattern.path_configurations.items())}

## Security Settings
{chr(10).join(f'- **{k}**: {v}' for k, v in pattern.security_settings.items())}

## Performance Settings
{chr(10).join(f'- **{k}**: {v}' for k, v in pattern.performance_settings.items())}

## Monitoring Settings
{chr(10).join(f'- **{k}**: {v}' for k, v in pattern.monitoring_settings.items())}

## Additional Metadata
{chr(10).join(f'- **{k}**: {v}' for k, v in pattern.metadata.items())}

## Quick Start

1. **Generate configuration files**:
   ```bash
   python -m src.config.deployment_patterns generate {pattern_name}
   ```

2. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your specific values
   ```

3. **Deploy**:
   ```bash
   {"docker-compose up -d" if "docker-compose" in pattern_name else "kubectl apply -f manifests/"}
   ```

4. **Verify deployment**:
   ```bash
   {"curl http://localhost:8000/health" if "docker-compose" in pattern_name else "kubectl get pods"}
   ```

## Path Management

This deployment pattern uses the enhanced path management system that:
- Automatically resolves paths for the deployment context
- Handles containerized vs. host path mapping
- Provides robust error handling and recovery
- Supports path migration for existing installations

## Troubleshooting

### Common Issues
1. **Path not found errors**: Check volume mappings and ensure host directories exist
2. **Permission denied**: Verify container user has access to mounted volumes
3. **Database connection issues**: Check database service connectivity and credentials

### Health Checks
- **Health endpoint**: `http://localhost:8000/health`
- **Metrics endpoint**: `http://localhost:8000/metrics` (if enabled)
- **Path validation**: `http://localhost:8000/admin/paths/validate`

### Log Locations
- Container logs: `docker logs ai-validation-backend`
- Application logs: `/app/logs/` (inside container)
- System logs: Check deployment platform logs

"""
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(doc_content)
        
        return doc_content
    
    def list_patterns(self) -> Dict[str, str]:
        """List available deployment patterns"""
        return {name: pattern.description for name, pattern in self.patterns.items()}


def main():
    """Command-line interface for deployment configuration generation"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate deployment configurations")
    parser.add_argument("command", choices=["list", "generate", "docs"], help="Command to execute")
    parser.add_argument("pattern", nargs="?", help="Deployment pattern name")
    parser.add_argument("--output-dir", "-o", help="Output directory for generated files")
    parser.add_argument("--format", choices=["docker-compose", "kubernetes", "env", "all"], default="all", help="Configuration format to generate")
    
    args = parser.parse_args()
    
    generator = DeploymentConfigGenerator()
    
    if args.command == "list":
        patterns = generator.list_patterns()
        print("Available deployment patterns:")
        for name, description in patterns.items():
            print(f"  {name}: {description}")
    
    elif args.command == "generate":
        if not args.pattern:
            print("Error: pattern name required for generate command")
            return
        
        output_dir = args.output_dir or f"deployment-{args.pattern}"
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"Generating {args.pattern} configuration...")
        
        if args.format in ["docker-compose", "all"]:
            compose_content = generator.generate_docker_compose(args.pattern)
            with open(f"{output_dir}/docker-compose.yml", 'w') as f:
                f.write(compose_content)
            print(f"Generated: {output_dir}/docker-compose.yml")
        
        if args.format in ["kubernetes", "all"]:
            manifests = generator.generate_kubernetes_manifests(args.pattern, f"{output_dir}/k8s")
            print(f"Generated {len(manifests)} Kubernetes manifests in {output_dir}/k8s/")
        
        if args.format in ["env", "all"]:
            env_content = generator.generate_environment_file(args.pattern)
            with open(f"{output_dir}/.env.example", 'w') as f:
                f.write(env_content)
            print(f"Generated: {output_dir}/.env.example")
    
    elif args.command == "docs":
        if not args.pattern:
            print("Error: pattern name required for docs command")
            return
        
        output_dir = args.output_dir or f"docs-{args.pattern}"
        os.makedirs(output_dir, exist_ok=True)
        
        doc_content = generator.generate_documentation(args.pattern)
        with open(f"{output_dir}/README.md", 'w') as f:
            f.write(doc_content)
        print(f"Generated: {output_dir}/README.md")


if __name__ == "__main__":
    main()