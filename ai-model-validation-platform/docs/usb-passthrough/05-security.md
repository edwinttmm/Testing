# Security Considerations and Best Practices

USB passthrough introduces security considerations that must be carefully addressed, especially in development and production environments. This guide covers security best practices for LabJack USB passthrough configurations.

## Table of Contents

1. [Security Risk Assessment](#security-risk-assessment)
2. [Network Security](#network-security)
3. [Access Control](#access-control)
4. [Container Security](#container-security)
5. [Data Protection](#data-protection)
6. [Audit and Monitoring](#audit-and-monitoring)
7. [Secure Development Practices](#secure-development-practices)
8. [Compliance Considerations](#compliance-considerations)

## Security Risk Assessment

### Threat Model

| Threat | Likelihood | Impact | Mitigation Priority |
|--------|------------|---------|-------------------|
| Unauthorized device access | Medium | High | Critical |
| Network eavesdropping | High | Medium | High |
| Container escape | Low | Critical | High |
| Data exfiltration | Medium | High | Critical |
| Device firmware compromise | Low | Critical | Medium |
| Man-in-the-middle attacks | Medium | High | High |

### Attack Vectors

#### 1. USB/IP Protocol Vulnerabilities

**Risk**: USB/IP protocol lacks built-in encryption and authentication
**Impact**: Data interception, device spoofing, unauthorized access

```python
# Example of vulnerable USB/IP traffic
# All data transmitted in plain text
class VulnerableUSBIPClient:
    def connect(self, host, port=3240):
        # No authentication or encryption
        self.socket = socket.connect((host, port))
        # All LabJack data sent unencrypted
        return self.socket
```

**Mitigation**: Implement additional security layers

#### 2. Privilege Escalation

**Risk**: USB passthrough often requires elevated privileges
**Impact**: System compromise, lateral movement

#### 3. Container Security

**Risk**: Privileged containers with device access
**Impact**: Host system compromise

#### 4. Network Exposure

**Risk**: USB/IP services exposed to network
**Impact**: Remote unauthorized access

## Network Security

### Secure Network Configuration

#### 1. Firewall Rules

Create `setup_firewall_rules.ps1`:

```powershell
#Requires -RunAsAdministrator

Write-Host "Configuring firewall for secure USB/IP access..." -ForegroundColor Green

# Block USB/IP port (3240) from external networks
New-NetFirewallRule -DisplayName "Block USB/IP External" -Direction Inbound -Protocol TCP -LocalPort 3240 -Action Block -RemoteAddress "0.0.0.0-10.0.0.0", "11.0.0.0-172.15.255.255", "172.32.0.0-192.167.255.255", "192.169.0.0-255.255.255.255"

# Allow USB/IP only from local networks
New-NetFirewallRule -DisplayName "Allow USB/IP Local" -Direction Inbound -Protocol TCP -LocalPort 3240 -Action Allow -RemoteAddress LocalSubnet

# Log connections for monitoring
New-NetFirewallRule -DisplayName "USB/IP Logging" -Direction Inbound -Protocol TCP -LocalPort 3240 -Action Allow -LocalAddress Any -RemoteAddress LocalSubnet -EdgeTraversalPolicy Block -LogFileName "%SystemRoot%\System32\LogFiles\Firewall\usbip.log" -LogAllowed True -LogBlocked True

Write-Host "Firewall rules configured for USB/IP security" -ForegroundColor Green
```

#### 2. VPN-Only Access

```yaml
# docker-compose.yml with VPN requirement
version: '3.8'
services:
  vpn:
    image: dperson/openvpn-client
    cap_add:
      - NET_ADMIN
    volumes:
      - ./vpn-config:/vpn:ro
    environment:
      - VPN_CONF=client.ovpn
      - VPN_USER=labjack_user
      - VPN_PASS=secure_password
    
  labjack-app:
    image: labjack-app:secure
    network_mode: "service:vpn"  # Route through VPN
    depends_on:
      - vpn
    devices:
      - "/dev/bus/usb:/dev/bus/usb"
```

#### 3. Network Segmentation

```bash
# Create isolated network for LabJack operations
docker network create --driver bridge \
  --subnet=172.20.0.0/16 \
  --opt com.docker.network.bridge.name=labjack-net \
  --opt com.docker.network.bridge.enable_ip_masquerade=false \
  labjack-isolated
```

### Secure Communication Protocols

#### 1. TLS Wrapper for USB/IP

Create `secure_usbip_wrapper.py`:

```python
import ssl
import socket
import threading
import logging
from cryptography.fernet import Fernet
import hashlib
import hmac

class SecureUSBIPWrapper:
    def __init__(self, cert_file, key_file, ca_file=None):
        self.cert_file = cert_file
        self.key_file = key_file
        self.ca_file = ca_file
        self.encryption_key = Fernet.generate_key()
        self.cipher = Fernet(self.encryption_key)
        self.clients = {}
        
    def create_secure_context(self):
        """Create secure SSL context"""
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(self.cert_file, self.key_file)
        
        if self.ca_file:
            context.load_verify_locations(self.ca_file)
            context.verify_mode = ssl.CERT_REQUIRED
        
        # Strong security settings
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
        
        return context
    
    def start_secure_proxy(self, listen_port=3241, target_host='localhost', target_port=3240):
        """Start secure proxy for USB/IP"""
        context = self.create_secure_context()
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind(('0.0.0.0', listen_port))
            server_sock.listen(5)
            
            logging.info(f"Secure USB/IP proxy listening on port {listen_port}")
            
            while True:
                client_sock, client_addr = server_sock.accept()
                logging.info(f"Connection from {client_addr}")
                
                # Wrap with SSL
                try:
                    ssl_sock = context.wrap_socket(client_sock, server_side=True)
                    
                    # Handle client in separate thread
                    client_thread = threading.Thread(
                        target=self.handle_secure_client,
                        args=(ssl_sock, target_host, target_port)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except ssl.SSLError as e:
                    logging.error(f"SSL error with {client_addr}: {e}")
                    client_sock.close()
    
    def handle_secure_client(self, ssl_sock, target_host, target_port):
        """Handle secure client connection"""
        try:
            # Authenticate client
            if not self.authenticate_client(ssl_sock):
                ssl_sock.close()
                return
            
            # Connect to USB/IP server
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as target_sock:
                target_sock.connect((target_host, target_port))
                
                # Start bidirectional proxy
                self.proxy_data(ssl_sock, target_sock)
                
        except Exception as e:
            logging.error(f"Client handling error: {e}")
        finally:
            ssl_sock.close()
    
    def authenticate_client(self, ssl_sock):
        """Authenticate client with challenge-response"""
        try:
            # Send challenge
            challenge = os.urandom(32)
            ssl_sock.send(challenge)
            
            # Receive response
            response = ssl_sock.recv(64)
            
            # Verify response (implement your authentication logic)
            expected = hmac.new(b'shared_secret', challenge, hashlib.sha256).digest()
            
            return hmac.compare_digest(response, expected)
            
        except Exception as e:
            logging.error(f"Authentication error: {e}")
            return False
    
    def proxy_data(self, client_sock, server_sock):
        """Proxy data between client and server"""
        def forward_data(src, dst):
            try:
                while True:
                    data = src.recv(4096)
                    if not data:
                        break
                    
                    # Encrypt/decrypt data if needed
                    if isinstance(src, ssl.SSLSocket):
                        # Data from client, forward to server
                        dst.send(data)
                    else:
                        # Data from server, forward to client  
                        src.send(data)
            except Exception as e:
                logging.error(f"Forwarding error: {e}")
        
        # Start forwarding threads
        client_to_server = threading.Thread(target=forward_data, args=(client_sock, server_sock))
        server_to_client = threading.Thread(target=forward_data, args=(server_sock, client_sock))
        
        client_to_server.daemon = True
        server_to_client.daemon = True
        
        client_to_server.start()
        server_to_client.start()
        
        # Wait for threads to complete
        client_to_server.join()
        server_to_client.join()

# Usage example
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    proxy = SecureUSBIPWrapper(
        cert_file='server.crt',
        key_file='server.key',
        ca_file='ca.crt'
    )
    
    proxy.start_secure_proxy()
```

#### 2. Certificate Management

Create certificates for secure communication:

```bash
#!/bin/bash
# generate_certificates.sh

echo "Generating certificates for secure USB/IP..."

# Create CA key and certificate
openssl genrsa -out ca.key 4096
openssl req -new -x509 -days 365 -key ca.key -out ca.crt -subj "/C=US/ST=State/L=City/O=Organization/CN=USB-IP-CA"

# Create server key and certificate
openssl genrsa -out server.key 4096
openssl req -new -key server.key -out server.csr -subj "/C=US/ST=State/L=City/O=Organization/CN=usbip-server"
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 365

# Create client key and certificate  
openssl genrsa -out client.key 4096
openssl req -new -key client.key -out client.csr -subj "/C=US/ST=State/L=City/O=Organization/CN=usbip-client"
openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out client.crt -days 365

# Set proper permissions
chmod 600 *.key
chmod 644 *.crt

echo "Certificates generated successfully"
```

## Access Control

### Role-Based Access Control (RBAC)

#### 1. User Management

Create `manage_usbip_users.ps1`:

```powershell
#Requires -RunAsAdministrator

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("create", "delete", "list", "grant", "revoke")]
    [string]$Action,
    
    [string]$Username,
    [string]$Role
)

# Define roles and permissions
$Roles = @{
    "usbip-admin" = @("bind", "unbind", "attach", "detach", "list", "configure")
    "usbip-user" = @("attach", "detach", "list")
    "usbip-readonly" = @("list")
}

function Create-USBIPUser {
    param([string]$Username, [string]$Role)
    
    if ($Roles.ContainsKey($Role)) {
        # Create local user
        $Password = ConvertTo-SecureString -String (New-Guid).ToString() -AsPlainText -Force
        New-LocalUser -Name $Username -Password $Password -Description "USB/IP $Role user"
        
        # Add to appropriate groups
        switch ($Role) {
            "usbip-admin" { Add-LocalGroupMember -Group "Administrators" -Member $Username }
            "usbip-user" { Add-LocalGroupMember -Group "Users" -Member $Username }
            "usbip-readonly" { Add-LocalGroupMember -Group "Users" -Member $Username }
        }
        
        Write-Host "User $Username created with role $Role"
    } else {
        Write-Error "Invalid role: $Role"
    }
}

function Grant-USBIPPermission {
    param([string]$Username, [string]$Role)
    
    # Create custom security policy for USB/IP access
    $PolicyContent = @"
[Unicode]
Unicode=yes
[System Access]
MinimumPasswordAge = 1
MaximumPasswordAge = 42
MinimumPasswordLength = 8
[Privilege Rights]
SeServiceLogonRight = $Username
SeInteractiveLogonRight = $Username
"@

    $PolicyFile = "usb_ip_policy_$Username.inf"
    $PolicyContent | Out-File -FilePath $PolicyFile
    
    # Apply security policy
    secedit /configure /db database.sdb /cfg $PolicyFile
    
    Remove-Item $PolicyFile
}

switch ($Action) {
    "create" { Create-USBIPUser -Username $Username -Role $Role }
    "grant" { Grant-USBIPPermission -Username $Username -Role $Role }
    "list" { Get-LocalUser | Where-Object { $_.Description -match "USB/IP" } }
}
```

#### 2. Linux Access Control

Create `/etc/security/usbip.conf`:

```bash
# USB/IP Access Control Configuration

# Allow specific users to use USB/IP
usbip_users = labjack_user,developer,admin

# Allow specific groups
usbip_groups = labjack,developers

# Device-specific access control
# Format: vendor_id:product_id = user1,user2,group1
0cd5:0009 = labjack_user,developers
0cd5:000a = admin,labjack

# Time-based access (optional)
time_restrictions = weekdays:09:00-17:00

# Logging settings
log_access = true
log_file = /var/log/usbip_access.log
```

Create access control script `usbip_access_control.sh`:

```bash
#!/bin/bash

USBIP_CONFIG="/etc/security/usbip.conf"
LOG_FILE="/var/log/usbip_access.log"

check_user_access() {
    local user=$1
    local device_id=$2
    local current_time=$(date +%H:%M)
    local current_day=$(date +%u)  # 1-7, Monday=1
    
    # Log access attempt
    echo "$(date): Access attempt by $user for device $device_id" >> "$LOG_FILE"
    
    # Check if user is in allowed users
    if grep -q "^usbip_users.*$user" "$USBIP_CONFIG"; then
        echo "User access granted"
        return 0
    fi
    
    # Check if user's primary group is allowed
    user_group=$(id -gn "$user")
    if grep -q "^usbip_groups.*$user_group" "$USBIP_CONFIG"; then
        echo "Group access granted"
        return 0
    fi
    
    # Check device-specific access
    if grep -q "^$device_id.*$user" "$USBIP_CONFIG"; then
        echo "Device-specific access granted"
        return 0
    fi
    
    echo "Access denied"
    echo "$(date): Access denied for $user on device $device_id" >> "$LOG_FILE"
    return 1
}

# Wrapper for usbipd commands
original_usbipd="/usr/bin/usbipd.original"

case "$1" in
    "bind"|"attach")
        device_id=$(echo "$@" | grep -o '0cd5:[0-9a-f]\+')
        if check_user_access "$(whoami)" "$device_id"; then
            exec "$original_usbipd" "$@"
        else
            echo "Permission denied"
            exit 1
        fi
        ;;
    *)
        exec "$original_usbipd" "$@"
        ;;
esac
```

### Device-Level Security

#### 1. Hardware Security Module Integration

```python
import pkcs11
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding

class SecureLabJackAccess:
    def __init__(self, hsm_token_label, pin):
        self.lib = pkcs11.lib('/usr/lib/softhsm/libsofthsm2.so')
        self.token = self.lib.get_token(token_label=hsm_token_label)
        self.session = self.token.open(rw=True, user_pin=pin)
        self.device_key = self._get_or_create_device_key()
    
    def _get_or_create_device_key(self):
        """Get or create device-specific key in HSM"""
        try:
            # Try to find existing key
            key = self.session.get_key(label='labjack_device_key')
        except:
            # Generate new key
            key = self.session.generate_key(
                pkcs11.KeyType.RSA,
                2048,
                label='labjack_device_key',
                store=True
            )
        return key
    
    def secure_device_command(self, command_data):
        """Execute device command with HSM signature"""
        # Sign command with HSM key
        signature = command_data.sign(
            self.device_key,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Send signed command to device
        return self._send_secure_command(command_data, signature)
    
    def _send_secure_command(self, command, signature):
        """Send signed command to LabJack"""
        # Implementation depends on your protocol
        pass
```

## Container Security

### Secure Container Configuration

#### 1. Hardened Dockerfile

```dockerfile
FROM ubuntu:22.04

# Create non-root user
RUN groupadd -g 1000 labjack && \
    useradd -u 1000 -g labjack -s /bin/bash -m labjack

# Install minimal dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libusb-1.0-0-dev \
    python3-minimal \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install LabJack library
RUN pip3 install --no-cache-dir u3

# Set up secure permissions
RUN chmod 755 /home/labjack && \
    chown -R labjack:labjack /home/labjack

# Create device access rules
COPY 99-labjack-secure.rules /etc/udev/rules.d/
RUN chmod 644 /etc/udev/rules.d/99-labjack-secure.rules

# Switch to non-root user
USER labjack
WORKDIR /home/labjack

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python3 -c "import u3; print('OK')" || exit 1

COPY --chown=labjack:labjack app.py .

CMD ["python3", "app.py"]
```

#### 2. Security Policies

Create `labjack-security-policy.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: labjack-secure
  annotations:
    seccomp.security.alpha.kubernetes.io/pod: runtime/default
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    fsGroup: 1000
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: labjack-app
    image: labjack-app:secure
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop:
          - ALL
        add:
          - CAP_DAC_OVERRIDE  # Only for device access
    volumeMounts:
    - name: tmp
      mountPath: /tmp
    - name: device
      mountPath: /dev/bus/usb
    resources:
      limits:
        memory: "256Mi"
        cpu: "500m"
      requests:
        memory: "128Mi"
        cpu: "250m"
  volumes:
  - name: tmp
    emptyDir: {}
  - name: device
    hostPath:
      path: /dev/bus/usb
```

#### 3. AppArmor Profile

Create `/etc/apparmor.d/labjack-container`:

```bash
#include <tunables/global>

profile labjack-container flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/base>
  
  # Allow basic system access
  /lib/x86_64-linux-gnu/** r,
  /usr/lib/python3*/** r,
  /usr/bin/python3* ix,
  
  # Allow LabJack library access
  /usr/local/lib/liblabjackusb.so* r,
  
  # Allow USB device access (restricted)
  /dev/bus/usb/** rw,
  /sys/bus/usb/devices/** r,
  
  # Allow application files
  /home/labjack/** rw,
  /tmp/** rw,
  
  # Network access (if needed)
  network inet stream,
  network inet dgram,
  
  # Deny dangerous capabilities
  deny capability sys_admin,
  deny capability sys_rawio,
  deny capability sys_ptrace,
  
  # Deny access to sensitive files
  deny /boot/** rw,
  deny /etc/shadow r,
  deny /etc/passwd w,
  deny /root/** rw,
  
  # Process restrictions
  deny ptrace,
  deny signal,
}
```

## Data Protection

### Data Encryption

#### 1. Data-at-Rest Encryption

```python
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
import base64
import json

class SecureDataStorage:
    def __init__(self, password: bytes, salt: bytes = None):
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        self.cipher = Fernet(key)
        self.salt = salt
    
    def encrypt_sensor_data(self, data: dict) -> bytes:
        """Encrypt sensor data before storage"""
        json_data = json.dumps(data).encode('utf-8')
        encrypted = self.cipher.encrypt(json_data)
        
        # Prepend salt for storage
        return self.salt + encrypted
    
    def decrypt_sensor_data(self, encrypted_data: bytes) -> dict:
        """Decrypt stored sensor data"""
        # Extract salt
        salt = encrypted_data[:16]
        encrypted = encrypted_data[16:]
        
        # Decrypt
        decrypted = self.cipher.decrypt(encrypted)
        return json.loads(decrypted.decode('utf-8'))
    
    def secure_file_write(self, filename: str, data: dict):
        """Securely write data to file"""
        encrypted_data = self.encrypt_sensor_data(data)
        
        # Write with secure permissions
        os.umask(0o077)  # Only owner can read/write
        with open(filename, 'wb') as f:
            f.write(encrypted_data)
    
    def secure_file_read(self, filename: str) -> dict:
        """Securely read data from file"""
        with open(filename, 'rb') as f:
            encrypted_data = f.read()
        
        return self.decrypt_sensor_data(encrypted_data)

# Usage example
def secure_labjack_logging():
    # Use strong password for encryption
    password = os.environ.get('LABJACK_ENCRYPTION_KEY', '').encode('utf-8')
    if not password:
        raise ValueError("LABJACK_ENCRYPTION_KEY environment variable required")
    
    storage = SecureDataStorage(password)
    
    # Simulate LabJack data
    sensor_data = {
        'timestamp': time.time(),
        'voltage_channel_0': 2.45,
        'voltage_channel_1': 1.23,
        'temperature': 25.6
    }
    
    # Encrypt and store
    storage.secure_file_write('sensor_data.enc', sensor_data)
    
    # Read and decrypt
    retrieved_data = storage.secure_file_read('sensor_data.enc')
    print(f"Retrieved: {retrieved_data}")
```

#### 2. Data-in-Transit Protection

```python
import ssl
import socket
import json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes

class SecureLabJackClient:
    def __init__(self, server_cert_file, client_cert_file, client_key_file):
        self.server_cert = server_cert_file
        self.client_cert = client_cert_file  
        self.client_key = client_key_file
        self.session_key = None
    
    def create_secure_connection(self, host, port):
        """Create secure connection to LabJack server"""
        # Create SSL context
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.load_verify_locations(self.server_cert)
        context.load_cert_chain(self.client_cert, self.client_key)
        
        # Require certificate verification
        context.check_hostname = False  # Using IP addresses
        context.verify_mode = ssl.CERT_REQUIRED
        
        # Strong cipher suites only
        context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20')
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        
        # Connect with SSL
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ssl_sock = context.wrap_socket(sock, server_hostname=host)
        ssl_sock.connect((host, port))
        
        return ssl_sock
    
    def send_secure_command(self, ssl_sock, command_data):
        """Send encrypted command over secure connection"""
        # Additional encryption layer
        if self.session_key:
            cipher = Fernet(self.session_key)
            encrypted_command = cipher.encrypt(json.dumps(command_data).encode('utf-8'))
            ssl_sock.send(encrypted_command)
        else:
            ssl_sock.send(json.dumps(command_data).encode('utf-8'))
        
        # Receive response
        response_data = ssl_sock.recv(4096)
        
        if self.session_key:
            decrypted_response = cipher.decrypt(response_data)
            return json.loads(decrypted_response.decode('utf-8'))
        else:
            return json.loads(response_data.decode('utf-8'))
```

## Audit and Monitoring

### Security Logging

#### 1. Comprehensive Logging

Create `security_logger.py`:

```python
import logging
import json
import hashlib
import time
import os
from datetime import datetime
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding

class SecurityLogger:
    def __init__(self, log_file='/var/log/labjack_security.log', signing_key_file=None):
        self.log_file = log_file
        self.setup_logging()
        
        # Load signing key for log integrity
        if signing_key_file and os.path.exists(signing_key_file):
            with open(signing_key_file, 'rb') as f:
                self.signing_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None
                )
        else:
            self.signing_key = None
    
    def setup_logging(self):
        """Setup secure logging configuration"""
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File handler with rotation
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            self.log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(formatter)
        
        # Syslog handler for centralized logging
        from logging.handlers import SysLogHandler
        syslog_handler = SysLogHandler(address='/dev/log')
        syslog_handler.setFormatter(formatter)
        
        # Configure root logger
        self.logger = logging.getLogger('LabJackSecurity')
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(syslog_handler)
    
    def log_device_access(self, user, device_id, action, success, details=None):
        """Log device access attempts"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': 'device_access',
            'user': user,
            'device_id': device_id,
            'action': action,
            'success': success,
            'details': details or {},
            'source_ip': self._get_source_ip(),
            'session_id': self._get_session_id()
        }
        
        self._write_secure_log(log_entry)
    
    def log_security_event(self, event_type, severity, description, metadata=None):
        """Log general security events"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'severity': severity,
            'description': description,
            'metadata': metadata or {},
            'source_ip': self._get_source_ip(),
            'process_id': os.getpid()
        }
        
        self._write_secure_log(log_entry)
    
    def log_data_access(self, user, data_type, operation, file_path=None):
        """Log data access events"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': 'data_access',
            'user': user,
            'data_type': data_type,
            'operation': operation,
            'file_path': file_path,
            'file_hash': self._calculate_file_hash(file_path) if file_path else None
        }
        
        self._write_secure_log(log_entry)
    
    def _write_secure_log(self, log_entry):
        """Write log entry with integrity protection"""
        log_json = json.dumps(log_entry, sort_keys=True)
        
        # Calculate hash for integrity
        log_hash = hashlib.sha256(log_json.encode('utf-8')).hexdigest()
        log_entry['integrity_hash'] = log_hash
        
        # Sign log entry if signing key available
        if self.signing_key:
            signature = self.signing_key.sign(
                log_json.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            log_entry['signature'] = signature.hex()
        
        # Write to log
        final_log = json.dumps(log_entry)
        self.logger.info(final_log)
    
    def _get_source_ip(self):
        """Get source IP address"""
        # Implementation depends on your environment
        return os.environ.get('SSH_CLIENT', 'unknown').split()[0]
    
    def _get_session_id(self):
        """Get session identifier"""
        return os.environ.get('SSH_TTY', f'pid_{os.getpid()}')
    
    def _calculate_file_hash(self, file_path):
        """Calculate SHA256 hash of file"""
        if not file_path or not os.path.exists(file_path):
            return None
        
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception:
            return None

# Usage example
def secure_labjack_operation():
    logger = SecurityLogger('/var/log/labjack_security.log', 'signing_key.pem')
    
    try:
        # Log device access
        logger.log_device_access(
            user='john_doe',
            device_id='0cd5:0009',
            action='attach',
            success=True,
            details={'bus_id': '1-4', 'wsl_instance': 'Ubuntu-20.04'}
        )
        
        # Perform LabJack operation
        device = u3.U3()
        voltage = device.getAIN(0)
        
        # Log data access
        logger.log_data_access(
            user='john_doe',
            data_type='sensor_reading',
            operation='read',
            file_path='sensor_data.log'
        )
        
        device.close()
        
    except Exception as e:
        logger.log_security_event(
            event_type='device_error',
            severity='HIGH',
            description=f'LabJack operation failed: {str(e)}',
            metadata={'error_type': type(e).__name__}
        )
```

#### 2. Security Monitoring Dashboard

Create `security_monitor.py` for real-time monitoring:

```python
import json
import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.animation as animation

class SecurityMonitor:
    def __init__(self, log_file='/var/log/labjack_security.log'):
        self.log_file = log_file
        self.events = deque(maxlen=1000)  # Keep last 1000 events
        self.alerts = deque(maxlen=100)   # Keep last 100 alerts
        self.stats = defaultdict(int)
        self.monitoring = True
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self._monitor_logs)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def _monitor_logs(self):
        """Monitor security logs for events"""
        try:
            with open(self.log_file, 'r') as f:
                # Seek to end of file
                f.seek(0, 2)
                
                while self.monitoring:
                    line = f.readline()
                    if line:
                        self._process_log_line(line)
                    else:
                        time.sleep(0.1)
        except FileNotFoundError:
            print(f"Log file {self.log_file} not found")
    
    def _process_log_line(self, line):
        """Process individual log line"""
        try:
            if 'LabJackSecurity' in line:
                # Extract JSON part
                json_start = line.find('{')
                if json_start != -1:
                    json_data = line[json_start:]
                    event = json.loads(json_data)
                    
                    self.events.append(event)
                    self._update_stats(event)
                    self._check_alerts(event)
        except json.JSONDecodeError:
            pass
    
    def _update_stats(self, event):
        """Update statistics"""
        self.stats['total_events'] += 1
        self.stats[f"event_type_{event.get('event_type', 'unknown')}"] += 1
        
        if event.get('event_type') == 'device_access':
            if event.get('success'):
                self.stats['successful_access'] += 1
            else:
                self.stats['failed_access'] += 1
    
    def _check_alerts(self, event):
        """Check for security alerts"""
        current_time = datetime.utcnow()
        
        # Failed access attempts
        if event.get('event_type') == 'device_access' and not event.get('success'):
            recent_failures = sum(1 for e in self.events 
                                if e.get('event_type') == 'device_access' 
                                and not e.get('success')
                                and e.get('user') == event.get('user'))
            
            if recent_failures >= 5:  # 5 failures from same user
                self._create_alert('MULTIPLE_FAILED_ACCESS', event)
        
        # Unusual access times
        if event.get('event_type') == 'device_access':
            hour = current_time.hour
            if hour < 6 or hour > 22:  # Outside business hours
                self._create_alert('OFF_HOURS_ACCESS', event)
        
        # High-severity events
        if event.get('severity') == 'HIGH':
            self._create_alert('HIGH_SEVERITY_EVENT', event)
    
    def _create_alert(self, alert_type, event):
        """Create security alert"""
        alert = {
            'timestamp': datetime.utcnow().isoformat(),
            'alert_type': alert_type,
            'severity': 'HIGH',
            'event': event,
            'description': f'Security alert: {alert_type}'
        }
        
        self.alerts.append(alert)
        print(f"SECURITY ALERT: {alert_type} - {event.get('user', 'unknown')}")
    
    def get_dashboard_data(self):
        """Get data for security dashboard"""
        recent_events = [e for e in self.events 
                        if datetime.fromisoformat(e['timestamp']) > 
                        datetime.utcnow() - timedelta(hours=24)]
        
        return {
            'total_events': len(self.events),
            'recent_events': len(recent_events),
            'active_alerts': len(self.alerts),
            'stats': dict(self.stats),
            'latest_alerts': list(self.alerts)[-10:],  # Last 10 alerts
            'event_timeline': self._get_event_timeline()
        }
    
    def _get_event_timeline(self):
        """Get timeline of events for graphing"""
        timeline = defaultdict(int)
        
        for event in self.events:
            timestamp = datetime.fromisoformat(event['timestamp'])
            hour_key = timestamp.replace(minute=0, second=0, microsecond=0)
            timeline[hour_key] += 1
        
        return dict(timeline)
```

## Secure Development Practices

### Code Review Checklist

#### Security Code Review Items

1. **Input Validation**
   - [ ] All USB device inputs validated
   - [ ] Buffer overflow protections
   - [ ] SQL injection prevention (if using databases)
   - [ ] Command injection prevention

2. **Authentication & Authorization**
   - [ ] Strong authentication mechanisms
   - [ ] Principle of least privilege
   - [ ] Session management
   - [ ] Token validation

3. **Encryption & Cryptography**
   - [ ] Strong encryption algorithms
   - [ ] Proper key management
   - [ ] Secure random number generation
   - [ ] Certificate validation

4. **Error Handling**
   - [ ] No sensitive information in error messages
   - [ ] Proper exception handling
   - [ ] Security event logging
   - [ ] Graceful failure modes

#### Secure Coding Standards

Create `.security-rules.yml`:

```yaml
# Security rules for LabJack development
rules:
  - id: no-hardcoded-credentials
    pattern: |
      password|secret|key|token\s*=\s*["'][^"']+["']
    message: "No hardcoded credentials allowed"
    severity: HIGH
  
  - id: secure-random
    pattern: |
      random\.random|random\.randint
    message: "Use cryptographically secure random"
    severity: MEDIUM
    
  - id: usb-input-validation
    pattern: |
      device\.(get|set).*\(.*\)
    message: "Validate all device inputs"
    severity: HIGH
    
  - id: logging-sensitive-data
    pattern: |
      log.*password|log.*secret|print.*password
    message: "Don't log sensitive data"
    severity: HIGH
```

## Compliance Considerations

### Regulatory Requirements

#### 1. GDPR Compliance

```python
class GDPRCompliantDataHandler:
    def __init__(self):
        self.data_retention_days = 365  # Configurable
        self.consent_records = {}
        
    def collect_sensor_data(self, user_id, device_id, data, consent_given=False):
        """Collect sensor data with GDPR compliance"""
        if not consent_given:
            raise ValueError("User consent required for data collection")
        
        # Record consent
        self.consent_records[user_id] = {
            'timestamp': datetime.utcnow(),
            'purpose': 'sensor_data_collection',
            'device_id': device_id
        }
        
        # Add privacy metadata
        data['privacy'] = {
            'collected_at': datetime.utcnow().isoformat(),
            'consent_id': f"{user_id}_{int(time.time())}",
            'retention_until': (datetime.utcnow() + timedelta(days=self.data_retention_days)).isoformat(),
            'data_controller': 'your_organization'
        }
        
        return data
    
    def anonymize_data(self, data):
        """Anonymize sensor data"""
        # Remove or hash personally identifiable information
        if 'user_id' in data:
            data['user_id'] = hashlib.sha256(data['user_id'].encode()).hexdigest()[:8]
        
        # Remove location data if present
        data.pop('location', None)
        data.pop('ip_address', None)
        
        return data
    
    def handle_data_deletion_request(self, user_id):
        """Handle right to be forgotten requests"""
        # Delete user's sensor data
        # Implementation depends on your storage system
        pass
```

#### 2. HIPAA Compliance (if applicable)

```python
class HIPAACompliantLogging:
    def __init__(self):
        self.audit_trail = []
        
    def log_phi_access(self, user, patient_id, action):
        """Log PHI access for HIPAA compliance"""
        audit_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'user': user,
            'patient_id': self._hash_patient_id(patient_id),
            'action': action,
            'workstation': socket.gethostname(),
            'session_id': os.environ.get('SESSION_ID', 'unknown')
        }
        
        self.audit_trail.append(audit_entry)
        
        # Write to secure audit log
        with open('/secure/logs/hipaa_audit.log', 'a') as f:
            f.write(json.dumps(audit_entry) + '\n')
    
    def _hash_patient_id(self, patient_id):
        """Hash patient ID for audit trail"""
        return hashlib.sha256(f"{patient_id}_{os.environ.get('AUDIT_SALT', '')}".encode()).hexdigest()[:16]
```

## Next Steps

- Review [Validation Procedures](./06-validation.md) for security testing methods
- Implement monitoring and alerting systems
- Conduct regular security assessments
- Train team on security best practices
- Establish incident response procedures