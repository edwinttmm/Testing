# HIL Ground Truth Timing Implementation Plan

## Executive Summary

This document provides a comprehensive implementation plan to fix the HIL (Hardware-in-the-Loop) test system to properly compare LabJack detections against ground truth timing. The current system captures LabJack voltage signals but lacks proper synchronization with the 24 pre-recorded ground truth detections and accurate latency calculation.

## Current State Analysis

### ✅ Working Components
- **LabJack Detection Service**: Captures voltage signals with timestamps
- **Video Timing Service**: Provides high-precision video start timing
- **Database Schema**: Contains all required tables:
  - `ground_truth_objects`: 24 records with timestamps (0.208s, 0.417s, 0.625s, etc.)
  - `detection_events`: LabJack captures with Unix timestamps
  - `detection_comparisons`: Table with `temporal_offset` field (currently unused)
- **Latency Validation Service**: Basic timing tolerance validation exists

### ❌ Missing Components
- **Video-to-Ground Truth Synchronization**: No system to convert LabJack Unix timestamps to video-relative time
- **Ground Truth Matching Algorithm**: No temporal matching of LabJack detections to expected ground truth timings
- **Session Workflow Integration**: Results are based on simple detection counting, not precision/recall
- **Real Latency Calculation**: Shows fixed 5ms instead of actual LabJack time - expected ground truth time

## Implementation Architecture

### Phase 1: Video Timing Synchronization Integration

#### 1.1 Database Schema Updates

```sql
-- Add video timing fields to test_sessions table
ALTER TABLE test_sessions ADD COLUMN video_playback_start_time DOUBLE PRECISION;
ALTER TABLE test_sessions ADD COLUMN video_playback_start_time_ns BIGINT;
ALTER TABLE test_sessions ADD COLUMN ground_truth_sync_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE test_sessions ADD COLUMN ground_truth_tolerance_ms INTEGER DEFAULT 100;

-- Update detection_events table for ground truth correlation
ALTER TABLE detection_events ADD COLUMN video_relative_timestamp DOUBLE PRECISION;
ALTER TABLE detection_events ADD COLUMN expected_ground_truth_timestamp DOUBLE PRECISION;
ALTER TABLE detection_events ADD COLUMN ground_truth_matched BOOLEAN DEFAULT FALSE;
ALTER TABLE detection_events ADD COLUMN actual_latency_ms DOUBLE PRECISION;

-- Enhance detection_comparisons table
ALTER TABLE detection_comparisons ADD COLUMN ground_truth_timestamp DOUBLE PRECISION;
ALTER TABLE detection_comparisons ADD COLUMN labjack_timestamp DOUBLE PRECISION; 
ALTER TABLE detection_comparisons ADD COLUMN video_relative_detection_time DOUBLE PRECISION;
ALTER TABLE detection_comparisons ADD COLUMN is_matched BOOLEAN DEFAULT FALSE;
ALTER TABLE detection_comparisons ADD COLUMN matching_confidence DOUBLE PRECISION;
```

#### 1.2 Enhanced Video Timing Service

```python
# File: services/enhanced_video_timing_service.py

class GroundTruthVideoTimingService:
    """Enhanced video timing service with ground truth synchronization"""
    
    def start_video_with_ground_truth_sync(self, session_id: str, video_id: str) -> Dict[str, Any]:
        """Start video timing with ground truth synchronization"""
        
        # Get ground truth objects for this video
        ground_truth_objects = self._get_ground_truth_objects(video_id)
        
        # Start precision video timing
        video_start_time, video_start_ns = self._start_precision_timing(session_id, video_id)
        
        # Store timing reference in session
        self._store_ground_truth_timing_reference(session_id, {
            'video_start_time': video_start_time,
            'video_start_time_ns': video_start_ns,
            'ground_truth_count': len(ground_truth_objects),
            'expected_detections': [gt.timestamp for gt in ground_truth_objects]
        })
        
        return {
            'video_start_time': video_start_time,
            'video_start_time_ns': video_start_ns,
            'ground_truth_count': len(ground_truth_objects),
            'expected_timestamps': [gt.timestamp for gt in ground_truth_objects]
        }
    
    def convert_labjack_to_video_time(self, session_id: str, labjack_unix_timestamp: float) -> Optional[float]:
        """Convert LabJack Unix timestamp to video-relative time"""
        
        timing_ref = self._get_timing_reference(session_id)
        if not timing_ref:
            return None
            
        video_start_time = timing_ref['video_start_time']
        video_relative_time = labjack_unix_timestamp - video_start_time
        
        return video_relative_time if video_relative_time >= 0 else None
```

### Phase 2: Ground Truth Matching Service

#### 2.1 Temporal Matching Algorithm

```python
# File: services/ground_truth_matching_service.py

@dataclass
class GroundTruthMatch:
    """Represents a match between LabJack detection and ground truth"""
    detection_event_id: str
    ground_truth_id: str
    ground_truth_timestamp: float
    labjack_timestamp: float
    video_relative_detection_time: float
    temporal_offset: float  # Actual latency: labjack_time - expected_time
    is_within_tolerance: bool
    matching_confidence: float
    match_type: str  # 'TP', 'FP', 'FN'

class GroundTruthMatchingService:
    """Service for matching LabJack detections to ground truth timing"""
    
    def __init__(self, default_tolerance_ms: float = 100.0):
        self.default_tolerance_ms = default_tolerance_ms
        
    def match_detections_to_ground_truth(self, 
                                       session_id: str,
                                       detection_events: List[DetectionEvent],
                                       ground_truth_objects: List[GroundTruthObject],
                                       tolerance_ms: Optional[float] = None) -> List[GroundTruthMatch]:
        """
        Match LabJack detection events to ground truth objects using temporal proximity
        
        Algorithm:
        1. Convert all LabJack timestamps to video-relative time
        2. For each ground truth timestamp, find nearest LabJack detection within tolerance
        3. Calculate actual latency (detection_time - expected_time)
        4. Mark matches as TP, unmatched detections as FP, unmatched ground truth as FN
        """
        
        tolerance_seconds = (tolerance_ms or self.default_tolerance_ms) / 1000.0
        matches = []
        matched_detections = set()
        matched_ground_truth = set()
        
        # Convert LabJack timestamps to video-relative time
        video_timing_service = get_video_timing_service()
        detection_times = []
        
        for detection in detection_events:
            video_relative_time = video_timing_service.convert_labjack_to_video_time(
                session_id, detection.labjack_timestamp
            )
            if video_relative_time is not None:
                detection_times.append((detection, video_relative_time))
        
        # Match each ground truth to nearest detection within tolerance
        for gt_obj in ground_truth_objects:
            best_match = None
            best_distance = float('inf')
            
            for detection, video_relative_time in detection_times:
                if detection.id in matched_detections:
                    continue
                    
                time_diff = abs(video_relative_time - gt_obj.timestamp)
                
                if time_diff <= tolerance_seconds and time_diff < best_distance:
                    best_distance = time_diff
                    best_match = (detection, video_relative_time, time_diff)
            
            if best_match:
                detection, video_relative_time, time_diff = best_match
                
                # Calculate actual latency (positive = detection after expected, negative = before)
                actual_latency_ms = (video_relative_time - gt_obj.timestamp) * 1000.0
                
                match = GroundTruthMatch(
                    detection_event_id=detection.id,
                    ground_truth_id=gt_obj.id,
                    ground_truth_timestamp=gt_obj.timestamp,
                    labjack_timestamp=detection.labjack_timestamp,
                    video_relative_detection_time=video_relative_time,
                    temporal_offset=actual_latency_ms,
                    is_within_tolerance=True,
                    matching_confidence=1.0 - (time_diff / tolerance_seconds),
                    match_type='TP'
                )
                
                matches.append(match)
                matched_detections.add(detection.id)
                matched_ground_truth.add(gt_obj.id)
        
        # Mark unmatched detections as False Positives
        for detection, video_relative_time in detection_times:
            if detection.id not in matched_detections:
                match = GroundTruthMatch(
                    detection_event_id=detection.id,
                    ground_truth_id=None,
                    ground_truth_timestamp=None,
                    labjack_timestamp=detection.labjack_timestamp,
                    video_relative_detection_time=video_relative_time,
                    temporal_offset=None,
                    is_within_tolerance=False,
                    matching_confidence=0.0,
                    match_type='FP'
                )
                matches.append(match)
        
        # Create False Negative entries for unmatched ground truth
        for gt_obj in ground_truth_objects:
            if gt_obj.id not in matched_ground_truth:
                match = GroundTruthMatch(
                    detection_event_id=None,
                    ground_truth_id=gt_obj.id,
                    ground_truth_timestamp=gt_obj.timestamp,
                    labjack_timestamp=None,
                    video_relative_detection_time=None,
                    temporal_offset=None,
                    is_within_tolerance=False,
                    matching_confidence=0.0,
                    match_type='FN'
                )
                matches.append(match)
        
        return matches
    
    def calculate_precision_recall_metrics(self, matches: List[GroundTruthMatch]) -> Dict[str, float]:
        """Calculate precision, recall, and F1 score from matches"""
        
        tp_count = len([m for m in matches if m.match_type == 'TP'])
        fp_count = len([m for m in matches if m.match_type == 'FP'])
        fn_count = len([m for m in matches if m.match_type == 'FN'])
        
        precision = tp_count / (tp_count + fp_count) if (tp_count + fp_count) > 0 else 0
        recall = tp_count / (tp_count + fn_count) if (tp_count + fn_count) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        # Calculate average latency for true positives
        tp_matches = [m for m in matches if m.match_type == 'TP' and m.temporal_offset is not None]
        avg_latency_ms = sum(m.temporal_offset for m in tp_matches) / len(tp_matches) if tp_matches else 0
        
        return {
            'true_positives': tp_count,
            'false_positives': fp_count,
            'false_negatives': fn_count,
            'precision': precision,
            'recall': recall,
            'f1_score': f1_score,
            'average_latency_ms': avg_latency_ms,
            'total_ground_truth': tp_count + fn_count,
            'total_detections': tp_count + fp_count
        }
```

### Phase 3: Session Workflow Integration

#### 3.1 Enhanced Session Completion Service

```python
# File: services/enhanced_session_completion_service.py

class GroundTruthSessionCompletionService:
    """Enhanced session completion with ground truth validation"""
    
    async def complete_session_with_ground_truth_analysis(self, session_id: str) -> Dict[str, Any]:
        """Complete session with full ground truth matching and analysis"""
        
        db = SessionLocal()
        try:
            # Get test session and video
            test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
            if not test_session:
                raise ValueError(f"Session {session_id} not found")
            
            # Get LabJack detection events
            detection_events = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session_id
            ).all()
            
            # Get ground truth objects for the video
            ground_truth_objects = db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == test_session.video_id
            ).all()
            
            if not ground_truth_objects:
                raise ValueError(f"No ground truth objects found for video {test_session.video_id}")
            
            # Perform ground truth matching
            matching_service = GroundTruthMatchingService()
            matches = matching_service.match_detections_to_ground_truth(
                session_id=session_id,
                detection_events=detection_events,
                ground_truth_objects=ground_truth_objects,
                tolerance_ms=test_session.tolerance_ms or 100
            )
            
            # Calculate metrics
            metrics = matching_service.calculate_precision_recall_metrics(matches)
            
            # Store matches in detection_comparisons table
            await self._store_ground_truth_matches(session_id, matches, db)
            
            # Update detection events with ground truth correlation
            await self._update_detection_events_with_matches(session_id, matches, db)
            
            # Create TestResult with real metrics
            test_result = TestResult(
                test_session_id=session_id,
                validation_type="ground_truth_timing",
                pass_rate=metrics['precision'],  # Use precision as primary metric
                avg_latency_ms=metrics['average_latency_ms'],
                total_detections=metrics['total_detections'],
                passed_detections=metrics['true_positives'],
                failed_detections=metrics['false_positives'],
                threshold_ms=test_session.tolerance_ms or 100,
                
                # Store legacy metrics for compatibility
                accuracy=metrics['precision'],
                precision=metrics['precision'],
                recall=metrics['recall'],
                f1_score=metrics['f1_score'],
                true_positives=metrics['true_positives'],
                false_positives=metrics['false_positives'],
                false_negatives=metrics['false_negatives'],
                
                statistical_analysis={
                    'ground_truth_matching': {
                        'total_ground_truth_objects': len(ground_truth_objects),
                        'matched_ground_truth': metrics['true_positives'],
                        'missed_ground_truth': metrics['false_negatives'],
                        'extra_detections': metrics['false_positives'],
                        'matching_tolerance_ms': test_session.tolerance_ms or 100,
                        'average_detection_latency_ms': metrics['average_latency_ms']
                    },
                    'latency_distribution': self._calculate_latency_distribution(matches)
                }
            )
            
            db.add(test_result)
            
            # Update session status
            test_session.status = "completed"
            test_session.completed_at = datetime.now(timezone.utc)
            
            db.commit()
            
            return {
                'session_id': session_id,
                'ground_truth_matches': len([m for m in matches if m.match_type == 'TP']),
                'total_ground_truth': len(ground_truth_objects),
                'total_detections': len(detection_events),
                'precision': metrics['precision'],
                'recall': metrics['recall'],
                'f1_score': metrics['f1_score'],
                'average_latency_ms': metrics['average_latency_ms'],
                'matches_summary': {
                    'true_positives': metrics['true_positives'],
                    'false_positives': metrics['false_positives'],
                    'false_negatives': metrics['false_negatives']
                }
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to complete session with ground truth analysis: {e}")
            raise
        finally:
            db.close()
```

### Phase 4: Results API and Frontend Integration

#### 4.1 Enhanced Results Endpoints

```python
# File: routers/enhanced_ground_truth_results.py

@router.get("/api/sessions/{session_id}/ground-truth-results")
async def get_ground_truth_results(session_id: str, db: Session = Depends(get_db)):
    """Get comprehensive ground truth validation results"""
    
    # Get test session
    test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
    if not test_session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get ground truth matches
    matches = db.query(DetectionComparison).filter(
        DetectionComparison.test_session_id == session_id
    ).all()
    
    # Get test results
    test_result = db.query(TestResult).filter(
        TestResult.test_session_id == session_id
    ).first()
    
    # Get ground truth objects
    ground_truth_objects = db.query(GroundTruthObject).filter(
        GroundTruthObject.video_id == test_session.video_id
    ).all()
    
    # Format response
    response = {
        'session_id': session_id,
        'session_info': {
            'name': test_session.name,
            'video_id': test_session.video_id,
            'tolerance_ms': test_session.tolerance_ms,
            'status': test_session.status,
            'started_at': test_session.started_at.isoformat() if test_session.started_at else None,
            'completed_at': test_session.completed_at.isoformat() if test_session.completed_at else None
        },
        'ground_truth_info': {
            'total_objects': len(ground_truth_objects),
            'expected_timestamps': [gt.timestamp for gt in ground_truth_objects],
            'vru_types': list(set(gt.class_label for gt in ground_truth_objects))
        },
        'validation_results': {
            'precision': test_result.precision if test_result else 0,
            'recall': test_result.recall if test_result else 0,
            'f1_score': test_result.f1_score if test_result else 0,
            'average_latency_ms': test_result.avg_latency_ms if test_result else 0,
            'true_positives': test_result.true_positives if test_result else 0,
            'false_positives': test_result.false_positives if test_result else 0,
            'false_negatives': test_result.false_negatives if test_result else 0
        },
        'detection_matches': [
            {
                'detection_event_id': match.detection_event_id,
                'ground_truth_id': match.ground_truth_id,
                'ground_truth_timestamp': match.ground_truth_timestamp,
                'labjack_timestamp': match.labjack_timestamp,
                'video_relative_detection_time': match.video_relative_detection_time,
                'temporal_offset_ms': match.temporal_offset,
                'match_type': match.match_type,
                'is_within_tolerance': match.is_matched,
                'matching_confidence': match.matching_confidence
            }
            for match in matches
        ],
        'summary': {
            'total_ground_truth_objects': len(ground_truth_objects),
            'detected_ground_truth_objects': len([m for m in matches if m.match_type == 'TP']),
            'missed_ground_truth_objects': len([m for m in matches if m.match_type == 'FN']),
            'extra_detections': len([m for m in matches if m.match_type == 'FP']),
            'detection_rate': (len([m for m in matches if m.match_type == 'TP']) / len(ground_truth_objects)) * 100 if ground_truth_objects else 0
        }
    }
    
    return response
```

#### 4.2 Frontend Integration Changes

```typescript
// Frontend interface updates for ground truth results
interface GroundTruthResults {
  sessionId: string;
  sessionInfo: {
    name: string;
    videoId: string;
    toleranceMs: number;
    status: string;
    startedAt?: string;
    completedAt?: string;
  };
  groundTruthInfo: {
    totalObjects: number;
    expectedTimestamps: number[];
    vruTypes: string[];
  };
  validationResults: {
    precision: number;
    recall: number;
    f1Score: number;
    averageLatencyMs: number;
    truePositives: number;
    falsePositives: number;
    falseNegatives: number;
  };
  detectionMatches: DetectionMatch[];
  summary: {
    totalGroundTruthObjects: number;
    detectedGroundTruthObjects: number;
    missedGroundTruthObjects: number;
    extraDetections: number;
    detectionRate: number;
  };
}

interface DetectionMatch {
  detectionEventId?: string;
  groundTruthId?: string;
  groundTruthTimestamp?: number;
  labjackTimestamp?: number;
  videoRelativeDetectionTime?: number;
  temporalOffsetMs?: number;
  matchType: 'TP' | 'FP' | 'FN';
  isWithinTolerance: boolean;
  matchingConfidence: number;
}
```

## Implementation Timeline

### Week 1: Database Schema and Core Services
- [ ] Implement database schema changes
- [ ] Create GroundTruthVideoTimingService
- [ ] Develop GroundTruthMatchingService
- [ ] Write comprehensive unit tests

### Week 2: Session Workflow Integration
- [ ] Enhance SessionCompletionService with ground truth analysis
- [ ] Update TestResult generation with real metrics
- [ ] Integrate matching algorithm into session completion
- [ ] Test end-to-end session workflow

### Week 3: API and Frontend Integration
- [ ] Create enhanced results API endpoints
- [ ] Update frontend components for ground truth results display
- [ ] Implement real-time latency visualization
- [ ] Add debugging tools for ground truth matching

### Week 4: Testing and Documentation
- [ ] Comprehensive integration testing with real HIL hardware
- [ ] Performance optimization and error handling
- [ ] Documentation and user guides
- [ ] Deployment and validation

## Success Metrics

### Technical Metrics
- ✅ All 24 ground truth detections properly matched or identified as missed
- ✅ Real latency calculation showing actual LabJack time - expected time
- ✅ Precision/Recall calculations based on matched detections vs expected
- ✅ Temporal offset calculations with sub-millisecond accuracy
- ✅ Zero phantom detections in results

### Functional Metrics
- ✅ Session completion shows actual ground truth coverage (e.g., "18/24 ground truth detections found")
- ✅ Results display real latency values instead of fixed 5ms
- ✅ Clear visualization of which ground truth detections were missed
- ✅ Accurate pass/fail determination based on actual system performance

## Risk Mitigation

### Technical Risks
1. **Timing Synchronization Accuracy**: Use existing high-precision timing services
2. **Database Performance**: Optimize queries and add appropriate indexes
3. **Legacy Compatibility**: Maintain backward compatibility with existing APIs

### Integration Risks
1. **Frontend Breaking Changes**: Phase deployment with feature flags
2. **Hardware Timing Issues**: Extensive testing with real LabJack hardware
3. **Data Migration**: Careful migration of existing test results

## Dependencies

### Internal Dependencies
- Existing VideoTimingService (✅ Available)
- LabJack Detection Service (✅ Available)
- Precision Timing Service (✅ Available)
- Database Models (✅ Available)

### External Dependencies
- LabJack hardware for testing
- Video files with pre-recorded ground truth
- Database migration tools

## Conclusion

This implementation plan transforms the HIL test system from a simple "capture voltage signals" approach to a comprehensive "compare against ground truth timing" validation system. The plan leverages existing infrastructure while adding the critical missing components for proper temporal matching and real latency calculation.

The phased approach ensures minimal disruption to existing functionality while delivering the precision timing validation required for professional HIL testing systems.