#!/usr/bin/env python3
"""
PortManager - SPARC Architecture Component
Dynamic port conflict detection and resolution with intelligent fallbacks
Solves port conflict issues in multi-process environments
"""

import os
import socket
import time
import logging
import subprocess
import signal
from typing import Dict, Any, Optional, List, Set, Tuple
from dataclasses import dataclass
from enum import Enum
import psutil

from .environment_detector import detect_environment, EnvironmentType, ServiceMode

logger = logging.getLogger(__name__)

class PortStatus(Enum):
    """Port availability status"""
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    RESERVED = "reserved"
    BLOCKED = "blocked"

class ProcessType(Enum):
    """Types of processes that might occupy ports"""
    UVICORN = "uvicorn"
    FASTAPI = "fastapi"
    PYTHON = "python"
    NODE = "node"
    NGINX = "nginx"
    UNKNOWN = "unknown"

@dataclass
class PortInfo:
    """Port usage information"""
    port: int
    status: PortStatus
    pid: Optional[int] = None
    process_name: Optional[str] = None
    process_type: ProcessType = ProcessType.UNKNOWN
    command_line: Optional[str] = None
    user: Optional[str] = None
    listening_address: Optional[str] = None
    can_terminate: bool = False

class PortManager:
    """
    Dynamic port management with conflict resolution
    Handles port discovery, conflict detection, and process management
    """
    
    def __init__(self):
        self._env_info = detect_environment()
        self._reserved_ports: Set[int] = set()
        self._port_cache: Dict[int, PortInfo] = {}
        self.cache_ttl = 30  # 30 seconds
        
        # Common service ports to check
        self._service_ports = {
            'api': [8000, 8001, 8080, 5000, 3000],
            'database': [5432, 3306, 27017],
            'redis': [6379],
            'web': [3000, 3001, 8080, 80, 443],
            'development': [8000, 3000, 5000, 8080]
        }
        
    def find_available_port(self, 
                          preferred_port: int = 8000,
                          port_range: Tuple[int, int] = (8000, 8100),
                          exclude_ports: Optional[List[int]] = None) -> int:
        """
        Find an available port, starting with the preferred port
        
        Args:
            preferred_port: Preferred port number
            port_range: Range to search if preferred port is unavailable
            exclude_ports: Ports to exclude from search
            
        Returns:
            Available port number
        """
        exclude_ports = exclude_ports or []
        exclude_set = set(exclude_ports) | self._reserved_ports
        
        logger.info(f"🔍 Finding available port (preferred: {preferred_port})")
        
        # Try preferred port first
        if preferred_port not in exclude_set:
            port_info = self.check_port_status(preferred_port)
            if port_info.status == PortStatus.AVAILABLE:
                logger.info(f"✅ Preferred port {preferred_port} is available")
                return preferred_port
            else:
                logger.info(f"⚠️ Preferred port {preferred_port} is {port_info.status.value}")
                if port_info.pid:
                    logger.info(f"   Occupied by PID {port_info.pid}: {port_info.process_name}")
        
        # Search in range
        start_port, end_port = port_range
        for port in range(start_port, end_port + 1):
            if port in exclude_set:
                continue
                
            port_info = self.check_port_status(port)
            if port_info.status == PortStatus.AVAILABLE:
                logger.info(f"✅ Found available port: {port}")
                return port
        
        # If no port found, try system-assigned port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            port = s.getsockname()[1]
            logger.info(f"✅ Using system-assigned port: {port}")
            return port
    
    def check_port_status(self, port: int, force_refresh: bool = False) -> PortInfo:
        """
        Check the status of a specific port
        
        Args:
            port: Port number to check
            force_refresh: Force refresh instead of using cache
            
        Returns:
            PortInfo with detailed port information
        """
        cache_key = port
        
        # Check cache first
        if not force_refresh and cache_key in self._port_cache:
            cached_info = self._port_cache[cache_key]
            if time.time() - getattr(cached_info, '_cached_at', 0) < self.cache_ttl:
                return cached_info
        
        logger.debug(f"Checking port status: {port}")
        
        # Check if port is available
        port_info = self._check_port_availability(port)
        
        # If occupied, get process information
        if port_info.status == PortStatus.OCCUPIED:
            self._enrich_port_info_with_process(port_info)
        
        # Cache the result
        port_info._cached_at = time.time()
        self._port_cache[cache_key] = port_info
        
        return port_info
    
    def _check_port_availability(self, port: int) -> PortInfo:
        """Check if a port is available for binding"""
        try:
            # Try to bind to the port
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('', port))
                return PortInfo(port=port, status=PortStatus.AVAILABLE)
        except OSError as e:
            if e.errno == 98:  # Address already in use
                return PortInfo(port=port, status=PortStatus.OCCUPIED)
            elif e.errno == 13:  # Permission denied
                return PortInfo(port=port, status=PortStatus.BLOCKED)
            else:
                return PortInfo(port=port, status=PortStatus.OCCUPIED)
    
    def _enrich_port_info_with_process(self, port_info: PortInfo):
        """Enrich port info with process details"""
        try:
            # Find process using the port
            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr.port == port_info.port and conn.status == psutil.CONN_LISTEN:
                    try:
                        process = psutil.Process(conn.pid)
                        port_info.pid = conn.pid
                        port_info.process_name = process.name()
                        port_info.command_line = ' '.join(process.cmdline())
                        port_info.user = process.username()
                        port_info.listening_address = conn.laddr.ip
                        port_info.process_type = self._identify_process_type(process)
                        port_info.can_terminate = self._can_terminate_process(process)
                        break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                        
        except Exception as e:
            logger.debug(f"Failed to get process info for port {port_info.port}: {e}")
    
    def _identify_process_type(self, process: psutil.Process) -> ProcessType:
        """Identify the type of process"""
        try:
            name = process.name().lower()
            cmdline = ' '.join(process.cmdline()).lower()
            
            if 'uvicorn' in name or 'uvicorn' in cmdline:
                return ProcessType.UVICORN
            elif 'fastapi' in cmdline or 'main:app' in cmdline:
                return ProcessType.FASTAPI
            elif name == 'python' or name.startswith('python'):
                return ProcessType.PYTHON
            elif name == 'node' or name.startswith('node'):
                return ProcessType.NODE
            elif name == 'nginx':
                return ProcessType.NGINX
            else:
                return ProcessType.UNKNOWN
                
        except Exception:
            return ProcessType.UNKNOWN
    
    def _can_terminate_process(self, process: psutil.Process) -> bool:
        """Check if we can safely terminate a process"""
        try:
            # Check if it's our own process or child process
            current_pid = os.getpid()
            if process.pid == current_pid:
                return False  # Don't terminate ourselves
            
            # Check if it's a child process
            try:
                current_process = psutil.Process(current_pid)
                if process.pid in [child.pid for child in current_process.children(recursive=True)]:
                    return True  # Can terminate our own child processes
            except:
                pass
            
            # Check if it's a development server (uvicorn, fastapi)
            process_type = self._identify_process_type(process)
            if process_type in [ProcessType.UVICORN, ProcessType.FASTAPI]:
                # Only terminate if it's likely a development server
                cmdline = ' '.join(process.cmdline()).lower()
                if '--reload' in cmdline or 'main:app' in cmdline:
                    return True
            
            return False
            
        except Exception:
            return False
    
    def resolve_port_conflict(self, port: int, allow_termination: bool = True) -> Optional[int]:
        """
        Resolve port conflict by terminating conflicting processes or finding alternative
        
        Args:
            port: Port with conflict
            allow_termination: Whether to terminate conflicting processes
            
        Returns:
            Available port (original or alternative)
        """
        logger.info(f"🔧 Resolving port conflict for port {port}")
        
        port_info = self.check_port_status(port, force_refresh=True)
        
        if port_info.status == PortStatus.AVAILABLE:
            logger.info(f"✅ Port {port} is now available")
            return port
        
        if port_info.status != PortStatus.OCCUPIED:
            logger.warning(f"⚠️ Port {port} is {port_info.status.value}, cannot resolve")
            return None
        
        # Try to terminate conflicting process if allowed
        if allow_termination and port_info.can_terminate and port_info.pid:
            logger.info(f"🔄 Attempting to terminate process {port_info.pid} ({port_info.process_name})")
            
            if self._terminate_process(port_info.pid):
                # Wait a bit and check if port is available
                time.sleep(2)
                new_port_info = self.check_port_status(port, force_refresh=True)
                if new_port_info.status == PortStatus.AVAILABLE:
                    logger.info(f"✅ Port {port} is now available after termination")
                    return port
        
        # If we can't terminate or termination failed, find alternative port
        logger.info(f"🔍 Finding alternative port for {port}")
        alternative_port = self.find_available_port(
            preferred_port=port + 1,
            port_range=(port + 1, port + 100),
            exclude_ports=[port]
        )
        
        logger.info(f"✅ Alternative port found: {alternative_port}")
        return alternative_port
    
    def _terminate_process(self, pid: int) -> bool:
        """Terminate a process by PID"""
        try:
            process = psutil.Process(pid)
            
            # Try graceful termination first
            logger.debug(f"Sending SIGTERM to process {pid}")
            process.terminate()
            
            # Wait for graceful termination
            try:
                process.wait(timeout=5)
                logger.info(f"✅ Process {pid} terminated gracefully")
                return True
            except psutil.TimeoutExpired:
                # Force kill if graceful termination failed
                logger.debug(f"Sending SIGKILL to process {pid}")
                process.kill()
                process.wait(timeout=5)
                logger.info(f"✅ Process {pid} force killed")
                return True
                
        except psutil.NoSuchProcess:
            logger.info(f"✅ Process {pid} no longer exists")
            return True
        except psutil.AccessDenied:
            logger.warning(f"⚠️ Access denied when trying to terminate process {pid}")
            return False
        except Exception as e:
            logger.warning(f"⚠️ Failed to terminate process {pid}: {e}")
            return False
    
    def kill_processes_on_port(self, port: int, force: bool = False) -> bool:
        """
        Kill all processes using a specific port
        
        Args:
            port: Port number
            force: Force kill even if process can't be safely terminated
            
        Returns:
            True if all processes were killed
        """
        logger.info(f"🔧 Killing processes on port {port}")
        
        port_info = self.check_port_status(port, force_refresh=True)
        
        if port_info.status != PortStatus.OCCUPIED:
            logger.info(f"✅ Port {port} is not occupied")
            return True
        
        if not port_info.pid:
            logger.warning(f"⚠️ No process ID found for port {port}")
            return False
        
        # Check if we can terminate the process
        if not force and not port_info.can_terminate:
            logger.warning(f"⚠️ Cannot safely terminate process {port_info.pid} on port {port}")
            return False
        
        # Terminate the process
        success = self._terminate_process(port_info.pid)
        
        if success:
            # Clear cache for this port
            self._port_cache.pop(port, None)
            logger.info(f"✅ Successfully killed processes on port {port}")
        else:
            logger.error(f"❌ Failed to kill processes on port {port}")
        
        return success
    
    def get_port_usage_report(self, ports: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Get a comprehensive port usage report
        
        Args:
            ports: Specific ports to check (if None, checks common service ports)
            
        Returns:
            Port usage report
        """
        if ports is None:
            ports = []
            for port_list in self._service_ports.values():
                ports.extend(port_list)
            ports = list(set(ports))  # Remove duplicates
        
        report = {
            'environment_type': self._env_info.environment_type.value,
            'timestamp': time.time(),
            'ports_checked': len(ports),
            'available_ports': [],
            'occupied_ports': [],
            'blocked_ports': [],
            'processes': {}
        }
        
        for port in sorted(ports):
            port_info = self.check_port_status(port)
            
            port_data = {
                'port': port,
                'status': port_info.status.value,
                'pid': port_info.pid,
                'process_name': port_info.process_name,
                'process_type': port_info.process_type.value if port_info.process_type else None,
                'can_terminate': port_info.can_terminate
            }
            
            if port_info.status == PortStatus.AVAILABLE:
                report['available_ports'].append(port_data)
            elif port_info.status == PortStatus.OCCUPIED:
                report['occupied_ports'].append(port_data)
                if port_info.pid:
                    report['processes'][port_info.pid] = {
                        'name': port_info.process_name,
                        'command': port_info.command_line,
                        'user': port_info.user,
                        'ports': [port]
                    }
            elif port_info.status == PortStatus.BLOCKED:
                report['blocked_ports'].append(port_data)
        
        return report
    
    def cleanup_stale_processes(self, 
                               process_patterns: Optional[List[str]] = None,
                               max_age_seconds: int = 3600) -> Dict[str, Any]:
        """
        Clean up stale processes that might be holding ports
        
        Args:
            process_patterns: Process name patterns to look for
            max_age_seconds: Maximum age of processes to keep
            
        Returns:
            Cleanup report
        """
        if process_patterns is None:
            process_patterns = ['uvicorn', 'fastapi', 'main:app']
        
        logger.info(f"🧹 Cleaning up stale processes (patterns: {process_patterns})")
        
        cleanup_report = {
            'processes_found': 0,
            'processes_terminated': 0,
            'ports_freed': [],
            'errors': []
        }
        
        try:
            current_time = time.time()
            
            for process in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    process_info = process.info
                    process_age = current_time - process_info['create_time']
                    
                    # Skip processes that are too young
                    if process_age < max_age_seconds:
                        continue
                    
                    # Check if process matches our patterns
                    cmdline = ' '.join(process_info['cmdline'] or []).lower()
                    name = process_info['name'].lower()
                    
                    matches_pattern = any(
                        pattern.lower() in name or pattern.lower() in cmdline
                        for pattern in process_patterns
                    )
                    
                    if matches_pattern:
                        cleanup_report['processes_found'] += 1
                        
                        # Get ports used by this process
                        process_ports = []
                        try:
                            for conn in process.connections(kind='inet'):
                                if conn.status == psutil.CONN_LISTEN:
                                    process_ports.append(conn.laddr.port)
                        except:
                            pass
                        
                        # Terminate the process
                        if self._terminate_process(process_info['pid']):
                            cleanup_report['processes_terminated'] += 1
                            cleanup_report['ports_freed'].extend(process_ports)
                            logger.info(f"✅ Terminated stale process {process_info['pid']}: {name}")
                        else:
                            cleanup_report['errors'].append(
                                f"Failed to terminate process {process_info['pid']}: {name}"
                            )
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    cleanup_report['errors'].append(f"Process access error: {e}")
                
        except Exception as e:
            cleanup_report['errors'].append(f"Cleanup error: {e}")
            logger.error(f"Cleanup error: {e}")
        
        logger.info(f"✅ Cleanup completed: {cleanup_report['processes_terminated']}/{cleanup_report['processes_found']} processes terminated")
        
        return cleanup_report
    
    def reserve_port(self, port: int):
        """Reserve a port to prevent it from being allocated"""
        self._reserved_ports.add(port)
        logger.debug(f"Reserved port {port}")
    
    def release_port(self, port: int):
        """Release a reserved port"""
        self._reserved_ports.discard(port)
        logger.debug(f"Released port {port}")
    
    def get_reserved_ports(self) -> List[int]:
        """Get list of reserved ports"""
        return list(self._reserved_ports)
    
    def clear_cache(self):
        """Clear the port information cache"""
        self._port_cache.clear()
        logger.info("Port manager cache cleared")

# Global port manager instance
port_manager = PortManager()

# Convenience functions
def find_available_port(preferred_port: int = 8000) -> int:
    """Find an available port"""
    return port_manager.find_available_port(preferred_port)

def check_port_available(port: int) -> bool:
    """Check if a port is available"""
    return port_manager.check_port_status(port).status == PortStatus.AVAILABLE

def resolve_port_conflict(port: int) -> Optional[int]:
    """Resolve port conflict"""
    return port_manager.resolve_port_conflict(port)

def kill_processes_on_port(port: int) -> bool:
    """Kill processes on a specific port"""
    return port_manager.kill_processes_on_port(port)

def cleanup_stale_processes() -> Dict[str, Any]:
    """Clean up stale processes"""
    return port_manager.cleanup_stale_processes()

if __name__ == "__main__":
    # Test the port manager
    import json
    
    manager = PortManager()
    
    print("Port Usage Report:")
    report = manager.get_port_usage_report([8000, 8001, 3000, 5000])
    print(json.dumps(report, indent=2, default=str))
    
    print(f"\nTesting port 8000 availability:")
    port_info = manager.check_port_status(8000)
    print(f"Port 8000: {port_info.status.value}")
    if port_info.pid:
        print(f"  Process: {port_info.process_name} (PID: {port_info.pid})")
        print(f"  Can terminate: {port_info.can_terminate}")
    
    print(f"\nFinding available port:")
    available_port = manager.find_available_port(8000)
    print(f"Available port: {available_port}")