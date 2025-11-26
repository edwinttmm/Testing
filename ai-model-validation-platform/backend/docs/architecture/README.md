# Architecture Documentation

This directory contains architecture analysis and design documents for the AI Model Validation Platform's HIL (Hardware-in-Loop) testing system.

## Documents

### 1. [Session Management Analysis](./session-management-analysis.md)
**Status:** Root Cause Identified
**Priority:** HIGH - System Correctness Issue

Comprehensive analysis of the duplicate session problem where TWO concurrent sessions are created for a single test execution.

**Key Findings:**
- Session 1 (028afcb1...): Created by API (polling mode) ✅ Correct
- Session 2 (90fb1ae4...): Created by unknown path (stream mode) ❌ Bug
- Result: Duplicate detection processing, hardware conflicts, data integrity issues

**Sections:**
- Executive Summary
- Root Cause Analysis
- Session Creation Flow (2 paths identified)
- Architecture Design Issues
- Evidence of Dual Session Behavior

### 2. [Duplicate Session Fix Recommendations](./duplicate-session-fix-recommendations.md)
**Status:** Implementation Ready
**Priority:** CRITICAL

Detailed recommendations and implementation guide for fixing the duplicate session issue.

**Key Solutions:**
1. **Session Registration Guard** (Immediate) - Add existence checks
2. **Comprehensive Logging** (Immediate) - Track call sources
3. **Session Registry Pattern** (Short-term) - Centralized session management
4. **Investigation Script** (Urgent) - Find phantom session source
5. **Metrics & Alerts** (Medium-term) - Monitoring and prevention

**Deployment Plan:**
- Phase 1 (Day 1): Guards and logging
- Phase 2 (Days 2-3): SessionRegistry implementation
- Phase 3 (Week 1): Metrics and alerts
- Phase 4 (Weeks 2-4): Lifecycle refactoring

### 3. [Session Flow Diagram](./session-flow-diagram.md)
**Status:** Documentation
**Type:** Visual Architecture

Visual diagrams showing:
- Current architecture (with bug)
- Session creation flow paths
- Duplicate session impact cascade
- Proposed architecture (with fix)
- Investigation tools

**Key Visualizations:**
- API → Monitor flow (correct path)
- Unknown caller → Monitor flow (bug)
- Hardware layer confusion
- Session Registry guard mechanism

## Quick Reference

### Problem Summary

```
EXPECTED:  1 test → 1 session → 1 video → 1 callback
ACTUAL:    1 test → 2 sessions → 1 video → 2 callbacks ❌
```

### Symptoms

- ✅ Database has primary session (028afcb1...)
- ❌ Monitor has TWO active_sessions entries
- ❌ TWO detection callbacks registered
- ❌ Hardware mode oscillates (polling ↔ stream)
- ❌ Detections processed twice
- ❌ 219ms timing drift between sessions

### Root Cause

**An unidentified code path** is calling `start_monitoring_with_video_sync()` with a new session ID, bypassing the API's session creation.

**Suspects:**
1. WebSocket handlers
2. Background workers/threads
3. LabJack service manager
4. Windows bridge service
5. Video lifecycle orchestrator
6. Health check/recovery processes

### Immediate Actions

1. **Add logging to identify caller:**
   ```python
   # In dedicated_labjack_monitor.py
   import traceback
   logger.info("Call stack:\n" + "".join(traceback.format_stack()[-5:]))
   ```

2. **Add existence guard:**
   ```python
   if session_id in self.active_sessions:
       logger.warning(f"Session {session_id} already exists")
       return False
   ```

3. **Run monitoring script:**
   ```bash
   python backend/scripts/find_duplicate_sessions.py
   ```

4. **Trigger test and capture logs:**
   - Start video sequence test
   - Watch for "NEW SESSION DETECTED" logs
   - Identify caller from stack trace

### Files to Modify

**High Priority:**
- `/backend/services/dedicated_labjack_monitor.py` (lines 450-620)
  - Add session existence guard
  - Add database validation
  - Add call stack logging

**New Files:**
- `/backend/services/session_registry.py` (SessionRegistry class)
- `/backend/scripts/find_duplicate_sessions.py` (Investigation tool)

**Testing:**
- `/backend/tests/test_session_uniqueness.py` (New test suite)

### Success Criteria

- [ ] Only ONE session created per test
- [ ] Only ONE detection callback registered
- [ ] Hardware mode stays constant
- [ ] All detections assigned to primary session
- [ ] Zero duplicate session attempts blocked
- [ ] Database and monitor state consistent

## Related Documentation

### Internal Links
- [HIL Timing Fix Implementation](../hil_timing_fix_implementation.md)
- [Database Schema Design](../database/schema-design.md)
- [Session Completion Service](../../services/session_completion_service.py)

### Key Source Files
- `/backend/routers/video_sequence_testing.py` - API endpoint (correct)
- `/backend/services/dedicated_labjack_monitor.py` - Monitor core (needs guards)
- `/backend/services/session_management_service.py` - Project session management

### Models
- `/backend/models.py` - TestSession, DetectionEvent, VideoTestSequence

## Investigation Checklist

When debugging session issues:

- [ ] Check active_sessions count in monitor
- [ ] Verify TestSession exists in database
- [ ] Count detection_callbacks registered
- [ ] Check LabJack hardware mode (stream vs polling)
- [ ] Query DetectionEvent table for duplicates
- [ ] Review application logs for session creation
- [ ] Check WebSocket connection handlers
- [ ] Verify no background workers creating sessions
- [ ] Test with monitoring script running

## Contact

For questions about this architecture:
- Review the [session-management-analysis.md](./session-management-analysis.md) document
- Check the [duplicate-session-fix-recommendations.md](./duplicate-session-fix-recommendations.md) implementation guide
- Refer to code comments in `dedicated_labjack_monitor.py`

---

**Last Updated:** 2025-11-25
**Status:** Root cause identified, fix implementation ready
**Priority:** CRITICAL - Deploy Phase 1 immediately
