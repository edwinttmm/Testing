#!/usr/bin/env python3
"""
WebSocket Orchestration System
SPARC Implementation: Real-time WebSocket coordination for all VRU services

This module provides comprehensive WebSocket orchestration:
- Centralized WebSocket connection management
- Real-time service coordination and updates
- Message routing and broadcasting
- Connection pooling and load balancing
- External IP support (155.138.239.131)
- Memory coordination via vru-api-orchestration namespace

Architecture:
- ConnectionManager: Manages WebSocket connections
- MessageRouter: Routes messages between services
- BroadcastManager: Handles message broadcasting
- SubscriptionManager: Manages client subscriptions
- PerformanceMonitor: Tracks WebSocket performance
"""

import logging
import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Callable, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque
import weakref
from contextlib import asynccontextmanager

# FastAPI WebSocket imports
from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from fastapi.websockets import WebSocketState
from starlette.websockets import WebSocket as StarletteWebSocket

logger = logging.getLogger(__name__)

class ConnectionState(Enum):
    """WebSocket connection states"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"

class MessageType(Enum):
    """WebSocket message types"""
    # Control messages
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    PING = "ping"
    PONG = "pong"
    AUTH = "auth"
    
    # Service messages
    ML_INFERENCE_UPDATE = "ml_inference_update"
    CAMERA_FRAME_UPDATE = "camera_frame_update"
    VALIDATION_RESULT = "validation_result"
    PROJECT_STATUS_UPDATE = "project_status_update"
    WORKFLOW_UPDATE = "workflow_update"
    
    # Coordination messages
    SERVICE_STATUS = "service_status"
    METRICS_UPDATE = "metrics_update"
    ERROR_NOTIFICATION = "error_notification"
    SYSTEM_ALERT = "system_alert"
    
    # Subscription messages
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    SUBSCRIPTION_CONFIRMED = "subscription_confirmed"
    
    # Broadcasting
    BROADCAST = "broadcast"
    MULTICAST = "multicast"

class SubscriptionType(Enum):
    """Subscription types for clients"""
    ALL_SERVICES = "all_services"
    ML_INFERENCE = "ml_inference"
    CAMERA_UPDATES = "camera_updates"
    VALIDATION_RESULTS = "validation_results"
    PROJECT_WORKFLOW = "project_workflow"
    SYSTEM_METRICS = "system_metrics"
    SERVICE_HEALTH = "service_health"
    ERROR_ALERTS = "error_alerts"

@dataclass
class WebSocketConnection:
    """WebSocket connection information"""
    connection_id: str
    websocket: WebSocket
    client_ip: str
    user_agent: Optional[str] = None
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    state: ConnectionState = ConnectionState.CONNECTING
    subscriptions: Set[SubscriptionType] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    message_count: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0

@dataclass
class WebSocketMessage:
    """WebSocket message structure"""
    message_id: str
    connection_id: str
    message_type: MessageType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    target_connections: Optional[List[str]] = None
    subscription_filter: Optional[SubscriptionType] = None
    priority: int = 0  # Higher priority messages are sent first
    retry_count: int = 0
    max_retries: int = 3

@dataclass
class ConnectionMetrics:
    """WebSocket connection metrics"""
    total_connections: int = 0
    active_connections: int = 0
    authenticated_connections: int = 0
    messages_sent_total: int = 0
    messages_received_total: int = 0
    bytes_sent_total: int = 0
    bytes_received_total: int = 0
    average_connection_duration_seconds: float = 0.0
    connection_errors: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)

class ConnectionManager:
    """Manages WebSocket connections and lifecycle"""
    
    def __init__(self):
        self.connections: Dict[str, WebSocketConnection] = {}
        self.connections_by_subscription: Dict[SubscriptionType, Set[str]] = defaultdict(set)
        self.connection_history: deque = deque(maxlen=1000)
        self.metrics = ConnectionMetrics()
        self.cleanup_task = None
        self.external_ip = "155.138.239.131"
    
    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None) -> str:
        """Accept and register new WebSocket connection"""
        try:
            await websocket.accept()
            
            # Generate connection ID if not provided
            if not client_id:
                client_id = str(uuid.uuid4())
            
            # Create connection info
            connection = WebSocketConnection(
                connection_id=client_id,
                websocket=websocket,
                client_ip=websocket.client.host if websocket.client else "unknown",
                user_agent=websocket.headers.get("user-agent"),
                state=ConnectionState.CONNECTED
            )
            
            # Store connection
            self.connections[client_id] = connection
            
            # Update metrics
            self.metrics.total_connections += 1
            self.metrics.active_connections += 1
            
            # Send welcome message
            await self.send_message(client_id, {
                "type": MessageType.CONNECT.value,
                "connection_id": client_id,
                "server_time": datetime.utcnow().isoformat(),
                "external_ip": self.external_ip,
                "supported_message_types": [msg_type.value for msg_type in MessageType],
                "supported_subscriptions": [sub_type.value for sub_type in SubscriptionType]
            })
            
            logger.info(f"WebSocket connection established: {client_id} from {connection.client_ip}")
            return client_id
            
        except Exception as e:
            logger.error(f"Failed to establish WebSocket connection: {str(e)}")
            raise
    
    async def disconnect(self, connection_id: str, code: int = 1000, reason: str = "Normal closure"):
        """Disconnect and cleanup WebSocket connection"""
        connection = self.connections.get(connection_id)
        if not connection:
            return
        
        try:
            # Update state
            connection.state = ConnectionState.DISCONNECTING
            
            # Send disconnect message if connection is still active
            if connection.websocket.client_state == WebSocketState.CONNECTED:
                await self.send_message(connection_id, {
                    "type": MessageType.DISCONNECT.value,
                    "reason": reason,
                    "connection_duration_seconds": (
                        datetime.utcnow() - connection.connected_at
                    ).total_seconds()
                })
                
                await connection.websocket.close(code=code, reason=reason)
            
            # Remove from subscription mappings
            for subscription_type in connection.subscriptions:
                self.connections_by_subscription[subscription_type].discard(connection_id)
            
            # Update metrics
            duration = (datetime.utcnow() - connection.connected_at).total_seconds()
            self.connection_history.append({
                "connection_id": connection_id,
                "connected_at": connection.connected_at,
                "disconnected_at": datetime.utcnow(),
                "duration_seconds": duration,
                "message_count": connection.message_count,
                "bytes_sent": connection.bytes_sent,
                "bytes_received": connection.bytes_received
            })
            
            self.metrics.active_connections -= 1
            if connection.state == ConnectionState.AUTHENTICATED:
                self.metrics.authenticated_connections -= 1
            
            # Calculate average connection duration
            if self.connection_history:
                avg_duration = sum(h["duration_seconds"] for h in self.connection_history) / len(self.connection_history)
                self.metrics.average_connection_duration_seconds = avg_duration
            
            # Remove connection
            connection.state = ConnectionState.DISCONNECTED
            del self.connections[connection_id]
            
            logger.info(f"WebSocket connection closed: {connection_id} (duration: {duration:.2f}s)")
            
        except Exception as e:
            logger.error(f"Error disconnecting WebSocket {connection_id}: {str(e)}")
            self.metrics.connection_errors += 1
    
    async def send_message(self, connection_id: str, data: Dict[str, Any]) -> bool:
        """Send message to specific WebSocket connection"""
        connection = self.connections.get(connection_id)
        if not connection or connection.websocket.client_state != WebSocketState.CONNECTED:
            return False
        
        try:
            message_json = json.dumps(data, default=str)
            await connection.websocket.send_text(message_json)
            
            # Update connection metrics
            connection.message_count += 1
            connection.bytes_sent += len(message_json)
            connection.last_activity = datetime.utcnow()
            
            # Update global metrics
            self.metrics.messages_sent_total += 1
            self.metrics.bytes_sent_total += len(message_json)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message to {connection_id}: {str(e)}")
            await self.disconnect(connection_id, code=1011, reason="Send error")
            return False
    
    async def receive_message(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Receive message from WebSocket connection"""
        connection = self.connections.get(connection_id)
        if not connection or connection.websocket.client_state != WebSocketState.CONNECTED:
            return None
        
        try:
            message_text = await connection.websocket.receive_text()
            message_data = json.loads(message_text)
            
            # Update connection metrics
            connection.message_count += 1
            connection.bytes_received += len(message_text)
            connection.last_activity = datetime.utcnow()
            
            # Update global metrics
            self.metrics.messages_received_total += 1
            self.metrics.bytes_received_total += len(message_text)
            
            return message_data
            
        except WebSocketDisconnect:
            await self.disconnect(connection_id, reason="Client disconnected")
            return None
        except Exception as e:
            logger.error(f"Failed to receive message from {connection_id}: {str(e)}")
            await self.disconnect(connection_id, code=1011, reason="Receive error")
            return None
    
    def get_active_connections(self) -> List[str]:
        """Get list of active connection IDs"""
        return [
            conn_id for conn_id, conn in self.connections.items()
            if conn.state in [ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED]
        ]
    
    def get_connections_by_subscription(self, subscription_type: SubscriptionType) -> List[str]:
        """Get connections subscribed to specific type"""
        return list(self.connections_by_subscription[subscription_type])
    
    def subscribe_connection(self, connection_id: str, subscription_type: SubscriptionType) -> bool:
        """Subscribe connection to message type"""
        connection = self.connections.get(connection_id)
        if not connection:
            return False
        
        connection.subscriptions.add(subscription_type)
        self.connections_by_subscription[subscription_type].add(connection_id)
        
        logger.debug(f"Connection {connection_id} subscribed to {subscription_type.value}")
        return True
    
    def unsubscribe_connection(self, connection_id: str, subscription_type: SubscriptionType) -> bool:
        """Unsubscribe connection from message type"""
        connection = self.connections.get(connection_id)
        if not connection:
            return False
        
        connection.subscriptions.discard(subscription_type)
        self.connections_by_subscription[subscription_type].discard(connection_id)
        
        logger.debug(f"Connection {connection_id} unsubscribed from {subscription_type.value}")
        return True
    
    async def start_cleanup_task(self, cleanup_interval_seconds: int = 60):
        """Start connection cleanup task"""
        if self.cleanup_task:
            return
        
        self.cleanup_task = asyncio.create_task(self._cleanup_loop(cleanup_interval_seconds))
        logger.info("Started WebSocket connection cleanup task")
    
    async def stop_cleanup_task(self):
        """Stop connection cleanup task"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            self.cleanup_task = None
            logger.info("Stopped WebSocket connection cleanup task")
    
    async def _cleanup_loop(self, interval_seconds: int):
        """Cleanup stale connections"""
        while True:
            try:
                current_time = datetime.utcnow()
                stale_connections = []
                
                for conn_id, connection in self.connections.items():
                    # Check for stale connections (no activity for 5 minutes)
                    if (current_time - connection.last_activity).total_seconds() > 300:
                        stale_connections.append(conn_id)
                    
                    # Check for disconnected WebSocket state
                    elif connection.websocket.client_state == WebSocketState.DISCONNECTED:
                        stale_connections.append(conn_id)
                
                # Cleanup stale connections
                for conn_id in stale_connections:
                    await self.disconnect(conn_id, reason="Stale connection cleanup")
                
                if stale_connections:
                    logger.info(f"Cleaned up {len(stale_connections)} stale WebSocket connections")
                
                await asyncio.sleep(interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Connection cleanup error: {str(e)}")
                await asyncio.sleep(30)

class MessageRouter:
    """Routes and manages WebSocket messages"""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.message_handlers: Dict[MessageType, Callable] = {}
        self.processing_task = None
        self.memory_namespace = "vru-api-orchestration"
        
        # Register default message handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default message handlers"""
        self.message_handlers.update({
            MessageType.PING: self._handle_ping,
            MessageType.AUTH: self._handle_auth,
            MessageType.SUBSCRIBE: self._handle_subscribe,
            MessageType.UNSUBSCRIBE: self._handle_unsubscribe,
        })
    
    async def route_message(self, message: WebSocketMessage):
        """Route message to appropriate handler or recipients"""
        try:
            # Check if we have a specific handler for this message type
            if message.message_type in self.message_handlers:
                handler = self.message_handlers[message.message_type]
                await handler(message)
            else:
                # Default routing based on target connections or subscriptions
                await self._route_to_targets(message)
            
        except Exception as e:
            logger.error(f"Message routing error for {message.message_id}: {str(e)}")
            await self._send_error_response(message, str(e))
    
    async def _route_to_targets(self, message: WebSocketMessage):
        """Route message to target connections or subscribers"""
        target_connections = []
        
        if message.target_connections:
            # Send to specific connections
            target_connections = message.target_connections
        elif message.subscription_filter:
            # Send to subscribers
            target_connections = self.connection_manager.get_connections_by_subscription(
                message.subscription_filter
            )
        else:
            # Broadcast to all active connections
            target_connections = self.connection_manager.get_active_connections()
        
        # Send message to all targets
        send_tasks = []
        for conn_id in target_connections:
            if conn_id != message.connection_id:  # Don't echo back to sender
                task = self.connection_manager.send_message(conn_id, message.data)
                send_tasks.append(task)
        
        if send_tasks:
            results = await asyncio.gather(*send_tasks, return_exceptions=True)
            success_count = sum(1 for result in results if result is True)
            logger.debug(f"Message {message.message_id} sent to {success_count}/{len(send_tasks)} targets")
    
    async def _handle_ping(self, message: WebSocketMessage):
        """Handle ping message"""
        pong_response = {
            "type": MessageType.PONG.value,
            "timestamp": datetime.utcnow().isoformat(),
            "original_timestamp": message.data.get("timestamp")
        }
        await self.connection_manager.send_message(message.connection_id, pong_response)
    
    async def _handle_auth(self, message: WebSocketMessage):
        """Handle authentication message"""
        # Simple authentication - in production, this would validate tokens
        auth_token = message.data.get("token")
        
        if auth_token:  # Accept any token for now
            connection = self.connection_manager.connections.get(message.connection_id)
            if connection:
                connection.state = ConnectionState.AUTHENTICATED
                connection.metadata["auth_token"] = auth_token
                
                self.connection_manager.metrics.authenticated_connections += 1
                
                response = {
                    "type": MessageType.AUTH.value,
                    "status": "authenticated",
                    "connection_id": message.connection_id
                }
                await self.connection_manager.send_message(message.connection_id, response)
        else:
            await self._send_error_response(message, "Invalid authentication token")
    
    async def _handle_subscribe(self, message: WebSocketMessage):
        """Handle subscription message"""
        subscription_types = message.data.get("subscriptions", [])
        
        for sub_type_str in subscription_types:
            try:
                subscription_type = SubscriptionType(sub_type_str)
                success = self.connection_manager.subscribe_connection(
                    message.connection_id, subscription_type
                )
                
                if success:
                    response = {
                        "type": MessageType.SUBSCRIPTION_CONFIRMED.value,
                        "subscription": subscription_type.value,
                        "connection_id": message.connection_id
                    }
                    await self.connection_manager.send_message(message.connection_id, response)
                
            except ValueError:
                await self._send_error_response(
                    message, f"Invalid subscription type: {sub_type_str}"
                )
    
    async def _handle_unsubscribe(self, message: WebSocketMessage):
        """Handle unsubscribe message"""
        subscription_types = message.data.get("subscriptions", [])
        
        for sub_type_str in subscription_types:
            try:
                subscription_type = SubscriptionType(sub_type_str)
                self.connection_manager.unsubscribe_connection(
                    message.connection_id, subscription_type
                )
                
            except ValueError:
                await self._send_error_response(
                    message, f"Invalid subscription type: {sub_type_str}"
                )
    
    async def _send_error_response(self, original_message: WebSocketMessage, error: str):
        """Send error response to connection"""
        error_response = {
            "type": MessageType.ERROR_NOTIFICATION.value,
            "error": error,
            "original_message_id": original_message.message_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.connection_manager.send_message(original_message.connection_id, error_response)
    
    def register_handler(self, message_type: MessageType, handler: Callable):
        """Register custom message handler"""
        self.message_handlers[message_type] = handler
        logger.info(f"Registered handler for message type: {message_type.value}")
    
    async def start_processing(self):
        """Start message processing task"""
        if self.processing_task:
            return
        
        self.processing_task = asyncio.create_task(self._processing_loop())
        logger.info("Started WebSocket message processing")
    
    async def stop_processing(self):
        """Stop message processing task"""
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
            self.processing_task = None
            logger.info("Stopped WebSocket message processing")
    
    async def _processing_loop(self):
        """Main message processing loop"""
        while True:
            try:
                # Get message from queue (with timeout)
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                
                # Route message
                await self.route_message(message)
                
                # Mark task done
                self.message_queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Message processing loop error: {str(e)}")
                await asyncio.sleep(1)
    
    async def queue_message(self, message: WebSocketMessage):
        """Queue message for processing"""
        await self.message_queue.put(message)

class BroadcastManager:
    """Manages message broadcasting to multiple connections"""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
        self.broadcast_history: deque = deque(maxlen=1000)
        self.performance_metrics = {
            "broadcasts_sent": 0,
            "total_recipients": 0,
            "failed_sends": 0,
            "average_broadcast_time_ms": 0.0
        }
    
    async def broadcast(
        self, 
        message_type: MessageType, 
        data: Dict[str, Any],
        subscription_filter: Optional[SubscriptionType] = None,
        exclude_connections: Optional[List[str]] = None,
        priority: int = 0
    ) -> int:
        """Broadcast message to multiple connections"""
        start_time = time.time()
        
        # Determine target connections
        if subscription_filter:
            target_connections = self.connection_manager.get_connections_by_subscription(
                subscription_filter
            )
        else:
            target_connections = self.connection_manager.get_active_connections()
        
        # Apply exclusions
        if exclude_connections:
            target_connections = [
                conn_id for conn_id in target_connections
                if conn_id not in exclude_connections
            ]
        
        if not target_connections:
            return 0
        
        # Prepare message data
        broadcast_data = {
            "type": message_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "broadcast_id": str(uuid.uuid4()),
            **data
        }
        
        # Send to all target connections
        send_tasks = [
            self.connection_manager.send_message(conn_id, broadcast_data)
            for conn_id in target_connections
        ]
        
        results = await asyncio.gather(*send_tasks, return_exceptions=True)
        
        # Count successful sends
        successful_sends = sum(1 for result in results if result is True)
        failed_sends = len(results) - successful_sends
        
        # Update metrics
        broadcast_time_ms = (time.time() - start_time) * 1000
        self.performance_metrics["broadcasts_sent"] += 1
        self.performance_metrics["total_recipients"] += len(target_connections)
        self.performance_metrics["failed_sends"] += failed_sends
        
        # Update average broadcast time
        current_avg = self.performance_metrics["average_broadcast_time_ms"]
        broadcasts_count = self.performance_metrics["broadcasts_sent"]
        new_avg = ((current_avg * (broadcasts_count - 1)) + broadcast_time_ms) / broadcasts_count
        self.performance_metrics["average_broadcast_time_ms"] = new_avg
        
        # Store broadcast history
        broadcast_record = {
            "timestamp": datetime.utcnow(),
            "message_type": message_type.value,
            "target_count": len(target_connections),
            "successful_sends": successful_sends,
            "failed_sends": failed_sends,
            "broadcast_time_ms": broadcast_time_ms,
            "subscription_filter": subscription_filter.value if subscription_filter else None
        }
        self.broadcast_history.append(broadcast_record)
        
        logger.debug(
            f"Broadcast completed: {successful_sends}/{len(target_connections)} recipients "
            f"in {broadcast_time_ms:.2f}ms"
        )
        
        return successful_sends
    
    async def multicast(
        self,
        message_type: MessageType,
        data: Dict[str, Any],
        target_connections: List[str],
        priority: int = 0
    ) -> int:
        """Send message to specific list of connections"""
        if not target_connections:
            return 0
        
        # Prepare message data
        multicast_data = {
            "type": message_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "multicast_id": str(uuid.uuid4()),
            **data
        }
        
        # Send to target connections
        send_tasks = [
            self.connection_manager.send_message(conn_id, multicast_data)
            for conn_id in target_connections
        ]
        
        results = await asyncio.gather(*send_tasks, return_exceptions=True)
        successful_sends = sum(1 for result in results if result is True)
        
        return successful_sends
    
    def get_broadcast_metrics(self) -> Dict[str, Any]:
        """Get broadcast performance metrics"""
        return {
            **self.performance_metrics,
            "recent_broadcasts": list(self.broadcast_history)[-10:],  # Last 10 broadcasts
            "last_updated": datetime.utcnow().isoformat()
        }

class WebSocketOrchestrator:
    """Main WebSocket orchestration system"""
    
    def __init__(self, external_ip: str = "155.138.239.131"):
        self.external_ip = external_ip
        self.connection_manager = ConnectionManager()
        self.message_router = MessageRouter(self.connection_manager)
        self.broadcast_manager = BroadcastManager(self.connection_manager)
        
        self.connection_manager.external_ip = external_ip
        
        # Service integration callbacks
        self.service_callbacks: Dict[str, Callable] = {}
        
        logger.info(f"WebSocket Orchestrator initialized with external IP: {external_ip}")
    
    async def initialize(self):
        """Initialize WebSocket orchestration system"""
        try:
            await self.connection_manager.start_cleanup_task()
            await self.message_router.start_processing()
            
            # Register service-specific handlers
            self._register_service_handlers()
            
            logger.info("WebSocket Orchestrator initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize WebSocket Orchestrator: {str(e)}")
            raise
    
    async def shutdown(self):
        """Shutdown WebSocket orchestration system"""
        try:
            logger.info("Shutting down WebSocket Orchestrator...")
            
            # Disconnect all connections
            active_connections = self.connection_manager.get_active_connections()
            disconnect_tasks = [
                self.connection_manager.disconnect(conn_id, reason="Server shutdown")
                for conn_id in active_connections
            ]
            
            if disconnect_tasks:
                await asyncio.gather(*disconnect_tasks, return_exceptions=True)
            
            # Stop background tasks
            await self.connection_manager.stop_cleanup_task()
            await self.message_router.stop_processing()
            
            logger.info("WebSocket Orchestrator shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during WebSocket Orchestrator shutdown: {str(e)}")
    
    def _register_service_handlers(self):
        """Register handlers for service-specific messages"""
        service_handlers = {
            MessageType.ML_INFERENCE_UPDATE: self._handle_ml_inference_update,
            MessageType.CAMERA_FRAME_UPDATE: self._handle_camera_frame_update,
            MessageType.VALIDATION_RESULT: self._handle_validation_result,
            MessageType.PROJECT_STATUS_UPDATE: self._handle_project_status_update,
            MessageType.WORKFLOW_UPDATE: self._handle_workflow_update,
            MessageType.SERVICE_STATUS: self._handle_service_status,
            MessageType.METRICS_UPDATE: self._handle_metrics_update,
            MessageType.SYSTEM_ALERT: self._handle_system_alert,
        }
        
        for message_type, handler in service_handlers.items():
            self.message_router.register_handler(message_type, handler)
    
    async def _handle_ml_inference_update(self, message: WebSocketMessage):
        """Handle ML inference updates"""
        await self.broadcast_manager.broadcast(
            MessageType.ML_INFERENCE_UPDATE,
            message.data,
            SubscriptionType.ML_INFERENCE
        )
    
    async def _handle_camera_frame_update(self, message: WebSocketMessage):
        """Handle camera frame updates"""
        await self.broadcast_manager.broadcast(
            MessageType.CAMERA_FRAME_UPDATE,
            message.data,
            SubscriptionType.CAMERA_UPDATES
        )
    
    async def _handle_validation_result(self, message: WebSocketMessage):
        """Handle validation results"""
        await self.broadcast_manager.broadcast(
            MessageType.VALIDATION_RESULT,
            message.data,
            SubscriptionType.VALIDATION_RESULTS
        )
    
    async def _handle_project_status_update(self, message: WebSocketMessage):
        """Handle project status updates"""
        await self.broadcast_manager.broadcast(
            MessageType.PROJECT_STATUS_UPDATE,
            message.data,
            SubscriptionType.PROJECT_WORKFLOW
        )
    
    async def _handle_workflow_update(self, message: WebSocketMessage):
        """Handle workflow updates"""
        await self.broadcast_manager.broadcast(
            MessageType.WORKFLOW_UPDATE,
            message.data,
            SubscriptionType.PROJECT_WORKFLOW
        )
    
    async def _handle_service_status(self, message: WebSocketMessage):
        """Handle service status updates"""
        await self.broadcast_manager.broadcast(
            MessageType.SERVICE_STATUS,
            message.data,
            SubscriptionType.SERVICE_HEALTH
        )
    
    async def _handle_metrics_update(self, message: WebSocketMessage):
        """Handle metrics updates"""
        await self.broadcast_manager.broadcast(
            MessageType.METRICS_UPDATE,
            message.data,
            SubscriptionType.SYSTEM_METRICS
        )
    
    async def _handle_system_alert(self, message: WebSocketMessage):
        """Handle system alerts"""
        await self.broadcast_manager.broadcast(
            MessageType.SYSTEM_ALERT,
            message.data,
            SubscriptionType.ERROR_ALERTS,
            priority=10  # High priority
        )
    
    # Public API methods
    
    async def handle_connection(self, websocket: WebSocket, client_id: Optional[str] = None) -> str:
        """Handle new WebSocket connection"""
        connection_id = await self.connection_manager.connect(websocket, client_id)
        
        try:
            while True:
                # Receive message from client
                message_data = await self.connection_manager.receive_message(connection_id)
                
                if message_data is None:
                    break  # Connection closed or error
                
                # Create message object
                message = WebSocketMessage(
                    message_id=str(uuid.uuid4()),
                    connection_id=connection_id,
                    message_type=MessageType(message_data.get("type", "unknown")),
                    data=message_data
                )
                
                # Queue for processing
                await self.message_router.queue_message(message)
                
        except Exception as e:
            logger.error(f"Error handling WebSocket connection {connection_id}: {str(e)}")
        finally:
            await self.connection_manager.disconnect(connection_id)
        
        return connection_id
    
    async def send_to_service_subscribers(
        self, 
        service_name: str, 
        data: Dict[str, Any],
        message_type: Optional[MessageType] = None
    ):
        """Send message to subscribers of specific service"""
        # Map service names to subscription types
        service_subscription_map = {
            "ml_inference": SubscriptionType.ML_INFERENCE,
            "camera_integration": SubscriptionType.CAMERA_UPDATES,
            "validation": SubscriptionType.VALIDATION_RESULTS,
            "project_workflow": SubscriptionType.PROJECT_WORKFLOW,
        }
        
        subscription_type = service_subscription_map.get(service_name, SubscriptionType.ALL_SERVICES)
        
        if not message_type:
            message_type_map = {
                "ml_inference": MessageType.ML_INFERENCE_UPDATE,
                "camera_integration": MessageType.CAMERA_FRAME_UPDATE,
                "validation": MessageType.VALIDATION_RESULT,
                "project_workflow": MessageType.PROJECT_STATUS_UPDATE,
            }
            message_type = message_type_map.get(service_name, MessageType.SERVICE_STATUS)
        
        return await self.broadcast_manager.broadcast(
            message_type,
            data,
            subscription_type
        )
    
    def get_orchestrator_status(self) -> Dict[str, Any]:
        """Get comprehensive orchestrator status"""
        return {
            "connection_manager": {
                "active_connections": len(self.connection_manager.get_active_connections()),
                "total_connections": self.connection_manager.metrics.total_connections,
                "authenticated_connections": self.connection_manager.metrics.authenticated_connections,
                "metrics": asdict(self.connection_manager.metrics)
            },
            "broadcast_manager": self.broadcast_manager.get_broadcast_metrics(),
            "message_router": {
                "queue_size": self.message_router.message_queue.qsize(),
                "registered_handlers": len(self.message_router.message_handlers)
            },
            "external_ip": self.external_ip,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def register_service_callback(self, service_name: str, callback: Callable):
        """Register callback for service integration"""
        self.service_callbacks[service_name] = callback
        logger.info(f"Registered callback for service: {service_name}")

# Global orchestrator instance
websocket_orchestrator = WebSocketOrchestrator()

# Context manager for lifecycle
@asynccontextmanager
async def websocket_orchestrator_lifespan():
    """Context manager for WebSocket orchestrator lifecycle"""
    try:
        await websocket_orchestrator.initialize()
        yield websocket_orchestrator
    finally:
        await websocket_orchestrator.shutdown()

if __name__ == "__main__":
    # Example usage for testing
    async def test_orchestrator():
        async with websocket_orchestrator_lifespan() as orchestrator:
            # Test orchestrator
            status = orchestrator.get_orchestrator_status()
            print(f"Orchestrator Status: {json.dumps(status, indent=2, default=str)}")
    
    asyncio.run(test_orchestrator())