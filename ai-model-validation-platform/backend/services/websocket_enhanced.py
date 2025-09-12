"""
Enhanced WebSocket Service - Real-time updates for detection results and monitoring
Provides comprehensive real-time communication for the results pipeline
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)

class EnhancedWebSocketService:
    """Enhanced WebSocket service for real-time detection results and monitoring"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        self.session_subscribers: Dict[str, Set[str]] = defaultdict(set)  # test_session_id -> connection_ids
        self.project_subscribers: Dict[str, Set[str]] = defaultdict(set)  # project_id -> connection_ids
        self.lock = threading.RLock()
        
    async def connect(self, websocket: WebSocket, connection_type: str = "general") -> str:
        """Accept WebSocket connection and return connection ID"""
        connection_id = str(uuid.uuid4())
        
        try:
            await websocket.accept()
            
            with self.lock:
                self.active_connections[connection_id] = websocket
                self.connection_metadata[connection_id] = {
                    "connection_type": connection_type,
                    "connected_at": datetime.now(timezone.utc),
                    "subscriptions": set(),
                    "last_activity": datetime.now(timezone.utc)
                }
            
            # Send connection confirmation
            await self._send_to_connection(connection_id, {
                "type": "connection_established",
                "connection_id": connection_id,
                "connection_type": connection_type,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            logger.info(f"WebSocket connection established: {connection_id} ({connection_type})")
            return connection_id
            
        except Exception as e:
            logger.error(f"Error establishing WebSocket connection: {e}")
            raise
    
    async def disconnect(self, connection_id: str):
        """Disconnect WebSocket and clean up subscriptions"""
        try:
            with self.lock:
                # Remove from all subscriptions
                for session_id in list(self.session_subscribers.keys()):
                    self.session_subscribers[session_id].discard(connection_id)
                    if not self.session_subscribers[session_id]:
                        del self.session_subscribers[session_id]
                
                for project_id in list(self.project_subscribers.keys()):
                    self.project_subscribers[project_id].discard(connection_id)
                    if not self.project_subscribers[project_id]:
                        del self.project_subscribers[project_id]
                
                # Remove connection
                if connection_id in self.active_connections:
                    del self.active_connections[connection_id]
                if connection_id in self.connection_metadata:
                    del self.connection_metadata[connection_id]
            
            logger.info(f"WebSocket connection disconnected: {connection_id}")
            
        except Exception as e:
            logger.error(f"Error disconnecting WebSocket: {e}")
    
    async def handle_message(self, connection_id: str, message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            # Update last activity
            if connection_id in self.connection_metadata:
                self.connection_metadata[connection_id]["last_activity"] = datetime.now(timezone.utc)
            
            if message_type == "subscribe_session":
                await self._handle_session_subscription(connection_id, data)
            elif message_type == "subscribe_project":
                await self._handle_project_subscription(connection_id, data)
            elif message_type == "unsubscribe_session":
                await self._handle_session_unsubscription(connection_id, data)
            elif message_type == "unsubscribe_project":
                await self._handle_project_unsubscription(connection_id, data)
            elif message_type == "ping":
                await self._send_to_connection(connection_id, {
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            elif message_type == "get_status":
                await self._send_status_update(connection_id)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from connection {connection_id}: {e}")
        except Exception as e:
            logger.error(f"Error handling message from {connection_id}: {e}")
    
    async def _handle_session_subscription(self, connection_id: str, data: Dict[str, Any]):
        """Handle subscription to test session updates"""
        test_session_id = data.get("test_session_id")
        
        if not test_session_id:
            await self._send_to_connection(connection_id, {
                "type": "error",
                "message": "test_session_id required for session subscription"
            })
            return
        
        with self.lock:
            self.session_subscribers[test_session_id].add(connection_id)
            if connection_id in self.connection_metadata:
                self.connection_metadata[connection_id]["subscriptions"].add(f"session:{test_session_id}")
        
        await self._send_to_connection(connection_id, {
            "type": "subscription_confirmed",
            "subscription_type": "session",
            "test_session_id": test_session_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        logger.info(f"Connection {connection_id} subscribed to session {test_session_id}")
    
    async def _handle_project_subscription(self, connection_id: str, data: Dict[str, Any]):
        """Handle subscription to project updates"""
        project_id = data.get("project_id")
        
        if not project_id:
            await self._send_to_connection(connection_id, {
                "type": "error",
                "message": "project_id required for project subscription"
            })
            return
        
        with self.lock:
            self.project_subscribers[project_id].add(connection_id)
            if connection_id in self.connection_metadata:
                self.connection_metadata[connection_id]["subscriptions"].add(f"project:{project_id}")
        
        await self._send_to_connection(connection_id, {
            "type": "subscription_confirmed",
            "subscription_type": "project",
            "project_id": project_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        logger.info(f"Connection {connection_id} subscribed to project {project_id}")
    
    async def _handle_session_unsubscription(self, connection_id: str, data: Dict[str, Any]):
        """Handle unsubscription from test session updates"""
        test_session_id = data.get("test_session_id")
        
        if test_session_id:
            with self.lock:
                self.session_subscribers[test_session_id].discard(connection_id)
                if connection_id in self.connection_metadata:
                    self.connection_metadata[connection_id]["subscriptions"].discard(f"session:{test_session_id}")
        
        await self._send_to_connection(connection_id, {
            "type": "unsubscription_confirmed",
            "subscription_type": "session",
            "test_session_id": test_session_id
        })
    
    async def _handle_project_unsubscription(self, connection_id: str, data: Dict[str, Any]):
        """Handle unsubscription from project updates"""
        project_id = data.get("project_id")
        
        if project_id:
            with self.lock:
                self.project_subscribers[project_id].discard(connection_id)
                if connection_id in self.connection_metadata:
                    self.connection_metadata[connection_id]["subscriptions"].discard(f"project:{project_id}")
        
        await self._send_to_connection(connection_id, {
            "type": "unsubscription_confirmed",
            "subscription_type": "project",
            "project_id": project_id
        })
    
    async def _send_status_update(self, connection_id: str):
        """Send status update to specific connection"""
        try:
            status = {
                "type": "status_update",
                "active_connections": len(self.active_connections),
                "session_subscriptions": {
                    session_id: len(subscribers) 
                    for session_id, subscribers in self.session_subscribers.items()
                },
                "project_subscriptions": {
                    project_id: len(subscribers) 
                    for project_id, subscribers in self.project_subscribers.items()
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            if connection_id in self.connection_metadata:
                status["connection_metadata"] = {
                    "connection_type": self.connection_metadata[connection_id]["connection_type"],
                    "connected_at": self.connection_metadata[connection_id]["connected_at"].isoformat(),
                    "subscriptions": list(self.connection_metadata[connection_id]["subscriptions"]),
                    "last_activity": self.connection_metadata[connection_id]["last_activity"].isoformat()
                }
            
            await self._send_to_connection(connection_id, status)
            
        except Exception as e:
            logger.error(f"Error sending status update: {e}")
    
    async def broadcast_to_session(self, test_session_id: str, message: Dict[str, Any]):
        """Broadcast message to all subscribers of a test session"""
        subscribers = self.session_subscribers.get(test_session_id, set())
        
        if not subscribers:
            logger.debug(f"No subscribers for session {test_session_id}")
            return
        
        logger.info(f"Broadcasting to {len(subscribers)} subscribers of session {test_session_id}")
        
        # Add session context to message
        enhanced_message = {
            **message,
            "subscription_type": "session",
            "target_session_id": test_session_id
        }
        
        await self._broadcast_to_connections(subscribers, enhanced_message)
    
    async def broadcast_to_project(self, project_id: str, message: Dict[str, Any]):
        """Broadcast message to all subscribers of a project"""
        subscribers = self.project_subscribers.get(project_id, set())
        
        if not subscribers:
            logger.debug(f"No subscribers for project {project_id}")
            return
        
        logger.info(f"Broadcasting to {len(subscribers)} subscribers of project {project_id}")
        
        # Add project context to message
        enhanced_message = {
            **message,
            "subscription_type": "project",
            "target_project_id": project_id
        }
        
        await self._broadcast_to_connections(subscribers, enhanced_message)
    
    async def broadcast_to_all(self, message: Dict[str, Any]):
        """Broadcast message to all active connections"""
        connection_ids = set(self.active_connections.keys())
        
        if not connection_ids:
            logger.debug("No active connections to broadcast to")
            return
        
        logger.info(f"Broadcasting to all {len(connection_ids)} active connections")
        
        enhanced_message = {
            **message,
            "subscription_type": "broadcast"
        }
        
        await self._broadcast_to_connections(connection_ids, enhanced_message)
    
    async def _broadcast_to_connections(self, connection_ids: Set[str], message: Dict[str, Any]):
        """Send message to multiple connections"""
        if not connection_ids:
            return
        
        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        # Send to all connections concurrently
        tasks = []
        for connection_id in list(connection_ids):  # Convert to list to avoid set changed during iteration
            if connection_id in self.active_connections:
                task = asyncio.create_task(self._send_to_connection(connection_id, message))
                tasks.append(task)
        
        if tasks:
            # Wait for all sends to complete, but don't let failures stop others
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_to_connection(self, connection_id: str, message: Dict[str, Any]):
        """Send message to specific connection"""
        try:
            if connection_id not in self.active_connections:
                logger.warning(f"Connection {connection_id} not found")
                return
            
            websocket = self.active_connections[connection_id]
            await websocket.send_text(json.dumps(message))
            
        except WebSocketDisconnect:
            logger.info(f"Connection {connection_id} disconnected during send")
            await self.disconnect(connection_id)
        except Exception as e:
            logger.error(f"Error sending message to connection {connection_id}: {e}")
            # Remove problematic connection
            await self.disconnect(connection_id)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get statistics about current connections"""
        with self.lock:
            return {
                "total_connections": len(self.active_connections),
                "session_subscriptions": len(self.session_subscribers),
                "project_subscriptions": len(self.project_subscribers),
                "connections_by_type": {
                    conn_type: len([
                        cid for cid, meta in self.connection_metadata.items() 
                        if meta.get("connection_type") == conn_type
                    ])
                    for conn_type in set(
                        meta.get("connection_type", "unknown") 
                        for meta in self.connection_metadata.values()
                    )
                }
            }
    
    async def cleanup_inactive_connections(self, max_idle_minutes: int = 30):
        """Clean up connections that have been idle for too long"""
        try:
            cutoff_time = datetime.now(timezone.utc).timestamp() - (max_idle_minutes * 60)
            
            inactive_connections = []
            
            with self.lock:
                for connection_id, metadata in self.connection_metadata.items():
                    last_activity = metadata.get("last_activity", metadata.get("connected_at"))
                    if last_activity and last_activity.timestamp() < cutoff_time:
                        inactive_connections.append(connection_id)
            
            # Disconnect inactive connections
            for connection_id in inactive_connections:
                logger.info(f"Cleaning up inactive connection: {connection_id}")
                await self.disconnect(connection_id)
            
            return len(inactive_connections)
            
        except Exception as e:
            logger.error(f"Error cleaning up inactive connections: {e}")
            return 0

# Global enhanced WebSocket service instance
enhanced_websocket_service = EnhancedWebSocketService()

# Integration with main WebSocket endpoint
async def handle_enhanced_websocket_connection(websocket: WebSocket, connection_type: str = "general"):
    """Handle enhanced WebSocket connection with full feature support"""
    connection_id = None
    
    try:
        # Connect
        connection_id = await enhanced_websocket_service.connect(websocket, connection_type)
        
        # Handle messages
        while True:
            try:
                # Wait for message with timeout to enable periodic cleanup
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                await enhanced_websocket_service.handle_message(connection_id, message)
                
            except asyncio.TimeoutError:
                # Send ping to check if connection is still alive
                await enhanced_websocket_service._send_to_connection(connection_id, {
                    "type": "ping",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if connection_id:
            await enhanced_websocket_service.disconnect(connection_id)