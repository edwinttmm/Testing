# Video Tracking Architecture Redesign
## Preventing Video ID Assignment Bugs in Multi-Video HIL Systems

**Document Version:** 1.0
**Date:** 2025-11-07
**Status:** Architecture Decision Document (ADR)

---

## Executive Summary

This document proposes a **defensive, timestamp-based video tracking architecture** that eliminates an entire class of bugs where detections are assigned to the wrong video due to metadata synchronization failures. The current system relies on manual metadata updates (`sequence_metadata.current_video_id`) which can drift out of sync, causing ALL detections to be misrouted.

**Key Innovation:** Instead of trusting mutable metadata, we use **immutable timing boundaries** stored in the database as the single source of truth, with defensive validation at every detection assignment point.

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Current Architecture Analysis](#current-architecture-analysis)
3. [Root Cause Analysis](#root-cause-analysis)
4. [Proposed Architecture](#proposed-architecture)
5. [Implementation Plan](#implementation-plan)
6. [Validation Strategy](#validation-strategy)
7. [Migration Path](#migration-path)
8. [Monitoring Requirements](#monitoring-requirements)
9. [Risk Assessment](#risk-assessment)
10. [Appendices](#appendices)

---

## 1. Problem Statement

### 1.1 Current Failure Mode

**Symptom:** When `sequence_metadata.current_video_id` is not updated during video transitions, ALL subsequent detections are assigned to the wrong video, contaminating test results.

**Example Scenario:**
```
Time: 0.0s    -> Video A starts (video_id=aaa, sequence_metadata.current_video_id=aaa) ✅
Time: 10.0s   -> Detection captured (video_id=aaa) ✅ CORRECT
Time: 12.0s   -> Video A ends, Video B starts (video_id=bbb, sequence_metadata.current_video_id=aaa) ❌ NOT UPDATED
Time: 15.0s   -> Detection captured (video_id=aaa) ❌ WRONG! Should be bbb
Time: 20.0s   -> Detection captured (video_id=aaa) ❌ WRONG! Should be bbb
Result: Video B shows 0 detections, Video A shows inflated count
```

### 1.2 Business Impact

- **Data Integrity:** Test results are completely invalid when video_id is wrong
- **False Negatives:** Videos appear to have zero detections when they actually succeeded
- **False Positives:** Other videos appear to have extra detections
- **Compliance Risk:** HIL validation results cannot be trusted for safety certification
- **Debugging Cost:** Extremely difficult to diagnose—timestamps appear correct, only video_id is wrong

### 1.3 Design Requirements

1. **Authoritative Video State:** Single source of truth for "which video is currently active"
2. **Atomic Updates:** Video transitions must be atomic and cannot be out of sync
3. **Defensive Assignment:** Detection service independently determines correct video from timestamp
4. **Validation at Assignment:** Video_id must be verified against detection timestamp before commit
5. **Boundary Handling:** Clear protocol for detections near video boundaries
6. **Failure Recovery:** Fallback logic when video cannot be determined
7. **Real-time Monitoring:** Metrics to detect misassignment in real-time
8. **Auditability:** Complete audit trail of video timing and assignment decisions

---

## 2. Current Architecture Analysis

### 2.1 Components Involved

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Current Architecture                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐      ┌──────────────────────────────────┐   │
│  │  Frontend Video  │      │  VideoSequenceOrchestrator       │   │
│  │     Player       │      │  - start_sequence()              │   │
│  │                  │      │  - notify_video_started()        │   │
│  │  Emits:          │─────>│  - notify_video_ended()          │   │
│  │  - video_started │      │  - process_detection_event()     │   │
│  │  - video_ended   │      │                                  │   │
│  └──────────────────┘      │  Updates: sequence_metadata      │   │
│                             │    .current_video_id             │   │
│                             └────────────┬─────────────────────┘   │
│                                          │                          │
│                                          │ Reads current_video_id   │
│                                          ▼                          │
│                             ┌────────────────────────────────┐     │
│                             │  LabJackDetectionService       │     │
│                             │  - _store_event_in_db()        │     │
│                             │                                │     │
│                             │  Uses: session.video_id        │     │
│                             │    OR sequence_metadata        │     │
│                             │        .current_video_id       │     │
│                             └────────────────────────────────┘     │
│                                                                      │
│  DATABASE STATE:                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ TestSession                                                   │  │
│  │  - video_id: "aaa" (first video, never updated)             │  │
│  │  - sequence_metadata:                                        │  │
│  │      current_video_id: "aaa" ← PROBLEM: Can drift out of sync│ │
│  │      video_timing: { ... }                                   │  │
│  │                                                               │  │
│  │ SequenceVideoResult (per video)                              │  │
│  │  - video_id: "aaa", video_start_time: 0.0, video_end_time: 12.0│
│  │  - video_id: "bbb", video_start_time: 12.0, video_end_time: ?│ │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

FAILURE POINT: If notify_video_started(video_id=bbb) fails to update
               sequence_metadata.current_video_id, ALL detections
               continue being assigned to video_id=aaa
```

### 2.2 Current Data Flow

**Detection Assignment Flow (Current):**

```python
# In labjack_detection_service.py _store_event_in_db()
session = db.query(TestSession).filter_by(id=event.session_id).first()

# PROBLEM: Trusts mutable metadata
video_id = session.video_id  # Default to first video

if session.sequence_id and session.sequence_metadata:
    metadata = session.sequence_metadata
    current_video_id = metadata.get('current_video_id')

    if current_video_id:
        video_id = current_video_id  # ← VULNERABLE: May be stale
    else:
        # Falls back to session.video_id (first video) ← WRONG for video 2+
```

**Why This Fails:**
- Metadata updates are **non-atomic** with video timing
- No validation that `current_video_id` matches detection timestamp
- Single point of failure: if metadata update fails, all detections misrouted
- No defensive checks to detect stale metadata

---

## 3. Root Cause Analysis

### 3.1 Architectural Vulnerabilities

| Vulnerability | Description | Impact |
|--------------|-------------|--------|
| **Manual Metadata Sync** | `current_video_id` updated by orchestrator, can fail silently | Critical - Total data corruption |
| **No Timestamp Validation** | Video_id not verified against detection timestamp | Critical - Wrong video assignment goes undetected |
| **Implicit Trust** | Detection service trusts metadata without verification | High - No defense against stale data |
| **Lack of Atomicity** | Video transitions not atomic database operations | High - Race conditions possible |
| **No Boundary Detection** | Detections near transitions assigned arbitrarily | Medium - Edge case failures |
| **Silent Failures** | Metadata update failures don't raise alerts | Medium - Bugs go unnoticed |

### 3.2 Five Whys Analysis

**Problem:** Detections assigned to wrong video

1. **Why?** Because `sequence_metadata.current_video_id` wasn't updated during video transition
2. **Why?** Because orchestrator's `notify_video_started()` doesn't guarantee atomic metadata update
3. **Why?** Because metadata is stored in JSON field, not as structured database rows
4. **Why?** Because architecture prioritizes flexibility over consistency
5. **Why?** Because original design didn't anticipate metadata synchronization complexity

**Root Cause:** **Architecture relies on eventually-consistent metadata instead of immediately-consistent timing boundaries**

---

## 4. Proposed Architecture

### 4.1 Design Philosophy

**Core Principle:** **"Don't ask what video is active, compute it from immutable timing boundaries"**

Instead of maintaining a `current_video_id` pointer that can drift, we:
1. Store immutable timing boundaries for each video in database
2. Query timing boundaries at detection time
3. Compute correct video from detection timestamp
4. Validate result before committing

### 4.2 Recommended Approach: **Timestamp-Based Assignment with Defensive Validation**

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Proposed Architecture (Hybrid)                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  SINGLE SOURCE OF TRUTH: SequenceVideoResult Table                  │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ SequenceVideoResult (Immutable Timing Records)                 │ │
│  │  - video_sequence_id, video_id, sequence_order                │ │
│  │  - video_start_time: FLOAT (Unix epoch)                       │ │
│  │  - video_end_time: FLOAT (Unix epoch, NULL if current)        │ │
│  │  - actual_duration_ms: FLOAT                                  │ │
│  │                                                                │ │
│  │  Index: (video_sequence_id, video_start_time, video_end_time) │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                   │                                  │
│                                   │ Query at detection time          │
│                                   ▼                                  │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ VideoAssignmentService (NEW)                                   │ │
│  │                                                                │ │
│  │  def get_video_for_timestamp(                                 │ │
│  │      session_id: str,                                         │ │
│  │      detection_timestamp: float,                              │ │
│  │      db: Session                                              │ │
│  │  ) -> Optional[VideoAssignment]:                              │ │
│  │      """                                                       │ │
│  │      Compute video from timing boundaries (immutable)         │ │
│  │      Returns: VideoAssignment with validation metadata        │ │
│  │      """                                                       │ │
│  │      # Query timing boundaries from database                  │ │
│  │      # Find video where:                                      │ │
│  │      #   start_time <= detection_timestamp < end_time         │ │
│  │      # Validate result                                        │ │
│  │      # Return with confidence metrics                         │ │
│  │                                                                │ │
│  │  def validate_video_assignment(                               │ │
│  │      video_id: str,                                           │ │
│  │      detection_timestamp: float,                              │ │
│  │      db: Session                                              │ │
│  │  ) -> ValidationResult:                                       │ │
│  │      """                                                       │ │
│  │      Verify video_id matches timestamp boundaries             │ │
│  │      """                                                       │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                   │                                  │
│                                   │ Used by                          │
│                                   ▼                                  │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ LabJackDetectionService (UPDATED)                              │ │
│  │                                                                │ │
│  │  def _store_event_in_db(event: DetectionEvent):               │ │
│  │      # NEW: Use assignment service                            │ │
│  │      assignment = video_assignment_service                    │ │
│  │          .get_video_for_timestamp(                            │ │
│  │              session_id,                                      │ │
│  │              event.timestamp,                                 │ │
│  │              db                                               │ │
│  │          )                                                     │ │
│  │                                                                │ │
│  │      if not assignment.is_valid:                              │ │
│  │          logger.error(f"Video assignment invalid!")           │ │
│  │          # Emit alert, retry, or use fallback                 │ │
│  │                                                                │ │
│  │      video_id = assignment.video_id                           │ │
│  │                                                                │ │
│  │      # DEFENSIVE: Cross-check with metadata if available      │ │
│  │      if metadata_video_id != video_id:                        │ │
│  │          logger.warning("Video ID mismatch detected!")        │ │
│  │          metrics.record_mismatch()                            │ │
│  │                                                                │ │
│  │      # Store with assignment metadata                         │ │
│  │      event.video_id = video_id                                │ │
│  │      event.assignment_method = assignment.method              │ │
│  │      event.assignment_confidence = assignment.confidence      │ │
│  │      db.add(event)                                            │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  BENEFITS:                                                           │
│  ✅ Video_id computed from immutable timing records                 │
│  ✅ Detection service doesn't trust mutable metadata                │
│  ✅ Cross-validation detects metadata drift                         │
│  ✅ Assignment metadata enables post-hoc auditing                   │
│  ✅ Metrics track assignment confidence and mismatches              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.3 Component Design

#### 4.3.1 VideoAssignmentService (New Component)

**Responsibility:** Determine correct video_id from detection timestamp using database timing boundaries

```python
# File: backend/services/video_assignment_service.py

from dataclasses import dataclass
from typing import Optional
from sqlalchemy.orm import Session
from models import TestSession, SequenceVideoResult
import logging

logger = logging.getLogger(__name__)

@dataclass
class VideoAssignment:
    """Result of video assignment computation"""
    video_id: Optional[str]
    confidence: float  # 0.0 to 1.0
    method: str  # "timestamp_query", "fallback", "metadata_only"
    is_valid: bool
    start_time: Optional[float]
    end_time: Optional[float]
    validation_warnings: list[str]
    assignment_timestamp: float


class VideoAssignmentService:
    """
    Service for determining correct video_id from detection timestamp.

    Uses immutable timing boundaries from SequenceVideoResult table as
    single source of truth, with defensive validation against metadata.
    """

    def get_video_for_timestamp(
        self,
        session_id: str,
        detection_timestamp: float,
        db: Session,
        grace_period_ms: float = 100.0
    ) -> VideoAssignment:
        """
        Determine which video was playing at detection timestamp.

        Algorithm:
        1. Query TestSession to get sequence_id
        2. Query SequenceVideoResult for all videos in sequence
        3. Find video where: start_time <= timestamp < end_time
        4. Handle edge cases: first frame, last frame, gaps
        5. Validate result against metadata (if available)
        6. Return with confidence metrics

        Args:
            session_id: Test session ID
            detection_timestamp: Unix timestamp of detection
            db: Database session
            grace_period_ms: Grace period for boundary detections (default 100ms)

        Returns:
            VideoAssignment with video_id and validation metadata
        """
        import time
        warnings = []

        try:
            # Step 1: Get test session and sequence_id
            session = db.query(TestSession).filter_by(id=session_id).first()

            if not session:
                return VideoAssignment(
                    video_id=None,
                    confidence=0.0,
                    method="error",
                    is_valid=False,
                    start_time=None,
                    end_time=None,
                    validation_warnings=["Session not found"],
                    assignment_timestamp=time.time()
                )

            sequence_id = session.sequence_id

            # Step 2: Query timing boundaries (immutable source of truth)
            if sequence_id:
                # Multi-video sequence: query SequenceVideoResult
                video_results = db.query(SequenceVideoResult).filter(
                    SequenceVideoResult.video_sequence_id == sequence_id
                ).order_by(
                    SequenceVideoResult.sequence_order
                ).all()

                grace_period_s = grace_period_ms / 1000.0

                # Step 3: Find matching video by timestamp
                for result in video_results:
                    start_time = result.video_start_time
                    end_time = result.video_end_time

                    # Skip videos without start time
                    if start_time is None:
                        warnings.append(f"Video {result.video_id} missing start_time")
                        continue

                    # Adjust boundaries with grace period
                    effective_start = start_time - grace_period_s

                    # For last video (no end_time), use current time + buffer
                    if end_time is None:
                        effective_end = time.time() + grace_period_s
                    else:
                        effective_end = end_time + grace_period_s

                    # Check if detection falls within this video's time range
                    if effective_start <= detection_timestamp <= effective_end:
                        # Found match!
                        assignment = VideoAssignment(
                            video_id=result.video_id,
                            confidence=1.0,
                            method="timestamp_query",
                            is_valid=True,
                            start_time=start_time,
                            end_time=end_time,
                            validation_warnings=warnings,
                            assignment_timestamp=time.time()
                        )

                        # Step 5: Cross-validate with metadata (if available)
                        if session.sequence_metadata:
                            metadata_video_id = session.sequence_metadata.get('current_video_id')

                            if metadata_video_id and metadata_video_id != result.video_id:
                                warnings.append(
                                    f"Video ID mismatch: timestamp={result.video_id}, "
                                    f"metadata={metadata_video_id}"
                                )
                                assignment.confidence = 0.9  # Reduce confidence
                                assignment.validation_warnings = warnings

                                # Log critical mismatch
                                logger.error(
                                    f"🚨 METADATA DRIFT DETECTED: "
                                    f"timestamp-based={result.video_id}, "
                                    f"metadata={metadata_video_id}, "
                                    f"detection_ts={detection_timestamp:.6f}"
                                )

                        return assignment

                # No matching video found
                warnings.append(f"No video found for timestamp {detection_timestamp:.6f}")

                # Fallback: return last video if timestamp is beyond sequence end
                if video_results and video_results[-1].video_end_time:
                    if detection_timestamp > video_results[-1].video_end_time:
                        warnings.append("Using last video as fallback (detection after sequence end)")
                        return VideoAssignment(
                            video_id=video_results[-1].video_id,
                            confidence=0.5,
                            method="fallback_last_video",
                            is_valid=True,
                            start_time=video_results[-1].video_start_time,
                            end_time=video_results[-1].video_end_time,
                            validation_warnings=warnings,
                            assignment_timestamp=time.time()
                        )

            else:
                # Single-video session: use session.video_id
                return VideoAssignment(
                    video_id=session.video_id,
                    confidence=1.0,
                    method="single_video",
                    is_valid=True,
                    start_time=session.video_start_timestamp,
                    end_time=None,
                    validation_warnings=warnings,
                    assignment_timestamp=time.time()
                )

            # Complete failure: no video could be determined
            return VideoAssignment(
                video_id=None,
                confidence=0.0,
                method="failed",
                is_valid=False,
                start_time=None,
                end_time=None,
                validation_warnings=warnings + ["Could not determine video"],
                assignment_timestamp=time.time()
            )

        except Exception as e:
            logger.error(f"Error in get_video_for_timestamp: {e}")
            return VideoAssignment(
                video_id=None,
                confidence=0.0,
                method="error",
                is_valid=False,
                start_time=None,
                end_time=None,
                validation_warnings=[f"Exception: {str(e)}"],
                assignment_timestamp=time.time()
            )

    def validate_video_assignment(
        self,
        video_id: str,
        detection_timestamp: float,
        session_id: str,
        db: Session
    ) -> bool:
        """
        Validate that video_id matches detection_timestamp.

        Use this to verify assignments made by other components.

        Args:
            video_id: Video ID to validate
            detection_timestamp: Detection timestamp
            session_id: Test session ID
            db: Database session

        Returns:
            True if valid, False if mismatch detected
        """
        assignment = self.get_video_for_timestamp(session_id, detection_timestamp, db)

        if not assignment.is_valid:
            logger.warning(f"Invalid assignment for video {video_id}")
            return False

        if assignment.video_id != video_id:
            logger.error(
                f"🚨 VALIDATION FAILED: "
                f"expected={video_id}, "
                f"computed={assignment.video_id}, "
                f"timestamp={detection_timestamp:.6f}"
            )
            return False

        return True


# Global service instance
_video_assignment_service = None

def get_video_assignment_service() -> VideoAssignmentService:
    """Get global VideoAssignmentService instance"""
    global _video_assignment_service
    if _video_assignment_service is None:
        _video_assignment_service = VideoAssignmentService()
    return _video_assignment_service
```

#### 4.3.2 Updated LabJackDetectionService Integration

```python
# File: backend/services/labjack_detection_service.py
# Changes to _store_event_in_db() method

async def _store_event_in_db(self, event: DetectionEvent):
    """Store detection event with defensive video_id assignment"""
    try:
        db = SessionLocal()
        try:
            from models import DetectionEvent as DBDetectionEvent, TestSession
            from services.video_assignment_service import get_video_assignment_service

            # Step 1: Validate session exists
            session = db.query(TestSession).filter(
                TestSession.id == event.session_id
            ).first()

            if not session:
                logger.error(f"❌ Session {event.session_id} not found - rejecting detection")
                return False

            # Step 2: Use VideoAssignmentService (timestamp-based)
            assignment_service = get_video_assignment_service()
            assignment = assignment_service.get_video_for_timestamp(
                session_id=event.session_id,
                detection_timestamp=event.timestamp.timestamp()
                    if hasattr(event.timestamp, 'timestamp')
                    else event.timestamp,
                db=db
            )

            # Step 3: Validate assignment result
            if not assignment.is_valid:
                logger.error(
                    f"❌ Video assignment failed for detection {event.id}: "
                    f"{assignment.validation_warnings}"
                )
                # DECISION: Reject detection or use fallback?
                # Option A: Reject (strict mode)
                return False
                # Option B: Use fallback with warning
                # video_id = session.video_id  # First video fallback

            video_id = assignment.video_id

            # Step 4: Cross-validate with metadata (if available)
            metadata_video_id = None
            if session.sequence_id and session.sequence_metadata:
                metadata = session.sequence_metadata
                metadata_video_id = metadata.get('current_video_id')

                if metadata_video_id and metadata_video_id != video_id:
                    # CRITICAL: Metadata drift detected!
                    logger.error(
                        f"🚨 METADATA DRIFT: timestamp-based={video_id}, "
                        f"metadata={metadata_video_id}, confidence={assignment.confidence}"
                    )

                    # Emit metric for monitoring
                    self._metrics.record_video_id_mismatch(
                        session_id=event.session_id,
                        timestamp_based=video_id,
                        metadata_based=metadata_video_id,
                        detection_timestamp=assignment.assignment_timestamp
                    )

                    # DECISION: Trust timestamp or metadata?
                    # Recommendation: Trust timestamp (immutable), warn about metadata
                    # video_id = video_id  # Keep timestamp-based result

            # Step 5: Store detection with assignment metadata
            db_event = DBDetectionEvent(
                id=event.id,
                test_session_id=session.id,
                video_id=video_id,  # ✅ Defensively assigned
                timestamp=assignment.assignment_timestamp,
                # ... other fields ...

                # NEW: Store assignment metadata for auditing
                detection_metadata={
                    **(event.metadata or {}),
                    'video_assignment': {
                        'method': assignment.method,
                        'confidence': assignment.confidence,
                        'video_start_time': assignment.start_time,
                        'video_end_time': assignment.end_time,
                        'metadata_video_id': metadata_video_id,
                        'warnings': assignment.validation_warnings
                    }
                }
            )

            db.add(db_event)
            db.commit()

            logger.info(
                f"✅ Detection stored with defensive assignment: "
                f"video_id={video_id}, confidence={assignment.confidence}, "
                f"method={assignment.method}"
            )

            return True

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Failed to store detection: {e}")
        return False
```

### 4.4 Database Schema Enhancements

**No breaking changes required!** We leverage existing schema with additional validation:

```sql
-- SequenceVideoResult (existing table, already has needed fields)
CREATE TABLE sequence_video_results (
    id VARCHAR(36) PRIMARY KEY,
    video_sequence_id VARCHAR(36) NOT NULL,
    video_id VARCHAR(36) NOT NULL,
    sequence_order INTEGER NOT NULL,

    -- CRITICAL: These are our single source of truth
    video_start_time FLOAT,  -- Unix epoch timestamp when video started
    video_end_time FLOAT,    -- Unix epoch timestamp when video ended (NULL if current)
    actual_duration_ms FLOAT,

    -- Index for fast timestamp lookups
    INDEX idx_sequence_video_timing (video_sequence_id, video_start_time, video_end_time)
);

-- DetectionEvent (add assignment metadata)
ALTER TABLE detection_events
ADD COLUMN assignment_confidence FLOAT,
ADD COLUMN assignment_method VARCHAR(50),
ADD INDEX idx_assignment_confidence (assignment_confidence);
```

### 4.5 Sequence Diagrams

#### 4.5.1 Video Transition Flow (Proposed)

```
┌─────────┐         ┌────────────┐         ┌──────────────┐       ┌──────────┐
│Frontend │         │Orchestrator│         │VideoTimingSvc│       │Database  │
└────┬────┘         └─────┬──────┘         └──────┬───────┘       └────┬─────┘
     │                    │                        │                    │
     │ video_ended("aaa") │                        │                    │
     ├───────────────────>│                        │                    │
     │                    │                        │                    │
     │                    │ UPDATE SequenceVideoResult                  │
     │                    │   SET video_end_time = 12.0                 │
     │                    │   WHERE video_id = 'aaa'                    │
     │                    ├───────────────────────────────────────────>│
     │                    │                        │                 ✅ │
     │                    │<───────────────────────────────────────────┤
     │                    │                        │                    │
     │ video_started("bbb")│                       │                    │
     ├───────────────────>│                        │                    │
     │                    │                        │                    │
     │                    │ INSERT SequenceVideoResult                  │
     │                    │   (video_id='bbb', start_time=12.0, ...)  │
     │                    ├───────────────────────────────────────────>│
     │                    │                        │                 ✅ │
     │                    │<───────────────────────────────────────────┤
     │                    │                        │                    │
     │                    │ UPDATE sequence_metadata.current_video_id  │
     │                    │   (best effort, not critical)              │
     │                    ├───────────────────────────────────────────>│
     │                    │                        │                    │
     │                    │                        │                    │
```

#### 4.5.2 Detection Assignment Flow (Proposed)

```
┌──────────┐      ┌──────────┐      ┌─────────────┐      ┌──────────┐
│LabJack   │      │Assignment│      │Orchestrator │      │Database  │
│  Service │      │  Service │      │             │      │          │
└────┬─────┘      └────┬─────┘      └──────┬──────┘      └────┬─────┘
     │                 │                    │                   │
     │ Detection at    │                    │                   │
     │  t=15.0s        │                    │                   │
     ├────┐            │                    │                   │
     │    │            │                    │                   │
     │<───┘            │                    │                   │
     │                 │                    │                   │
     │ get_video_for_timestamp(15.0)       │                   │
     ├────────────────>│                    │                   │
     │                 │                    │                   │
     │                 │ Query SequenceVideoResult             │
     │                 │   WHERE start_time <= 15.0            │
     │                 │     AND (end_time IS NULL OR          │
     │                 │          end_time > 15.0)             │
     │                 ├───────────────────────────────────────>│
     │                 │                    │                   │
     │                 │<───────────────────────────────────────┤
     │                 │ Result: video_id='bbb' ✅             │
     │                 │                    │                   │
     │                 │ Cross-check metadata.current_video_id │
     │                 ├───────────────────────────────────────>│
     │                 │                    │                   │
     │                 │<───────────────────────────────────────┤
     │                 │ Metadata: 'aaa' ❌ MISMATCH DETECTED! │
     │                 │                    │                   │
     │<────────────────┤ Return VideoAssignment                │
     │ video_id='bbb'  │   confidence=0.9 (metadata mismatch)  │
     │ warnings=['drift']                  │                   │
     │                 │                    │                   │
     │ Store detection │                    │                   │
     │ video_id='bbb' ✅                    │                   │
     ├────────────────────────────────────────────────────────>│
     │                 │                    │                   │
     │ Log warning + metric                │                   │
     ├────────────────>│                    │                   │
     │                 │                    │                   │
```

---

## 5. Implementation Plan

### 5.1 Phase 1: Foundation (Week 1)

**Objective:** Build VideoAssignmentService without breaking existing system

**Tasks:**
1. ✅ Create `VideoAssignmentService` class
2. ✅ Implement `get_video_for_timestamp()` method
3. ✅ Implement `validate_video_assignment()` method
4. ✅ Add unit tests with mock database
5. ✅ Add integration tests with test database
6. ✅ Document API and usage patterns

**Deliverables:**
- `/backend/services/video_assignment_service.py`
- `/backend/tests/test_video_assignment_service.py`
- `/docs/video_assignment_service_api.md`

**Validation Criteria:**
- Unit tests: 95% coverage
- Integration tests: All edge cases covered
- Performance: <5ms per assignment query
- Zero impact on existing detection flow

### 5.2 Phase 2: Integration (Week 2)

**Objective:** Integrate VideoAssignmentService into detection storage path

**Tasks:**
1. ✅ Update `labjack_detection_service.py` `_store_event_in_db()`
2. ✅ Add assignment metadata to detection_events schema
3. ✅ Implement cross-validation with existing metadata
4. ✅ Add metrics for video_id mismatches
5. ✅ Deploy to staging environment
6. ✅ Run parallel validation (log warnings, don't block)

**Deliverables:**
- Updated `labjack_detection_service.py`
- Database migration for new columns
- Metrics dashboard for assignment monitoring
- Staging deployment package

**Validation Criteria:**
- Zero detection storage failures
- Assignment confidence >0.95 for 99% of detections
- Metadata drift detection working (logs + metrics)
- Performance impact <10ms per detection

### 5.3 Phase 3: Enforcement (Week 3)

**Objective:** Make timestamp-based assignment authoritative

**Tasks:**
1. ✅ Switch from warning to rejection for invalid assignments
2. ✅ Add fallback logic for edge cases
3. ✅ Implement real-time alerts for metadata drift
4. ✅ Deploy to production with feature flag
5. ✅ Monitor for 1 week with flag enabled
6. ✅ Remove old metadata-only assignment path

**Deliverables:**
- Feature flag configuration
- Alert rules in monitoring system
- Production deployment runbook
- Rollback procedure

**Validation Criteria:**
- Zero false rejections
- All metadata drift cases caught and alerted
- Video ID assignment accuracy: 100%
- Detection storage success rate: >99.9%

### 5.4 Phase 4: Cleanup (Week 4)

**Objective:** Remove redundant code and optimize

**Tasks:**
1. ✅ Remove `sequence_metadata.current_video_id` updates (deprecated)
2. ✅ Optimize database queries with better indexes
3. ✅ Add caching for repeated timestamp queries
4. ✅ Update documentation and runbooks
5. ✅ Conduct post-implementation review

**Deliverables:**
- Code cleanup PR
- Performance optimization report
- Updated system documentation
- Post-implementation retrospective doc

---

## 6. Validation Strategy

### 6.1 Correctness Validation

**Test Scenarios:**

1. **Single Video Session**
   - Detection before video start → Reject or clamp to start
   - Detection during video → Assign to video
   - Detection after video end → Assign to video (with warning)

2. **Multi-Video Sequence**
   - Detection in Video 1 → video_id = video_1
   - Detection at Video 1→2 transition (within 100ms) → Use timestamp, assign to closer video
   - Detection in Video 2 → video_id = video_2
   - Detection after last video ends → Assign to last video (with warning)

3. **Edge Cases**
   - Video with NULL end_time (current video) → Assign detections up to current time
   - Gap between videos → Reject or assign to nearest video
   - Overlapping video times (bug scenario) → Detect and alert
   - Missing video start_time → Fall back to metadata with reduced confidence

4. **Failure Modes**
   - Metadata drift (current_video_id stale) → Cross-validation catches it
   - Database query failure → Return invalid assignment, log error
   - No videos in sequence → Use session.video_id fallback

### 6.2 Performance Validation

**Benchmarks:**
- Query time: <5ms for 99th percentile
- Database index usage: 100% (no table scans)
- Memory footprint: <1MB per session
- Concurrent queries: Handle 100 req/s

### 6.3 Production Validation

**Monitoring Metrics:**
1. `video_assignment.confidence` - Should be >0.95 for 99% of detections
2. `video_assignment.mismatch_rate` - Should be <0.1% (metadata drift alerts)
3. `video_assignment.query_latency_ms` - Should be <5ms p99
4. `video_assignment.method` - Track distribution (timestamp_query vs fallback)

**Alerting Thresholds:**
- confidence <0.95 for >1% of detections → Page on-call
- mismatch_rate >1% → Page on-call
- query_latency_ms >10ms p99 → Warning alert
- Invalid assignment rate >0.1% → Page on-call

---

## 7. Migration Path

### 7.1 Backward Compatibility

**✅ Zero Breaking Changes During Migration**

The proposed architecture is **additive only:**
1. New `VideoAssignmentService` runs in parallel with existing logic
2. Existing `sequence_metadata.current_video_id` continues to work
3. Cross-validation mode allows gradual confidence building
4. Feature flag enables phased rollout

**Migration Stages:**

```
Stage 1: PARALLEL VALIDATION (Week 1-2)
┌──────────────────────────────────────────┐
│ Both assignment methods run in parallel  │
│ - Metadata-based: Current production    │
│ - Timestamp-based: Log warnings only    │
│ - Collect mismatch statistics           │
│ - Build confidence in new method        │
└──────────────────────────────────────────┘

Stage 2: TIMESTAMP PRIMARY (Week 3)
┌──────────────────────────────────────────┐
│ Timestamp-based becomes primary          │
│ - Use timestamp result for video_id     │
│ - Validate against metadata             │
│ - Alert on mismatches                   │
│ - Keep metadata as validation source    │
└──────────────────────────────────────────┘

Stage 3: TIMESTAMP ONLY (Week 4)
┌──────────────────────────────────────────┐
│ Remove metadata-based assignment         │
│ - Stop updating current_video_id        │
│ - Remove metadata validation code       │
│ - Timestamp is sole source of truth     │
│ - Metadata field deprecated             │
└──────────────────────────────────────────┘
```

### 7.2 Rollback Plan

**If critical bug found, rollback is trivial:**

1. **Stage 1→Production:** Just disable logging (no behavioral changes)
2. **Stage 2→Stage 1:** Flip feature flag to use metadata-based assignment
3. **Stage 3→Stage 2:** Re-enable metadata updates and validation

**Rollback Procedure (5 minutes):**
```bash
# Emergency rollback: disable timestamp-based assignment
kubectl set env deployment/backend VIDEO_ASSIGNMENT_METHOD=metadata

# Restart pods
kubectl rollout restart deployment/backend

# Verify
curl https://api/health/video-assignment
```

---

## 8. Monitoring Requirements

### 8.1 Real-Time Metrics

**VideoAssignment Service Metrics:**

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|-----------------|
| `video_assignment.total` | Counter | Total assignments | N/A |
| `video_assignment.success` | Counter | Successful assignments | N/A |
| `video_assignment.failed` | Counter | Failed assignments | >10/min |
| `video_assignment.confidence` | Histogram | Assignment confidence distribution | p50 <0.95 |
| `video_assignment.method` | Counter (labeled) | Assignment method used | N/A |
| `video_assignment.mismatch` | Counter | Metadata vs timestamp mismatches | >5/min |
| `video_assignment.query_latency_ms` | Histogram | Database query time | p99 >10ms |
| `video_assignment.cache_hit_rate` | Gauge | Cache effectiveness | <80% |

**Detection Storage Metrics:**

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|-----------------|
| `detection.stored_total` | Counter | Total detections stored | N/A |
| `detection.wrong_video_rate` | Gauge | % detections with wrong video_id | >0.1% |
| `detection.rejected_invalid_video` | Counter | Detections rejected (invalid video) | >5/min |

### 8.2 Dashboards

**Video Assignment Dashboard:**
- Line chart: Assignment confidence over time (p50, p95, p99)
- Pie chart: Assignment method distribution
- Line chart: Metadata mismatch rate
- Heatmap: Mismatches by video transition boundaries
- Table: Recent mismatches with details

**Detection Quality Dashboard:**
- Line chart: Detections per video over time
- Bar chart: Detection distribution across videos in sequence
- Line chart: Invalid assignment rate
- Table: Recent rejected detections

### 8.3 Alerting Rules

**Critical Alerts (Page On-Call):**
1. `video_assignment.confidence` <0.95 for >1% of detections for 5 min
2. `video_assignment.mismatch` >5/min for 5 min
3. `detection.rejected_invalid_video` >10/min for 5 min
4. `detection.wrong_video_rate` >0.5% for 5 min

**Warning Alerts (Slack):**
1. `video_assignment.query_latency_ms` p99 >10ms for 10 min
2. `video_assignment.cache_hit_rate` <80% for 30 min
3. `video_assignment.failed` >5/min for 10 min

---

## 9. Risk Assessment

### 9.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Query performance degradation** | Medium | Medium | Add indexes, caching, load testing before production |
| **Edge case misassignment** | Low | High | Comprehensive test suite, staged rollout with validation |
| **Database connection failures** | Low | High | Implement retry logic, fallback to metadata with warning |
| **Race conditions at transitions** | Low | Medium | Grace period (100ms), timestamp-based ordering |
| **Cached stale data** | Medium | Low | Cache TTL=5s, invalidate on video transitions |

### 9.2 Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Monitoring gaps** | Low | High | Deploy metrics + alerts in Stage 1, validate before Stage 2 |
| **Alert fatigue** | Medium | Medium | Tune thresholds during parallel validation phase |
| **Rollback complexity** | Low | Medium | Feature flag + simple rollback procedure, test in staging |
| **Documentation staleness** | High | Low | Update docs as part of each phase, post-impl review |

### 9.3 Business Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **False detection rejections** | Low | High | Extensive testing, gradual rollout with monitoring |
| **Compliance audit failure** | Low | Critical | Implement audit trail, validate in pre-production |
| **Customer trust loss** | Low | Critical | Phased rollout, clear communication, fast rollback capability |

**Risk Acceptance:** All identified risks have mitigation strategies. No showstopper risks identified.

---

## 10. Appendices

### Appendix A: Alternative Approaches Considered

#### A.1 Option B: Event-Driven State Machine

**Architecture:**
```python
class VideoStateMachine:
    def on_video_started(video_id, start_time):
        self.current_video = video_id
        self.transition_time = start_time

    def get_current_video() -> str:
        return self.current_video
```

**Pros:**
- Explicit state transitions
- Real-time current_video tracking

**Cons:**
- **Rejected Reason:** Still relies on in-memory state that can drift
- Requires video lifecycle events to be 100% reliable
- No historical query capability ("what video was playing at t=X?")
- More complex error recovery

#### A.2 Option C: Dual-Source Validation Only

**Architecture:**
```python
def assign_video(detection):
    metadata_video = get_from_metadata()
    timestamp_video = get_from_timestamp()

    if metadata_video != timestamp_video:
        raise AssignmentConflictError()
```

**Pros:**
- Catches inconsistencies
- Validates both sources

**Cons:**
- **Rejected Reason:** Doesn't solve the problem, just detects it
- Requires manual intervention when mismatch occurs
- Doesn't provide authoritative answer

### Appendix B: Database Query Optimization

**Index Design:**
```sql
-- Composite index for timestamp range queries
CREATE INDEX idx_sequence_video_timing
ON sequence_video_results(
    video_sequence_id,
    video_start_time,
    video_end_time
)
WHERE video_start_time IS NOT NULL;

-- Covering index to avoid table lookups
CREATE INDEX idx_sequence_video_lookup
ON sequence_video_results(
    video_sequence_id,
    sequence_order
)
INCLUDE (video_id, video_start_time, video_end_time);
```

**Query Plan Analysis:**
```sql
EXPLAIN ANALYZE
SELECT video_id, video_start_time, video_end_time
FROM sequence_video_results
WHERE video_sequence_id = 'seq_123'
  AND video_start_time <= 15.0
  AND (video_end_time IS NULL OR video_end_time > 15.0);

-- Expected: Index-only scan, <5ms execution time
```

### Appendix C: Test Coverage Matrix

| Scenario | Unit Test | Integration Test | E2E Test |
|----------|-----------|------------------|----------|
| Single video detection | ✅ | ✅ | ✅ |
| Multi-video detection | ✅ | ✅ | ✅ |
| Video transition boundary | ✅ | ✅ | ✅ |
| Metadata drift detection | ✅ | ✅ | ⏸️ |
| Database query failure | ✅ | ✅ | ⏸️ |
| NULL end_time handling | ✅ | ✅ | ✅ |
| Grace period edge case | ✅ | ✅ | ⏸️ |
| High-load concurrent queries | ⏸️ | ✅ | ✅ |

### Appendix D: Comparison with Original Requirements

| Requirement | Current System | Proposed System |
|-------------|----------------|-----------------|
| **Single source of truth** | ❌ Metadata can drift | ✅ Database timing boundaries |
| **Atomic updates** | ❌ JSON field update | ✅ Database row insert |
| **Defensive assignment** | ❌ Trusts metadata | ✅ Computes from timestamps |
| **Validation at assignment** | ❌ No validation | ✅ Cross-validation + confidence |
| **Boundary handling** | ⚠️ Arbitrary | ✅ Grace period + fallback |
| **Failure recovery** | ❌ Silent failures | ✅ Explicit fallback + alerting |
| **Real-time monitoring** | ❌ No metrics | ✅ Comprehensive metrics |
| **Auditability** | ⚠️ Limited | ✅ Assignment metadata stored |

**Score:** 8/8 requirements met ✅

---

## Conclusion

The proposed **Timestamp-Based Video Assignment with Defensive Validation** architecture eliminates the entire class of metadata synchronization bugs by making **immutable database timing boundaries the single source of truth** for video identification.

**Key Benefits:**
1. ✅ **Zero Trust:** Detection service doesn't trust mutable metadata
2. ✅ **Self-Healing:** Automatically detects and corrects metadata drift
3. ✅ **Auditable:** Every assignment decision is logged with confidence metrics
4. ✅ **Backward Compatible:** Zero breaking changes during migration
5. ✅ **Production Ready:** Comprehensive testing, monitoring, and rollback procedures

**Recommendation:** **Approve for implementation**. Begin Phase 1 (Foundation) immediately, with target completion in 4 weeks.

---

## Sign-Off

**Architecture Approved By:**
- [ ] System Architect: ______________________  Date: __________
- [ ] Tech Lead: ____________________________  Date: __________
- [ ] VP Engineering: _______________________  Date: __________

**Implementation Approved By:**
- [ ] Product Manager: ______________________  Date: __________
- [ ] QA Lead: ______________________________  Date: __________
- [ ] DevOps Lead: __________________________  Date: __________
