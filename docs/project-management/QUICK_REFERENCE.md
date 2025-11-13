# QUICK REFERENCE GUIDE
## Video Assignment Architecture Migration - At-a-Glance

**Status**: Ready for Execution | **Last Updated**: 2025-11-07

---

## 🚀 IMMEDIATE ACTION REQUIRED (TODAY - 2 HOURS)

### Phase 0: Emergency Fix
```bash
# 1. Fix socketio_server.py line 594
# Change: active_video_id → event.get('video_id', active_video_id)

# 2. Deploy
systemctl stop hil-backend
# Apply changes
systemctl start hil-backend

# 3. Validate
# Run test session with 2 videos
# Query: SELECT video_id, COUNT(*) FROM detection_events GROUP BY video_id
```

**Success Criteria**: Video 2 detections have correct video_id

---

## 📅 5-WEEK PLAN (ONE-PAGE SUMMARY)

| Week | Phase | Duration | Outcome | Go/No-Go |
|------|-------|----------|---------|----------|
| **Week 1** | Phase 1: Stabilization | 5 days (40h) | <1% error rate, system stable | ✓ Required |
| **Week 2** | Phase 2: Enhancements | 5 days (32h) | <0.1% timestamp mismatches | Optional |
| **Week 3** | Phase 3: Review + Phase 4 Start | 2 days + 3 days | Stakeholder approval + 60% complete | ✓ Required |
| **Week 4** | Phase 4: Implementation | 5 days (56h) | Service deployed, 95% test coverage | ✓ Required |
| **Week 5** | Phase 5: Migration | 5 days (32h) | Single service, legacy code removed | ✓ Required |

**Total Investment**: $19,000 | **Expected ROI**: 156% in year 1

---

## 🎯 KEY METRICS

### Current State (Broken)
- ❌ 30% of Video 2 detections have wrong video_id
- ❌ 50+ N+1 queries per session
- ❌ 8 hours/week spent debugging
- ❌ Customer satisfaction: 3.2/5

### Target State (Fixed)
- ✅ <0.1% detection assignment errors
- ✅ 0 N+1 queries
- ✅ 2 hours/week maintenance
- ✅ Customer satisfaction: 4.5/5

---

## ⚠️ TOP 5 RISKS

| Risk | Mitigation |
|------|------------|
| 1. Migration breaks production | Phased rollout, instant rollback (<5 min) |
| 2. Key engineer unavailable | Knowledge sharing, contractor backup |
| 3. Customer reports issue | Fast response SLA (<2h), on-call |
| 4. Stakeholders reject refactoring | Strong business case, demo benefits |
| 5. False sense of security | Comprehensive test scenarios |

**Overall Risk**: MEDIUM (well-managed)

---

## 🔄 ROLLBACK PROCEDURES

| Phase | Rollback Time | Procedure |
|-------|---------------|-----------|
| Phase 0 | 5 minutes | `git revert HEAD && systemctl restart hil-backend` |
| Phase 1 | 10-15 minutes | Revert specific commit, redeploy |
| Phase 2 | <1 minute | Feature flag toggle |
| Phase 5b-c | 5-15 minutes | Service-by-service rollback |
| Emergency | 15 minutes | Full system revert to last known good |

---

## 📊 RESOURCE REQUIREMENTS

| Role | Total Hours | Cost | Availability |
|------|-------------|------|--------------|
| Backend Engineer | 130h | $9,750 | Full-time Weeks 1-5 |
| Senior Backend Engineer | 48h | $4,800 | 60% Weeks 3-4 |
| QA Engineer | 40h | $2,600 | Part-time 20-40% |
| DevOps | 12h | $960 | On-demand 10-20% |
| Engineering Manager | 8h | $880 | Meetings only Week 3 |
| **TOTAL** | **238h** | **$19,000** | |

---

## 📞 WHO TO CONTACT

### Decision Makers
- **Engineering Manager (Sarah Chen)**: Budget approval, go/no-go decisions
- **VP Engineering (David Park)**: Executive sponsor, major delays
- **Product Manager (Emily Rodriguez)**: Customer impact, timeline changes

### Technical Leads
- **Backend Engineer (Technical Lead)**: Day-to-day execution, code review
- **Senior Backend Engineer**: Architecture design, Phase 4 implementation
- **QA Lead (Michael Kim)**: Testing strategy, quality gates
- **DevOps Lead (Alex Thompson)**: Deployments, rollbacks, monitoring

### Escalation Path
P0 (Critical) → Backend Eng → Eng Manager → VP Eng (15 min response)
P1 (High) → Backend Eng → Eng Manager (1 hour response)

---

## 📈 SUCCESS CRITERIA BY PHASE

### Phase 0 (TODAY, 2 hours)
- ✅ Video 2 detections have correct video_id
- ✅ No regression in Video 1 assignments

### Phase 1 (Week 1)
- ✅ <1% detection assignment errors
- ✅ Zero N+1 query occurrences
- ✅ >99.9% websocket delivery

### Phase 2 (Week 2) - OPTIONAL
- ✅ <0.1% timestamp mismatches
- ✅ Zero race conditions
- ✅ <10ms validation overhead

### Phase 3 (Week 3, Days 1-2)
- ✅ Stakeholder approval (100% of groups)
- ✅ Maintenance window scheduled
- ✅ Budget allocated

### Phase 4 (Week 3-4, Days 3-10)
- ✅ 95% test coverage
- ✅ <5ms assignment latency
- ✅ Zero memory leaks
- ✅ Complete documentation

### Phase 5 (Week 5)
- ✅ <1% discrepancy in validation mode (Phase 5a)
- ✅ All services using unified VideoAssignmentService (Phase 5b-c)
- ✅ Zero deprecated code (Phase 5d)
- ✅ 100% test suite pass rate

---

## 🗓️ CRITICAL DATES

| Date | Event | Stakeholders |
|------|-------|--------------|
| **2025-11-07 (TODAY)** | Phase 0: Emergency Fix | Backend Eng, DevOps |
| **2025-11-13** | Phase 1 Complete + Go/No-Go | Eng Manager, Team |
| **2025-11-20** | Phase 2 Complete + Go/No-Go | Eng Manager, Team |
| **2025-11-21-22** | Phase 3: Stakeholder Presentations | Eng Leadership, PM, Execs |
| **2025-11-22** | Phase 4 Approval Decision | All stakeholders |
| **2025-12-05** | Phase 4 Complete + Go/No-Go | Eng Manager, Team |
| **2025-12-12** | 🎉 PROJECT COMPLETE 🎉 | All stakeholders |

---

## 📋 DAILY CHECKLIST (Phase 0-1)

### TODAY (Phase 0)
- [ ] Apply fix to socketio_server.py
- [ ] Deploy to production
- [ ] Run validation tests
- [ ] Document incident
- [ ] Send completion email to Eng Manager

### Week 1 (Phase 1)
**Daily Tasks**:
- [ ] Check error logs (morning, midday, evening)
- [ ] Review metrics dashboard
- [ ] Update Slack #hil-video-assignment-project (4pm)
- [ ] Triage any new issues discovered

**End of Week**:
- [ ] Generate weekly status report (Friday 3pm)
- [ ] Present go/no-go decision to Eng Manager (Friday 4pm)

---

## 💰 BUDGET TRACKING

```
Total Budget: $19,000
├─ Phase 0: $150 (0.8%)
├─ Phase 1: $3,900 (20.5%)
├─ Phase 2: $3,000 (15.8%)  ← OPTIONAL
├─ Phase 3: $1,800 (9.5%)
├─ Phase 4: $6,000 (31.6%)
└─ Phase 5: $3,000 (15.8%)

Budget Burn Rate:
Week 1: $3,900 (20.5%)
Week 2: $3,000 (15.8%)
Week 3: $3,600 (19.0%)
Week 4: $4,200 (22.1%)
Week 5: $3,000 (15.8%)
```

---

## 🎯 PROJECT GOALS (REMIND YOURSELF DAILY)

**Problem**: Video assignment logic is fragmented across 4+ services, causing 30% error rate

**Solution**: Build unified VideoAssignmentService as single source of truth

**Outcome**: <0.1% error rate, zero N+1 queries, 75% less maintenance

**Timeline**: 5 weeks (25 business days)

**Investment**: $19,000

**ROI**: 156% in year 1, 4.7 month payback

---

## 🚦 GO/NO-GO DECISION FRAMEWORK

### When to STOP (Red Flags)
- ❌ Error rate increases above 5% after fix
- ❌ Customer-impacting bugs reported
- ❌ Performance degrades >20%
- ❌ Key engineer unavailable (illness/emergency)
- ❌ Stakeholders reject refactoring (Phase 3)
- ❌ Budget overrun >25%

### When to PROCEED (Green Lights)
- ✅ All success criteria met for current phase
- ✅ No critical bugs in production
- ✅ Team capacity available for next phase
- ✅ Budget on track
- ✅ Stakeholder approval secured

---

## 📚 DOCUMENTATION INDEX

**Detailed Plans**:
- `/docs/project-management/DEPLOYMENT_ROADMAP.md` (full 25-page plan)
- `/docs/project-management/VISUAL_GANTT_CHART.md` (timeline visualization)
- `/docs/project-management/EXECUTIVE_SUMMARY.md` (leadership presentation)

**Quick References**:
- `/docs/project-management/QUICK_REFERENCE.md` (this document)
- `/docs/project-management/ROLLBACK_PROCEDURES.md` (detailed rollback steps)

**Status Tracking**:
- Slack: `#hil-video-assignment-project` (daily updates)
- Jira: `HIL-VIDEO-ASSIGNMENT` (task tracking)
- Confluence: `Video Assignment Migration` (living documentation)

---

## 🎬 NEXT IMMEDIATE ACTIONS

1. **RIGHT NOW** (0-30 min):
   - Read this Quick Reference
   - Review Phase 0 tasks
   - Confirm team availability

2. **TODAY** (30 min - 2 hours):
   - Execute Phase 0 emergency fix
   - Validate fix works
   - Send completion notification

3. **TOMORROW** (Day 2):
   - Begin Phase 1 monitoring
   - Set up metrics dashboard
   - Start edge case discovery

4. **END OF WEEK 1**:
   - Generate weekly status report
   - Present go/no-go decision for Phase 2

5. **WEEK 3, DAY 1-2**:
   - Stakeholder presentations
   - Get approval for Phases 4-5

---

**REMEMBER**: This is a phased, low-risk approach. We have rollback plans at every step. The goal is steady progress, not heroic rescues.

---

**Status**: ✅ Ready to Execute
**Confidence**: High
**Recommendation**: PROCEED with Phase 0 immediately

**Questions?** Contact:
- Technical: Backend Engineering Lead
- Process: Engineering Manager (Sarah Chen)
- Budget: VP Engineering (David Park)
