"""
Real-time Collaboration Service for Annotations
SPARC Implementation - WebSocket-based collaborative annotation system
"""

import asyncio
import json
import uuid
from typing import Dict, List, Set, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from sqlalchemy.orm import Session
from fastapi import WebSocket
from models import Annotation, AnnotationSession, Video, Project

logger = logging.getLogger(__name__)


class CollaborationEventType(Enum):
    """Types of collaboration events"""
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    ANNOTATION_CREATED = "annotation_created"
    ANNOTATION_UPDATED = "annotation_updated"
    ANNOTATION_DELETED = "annotation_deleted"
    ANNOTATION_LOCKED = "annotation_locked"
    ANNOTATION_UNLOCKED = "annotation_unlocked"
    CURSOR_MOVED = "cursor_moved"
    FRAME_CHANGED = "frame_changed"
    SESSION_UPDATED = "session_updated"
    CONFLICT_DETECTED = "conflict_detected"
    SYNC_REQUEST = "sync_request"
    HEARTBEAT = "heartbeat"


@dataclass
class CollaborationUser:
    """User in collaboration session"""
    user_id: str
    username: str
    color: str
    current_frame: int
    cursor_position: Optional[Dict[str, float]]
    last_activity: datetime
    locked_annotations: Set[str]
    session_role: str = "annotator"  # annotator, reviewer, observer


@dataclass
class CollaborationEvent:
    """Collaboration event data structure"""
    event_id: str
    event_type: CollaborationEventType
    user_id: str
    timestamp: datetime
    video_id: str
    data: Dict[str, Any]
    target_users: Optional[List[str]] = None  # None means broadcast to all


class AnnotationLock:
    """Lock for preventing concurrent annotation editing"""
    
    def __init__(self, annotation_id: str, user_id: str, expires_at: datetime):
        self.annotation_id = annotation_id
        self.user_id = user_id
        self.locked_at = datetime.utcnow()
        self.expires_at = expires_at


class CollaborationRoom:
    """Manages a collaboration session for a video"""
    
    def __init__(self, video_id: str, project_id: str):
        self.video_id = video_id
        self.project_id = project_id
        self.users: Dict[str, CollaborationUser] = {}
        self.connections: Dict[str, WebSocket] = {}
        self.annotation_locks: Dict[str, AnnotationLock] = {}
        self.event_history: List[CollaborationEvent] = []
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        
        # Configuration
        self.max_users = 10
        self.lock_timeout_minutes = 5
        self.history_limit = 1000
        self.heartbeat_interval = 30  # seconds
        
        # User color palette for visual distinction
        self.user_colors = [
            "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FECA57",
            "#FF9FF3", "#54A0FF", "#5F27CD", "#00D2D3", "#FF9F43",
            "#6C5CE7", "#A29BFE", "#FD79A8", "#FDCB6E", "#E17055"
        ]
        self.assigned_colors: Set[str] = set()
    
    def get_available_color(self) -> str:
        """Get next available user color"""
        available_colors = [color for color in self.user_colors if color not in self.assigned_colors]
        if available_colors:
            color = available_colors[0]
            self.assigned_colors.add(color)
            return color
        # If all colors used, cycle through them
        return self.user_colors[len(self.users) % len(self.user_colors)]
    
    def release_color(self, color: str):
        """Release user color when user leaves"""
        self.assigned_colors.discard(color)
    
    async def add_user(self, user_id: str, username: str, websocket: WebSocket) -> CollaborationUser:
        """Add user to collaboration room"""
        if len(self.users) >= self.max_users:
            raise ValueError("Room is full")
        
        color = self.get_available_color()
        
        user = CollaborationUser(
            user_id=user_id,
            username=username,
            color=color,
            current_frame=0,
            cursor_position=None,
            last_activity=datetime.utcnow(),
            locked_annotations=set()
        )
        
        self.users[user_id] = user
        self.connections[user_id] = websocket
        
        # Send user joined event
        event = CollaborationEvent(
            event_id=str(uuid.uuid4()),
            event_type=CollaborationEventType.USER_JOINED,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            video_id=self.video_id,
            data={
                "user": asdict(user),
                "room_users": [asdict(u) for u in self.users.values()]
            }
        )
        
        await self.broadcast_event(event, exclude_user=user_id)
        self.add_event_to_history(event)
        
        logger.info(f"User {username} ({user_id}) joined collaboration room for video {self.video_id}")
        return user
    
    async def remove_user(self, user_id: str):
        """Remove user from collaboration room"""
        if user_id not in self.users:
            return
        
        user = self.users[user_id]
        
        # Release any locked annotations
        await self.release_user_locks(user_id)
        
        # Release color
        self.release_color(user.color)
        
        # Remove user
        del self.users[user_id]
        del self.connections[user_id]
        
        # Send user left event
        event = CollaborationEvent(
            event_id=str(uuid.uuid4()),
            event_type=CollaborationEventType.USER_LEFT,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            video_id=self.video_id,
            data={
                "user_id": user_id,
                "username": user.username,
                "room_users": [asdict(u) for u in self.users.values()]
            }
        )
        
        await self.broadcast_event(event)
        self.add_event_to_history(event)
        
        logger.info(f"User {user.username} ({user_id}) left collaboration room for video {self.video_id}")
    
    async def lock_annotation(self, annotation_id: str, user_id: str) -> bool:
        """Lock annotation for editing"""
        # Check if already locked by another user
        if annotation_id in self.annotation_locks:
            existing_lock = self.annotation_locks[annotation_id]
            if existing_lock.user_id != user_id and existing_lock.expires_at > datetime.utcnow():
                return False
        
        # Create lock
        expires_at = datetime.utcnow() + timedelta(minutes=self.lock_timeout_minutes)
        lock = AnnotationLock(annotation_id, user_id, expires_at)
        self.annotation_locks[annotation_id] = lock
        
        # Add to user's locked annotations
        if user_id in self.users:
            self.users[user_id].locked_annotations.add(annotation_id)
        
        # Broadcast lock event
        event = CollaborationEvent(
            event_id=str(uuid.uuid4()),
            event_type=CollaborationEventType.ANNOTATION_LOCKED,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            video_id=self.video_id,
            data={
                "annotation_id": annotation_id,
                "locked_by": user_id,
                "expires_at": expires_at.isoformat()
            }
        )
        
        await self.broadcast_event(event, exclude_user=user_id)
        self.add_event_to_history(event)
        
        return True
    
    async def unlock_annotation(self, annotation_id: str, user_id: str):
        """Unlock annotation"""
        if annotation_id in self.annotation_locks:
            lock = self.annotation_locks[annotation_id]
            if lock.user_id == user_id:
                del self.annotation_locks[annotation_id]
                
                # Remove from user's locked annotations
                if user_id in self.users:
                    self.users[user_id].locked_annotations.discard(annotation_id)
                
                # Broadcast unlock event
                event = CollaborationEvent(
                    event_id=str(uuid.uuid4()),
                    event_type=CollaborationEventType.ANNOTATION_UNLOCKED,
                    user_id=user_id,
                    timestamp=datetime.utcnow(),
                    video_id=self.video_id,
                    data={
                        "annotation_id": annotation_id,
                        "unlocked_by": user_id
                    }
                )
                
                await self.broadcast_event(event, exclude_user=user_id)
                self.add_event_to_history(event)
    
    async def release_user_locks(self, user_id: str):
        """Release all locks held by a user"""
        user_locks = [lock_id for lock_id, lock in self.annotation_locks.items() 
                     if lock.user_id == user_id]
        
        for lock_id in user_locks:
            await self.unlock_annotation(lock_id, user_id)
    
    def cleanup_expired_locks(self):
        """Remove expired annotation locks"""
        now = datetime.utcnow()
        expired_locks = [lock_id for lock_id, lock in self.annotation_locks.items() 
                        if lock.expires_at <= now]
        
        for lock_id in expired_locks:
            lock = self.annotation_locks[lock_id]
            del self.annotation_locks[lock_id]
            
            # Remove from user's locked annotations
            if lock.user_id in self.users:
                self.users[lock.user_id].locked_annotations.discard(lock_id)
    
    async def handle_annotation_change(self, event_type: CollaborationEventType, 
                                     user_id: str, annotation_data: Dict[str, Any]):
        """Handle annotation changes and broadcast to other users"""
        event = CollaborationEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            video_id=self.video_id,
            data=annotation_data
        )
        
        await self.broadcast_event(event, exclude_user=user_id)
        self.add_event_to_history(event)
    
    async def handle_cursor_movement(self, user_id: str, cursor_position: Dict[str, float]):
        """Handle user cursor movement"""
        if user_id in self.users:
            self.users[user_id].cursor_position = cursor_position
            self.users[user_id].last_activity = datetime.utcnow()
            
            event = CollaborationEvent(
                event_id=str(uuid.uuid4()),
                event_type=CollaborationEventType.CURSOR_MOVED,
                user_id=user_id,
                timestamp=datetime.utcnow(),
                video_id=self.video_id,
                data={
                    "user_id": user_id,
                    "cursor_position": cursor_position
                }
            )
            
            # Don't add cursor movements to history (too frequent)
            await self.broadcast_event(event, exclude_user=user_id)
    
    async def handle_frame_change(self, user_id: str, frame_number: int):
        """Handle user frame navigation"""
        if user_id in self.users:
            self.users[user_id].current_frame = frame_number
            self.users[user_id].last_activity = datetime.utcnow()
            
            event = CollaborationEvent(
                event_id=str(uuid.uuid4()),
                event_type=CollaborationEventType.FRAME_CHANGED,
                user_id=user_id,
                timestamp=datetime.utcnow(),
                video_id=self.video_id,
                data={
                    "user_id": user_id,
                    "frame_number": frame_number
                }
            )
            
            await self.broadcast_event(event, exclude_user=user_id)
    
    async def broadcast_event(self, event: CollaborationEvent, 
                            exclude_user: Optional[str] = None,
                            target_users: Optional[List[str]] = None):
        """Broadcast event to users in room"""
        event_data = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "user_id": event.user_id,
            "timestamp": event.timestamp.isoformat(),
            "video_id": event.video_id,
            "data": event.data
        }
        
        message = json.dumps(event_data)
        
        # Determine target users
        if target_users:
            targets = target_users
        else:
            targets = list(self.connections.keys())
        
        if exclude_user:
            targets = [user_id for user_id in targets if user_id != exclude_user]
        
        # Send to all target users
        disconnected_users = []
        for user_id in targets:
            if user_id in self.connections:
                try:
                    await self.connections[user_id].send_text(message)
                except Exception as e:
                    logger.error(f"Failed to send message to user {user_id}: {e}")
                    disconnected_users.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected_users:
            await self.remove_user(user_id)
    
    def add_event_to_history(self, event: CollaborationEvent):
        """Add event to room history"""
        self.event_history.append(event)
        self.last_activity = datetime.utcnow()
        
        # Limit history size
        if len(self.event_history) > self.history_limit:
            self.event_history = self.event_history[-self.history_limit:]
    
    def get_room_state(self) -> Dict[str, Any]:
        """Get current room state for sync"""
        return {
            "video_id": self.video_id,
            "project_id": self.project_id,
            "users": [asdict(user) for user in self.users.values()],
            "locked_annotations": {
                lock_id: {
                    "user_id": lock.user_id,
                    "expires_at": lock.expires_at.isoformat()
                }
                for lock_id, lock in self.annotation_locks.items()
            },
            "room_created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat()
        }


class RealTimeCollaborationService:
    """Service for managing real-time collaboration"""
    
    def __init__(self):
        self.rooms: Dict[str, CollaborationRoom] = {}
        self.user_sessions: Dict[str, str] = {}  # user_id -> video_id mapping
        
        # Start background tasks
        asyncio.create_task(self.cleanup_task())
    
    def get_or_create_room(self, video_id: str, project_id: str) -> CollaborationRoom:
        """Get existing room or create new one"""
        if video_id not in self.rooms:
            self.rooms[video_id] = CollaborationRoom(video_id, project_id)
            logger.info(f"Created collaboration room for video {video_id}")
        
        return self.rooms[video_id]
    
    async def join_room(self, video_id: str, project_id: str, user_id: str, 
                       username: str, websocket: WebSocket) -> CollaborationUser:
        """Join user to collaboration room"""
        room = self.get_or_create_room(video_id, project_id)
        
        # Remove user from previous room if exists
        if user_id in self.user_sessions:
            previous_video_id = self.user_sessions[user_id]
            if previous_video_id != video_id and previous_video_id in self.rooms:
                await self.rooms[previous_video_id].remove_user(user_id)
        
        # Add to new room
        user = await room.add_user(user_id, username, websocket)
        self.user_sessions[user_id] = video_id
        
        return user
    
    async def leave_room(self, user_id: str):
        """Remove user from current room"""
        if user_id in self.user_sessions:
            video_id = self.user_sessions[user_id]
            if video_id in self.rooms:
                await self.rooms[video_id].remove_user(user_id)
            del self.user_sessions[user_id]
    
    async def handle_websocket_message(self, user_id: str, message: Dict[str, Any]):
        """Handle incoming WebSocket message"""
        if user_id not in self.user_sessions:
            return
        
        video_id = self.user_sessions[user_id]
        if video_id not in self.rooms:
            return
        
        room = self.rooms[video_id]
        event_type = message.get("event_type")
        
        try:
            if event_type == "cursor_moved":
                await room.handle_cursor_movement(user_id, message.get("cursor_position", {}))
            
            elif event_type == "frame_changed":
                await room.handle_frame_change(user_id, message.get("frame_number", 0))
            
            elif event_type == "annotation_created":
                await room.handle_annotation_change(
                    CollaborationEventType.ANNOTATION_CREATED,
                    user_id,
                    message.get("annotation_data", {})
                )
            
            elif event_type == "annotation_updated":
                await room.handle_annotation_change(
                    CollaborationEventType.ANNOTATION_UPDATED,
                    user_id,
                    message.get("annotation_data", {})
                )
            
            elif event_type == "annotation_deleted":
                await room.handle_annotation_change(
                    CollaborationEventType.ANNOTATION_DELETED,
                    user_id,
                    message.get("annotation_data", {})
                )
            
            elif event_type == "lock_annotation":
                annotation_id = message.get("annotation_id")
                if annotation_id:
                    success = await room.lock_annotation(annotation_id, user_id)
                    # Send response back to user
                    response = {
                        "event_type": "lock_response",
                        "annotation_id": annotation_id,
                        "success": success
                    }
                    if user_id in room.connections:
                        await room.connections[user_id].send_text(json.dumps(response))
            
            elif event_type == "unlock_annotation":
                annotation_id = message.get("annotation_id")
                if annotation_id:
                    await room.unlock_annotation(annotation_id, user_id)
            
            elif event_type == "sync_request":
                # Send current room state to user
                state = room.get_room_state()
                response = {
                    "event_type": "sync_response",
                    "room_state": state
                }
                if user_id in room.connections:
                    await room.connections[user_id].send_text(json.dumps(response))
            
            elif event_type == "heartbeat":
                # Update user activity
                if user_id in room.users:
                    room.users[user_id].last_activity = datetime.utcnow()
                
                # Send heartbeat response
                response = {
                    "event_type": "heartbeat_response",
                    "timestamp": datetime.utcnow().isoformat()
                }
                if user_id in room.connections:
                    await room.connections[user_id].send_text(json.dumps(response))
            
        except Exception as e:
            logger.error(f"Error handling WebSocket message from {user_id}: {e}")
    
    async def cleanup_task(self):
        """Background task for cleanup operations"""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                
                # Clean up expired locks
                for room in self.rooms.values():
                    room.cleanup_expired_locks()
                
                # Remove empty rooms
                empty_rooms = [video_id for video_id, room in self.rooms.items() 
                              if not room.users]
                
                for video_id in empty_rooms:
                    logger.info(f"Removing empty collaboration room for video {video_id}")
                    del self.rooms[video_id]
                
                # Clean up stale user sessions
                stale_sessions = []
                for user_id, video_id in self.user_sessions.items():
                    if video_id not in self.rooms or user_id not in self.rooms[video_id].users:
                        stale_sessions.append(user_id)
                
                for user_id in stale_sessions:
                    del self.user_sessions[user_id]
                
            except Exception as e:
                logger.error(f"Error in collaboration cleanup task: {e}")
    
    def get_collaboration_statistics(self) -> Dict[str, Any]:
        """Get collaboration system statistics"""
        total_users = sum(len(room.users) for room in self.rooms.values())
        total_locks = sum(len(room.annotation_locks) for room in self.rooms.values())
        
        room_stats = []
        for video_id, room in self.rooms.items():
            room_stats.append({
                "video_id": video_id,
                "user_count": len(room.users),
                "active_locks": len(room.annotation_locks),
                "last_activity": room.last_activity.isoformat(),
                "created_at": room.created_at.isoformat()
            })
        
        return {
            "total_rooms": len(self.rooms),
            "total_users": total_users,
            "total_active_locks": total_locks,
            "active_sessions": len(self.user_sessions),
            "room_details": room_stats,
            "timestamp": datetime.utcnow().isoformat()
        }


# Global collaboration service instance
collaboration_service = RealTimeCollaborationService()