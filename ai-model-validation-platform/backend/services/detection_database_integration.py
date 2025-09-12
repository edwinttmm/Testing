"""
Detection Database Integration Service

This module provides database integration for LabJack detection events,
including proper schema integration and data persistence.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

# Database imports
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean, ForeignKey, text
from sqlalchemy.orm import Session, sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import IntegrityError
import json

# Import existing database configuration
try:
    from database import get_db_session, engine
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    logging.warning("Database module not available, detection events will not be persisted")

# Import detection service models
from services.labjack_detection_service import DetectionEvent as DetectionEventData

logger = logging.getLogger(__name__)

# Database base
Base = declarative_base()


class DetectionEvent(Base):
    """
    Detection Event database model
    
    Stores individual detection events captured from LabJack hardware
    for latency analysis and validation purposes.
    """
    __tablename__ = 'detection_events'
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Event identification
    session_id = Column(String(255), nullable=False, index=True)
    event_id = Column(String(255), nullable=True, index=True)
    
    # Timing information
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Detection data
    channel = Column(String(50), nullable=False)  # AIN0, AIN1, etc.
    voltage = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    
    # Detection status
    detected = Column(Boolean, default=True)
    is_duplicate = Column(Boolean, default=False)
    
    # Metadata
    metadata = Column(String(1000), nullable=True)  # JSON string
    
    # Optional relationships (if validation sessions exist)
    # validation_session_id = Column(Integer, ForeignKey('validation_sessions.id'), nullable=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'event_id': self.event_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'channel': self.channel,
            'voltage': self.voltage,
            'threshold': self.threshold,
            'detected': self.detected,
            'is_duplicate': self.is_duplicate,
            'metadata': json.loads(self.metadata) if self.metadata else None
        }
    
    @classmethod
    def from_detection_data(cls, event_data: DetectionEventData):
        """Create DetectionEvent from DetectionEventData"""
        metadata_json = json.dumps(event_data.metadata) if event_data.metadata else None
        
        return cls(
            session_id=event_data.session_id,
            event_id=event_data.id,
            timestamp=event_data.timestamp,
            channel=event_data.channel,
            voltage=event_data.voltage,
            threshold=event_data.threshold,
            detected=event_data.detected,
            is_duplicate=event_data.is_duplicate,
            metadata=metadata_json
        )
    
    def __repr__(self) -> str:
        return (
            f"<DetectionEvent(id={self.id}, session={self.session_id}, "
            f"channel={self.channel}, voltage={self.voltage:.3f}V, "
            f"timestamp={self.timestamp})>"
        )


class DetectionSession(Base):
    """
    Detection Session model to group related detection events
    """
    __tablename__ = 'detection_sessions'
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    
    # Session metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    
    # Configuration
    channels = Column(String(200), nullable=False)  # JSON array of channel names
    voltage_threshold = Column(Float, nullable=False, default=2.5)
    debounce_ms = Column(Integer, default=100)
    sample_rate = Column(Integer, default=1000)
    
    # Status
    is_active = Column(Boolean, default=False)
    total_events = Column(Integer, default=0)
    
    # Metadata
    metadata = Column(String(1000), nullable=True)  # JSON string
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'channels': json.loads(self.channels) if self.channels else [],
            'voltage_threshold': self.voltage_threshold,
            'debounce_ms': self.debounce_ms,
            'sample_rate': self.sample_rate,
            'is_active': self.is_active,
            'total_events': self.total_events,
            'metadata': json.loads(self.metadata) if self.metadata else None
        }
    
    def __repr__(self) -> str:
        return (
            f"<DetectionSession(id={self.id}, session_id={self.session_id}, "
            f"active={self.is_active}, events={self.total_events})>"
        )


class DetectionDatabaseService:
    """
    Service for managing detection event database operations
    """
    
    def __init__(self):
        self.database_available = DATABASE_AVAILABLE
        if self.database_available:
            self._ensure_tables()
        else:
            logger.warning("Database not available, detection events will not be persisted")
    
    def _ensure_tables(self):
        """Ensure detection tables exist in the database"""
        if not self.database_available:
            return
            
        try:
            # Create tables if they don't exist
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Detection database tables ensured")
        except Exception as e:
            logger.error(f"Failed to create detection tables: {e}")
            self.database_available = False
    
    @asynccontextmanager
    async def get_session(self):
        """Get database session context manager"""
        if not self.database_available:
            yield None
            return
            
        session = None
        try:
            session = get_db_session()
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            if session:
                session.rollback()
            raise
        finally:
            if session:
                session.close()
    
    async def create_session(self, session_id: str, channels: List[str], 
                           voltage_threshold: float, debounce_ms: int, 
                           sample_rate: int, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Create a new detection session record"""
        if not self.database_available:
            logger.info(f"Database not available, session {session_id} not persisted")
            return True
            
        try:
            async with self.get_session() as db:
                if db is None:
                    return False
                    
                # Check if session already exists
                existing = db.query(DetectionSession).filter(
                    DetectionSession.session_id == session_id
                ).first()
                
                if existing:
                    # Update existing session
                    existing.started_at = datetime.utcnow()
                    existing.is_active = True
                    existing.channels = json.dumps(channels)
                    existing.voltage_threshold = voltage_threshold
                    existing.debounce_ms = debounce_ms
                    existing.sample_rate = sample_rate
                    if metadata:
                        existing.metadata = json.dumps(metadata)
                else:
                    # Create new session
                    session = DetectionSession(
                        session_id=session_id,
                        started_at=datetime.utcnow(),
                        channels=json.dumps(channels),
                        voltage_threshold=voltage_threshold,
                        debounce_ms=debounce_ms,
                        sample_rate=sample_rate,
                        is_active=True,
                        metadata=json.dumps(metadata) if metadata else None
                    )
                    db.add(session)
                
                db.commit()
                logger.info(f"💾 Created/updated detection session: {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to create detection session: {e}")
            return False
    
    async def end_session(self, session_id: str) -> bool:
        """Mark a detection session as ended"""
        if not self.database_available:
            return True
            
        try:
            async with self.get_session() as db:
                if db is None:
                    return False
                    
                session = db.query(DetectionSession).filter(
                    DetectionSession.session_id == session_id
                ).first()
                
                if session:
                    session.ended_at = datetime.utcnow()
                    session.is_active = False
                    
                    # Update total events count
                    event_count = db.query(DetectionEvent).filter(
                        DetectionEvent.session_id == session_id
                    ).count()
                    session.total_events = event_count
                    
                    db.commit()
                    logger.info(f"📝 Ended detection session: {session_id} ({event_count} events)")
                    return True
                else:
                    logger.warning(f"Session not found in database: {session_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to end detection session: {e}")
            return False
    
    async def store_detection_event(self, event_data: DetectionEventData) -> bool:
        """Store a detection event in the database"""
        if not self.database_available:
            logger.debug(f"Database not available, event {event_data.id} not persisted")
            return True
            
        try:
            async with self.get_session() as db:
                if db is None:
                    return False
                    
                # Create database event from detection data
                db_event = DetectionEvent.from_detection_data(event_data)
                db.add(db_event)
                db.commit()
                
                logger.debug(f"💾 Stored detection event: {event_data.id}")
                return True
                
        except IntegrityError as e:
            logger.warning(f"Duplicate detection event, skipping: {event_data.id}")
            return True  # Consider duplicates as successful
        except Exception as e:
            logger.error(f"Failed to store detection event: {e}")
            return False
    
    async def get_session_events(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all detection events for a session"""
        if not self.database_available:
            return []
            
        try:
            async with self.get_session() as db:
                if db is None:
                    return []
                    
                query = db.query(DetectionEvent).filter(
                    DetectionEvent.session_id == session_id
                ).order_by(DetectionEvent.timestamp)
                
                if limit:
                    query = query.limit(limit)
                
                events = query.all()
                return [event.to_dict() for event in events]
                
        except Exception as e:
            logger.error(f"Failed to get session events: {e}")
            return []
    
    async def get_session_statistics(self, session_id: str) -> Dict[str, Any]:
        """Get statistics for a detection session"""
        if not self.database_available:
            return {}
            
        try:
            async with self.get_session() as db:
                if db is None:
                    return {}
                    
                # Get session info
                session = db.query(DetectionSession).filter(
                    DetectionSession.session_id == session_id
                ).first()
                
                if not session:
                    return {}
                
                # Get event statistics
                events = db.query(DetectionEvent).filter(
                    DetectionEvent.session_id == session_id
                )
                
                total_events = events.count()
                
                # Channel breakdown
                channel_stats = {}
                for event in events:
                    channel = event.channel
                    if channel not in channel_stats:
                        channel_stats[channel] = {
                            'count': 0,
                            'min_voltage': float('inf'),
                            'max_voltage': float('-inf'),
                            'avg_voltage': 0
                        }
                    
                    stats = channel_stats[channel]
                    stats['count'] += 1
                    stats['min_voltage'] = min(stats['min_voltage'], event.voltage)
                    stats['max_voltage'] = max(stats['max_voltage'], event.voltage)
                    stats['avg_voltage'] += event.voltage
                
                # Calculate averages
                for channel, stats in channel_stats.items():
                    if stats['count'] > 0:
                        stats['avg_voltage'] /= stats['count']
                        if stats['min_voltage'] == float('inf'):
                            stats['min_voltage'] = 0
                        if stats['max_voltage'] == float('-inf'):
                            stats['max_voltage'] = 0
                
                return {
                    'session': session.to_dict(),
                    'total_events': total_events,
                    'channel_statistics': channel_stats
                }
                
        except Exception as e:
            logger.error(f"Failed to get session statistics: {e}")
            return {}
    
    async def cleanup_old_sessions(self, days_old: int = 7) -> int:
        """Clean up old detection sessions and events"""
        if not self.database_available:
            return 0
            
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            async with self.get_session() as db:
                if db is None:
                    return 0
                    
                # Get old sessions
                old_sessions = db.query(DetectionSession).filter(
                    DetectionSession.created_at < cutoff_date
                ).all()
                
                session_ids = [session.session_id for session in old_sessions]
                
                # Delete events for old sessions
                events_deleted = db.query(DetectionEvent).filter(
                    DetectionEvent.session_id.in_(session_ids)
                ).delete(synchronize_session=False)
                
                # Delete old sessions
                sessions_deleted = db.query(DetectionSession).filter(
                    DetectionSession.created_at < cutoff_date
                ).delete(synchronize_session=False)
                
                db.commit()
                
                logger.info(f"🧹 Cleaned up {sessions_deleted} old sessions and {events_deleted} events")
                return sessions_deleted
                
        except Exception as e:
            logger.error(f"Failed to cleanup old sessions: {e}")
            return 0


# Global database service instance
_db_service: Optional[DetectionDatabaseService] = None


def get_detection_db_service() -> DetectionDatabaseService:
    """Get global detection database service instance"""
    global _db_service
    if _db_service is None:
        _db_service = DetectionDatabaseService()
    return _db_service


# Export key classes and functions
__all__ = [
    "DetectionEvent",
    "DetectionSession", 
    "DetectionDatabaseService",
    "get_detection_db_service"
]