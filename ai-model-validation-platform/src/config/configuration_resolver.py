#!/usr/bin/env python3
"""
Configuration Resolver - SPARC Root Cause Solution
Resolves configuration file conflicts and establishes precedence hierarchy
Unifies VRU_ vs AIVALIDATION_ naming conflicts and multiple configuration sources
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)

class ConfigSource(Enum):
    """Configuration source types in precedence order (higher = more important)"""
    DEFAULT = 1
    FILE_CONFIG = 2
    ENV_FILE = 3
    ENVIRONMENT_VARS = 4
    RUNTIME_OVERRIDE = 5

class ConfigType(Enum):
    """Configuration category types"""
    BACKEND = "backend"
    FRONTEND = "frontend"
    DATABASE = "database"
    REDIS = "redis"
    CORS = "cors"
    SECURITY = "security"
    DOCKER = "docker"
    GENERAL = "general"

@dataclass
class ConfigValue:
    """Configuration value with metadata"""
    key: str
    value: Any
    source: ConfigSource
    source_file: Optional[str] = None
    precedence_score: int = 0
    is_sensitive: bool = False

@dataclass
class ResolvedConfig:
    """Final resolved configuration"""
    values: Dict[str, ConfigValue] = field(default_factory=dict)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    sources_loaded: List[str] = field(default_factory=list)

class ConfigurationResolver:
    """
    Master configuration resolver
    Solves configuration conflicts:
    1. Multiple configuration file conflicts (config.py, unified_config.py, appConfig.ts, envConfig.ts)
    2. Environment variable naming conflicts (VRU_ vs AIVALIDATION_ prefixes)
    3. Docker Compose vs .env file precedence issues
    4. Frontend vs Backend configuration mismatches
    """
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self._config_cache: Dict[str, ResolvedConfig] = {}
        
        # Define configuration file hierarchy (order matters)
        self.config_files = [
            # Environment files (lowest precedence)
            ".env.defaults",
            ".env.example", 
            ".env.development",
            ".env.production",
            ".env.vultr",
            ".env",
            
            # Backend config files
            "backend/.env.example",
            "backend/.env.production",
            "backend/.env",
            
            # Docker environment
            ".env.docker",
            "docker-compose.yml",
            "docker-compose.production.yml",
        ]
        
        # Define environment variable prefixes in precedence order
        self.env_prefixes = [
            "AIVALIDATION_",  # Primary prefix
            "VRU_",           # Legacy prefix  
            "REACT_APP_",     # Frontend prefix
            ""                # No prefix (lowest precedence)
        ]
    
    async def resolve_configuration(self, config_type: Optional[ConfigType] = None) -> ResolvedConfig:
        """
        Resolve configuration with conflict resolution and precedence handling
        
        Args:
            config_type: Specific configuration type to resolve (None for all)
            
        Returns:
            ResolvedConfig with resolved values and conflict information
        """
        cache_key = config_type.value if config_type else "all"
        
        # Check cache
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]
        
        logger.info(f"🔧 Resolving configuration{f' for {config_type.value}' if config_type else ''}...")
        
        resolved_config = ResolvedConfig()
        
        # Step 1: Load default configuration
        await self._load_default_config(resolved_config, config_type)
        
        # Step 2: Load configuration files
        await self._load_config_files(resolved_config, config_type)
        
        # Step 3: Load environment variables
        await self._load_environment_variables(resolved_config, config_type)
        
        # Step 4: Apply naming unification (VRU_ -> AIVALIDATION_)
        await self._unify_naming_conventions(resolved_config)
        
        # Step 5: Resolve conflicts using precedence rules
        await self._resolve_conflicts(resolved_config)
        
        # Step 6: Validate final configuration
        await self._validate_resolved_config(resolved_config, config_type)
        
        # Cache result
        self._config_cache[cache_key] = resolved_config
        
        logger.info(f"✅ Configuration resolved: {len(resolved_config.values)} values, "
                   f"{len(resolved_config.conflicts)} conflicts, {len(resolved_config.warnings)} warnings")
        
        return resolved_config
    
    async def _load_default_config(self, config: ResolvedConfig, config_type: Optional[ConfigType]):
        """Load default configuration values"""
        
        defaults = {
            # Backend defaults
            'AIVALIDATION_API_HOST': '0.0.0.0',
            'AIVALIDATION_API_PORT': '8000',
            'AIVALIDATION_APP_ENVIRONMENT': 'development',
            'AIVALIDATION_DATABASE_URL': 'sqlite:///./dev_database.db',
            'AIVALIDATION_DOCKER_MODE': 'false',
            
            # Frontend defaults
            'REACT_APP_API_URL': 'http://localhost:8000',
            'REACT_APP_WS_URL': 'ws://localhost:8000',
            'REACT_APP_ENVIRONMENT': 'development',
            'REACT_APP_DEBUG': 'true',
            
            # CORS defaults
            'AIVALIDATION_CORS_ORIGINS': '["http://localhost:3000","http://127.0.0.1:3000"]',
            
            # Security defaults
            'AIVALIDATION_SECRET_KEY': 'INSECURE-DEFAULT-CHANGE-ME',
            
            # Redis defaults
            'AIVALIDATION_REDIS_URL': 'redis://localhost:6379',
            
            # Docker defaults
            'COMPOSE_PROJECT_NAME': 'ai-model-validation',
            'DOCKER_BUILDKIT': '1'
        }
        
        for key, value in defaults.items():
            if not config_type or self._matches_config_type(key, config_type):
                config.values[key] = ConfigValue(
                    key=key,
                    value=value,
                    source=ConfigSource.DEFAULT,
                    precedence_score=ConfigSource.DEFAULT.value
                )
        
        config.sources_loaded.append("defaults")
    
    async def _load_config_files(self, config: ResolvedConfig, config_type: Optional[ConfigType]):
        """Load configuration from files"""
        
        for config_file in self.config_files:
            file_path = self.project_root / config_file
            
            if not file_path.exists():
                continue
                
            try:
                if config_file.endswith('.yml') or config_file.endswith('.yaml'):
                    await self._load_docker_compose_config(config, file_path, config_type)
                elif config_file.startswith('.env') or file_path.name.startswith('.env'):
                    await self._load_env_file_config(config, file_path, config_type)
                elif config_file.endswith('.json'):
                    await self._load_json_config(config, file_path, config_type)
                    
                config.sources_loaded.append(str(file_path))
                
            except Exception as e:
                logger.warning(f"Failed to load config file {file_path}: {e}")
    
    async def _load_env_file_config(self, config: ResolvedConfig, file_path: Path, config_type: Optional[ConfigType]):
        """Load .env file configuration"""
        
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                
                # Parse key=value
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")  # Remove quotes
                    
                    if not config_type or self._matches_config_type(key, config_type):
                        # Determine precedence based on file type
                        if 'production' in file_path.name:
                            precedence = 3
                        elif 'development' in file_path.name:
                            precedence = 2
                        else:
                            precedence = 2
                            
                        config.values[key] = ConfigValue(
                            key=key,
                            value=value,
                            source=ConfigSource.ENV_FILE,
                            source_file=str(file_path),
                            precedence_score=precedence,
                            is_sensitive=self._is_sensitive_key(key)
                        )
    
    async def _load_docker_compose_config(self, config: ResolvedConfig, file_path: Path, config_type: Optional[ConfigType]):
        """Load Docker Compose environment configuration"""
        
        try:
            import yaml
        except ImportError:
            logger.warning("PyYAML not available, skipping Docker Compose config")
            return
            
        with open(file_path, 'r') as f:
            compose_data = yaml.safe_load(f)
        
        # Extract environment variables from services
        services = compose_data.get('services', {})
        
        for service_name, service_config in services.items():
            env_vars = service_config.get('environment', [])
            
            # Handle both list and dict formats
            if isinstance(env_vars, list):
                for env_item in env_vars:
                    if isinstance(env_item, str) and '=' in env_item:
                        key, value = env_item.split('=', 1)
                        self._add_docker_env_var(config, key, value, file_path, service_name, config_type)
            elif isinstance(env_vars, dict):
                for key, value in env_vars.items():
                    self._add_docker_env_var(config, key, str(value), file_path, service_name, config_type)
    
    def _add_docker_env_var(self, config: ResolvedConfig, key: str, value: str, 
                          file_path: Path, service_name: str, config_type: Optional[ConfigType]):
        """Add Docker environment variable to config"""
        
        if not config_type or self._matches_config_type(key, config_type):
            config.values[key] = ConfigValue(
                key=key,
                value=value,
                source=ConfigSource.FILE_CONFIG,
                source_file=f"{file_path} (service: {service_name})",
                precedence_score=ConfigSource.FILE_CONFIG.value,
                is_sensitive=self._is_sensitive_key(key)
            )
    
    async def _load_json_config(self, config: ResolvedConfig, file_path: Path, config_type: Optional[ConfigType]):
        """Load JSON configuration file"""
        
        with open(file_path, 'r') as f:
            json_data = json.load(f)
        
        # Flatten nested JSON to environment variable format
        flattened = self._flatten_json(json_data)
        
        for key, value in flattened.items():
            if not config_type or self._matches_config_type(key, config_type):
                config.values[key] = ConfigValue(
                    key=key,
                    value=str(value),
                    source=ConfigSource.FILE_CONFIG,
                    source_file=str(file_path),
                    precedence_score=ConfigSource.FILE_CONFIG.value,
                    is_sensitive=self._is_sensitive_key(key)
                )
    
    async def _load_environment_variables(self, config: ResolvedConfig, config_type: Optional[ConfigType]):
        """Load environment variables with prefix handling"""
        
        # Get all environment variables
        env_vars = dict(os.environ)
        
        for key, value in env_vars.items():
            if not config_type or self._matches_config_type(key, config_type):
                
                # Determine precedence based on prefix
                precedence = ConfigSource.ENVIRONMENT_VARS.value
                for i, prefix in enumerate(self.env_prefixes):
                    if prefix and key.startswith(prefix):
                        precedence += (len(self.env_prefixes) - i)  # Higher precedence for preferred prefixes
                        break
                
                config.values[key] = ConfigValue(
                    key=key,
                    value=value,
                    source=ConfigSource.ENVIRONMENT_VARS,
                    precedence_score=precedence,
                    is_sensitive=self._is_sensitive_key(key)
                )
    
    async def _unify_naming_conventions(self, config: ResolvedConfig):
        """Unify naming conventions (VRU_ -> AIVALIDATION_)"""
        
        # Mapping of legacy prefixes to unified prefix
        prefix_mappings = {
            'VRU_': 'AIVALIDATION_',
            'AI_VALIDATION_': 'AIVALIDATION_',
            'REACT_APP_VRU_': 'REACT_APP_',
        }
        
        # Create unified keys
        unified_values = {}
        naming_conflicts = []
        
        for old_key, config_value in config.values.items():
            # Find applicable prefix mapping
            new_key = old_key
            for old_prefix, new_prefix in prefix_mappings.items():
                if old_key.startswith(old_prefix):
                    new_key = old_key.replace(old_prefix, new_prefix, 1)
                    break
            
            # If key changed, check for conflicts
            if new_key != old_key:
                if new_key in unified_values:
                    # Conflict detected - keep the one with higher precedence
                    existing = unified_values[new_key]
                    if config_value.precedence_score > existing.precedence_score:
                        naming_conflicts.append({
                            'unified_key': new_key,
                            'old_key': old_key,
                            'replaced_key': existing.key,
                            'winner_source': config_value.source.name,
                            'loser_source': existing.source.name
                        })
                        unified_values[new_key] = ConfigValue(
                            key=new_key,
                            value=config_value.value,
                            source=config_value.source,
                            source_file=config_value.source_file,
                            precedence_score=config_value.precedence_score,
                            is_sensitive=config_value.is_sensitive
                        )
                else:
                    unified_values[new_key] = ConfigValue(
                        key=new_key,
                        value=config_value.value,
                        source=config_value.source,
                        source_file=config_value.source_file,
                        precedence_score=config_value.precedence_score,
                        is_sensitive=config_value.is_sensitive
                    )
            else:
                unified_values[new_key] = config_value
        
        # Update config with unified values
        config.values = unified_values
        config.conflicts.extend(naming_conflicts)
        
        if naming_conflicts:
            logger.info(f"📝 Unified {len(naming_conflicts)} naming conflicts")
    
    async def _resolve_conflicts(self, config: ResolvedConfig):
        """Resolve configuration conflicts using precedence rules"""
        
        # Group values by unified key
        key_groups = {}
        for key, value in config.values.items():
            # Normalize key for conflict detection (remove prefixes temporarily)
            normalized_key = self._normalize_key_for_conflict_detection(key)
            
            if normalized_key not in key_groups:
                key_groups[normalized_key] = []
            key_groups[normalized_key].append((key, value))
        
        # Resolve conflicts within each group
        resolved_values = {}
        
        for normalized_key, key_value_pairs in key_groups.items():
            if len(key_value_pairs) == 1:
                # No conflict
                key, value = key_value_pairs[0]
                resolved_values[key] = value
            else:
                # Conflict - select winner based on precedence
                winner_key, winner_value = max(key_value_pairs, key=lambda x: x[1].precedence_score)
                resolved_values[winner_key] = winner_value
                
                # Log conflict
                losers = [kv for kv in key_value_pairs if kv[0] != winner_key]
                conflict_info = {
                    'normalized_key': normalized_key,
                    'winner': {
                        'key': winner_key,
                        'value': winner_value.value if not winner_value.is_sensitive else '[REDACTED]',
                        'source': winner_value.source.name,
                        'precedence': winner_value.precedence_score
                    },
                    'losers': [
                        {
                            'key': k,
                            'value': v.value if not v.is_sensitive else '[REDACTED]',
                            'source': v.source.name,
                            'precedence': v.precedence_score
                        }
                        for k, v in losers
                    ]
                }
                config.conflicts.append(conflict_info)
        
        config.values = resolved_values
        
        if config.conflicts:
            logger.info(f"⚔️  Resolved {len(config.conflicts)} configuration conflicts")
    
    def _normalize_key_for_conflict_detection(self, key: str) -> str:
        """Normalize key for conflict detection"""
        
        # Remove prefixes for comparison
        for prefix in self.env_prefixes:
            if prefix and key.startswith(prefix):
                return key[len(prefix):]
        
        return key
    
    async def _validate_resolved_config(self, config: ResolvedConfig, config_type: Optional[ConfigType]):
        """Validate resolved configuration"""
        
        warnings = []
        
        # Check for required values
        required_keys = [
            'AIVALIDATION_API_HOST',
            'AIVALIDATION_API_PORT',
            'AIVALIDATION_DATABASE_URL'
        ]
        
        for required_key in required_keys:
            if required_key not in config.values:
                warnings.append(f"Required configuration key missing: {required_key}")
        
        # Check for insecure defaults in production
        env_type = config.values.get('AIVALIDATION_APP_ENVIRONMENT', ConfigValue('', 'development', ConfigSource.DEFAULT)).value
        
        if env_type.lower() in ['production', 'prod']:
            insecure_defaults = [
                ('AIVALIDATION_SECRET_KEY', 'INSECURE-DEFAULT-CHANGE-ME'),
                ('AIVALIDATION_SECRET_KEY', 'your-secret-key-here'),
                ('AIVALIDATION_SECRET_KEY', 'REPLACE-ME-IN-PRODUCTION')
            ]
            
            for key, insecure_value in insecure_defaults:
                if key in config.values and config.values[key].value == insecure_value:
                    warnings.append(f"Insecure default value for {key} in production")
        
        # Validate CORS origins format
        cors_key = 'AIVALIDATION_CORS_ORIGINS'
        if cors_key in config.values:
            cors_value = config.values[cors_key].value
            try:
                if isinstance(cors_value, str) and cors_value.startswith('['):
                    json.loads(cors_value)  # Validate JSON format
            except json.JSONDecodeError:
                warnings.append(f"Invalid JSON format for {cors_key}")
        
        # Validate URL formats
        url_keys = [
            'AIVALIDATION_DATABASE_URL',
            'AIVALIDATION_REDIS_URL',
            'REACT_APP_API_URL',
            'REACT_APP_WS_URL'
        ]
        
        for url_key in url_keys:
            if url_key in config.values:
                url_value = config.values[url_key].value
                if isinstance(url_value, str) and not self._is_valid_url(url_value):
                    warnings.append(f"Invalid URL format for {url_key}: {url_value}")
        
        config.warnings = warnings
        
        if warnings:
            logger.warning(f"⚠️ Configuration validation warnings: {len(warnings)} issues found")
    
    def _matches_config_type(self, key: str, config_type: ConfigType) -> bool:
        """Check if key matches specified configuration type"""
        
        type_patterns = {
            ConfigType.BACKEND: ['API_', 'BACKEND_', 'UVICORN_', 'FASTAPI_'],
            ConfigType.FRONTEND: ['REACT_APP_', 'FRONTEND_', 'NODE_', 'NPM_'],
            ConfigType.DATABASE: ['DATABASE_', 'POSTGRES_', 'MYSQL_', 'DB_'],
            ConfigType.REDIS: ['REDIS_', 'CACHE_'],
            ConfigType.CORS: ['CORS_', 'ALLOWED_ORIGINS'],
            ConfigType.SECURITY: ['SECRET_', 'JWT_', 'SSL_', 'SECURITY_'],
            ConfigType.DOCKER: ['DOCKER_', 'COMPOSE_', 'CONTAINER_']
        }
        
        patterns = type_patterns.get(config_type, [])
        
        # Check if key contains any pattern
        key_upper = key.upper()
        return any(pattern in key_upper for pattern in patterns)
    
    def _is_sensitive_key(self, key: str) -> bool:
        """Check if key contains sensitive information"""
        
        sensitive_patterns = [
            'SECRET', 'KEY', 'PASSWORD', 'TOKEN', 'AUTH', 'PRIVATE',
            'CERT', 'CREDENTIAL', 'PASS', 'PWD'
        ]
        
        key_upper = key.upper()
        return any(pattern in key_upper for pattern in sensitive_patterns)
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format"""
        try:
            from urllib.parse import urlparse
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    def _flatten_json(self, data: Dict[str, Any], prefix: str = '') -> Dict[str, Any]:
        """Flatten nested JSON to dot notation"""
        
        result = {}
        
        for key, value in data.items():
            new_key = f"{prefix}{key}".upper() if prefix else key.upper()
            
            if isinstance(value, dict):
                result.update(self._flatten_json(value, f"{new_key}_"))
            elif isinstance(value, list):
                result[new_key] = json.dumps(value)
            else:
                result[new_key] = str(value)
        
        return result
    
    def export_resolved_config(self, config: ResolvedConfig, format: str = 'env') -> str:
        """Export resolved configuration in specified format"""
        
        if format == 'env':
            lines = ['# Resolved Configuration']
            lines.append('# Generated by Configuration Resolver')
            lines.append('')
            
            for key, config_value in sorted(config.values.items()):
                if config_value.is_sensitive:
                    lines.append(f"# {key}=[REDACTED] # Source: {config_value.source.name}")
                else:
                    lines.append(f"{key}={config_value.value}")
            
            return '\n'.join(lines)
            
        elif format == 'json':
            export_data = {
                'values': {
                    key: value.value if not value.is_sensitive else '[REDACTED]'
                    for key, value in config.values.items()
                },
                'metadata': {
                    'sources_loaded': config.sources_loaded,
                    'conflicts_count': len(config.conflicts),
                    'warnings_count': len(config.warnings)
                },
                'conflicts': config.conflicts,
                'warnings': config.warnings
            }
            return json.dumps(export_data, indent=2)
            
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def get_configuration_summary(self, config: ResolvedConfig) -> Dict[str, Any]:
        """Get configuration summary"""
        
        return {
            'total_values': len(config.values),
            'sources_loaded': config.sources_loaded,
            'conflicts': len(config.conflicts),
            'warnings': len(config.warnings),
            'sensitive_keys': sum(1 for v in config.values.values() if v.is_sensitive),
            'source_breakdown': {
                source.name: sum(1 for v in config.values.values() if v.source == source)
                for source in ConfigSource
            },
            'prefix_breakdown': {
                'AIVALIDATION_': sum(1 for k in config.values.keys() if k.startswith('AIVALIDATION_')),
                'REACT_APP_': sum(1 for k in config.values.keys() if k.startswith('REACT_APP_')),
                'VRU_': sum(1 for k in config.values.keys() if k.startswith('VRU_')),
                'Other': sum(1 for k in config.values.keys() 
                           if not any(k.startswith(p) for p in ['AIVALIDATION_', 'REACT_APP_', 'VRU_']))
            }
        }

# Global instance
configuration_resolver = ConfigurationResolver()

# Convenience functions
async def resolve_all_configuration() -> ResolvedConfig:
    """Resolve all configuration"""
    return await configuration_resolver.resolve_configuration()

async def resolve_backend_configuration() -> ResolvedConfig:
    """Resolve backend-specific configuration"""
    return await configuration_resolver.resolve_configuration(ConfigType.BACKEND)

async def resolve_frontend_configuration() -> ResolvedConfig:
    """Resolve frontend-specific configuration"""
    return await configuration_resolver.resolve_configuration(ConfigType.FRONTEND)

async def export_unified_env_file(output_path: str = '.env.unified'):
    """Export unified environment file"""
    config = await resolve_all_configuration()
    content = configuration_resolver.export_resolved_config(config, 'env')
    
    with open(output_path, 'w') as f:
        f.write(content)
    
    logger.info(f"📁 Unified configuration exported to {output_path}")

if __name__ == "__main__":
    # Test configuration resolver
    async def test_configuration_resolver():
        import json
        
        # Resolve all configuration
        config = await resolve_all_configuration()
        
        # Get summary
        summary = configuration_resolver.get_configuration_summary(config)
        
        print("🔧 Configuration Resolution Summary:")
        print(json.dumps(summary, indent=2))
        
        if config.conflicts:
            print(f"\n⚔️ {len(config.conflicts)} Conflicts resolved:")
            for conflict in config.conflicts[:3]:  # Show first 3
                print(f"  - {conflict}")
        
        if config.warnings:
            print(f"\n⚠️ {len(config.warnings)} Warnings:")
            for warning in config.warnings[:3]:  # Show first 3
                print(f"  - {warning}")
        
        # Export unified config
        await export_unified_env_file()
    
    asyncio.run(test_configuration_resolver())