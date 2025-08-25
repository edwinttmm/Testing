#!/usr/bin/env python3
"""
Configuration Verification Script for External IP Access
Verifies all configuration files are properly set up for 155.138.239.131
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Any

def check_file_exists(file_path: str) -> bool:
    """Check if a file exists"""
    return Path(file_path).exists()

def read_file_content(file_path: str) -> str:
    """Read file content safely"""
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except Exception as e:
        return f"ERROR: {str(e)}"

def check_cors_config(content: str, file_name: str) -> Dict[str, Any]:
    """Check CORS configuration in file content"""
    external_ip = "155.138.239.131"
    issues = []
    configs_found = []
    
    # Look for CORS-related configurations
    cors_patterns = [
        r'CORS_ORIGINS.*155\.138\.239\.131',
        r'AIVALIDATION_CORS_ORIGINS.*155\.138\.239\.131',
        r'ALLOWED_ORIGINS.*155\.138\.239\.131',
        r'cors_allowed_origins.*155\.138\.239\.131',
        r'allow_origins.*155\.138\.239\.131'
    ]
    
    for pattern in cors_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            configs_found.append(pattern)
    
    if not configs_found:
        issues.append(f"No CORS configuration found for {external_ip}")
    
    # Check for localhost/127.0.0.1 configurations (should be inclusive)
    has_localhost = 'localhost' in content.lower() or '127.0.0.1' in content
    has_external_ip = external_ip in content
    
    if has_localhost and not has_external_ip:
        issues.append(f"Configuration has localhost but missing {external_ip}")
    
    return {
        'file': file_name,
        'has_external_ip_config': has_external_ip,
        'has_localhost_config': has_localhost,
        'cors_configs_found': len(configs_found),
        'issues': issues,
        'configs': configs_found
    }

def check_api_urls(content: str, file_name: str) -> Dict[str, Any]:
    """Check API URL configurations"""
    external_ip = "155.138.239.131"
    issues = []
    urls_found = []
    
    # Look for API URL patterns
    api_patterns = [
        r'REACT_APP_API_URL.*155\.138\.239\.131',
        r'REACT_APP_WS_URL.*155\.138\.239\.131',
        r'REACT_APP_SOCKETIO_URL.*155\.138\.239\.131',
        r'REACT_APP_VIDEO_BASE_URL.*155\.138\.239\.131'
    ]
    
    for pattern in api_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            urls_found.extend(matches)
    
    has_external_ip_urls = any(external_ip in url for url in urls_found)
    has_localhost_urls = 'localhost' in content.lower() or '127.0.0.1' in content
    
    if has_localhost_urls and not has_external_ip_urls:
        issues.append(f"API URLs reference localhost but not {external_ip}")
    
    return {
        'file': file_name,
        'has_external_ip_urls': has_external_ip_urls,
        'has_localhost_urls': has_localhost_urls,
        'urls_found': len(urls_found),
        'issues': issues,
        'urls': urls_found
    }

def verify_docker_compose_config() -> Dict[str, Any]:
    """Verify Docker Compose configuration"""
    file_path = "docker-compose.yml"
    
    if not check_file_exists(file_path):
        return {'error': 'docker-compose.yml not found'}
    
    content = read_file_content(file_path)
    external_ip = "155.138.239.131"
    
    checks = {
        'has_external_ip_in_environment': external_ip in content,
        'has_cors_origins': 'AIVALIDATION_CORS_ORIGINS' in content or 'ALLOWED_ORIGINS' in content,
        'binds_to_all_interfaces': '0.0.0.0:' in content,
        'issues': []
    }
    
    if not checks['has_external_ip_in_environment']:
        checks['issues'].append(f"No references to {external_ip} found in docker-compose.yml")
    
    if not checks['has_cors_origins']:
        checks['issues'].append("No CORS origins configuration found in docker-compose.yml")
    
    if not checks['binds_to_all_interfaces']:
        checks['issues'].append("Services may not be binding to all interfaces (0.0.0.0)")
    
    return checks

def main():
    print("🔍 AI Model Validation Platform - External IP Configuration Verification")
    print("   Checking configuration for IP: 155.138.239.131")
    print("=" * 70)
    
    # Files to check
    config_files = [
        'backend/.env',
        'backend/.env.production', 
        'frontend/.env',
        'frontend/.env.production',
        '.env.production',
        'docker-compose.yml'
    ]
    
    verification_results = {
        'external_ip': '155.138.239.131',
        'timestamp': str(Path().cwd()),
        'files_checked': [],
        'issues_found': [],
        'recommendations': []
    }
    
    print("📁 Checking configuration files...")
    
    for file_path in config_files:
        full_path = Path(file_path)
        file_exists = full_path.exists()
        
        print(f"\n🔍 Checking: {file_path}")
        print(f"   Exists: {'✅' if file_exists else '❌'}")
        
        file_result = {
            'file': file_path,
            'exists': file_exists,
            'issues': []
        }
        
        if file_exists:
            content = read_file_content(str(full_path))
            
            # Check CORS configuration
            if any(keyword in file_path.lower() for keyword in ['.env', 'docker-compose']):
                cors_check = check_cors_config(content, file_path)
                file_result['cors_check'] = cors_check
                
                if cors_check['issues']:
                    print(f"   CORS Issues: ❌ {len(cors_check['issues'])} issues found")
                    verification_results['issues_found'].extend(cors_check['issues'])
                else:
                    print(f"   CORS Config: ✅ {cors_check['cors_configs_found']} configurations found")
            
            # Check API URLs for frontend files
            if 'frontend' in file_path or 'docker-compose' in file_path:
                api_check = check_api_urls(content, file_path)
                file_result['api_check'] = api_check
                
                if api_check['issues']:
                    print(f"   API URLs: ❌ {len(api_check['issues'])} issues found")
                    verification_results['issues_found'].extend(api_check['issues'])
                else:
                    print(f"   API URLs: ✅ {api_check['urls_found']} URLs configured")
        else:
            file_result['issues'].append(f"File {file_path} does not exist")
            verification_results['issues_found'].append(f"Missing file: {file_path}")
        
        verification_results['files_checked'].append(file_result)
    
    # Special check for Docker Compose
    print(f"\n🐳 Docker Compose Configuration...")
    docker_check = verify_docker_compose_config()
    verification_results['docker_compose'] = docker_check
    
    if docker_check.get('issues'):
        print(f"   Docker Issues: ❌ {len(docker_check['issues'])} issues found")
        verification_results['issues_found'].extend(docker_check['issues'])
    else:
        print(f"   Docker Config: ✅ Properly configured")
    
    # Generate recommendations
    if verification_results['issues_found']:
        print(f"\n⚠️  Configuration Issues Found:")
        for i, issue in enumerate(verification_results['issues_found'], 1):
            print(f"   {i}. {issue}")
        
        verification_results['recommendations'] = [
            "Ensure all .env files include CORS origins for 155.138.239.131",
            "Update API URLs to use external IP address",
            "Verify Docker Compose binds to 0.0.0.0 for external access",
            "Test CORS headers with external IP origins",
            "Check firewall settings on server"
        ]
        
        print(f"\n💡 Recommendations:")
        for i, rec in enumerate(verification_results['recommendations'], 1):
            print(f"   {i}. {rec}")
    else:
        print(f"\n✅ All configuration files are properly set up for external IP access!")
    
    # Summary
    print(f"\n" + "=" * 70)
    print(f"📊 VERIFICATION SUMMARY")
    print(f"=" * 70)
    print(f"📁 Files Checked: {len([f for f in verification_results['files_checked'] if f['exists']])}/{len(config_files)}")
    print(f"⚠️  Issues Found: {len(verification_results['issues_found'])}")
    print(f"🎯 External IP: {'✅ Configured' if not verification_results['issues_found'] else '❌ Needs Attention'}")
    
    # Save results
    with open('external-ip-config-verification.json', 'w') as f:
        json.dump(verification_results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: external-ip-config-verification.json")
    
    return len(verification_results['issues_found']) == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)