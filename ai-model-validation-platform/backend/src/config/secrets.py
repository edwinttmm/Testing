"""
Centralized Secret Management System
Replaces hardcoded secrets with secure configuration management
"""

import os
import secrets
import logging
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from pathlib import Path

logger = logging.getLogger(__name__)

class SecretManager:
    """
    Centralized secret management with multiple backend support
    
    Supports:
    - Environment variables (primary)
    - Encrypted files (future enhancement)
    - Development defaults (dev/test only)
    """
    
    def __init__(self):
        self.environment = self._detect_environment()
        self.encryption_key = self._get_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key) if self.encryption_key else None
        self._secret_cache: Dict[str, str] = {}
        
        logger.info(f"SecretManager initialized for environment: {self.environment}")
    
    def _detect_environment(self) -> str:
        """Detect current environment"""
        env_indicators = [
            os.getenv('AIVALIDATION_APP_ENVIRONMENT'),
            os.getenv('APP_ENV'),
            os.getenv('ENVIRONMENT'),
            os.getenv('NODE_ENV'),
            os.getenv('FLASK_ENV')
        ]
        
        for env in env_indicators:
            if env:
                env_lower = env.lower()
                if env_lower in ['production', 'prod']:
                    return 'production'
                elif env_lower in ['staging', 'stage', 'test']:
                    return 'staging'
                elif env_lower in ['development', 'dev', 'local']:
                    return 'development'
        
        # Default to development if not specified
        return 'development'
    
    def _get_encryption_key(self) -> Optional[bytes]:
        """Get encryption key for secret files (future enhancement)"""
        key_env = os.getenv('SECRET_ENCRYPTION_KEY')
        if key_env:
            try:
                return key_env.encode()
            except Exception as e:
                logger.warning(f"Invalid encryption key format: {e}")
        return None
    
    def get_secret(self, key: str, default: Optional[str] = None, required: bool = True) -> str:
        """
        Get secret with fallback hierarchy
        
        Args:
            key: Secret key name
            default: Default value (only used in dev/test)
            required: Whether secret is required
            
        Returns:
            Secret value
            
        Raises:
            ValueError: If required secret not found
        """
        # Check cache first
        if key in self._secret_cache:
            return self._secret_cache[key]
        
        # 1. Environment variable (primary source)
        value = self._get_from_environment(key)
        if value:
            self._secret_cache[key] = value
            return value
        
        # 2. Encrypted secrets file (future enhancement)
        value = self._get_from_encrypted_file(key)
        if value:
            self._secret_cache[key] = value
            return value
        
        # 3. Development defaults (dev/test only)
        if default and not self._is_production():
            logger.warning(f"Using default value for secret '{key}' in {self.environment} environment")
            self._secret_cache[key] = default
            return default
        
        # 4. Handle missing required secrets
        if required:
            error_msg = f"Required secret '{key}' not found"
            if self._is_production():
                error_msg += " - production environment requires all secrets to be configured"
            else:
                error_msg += f" - set environment variable {key} or provide default"
            
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        return ""
    
    def _get_from_environment(self, key: str) -> Optional[str]:
        """Get secret from environment variables with multiple naming patterns"""
        # Try multiple environment variable patterns
        env_patterns = [
            key,  # Exact key
            f"AIVALIDATION_{key}",  # Project-prefixed
            f"VRU_{key}",  # Legacy prefix
            key.upper(),  # Uppercase
            key.lower(),  # Lowercase
        ]
        
        for pattern in env_patterns:
            value = os.getenv(pattern)
            if value:
                logger.debug(f"Found secret '{key}' in environment variable '{pattern}'")
                return value
        
        return None
    
    def _get_from_encrypted_file(self, key: str) -> Optional[str]:
        """Get secret from encrypted file (future enhancement)"""
        if not self.cipher_suite:
            return None
        
        try:
            secrets_file = Path.home() / '.aivalidation' / 'secrets.enc'
            if not secrets_file.exists():
                return None
            
            # Implementation for encrypted secrets file
            # This is a placeholder for future enhancement
            logger.debug(f"Encrypted secrets file not yet implemented")
            return None
            
        except Exception as e:
            logger.warning(f"Failed to read encrypted secrets file: {e}")
            return None
    
    def generate_secret_key(self, length: int = 32) -> str:
        """Generate cryptographically secure secret"""
        return secrets.token_urlsafe(length)
    
    def generate_all_secrets(self) -> Dict[str, str]:
        """Generate all required secrets for initial setup"""
        required_secrets = {
            'SECRET_KEY': self.generate_secret_key(32),
            'JWT_SECRET_KEY': self.generate_secret_key(32),
            'SERVICE_TOKEN': self.generate_secret_key(48),
            'ENCRYPTION_KEY': Fernet.generate_key().decode(),
        }
        
        return required_secrets
    
    def validate_secrets(self) -> Dict[str, Any]:
        """Validate all configured secrets"""
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'secrets_checked': []
        }
        
        # Required secrets for production
        required_secrets = [
            'SECRET_KEY',
            'JWT_SECRET_KEY', 
            'SERVICE_TOKEN'
        ]
        
        # Optional secrets
        optional_secrets = [
            'DATABASE_PASSWORD',
            'REDIS_PASSWORD',
            'ENCRYPTION_KEY'
        ]
        
        # Check required secrets
        for secret_key in required_secrets:
            try:
                value = self.get_secret(secret_key, required=False)
                if not value:
                    validation_results['errors'].append(f"Missing required secret: {secret_key}")
                    validation_results['valid'] = False
                elif len(value) < 16:
                    validation_results['warnings'].append(f"Secret '{secret_key}' is shorter than recommended (16+ chars)")
                elif value in ['INSECURE-DEFAULT-CHANGE-ME', 'your-secret-key-here', 'change-me']:
                    validation_results['errors'].append(f"Secret '{secret_key}' uses insecure default value")
                    validation_results['valid'] = False
                else:
                    validation_results['secrets_checked'].append(secret_key)
            except Exception as e:
                validation_results['errors'].append(f"Error checking secret '{secret_key}': {e}")
                validation_results['valid'] = False
        
        # Check optional secrets
        for secret_key in optional_secrets:
            try:
                value = self.get_secret(secret_key, required=False)
                if value:
                    validation_results['secrets_checked'].append(f"{secret_key} (optional)")
            except Exception as e:
                validation_results['warnings'].append(f"Issue with optional secret '{secret_key}': {e}")
        
        return validation_results
    
    def _is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment.lower() in ['production', 'prod']
    
    def get_environment(self) -> str:
        """Get current environment"""
        return self.environment
    
    def clear_cache(self):
        """Clear secret cache (useful for testing)"""
        self._secret_cache.clear()
        logger.debug("Secret cache cleared")
    
    def export_template(self, include_values: bool = False) -> str:
        """Export environment template for deployment"""
        required_secrets = [
            ('SECRET_KEY', 'Main application secret key'),
            ('JWT_SECRET_KEY', 'JWT token signing key'),  
            ('SERVICE_TOKEN', 'Service authentication token'),
            ('DATABASE_PASSWORD', 'Database password'),
            ('REDIS_PASSWORD', 'Redis password (optional)'),
        ]
        
        lines = [
            "# AI Validation Platform - Environment Configuration",
            "# Generated secret template",
            "# SECURITY WARNING: Replace all values before deployment",
            "",
        ]
        
        for key, description in required_secrets:
            lines.append(f"# {description}")
            if include_values and not self._is_production():
                try:
                    value = self.get_secret(key, required=False)
                    if value:
                        lines.append(f"{key}={value}")
                    else:
                        lines.append(f"{key}=REQUIRED-GENERATE-SECURE-VALUE")
                except:
                    lines.append(f"{key}=REQUIRED-GENERATE-SECURE-VALUE")
            else:
                lines.append(f"{key}=REQUIRED-GENERATE-SECURE-VALUE")
            lines.append("")
        
        return "\n".join(lines)

# Global instance
secret_manager = SecretManager()

# Convenience functions for common patterns
def get_secret(key: str, default: Optional[str] = None, required: bool = True) -> str:
    """Convenience function to get secret"""
    return secret_manager.get_secret(key, default, required)

def generate_secret(length: int = 32) -> str:
    """Convenience function to generate secret"""
    return secret_manager.generate_secret_key(length)

def validate_all_secrets() -> Dict[str, Any]:
    """Convenience function to validate all secrets"""
    return secret_manager.validate_secrets()

# Export template generation
def generate_env_template(environment: str = 'development') -> str:
    """Generate environment template file"""
    include_values = environment in ['development', 'test']
    return secret_manager.export_template(include_values)