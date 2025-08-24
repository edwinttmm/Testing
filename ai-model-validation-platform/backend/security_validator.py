"""
Security Configuration Validator for AI Model Validation Platform.

This module provides comprehensive security validation that runs at startup
to ensure the application is properly configured for the target environment.
"""

import os
import sys
import logging
import re
import urllib.parse
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import secrets
import hashlib

from config import Settings, get_settings

logger = logging.getLogger(__name__)

class SecurityValidationError(Exception):
    """Raised when critical security validation fails"""
    pass

class SecurityValidator:
    """
    Comprehensive security configuration validator.
    
    Performs startup-time validation of security configurations to ensure
    the application is properly secured for its target environment.
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.warnings: List[str] = []
        self.errors: List[str] = []
        self.recommendations: List[str] = []
    
    def validate_all(self) -> Tuple[bool, List[str], List[str], List[str]]:
        """
        Run all security validations.
        
        Returns:
            Tuple of (is_valid, errors, warnings, recommendations)
        """
        self.warnings.clear()
        self.errors.clear()
        self.recommendations.clear()
        
        # Run all validation checks
        self._validate_secret_keys()
        self._validate_database_security()
        self._validate_api_security()
        self._validate_cors_configuration()
        self._validate_file_upload_security()
        self._validate_logging_security()
        self._validate_production_requirements()
        self._validate_environment_consistency()
        self._validate_ssl_configuration()
        self._validate_dependencies()
        
        is_valid = len(self.errors) == 0
        
        # Log validation results
        if is_valid:
            logger.info("Security validation passed")
        else:
            logger.error(f"Security validation failed with {len(self.errors)} errors")
        
        if self.warnings:
            logger.warning(f"Security validation found {len(self.warnings)} warnings")
        
        return is_valid, self.errors.copy(), self.warnings.copy(), self.recommendations.copy()
    
    def _validate_secret_keys(self) -> None:
        """Validate all secret keys and cryptographic settings"""
        
        # Check main secret key
        if not self.settings.secret_key or len(self.settings.secret_key) < 32:
            self.errors.append("SECRET_KEY must be at least 32 characters long")
        
        # Check for insecure default keys
        insecure_keys = [
            "your-secret-key-change-in-production",
            "INSECURE-DEFAULT-CHANGE-ME", 
            "your-secret-key-here-development-only",
            "REPLACE-WITH-SECURE-32-CHAR-RANDOM-STRING",
            "GENERATE_SECURE_KEY_FOR_PRODUCTION",
            "dev-secret-key-not-for-production-use-only"
        ]
        
        if self.settings.secret_key in insecure_keys:
            if self.settings.app_environment.lower() == 'production':
                self.errors.append(f"CRITICAL: Using insecure default SECRET_KEY in production: {self.settings.secret_key}")
            else:
                self.warnings.append("Using default SECRET_KEY - change for production deployment")
        
        # Check key entropy (basic check)
        if self._is_weak_key(self.settings.secret_key):
            self.warnings.append("SECRET_KEY appears to have low entropy - consider using secrets.token_urlsafe(32)")
        
        # Check JWT secret key
        if hasattr(self.settings, 'jwt_secret_key'):
            if self.settings.jwt_secret_key == self.settings.secret_key:
                self.recommendations.append("Consider using separate JWT_SECRET_KEY from main SECRET_KEY")
    
    def _validate_database_security(self) -> None:
        """Validate database security configuration"""
        
        db_url = self.settings.database_url.lower()
        
        # Check database type vs environment
        if "sqlite" in db_url:
            if self.settings.app_environment.lower() == 'production':
                self.warnings.append("Using SQLite in production - consider PostgreSQL for better performance and security")
            else:
                logger.info("Using SQLite for development (OK)")
        
        # Check for credentials in database URL
        if "postgresql://" in db_url or "mysql://" in db_url:
            parsed = urllib.parse.urlparse(self.settings.database_url)
            
            if parsed.password:
                # Check for weak passwords
                if len(parsed.password) < 8:
                    self.warnings.append("Database password is less than 8 characters")
                
                if parsed.password in ["password", "123456", "admin", "root"]:
                    self.errors.append(f"Database using weak password: {parsed.password}")
            
            # Check SSL mode for production
            if self.settings.app_environment.lower() == 'production':
                if not hasattr(self.settings, 'database_sslmode') or self.settings.database_sslmode != 'require':
                    self.warnings.append("Database SSL not required in production - consider setting sslmode=require")
    
    def _validate_api_security(self) -> None:
        """Validate API security configuration"""
        
        # Check if API is bound to all interfaces
        if self.settings.api_host == "0.0.0.0":
            if self.settings.app_environment.lower() == 'production':
                self.warnings.append("API bound to all interfaces (0.0.0.0) in production - ensure firewall is configured")
        
        # Check debug mode
        if self.settings.api_debug:
            if self.settings.app_environment.lower() == 'production':
                self.errors.append("CRITICAL: Debug mode enabled in production")
            else:
                logger.info("Debug mode enabled for development")
        
        # Check base URL protocol
        if hasattr(self.settings, 'api_base_url'):
            if self.settings.api_base_url.startswith('http://') and self.settings.app_environment.lower() == 'production':
                self.warnings.append("Using HTTP in production - consider HTTPS for security")
    
    def _validate_cors_configuration(self) -> None:
        """Validate CORS security configuration"""
        
        if not self.settings.cors_origins:
            self.warnings.append("No CORS origins configured - this may block legitimate requests")
            return
        
        # Check for overly permissive CORS
        dangerous_origins = ["*", "null", "localhost", "127.0.0.1"]
        
        for origin in self.settings.cors_origins:
            origin = origin.strip()
            
            if origin == "*":
                if self.settings.app_environment.lower() == 'production':
                    self.errors.append("CRITICAL: CORS allows all origins (*) in production")
                else:
                    self.warnings.append("CORS allows all origins (*) - restrict for production")
            
            if origin.startswith("http://") and self.settings.app_environment.lower() == 'production':
                self.warnings.append(f"CORS origin uses HTTP in production: {origin}")
    
    def _validate_file_upload_security(self) -> None:
        """Validate file upload security settings"""
        
        # Check maximum file size
        max_size_mb = self.settings.max_file_size / (1024 * 1024)
        
        if max_size_mb > 1000:  # 1GB
            self.warnings.append(f"Very large max file size ({max_size_mb:.1f}MB) may cause memory issues")
        
        if max_size_mb > 100 and self.settings.app_environment.lower() == 'production':
            self.recommendations.append(f"Consider reducing max file size ({max_size_mb:.1f}MB) for production")
        
        # Check upload directory
        upload_path = Path(self.settings.upload_directory)
        
        if upload_path.is_absolute():
            # Absolute path - check if it's secure
            if not str(upload_path).startswith(('/var/', '/opt/', '/srv/')):
                self.warnings.append(f"Upload directory outside standard locations: {upload_path}")
        else:
            # Relative path - ensure it's not going up directories
            if '..' in str(upload_path):
                self.errors.append(f"Upload directory contains '..' - potential security risk: {upload_path}")
        
        # Check allowed extensions
        if hasattr(self.settings, 'allowed_video_extensions'):
            dangerous_extensions = ['.exe', '.bat', '.sh', '.py', '.js', '.html', '.php']
            
            for ext in self.settings.allowed_video_extensions:
                if ext.lower() in dangerous_extensions:
                    self.warnings.append(f"Potentially dangerous file extension allowed: {ext}")
    
    def _validate_logging_security(self) -> None:
        """Validate logging configuration security"""
        
        # Check log level
        if self.settings.log_level.upper() == 'DEBUG':
            if self.settings.app_environment.lower() == 'production':
                self.warnings.append("DEBUG logging enabled in production - may expose sensitive information")
        
        # Check log file location
        if self.settings.log_file:
            log_path = Path(self.settings.log_file)
            
            if not log_path.parent.exists():
                self.warnings.append(f"Log directory does not exist: {log_path.parent}")
            
            # Check if log file is in web-accessible location
            web_paths = ['static', 'public', 'www', 'html']
            if any(part in str(log_path).lower() for part in web_paths):
                self.errors.append(f"Log file in potentially web-accessible location: {log_path}")
    
    def _validate_production_requirements(self) -> None:
        """Validate production-specific security requirements"""
        
        if self.settings.app_environment.lower() != 'production':
            return
        
        # HTTPS requirements
        if hasattr(self.settings, 'ssl_enabled') and not self.settings.ssl_enabled:
            self.warnings.append("SSL/TLS not enabled in production")
        
        # Security headers
        if hasattr(self.settings, 'security_headers_enabled') and not self.settings.security_headers_enabled:
            self.warnings.append("Security headers not enabled in production")
        
        # HSTS
        if hasattr(self.settings, 'hsts_enabled') and not self.settings.hsts_enabled:
            self.recommendations.append("Enable HSTS for HTTPS deployments")
        
        # Content Security Policy
        if hasattr(self.settings, 'csp_enabled') and not self.settings.csp_enabled:
            self.recommendations.append("Enable Content Security Policy for better security")
        
        # Feature flags
        if self.settings.api_reload:
            self.errors.append("Auto-reload enabled in production - disable for security")
        
        # Caching
        if hasattr(self.settings, 'enable_caching') and not self.settings.enable_caching:
            self.recommendations.append("Enable caching for better production performance")
    
    def _validate_environment_consistency(self) -> None:
        """Validate consistency between environment settings"""
        
        # Check environment variable consistency
        env_var = os.getenv('APP_ENV', os.getenv('AIVALIDATION_APP_ENVIRONMENT', 'development'))
        
        if env_var.lower() != self.settings.app_environment.lower():
            self.warnings.append(f"Environment mismatch: env={env_var}, config={self.settings.app_environment}")
        
        # Check debug consistency
        if self.settings.app_environment.lower() == 'production' and self.settings.api_debug:
            self.errors.append("Debug mode enabled in production environment")
    
    def _validate_ssl_configuration(self) -> None:
        """Validate SSL/TLS configuration"""
        
        if not hasattr(self.settings, 'ssl_enabled'):
            return
        
        if self.settings.ssl_enabled:
            # Check certificate files
            if hasattr(self.settings, 'ssl_cert_file') and self.settings.ssl_cert_file:
                cert_path = Path(self.settings.ssl_cert_file)
                if not cert_path.exists():
                    self.errors.append(f"SSL certificate file not found: {cert_path}")
                else:
                    # Check file permissions
                    if cert_path.stat().st_mode & 0o077:
                        self.warnings.append(f"SSL certificate file has overly permissive permissions: {cert_path}")
            
            if hasattr(self.settings, 'ssl_key_file') and self.settings.ssl_key_file:
                key_path = Path(self.settings.ssl_key_file)
                if not key_path.exists():
                    self.errors.append(f"SSL private key file not found: {key_path}")
                else:
                    # Check key file permissions (should be 600)
                    mode = key_path.stat().st_mode & 0o777
                    if mode != 0o600:
                        self.warnings.append(f"SSL private key should have 600 permissions, has {oct(mode)}: {key_path}")
    
    def _validate_dependencies(self) -> None:
        """Validate security-related dependencies"""
        
        try:
            import jwt
            import passlib
            import cryptography
        except ImportError as e:
            self.errors.append(f"Required security dependency missing: {e}")
        
        # Check for development dependencies in production
        if self.settings.app_environment.lower() == 'production':
            dev_modules = ['pytest', 'debugpy', 'ipdb']
            
            for module in dev_modules:
                try:
                    __import__(module)
                    self.warnings.append(f"Development dependency found in production: {module}")
                except ImportError:
                    pass  # Good, dev dependency not installed
    
    def _is_weak_key(self, key: str) -> bool:
        """Check if a key has weak entropy"""
        if len(key) < 32:
            return True
        
        # Check for repeating patterns
        if len(set(key)) < len(key) * 0.5:
            return True
        
        # Check for common patterns
        if re.search(r'(.)\1{3,}', key):  # 4+ consecutive identical characters
            return True
        
        return False

def validate_security_configuration(settings: Optional[Settings] = None) -> None:
    """
    Main entry point for security validation.
    
    Raises SecurityValidationError if critical security issues are found.
    """
    if settings is None:
        settings = get_settings()
    
    validator = SecurityValidator(settings)
    is_valid, errors, warnings, recommendations = validator.validate_all()
    
    # Log all findings
    for error in errors:
        logger.error(f"SECURITY ERROR: {error}")
    
    for warning in warnings:
        logger.warning(f"SECURITY WARNING: {warning}")
    
    for recommendation in recommendations:
        logger.info(f"SECURITY RECOMMENDATION: {recommendation}")
    
    # Raise exception for critical errors in production
    if errors and settings.app_environment.lower() == 'production':
        error_summary = "; ".join(errors[:3])  # Show first 3 errors
        if len(errors) > 3:
            error_summary += f" (and {len(errors) - 3} more)"
        
        raise SecurityValidationError(
            f"Critical security configuration errors found: {error_summary}"
        )
    
    # Log summary
    if is_valid:
        logger.info("✅ Security validation passed")
    else:
        logger.warning(f"⚠️ Security validation completed with {len(errors)} errors and {len(warnings)} warnings")
    
    return is_valid, errors, warnings, recommendations

def generate_security_report(settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Generate a comprehensive security configuration report"""
    if settings is None:
        settings = get_settings()
    
    validator = SecurityValidator(settings)
    is_valid, errors, warnings, recommendations = validator.validate_all()
    
    return {
        'timestamp': os.environ.get('TZ', 'UTC'),
        'environment': settings.app_environment,
        'validation_passed': is_valid,
        'summary': {
            'errors': len(errors),
            'warnings': len(warnings),
            'recommendations': len(recommendations)
        },
        'findings': {
            'errors': errors,
            'warnings': warnings,
            'recommendations': recommendations
        },
        'configuration': {
            'secret_key_length': len(settings.secret_key) if settings.secret_key else 0,
            'database_type': 'sqlite' if 'sqlite' in settings.database_url.lower() else 'postgresql',
            'ssl_enabled': getattr(settings, 'ssl_enabled', False),
            'security_headers': getattr(settings, 'security_headers_enabled', False),
            'debug_mode': settings.api_debug,
            'cors_origins_count': len(settings.cors_origins) if settings.cors_origins else 0
        }
    }

# CLI command for security validation
def main():
    """Command-line interface for security validation"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Validate security configuration')
    parser.add_argument('--report', action='store_true', help='Generate JSON security report')
    parser.add_argument('--strict', action='store_true', help='Treat warnings as errors')
    
    args = parser.parse_args()
    
    try:
        settings = get_settings()
        
        if args.report:
            report = generate_security_report(settings)
            print(json.dumps(report, indent=2))
            return
        
        is_valid, errors, warnings, recommendations = validate_security_configuration(settings)
        
        if errors or (args.strict and warnings):
            sys.exit(1)
        else:
            print("✅ Security validation passed")
            sys.exit(0)
            
    except SecurityValidationError as e:
        print(f"❌ Security validation failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Validation error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()