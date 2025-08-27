"""
Camera WebSocket Handlers for Real-Time Communication
Provides WebSocket endpoints and handlers for camera integration system
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from fastapi.routing import APIRouter

from camera_integration_service import camera_service, camera_api

logger = logging.getLogger(__name__)

# WebSocket router for camera integration
camera_websocket_router = APIRouter()

class CameraWebSocketManager:
    """Enhanced WebSocket manager for camera-specific operations"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.camera_subscriptions: Dict[str, List[str]] = {}  # camera_id -> [client_ids]
        self.client_cameras: Dict[str, List[str]] = {}  # client_id -> [camera_ids]
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str = None) -> str:
        """Connect new camera WebSocket client"""
        if not client_id:
            client_id = f"camera_client_{int(datetime.now().timestamp())}"
        
        try:
            # Use the main service's WebSocket connection method
            await camera_service.connect_websocket(websocket, client_id)
            
            self.active_connections[client_id] = websocket
            self.client_cameras[client_id] = []
            self.connection_metadata[client_id] = {
                "connected_at": datetime.utcnow(),
                "client_ip": websocket.client.host if websocket.client else "unknown",
                "subscribed_cameras": [],
                "last_activity": datetime.utcnow()
            }
            
            logger.info(f"Camera WebSocket client connected: {client_id}")
            return client_id
            
        except Exception as e:
            logger.error(f"Failed to connect camera WebSocket client: {str(e)}")
            raise
    
    def disconnect(self, client_id: str):
        """Disconnect camera WebSocket client"""
        try:
            # Unsubscribe from all cameras
            if client_id in self.client_cameras:
                for camera_id in self.client_cameras[client_id]:
                    self._unsubscribe_from_camera(client_id, camera_id)
                del self.client_cameras[client_id]
            
            # Remove from active connections
            if client_id in self.active_connections:
                del self.active_connections[client_id]
            
            # Remove metadata
            if client_id in self.connection_metadata:
                del self.connection_metadata[client_id]
            
            # Disconnect from main service
            camera_service.disconnect_websocket(client_id)
            
            logger.info(f"Camera WebSocket client disconnected: {client_id}")
            
        except Exception as e:
            logger.error(f"Error disconnecting camera WebSocket client: {str(e)}")
    
    async def subscribe_to_camera(self, client_id: str, camera_id: str) -> bool:
        """Subscribe client to specific camera updates"""
        try:
            if camera_id not in camera_service.cameras:
                return False
            
            # Add to camera subscriptions
            if camera_id not in self.camera_subscriptions:
                self.camera_subscriptions[camera_id] = []
            
            if client_id not in self.camera_subscriptions[camera_id]:
                self.camera_subscriptions[camera_id].append(client_id)
            
            # Add to client cameras
            if client_id not in self.client_cameras:
                self.client_cameras[client_id] = []
            
            if camera_id not in self.client_cameras[client_id]:
                self.client_cameras[client_id].append(camera_id)
            
            # Update metadata
            if client_id in self.connection_metadata:
                self.connection_metadata[client_id]["subscribed_cameras"].append(camera_id)
                self.connection_metadata[client_id]["last_activity"] = datetime.utcnow()
            
            logger.info(f"Client {client_id} subscribed to camera {camera_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to subscribe client to camera: {str(e)}")
            return False
    
    def _unsubscribe_from_camera(self, client_id: str, camera_id: str):
        """Unsubscribe client from camera updates"""
        try:
            # Remove from camera subscriptions
            if camera_id in self.camera_subscriptions:
                if client_id in self.camera_subscriptions[camera_id]:
                    self.camera_subscriptions[camera_id].remove(client_id)
                
                # Clean up empty subscription lists
                if not self.camera_subscriptions[camera_id]:
                    del self.camera_subscriptions[camera_id]
            
            # Remove from client cameras
            if client_id in self.client_cameras:
                if camera_id in self.client_cameras[client_id]:
                    self.client_cameras[client_id].remove(camera_id)
            
            # Update metadata
            if client_id in self.connection_metadata:
                subscribed = self.connection_metadata[client_id]["subscribed_cameras"]
                if camera_id in subscribed:
                    subscribed.remove(camera_id)
            
            logger.debug(f"Client {client_id} unsubscribed from camera {camera_id}")
            
        except Exception as e:
            logger.error(f"Error unsubscribing from camera: {str(e)}")
    
    async def broadcast_camera_update(self, camera_id: str, update_data: Dict[str, Any]):
        """Broadcast update to all clients subscribed to a camera"""
        if camera_id not in self.camera_subscriptions:
            return
        
        message = json.dumps(update_data, default=str)
        disconnected_clients = []
        
        for client_id in self.camera_subscriptions[camera_id]:
            if client_id in self.active_connections:
                try:
                    websocket = self.active_connections[client_id]
                    await websocket.send_text(message)
                except Exception as e:
                    logger.warning(f"Failed to send camera update to {client_id}: {str(e)}")
                    disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)
    
    async def send_to_client(self, client_id: str, data: Dict[str, Any]):
        """Send data to specific client"""
        if client_id in self.active_connections:
            try:
                websocket = self.active_connections[client_id]
                message = json.dumps(data, default=str)
                await websocket.send_text(message)
                
                # Update last activity
                if client_id in self.connection_metadata:
                    self.connection_metadata[client_id]["last_activity"] = datetime.utcnow()
                
                return True
            except Exception as e:
                logger.error(f"Failed to send to client {client_id}: {str(e)}")
                self.disconnect(client_id)
                return False
        return False
    
    def get_client_info(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get client connection information"""
        return self.connection_metadata.get(client_id)
    
    def get_camera_subscribers(self, camera_id: str) -> List[str]:
        """Get list of clients subscribed to camera"""
        return self.camera_subscriptions.get(camera_id, [])
    
    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket manager statistics"""
        return {
            "active_connections": len(self.active_connections),
            "camera_subscriptions": {
                camera_id: len(clients) 
                for camera_id, clients in self.camera_subscriptions.items()
            },
            "total_subscriptions": sum(len(clients) for clients in self.camera_subscriptions.values()),
            "cameras_with_subscribers": len(self.camera_subscriptions)
        }

# Global camera WebSocket manager
camera_ws_manager = CameraWebSocketManager()

class CameraWebSocketHandler:
    """Handler for camera WebSocket messages"""
    
    def __init__(self, ws_manager: CameraWebSocketManager):
        self.ws_manager = ws_manager
    
    async def handle_connection(self, websocket: WebSocket):
        """Handle new WebSocket connection"""
        client_id = None
        
        try:
            # Connect client
            client_id = await self.ws_manager.connect(websocket)
            
            # Send connection confirmation
            welcome_message = {
                "type": "connection_established",
                "client_id": client_id,
                "timestamp": datetime.utcnow().isoformat(),
                "available_cameras": list(camera_service.cameras.keys()),
                "service_stats": camera_service.get_service_stats()
            }
            await self.ws_manager.send_to_client(client_id, welcome_message)
            
            # Handle messages
            while True:
                try:
                    message = await websocket.receive_text()
                    data = json.loads(message)
                    await self.handle_message(client_id, data)
                    
                except WebSocketDisconnect:
                    logger.info(f"WebSocket client {client_id} disconnected normally")
                    break
                except Exception as e:
                    logger.error(f"Error handling WebSocket message: {str(e)}")
                    # Send error message to client
                    error_msg = {
                        "type": "error",
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    await self.ws_manager.send_to_client(client_id, error_msg)
        
        except Exception as e:
            logger.error(f"WebSocket connection error: {str(e)}")
        finally:
            if client_id:
                self.ws_manager.disconnect(client_id)
    
    async def handle_message(self, client_id: str, message: Dict[str, Any]):
        """Handle incoming WebSocket message"""
        message_type = message.get("type")
        logger.debug(f"Received message from {client_id}: {message_type}")
        
        try:
            if message_type == "ping":
                await self._handle_ping(client_id, message)
            
            elif message_type == "subscribe_camera":
                await self._handle_subscribe_camera(client_id, message)
            
            elif message_type == "unsubscribe_camera":
                await self._handle_unsubscribe_camera(client_id, message)
            
            elif message_type == "get_camera_list":
                await self._handle_get_camera_list(client_id, message)
            
            elif message_type == "get_camera_status":
                await self._handle_get_camera_status(client_id, message)
            
            elif message_type == "get_service_stats":
                await self._handle_get_service_stats(client_id, message)
            
            elif message_type == "add_camera":
                await self._handle_add_camera(client_id, message)
            
            elif message_type == "remove_camera":
                await self._handle_remove_camera(client_id, message)
            
            elif message_type == "start_camera_stream":
                await self._handle_start_camera_stream(client_id, message)
            
            elif message_type == "stop_camera_stream":
                await self._handle_stop_camera_stream(client_id, message)
            
            else:
                await self._handle_unknown_message(client_id, message)
        
        except Exception as e:
            logger.error(f"Error handling message type {message_type}: {str(e)}")
            error_response = {
                "type": "error",
                "error": f"Failed to handle {message_type}: {str(e)}",
                "original_message_type": message_type,
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.ws_manager.send_to_client(client_id, error_response)
    
    async def _handle_ping(self, client_id: str, message: Dict[str, Any]):
        """Handle ping message"""
        pong_response = {
            "type": "pong",
            "timestamp": datetime.utcnow().isoformat(),
            "client_id": client_id
        }
        await self.ws_manager.send_to_client(client_id, pong_response)
    
    async def _handle_subscribe_camera(self, client_id: str, message: Dict[str, Any]):
        """Handle camera subscription request"""
        camera_id = message.get("camera_id")
        
        if not camera_id:
            error_response = {
                "type": "error",
                "error": "camera_id is required for subscription",
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.ws_manager.send_to_client(client_id, error_response)
            return
        
        success = await self.ws_manager.subscribe_to_camera(client_id, camera_id)
        
        response = {
            "type": "subscription_response",
            "camera_id": camera_id,
            "subscribed": success,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if success:
            # Send current camera status
            try:
                camera_status = await camera_service.get_camera_status(camera_id)
                response["camera_status"] = camera_status
            except Exception as e:
                logger.warning(f"Could not get camera status: {str(e)}")
        
        await self.ws_manager.send_to_client(client_id, response)
    
    async def _handle_unsubscribe_camera(self, client_id: str, message: Dict[str, Any]):
        """Handle camera unsubscription request"""
        camera_id = message.get("camera_id")
        
        if not camera_id:
            error_response = {
                "type": "error",
                "error": "camera_id is required for unsubscription",
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.ws_manager.send_to_client(client_id, error_response)
            return
        
        self.ws_manager._unsubscribe_from_camera(client_id, camera_id)
        
        response = {
            "type": "unsubscription_response",
            "camera_id": camera_id,
            "unsubscribed": True,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.ws_manager.send_to_client(client_id, response)
    
    async def _handle_get_camera_list(self, client_id: str, message: Dict[str, Any]):
        """Handle camera list request"""
        cameras = []
        
        for camera_id, camera_config in camera_service.cameras.items():
            camera_info = {
                "camera_id": camera_id,
                "camera_type": camera_config.camera_type,
                "enabled": camera_config.enabled,
                "validation_enabled": camera_config.validation_enabled,
                "connection_url": camera_config.connection_url,
                "subscribers": len(self.ws_manager.get_camera_subscribers(camera_id))
            }
            cameras.append(camera_info)
        
        response = {
            "type": "camera_list",
            "cameras": cameras,
            "total_cameras": len(cameras),
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.ws_manager.send_to_client(client_id, response)
    
    async def _handle_get_camera_status(self, client_id: str, message: Dict[str, Any]):
        """Handle camera status request"""
        camera_id = message.get("camera_id")
        
        try:
            camera_status = await camera_service.get_camera_status(camera_id)
            
            response = {
                "type": "camera_status",
                "camera_status": camera_status,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            response = {
                "type": "error",
                "error": f"Failed to get camera status: {str(e)}",
                "camera_id": camera_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        await self.ws_manager.send_to_client(client_id, response)
    
    async def _handle_get_service_stats(self, client_id: str, message: Dict[str, Any]):
        """Handle service statistics request"""
        try:
            service_stats = camera_service.get_service_stats()
            ws_stats = self.ws_manager.get_stats()
            
            response = {
                "type": "service_stats",
                "service_stats": service_stats,
                "websocket_stats": ws_stats,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            response = {
                "type": "error",
                "error": f"Failed to get service stats: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        await self.ws_manager.send_to_client(client_id, response)
    
    async def _handle_add_camera(self, client_id: str, message: Dict[str, Any]):
        """Handle add camera request"""
        try:
            camera_config_data = message.get("camera_config", {})
            result = await camera_api.add_camera_endpoint(camera_config_data)
            
            response = {
                "type": "add_camera_response",
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            response = {
                "type": "error",
                "error": f"Failed to add camera: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        await self.ws_manager.send_to_client(client_id, response)
    
    async def _handle_remove_camera(self, client_id: str, message: Dict[str, Any]):
        """Handle remove camera request"""
        try:
            camera_id = message.get("camera_id")
            result = await camera_api.remove_camera_endpoint(camera_id)
            
            response = {
                "type": "remove_camera_response",
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            response = {
                "type": "error",
                "error": f"Failed to remove camera: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        await self.ws_manager.send_to_client(client_id, response)
    
    async def _handle_start_camera_stream(self, client_id: str, message: Dict[str, Any]):
        """Handle start camera stream request"""
        camera_id = message.get("camera_id")
        
        # Implementation would start streaming camera frames
        # For now, just confirm subscription
        success = await self.ws_manager.subscribe_to_camera(client_id, camera_id)
        
        response = {
            "type": "stream_started",
            "camera_id": camera_id,
            "streaming": success,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.ws_manager.send_to_client(client_id, response)
    
    async def _handle_stop_camera_stream(self, client_id: str, message: Dict[str, Any]):
        """Handle stop camera stream request"""
        camera_id = message.get("camera_id")
        
        # Stop streaming by unsubscribing
        self.ws_manager._unsubscribe_from_camera(client_id, camera_id)
        
        response = {
            "type": "stream_stopped",
            "camera_id": camera_id,
            "streaming": False,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.ws_manager.send_to_client(client_id, response)
    
    async def _handle_unknown_message(self, client_id: str, message: Dict[str, Any]):
        """Handle unknown message type"""
        response = {
            "type": "error",
            "error": f"Unknown message type: {message.get('type')}",
            "supported_types": [
                "ping", "subscribe_camera", "unsubscribe_camera", 
                "get_camera_list", "get_camera_status", "get_service_stats",
                "add_camera", "remove_camera", "start_camera_stream", "stop_camera_stream"
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.ws_manager.send_to_client(client_id, response)

# Global camera WebSocket handler
camera_ws_handler = CameraWebSocketHandler(camera_ws_manager)

# WebSocket endpoint
@camera_websocket_router.websocket("/ws/camera")
async def camera_websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for camera integration"""
    await camera_ws_handler.handle_connection(websocket)

# Additional WebSocket endpoints for specific camera types
@camera_websocket_router.websocket("/ws/camera/{camera_id}")
async def camera_specific_websocket(websocket: WebSocket, camera_id: str):
    """WebSocket endpoint for specific camera"""
    client_id = None
    
    try:
        # Connect and immediately subscribe to the specific camera
        client_id = await camera_ws_manager.connect(websocket)
        
        # Auto-subscribe to the specified camera
        await camera_ws_manager.subscribe_to_camera(client_id, camera_id)
        
        # Send connection confirmation
        welcome_message = {
            "type": "camera_connection_established",
            "client_id": client_id,
            "camera_id": camera_id,
            "auto_subscribed": True,
            "timestamp": datetime.utcnow().isoformat()
        }
        await camera_ws_manager.send_to_client(client_id, welcome_message)
        
        # Handle messages
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
                await camera_ws_handler.handle_message(client_id, data)
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in camera-specific WebSocket: {str(e)}")
                break
    
    except Exception as e:
        logger.error(f"Camera-specific WebSocket error: {str(e)}")
    finally:
        if client_id:
            camera_ws_manager.disconnect(client_id)

# Function to broadcast frame updates (called by the camera service)
async def broadcast_frame_update(camera_id: str, frame_data: Dict[str, Any], validation_result: Dict[str, Any]):
    """Broadcast frame update to subscribed WebSocket clients"""
    try:
        update_data = {
            "type": "camera_frame_update",
            "camera_id": camera_id,
            "frame_data": frame_data,
            "validation_result": validation_result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await camera_ws_manager.broadcast_camera_update(camera_id, update_data)
        
    except Exception as e:
        logger.error(f"Failed to broadcast frame update: {str(e)}")

# Export router and handlers for use in main application
__all__ = [
    "camera_websocket_router",
    "camera_ws_manager", 
    "camera_ws_handler",
    "broadcast_frame_update"
]