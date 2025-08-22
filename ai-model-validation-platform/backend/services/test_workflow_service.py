"""
Enhanced Test Workflow Service
Supports sequential video playback, timeline synchronization, and enhanced test execution
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import json
import time
from pathlib import Path

from sqlalchemy.orm import Session
from fastapi import WebSocket, WebSocketDisconnect

from models import TestSession, Video, Project
from schemas import TestSessionCreate, TestSessionResponse

logger = logging.getLogger(__name__)

class PlaybackMode(Enum):
    SEQUENTIAL = "sequential"
    RANDOM = "random"
    LOOP = "loop"
    SINGLE = "single"

class SyncStatus(Enum):
    SYNCHRONIZED = "synchronized"
    DRIFT_DETECTED = "drift_detected"
    DISCONNECTED = "disconnected"
    SYNCHRONIZING = "synchronizing"

@dataclass
class TestConfiguration:
    """Enhanced test configuration for sequential playback"""
    batch_size: int = 1
    concurrent: bool = False
    save_intermediate_results: bool = True
    generate_report: bool = True
    sequential_playback: bool = True
    auto_advance: bool = True
    latency_ms: int = 100
    sync_external_signals: bool = False
    loop_playback: bool = False
    random_order: bool = False
    playback_mode: PlaybackMode = PlaybackMode.SEQUENTIAL
    max_sync_drift_ms: int = 50
    sync_check_interval_ms: int = 1000

@dataclass
class PlaybackState:
    """Current state of sequential video playback"""
    current_video_index: int = 0
    total_videos: int = 0
    current_video_id: Optional[str] = None
    current_time: float = 0.0
    is_playing: bool = False
    is_recording: bool = False
    total_progress: float = 0.0
    played_videos: List[str] = None
    video_progress: Dict[str, float] = None
    last_sync_time: Optional[datetime] = None
    sync_status: SyncStatus = SyncStatus.DISCONNECTED
    
    def __post_init__(self):
        if self.played_videos is None:
            self.played_videos = []
        if self.video_progress is None:
            self.video_progress = {}

@dataclass
class ConnectionStatus:
    """Connection health monitoring"""
    api_connected: bool = False
    websocket_connected: bool = False
    latency_ms: int = 0
    last_check: Optional[datetime] = None
    error_count: int = 0
    reconnect_attempts: int = 0

class TestWorkflowService:
    """Enhanced test workflow service with sequential playback and sync capabilities"""
    
    def __init__(self):
        self.active_sessions: Dict[str, Dict] = {}
        self.websocket_connections: Dict[str, WebSocket] = {}
        self.sync_tasks: Dict[str, asyncio.Task] = {}
        
    async def create_test_session(
        self, 
        db: Session, 
        session_data: TestSessionCreate,
        config: TestConfiguration
    ) -> TestSessionResponse:
        """Create a new test session with enhanced configuration"""
        try:
            # Create base test session
            test_session = TestSession(
                name=session_data.name,
                description=session_data.description,
                project_id=session_data.project_id,
                status="pending",
                created_at=datetime.utcnow(),
                configuration=asdict(config)
            )
            
            db.add(test_session)
            db.commit()
            db.refresh(test_session)
            
            # Initialize playback state
            videos = db.query(Video).filter(
                Video.id.in_(session_data.video_ids if hasattr(session_data, 'video_ids') else [])
            ).all()
            
            playback_state = PlaybackState(
                total_videos=len(videos),
                current_video_id=videos[0].id if videos else None
            )
            
            # Store session state
            self.active_sessions[test_session.id] = {
                'session': test_session,
                'config': config,
                'playback_state': playback_state,
                'videos': videos,
                'connection_status': ConnectionStatus(),
                'start_time': datetime.utcnow()
            }
            
            logger.info(f"Created test session {test_session.id} with {len(videos)} videos")
            
            return TestSessionResponse(
                id=test_session.id,
                name=test_session.name,
                description=test_session.description,
                project_id=test_session.project_id,
                status=test_session.status,
                created_at=test_session.created_at,
                configuration=test_session.configuration
            )
            
        except Exception as e:
            logger.error(f"Failed to create test session: {e}")
            db.rollback()
            raise
    
    async def start_sequential_playback(
        self, 
        session_id: str, 
        websocket: Optional[WebSocket] = None
    ) -> bool:
        """Start sequential video playback for a test session"""
        if session_id not in self.active_sessions:
            logger.error(f"Session {session_id} not found")
            return False
        
        session_data = self.active_sessions[session_id]
        config = session_data['config']
        playback_state = session_data['playback_state']
        videos = session_data['videos']
        
        try:
            # Setup playback order
            if config.random_order:
                import random
                video_indices = list(range(len(videos)))
                random.shuffle(video_indices)
                session_data['playback_order'] = video_indices
            else:
                session_data['playback_order'] = list(range(len(videos)))
            
            # Start with first video
            playback_state.current_video_index = 0
            playback_state.current_video_id = videos[session_data['playback_order'][0]].id
            playback_state.is_playing = True
            playback_state.sync_status = SyncStatus.SYNCHRONIZING if config.sync_external_signals else SyncStatus.DISCONNECTED
            
            # Register websocket
            if websocket:
                self.websocket_connections[session_id] = websocket
            
            # Start sync monitoring if enabled
            if config.sync_external_signals:
                self.sync_tasks[session_id] = asyncio.create_task(
                    self._monitor_sync(session_id)
                )
            
            # Notify clients
            await self._broadcast_state_update(session_id)
            
            logger.info(f"Started sequential playback for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start playback for session {session_id}: {e}")
            return False
    
    async def advance_to_next_video(self, session_id: str) -> bool:
        """Advance to the next video in sequence"""
        if session_id not in self.active_sessions:
            return False
        
        session_data = self.active_sessions[session_id]
        config = session_data['config']
        playback_state = session_data['playback_state']
        videos = session_data['videos']
        playback_order = session_data.get('playback_order', list(range(len(videos))))
        
        try:
            current_index = playback_state.current_video_index
            next_index = current_index + 1
            
            # Mark current video as played
            if playback_state.current_video_id:
                playback_state.played_videos.append(playback_state.current_video_id)
            
            if next_index < len(playback_order):
                # Move to next video
                actual_video_index = playback_order[next_index]
                playback_state.current_video_index = next_index
                playback_state.current_video_id = videos[actual_video_index].id
                playback_state.current_time = 0.0
                playback_state.total_progress = (next_index / len(videos)) * 100
                
                # Apply latency delay if configured
                if config.latency_ms > 0:
                    await asyncio.sleep(config.latency_ms / 1000)
                
            elif config.loop_playback:
                # Loop back to first video
                actual_video_index = playback_order[0]
                playback_state.current_video_index = 0
                playback_state.current_video_id = videos[actual_video_index].id
                playback_state.current_time = 0.0
                playback_state.total_progress = 0.0
                playback_state.played_videos = []
                
            else:
                # End of sequence
                playback_state.is_playing = False
                playback_state.total_progress = 100.0
                await self._handle_playback_complete(session_id)
            
            await self._broadcast_state_update(session_id)
            return True
            
        except Exception as e:
            logger.error(f"Failed to advance video for session {session_id}: {e}")
            return False
    
    async def update_video_time(
        self, 
        session_id: str, 
        current_time: float, 
        frame_number: int
    ) -> bool:
        """Update current video playback time"""
        if session_id not in self.active_sessions:
            return False
        
        session_data = self.active_sessions[session_id]
        playback_state = session_data['playback_state']
        
        try:
            playback_state.current_time = current_time
            
            # Update video progress
            if playback_state.current_video_id:
                playback_state.video_progress[playback_state.current_video_id] = current_time
            
            # Check for sync drift if external sync is enabled
            config = session_data['config']
            if config.sync_external_signals:
                await self._check_sync_drift(session_id, current_time)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update video time for session {session_id}: {e}")
            return False
    
    async def handle_video_end(self, session_id: str) -> bool:
        """Handle when a video reaches its end"""
        if session_id not in self.active_sessions:
            return False
        
        session_data = self.active_sessions[session_id]
        config = session_data['config']
        
        try:
            if config.auto_advance:
                return await self.advance_to_next_video(session_id)
            else:
                # Wait for manual advance
                playback_state = session_data['playback_state']
                playback_state.is_playing = False
                await self._broadcast_state_update(session_id)
                return True
            
        except Exception as e:
            logger.error(f"Failed to handle video end for session {session_id}: {e}")
            return False
    
    async def sync_external_timeline(self, session_id: str, external_time: float) -> bool:
        """Synchronize with external timeline signal"""
        if session_id not in self.active_sessions:
            return False
        
        session_data = self.active_sessions[session_id]
        playback_state = session_data['playback_state']
        config = session_data['config']
        
        if not config.sync_external_signals:
            return False
        
        try:
            # Calculate drift
            drift_ms = abs(external_time - playback_state.current_time) * 1000
            
            if drift_ms > config.max_sync_drift_ms:
                # Apply sync correction
                playback_state.current_time = external_time
                playback_state.last_sync_time = datetime.utcnow()
                playback_state.sync_status = SyncStatus.SYNCHRONIZED
                
                # Notify clients of sync correction
                await self._broadcast_sync_update(session_id, external_time, drift_ms)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync external timeline for session {session_id}: {e}")
            return False
    
    async def check_connection_health(self, session_id: str) -> ConnectionStatus:
        """Check the health of API and WebSocket connections"""
        if session_id not in self.active_sessions:
            return ConnectionStatus()
        
        session_data = self.active_sessions[session_id]
        connection_status = session_data['connection_status']
        
        try:
            start_time = time.time()
            
            # Check WebSocket connection
            websocket = self.websocket_connections.get(session_id)
            if websocket and not websocket.client_state.DISCONNECTED:
                connection_status.websocket_connected = True
            else:
                connection_status.websocket_connected = False
            
            # Calculate latency (simplified)
            connection_status.latency_ms = int((time.time() - start_time) * 1000)
            connection_status.last_check = datetime.utcnow()
            connection_status.api_connected = True
            
            return connection_status
            
        except Exception as e:
            logger.error(f"Connection health check failed for session {session_id}: {e}")
            connection_status.api_connected = False
            connection_status.error_count += 1
            return connection_status
    
    async def get_session_state(self, session_id: str) -> Optional[Dict]:
        """Get current session state"""
        if session_id not in self.active_sessions:
            return None
        
        session_data = self.active_sessions[session_id]
        playback_state = session_data['playback_state']
        config = session_data['config']
        connection_status = session_data['connection_status']
        
        return {
            'session_id': session_id,
            'playback_state': asdict(playback_state),
            'configuration': asdict(config),
            'connection_status': asdict(connection_status),
            'total_videos': len(session_data['videos']),
            'current_video': {
                'id': playback_state.current_video_id,
                'index': playback_state.current_video_index,
                'filename': next(
                    (v.filename for v in session_data['videos'] 
                     if v.id == playback_state.current_video_id), 
                    None
                )
            } if playback_state.current_video_id else None
        }
    
    async def stop_session(self, session_id: str) -> bool:
        """Stop a test session and cleanup resources"""
        if session_id not in self.active_sessions:
            return False
        
        try:
            # Stop sync monitoring
            if session_id in self.sync_tasks:
                self.sync_tasks[session_id].cancel()
                del self.sync_tasks[session_id]
            
            # Close WebSocket
            if session_id in self.websocket_connections:
                websocket = self.websocket_connections[session_id]
                try:
                    await websocket.close()
                except:
                    pass
                del self.websocket_connections[session_id]
            
            # Update session status
            session_data = self.active_sessions[session_id]
            playback_state = session_data['playback_state']
            playback_state.is_playing = False
            
            logger.info(f"Stopped test session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop session {session_id}: {e}")
            return False
    
    # Private helper methods
    async def _monitor_sync(self, session_id: str):
        """Monitor external sync signals"""
        session_data = self.active_sessions[session_id]
        config = session_data['config']
        
        while session_id in self.active_sessions:
            try:
                await asyncio.sleep(config.sync_check_interval_ms / 1000)
                
                # Check for sync drift
                playback_state = session_data['playback_state']
                if playback_state.last_sync_time:
                    time_since_sync = datetime.utcnow() - playback_state.last_sync_time
                    if time_since_sync > timedelta(seconds=5):
                        playback_state.sync_status = SyncStatus.DRIFT_DETECTED
                        await self._broadcast_state_update(session_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sync monitoring error for session {session_id}: {e}")
    
    async def _check_sync_drift(self, session_id: str, current_time: float):
        """Check for timeline synchronization drift"""
        session_data = self.active_sessions[session_id]
        playback_state = session_data['playback_state']
        config = session_data['config']
        
        # Simplified drift detection logic
        # In a real implementation, this would compare with external timing signals
        pass
    
    async def _broadcast_state_update(self, session_id: str):
        """Broadcast state update to connected clients"""
        websocket = self.websocket_connections.get(session_id)
        if not websocket:
            return
        
        try:
            state = await self.get_session_state(session_id)
            if state:
                await websocket.send_text(json.dumps({
                    'type': 'state_update',
                    'data': state
                }))
        except Exception as e:
            logger.error(f"Failed to broadcast state update for session {session_id}: {e}")
    
    async def _broadcast_sync_update(self, session_id: str, sync_time: float, drift_ms: float):
        """Broadcast sync correction to connected clients"""
        websocket = self.websocket_connections.get(session_id)
        if not websocket:
            return
        
        try:
            await websocket.send_text(json.dumps({
                'type': 'sync_update',
                'data': {
                    'session_id': session_id,
                    'sync_time': sync_time,
                    'drift_ms': drift_ms,
                    'timestamp': datetime.utcnow().isoformat()
                }
            }))
        except Exception as e:
            logger.error(f"Failed to broadcast sync update for session {session_id}: {e}")
    
    async def _handle_playback_complete(self, session_id: str):
        """Handle completion of sequential playback"""
        websocket = self.websocket_connections.get(session_id)
        if websocket:
            try:
                await websocket.send_text(json.dumps({
                    'type': 'playback_complete',
                    'data': {
                        'session_id': session_id,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                }))
            except Exception as e:
                logger.error(f"Failed to broadcast playback complete for session {session_id}: {e}")

# Global service instance
test_workflow_service = TestWorkflowService()