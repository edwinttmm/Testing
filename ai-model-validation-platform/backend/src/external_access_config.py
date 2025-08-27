#!/usr/bin/env python3
"""
External Access Configuration for VRU API
SPARC Implementation: External IP configuration and access management

This module configures external access for the VRU API system:
- External IP configuration (155.138.239.131)
- Network access control and security
- Firewall and routing configuration
- SSL/TLS certificate management
- Load balancing configuration
- Performance optimization for external access

Architecture:
- NetworkAccessManager: Manages network access configuration
- FirewallManager: Handles firewall rules and security
- LoadBalancerConfig: Configures load balancing
- SSLManager: Manages SSL/TLS certificates
- PerformanceOptimizer: Optimizes for external access
"""

import logging
import asyncio
import json
import subprocess
import socket
import ssl
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import ipaddress
import platform

logger = logging.getLogger(__name__)

class AccessLevel(Enum):
    """Network access levels"""
    PUBLIC = "public"
    RESTRICTED = "restricted" 
    PRIVATE = "private"
    VPN_ONLY = "vpn_only"

class ProtocolType(Enum):
    """Network protocol types"""
    HTTP = "http"
    HTTPS = "https"
    WEBSOCKET = "ws"
    WEBSOCKET_SECURE = "wss"
    TCP = "tcp"
    UDP = "udp"

@dataclass
class NetworkRule:
    """Network access rule"""
    rule_id: str
    source_ip: str
    destination_port: int
    protocol: ProtocolType
    action: str  # "allow" or "deny"
    description: str = ""
    priority: int = 1000
    created_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class ExternalAccessConfig:
    """External access configuration"""
    external_ip: str
    internal_ip: str
    domain_name: Optional[str] = None
    access_level: AccessLevel = AccessLevel.PUBLIC
    enable_https: bool = True
    enable_websocket: bool = True
    max_connections: int = 1000
    rate_limit_requests_per_minute: int = 1000
    allowed_origins: List[str] = field(default_factory=lambda: ["*"])
    blocked_ips: List[str] = field(default_factory=list)
    ssl_cert_path: Optional[str] = None
    ssl_key_path: Optional[str] = None

@dataclass
class LoadBalancerConfig:
    """Load balancer configuration"""
    enable_load_balancing: bool = False
    backend_servers: List[Dict[str, Any]] = field(default_factory=list)
    algorithm: str = "round_robin"  # round_robin, least_conn, ip_hash
    health_check_interval: int = 30
    health_check_timeout: int = 5
    session_persistence: bool = False

class NetworkAccessManager:
    """Manages network access configuration"""
    
    def __init__(self, external_ip: str = "155.138.239.131"):
        self.external_ip = external_ip
        self.internal_ip = self._get_internal_ip()
        self.config = ExternalAccessConfig(
            external_ip=external_ip,
            internal_ip=self.internal_ip
        )
        self.network_rules: List[NetworkRule] = []
        self.is_configured = False
    
    def _get_internal_ip(self) -> str:
        """Get internal IP address"""
        try:
            # Connect to external service to determine internal IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                internal_ip = s.getsockname()[0]
            return internal_ip
        except Exception:
            return "127.0.0.1"
    
    def configure_external_access(self, config: ExternalAccessConfig) -> bool:
        """Configure external access settings"""
        try:
            self.config = config
            
            # Validate IP addresses
            if not self._validate_ip_address(config.external_ip):
                raise ValueError(f"Invalid external IP address: {config.external_ip}")
            
            if not self._validate_ip_address(config.internal_ip):
                raise ValueError(f"Invalid internal IP address: {config.internal_ip}")
            
            # Configure network rules
            self._setup_default_rules()
            
            # Configure firewall if possible
            self._configure_firewall()
            
            # Configure reverse proxy if available
            self._configure_reverse_proxy()
            
            self.is_configured = True
            logger.info(f"External access configured for {config.external_ip}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure external access: {str(e)}")
            return False
    
    def _validate_ip_address(self, ip: str) -> bool:
        """Validate IP address"""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    def _setup_default_rules(self):
        """Setup default network access rules"""
        default_rules = [
            NetworkRule(
                rule_id="allow_http",
                source_ip="0.0.0.0/0",
                destination_port=80,
                protocol=ProtocolType.HTTP,
                action="allow",
                description="Allow HTTP traffic",
                priority=1000
            ),
            NetworkRule(
                rule_id="allow_https",
                source_ip="0.0.0.0/0",
                destination_port=443,
                protocol=ProtocolType.HTTPS,
                action="allow",
                description="Allow HTTPS traffic",
                priority=1000
            ),
            NetworkRule(
                rule_id="allow_api",
                source_ip="0.0.0.0/0",
                destination_port=8000,
                protocol=ProtocolType.HTTP,
                action="allow",
                description="Allow API traffic",
                priority=1000
            ),
            NetworkRule(
                rule_id="allow_websocket",
                source_ip="0.0.0.0/0",
                destination_port=8000,
                protocol=ProtocolType.WEBSOCKET,
                action="allow",
                description="Allow WebSocket traffic",
                priority=1000
            )
        ]
        
        # Add rules for blocked IPs
        for blocked_ip in self.config.blocked_ips:
            rule = NetworkRule(
                rule_id=f"block_{blocked_ip.replace('.', '_')}",
                source_ip=blocked_ip,
                destination_port=0,  # All ports
                protocol=ProtocolType.TCP,
                action="deny",
                description=f"Block IP {blocked_ip}",
                priority=100  # Higher priority (lower number)
            )
            default_rules.append(rule)
        
        self.network_rules.extend(default_rules)
    
    def _configure_firewall(self):
        """Configure firewall rules (platform dependent)"""
        system = platform.system().lower()
        
        try:
            if system == "linux":
                self._configure_iptables()
            elif system == "darwin":  # macOS
                self._configure_pfctl()
            elif system == "windows":
                self._configure_windows_firewall()
            else:
                logger.warning(f"Firewall configuration not supported on {system}")
        except Exception as e:
            logger.warning(f"Could not configure firewall: {str(e)}")
    
    def _configure_iptables(self):
        """Configure Linux iptables"""
        try:
            # Check if iptables is available
            subprocess.run(["which", "iptables"], check=True, capture_output=True)
            
            # Allow established connections
            subprocess.run([
                "sudo", "iptables", "-A", "INPUT", "-m", "conntrack", 
                "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT"
            ], check=False)
            
            # Allow loopback traffic
            subprocess.run([
                "sudo", "iptables", "-A", "INPUT", "-i", "lo", "-j", "ACCEPT"
            ], check=False)
            
            # Configure rules based on network rules
            for rule in self.network_rules:
                if rule.action == "allow" and rule.destination_port > 0:
                    cmd = [
                        "sudo", "iptables", "-A", "INPUT", "-p", "tcp",
                        "--dport", str(rule.destination_port), "-j", "ACCEPT"
                    ]
                    subprocess.run(cmd, check=False)
            
            logger.info("iptables rules configured")
            
        except subprocess.CalledProcessError:
            logger.warning("iptables not available or permission denied")
        except Exception as e:
            logger.warning(f"Failed to configure iptables: {str(e)}")
    
    def _configure_pfctl(self):
        """Configure macOS pfctl (stub)"""
        logger.info("pfctl configuration would be implemented here for macOS")
    
    def _configure_windows_firewall(self):
        """Configure Windows firewall (stub)"""
        logger.info("Windows firewall configuration would be implemented here")
    
    def _configure_reverse_proxy(self):
        """Configure reverse proxy (nginx/apache)"""
        try:
            # Generate nginx configuration
            nginx_config = self._generate_nginx_config()
            
            # Write to temporary file for manual review
            config_path = "/tmp/vru_api_nginx.conf"
            with open(config_path, "w") as f:
                f.write(nginx_config)
            
            logger.info(f"Nginx configuration generated: {config_path}")
            logger.info("Please review and manually apply nginx configuration")
            
        except Exception as e:
            logger.warning(f"Could not generate reverse proxy configuration: {str(e)}")
    
    def _generate_nginx_config(self) -> str:
        """Generate nginx configuration"""
        config = f"""
# VRU API Nginx Configuration
# External IP: {self.config.external_ip}
# Internal IP: {self.config.internal_ip}

upstream vru_api_backend {{
    server {self.config.internal_ip}:8000;
    keepalive 32;
}}

# Rate limiting
limit_req_zone $binary_remote_addr zone=api:10m rate={self.config.rate_limit_requests_per_minute}r/m;

server {{
    listen 80;
    server_name {self.config.external_ip} {self.config.domain_name or '_'};
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # API endpoints
    location /api/ {{
        limit_req zone=api burst=20 nodelay;
        
        proxy_pass http://vru_api_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }}
    
    # WebSocket endpoints
    location /api/v1/ws {{
        proxy_pass http://vru_api_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }}
    
    # Health check
    location /health {{
        access_log off;
        proxy_pass http://vru_api_backend/api/v1/health;
        proxy_set_header Host $host;
    }}
}}
"""
        
        if self.config.enable_https:
            config += f"""
server {{
    listen 443 ssl http2;
    server_name {self.config.external_ip} {self.config.domain_name or '_'};
    
    # SSL configuration
    ssl_certificate {self.config.ssl_cert_path or '/path/to/cert.pem'};
    ssl_certificate_key {self.config.ssl_key_path or '/path/to/key.pem'};
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Include same location blocks as HTTP server
    include /etc/nginx/snippets/vru-api-locations.conf;
}}
"""
        
        return config
    
    def test_external_connectivity(self) -> Dict[str, Any]:
        """Test external connectivity"""
        results = {
            "external_ip": self.config.external_ip,
            "internal_ip": self.config.internal_ip,
            "tests": {}
        }
        
        # Test external IP accessibility
        results["tests"]["external_ip_ping"] = self._test_ping(self.config.external_ip)
        
        # Test port accessibility
        for port in [80, 443, 8000]:
            results["tests"][f"port_{port}"] = self._test_port_connection(
                self.config.external_ip, port
            )
        
        # Test domain name resolution if configured
        if self.config.domain_name:
            results["tests"]["domain_resolution"] = self._test_domain_resolution(
                self.config.domain_name
            )
        
        # Test SSL certificate if configured
        if self.config.enable_https:
            results["tests"]["ssl_certificate"] = self._test_ssl_certificate(
                self.config.external_ip, 443
            )
        
        return results
    
    def _test_ping(self, host: str) -> Dict[str, Any]:
        """Test ping connectivity"""
        try:
            result = subprocess.run(
                ["ping", "-c", "4", host],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout if result.returncode == 0 else result.stderr
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _test_port_connection(self, host: str, port: int) -> Dict[str, Any]:
        """Test port connection"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = sock.connect_ex((host, port))
            sock.close()
            
            return {
                "success": result == 0,
                "port": port,
                "accessible": result == 0
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _test_domain_resolution(self, domain: str) -> Dict[str, Any]:
        """Test domain name resolution"""
        try:
            ip = socket.gethostbyname(domain)
            return {
                "success": True,
                "domain": domain,
                "resolved_ip": ip,
                "matches_config": ip == self.config.external_ip
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _test_ssl_certificate(self, host: str, port: int) -> Dict[str, Any]:
        """Test SSL certificate"""
        try:
            context = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    
                    return {
                        "success": True,
                        "certificate": {
                            "subject": dict(x[0] for x in cert.get("subject", [])),
                            "issuer": dict(x[0] for x in cert.get("issuer", [])),
                            "expires": cert.get("notAfter"),
                            "valid": True
                        }
                    }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_access_config(self) -> Dict[str, Any]:
        """Get current access configuration"""
        return {
            "external_access_config": asdict(self.config),
            "network_rules": [asdict(rule) for rule in self.network_rules],
            "is_configured": self.is_configured,
            "system_info": {
                "platform": platform.system(),
                "hostname": socket.gethostname(),
                "internal_ip": self.internal_ip,
                "external_ip": self.external_ip
            }
        }

class SSLManager:
    """Manages SSL/TLS certificates"""
    
    def __init__(self):
        self.certificates = {}
    
    def generate_self_signed_certificate(
        self,
        domain: str,
        output_dir: str = "/tmp"
    ) -> Tuple[str, str]:
        """Generate self-signed SSL certificate"""
        try:
            import tempfile
            import subprocess
            
            cert_path = os.path.join(output_dir, f"{domain}.crt")
            key_path = os.path.join(output_dir, f"{domain}.key")
            
            # Generate private key
            subprocess.run([
                "openssl", "genrsa", "-out", key_path, "2048"
            ], check=True, capture_output=True)
            
            # Generate certificate
            subprocess.run([
                "openssl", "req", "-new", "-x509", "-key", key_path,
                "-out", cert_path, "-days", "365", "-subj",
                f"/C=US/ST=State/L=City/O=Organization/OU=Unit/CN={domain}"
            ], check=True, capture_output=True)
            
            logger.info(f"Self-signed certificate generated: {cert_path}")
            return cert_path, key_path
            
        except Exception as e:
            logger.error(f"Failed to generate certificate: {str(e)}")
            raise
    
    def validate_certificate(self, cert_path: str) -> Dict[str, Any]:
        """Validate SSL certificate"""
        try:
            result = subprocess.run([
                "openssl", "x509", "-in", cert_path, "-text", "-noout"
            ], check=True, capture_output=True, text=True)
            
            return {
                "valid": True,
                "details": result.stdout
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e)
            }

def configure_external_access(
    external_ip: str = "155.138.239.131",
    domain_name: Optional[str] = None,
    enable_https: bool = True,
    generate_ssl_cert: bool = False
) -> NetworkAccessManager:
    """Configure external access for VRU API"""
    
    try:
        logger.info(f"Configuring external access for {external_ip}")
        
        # Create access manager
        access_manager = NetworkAccessManager(external_ip)
        
        # Create configuration
        config = ExternalAccessConfig(
            external_ip=external_ip,
            internal_ip=access_manager.internal_ip,
            domain_name=domain_name,
            enable_https=enable_https,
            enable_websocket=True,
            max_connections=1000,
            rate_limit_requests_per_minute=1000
        )
        
        # Generate SSL certificate if requested
        if enable_https and generate_ssl_cert:
            ssl_manager = SSLManager()
            cert_path, key_path = ssl_manager.generate_self_signed_certificate(
                domain_name or external_ip
            )
            config.ssl_cert_path = cert_path
            config.ssl_key_path = key_path
        
        # Configure access
        success = access_manager.configure_external_access(config)
        
        if success:
            logger.info("External access configuration completed")
            
            # Test connectivity
            test_results = access_manager.test_external_connectivity()
            logger.info(f"Connectivity test results: {test_results}")
        else:
            logger.error("External access configuration failed")
        
        return access_manager
        
    except Exception as e:
        logger.error(f"Failed to configure external access: {str(e)}")
        raise

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Configure external access
    access_manager = configure_external_access(
        external_ip="155.138.239.131",
        domain_name=None,
        enable_https=True,
        generate_ssl_cert=True
    )
    
    # Print configuration
    config = access_manager.get_access_config()
    print(f"Access Configuration: {json.dumps(config, indent=2, default=str)}")