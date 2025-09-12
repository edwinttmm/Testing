"""
Detection Storage Service

This service provides high-level operations for storing, retrieving, and managing
LabJack and video detections with optimized performance and data integrity.

Features:
- Batch detection storage with validation
- Real-time streaming detection capture
- Detection lifecycle management  
- Performance monitoring and optimization
- Data integrity validation
- Automatic cleanup and maintenance
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Union, AsyncGenerator
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, text, desc, asc
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import uuid
import json
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
import threading
import queue
import time

from src.models.labjack_models import (
    LabJackDetection, VideoDetection, DetectionConfiguration,
    DetectionSourceEnum, DetectionStatusEnum
)
from database import SessionLocal

logger = logging.getLogger(__name__)


@dataclass
class DetectionBatch:
    """Batch detection data structure"""
    session_id: str
    detections: List[Dict[str, Any]]
    source: DetectionSourceEnum
    batch_id: str = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.batch_id is None:
            self.batch_id = str(uuid.uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@dataclass
class StorageMetrics:
    """Storage performance metrics"""
    total_stored: int = 0
    total_failed: int = 0
    avg_storage_time_ms: float = 0.0
    throughput_per_second: float = 0.0
    last_update: datetime = None
    
    def __post_init__(self):
        if self.last_update is None:
            self.last_update = datetime.now(timezone.utc)


class DetectionBuffer:
    """Thread-safe buffer for detection data"""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.buffer = queue.Queue(maxsize=max_size)
        self.lock = threading.Lock()
        self._stats = {
            'total_added': 0,
            'total_flushed': 0,
            'overflow_count': 0
        }
    
    def add_detection(self, detection_data: Dict[str, Any]) -> bool:
        """Add detection to buffer, returns False if buffer is full"""
        try:
            self.buffer.put_nowait(detection_data)
            with self.lock:
                self._stats['total_added'] += 1
            return True
        except queue.Full:
            with self.lock:
                self._stats['overflow_count'] += 1
            return False
    
    def get_batch(self, batch_size: int = 100) -> List[Dict[str, Any]]:
        """Get a batch of detections from buffer"""
        batch = []
        try:
            for _ in range(min(batch_size, self.buffer.qsize())):
                detection = self.buffer.get_nowait()
                batch.append(detection)
        except queue.Empty:
            pass
        
        if batch:
            with self.lock:
                self._stats['total_flushed'] += len(batch)
        
        return batch
    
    def size(self) -> int:
        """Get current buffer size"""
        return self.buffer.qsize()
    
    def stats(self) -> Dict[str, int]:
        """Get buffer statistics"""
        with self.lock:
            return self._stats.copy()


class DetectionStorageService:
    """
    High-performance detection storage service with real-time capabilities
    """
    
    def __init__(self, buffer_size: int = 10000, batch_size: int = 100):
        self.buffer_size = buffer_size
        self.batch_size = batch_size
        self.labjack_buffer = DetectionBuffer(buffer_size)
        self.video_buffer = DetectionBuffer(buffer_size)
        self.metrics = StorageMetrics()
        self.logger = logger
        self._running = False
        self._storage_task = None
        
        # Configuration cache
        self._config_cache = {}
        self._config_cache_expiry = {}
    
    async def start_background_storage(self):
        """Start background storage processing"""
        if self._running:
            return
        
        self._running = True
        self._storage_task = asyncio.create_task(self._background_storage_loop())
        self.logger.info("Started background detection storage service")
    
    async def stop_background_storage(self):
        """Stop background storage processing"""
        if not self._running:
            return
        
        self._running = False
        if self._storage_task:
            await self._storage_task
        
        # Flush remaining buffers
        await self._flush_all_buffers()
        self.logger.info("Stopped background detection storage service")
    
    async def store_labjack_detection(
        self,
        session_id: str,
        device_id: str,
        hardware_timestamp: datetime,
        signal_value: float,
        threshold_value: float,
        channel: int,
        system_timestamp: Optional[datetime] = None,
        monotonic_time: Optional[float] = None,
        detection_confidence: float = 1.0,
        device_config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        use_buffer: bool = True
    ) -> str:
        """Store a single LabJack detection"""
        
        if system_timestamp is None:
            system_timestamp = datetime.now(timezone.utc)
        
        if monotonic_time is None:
            monotonic_time = time.monotonic()
        
        detection_data = {
            'id': str(uuid.uuid4()),
            'session_id': session_id,
            'device_id': device_id,
            'hardware_timestamp': hardware_timestamp,
            'system_timestamp': system_timestamp,
            'monotonic_time': monotonic_time,
            'signal_value': signal_value,
            'threshold_value': threshold_value,
            'channel': channel,
            'detection_confidence': detection_confidence,
            'device_config': device_config,
            'metadata': metadata or {},
            'source': DetectionSourceEnum.LABJACK_HARDWARE,
            'status': DetectionStatusEnum.PENDING
        }
        
        if use_buffer:
            if not self.labjack_buffer.add_detection(detection_data):
                # Buffer full, store immediately
                await self._store_detection_immediate(detection_data, 'labjack')
        else:
            await self._store_detection_immediate(detection_data, 'labjack')
        
        return detection_data['id']
    
    async def store_video_detection(
        self,
        session_id: str,
        video_id: str,
        video_timestamp: float,
        detection_type: str,
        playback_timestamp: Optional[datetime] = None,
        frame_number: Optional[int] = None,
        confidence_score: float = 0.0,
        bounding_box: Optional[Dict[str, Any]] = None,
        playback_speed: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        use_buffer: bool = True
    ) -> str:
        """Store a single video detection"""
        
        if playback_timestamp is None:
            playback_timestamp = datetime.now(timezone.utc)
        
        detection_data = {
            'id': str(uuid.uuid4()),
            'session_id': session_id,
            'video_id': video_id,
            'video_timestamp': video_timestamp,
            'playback_timestamp': playback_timestamp,
            'frame_number': frame_number,
            'detection_type': detection_type,
            'confidence_score': confidence_score,
            'bounding_box': bounding_box,
            'playback_speed': playback_speed,
            'metadata': metadata or {},
            'source': DetectionSourceEnum.VIDEO_PLAYBACK,
            'status': DetectionStatusEnum.PENDING
        }
        
        if use_buffer:
            if not self.video_buffer.add_detection(detection_data):
                # Buffer full, store immediately
                await self._store_detection_immediate(detection_data, 'video')
        else:
            await self._store_detection_immediate(detection_data, 'video')
        
        return detection_data['id']
    
    async def store_detection_batch(
        self, batch: DetectionBatch, validate: bool = True
    ) -> Dict[str, Any]:
        """Store a batch of detections with validation"""
        
        start_time = time.time()
        successful_count = 0
        failed_count = 0
        errors = []
        
        db = SessionLocal()
        try:
            db.begin()
            
            for detection_data in batch.detections:
                try:
                    if validate:
                        validation_result = await self._validate_detection_data(
                            detection_data, batch.source
                        )
                        if not validation_result['valid']:
                            errors.append({
                                'detection_id': detection_data.get('id'),
                                'error': validation_result['errors']
                            })
                            failed_count += 1
                            continue
                    
                    # Create database record
                    if batch.source == DetectionSourceEnum.LABJACK_HARDWARE:
                        db_detection = LabJackDetection(**detection_data)
                    elif batch.source == DetectionSourceEnum.VIDEO_PLAYBACK:
                        db_detection = VideoDetection(**detection_data)
                    else:
                        raise ValueError(f"Unsupported detection source: {batch.source}")
                    
                    db.add(db_detection)
                    successful_count += 1
                    
                except Exception as e:
                    self.logger.error(f"Error storing detection: {str(e)}")
                    errors.append({
                        'detection_id': detection_data.get('id'),
                        'error': str(e)
                    })
                    failed_count += 1
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Batch storage failed: {str(e)}")
            failed_count = len(batch.detections)
            successful_count = 0
            errors.append({'batch_error': str(e)})
            
        finally:
            db.close()
        
        # Update metrics
        storage_time = (time.time() - start_time) * 1000
        self._update_metrics(successful_count, failed_count, storage_time)
        
        return {
            'batch_id': batch.batch_id,
            'successful_count': successful_count,
            'failed_count': failed_count,
            'total_count': len(batch.detections),
            'storage_time_ms': storage_time,
            'errors': errors
        }
    
    async def get_detection_stream(
        self,
        session_id: str,
        source: Optional[DetectionSourceEnum] = None,
        start_time: Optional[datetime] = None,
        buffer_size: int = 1000
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream detections in real-time"""
        
        db = SessionLocal()
        try:
            last_timestamp = start_time or datetime.now(timezone.utc) - timedelta(hours=1)
            
            while True:
                # Query for new detections
                if source == DetectionSourceEnum.LABJACK_HARDWARE or source is None:
                    labjack_query = db.query(LabJackDetection)\
                                     .filter(LabJackDetection.session_id == session_id)\
                                     .filter(LabJackDetection.created_at > last_timestamp)\
                                     .order_by(LabJackDetection.created_at)\
                                     .limit(buffer_size)
                    
                    for detection in labjack_query.all():
                        yield {
                            'type': 'labjack',
                            'data': detection.to_dict()
                        }
                        last_timestamp = max(last_timestamp, detection.created_at)
                
                if source == DetectionSourceEnum.VIDEO_PLAYBACK or source is None:
                    video_query = db.query(VideoDetection)\
                                   .filter(VideoDetection.session_id == session_id)\
                                   .filter(VideoDetection.created_at > last_timestamp)\
                                   .order_by(VideoDetection.created_at)\
                                   .limit(buffer_size)
                    
                    for detection in video_query.all():
                        yield {
                            'type': 'video',
                            'data': detection.to_dict()
                        }
                        last_timestamp = max(last_timestamp, detection.created_at)
                
                # Short pause to avoid excessive polling
                await asyncio.sleep(0.1)
                
        except Exception as e:
            self.logger.error(f"Error in detection stream: {str(e)}")
            raise
        finally:
            db.close()
    
    async def get_detection_statistics(
        self, session_id: str, time_range: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """Get detection statistics for a session"""
        
        db = SessionLocal()
        try:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - (time_range or timedelta(hours=24))
            
            # LabJack statistics
            labjack_stats = db.query(
                func.count(LabJackDetection.id).label('total'),
                func.count(LabJackDetection.id).filter(
                    LabJackDetection.status == DetectionStatusEnum.MATCHED
                ).label('matched'),
                func.avg(LabJackDetection.signal_value).label('avg_signal'),
                func.avg(LabJackDetection.detection_confidence).label('avg_confidence')
            ).filter(
                and_(
                    LabJackDetection.session_id == session_id,
                    LabJackDetection.created_at >= start_time,
                    LabJackDetection.created_at <= end_time
                )
            ).first()
            
            # Video statistics
            video_stats = db.query(
                func.count(VideoDetection.id).label('total'),
                func.count(VideoDetection.id).filter(
                    VideoDetection.status == DetectionStatusEnum.MATCHED
                ).label('matched'),
                func.avg(VideoDetection.confidence_score).label('avg_confidence')
            ).filter(
                and_(
                    VideoDetection.session_id == session_id,
                    VideoDetection.created_at >= start_time,
                    VideoDetection.created_at <= end_time
                )
            ).first()
            
            # Detection rate over time
            detection_rate = db.query(
                func.date_trunc('minute', LabJackDetection.created_at).label('minute'),
                func.count(LabJackDetection.id).label('count')
            ).filter(
                and_(
                    LabJackDetection.session_id == session_id,
                    LabJackDetection.created_at >= start_time,
                    LabJackDetection.created_at <= end_time
                )
            ).group_by('minute').order_by('minute').all()
            
            return {
                'session_id': session_id,
                'time_range': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                },
                'labjack_statistics': {
                    'total_detections': labjack_stats.total or 0,
                    'matched_detections': labjack_stats.matched or 0,
                    'average_signal_value': float(labjack_stats.avg_signal or 0),
                    'average_confidence': float(labjack_stats.avg_confidence or 0),
                    'match_rate': (labjack_stats.matched / max(labjack_stats.total, 1)) * 100
                },
                'video_statistics': {
                    'total_detections': video_stats.total or 0,
                    'matched_detections': video_stats.matched or 0,
                    'average_confidence': float(video_stats.avg_confidence or 0),
                    'match_rate': (video_stats.matched / max(video_stats.total, 1)) * 100
                },
                'detection_rate': [
                    {
                        'timestamp': rate.minute.isoformat(),
                        'detections_per_minute': rate.count
                    }
                    for rate in detection_rate
                ],
                'buffer_statistics': {
                    'labjack_buffer': self.labjack_buffer.stats(),
                    'video_buffer': self.video_buffer.stats()
                },
                'storage_metrics': asdict(self.metrics)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting detection statistics: {str(e)}")
            raise
        finally:
            db.close()
    
    async def cleanup_old_detections(
        self,
        retention_period: timedelta = timedelta(days=30),
        batch_size: int = 1000
    ) -> Dict[str, int]:
        """Clean up old detection data"""
        
        cutoff_time = datetime.now(timezone.utc) - retention_period
        
        db = SessionLocal()
        try:
            # Delete old LabJack detections
            labjack_deleted = 0
            while True:
                labjack_batch = db.query(LabJackDetection)\
                                 .filter(LabJackDetection.created_at < cutoff_time)\
                                 .limit(batch_size).all()
                
                if not labjack_batch:
                    break
                
                for detection in labjack_batch:
                    db.delete(detection)
                
                db.commit()
                labjack_deleted += len(labjack_batch)
                
                # Small delay to avoid overwhelming the database
                await asyncio.sleep(0.01)
            
            # Delete old video detections
            video_deleted = 0
            while True:
                video_batch = db.query(VideoDetection)\
                               .filter(VideoDetection.created_at < cutoff_time)\
                               .limit(batch_size).all()
                
                if not video_batch:
                    break
                
                for detection in video_batch:
                    db.delete(detection)
                
                db.commit()
                video_deleted += len(video_batch)
                
                # Small delay to avoid overwhelming the database
                await asyncio.sleep(0.01)
            
            self.logger.info(f"Cleanup completed: {labjack_deleted} LabJack, {video_deleted} video detections")
            
            return {
                'labjack_detections_deleted': labjack_deleted,
                'video_detections_deleted': video_deleted,
                'total_deleted': labjack_deleted + video_deleted,
                'cutoff_time': cutoff_time.isoformat()
            }
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error during cleanup: {str(e)}")
            raise
        finally:
            db.close()
    
    # Private methods
    
    async def _background_storage_loop(self):
        """Background loop for processing buffered detections"""
        
        while self._running:
            try:
                # Process LabJack buffer
                if self.labjack_buffer.size() >= self.batch_size:
                    labjack_batch = self.labjack_buffer.get_batch(self.batch_size)
                    if labjack_batch:
                        await self._store_batch_immediate(labjack_batch, 'labjack')
                
                # Process video buffer
                if self.video_buffer.size() >= self.batch_size:
                    video_batch = self.video_buffer.get_batch(self.batch_size)
                    if video_batch:
                        await self._store_batch_immediate(video_batch, 'video')
                
                # Periodic flush even if batch size not reached
                await asyncio.sleep(1.0)  # Check every second
                
                # Flush smaller batches if data is waiting
                if self.labjack_buffer.size() > 0:
                    labjack_batch = self.labjack_buffer.get_batch(self.batch_size)
                    if labjack_batch:
                        await self._store_batch_immediate(labjack_batch, 'labjack')
                
                if self.video_buffer.size() > 0:
                    video_batch = self.video_buffer.get_batch(self.batch_size)
                    if video_batch:
                        await self._store_batch_immediate(video_batch, 'video')
                
            except Exception as e:
                self.logger.error(f"Error in background storage loop: {str(e)}")
                await asyncio.sleep(5.0)  # Wait longer on error
    
    async def _store_detection_immediate(
        self, detection_data: Dict[str, Any], detection_type: str
    ):
        """Store a single detection immediately"""
        
        db = SessionLocal()
        try:
            if detection_type == 'labjack':
                db_detection = LabJackDetection(**detection_data)
            elif detection_type == 'video':
                db_detection = VideoDetection(**detection_data)
            else:
                raise ValueError(f"Unknown detection type: {detection_type}")
            
            db.add(db_detection)
            db.commit()
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error storing immediate detection: {str(e)}")
            raise
        finally:
            db.close()
    
    async def _store_batch_immediate(
        self, detections: List[Dict[str, Any]], detection_type: str
    ):
        """Store a batch of detections immediately"""
        
        if not detections:
            return
        
        db = SessionLocal()
        try:
            db_objects = []
            
            for detection_data in detections:
                if detection_type == 'labjack':
                    db_object = LabJackDetection(**detection_data)
                elif detection_type == 'video':
                    db_object = VideoDetection(**detection_data)
                else:
                    continue
                
                db_objects.append(db_object)
            
            db.bulk_save_objects(db_objects)
            db.commit()
            
            self.logger.debug(f"Stored batch of {len(db_objects)} {detection_type} detections")
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error storing batch: {str(e)}")
            raise
        finally:
            db.close()
    
    async def _flush_all_buffers(self):
        """Flush all remaining buffered detections"""
        
        # Flush LabJack buffer
        while self.labjack_buffer.size() > 0:
            batch = self.labjack_buffer.get_batch(self.batch_size)
            if batch:
                await self._store_batch_immediate(batch, 'labjack')
        
        # Flush video buffer
        while self.video_buffer.size() > 0:
            batch = self.video_buffer.get_batch(self.batch_size)
            if batch:
                await self._store_batch_immediate(batch, 'video')
    
    async def _validate_detection_data(
        self, detection_data: Dict[str, Any], source: DetectionSourceEnum
    ) -> Dict[str, Any]:
        """Validate detection data before storage"""
        
        errors = []
        
        # Common validation
        if not detection_data.get('session_id'):
            errors.append("Missing session_id")
        
        if not detection_data.get('id'):
            errors.append("Missing detection id")
        
        # Source-specific validation
        if source == DetectionSourceEnum.LABJACK_HARDWARE:
            required_fields = ['device_id', 'signal_value', 'threshold_value', 'channel']
            for field in required_fields:
                if field not in detection_data:
                    errors.append(f"Missing required field: {field}")
        
        elif source == DetectionSourceEnum.VIDEO_PLAYBACK:
            required_fields = ['video_id', 'video_timestamp', 'detection_type']
            for field in required_fields:
                if field not in detection_data:
                    errors.append(f"Missing required field: {field}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _update_metrics(self, successful: int, failed: int, storage_time_ms: float):
        """Update storage metrics"""
        
        self.metrics.total_stored += successful
        self.metrics.total_failed += failed
        
        # Update running average of storage time
        if self.metrics.total_stored > 0:
            total_ops = self.metrics.total_stored + self.metrics.total_failed
            self.metrics.avg_storage_time_ms = (
                (self.metrics.avg_storage_time_ms * (total_ops - successful - failed) + 
                 storage_time_ms) / total_ops
            )
        
        # Update throughput
        if storage_time_ms > 0:
            self.metrics.throughput_per_second = (successful / storage_time_ms) * 1000
        
        self.metrics.last_update = datetime.now(timezone.utc)


# Global service instance
detection_storage_service = DetectionStorageService()