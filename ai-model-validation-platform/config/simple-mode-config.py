"""
Simple Mode Configuration Handler
Ensures consistent database credentials between Docker containers and backend
"""

import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SimpleModeConfig:
    """Configuration handler for simple development mode"""
    
    # Docker container database credentials (must match docker-compose.simple.yml)
    DOCKER_DB_CREDENTIALS = {
        'host': 'postgres',
        'port': '5432',
        'database': 'vru_validation',
        'username': 'postgres', 
        'password': 'password'
    }
    
    # External access credentials (for local development tools)
    EXTERNAL_DB_CREDENTIALS = {
        'host': 'localhost',
        'port': '5432',
        'database': 'vru_validation',
        'username': 'postgres',
        'password': 'password'
    }
    
    def __init__(self):
        self.is_docker = self._detect_docker_environment()
        self.db_creds = self.DOCKER_DB_CREDENTIALS if self.is_docker else self.EXTERNAL_DB_CREDENTIALS
    
    def _detect_docker_environment(self) -> bool:
        """Detect if running inside Docker container"""
        # Check for Docker-specific environment variables
        docker_indicators = [
            os.getenv('DOCKER_MODE') == 'true',
            os.getenv('AIVALIDATION_DOCKER_MODE') == 'true', 
            os.path.exists('/.dockerenv'),
            os.getenv('HOSTNAME', '').startswith('docker-'),
        ]
        return any(docker_indicators)
    
    def get_database_url(self) -> str:
        """Get the appropriate database URL based on environment"""
        creds = self.db_creds
        database_url = f"postgresql://{creds['username']}:{creds['password']}@{creds['host']}:{creds['port']}/{creds['database']}"
        
        logger.info(f"Using database URL for {'Docker' if self.is_docker else 'External'} environment")
        return database_url
    
    def get_redis_url(self) -> str:
        """Get the appropriate Redis URL based on environment"""
        if self.is_docker:
            return "redis://redis:6379"
        else:
            return "redis://localhost:6379"
    
    def apply_environment_variables(self) -> None:
        """Apply simple mode environment variables"""
        env_vars = {
            'DATABASE_URL': self.get_database_url(),
            'AIVALIDATION_DATABASE_URL': self.get_database_url(),
            'VRU_DATABASE_URL': self.get_database_url(),
            'REDIS_URL': self.get_redis_url(),
            'AIVALIDATION_REDIS_URL': self.get_redis_url(),
            'ENVIRONMENT': 'development',
            'DEBUG': 'true',
            'LOG_LEVEL': 'DEBUG',
        }
        
        for key, value in env_vars.items():
            if not os.getenv(key):
                os.environ[key] = value
                logger.debug(f"Set environment variable: {key}")
        
        logger.info("Simple mode environment variables applied")
    
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate that configuration is correct for simple mode"""
        validation_results = {
            'status': 'valid',
            'environment': 'docker' if self.is_docker else 'external',
            'database_host': self.db_creds['host'],
            'database_name': self.db_creds['database'],
            'issues': []
        }
        
        # Check if environment variables match expected simple mode values
        expected_db_url = self.get_database_url()
        actual_db_url = os.getenv('DATABASE_URL') or os.getenv('AIVALIDATION_DATABASE_URL')
        
        if actual_db_url != expected_db_url:
            validation_results['issues'].append({
                'type': 'database_url_mismatch',
                'expected': expected_db_url,
                'actual': actual_db_url
            })
            validation_results['status'] = 'invalid'
        
        # Check Redis configuration
        expected_redis_url = self.get_redis_url()
        actual_redis_url = os.getenv('REDIS_URL') or os.getenv('AIVALIDATION_REDIS_URL')
        
        if actual_redis_url != expected_redis_url:
            validation_results['issues'].append({
                'type': 'redis_url_mismatch', 
                'expected': expected_redis_url,
                'actual': actual_redis_url
            })
            validation_results['status'] = 'invalid'
        
        return validation_results
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information for troubleshooting"""
        return {
            'environment': 'docker' if self.is_docker else 'external',
            'database_url': self.get_database_url(),
            'redis_url': self.get_redis_url(),
            'credentials': {
                'database_host': self.db_creds['host'],
                'database_name': self.db_creds['database'],
                'database_user': self.db_creds['username'],
                'database_port': self.db_creds['port']
            }
        }

# Global simple mode configuration instance
simple_config = SimpleModeConfig()

def initialize_simple_mode():
    """Initialize simple mode configuration"""
    logger.info("Initializing simple development mode configuration")
    simple_config.apply_environment_variables()
    
    validation = simple_config.validate_configuration()
    if validation['status'] != 'valid':
        logger.warning(f"Configuration issues detected: {validation['issues']}")
    else:
        logger.info("Simple mode configuration validated successfully")
    
    return simple_config

def get_simple_mode_info():
    """Get simple mode configuration information"""
    return simple_config.get_connection_info()