#!/usr/bin/env python3
"""
Deployment Orchestrator - SPARC Root Cause Solution
Unified deployment strategy for Docker + Host environments
Implements comprehensive environment validation and health checking
"""

import os
import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

try:
    from .environment_master import EnvironmentMaster, EnvironmentType, EnvironmentConfig
    from .service_discovery_master import ServiceDiscoveryMaster, ServiceType, DiscoveredService
    from .configuration_resolver import ConfigurationResolver, ConfigType, ResolvedConfig
except ImportError:
    # Fallback imports for standalone testing
    pass

logger = logging.getLogger(__name__)

class DeploymentPhase(Enum):
    """Deployment phases"""
    INITIALIZATION = "initialization"
    ENVIRONMENT_DETECTION = "environment_detection"
    SERVICE_DISCOVERY = "service_discovery"
    CONFIGURATION_RESOLUTION = "configuration_resolution"
    HEALTH_VALIDATION = "health_validation"
    DEPLOYMENT_STRATEGY = "deployment_strategy"
    FINAL_VALIDATION = "final_validation"
    COMPLETED = "completed"

class HealthStatus(Enum):
    """Health check status"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"

@dataclass
class HealthCheckResult:
    """Health check result"""
    component: str
    status: HealthStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    response_time_ms: Optional[float] = None
    timestamp: float = field(default_factory=time.time)

@dataclass
class DeploymentStrategy:
    """Deployment strategy configuration"""
    environment_type: EnvironmentType
    backend_access_mode: str  # "localhost", "docker", "external", "hybrid"
    frontend_access_mode: str
    cors_strategy: str  # "permissive", "restrictive", "auto"
    service_discovery_mode: str  # "dns", "localhost", "hybrid"
    health_check_endpoints: List[str] = field(default_factory=list)
    deployment_commands: List[str] = field(default_factory=list)

@dataclass
class OrchestrationResult:
    """Final orchestration result"""
    strategy: DeploymentStrategy
    environment_config: Optional[EnvironmentConfig] = None
    resolved_config: Optional[ResolvedConfig] = None
    discovered_services: Dict[str, DiscoveredService] = field(default_factory=dict)
    health_checks: List[HealthCheckResult] = field(default_factory=list)
    cors_origins: List[str] = field(default_factory=list)
    deployment_files: Dict[str, str] = field(default_factory=dict)
    validation_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    is_ready_for_deployment: bool = False
    phase: DeploymentPhase = DeploymentPhase.INITIALIZATION

class DeploymentOrchestrator:
    """
    Master deployment orchestrator
    Implements complete environment configuration fixes:
    1. Unified environment detection and configuration
    2. Adaptive service discovery  
    3. Configuration conflict resolution
    4. CORS unification across all components
    5. Unified deployment strategy for mixed environments
    6. Comprehensive health checking and validation
    """
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.environment_master = EnvironmentMaster()
        self.service_discovery = ServiceDiscoveryMaster(self.environment_master)
        self.config_resolver = ConfigurationResolver(str(self.project_root))
        
        # Initialize result
        self.result = OrchestrationResult(
            strategy=DeploymentStrategy(
                environment_type=EnvironmentType.LOCAL,
                backend_access_mode="localhost",
                frontend_access_mode="localhost", 
                cors_strategy="auto",
                service_discovery_mode="hybrid"
            )
        )
    
    async def orchestrate_deployment(self) -> OrchestrationResult:
        """
        Master orchestration method - executes all phases
        """
        logger.info("🚀 Starting Deployment Orchestration...")
        
        try:
            # Phase 1: Environment Detection
            await self._phase_environment_detection()
            
            # Phase 2: Service Discovery
            await self._phase_service_discovery()
            
            # Phase 3: Configuration Resolution
            await self._phase_configuration_resolution()
            
            # Phase 4: Generate Deployment Strategy
            await self._phase_deployment_strategy()
            
            # Phase 5: Unified CORS Configuration
            await self._phase_cors_unification()
            
            # Phase 6: Health Validation
            await self._phase_health_validation()
            
            # Phase 7: Generate Deployment Files
            await self._phase_generate_deployment_files()
            
            # Phase 8: Final Validation
            await self._phase_final_validation()
            
            self.result.phase = DeploymentPhase.COMPLETED
            self.result.is_ready_for_deployment = len(self.result.validation_errors) == 0
            
            logger.info(f"✅ Deployment Orchestration Complete - Ready: {self.result.is_ready_for_deployment}")
            
        except Exception as e:
            logger.error(f"❌ Deployment Orchestration Failed: {e}")
            self.result.validation_errors.append(f"Orchestration failed: {str(e)}")
            
        return self.result
    
    async def _phase_environment_detection(self):
        """Phase 1: Environment Detection"""
        self.result.phase = DeploymentPhase.ENVIRONMENT_DETECTION
        logger.info("📍 Phase 1: Environment Detection")
        
        try:
            # Initialize environment master
            env_config = await self.environment_master.initialize()
            self.result.environment_config = env_config
            
            # Update strategy based on environment
            self.result.strategy.environment_type = env_config.environment_type
            
            logger.info(f"   Environment: {env_config.environment_type.value} "
                       f"(confidence: {env_config.confidence_score:.1%})")
            
            # Validate confidence
            if env_config.confidence_score < 0.6:
                self.result.warnings.append(
                    f"Low environment detection confidence: {env_config.confidence_score:.1%}"
                )
            
        except Exception as e:
            error_msg = f"Environment detection failed: {e}"
            self.result.validation_errors.append(error_msg)
            logger.error(f"   ❌ {error_msg}")
    
    async def _phase_service_discovery(self):
        """Phase 2: Service Discovery"""
        self.result.phase = DeploymentPhase.SERVICE_DISCOVERY
        logger.info("🔍 Phase 2: Service Discovery")
        
        services_to_discover = [
            ("backend", ServiceType.BACKEND),
            ("database", ServiceType.DATABASE),
            ("redis", ServiceType.REDIS)
        ]
        
        for service_name, service_type in services_to_discover:
            try:
                discovered = await self.service_discovery.discover_service(service_name, service_type)
                self.result.discovered_services[service_name] = discovered
                
                logger.info(f"   {service_name}: {discovered.endpoint.get_url()} "
                           f"({discovered.status.value})")
                
                if discovered.status != DiscoveredService.AVAILABLE:
                    self.result.warnings.append(
                        f"Service {service_name} is {discovered.status.value}"
                    )
                    
            except Exception as e:
                error_msg = f"Service discovery failed for {service_name}: {e}"
                self.result.validation_errors.append(error_msg)
                logger.error(f"   ❌ {error_msg}")
    
    async def _phase_configuration_resolution(self):
        """Phase 3: Configuration Resolution"""
        self.result.phase = DeploymentPhase.CONFIGURATION_RESOLUTION
        logger.info("🔧 Phase 3: Configuration Resolution")
        
        try:
            # Resolve all configuration
            resolved = await self.config_resolver.resolve_configuration()
            self.result.resolved_config = resolved
            
            logger.info(f"   Resolved: {len(resolved.values)} values, "
                       f"{len(resolved.conflicts)} conflicts, {len(resolved.warnings)} warnings")
            
            # Add warnings to result
            self.result.warnings.extend(resolved.warnings)
            
            # Log conflicts as warnings (they're already resolved)
            for conflict in resolved.conflicts:
                self.result.warnings.append(f"Config conflict resolved: {conflict['unified_key']}")
                
        except Exception as e:
            error_msg = f"Configuration resolution failed: {e}"
            self.result.validation_errors.append(error_msg)
            logger.error(f"   ❌ {error_msg}")
    
    async def _phase_deployment_strategy(self):
        """Phase 4: Generate Deployment Strategy"""
        self.result.phase = DeploymentPhase.DEPLOYMENT_STRATEGY
        logger.info("⚙️  Phase 4: Deployment Strategy")
        
        try:
            env_type = self.result.environment_config.environment_type
            
            # Determine access modes based on environment and discovered services
            backend_mode = self._determine_backend_access_mode(env_type)
            frontend_mode = self._determine_frontend_access_mode(env_type)
            cors_strategy = self._determine_cors_strategy(env_type)
            discovery_mode = self._determine_service_discovery_mode(env_type)
            
            # Update strategy
            self.result.strategy.backend_access_mode = backend_mode
            self.result.strategy.frontend_access_mode = frontend_mode
            self.result.strategy.cors_strategy = cors_strategy
            self.result.strategy.service_discovery_mode = discovery_mode
            
            # Generate health check endpoints
            self.result.strategy.health_check_endpoints = self._generate_health_endpoints()
            
            # Generate deployment commands
            self.result.strategy.deployment_commands = self._generate_deployment_commands()
            
            logger.info(f"   Strategy: backend={backend_mode}, frontend={frontend_mode}, "
                       f"cors={cors_strategy}, discovery={discovery_mode}")
            
        except Exception as e:
            error_msg = f"Deployment strategy generation failed: {e}"
            self.result.validation_errors.append(error_msg)
            logger.error(f"   ❌ {error_msg}")
    
    async def _phase_cors_unification(self):
        """Phase 5: Unified CORS Configuration"""
        self.result.phase = DeploymentPhase.CORS_UNIFICATION
        logger.info("🌐 Phase 5: CORS Unification")
        
        try:
            cors_origins = await self._generate_unified_cors_origins()
            self.result.cors_origins = cors_origins
            
            logger.info(f"   Generated {len(cors_origins)} CORS origins")
            for origin in cors_origins[:5]:  # Show first 5
                logger.info(f"     - {origin}")
            if len(cors_origins) > 5:
                logger.info(f"     ... and {len(cors_origins) - 5} more")
                
        except Exception as e:
            error_msg = f"CORS unification failed: {e}"
            self.result.validation_errors.append(error_msg)
            logger.error(f"   ❌ {error_msg}")
    
    async def _phase_health_validation(self):
        """Phase 6: Health Validation"""
        self.result.phase = DeploymentPhase.HEALTH_VALIDATION
        logger.info("🏥 Phase 6: Health Validation")
        
        # Health check components
        health_checks = [
            self._health_check_environment(),
            self._health_check_configuration(),
            self._health_check_services(),
            self._health_check_cors_config(),
            self._health_check_deployment_readiness()
        ]
        
        for health_check in health_checks:
            try:
                result = await health_check
                self.result.health_checks.append(result)
                
                status_icon = "✅" if result.status == HealthStatus.HEALTHY else (
                    "⚠️" if result.status == HealthStatus.DEGRADED else "❌"
                )
                
                logger.info(f"   {status_icon} {result.component}: {result.message}")
                
                if result.status == HealthStatus.UNHEALTHY:
                    self.result.validation_errors.append(f"{result.component}: {result.message}")
                elif result.status == HealthStatus.DEGRADED:
                    self.result.warnings.append(f"{result.component}: {result.message}")
                    
            except Exception as e:
                error_msg = f"Health check failed for component: {e}"
                self.result.validation_errors.append(error_msg)
                logger.error(f"   ❌ {error_msg}")
    
    async def _phase_generate_deployment_files(self):
        """Phase 7: Generate Deployment Files"""
        logger.info("📁 Phase 7: Generate Deployment Files")
        
        try:
            # Generate unified .env file
            env_content = await self._generate_unified_env_file()
            self.result.deployment_files['.env.unified'] = env_content
            
            # Generate Docker Compose override
            docker_override = await self._generate_docker_compose_override()
            self.result.deployment_files['docker-compose.override.yml'] = docker_override
            
            # Generate frontend config
            frontend_config = await self._generate_frontend_config()
            self.result.deployment_files['frontend-config.js'] = frontend_config
            
            # Generate deployment script
            deployment_script = await self._generate_deployment_script()
            self.result.deployment_files['deploy.sh'] = deployment_script
            
            logger.info(f"   Generated {len(self.result.deployment_files)} deployment files")
            
        except Exception as e:
            error_msg = f"Deployment file generation failed: {e}"
            self.result.validation_errors.append(error_msg)
            logger.error(f"   ❌ {error_msg}")
    
    async def _phase_final_validation(self):
        """Phase 8: Final Validation"""
        self.result.phase = DeploymentPhase.FINAL_VALIDATION
        logger.info("✅ Phase 8: Final Validation")
        
        # Summary validation
        validation_summary = {
            'environment_detected': self.result.environment_config is not None,
            'services_discovered': len(self.result.discovered_services) > 0,
            'configuration_resolved': self.result.resolved_config is not None,
            'cors_configured': len(self.result.cors_origins) > 0,
            'deployment_files_generated': len(self.result.deployment_files) > 0,
            'health_checks_passed': all(
                h.status != HealthStatus.UNHEALTHY for h in self.result.health_checks
            )
        }
        
        failed_validations = [k for k, v in validation_summary.items() if not v]
        
        if failed_validations:
            for failure in failed_validations:
                self.result.validation_errors.append(f"Validation failed: {failure}")
        
        logger.info(f"   Validation Summary: {sum(validation_summary.values())}/{len(validation_summary)} passed")
        
        # Final readiness check
        self.result.is_ready_for_deployment = (
            len(self.result.validation_errors) == 0 and
            len(failed_validations) == 0
        )
    
    def _determine_backend_access_mode(self, env_type: EnvironmentType) -> str:
        """Determine backend access mode"""
        if env_type == EnvironmentType.DOCKER:
            return "docker"
        elif env_type == EnvironmentType.HYBRID:
            return "hybrid"
        elif self.result.environment_config and self.result.environment_config.external_ip:
            return "external"
        else:
            return "localhost"
    
    def _determine_frontend_access_mode(self, env_type: EnvironmentType) -> str:
        """Determine frontend access mode"""
        if self.result.environment_config and self.result.environment_config.external_ip:
            return "external"
        else:
            return "localhost"
    
    def _determine_cors_strategy(self, env_type: EnvironmentType) -> str:
        """Determine CORS strategy"""
        if env_type in [EnvironmentType.HYBRID, EnvironmentType.DOCKER]:
            return "permissive"
        else:
            return "auto"
    
    def _determine_service_discovery_mode(self, env_type: EnvironmentType) -> str:
        """Determine service discovery mode"""
        if env_type == EnvironmentType.DOCKER:
            return "dns"
        elif env_type == EnvironmentType.KUBERNETES:
            return "k8s"
        else:
            return "hybrid"
    
    def _generate_health_endpoints(self) -> List[str]:
        """Generate health check endpoints"""
        endpoints = []
        
        # Backend health endpoints
        if 'backend' in self.result.discovered_services:
            backend = self.result.discovered_services['backend']
            base_url = backend.endpoint.get_url()
            endpoints.extend([
                f"{base_url}/health",
                f"{base_url}/api/health",
                f"{base_url}/healthz"
            ])
        
        return endpoints
    
    def _generate_deployment_commands(self) -> List[str]:
        """Generate deployment commands"""
        commands = []
        
        env_type = self.result.strategy.environment_type
        
        if env_type == EnvironmentType.DOCKER:
            commands.extend([
                "docker-compose down",
                "docker-compose build --no-cache",
                "docker-compose up -d",
                "docker-compose logs -f"
            ])
        elif env_type == EnvironmentType.LOCAL:
            commands.extend([
                "cd backend && python -m uvicorn main:app --reload",
                "cd frontend && npm start"
            ])
        
        return commands
    
    async def _generate_unified_cors_origins(self) -> List[str]:
        """Generate unified CORS origins"""
        origins = set()
        
        # Add localhost origins
        origins.update([
            'http://localhost:3000',
            'http://127.0.0.1:3000',
            'http://localhost:3001',
            'http://127.0.0.1:3001'
        ])
        
        # Add detected IP origins
        if self.result.environment_config:
            # Internal IP
            internal_ip = self.result.environment_config.internal_ip
            if internal_ip and internal_ip != '127.0.0.1':
                origins.update([
                    f'http://{internal_ip}:3000',
                    f'http://{internal_ip}:3001'
                ])
            
            # External IP
            external_ip = self.result.environment_config.external_ip
            if external_ip:
                origins.update([
                    f'http://{external_ip}:3000',
                    f'http://{external_ip}:3001',
                    f'https://{external_ip}:3000',
                    f'https://{external_ip}:3001'
                ])
        
        # Add origins from resolved configuration
        if self.result.resolved_config:
            cors_config_keys = [
                'AIVALIDATION_CORS_ORIGINS',
                'CORS_ORIGINS',
                'ALLOWED_ORIGINS',
                'VRU_CORS_ORIGINS'
            ]
            
            for key in cors_config_keys:
                if key in self.result.resolved_config.values:
                    cors_value = self.result.resolved_config.values[key].value
                    try:
                        if isinstance(cors_value, str):
                            if cors_value.startswith('['):
                                origins.update(json.loads(cors_value))
                            else:
                                origins.update([o.strip() for o in cors_value.split(',') if o.strip()])
                    except:
                        pass
        
        # Filter and validate
        valid_origins = []
        for origin in origins:
            if origin and origin not in ['http://', 'https://']:
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(origin)
                    if parsed.scheme and parsed.netloc:
                        valid_origins.append(origin)
                except:
                    pass
        
        return sorted(valid_origins)
    
    async def _health_check_environment(self) -> HealthCheckResult:
        """Health check: Environment configuration"""
        if not self.result.environment_config:
            return HealthCheckResult(
                component="Environment",
                status=HealthStatus.UNHEALTHY,
                message="Environment not detected"
            )
        
        confidence = self.result.environment_config.confidence_score
        
        if confidence >= 0.8:
            status = HealthStatus.HEALTHY
            message = f"Environment detected with high confidence ({confidence:.1%})"
        elif confidence >= 0.6:
            status = HealthStatus.DEGRADED
            message = f"Environment detected with medium confidence ({confidence:.1%})"
        else:
            status = HealthStatus.UNHEALTHY
            message = f"Environment detected with low confidence ({confidence:.1%})"
        
        return HealthCheckResult(
            component="Environment",
            status=status,
            message=message,
            details={'confidence': confidence, 'type': self.result.environment_config.environment_type.value}
        )
    
    async def _health_check_configuration(self) -> HealthCheckResult:
        """Health check: Configuration resolution"""
        if not self.result.resolved_config:
            return HealthCheckResult(
                component="Configuration",
                status=HealthStatus.UNHEALTHY,
                message="Configuration not resolved"
            )
        
        conflicts = len(self.result.resolved_config.conflicts)
        warnings = len(self.result.resolved_config.warnings)
        
        if warnings == 0:
            status = HealthStatus.HEALTHY
            message = f"Configuration healthy ({len(self.result.resolved_config.values)} values)"
        elif warnings <= 3:
            status = HealthStatus.DEGRADED
            message = f"Configuration has {warnings} warnings"
        else:
            status = HealthStatus.UNHEALTHY
            message = f"Configuration has {warnings} warnings, {conflicts} conflicts"
        
        return HealthCheckResult(
            component="Configuration",
            status=status,
            message=message,
            details={'values': len(self.result.resolved_config.values), 'conflicts': conflicts, 'warnings': warnings}
        )
    
    async def _health_check_services(self) -> HealthCheckResult:
        """Health check: Service discovery"""
        if not self.result.discovered_services:
            return HealthCheckResult(
                component="Services",
                status=HealthStatus.UNHEALTHY,
                message="No services discovered"
            )
        
        healthy_services = sum(
            1 for s in self.result.discovered_services.values() 
            if s.status.value == "available"
        )
        total_services = len(self.result.discovered_services)
        
        if healthy_services == total_services:
            status = HealthStatus.HEALTHY
            message = f"All {total_services} services healthy"
        elif healthy_services >= total_services * 0.7:
            status = HealthStatus.DEGRADED
            message = f"{healthy_services}/{total_services} services healthy"
        else:
            status = HealthStatus.UNHEALTHY
            message = f"Only {healthy_services}/{total_services} services healthy"
        
        return HealthCheckResult(
            component="Services",
            status=status,
            message=message,
            details={'healthy': healthy_services, 'total': total_services}
        )
    
    async def _health_check_cors_config(self) -> HealthCheckResult:
        """Health check: CORS configuration"""
        cors_count = len(self.result.cors_origins)
        
        if cors_count == 0:
            return HealthCheckResult(
                component="CORS",
                status=HealthStatus.UNHEALTHY,
                message="No CORS origins configured"
            )
        elif cors_count >= 4:  # localhost + IP variants
            return HealthCheckResult(
                component="CORS",
                status=HealthStatus.HEALTHY,
                message=f"CORS configured with {cors_count} origins"
            )
        else:
            return HealthCheckResult(
                component="CORS",
                status=HealthStatus.DEGRADED,
                message=f"CORS configured with only {cors_count} origins"
            )
    
    async def _health_check_deployment_readiness(self) -> HealthCheckResult:
        """Health check: Overall deployment readiness"""
        
        readiness_factors = {
            'environment_config': self.result.environment_config is not None,
            'resolved_config': self.result.resolved_config is not None,
            'discovered_services': len(self.result.discovered_services) > 0,
            'cors_origins': len(self.result.cors_origins) > 0,
            'deployment_files': len(self.result.deployment_files) > 0,
        }
        
        ready_count = sum(readiness_factors.values())
        total_factors = len(readiness_factors)
        
        if ready_count == total_factors:
            status = HealthStatus.HEALTHY
            message = "Deployment ready"
        elif ready_count >= total_factors * 0.8:
            status = HealthStatus.DEGRADED
            message = f"Deployment mostly ready ({ready_count}/{total_factors})"
        else:
            status = HealthStatus.UNHEALTHY
            message = f"Deployment not ready ({ready_count}/{total_factors})"
        
        return HealthCheckResult(
            component="Deployment Readiness",
            status=status,
            message=message,
            details=readiness_factors
        )
    
    async def _generate_unified_env_file(self) -> str:
        """Generate unified .env file"""
        lines = [
            "# Unified Environment Configuration",
            "# Generated by Deployment Orchestrator",
            f"# Environment: {self.result.environment_config.environment_type.value if self.result.environment_config else 'unknown'}",
            f"# Strategy: {self.result.strategy.backend_access_mode}",
            ""
        ]
        
        if self.result.resolved_config:
            for key, config_value in sorted(self.result.resolved_config.values.items()):
                if config_value.is_sensitive:
                    lines.append(f"# {key}=[REDACTED]")
                else:
                    lines.append(f"{key}={config_value.value}")
        
        # Add unified CORS origins
        cors_json = json.dumps(self.result.cors_origins)
        lines.extend([
            "",
            "# Unified CORS Origins",
            f"AIVALIDATION_CORS_ORIGINS={cors_json}",
            f"CORS_ORIGINS={cors_json}",
            f"ALLOWED_ORIGINS={cors_json}"
        ])
        
        return '\n'.join(lines)
    
    async def _generate_docker_compose_override(self) -> str:
        """Generate Docker Compose override"""
        
        env_vars = {}
        if self.result.resolved_config:
            env_vars = {
                k: v.value for k, v in self.result.resolved_config.values.items()
                if not v.is_sensitive and not k.startswith('REACT_APP_')
            }
        
        # Add CORS configuration
        cors_json = json.dumps(self.result.cors_origins)
        env_vars['AIVALIDATION_CORS_ORIGINS'] = cors_json
        
        override_config = {
            'version': '3.8',
            'services': {
                'backend': {
                    'environment': env_vars
                },
                'frontend': {
                    'environment': {
                        k: v for k, v in env_vars.items() 
                        if k.startswith('REACT_APP_') or k in ['NODE_ENV', 'GENERATE_SOURCEMAP']
                    }
                }
            }
        }
        
        try:
            import yaml
            return yaml.dump(override_config, default_flow_style=False)
        except ImportError:
            return f"# Docker Compose Override (YAML library not available)\n{json.dumps(override_config, indent=2)}"
    
    async def _generate_frontend_config(self) -> str:
        """Generate frontend configuration"""
        
        # Extract frontend configuration
        frontend_config = {
            'apiUrl': 'http://localhost:8000',
            'wsUrl': 'ws://localhost:8000',
            'environment': 'development',
            'debug': True,
            'corsOrigins': self.result.cors_origins
        }
        
        if self.result.resolved_config:
            mapping = {
                'REACT_APP_API_URL': 'apiUrl',
                'REACT_APP_WS_URL': 'wsUrl',
                'REACT_APP_ENVIRONMENT': 'environment',
                'REACT_APP_DEBUG': 'debug'
            }
            
            for env_key, config_key in mapping.items():
                if env_key in self.result.resolved_config.values:
                    value = self.result.resolved_config.values[env_key].value
                    if config_key == 'debug':
                        value = value.lower() == 'true'
                    frontend_config[config_key] = value
        
        return f"""// Frontend Configuration
// Generated by Deployment Orchestrator
window.APP_CONFIG = {json.dumps(frontend_config, indent=2)};"""
    
    async def _generate_deployment_script(self) -> str:
        """Generate deployment script"""
        
        commands = self.result.strategy.deployment_commands
        
        script_lines = [
            "#!/bin/bash",
            "# Deployment Script",
            "# Generated by Deployment Orchestrator",
            "",
            "set -e",
            "",
            "echo '🚀 Starting deployment...'",
            ""
        ]
        
        for i, command in enumerate(commands, 1):
            script_lines.extend([
                f"echo 'Step {i}: {command}'",
                command,
                ""
            ])
        
        script_lines.extend([
            "echo '✅ Deployment completed successfully!'",
            "",
            "# Health check",
            "sleep 5"
        ])
        
        for endpoint in self.result.strategy.health_check_endpoints[:1]:  # Check first endpoint
            script_lines.extend([
                f"echo 'Health checking: {endpoint}'",
                f"curl -f {endpoint} || echo 'Health check failed'"
            ])
        
        return '\n'.join(script_lines)
    
    async def export_deployment_files(self, output_dir: str = "deployment_output"):
        """Export all deployment files to directory"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        for filename, content in self.result.deployment_files.items():
            file_path = output_path / filename
            
            with open(file_path, 'w') as f:
                f.write(content)
            
            # Make shell scripts executable
            if filename.endswith('.sh'):
                os.chmod(file_path, 0o755)
        
        # Export orchestration summary
        summary_path = output_path / 'orchestration_summary.json'
        with open(summary_path, 'w') as f:
            summary_data = {
                'strategy': asdict(self.result.strategy),
                'health_checks': [asdict(h) for h in self.result.health_checks],
                'cors_origins': self.result.cors_origins,
                'validation_errors': self.result.validation_errors,
                'warnings': self.result.warnings,
                'is_ready_for_deployment': self.result.is_ready_for_deployment,
                'phase': self.result.phase.value
            }
            json.dump(summary_data, f, indent=2)
        
        logger.info(f"📁 Deployment files exported to {output_path}")
        
        return output_path

# Global instance
deployment_orchestrator = DeploymentOrchestrator()

# Convenience functions
async def orchestrate_full_deployment() -> OrchestrationResult:
    """Orchestrate full deployment"""
    return await deployment_orchestrator.orchestrate_deployment()

async def export_deployment_configuration(output_dir: str = "deployment_output"):
    """Export deployment configuration"""
    result = await orchestrate_full_deployment()
    output_path = await deployment_orchestrator.export_deployment_files(output_dir)
    return result, output_path

if __name__ == "__main__":
    # Test deployment orchestrator
    async def test_deployment_orchestrator():
        result = await orchestrate_full_deployment()
        
        print("🚀 Deployment Orchestration Results:")
        print(f"   Phase: {result.phase.value}")
        print(f"   Ready: {result.is_ready_for_deployment}")
        print(f"   Environment: {result.strategy.environment_type.value}")
        print(f"   Backend Mode: {result.strategy.backend_access_mode}")
        print(f"   CORS Origins: {len(result.cors_origins)}")
        print(f"   Health Checks: {len(result.health_checks)}")
        print(f"   Warnings: {len(result.warnings)}")
        print(f"   Errors: {len(result.validation_errors)}")
        
        if result.validation_errors:
            print("\n❌ Validation Errors:")
            for error in result.validation_errors:
                print(f"   - {error}")
        
        # Export files
        await deployment_orchestrator.export_deployment_files()
        print("\n📁 Deployment files exported")
    
    asyncio.run(test_deployment_orchestrator())