"""
Temporal Synchronization Service

This service handles the core logic for temporal synchronization analysis
between LabJack hardware detections and video playback detections.

Features:
- Temporal correlation algorithms
- Configurable detection windows
- Statistical analysis of synchronization
- Performance optimization
- Quality assurance and validation
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, text
import uuid
import time
from dataclasses import dataclass
from scipy import stats
from scipy.signal import correlate, find_peaks
import statistics

from src.models.labjack_models import (
    LabJackDetection, VideoDetection, DetectionSynchronization,
    DetectionConfiguration, TemporalAnalysisResult,
    DetectionStatusEnum, SynchronizationStatusEnum
)

logger = logging.getLogger(__name__)


@dataclass
class DetectionPair:
    """Data structure for detection pairs"""
    labjack_detection: LabJackDetection
    video_detection: Optional[VideoDetection] = None
    time_difference_ms: Optional[float] = None
    correlation_score: Optional[float] = None
    is_match: bool = False


@dataclass
class AnalysisConfig:
    """Configuration for temporal analysis"""
    labjack_window_ms: int = 100
    video_window_ms: int = 100
    synchronization_tolerance_ms: int = 50
    confidence_threshold: float = 0.7
    correlation_method: str = "pearson"
    max_drift_rate: float = 0.1
    outlier_detection: bool = True
    parallel_processing: bool = True


class TemporalSynchronizationService:
    """
    Service for temporal synchronization analysis between hardware and video detections
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.logger = logger
    
    async def analyze_session_synchronization(
        self,
        analysis_id: str,
        session_id: str,
        config_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        force_reanalysis: bool = False,
        analysis_parameters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive temporal synchronization analysis for a session
        """
        start_analysis_time = time.time()
        
        try:
            # Load configuration
            config = await self._load_configuration(config_id)
            analysis_config = self._create_analysis_config(config, analysis_parameters)
            
            # Load detection data
            labjack_detections, video_detections = await self._load_detection_data(
                session_id, start_time, end_time
            )
            
            if not labjack_detections:
                self.logger.warning(f"No LabJack detections found for session {session_id}")
                return await self._create_empty_result(analysis_id, session_id, "no_labjack_data")
            
            if not video_detections:
                self.logger.warning(f"No video detections found for session {session_id}")
                return await self._create_empty_result(analysis_id, session_id, "no_video_data")
            
            # Clear existing synchronization data if force reanalysis
            if force_reanalysis:
                await self._clear_existing_synchronizations(session_id, start_time, end_time)
            
            # Perform temporal correlation analysis
            detection_pairs = await self._correlate_detections(
                labjack_detections, video_detections, analysis_config
            )
            
            # Analyze synchronization quality
            sync_metrics = await self._calculate_synchronization_metrics(detection_pairs)
            
            # Detect and handle outliers
            if analysis_config.outlier_detection:
                detection_pairs = await self._filter_outliers(detection_pairs, sync_metrics)
                sync_metrics = await self._calculate_synchronization_metrics(detection_pairs)
            
            # Store synchronization results
            await self._store_synchronization_results(session_id, detection_pairs)
            
            # Calculate drift analysis
            drift_analysis = await self._analyze_timing_drift(detection_pairs)
            
            # Create comprehensive analysis result
            result = await self._create_analysis_result(
                analysis_id=analysis_id,
                session_id=session_id,
                labjack_detections=labjack_detections,
                video_detections=video_detections,
                detection_pairs=detection_pairs,
                sync_metrics=sync_metrics,
                drift_analysis=drift_analysis,
                analysis_config=analysis_config,
                processing_time=time.time() - start_analysis_time,
                start_time=start_time,
                end_time=end_time
            )
            
            self.logger.info(f"Completed temporal analysis {analysis_id} in {result.processing_time_seconds:.2f}s")
            return result.to_dict()
            
        except Exception as e:
            self.logger.error(f"Error in temporal synchronization analysis: {str(e)}")
            raise
    
    async def _load_configuration(self, config_id: str) -> DetectionConfiguration:
        """Load detection configuration"""
        config = self.db.query(DetectionConfiguration)\
                        .filter(DetectionConfiguration.id == config_id)\
                        .first()
        
        if not config:
            raise ValueError(f"Configuration {config_id} not found")
        
        return config
    
    def _create_analysis_config(
        self, 
        config: DetectionConfiguration, 
        parameters: Dict[str, Any] = None
    ) -> AnalysisConfig:
        """Create analysis configuration from database config and parameters"""
        analysis_config = AnalysisConfig(
            labjack_window_ms=config.labjack_window_ms,
            video_window_ms=config.video_window_ms,
            synchronization_tolerance_ms=config.synchronization_tolerance_ms,
            confidence_threshold=config.confidence_threshold,
            correlation_method=config.correlation_method,
            max_drift_rate=config.max_drift_rate,
            outlier_detection=config.outlier_detection,
            parallel_processing=config.parallel_processing
        )
        
        # Override with custom parameters if provided
        if parameters:
            for key, value in parameters.items():
                if hasattr(analysis_config, key):
                    setattr(analysis_config, key, value)
        
        return analysis_config
    
    async def _load_detection_data(
        self,
        session_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Tuple[List[LabJackDetection], List[VideoDetection]]:
        """Load detection data for analysis"""
        
        # Build LabJack query
        labjack_query = self.db.query(LabJackDetection)\
                               .filter(LabJackDetection.session_id == session_id)\
                               .filter(LabJackDetection.is_valid == True)
        
        if start_time:
            labjack_query = labjack_query.filter(LabJackDetection.hardware_timestamp >= start_time)
        if end_time:
            labjack_query = labjack_query.filter(LabJackDetection.hardware_timestamp <= end_time)
        
        labjack_detections = labjack_query.order_by(LabJackDetection.hardware_timestamp).all()
        
        # Build video query
        video_query = self.db.query(VideoDetection)\
                             .filter(VideoDetection.session_id == session_id)\
                             .filter(VideoDetection.is_valid == True)
        
        if start_time:
            video_query = video_query.filter(VideoDetection.playback_timestamp >= start_time)
        if end_time:
            video_query = video_query.filter(VideoDetection.playback_timestamp <= end_time)
        
        video_detections = video_query.order_by(VideoDetection.video_timestamp).all()
        
        self.logger.info(f"Loaded {len(labjack_detections)} LabJack and {len(video_detections)} video detections")
        return labjack_detections, video_detections
    
    async def _clear_existing_synchronizations(
        self,
        session_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ):
        """Clear existing synchronization data for reanalysis"""
        query = self.db.query(DetectionSynchronization)\
                       .filter(DetectionSynchronization.session_id == session_id)
        
        if start_time or end_time:
            # Join with detections to filter by time range
            query = query.join(LabJackDetection)\
                         .filter(LabJackDetection.session_id == session_id)
            
            if start_time:
                query = query.filter(LabJackDetection.hardware_timestamp >= start_time)
            if end_time:
                query = query.filter(LabJackDetection.hardware_timestamp <= end_time)
        
        deleted_count = query.delete(synchronize_session=False)
        self.db.commit()
        
        self.logger.info(f"Cleared {deleted_count} existing synchronization records")
    
    async def _correlate_detections(
        self,
        labjack_detections: List[LabJackDetection],
        video_detections: List[VideoDetection],
        config: AnalysisConfig
    ) -> List[DetectionPair]:
        """
        Correlate LabJack detections with video detections using temporal windows
        """
        detection_pairs = []
        
        # Convert to time-series data for efficient processing
        labjack_times = np.array([det.monotonic_time for det in labjack_detections])
        video_times = np.array([det.playback_timestamp.timestamp() for det in video_detections])
        
        # Use sliding window approach for correlation
        for i, labjack_det in enumerate(labjack_detections):
            labjack_time = labjack_times[i]
            
            # Find video detections within correlation window
            window_start = labjack_time - (config.labjack_window_ms / 1000.0)
            window_end = labjack_time + (config.labjack_window_ms / 1000.0)
            
            # Get candidate video detections
            candidates = []
            for j, video_det in enumerate(video_detections):
                video_time = video_times[j]
                
                if window_start <= video_time <= window_end:
                    time_diff_ms = abs(labjack_time - video_time) * 1000
                    correlation_score = self._calculate_correlation_score(
                        labjack_det, video_det, time_diff_ms, config
                    )
                    candidates.append((video_det, time_diff_ms, correlation_score))
            
            # Select best match based on correlation score and time difference
            best_match = None
            if candidates:
                # Sort by correlation score (descending) then by time difference (ascending)
                candidates.sort(key=lambda x: (-x[2], x[1]))
                best_candidate = candidates[0]
                
                if best_candidate[2] >= config.confidence_threshold:
                    best_match = best_candidate[0]
                    time_diff = best_candidate[1]
                    correlation_score = best_candidate[2]
                else:
                    time_diff = None
                    correlation_score = best_candidate[2]
            
            # Create detection pair
            pair = DetectionPair(
                labjack_detection=labjack_det,
                video_detection=best_match,
                time_difference_ms=time_diff if best_match else None,
                correlation_score=correlation_score if candidates else 0.0,
                is_match=best_match is not None
            )
            
            detection_pairs.append(pair)
        
        matched_count = sum(1 for pair in detection_pairs if pair.is_match)
        self.logger.info(f"Correlated detections: {matched_count}/{len(detection_pairs)} matches")
        
        return detection_pairs
    
    def _calculate_correlation_score(
        self,
        labjack_det: LabJackDetection,
        video_det: VideoDetection,
        time_diff_ms: float,
        config: AnalysisConfig
    ) -> float:
        """
        Calculate correlation score between LabJack and video detections
        """
        # Base score from time proximity (closer = higher score)
        max_time_diff = config.synchronization_tolerance_ms
        time_score = max(0, 1 - (time_diff_ms / max_time_diff))
        
        # Confidence score from detection confidence
        confidence_score = (labjack_det.detection_confidence + video_det.confidence_score) / 2
        
        # Signal quality score
        quality_score = 1.0
        if labjack_det.signal_to_noise_ratio is not None:
            quality_score = min(1.0, labjack_det.signal_to_noise_ratio / 10.0)  # Normalize SNR
        
        # Combined score with weights
        combined_score = (
            0.5 * time_score +
            0.3 * confidence_score +
            0.2 * quality_score
        )
        
        return min(1.0, combined_score)
    
    async def _calculate_synchronization_metrics(
        self, detection_pairs: List[DetectionPair]
    ) -> Dict[str, Any]:
        """Calculate comprehensive synchronization metrics"""
        
        matched_pairs = [pair for pair in detection_pairs if pair.is_match]
        time_differences = [pair.time_difference_ms for pair in matched_pairs]
        correlation_scores = [pair.correlation_score for pair in detection_pairs]
        
        if not time_differences:
            return {
                "total_pairs": len(detection_pairs),
                "matched_pairs": 0,
                "synchronization_accuracy": 0.0,
                "mean_time_difference_ms": 0.0,
                "median_time_difference_ms": 0.0,
                "std_time_difference_ms": 0.0,
                "min_time_difference_ms": 0.0,
                "max_time_difference_ms": 0.0,
                "mean_correlation_score": statistics.mean(correlation_scores) if correlation_scores else 0.0,
                "quality_metrics": {}
            }
        
        # Basic statistics
        mean_time_diff = statistics.mean(time_differences)
        median_time_diff = statistics.median(time_differences)
        std_time_diff = statistics.stdev(time_differences) if len(time_differences) > 1 else 0.0
        min_time_diff = min(time_differences)
        max_time_diff = max(time_differences)
        
        # Quality metrics
        quality_metrics = {
            "precision": len(matched_pairs) / len(detection_pairs) if detection_pairs else 0.0,
            "temporal_consistency": self._calculate_temporal_consistency(time_differences),
            "outlier_ratio": self._calculate_outlier_ratio(time_differences),
            "stability_score": self._calculate_stability_score(time_differences)
        }
        
        return {
            "total_pairs": len(detection_pairs),
            "matched_pairs": len(matched_pairs),
            "synchronization_accuracy": quality_metrics["precision"] * 100,
            "mean_time_difference_ms": mean_time_diff,
            "median_time_difference_ms": median_time_diff,
            "std_time_difference_ms": std_time_diff,
            "min_time_difference_ms": min_time_diff,
            "max_time_difference_ms": max_time_diff,
            "mean_correlation_score": statistics.mean(correlation_scores) if correlation_scores else 0.0,
            "quality_metrics": quality_metrics
        }
    
    def _calculate_temporal_consistency(self, time_differences: List[float]) -> float:
        """Calculate temporal consistency score (lower variance = higher consistency)"""
        if len(time_differences) < 2:
            return 1.0
        
        variance = statistics.variance(time_differences)
        # Normalize variance to 0-1 scale (assuming max acceptable variance is 100ms²)
        consistency = max(0, 1 - (variance / 10000))  # 100ms² = 10000
        return consistency
    
    def _calculate_outlier_ratio(self, time_differences: List[float]) -> float:
        """Calculate ratio of outliers using IQR method"""
        if len(time_differences) < 4:
            return 0.0
        
        q1 = np.percentile(time_differences, 25)
        q3 = np.percentile(time_differences, 75)
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        outliers = [diff for diff in time_differences if diff < lower_bound or diff > upper_bound]
        return len(outliers) / len(time_differences)
    
    def _calculate_stability_score(self, time_differences: List[float]) -> float:
        """Calculate stability score based on coefficient of variation"""
        if not time_differences or len(time_differences) < 2:
            return 1.0
        
        mean_diff = statistics.mean(time_differences)
        std_diff = statistics.stdev(time_differences)
        
        if mean_diff == 0:
            return 1.0 if std_diff == 0 else 0.0
        
        cv = std_diff / abs(mean_diff)  # Coefficient of variation
        # Normalize CV to stability score (lower CV = higher stability)
        stability = max(0, 1 - min(cv, 1.0))
        return stability
    
    async def _filter_outliers(
        self, detection_pairs: List[DetectionPair], sync_metrics: Dict[str, Any]
    ) -> List[DetectionPair]:
        """Filter outlier detection pairs based on statistical analysis"""
        
        matched_pairs = [pair for pair in detection_pairs if pair.is_match]
        if len(matched_pairs) < 4:
            return detection_pairs  # Not enough data for outlier detection
        
        time_differences = [pair.time_difference_ms for pair in matched_pairs]
        
        # Use IQR method for outlier detection
        q1 = np.percentile(time_differences, 25)
        q3 = np.percentile(time_differences, 75)
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        # Filter pairs
        filtered_pairs = []
        outlier_count = 0
        
        for pair in detection_pairs:
            if not pair.is_match:
                filtered_pairs.append(pair)
            elif lower_bound <= pair.time_difference_ms <= upper_bound:
                filtered_pairs.append(pair)
            else:
                # Mark as outlier but keep in results for analysis
                pair.is_match = False
                filtered_pairs.append(pair)
                outlier_count += 1
        
        self.logger.info(f"Filtered {outlier_count} outlier detection pairs")
        return filtered_pairs
    
    async def _analyze_timing_drift(self, detection_pairs: List[DetectionPair]) -> Dict[str, Any]:
        """Analyze timing drift over the session"""
        
        matched_pairs = [pair for pair in detection_pairs if pair.is_match]
        if len(matched_pairs) < 10:  # Need sufficient data for drift analysis
            return {
                "drift_rate_ms_per_second": 0.0,
                "drift_direction": "stable",
                "drift_confidence": 0.0,
                "linear_regression": None
            }
        
        # Extract time series data
        timestamps = [pair.labjack_detection.monotonic_time for pair in matched_pairs]
        time_diffs = [pair.time_difference_ms for pair in matched_pairs]
        
        # Perform linear regression to detect drift
        slope, intercept, r_value, p_value, std_err = stats.linregress(timestamps, time_diffs)
        
        # Determine drift direction
        drift_direction = "stable"
        if abs(slope) > 0.01:  # Threshold for significant drift
            drift_direction = "increasing" if slope > 0 else "decreasing"
        
        return {
            "drift_rate_ms_per_second": slope,
            "drift_direction": drift_direction,
            "drift_confidence": abs(r_value),  # Correlation coefficient as confidence
            "linear_regression": {
                "slope": slope,
                "intercept": intercept,
                "r_squared": r_value ** 2,
                "p_value": p_value,
                "std_error": std_err
            }
        }
    
    async def _store_synchronization_results(
        self, session_id: str, detection_pairs: List[DetectionPair]
    ):
        """Store synchronization results in database"""
        
        sync_records = []
        for pair in detection_pairs:
            if pair.is_match:
                # Determine synchronization status
                sync_status = SynchronizationStatusEnum.SYNCHRONIZED
                if pair.time_difference_ms > 100:  # Beyond typical tolerance
                    sync_status = SynchronizationStatusEnum.OUT_OF_SYNC
                elif pair.time_difference_ms > 50:  # Within extended tolerance
                    sync_status = SynchronizationStatusEnum.WITHIN_TOLERANCE
                
                sync_record = DetectionSynchronization(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    labjack_detection_id=pair.labjack_detection.id,
                    video_detection_id=pair.video_detection.id,
                    time_difference_ms=pair.time_difference_ms,
                    synchronization_status=sync_status,
                    confidence_score=pair.correlation_score,
                    quality_score=min(1.0, pair.correlation_score * 1.2),  # Adjusted quality score
                    is_valid_match=True,
                    analysis_method="temporal_correlation",
                    correlation_algorithm="windowed_proximity"
                )
                
                sync_records.append(sync_record)
                
                # Update detection statuses
                pair.labjack_detection.status = DetectionStatusEnum.MATCHED
                pair.labjack_detection.matched_detection_id = pair.video_detection.id
                pair.video_detection.status = DetectionStatusEnum.MATCHED
                pair.video_detection.matched_labjack_id = pair.labjack_detection.id
            
            else:
                # Update unmatched detection status
                pair.labjack_detection.status = DetectionStatusEnum.UNMATCHED
        
        # Bulk insert synchronization records
        if sync_records:
            self.db.bulk_save_objects(sync_records)
        
        self.db.commit()
        self.logger.info(f"Stored {len(sync_records)} synchronization records")
    
    async def _create_analysis_result(
        self,
        analysis_id: str,
        session_id: str,
        labjack_detections: List[LabJackDetection],
        video_detections: List[VideoDetection],
        detection_pairs: List[DetectionPair],
        sync_metrics: Dict[str, Any],
        drift_analysis: Dict[str, Any],
        analysis_config: AnalysisConfig,
        processing_time: float,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> TemporalAnalysisResult:
        """Create comprehensive analysis result"""
        
        # Calculate time range
        if not start_time and labjack_detections:
            start_time = min(det.hardware_timestamp for det in labjack_detections)
        if not end_time and labjack_detections:
            end_time = max(det.hardware_timestamp for det in labjack_detections)
        
        if not start_time:
            start_time = datetime.now(timezone.utc)
        if not end_time:
            end_time = start_time
        
        duration = (end_time - start_time).total_seconds()
        
        # Create analysis result
        result = TemporalAnalysisResult(
            id=analysis_id,
            session_id=session_id,
            analysis_name=f"Temporal Sync Analysis {datetime.now().strftime('%Y%m%d_%H%M%S')}",
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            total_labjack_detections=len(labjack_detections),
            total_video_detections=len(video_detections),
            matched_detections=sync_metrics["matched_pairs"],
            unmatched_labjack=len(labjack_detections) - sync_metrics["matched_pairs"],
            unmatched_video=len(video_detections) - sync_metrics["matched_pairs"],
            mean_time_difference_ms=sync_metrics["mean_time_difference_ms"],
            median_time_difference_ms=sync_metrics["median_time_difference_ms"],
            std_time_difference_ms=sync_metrics["std_time_difference_ms"],
            min_time_difference_ms=sync_metrics["min_time_difference_ms"],
            max_time_difference_ms=sync_metrics["max_time_difference_ms"],
            synchronization_accuracy=sync_metrics["synchronization_accuracy"],
            mean_confidence_score=sync_metrics["mean_correlation_score"],
            mean_quality_score=sync_metrics["quality_metrics"]["precision"],
            detection_rate_hz=len(labjack_detections) / max(duration, 1),
            processing_time_seconds=processing_time,
            throughput_detections_per_second=len(detection_pairs) / max(processing_time, 0.001),
            timing_drift_ms_per_second=drift_analysis["drift_rate_ms_per_second"],
            stability_score=sync_metrics["quality_metrics"]["stability_score"],
            jitter_ms=sync_metrics["std_time_difference_ms"],
            configuration_used={
                "labjack_window_ms": analysis_config.labjack_window_ms,
                "video_window_ms": analysis_config.video_window_ms,
                "synchronization_tolerance_ms": analysis_config.synchronization_tolerance_ms,
                "confidence_threshold": analysis_config.confidence_threshold,
                "correlation_method": analysis_config.correlation_method
            },
            algorithm_version="1.0",
            analysis_parameters=sync_metrics,
            warnings=[],
            analysis_status="completed",
            is_valid=True,
            requires_review=sync_metrics["synchronization_accuracy"] < 70.0  # Review if < 70% accuracy
        )
        
        # Add warnings if needed
        warnings = []
        if sync_metrics["synchronization_accuracy"] < 50.0:
            warnings.append("Low synchronization accuracy detected")
        if sync_metrics["quality_metrics"]["outlier_ratio"] > 0.2:
            warnings.append("High outlier ratio detected")
        if abs(drift_analysis["drift_rate_ms_per_second"]) > 0.1:
            warnings.append("Significant timing drift detected")
        
        result.warnings = warnings
        
        # Save result to database
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        
        return result
    
    async def _create_empty_result(
        self, analysis_id: str, session_id: str, status: str
    ) -> Dict[str, Any]:
        """Create empty analysis result for cases with no data"""
        
        result = TemporalAnalysisResult(
            id=analysis_id,
            session_id=session_id,
            analysis_name=f"Empty Analysis - {status}",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            duration_seconds=0,
            analysis_status=status,
            is_valid=False,
            requires_review=True
        )
        
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        
        return result.to_dict()