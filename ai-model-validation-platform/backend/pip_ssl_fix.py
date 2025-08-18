#!/usr/bin/env python3
"""
SSL Certificate Fix for Docker pip installations
Handles SSL certificate verification failures in Docker containers
"""
import subprocess
import sys
import os
import logging

logger = logging.getLogger(__name__)

def fix_ssl_certificates():
    """Fix SSL certificate issues in Docker environments"""
    try:
        # Update CA certificates
        subprocess.run(['apt-get', 'update'], check=False, capture_output=True)
        subprocess.run(['apt-get', 'install', '-y', 'ca-certificates'], check=False, capture_output=True)
        
        # Configure pip to trust common hosts
        trusted_hosts = [
            "pypi.org",
            "pypi.python.org", 
            "files.pythonhosted.org",
            "download.pytorch.org"
        ]
        
        for host in trusted_hosts:
            subprocess.run([sys.executable, '-m', 'pip', 'config', 'set', 'global.trusted-host', host], 
                         check=False, capture_output=True)
        
        # Set environment variables
        os.environ['PIP_TRUSTED_HOST'] = " ".join(trusted_hosts)
        os.environ['PYTHONHTTPSVERIFY'] = '0'
        
        logger.info("✅ SSL certificate fixes applied")
        return True
        
    except Exception as e:
        logger.warning(f"⚠️  Could not apply SSL fixes: {e}")
        return False

if __name__ == "__main__":
    fix_ssl_certificates()