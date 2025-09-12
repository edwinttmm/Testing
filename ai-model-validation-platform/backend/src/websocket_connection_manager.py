"""
WebSocket Connection Manager - Advanced connection lifecycle management
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class WebSocketConnection:
    """Represents a WebSocket connection with metadata"""
    websocket: WebSocket
    connection_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_ping: Optional[datetime] = None
    status: str = "connecting"
    client_info: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert connection to dictionary for logging/monitoring"""
        return {
            "connection_id": self.connection_id,
            "created_at": self.created_at.isoformat(),
            "last_ping": self.last_ping.isoformat() if self.last_ping else None,
            "status": self.status,
            "client_info": self.client_info,
            "connection_age_ms": (datetime.now(timezone.utc) - self.created_at).total_seconds() * 1000
        }

class WebSocketConnectionManager:
    """
    Advanced WebSocket connection manager with proper lifecycle handling,
    timing synchronization, and connection state management.
    """
    
    def __init__(self):
        self._connections: Dict[str, WebSocketConnection] = {}
        self._lock = asyncio.Lock()
        self._connection_counter = 0
        
    async def generate_connection_id(self) -> str:
        """Generate a unique connection ID with proper timezone handling"""
        self._connection_counter += 1
        timestamp = datetime.now(timezone.utc).timestamp()
        return f"labjack-{int(timestamp * 1000)}-{self._connection_counter}"
    
    async def register_connection(self, websocket: WebSocket, client_info: Optional[Dict] = None) -> str:
        """
        Register a new WebSocket connection with proper lifecycle management
        
        Returns:
            connection_id: Unique identifier for the connection
        """
        connection_id = await self.generate_connection_id()
        
        try:
            # Accept connection with timeout protection
            await asyncio.wait_for(websocket.accept(), timeout=3.0)
            logger.info(f"WebSocket accepted successfully: {connection_id}")
            
            # Create connection object
            connection = WebSocketConnection(
                websocket=websocket,
                connection_id=connection_id,
                client_info=client_info or {},
                status="connected"
            )
            
            # Register in connection registry
            async with self._lock:
                self._connections[connection_id] = connection
            
            # Send immediate connection establishment confirmation
            await self.send_connection_established(connection_id)
            
            # Add stabilization delay to prevent immediate disconnection
            await asyncio.sleep(0.15)  # 150ms stabilization period
            
            logger.info(f"WebSocket connection fully established: {connection_id}")
            return connection_id
            
        except asyncio.TimeoutError:
            logger.error(f"WebSocket accept timeout for {connection_id}")
            raise
        except Exception as e:
            logger.error(f"Failed to register WebSocket connection {connection_id}: {e}")
            raise
    
    async def send_connection_established(self, connection_id: str):
        """Send connection establishment confirmation to client"""
        connection = await self.get_connection(connection_id)
        if connection and connection.websocket:
            try:
                message = {
                    "type": "connection_established",
                    "connection_id": connection_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "server_time_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "status": "ready"
                }
                await connection.websocket.send_text(json.dumps(message))
                logger.info(f"Connection establishment confirmed for {connection_id}")
            except Exception as e:
                logger.error(f"Failed to send connection established message: {e}")
    
    async def get_connection(self, connection_id: str) -> Optional[WebSocketConnection]:
        """Get connection by ID"""
        async with self._lock:
            return self._connections.get(connection_id)
    
    async def update_connection_status(self, connection_id: str, status: str):
        """Update connection status"""
        async with self._lock:
            if connection_id in self._connections:
                self._connections[connection_id].status = status
                logger.debug(f"Connection {connection_id} status updated to: {status}")
    
    async def ping_connection(self, connection_id: str) -> bool:
        """Send ping to connection and update last_ping time"""
        connection = await self.get_connection(connection_id)
        if not connection:
            return False
            
        try:
            ping_message = {
                "type": "ping",
                "connection_id": connection_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "server_time_ms": int(datetime.now(timezone.utc).timestamp() * 1000)
            }
            await connection.websocket.send_text(json.dumps(ping_message))
            
            # Update last ping time
            async with self._lock:
                if connection_id in self._connections:
                    self._connections[connection_id].last_ping = datetime.now(timezone.utc)
            
            return True
        except Exception as e:
            logger.error(f"Failed to ping connection {connection_id}: {e}")
            return False
    
    async def send_message(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """Send message to specific connection"""
        connection = await self.get_connection(connection_id)
        if not connection:
            logger.warning(f"Connection not found: {connection_id}")
            return False
        
        try:
            # Add timestamp to all messages
            message["timestamp"] = datetime.now(timezone.utc).isoformat()
            message["server_time_ms"] = int(datetime.now(timezone.utc).timestamp() * 1000)
            
            await connection.websocket.send_text(json.dumps(message))
            return True
        except WebSocketDisconnect:
            logger.info(f"Connection {connection_id} disconnected during send")
            await self.unregister_connection(connection_id)
            return False
        except Exception as e:
            logger.error(f"Failed to send message to {connection_id}: {e}")
            return False
    
    async def broadcast_message(self, message: Dict[str, Any], exclude: Optional[list] = None):
        """Broadcast message to all connections"""
        exclude = exclude or []
        
        async with self._lock:
            connection_ids = list(self._connections.keys())
        
        for connection_id in connection_ids:
            if connection_id not in exclude:
                await self.send_message(connection_id, message.copy())
    
    async def unregister_connection(self, connection_id: str) -> Optional[WebSocketConnection]:
        """Unregister connection and clean up"""
        async with self._lock:
            connection = self._connections.pop(connection_id, None)
            
        if connection:
            logger.info(f"WebSocket connection unregistered: {connection_id} "
                       f"(duration: {(datetime.now(timezone.utc) - connection.created_at).total_seconds():.2f}s)")
            
            # Log connection statistics
            connection_info = connection.to_dict()
            logger.debug(f"Connection stats: {connection_info}")
            
        return connection
    
    async def get_connection_count(self) -> int:
        """Get current connection count"""
        async with self._lock:
            return len(self._connections)
    
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get comprehensive connection statistics"""
        async with self._lock:
            connections = list(self._connections.values())
        
        if not connections:
            return {"total_connections": 0, "connections": []}
        
        now = datetime.now(timezone.utc)
        stats = {
            "total_connections": len(connections),
            "connections": [conn.to_dict() for conn in connections],
            "average_age_ms": sum((now - conn.created_at).total_seconds() * 1000 for conn in connections) / len(connections),
            "oldest_connection_age_ms": max((now - conn.created_at).total_seconds() * 1000 for conn in connections),
            "newest_connection_age_ms": min((now - conn.created_at).total_seconds() * 1000 for conn in connections)
        }
        
        return stats
    
    async def cleanup_stale_connections(self, max_age_seconds: int = 300):
        """Clean up connections that haven't pinged recently"""
        now = datetime.now(timezone.utc)
        stale_connections = []
        
        async with self._lock:
            for connection_id, connection in self._connections.items():
                age = (now - connection.created_at).total_seconds()
                last_ping_age = (now - connection.last_ping).total_seconds() if connection.last_ping else age
                
                if age > max_age_seconds or last_ping_age > max_age_seconds:
                    stale_connections.append(connection_id)
        
        for connection_id in stale_connections:
            logger.info(f"Cleaning up stale connection: {connection_id}")
            await self.unregister_connection(connection_id)
        
        return len(stale_connections)

# Global connection manager instance
connection_manager = WebSocketConnectionManager()

# Background task for connection maintenance
async def start_connection_maintenance():
    """Background task for connection health monitoring"""
    while True:
        try:
            await asyncio.sleep(30)  # Check every 30 seconds
            
            # Clean up stale connections
            cleaned = await connection_manager.cleanup_stale_connections()
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} stale connections")
            
            # Log connection statistics
            stats = await connection_manager.get_connection_stats()
            if stats["total_connections"] > 0:
                logger.debug(f"Connection stats: {stats['total_connections']} active, "
                           f"avg age: {stats['average_age_ms']:.0f}ms")
                
        except Exception as e:
            logger.error(f"Error in connection maintenance: {e}")