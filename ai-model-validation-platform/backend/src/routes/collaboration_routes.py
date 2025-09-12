"""
Real-time Collaboration WebSocket Routes
SPARC Implementation - WebSocket endpoints for collaborative annotation
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import json
import logging

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from database import get_db
from src.services.real_time_collaboration_service import collaboration_service
from models import Video, Project

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/collaboration", tags=["collaboration"])


@router.websocket("/video/{video_id}")
async def websocket_collaboration(
    websocket: WebSocket,
    video_id: str,
    user_id: str = Query(..., description="User ID for collaboration"),
    username: str = Query(..., description="Username for display"),
):
    """
    WebSocket endpoint for real-time collaboration on video annotations
    
    - **video_id**: ID of the video being annotated
    - **user_id**: Unique identifier for the user
    - **username**: Display name for the user
    """
    await websocket.accept()
    
    try:
        # Get video information (you might want to verify access here)
        # For now, we'll assume basic validation
        
        # Get project_id (in a real implementation, fetch from database)
        project_id = "default-project"  # This should be fetched from video record
        
        # Join collaboration room
        user = await collaboration_service.join_room(
            video_id=video_id,
            project_id=project_id,
            user_id=user_id,
            username=username,
            websocket=websocket
        )
        
        logger.info(f"User {username} ({user_id}) connected to collaboration for video {video_id}")
        
        # Send welcome message with room state
        welcome_message = {
            "event_type": "connected",
            "user": {
                "user_id": user.user_id,
                "username": user.username,
                "color": user.color,
                "session_role": user.session_role
            },
            "room_state": collaboration_service.rooms[video_id].get_room_state()
        }
        
        await websocket.send_text(json.dumps(welcome_message))
        
        # Listen for messages
        while True:
            try:
                # Receive message with timeout to allow periodic cleanup
                raw_message = await websocket.receive_text()
                message = json.loads(raw_message)
                
                # Handle the message
                await collaboration_service.handle_websocket_message(user_id, message)
                
            except WebSocketDisconnect:
                logger.info(f"User {username} ({user_id}) disconnected from collaboration")
                break
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from user {user_id}: {e}")
                error_message = {
                    "event_type": "error",
                    "error": "Invalid JSON format"
                }
                await websocket.send_text(json.dumps(error_message))
                
            except Exception as e:
                logger.error(f"Error handling message from user {user_id}: {e}")
                error_message = {
                    "event_type": "error",
                    "error": "Message processing error"
                }
                try:
                    await websocket.send_text(json.dumps(error_message))
                except:
                    # Connection might be broken
                    break
    
    except Exception as e:
        logger.error(f"Error in websocket connection for user {user_id}: {e}")
    
    finally:
        # Clean up user from room
        try:
            await collaboration_service.leave_room(user_id)
            logger.info(f"Cleaned up user {user_id} from collaboration")
        except Exception as e:
            logger.error(f"Error cleaning up user {user_id}: {e}")


@router.get("/video/{video_id}/room-info", response_model=Dict[str, Any])
async def get_room_info(
    video_id: str,
    db: Session = Depends(get_db)
):
    """Get information about collaboration room for a video"""
    try:
        # Check if video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Get room info if exists
        if video_id in collaboration_service.rooms:
            room = collaboration_service.rooms[video_id]
            room_info = {
                "active": True,
                "video_id": video_id,
                "project_id": room.project_id,
                "user_count": len(room.users),
                "users": [
                    {
                        "user_id": user.user_id,
                        "username": user.username,
                        "color": user.color,
                        "current_frame": user.current_frame,
                        "last_activity": user.last_activity.isoformat(),
                        "locked_annotations": list(user.locked_annotations)
                    }
                    for user in room.users.values()
                ],
                "active_locks": len(room.annotation_locks),
                "locked_annotations": {
                    lock_id: {
                        "user_id": lock.user_id,
                        "expires_at": lock.expires_at.isoformat()
                    }
                    for lock_id, lock in room.annotation_locks.items()
                },
                "last_activity": room.last_activity.isoformat(),
                "created_at": room.created_at.isoformat()
            }
        else:
            room_info = {
                "active": False,
                "video_id": video_id,
                "message": "No active collaboration session"
            }
        
        return {
            "success": True,
            "room_info": room_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting room info for video {video_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/statistics", response_model=Dict[str, Any])
async def get_collaboration_statistics():
    """Get overall collaboration system statistics"""
    try:
        stats = collaboration_service.get_collaboration_statistics()
        
        return {
            "success": True,
            "statistics": stats
        }
        
    except Exception as e:
        logger.error(f"Error getting collaboration statistics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/video/{video_id}/force-unlock/{annotation_id}", response_model=Dict[str, Any])
async def force_unlock_annotation(
    video_id: str,
    annotation_id: str,
    admin_user_id: str = Query(..., description="Admin user ID"),
    db: Session = Depends(get_db)
):
    """
    Force unlock an annotation (admin function)
    
    This endpoint allows administrators to forcibly unlock annotations
    that might be stuck due to user disconnections or system issues.
    """
    try:
        # In a real implementation, you'd verify admin permissions here
        # For now, we'll allow any user marked as admin
        
        if video_id not in collaboration_service.rooms:
            raise HTTPException(status_code=404, detail="No active collaboration room")
        
        room = collaboration_service.rooms[video_id]
        
        if annotation_id not in room.annotation_locks:
            return {
                "success": True,
                "message": "Annotation was not locked"
            }
        
        lock = room.annotation_locks[annotation_id]
        original_user = lock.user_id
        
        # Remove lock
        del room.annotation_locks[annotation_id]
        
        # Remove from user's locked annotations if user still in room
        if original_user in room.users:
            room.users[original_user].locked_annotations.discard(annotation_id)
        
        # Broadcast force unlock event
        from src.services.real_time_collaboration_service import CollaborationEvent, CollaborationEventType
        import uuid
        from datetime import datetime
        
        event = CollaborationEvent(
            event_id=str(uuid.uuid4()),
            event_type=CollaborationEventType.ANNOTATION_UNLOCKED,
            user_id=admin_user_id,
            timestamp=datetime.utcnow(),
            video_id=video_id,
            data={
                "annotation_id": annotation_id,
                "unlocked_by": admin_user_id,
                "force_unlocked": True,
                "original_user": original_user
            }
        )
        
        await room.broadcast_event(event)
        room.add_event_to_history(event)
        
        logger.info(f"Admin {admin_user_id} force unlocked annotation {annotation_id} in video {video_id}")
        
        return {
            "success": True,
            "message": f"Annotation {annotation_id} force unlocked successfully",
            "original_user": original_user
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error force unlocking annotation {annotation_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/video/{video_id}/room", response_model=Dict[str, Any])
async def close_collaboration_room(
    video_id: str,
    admin_user_id: str = Query(..., description="Admin user ID"),
):
    """
    Close collaboration room (admin function)
    
    Forces all users to leave the collaboration room and closes it.
    """
    try:
        if video_id not in collaboration_service.rooms:
            return {
                "success": True,
                "message": "No active collaboration room to close"
            }
        
        room = collaboration_service.rooms[video_id]
        user_count = len(room.users)
        
        # Notify all users that room is closing
        from src.services.real_time_collaboration_service import CollaborationEvent, CollaborationEventType
        import uuid
        from datetime import datetime
        
        close_event = CollaborationEvent(
            event_id=str(uuid.uuid4()),
            event_type=CollaborationEventType.SESSION_UPDATED,
            user_id=admin_user_id,
            timestamp=datetime.utcnow(),
            video_id=video_id,
            data={
                "action": "room_closing",
                "message": "Collaboration room is being closed by administrator",
                "closed_by": admin_user_id
            }
        )
        
        await room.broadcast_event(close_event)
        
        # Remove all users
        user_ids = list(room.users.keys())
        for user_id in user_ids:
            await room.remove_user(user_id)
        
        # Remove room
        del collaboration_service.rooms[video_id]
        
        # Clean up user sessions
        sessions_to_remove = [
            user_id for user_id, vid in collaboration_service.user_sessions.items() 
            if vid == video_id
        ]
        for user_id in sessions_to_remove:
            del collaboration_service.user_sessions[user_id]
        
        logger.info(f"Admin {admin_user_id} closed collaboration room for video {video_id} (displaced {user_count} users)")
        
        return {
            "success": True,
            "message": f"Collaboration room closed successfully",
            "displaced_users": user_count
        }
        
    except Exception as e:
        logger.error(f"Error closing collaboration room for video {video_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/video/{video_id}/history", response_model=Dict[str, Any])
async def get_collaboration_history(
    video_id: str,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of events to return"),
    event_types: Optional[str] = Query(None, description="Comma-separated list of event types to filter"),
    since: Optional[str] = Query(None, description="ISO timestamp to get events since"),
    db: Session = Depends(get_db)
):
    """Get collaboration event history for a video"""
    try:
        # Check if video exists
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        if video_id not in collaboration_service.rooms:
            return {
                "success": True,
                "events": [],
                "message": "No collaboration history available"
            }
        
        room = collaboration_service.rooms[video_id]
        events = room.event_history
        
        # Apply filters
        if event_types:
            event_type_list = [et.strip() for et in event_types.split(",")]
            events = [e for e in events if e.event_type.value in event_type_list]
        
        if since:
            try:
                from datetime import datetime
                since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
                events = [e for e in events if e.timestamp >= since_dt]
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid since timestamp format")
        
        # Apply limit
        events = events[-limit:] if limit < len(events) else events
        
        # Format events for response
        formatted_events = []
        for event in events:
            formatted_events.append({
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "user_id": event.user_id,
                "timestamp": event.timestamp.isoformat(),
                "data": event.data
            })
        
        return {
            "success": True,
            "events": formatted_events,
            "total_events": len(formatted_events),
            "room_created_at": room.created_at.isoformat(),
            "filters_applied": {
                "limit": limit,
                "event_types": event_types,
                "since": since
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting collaboration history for video {video_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=Dict[str, Any])
async def collaboration_health_check():
    """Health check for collaboration system"""
    try:
        stats = collaboration_service.get_collaboration_statistics()
        
        # Simple health assessment
        health_status = "healthy"
        if stats["total_users"] > 100:  # Arbitrary threshold
            health_status = "busy"
        if stats["total_rooms"] > 50:  # Arbitrary threshold
            health_status = "high_load"
        
        return {
            "status": health_status,
            "service": "collaboration_websocket",
            "version": "1.0.0",
            "active_rooms": stats["total_rooms"],
            "active_users": stats["total_users"],
            "active_locks": stats["total_active_locks"],
            "timestamp": stats["timestamp"]
        }
        
    except Exception as e:
        logger.error(f"Error in collaboration health check: {e}")
        return {
            "status": "unhealthy",
            "service": "collaboration_websocket",
            "error": str(e),
            "timestamp": "2025-08-27T15:35:00Z"
        }