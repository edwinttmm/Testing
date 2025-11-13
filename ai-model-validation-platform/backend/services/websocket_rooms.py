"""
WebSocket Room Management Utilities

Provides utilities for Socket.IO room-based event isolation, ensuring:
- Events are only sent to clients in the same session room
- Privacy: clients don't see other session IDs
- Scalability: bandwidth scales with session rate, not total event rate
- Observability: room member tracking and logging
"""

import logging
from typing import Optional, Dict, Any
import asyncio

logger = logging.getLogger(__name__)

# Global reference to Socket.IO server (set by main.py)
_sio = None


def set_socketio_server(sio):
    """Set the global Socket.IO server instance"""
    global _sio
    _sio = sio
    logger.info("WebSocket room utilities initialized with Socket.IO server")


def notify_session_room(session_id: str, event: str, data: Dict[str, Any]) -> bool:
    """
    Emit event to session room only (not broadcast)

    Args:
        session_id: Test session identifier
        event: Event name
        data: Event payload

    Returns:
        True if emission succeeded, False otherwise
    """
    if not _sio:
        logger.error("Socket.IO server not initialized")
        return False

    try:
        room_name = f"session_{session_id}"

        # Use asyncio to emit if in async context, otherwise schedule
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context - create task
                asyncio.create_task(_sio.emit(event, data, room=room_name))
            else:
                # Not in async context - run until complete
                loop.run_until_complete(_sio.emit(event, data, room=room_name))
        except RuntimeError:
            # No event loop - create new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_sio.emit(event, data, room=room_name))
            loop.close()

        logger.debug(f"Emitted {event} to session room {room_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to emit {event} to session {session_id}: {e}")
        return False


def get_room_members(session_id: str) -> int:
    """
    Get number of clients in session room

    Args:
        session_id: Test session identifier

    Returns:
        Number of clients in room, or 0 if error
    """
    if not _sio:
        logger.error("Socket.IO server not initialized")
        return 0

    try:
        room_name = f"session_{session_id}"

        # Access Socket.IO server manager to get room members
        # Note: This is implementation-specific to python-socketio
        namespace = '/'
        rooms = _sio.manager.rooms.get(namespace, {})
        members = rooms.get(room_name, set())

        return len(members)

    except Exception as e:
        logger.error(f"Failed to get room members for session {session_id}: {e}")
        return 0


def broadcast_to_room(session_id: str, event: str, data: Dict[str, Any]) -> bool:
    """
    Broadcast event to session room with logging

    Args:
        session_id: Test session identifier
        event: Event name
        data: Event payload

    Returns:
        True if broadcast succeeded, False otherwise
    """
    if not _sio:
        logger.error("Socket.IO server not initialized")
        return False

    try:
        member_count = get_room_members(session_id)
        room_name = f"session_{session_id}"

        logger.info(f"Broadcasting {event} to {member_count} clients in room {room_name}")

        # Use asyncio to emit
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(_sio.emit(event, data, room=room_name))
            else:
                loop.run_until_complete(_sio.emit(event, data, room=room_name))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_sio.emit(event, data, room=room_name))
            loop.close()

        return True

    except Exception as e:
        logger.error(f"Failed to broadcast {event} to session {session_id}: {e}")
        return False


def get_all_session_rooms() -> Dict[str, int]:
    """
    Get all session rooms and their member counts

    Returns:
        Dictionary mapping session_id to member count
    """
    if not _sio:
        logger.error("Socket.IO server not initialized")
        return {}

    try:
        namespace = '/'
        rooms = _sio.manager.rooms.get(namespace, {})

        session_rooms = {}
        for room_name, members in rooms.items():
            if room_name.startswith('session_'):
                session_id = room_name.replace('session_', '')
                session_rooms[session_id] = len(members)

        return session_rooms

    except Exception as e:
        logger.error(f"Failed to get session rooms: {e}")
        return {}


# Export key functions
__all__ = [
    'set_socketio_server',
    'notify_session_room',
    'get_room_members',
    'broadcast_to_room',
    'get_all_session_rooms'
]
