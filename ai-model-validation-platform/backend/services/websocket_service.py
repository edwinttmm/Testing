import asyncio
import json
import logging
from typing import Dict, Set, Any, Optional, List
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
import uuid

from schemas_video_annotation import (
    WebSocketMessage, AnnotationProgressMessage, ValidationResultMessage
)

logger = logging.getLogger(__name__)

class WebSocketManager:
    """WebSocket connection manager for real-time communication"""
    
    def __init__(self):
        # Active connections by connection ID
        self.active_connections: Dict[str, WebSocket] = {}
        
        # Connections grouped by room/channel
        self.rooms: Dict[str, Set[str]] = {}
        
        # Connection metadata
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Message history for replay
        self.message_history: Dict[str, List[Dict]] = {}
        self.max_history_size = 100
    
    async def connect(self, websocket: WebSocket, connection_id: str = None) -> str:
        """Accept new WebSocket connection"""
        if not connection_id:
            connection_id = str(uuid.uuid4())
        
        await websocket.accept()
        
        self.active_connections[connection_id] = websocket
        self.connection_metadata[connection_id] = {
            "connected_at": datetime.utcnow(),
            "client_ip": websocket.client.host if websocket.client else "unknown",
            "rooms": set(),
            "last_activity": datetime.utcnow()
        }
        
        logger.info(f"WebSocket connection established: {connection_id}")
        return connection_id
    
    def disconnect(self, connection_id: str):
        """Remove WebSocket connection"""
        if connection_id in self.active_connections:
            # Remove from all rooms
            if connection_id in self.connection_metadata:
                rooms = self.connection_metadata[connection_id].get("rooms", set())
                for room in rooms:
                    self.leave_room(connection_id, room)
            
            # Clean up connection
            del self.active_connections[connection_id]
            if connection_id in self.connection_metadata:
                del self.connection_metadata[connection_id]
            
            logger.info(f"WebSocket connection closed: {connection_id}")
    
    def join_room(self, connection_id: str, room: str):
        """Add connection to a room"""
        if room not in self.rooms:
            self.rooms[room] = set()
        
        self.rooms[room].add(connection_id)
        
        if connection_id in self.connection_metadata:
            self.connection_metadata[connection_id]["rooms"].add(room)
        
        logger.debug(f"Connection {connection_id} joined room {room}")
    
    def leave_room(self, connection_id: str, room: str):
        """Remove connection from a room"""
        if room in self.rooms:
            self.rooms[room].discard(connection_id)
            
            # Clean up empty rooms
            if not self.rooms[room]:
                del self.rooms[room]
        
        if connection_id in self.connection_metadata:
            self.connection_metadata[connection_id]["rooms"].discard(room)
        
        logger.debug(f"Connection {connection_id} left room {room}")
    
    def create_room(self, room: str):
        """Create a new room"""
        if room not in self.rooms:
            self.rooms[room] = set()
            logger.debug(f"Created room: {room}")
    
    async def send_personal_message(self, message: str, connection_id: str):
        """Send message to specific connection"""
        if connection_id in self.active_connections:
            try:
                websocket = self.active_connections[connection_id]
                await websocket.send_text(message)
                
                # Update last activity
                if connection_id in self.connection_metadata:
                    self.connection_metadata[connection_id]["last_activity"] = datetime.utcnow()
                
            except Exception as e:
                logger.error(f"Error sending message to {connection_id}: {str(e)}")
                self.disconnect(connection_id)
    
    async def send_to_room(self, message: str, room: str):
        """Send message to all connections in a room"""
        if room in self.rooms:
            disconnected = []
            
            for connection_id in self.rooms[room].copy():
                try:
                    await self.send_personal_message(message, connection_id)
                except Exception as e:
                    logger.error(f"Error sending to room {room}, connection {connection_id}: {str(e)}")
                    disconnected.append(connection_id)
            
            # Clean up disconnected connections
            for connection_id in disconnected:
                self.disconnect(connection_id)
            
            # Store message history
            if room not in self.message_history:
                self.message_history[room] = []
            
            self.message_history[room].append({
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "room": room
            })
            
            # Limit history size
            if len(self.message_history[room]) > self.max_history_size:
                self.message_history[room] = self.message_history[room][-self.max_history_size:]
    
    async def broadcast(self, message: str):
        """Send message to all active connections"""
        disconnected = []
        
        for connection_id in list(self.active_connections.keys()):
            try:
                await self.send_personal_message(message, connection_id)
            except Exception as e:
                logger.error(f"Error broadcasting to {connection_id}: {str(e)}")
                disconnected.append(connection_id)
        
        # Clean up disconnected connections
        for connection_id in disconnected:
            self.disconnect(connection_id)
    
    async def send_json(self, data: Dict[str, Any], connection_id: str):
        """Send JSON data to specific connection"""
        message = json.dumps(data, default=str)
        await self.send_personal_message(message, connection_id)
    
    async def send_json_to_room(self, data: Dict[str, Any], room: str):
        """Send JSON data to all connections in a room"""
        message = json.dumps(data, default=str)
        await self.send_to_room(message, room)
    
    async def broadcast_json(self, data: Dict[str, Any]):
        """Broadcast JSON data to all connections"""
        message = json.dumps(data, default=str)
        await self.broadcast(message)
    
    def get_room_history(self, room: str, limit: int = 50) -> List[Dict]:
        """Get message history for a room"""
        if room not in self.message_history:
            return []
        
        return self.message_history[room][-limit:]
    
    def get_connection_count(self) -> int:
        """Get total number of active connections"""
        return len(self.active_connections)
    
    def get_room_count(self, room: str) -> int:
        """Get number of connections in a room"""
        return len(self.rooms.get(room, set()))
    
    def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get connection metadata"""
        return self.connection_metadata.get(connection_id)
    
    def list_rooms(self) -> List[str]:
        """List all active rooms"""
        return list(self.rooms.keys())
    
    async def cleanup_inactive_connections(self, timeout_minutes: int = 30):
        """Clean up inactive connections"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        
        inactive_connections = []
        for connection_id, metadata in self.connection_metadata.items():
            if metadata["last_activity"] < cutoff_time:
                inactive_connections.append(connection_id)
        
        for connection_id in inactive_connections:
            logger.info(f"Cleaning up inactive connection: {connection_id}")
            self.disconnect(connection_id)
        
        return len(inactive_connections)

# Global WebSocket manager instance
websocket_manager = WebSocketManager()

class RealtimeService:
    """Service for real-time communication and notifications"""
    
    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager
    
    async def notify_annotation_progress(
        self, 
        session_id: str, 
        progress_percentage: float,
        current_frame: int,
        total_frames: int
    ):
        """Send annotation progress update"""
        message = AnnotationProgressMessage(
            session_id=session_id,
            progress_percentage=progress_percentage,
            current_frame=current_frame,
            total_frames=total_frames
        )
        
        room = f"annotation_session_{session_id}"
        await self.ws_manager.send_json_to_room(message.dict(), room)
    
    async def notify_validation_result(
        self,
        test_session_id: str,
        detection_id: str,
        validation_result: str,
        confidence_score: float
    ):
        """Send validation result update"""
        message = ValidationResultMessage(
            test_session_id=test_session_id,
            detection_id=detection_id,
            validation_result=validation_result,
            confidence_score=confidence_score
        )
        
        room = f"test_session_{test_session_id}"
        await self.ws_manager.send_json_to_room(message.dict(), room)
    
    async def notify_pre_annotation_status(
        self,
        video_id: str,
        task_id: str,
        status: str,
        progress_percentage: float,
        detections_found: int
    ):
        """Send pre-annotation status update"""
        message_data = {
            "type": "pre_annotation_status",
            "data": {
                "video_id": video_id,
                "task_id": task_id,
                "status": status,
                "progress_percentage": progress_percentage,
                "detections_found": detections_found,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        room = f"video_{video_id}"
        await self.ws_manager.send_json_to_room(message_data, room)
    
    async def notify_signal_detection(
        self,
        video_id: str,
        signal_type: str,
        detected_signals: List[Dict[str, Any]],
        processing_status: str
    ):
        """Send signal detection update"""
        message_data = {
            "type": "signal_detection",
            "data": {
                "video_id": video_id,
                "signal_type": signal_type,
                "detected_signals": detected_signals,
                "total_detections": len(detected_signals),
                "processing_status": processing_status,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        room = f"video_{video_id}"
        await self.ws_manager.send_json_to_room(message_data, room)
    
    async def notify_test_session_update(
        self,
        test_session_id: str,
        status: str,
        current_detections: int,
        metrics: Optional[Dict[str, Any]] = None
    ):
        """Send test session status update"""
        message_data = {
            "type": "test_session_update",
            "data": {
                "test_session_id": test_session_id,
                "status": status,
                "current_detections": current_detections,
                "metrics": metrics or {},
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        room = f"test_session_{test_session_id}"
        await self.ws_manager.send_json_to_room(message_data, room)
    
    async def notify_system_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "info",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Send system-wide alert"""
        message_data = {
            "type": "system_alert",
            "data": {
                "alert_type": alert_type,
                "message": message,
                "severity": severity,
                "metadata": metadata or {},
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        await self.ws_manager.broadcast_json(message_data)
    
    async def get_room_statistics(self) -> Dict[str, Any]:
        """Get WebSocket room statistics"""
        return {
            "total_connections": self.ws_manager.get_connection_count(),
            "active_rooms": len(self.ws_manager.list_rooms()),
            "room_details": {
                room: self.ws_manager.get_room_count(room)
                for room in self.ws_manager.list_rooms()
            }
        }

# Global realtime service instance
realtime_service = RealtimeService(websocket_manager)

# WebSocket endpoint handlers
async def handle_websocket_connection(
    websocket: WebSocket,
    connection_type: str = "general",
    room_id: str = None
):
    """Handle WebSocket connection lifecycle"""
    connection_id = None
    
    try:
        # Accept connection
        connection_id = await websocket_manager.connect(websocket)
        
        # Join specific room if provided
        if room_id:
            websocket_manager.join_room(connection_id, room_id)
        
        # Send welcome message
        welcome_message = {
            "type": "connection_established",
            "data": {
                "connection_id": connection_id,
                "connection_type": connection_type,
                "room_id": room_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        await websocket_manager.send_json(welcome_message, connection_id)
        
        # Send room history if applicable
        if room_id:
            history = websocket_manager.get_room_history(room_id)
            if history:
                history_message = {
                    "type": "room_history",
                    "data": {
                        "room_id": room_id,
                        "history": history
                    }
                }
                await websocket_manager.send_json(history_message, connection_id)
        
        # Keep connection alive and handle messages
        while True:
            try:
                # Wait for messages with timeout
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                
                # Parse and handle message
                try:
                    data = json.loads(message)
                    await handle_websocket_message(connection_id, data)
                except json.JSONDecodeError:
                    # Handle plain text message
                    await handle_websocket_message(connection_id, {"type": "text", "content": message})
                
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                ping_message = {
                    "type": "ping",
                    "timestamp": datetime.utcnow().isoformat()
                }
                await websocket_manager.send_json(ping_message, connection_id)
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        if connection_id:
            websocket_manager.disconnect(connection_id)

async def handle_websocket_message(connection_id: str, message_data: Dict[str, Any]):
    """Handle incoming WebSocket messages"""
    try:
        message_type = message_data.get("type")
        
        if message_type == "ping":
            # Respond to ping
            pong_message = {
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat()
            }
            await websocket_manager.send_json(pong_message, connection_id)
        
        elif message_type == "join_room":
            # Join a room
            room_id = message_data.get("room_id")
            if room_id:
                websocket_manager.join_room(connection_id, room_id)
                
                response = {
                    "type": "room_joined",
                    "data": {
                        "room_id": room_id,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
                await websocket_manager.send_json(response, connection_id)
        
        elif message_type == "leave_room":
            # Leave a room
            room_id = message_data.get("room_id")
            if room_id:
                websocket_manager.leave_room(connection_id, room_id)
                
                response = {
                    "type": "room_left",
                    "data": {
                        "room_id": room_id,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
                await websocket_manager.send_json(response, connection_id)
        
        elif message_type == "subscribe_video":
            # Subscribe to video updates
            video_id = message_data.get("video_id")
            if video_id:
                room_id = f"video_{video_id}"
                websocket_manager.join_room(connection_id, room_id)
        
        elif message_type == "subscribe_test_session":
            # Subscribe to test session updates
            test_session_id = message_data.get("test_session_id")
            if test_session_id:
                room_id = f"test_session_{test_session_id}"
                websocket_manager.join_room(connection_id, room_id)
        
        else:
            logger.warning(f"Unknown message type: {message_type}")
        
    except Exception as e:
        logger.error(f"Error handling WebSocket message: {str(e)}")

# Periodic cleanup task
async def periodic_cleanup():
    """Periodic cleanup of inactive connections"""
    while True:
        try:
            await asyncio.sleep(300)  # Run every 5 minutes
            cleaned_count = await websocket_manager.cleanup_inactive_connections()
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} inactive WebSocket connections")
        except Exception as e:
            logger.error(f"Error in periodic cleanup: {str(e)}")

# Start cleanup task on module import
# asyncio.create_task(periodic_cleanup())
