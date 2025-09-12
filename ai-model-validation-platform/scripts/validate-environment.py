#!/usr/bin/env python3
"""
Environment Variable Resolution Validator
This script validates that all environment variables are properly resolved
and there are no conflicts between different naming conventions.
"""

import os
import sys
from dotenv import load_dotenv

def main():
    """Main validation function"""
    print("=" * 70)
    print("AI MODEL VALIDATION PLATFORM - ENVIRONMENT VALIDATOR")
    print("=" * 70)
    
    # Load environment variables
    env_file = '.env'
    if not os.path.exists(env_file):
        print(f"❌ Environment file {env_file} not found!")
        return False
    
    load_dotenv(env_file, override=True)
    print(f"✅ Loaded environment variables from {env_file}")
    
    # Define critical variable groups
    validation_groups = {
        'Database Configuration': {
            'primary': 'VRU_DATABASE_URL',
            'aliases': ['DATABASE_URL', 'AIVALIDATION_DATABASE_URL'],
            'required': True
        },
        'Redis Configuration': {
            'primary': 'VRU_REDIS_URL', 
            'aliases': ['REDIS_URL', 'AIVALIDATION_REDIS_URL'],
            'required': True
        },
        'Security Configuration': {
            'primary': 'VRU_SECRET_KEY',
            'aliases': ['AIVALIDATION_SECRET_KEY', 'SECRET_KEY'],
            'required': True
        },
        'API Configuration': {
            'primary': 'VRU_API_HOST',
            'aliases': ['AIVALIDATION_API_HOST', 'API_HOST'],
            'required': True
        },
        'Environment Settings': {
            'primary': 'VRU_ENVIRONMENT',
            'aliases': ['AIVALIDATION_APP_ENVIRONMENT', 'APP_ENV'],
            'required': True
        }
    }
    
    all_passed = True
    
    for group_name, config in validation_groups.items():
        print(f"\n📋 {group_name}:")
        
        primary_var = config['primary']
        primary_value = os.getenv(primary_var)
        
        if not primary_value:
            if config['required']:
                print(f"  ❌ Primary variable {primary_var} is missing!")
                all_passed = False
            else:
                print(f"  ⚠️  Primary variable {primary_var} is optional and not set")
            continue
        
        # Mask sensitive information
        masked_value = mask_sensitive_info(primary_value)
        print(f"  ✅ {primary_var}: {masked_value}")
        
        # Check aliases resolve to same value
        for alias in config['aliases']:
            alias_value = os.getenv(alias)
            if alias_value:
                if resolve_variable_reference(alias_value) == resolve_variable_reference(primary_value):
                    print(f"  ✅ {alias}: matches primary")
                else:
                    print(f"  ❌ {alias}: MISMATCH - {mask_sensitive_info(alias_value)}")
                    all_passed = False
            else:
                print(f"  ⚠️  {alias}: not set")
    
    # Docker-specific validation
    print(f"\n🐳 Docker Configuration:")
    docker_vars = [
        ('POSTGRES_DB', 'VRU_DATABASE_NAME'),
        ('POSTGRES_USER', 'VRU_DATABASE_USER'), 
        ('COMPOSE_PROJECT_NAME', None)
    ]
    
    for docker_var, vru_equivalent in docker_vars:
        value = os.getenv(docker_var)
        if value:
            print(f"  ✅ {docker_var}: {value}")
            
            if vru_equivalent:
                vru_value = os.getenv(vru_equivalent)
                if vru_value and value != vru_value:
                    print(f"  ❌ {docker_var} doesn't match {vru_equivalent}")
                    all_passed = False
        else:
            print(f"  ❌ {docker_var}: missing")
            all_passed = False
    
    # Final summary
    print(f"\n" + "=" * 70)
    if all_passed:
        print("🎉 ALL ENVIRONMENT VARIABLES VALIDATED SUCCESSFULLY!")
        print("✅ No conflicts detected")
        print("✅ All services will use consistent configuration")
        print("✅ Database and Redis connections standardized")
        return True
    else:
        print("❌ ENVIRONMENT VALIDATION FAILED!")
        print("🔧 Please fix the issues above before deployment")
        return False

def mask_sensitive_info(value):
    """Mask sensitive information in environment variable values"""
    if not value:
        return value
    
    # Mask passwords and secrets
    masked = value
    sensitive_patterns = [
        'password', 'Password', 'PASSWORD',
        'secret', 'Secret', 'SECRET', 
        'secure_', 'key-2024'
    ]
    
    for pattern in sensitive_patterns:
        if pattern in masked:
            masked = masked.replace(pattern, '***')
    
    return masked

def resolve_variable_reference(value):
    """Resolve ${VAR} references in environment variable values"""
    if not value:
        return value
    
    if value.startswith('${') and value.endswith('}'):
        ref_var = value[2:-1]
        return os.getenv(ref_var, value)
    
    return value

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)