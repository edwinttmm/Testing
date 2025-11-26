# User Guide - Quality Metrics and Warnings

**Version**: 1.0.0
**Last Updated**: 2025-11-19
**Audience**: End Users, QA Engineers, Test Operators

---

## What is Quality Tracking?

The Quality Tracking system automatically monitors the reliability and accuracy of your test sessions. It helps you understand when test data may not be trustworthy due to timing issues, synchronization problems, or other quality concerns.

**In Simple Terms**: Think of it as a health check for your test data. Just like a doctor tells you if your vital signs are good or concerning, this system tells you if your test results are reliable or need attention.

---

## Table of Contents

1. [Understanding Quality Levels](#understanding-quality-levels)
2. [Quality Warnings Explained](#quality-warnings-explained)
3. [Using Quality Filters](#using-quality-filters)
4. [Reading the Quality Dashboard](#reading-the-quality-dashboard)
5. [When to Be Concerned](#when-to-be-concerned)
6. [Best Practices](#best-practices)
7. [Troubleshooting Common Issues](#troubleshooting-common-issues)
8. [FAQ](#frequently-asked-questions)

---

## Understanding Quality Levels

Every test session is automatically assigned a quality level based on its timing accuracy and data reliability.

### High Quality ✅

**What it means**: Your test data is reliable and can be trusted for validation.

**Indicators**:
- Timing accuracy is excellent (< 5% degraded)
- Most detections are usable (> 95%)
- No significant timing issues detected
- Data is suitable for ground truth validation

**What you should do**: Nothing! Your tests are working perfectly.

**Example**:
```
Session: video_test_001
Quality Level: HIGH ✅
Usable Detections: 98/100 (98%)
Timing Issues: 2%
```

---

### Medium Quality ⚠️

**What it means**: Your test data has some quality issues but is still mostly usable.

**Indicators**:
- Timing accuracy is good (5-25% degraded)
- Most detections are usable (75-95%)
- Some timing synchronization issues
- Data may be usable with caution

**What you should do**:
- Review the warnings to understand the issues
- Consider re-running critical tests
- Monitor if the issue persists

**Example**:
```
Session: video_test_002
Quality Level: MEDIUM ⚠️
Usable Detections: 85/100 (85%)
Timing Issues: 15%
Warning: 15% of detections have degraded timing accuracy
```

---

### Low Quality ❌

**What it means**: Your test data has significant quality issues and should not be used for validation.

**Indicators**:
- Timing accuracy is poor (> 25% degraded)
- Many detections are unusable (< 75%)
- Significant timing synchronization problems
- Data should not be used for ground truth

**What you should do**:
- Do NOT use this data for validation
- Review system logs for errors
- Check hardware connections (cameras, sensors)
- Re-run the test session
- Contact support if issue persists

**Example**:
```
Session: video_test_003
Quality Level: LOW ❌
Usable Detections: 45/100 (45%)
Timing Issues: 55%
Critical Warning: More than 50% of detections have timing issues
Recommendation: Re-run this test session
```

---

## Quality Warnings Explained

Warnings help you understand specific issues with your test data.

### Warning Types

#### 1. Timing Degraded ⏱️

**What it means**: The timing synchronization between video and sensor data is off.

**Why it happens**:
- Network latency spikes
- System overload during recording
- Hardware timing drift
- Sensor synchronization issues

**Impact**: Detections may not align correctly with ground truth

**Example Warning**:
```
⚠️ Timing Degraded
Message: 18% of detections have degraded timing accuracy
Impact: Moderate impact on timing precision
Affected Items: 18 detections
```

**What to do**:
- Check network stability
- Reduce system load during testing
- Verify sensor connections
- Review timing synchronization settings

---

#### 2. Low Confidence 📊

**What it means**: The detection algorithm is not confident about some detections.

**Why it happens**:
- Poor lighting conditions
- Object partially obscured
- Low video quality
- Movement blur

**Impact**: Detections may not be accurate

**Example Warning**:
```
⚠️ Low Confidence Detections
Message: 12 detections have confidence below threshold (0.6)
Impact: These detections may not be reliable
Affected Items: 12 detections
```

**What to do**:
- Improve lighting conditions
- Clean camera lens
- Increase video quality settings
- Reduce motion blur

---

#### 3. Detection Gaps 📉

**What it means**: Expected detections are missing from the results.

**Why it happens**:
- Object moved out of frame
- Detection algorithm missed the object
- Processing errors
- Hardware failures

**Impact**: Incomplete test coverage

**Example Warning**:
```
⚠️ Detection Gaps
Message: Expected 100 detections, only found 85
Impact: Test coverage is incomplete
Missing: 15 detections
```

**What to do**:
- Review video footage for missing objects
- Check detection algorithm settings
- Verify complete test execution
- Re-run test if necessary

---

#### 4. Validation Failure 🔴

**What it means**: Test results don't match expected ground truth.

**Why it happens**:
- Algorithm accuracy issues
- Ground truth data is incorrect
- Test environment changed
- Quality issues (see above)

**Impact**: Test failed validation

**Example Warning**:
```
🔴 Validation Failure
Message: Actual detections (65) significantly differ from expected (100)
Impact: Test did not meet acceptance criteria
Difference: -35 detections
```

**What to do**:
- Review test parameters
- Verify ground truth data is correct
- Check for quality issues
- Investigate algorithm behavior

---

## Using Quality Filters

Quality filters help you find and analyze test sessions based on their quality level.

### In the HIL Results Page

**Filter by Quality Level**:

1. Open the HIL Results page
2. Look for the "Quality Filter" dropdown
3. Select quality level:
   - **All**: Show all test sessions (default)
   - **High Quality Only**: Show only reliable sessions
   - **Medium or Better**: Exclude low-quality sessions
   - **Has Warnings**: Show sessions with any warnings
   - **Low Quality**: Show only problematic sessions

**Use Cases**:

- **For Validation**: Use "High Quality Only" to find trustworthy data
- **For Debugging**: Use "Low Quality" to find problematic sessions
- **For Review**: Use "Has Warnings" to find sessions needing attention

### Filter Examples

**Example 1: Find only reliable test data**
```
Filter: High Quality Only
Result: 15 sessions
All sessions have > 95% usable detections
Suitable for ground truth validation
```

**Example 2: Find sessions needing attention**
```
Filter: Has Warnings
Result: 8 sessions
Sessions have quality concerns
Review recommended before using data
```

**Example 3: Exclude problematic sessions**
```
Filter: Medium or Better
Result: 23 sessions
Excludes sessions with > 25% quality issues
Good baseline for analysis
```

---

## Reading the Quality Dashboard

The Quality Metrics Dashboard provides a system-wide view of test quality.

### Dashboard Sections

#### 1. Overall Quality Summary

Shows the big picture of your test quality:

```
┌─────────────────────────────────────┐
│   Overall Quality Summary           │
├─────────────────────────────────────┤
│ Total Sessions: 50                  │
│ High Quality: 35 (70%) ✅           │
│ Medium Quality: 10 (20%) ⚠️         │
│ Low Quality: 5 (10%) ❌             │
│                                     │
│ Average Usability: 87.5%            │
│ Sessions with Warnings: 15 (30%)    │
└─────────────────────────────────────┘
```

**What to look at**:
- **High Quality %**: Should be > 70%
- **Low Quality %**: Should be < 10%
- **Average Usability**: Should be > 85%
- **Sessions with Warnings**: Should be < 30%

---

#### 2. Quality Trends

Shows how quality changes over time:

```
Quality Trend (Last 30 Days)
100% ┤    ╭─╮      ╭──╮
 90% ┤  ╭─╯ ╰──╮   │  ╰─╮
 80% ┤╭─╯      ╰───╯    ╰─╮
 70% ┼╯                   ╰──
     └──────────────────────────
     Nov 1          Nov 15   Nov 30
```

**What to look at**:
- **Upward trend**: Quality is improving ✅
- **Downward trend**: Quality is degrading ⚠️
- **Stable trend**: Quality is consistent ✅
- **Sudden drop**: Investigate immediately ❌

---

#### 3. Warning Distribution

Shows the types of warnings occurring:

```
┌────────────────────────────┐
│  Warning Type Distribution │
├────────────────────────────┤
│ Timing Degraded:    45%    │
│ Low Confidence:     30%    │
│ Detection Gaps:     20%    │
│ Validation Failure:  5%    │
└────────────────────────────┘
```

**What to do**:
- **Timing Degraded dominates**: Check timing sync
- **Low Confidence high**: Improve test conditions
- **Detection Gaps increasing**: Review algorithms
- **Validation Failures**: Check ground truth

---

#### 4. Session Quality Details

Shows individual session quality:

```
Recent Sessions
┌──────────────┬─────────┬──────────┬──────────┐
│ Session      │ Quality │ Usable   │ Warnings │
├──────────────┼─────────┼──────────┼──────────┤
│ test_001     │ High ✅  │ 98/100   │ None     │
│ test_002     │ Medium⚠️│ 85/100   │ Timing   │
│ test_003     │ Low ❌   │ 45/100   │ Multiple │
│ test_004     │ High ✅  │ 97/100   │ None     │
└──────────────┴─────────┴──────────┴──────────┘
```

---

## When to Be Concerned

### Green Flags ✅ (All Good)

- Quality Level: High
- Usable Detections: > 95%
- No warnings
- Consistent quality across sessions
- Quality trend is stable or improving

**Action**: None needed. Continue normal operations.

---

### Yellow Flags ⚠️ (Monitor)

- Quality Level: Medium
- Usable Detections: 75-95%
- Some timing warnings
- Occasional quality dips
- Quality trend is slightly declining

**Action**:
1. Monitor the situation
2. Review warnings to identify patterns
3. Consider preventive measures
4. Document any environmental changes

---

### Red Flags ❌ (Take Action)

- Quality Level: Low
- Usable Detections: < 75%
- Multiple critical warnings
- Quality consistently declining
- Validation failures increasing

**Action**:
1. **STOP** using data for validation
2. Investigate root cause immediately
3. Check hardware connections
4. Review system logs
5. Contact support if needed
6. Re-run affected tests

---

## Best Practices

### Before Running Tests

1. **Verify System Health**
   ```
   ✓ Check all hardware connections
   ✓ Verify network stability
   ✓ Ensure adequate lighting
   ✓ Clean camera lenses
   ✓ Check available disk space
   ```

2. **Establish Baseline**
   ```
   ✓ Run a calibration test
   ✓ Verify timing synchronization
   ✓ Check detection accuracy
   ✓ Document test environment
   ```

---

### During Testing

1. **Monitor Real-Time Quality**
   ```
   ✓ Watch for warning notifications
   ✓ Check detection counts
   ✓ Monitor timing accuracy
   ✓ Observe system performance
   ```

2. **Document Issues**
   ```
   ✓ Note any environmental changes
   ✓ Record warning messages
   ✓ Take screenshots if needed
   ✓ Log timestamps of issues
   ```

---

### After Testing

1. **Review Quality Metrics**
   ```
   ✓ Check overall quality level
   ✓ Review all warnings
   ✓ Verify usable detection count
   ✓ Compare to baseline
   ```

2. **Validate Results**
   ```
   ✓ Only use High Quality data for validation
   ✓ Re-run Medium Quality sessions if critical
   ✓ Discard Low Quality data
   ✓ Document quality issues
   ```

3. **Trend Analysis**
   ```
   ✓ Compare to previous sessions
   ✓ Look for degradation patterns
   ✓ Identify improvement opportunities
   ✓ Update procedures if needed
   ```

---

### Data Usage Guidelines

**For Ground Truth Validation**:
- ✅ Use: High Quality sessions only
- ⚠️ Caution: Medium Quality (review warnings first)
- ❌ Avoid: Low Quality sessions

**For Algorithm Training**:
- ✅ Use: High and Medium Quality sessions
- ⚠️ Caution: Review and clean data first
- ❌ Avoid: Sessions with validation failures

**For Performance Testing**:
- ✅ Use: All quality levels (document quality)
- ⚠️ Caution: Note quality issues in reports
- ❌ Avoid: Using without quality context

---

## Troubleshooting Common Issues

### Issue: Consistent Low Quality Sessions

**Symptoms**: Most sessions are marked as Low Quality

**Possible Causes**:
1. Hardware not properly calibrated
2. Network latency too high
3. System resource constraints
4. Environmental issues (lighting, etc.)

**Solutions**:
```
Step 1: Run system diagnostics
  - Check CPU/memory usage
  - Verify network speed
  - Test hardware connections

Step 2: Check calibration
  - Re-calibrate timing sync
  - Verify sensor settings
  - Update ground truth data

Step 3: Improve environment
  - Optimize lighting
  - Reduce network load
  - Clear disk space
```

---

### Issue: Timing Warnings on All Sessions

**Symptoms**: Every session has timing degraded warnings

**Possible Causes**:
1. System clock drift
2. Network jitter
3. Processing delays
4. Synchronization misconfiguration

**Solutions**:
```
Step 1: Check system time
  - Verify system clock is accurate
  - Enable NTP synchronization
  - Check for clock drift

Step 2: Network optimization
  - Use wired connection
  - Reduce network traffic
  - Check for packet loss

Step 3: Timing configuration
  - Review timing tolerance settings
  - Adjust synchronization parameters
  - Update timing calibration
```

---

### Issue: False Quality Warnings

**Symptoms**: Warnings appear but data seems fine

**Possible Causes**:
1. Thresholds too strict
2. Incorrect baseline data
3. Algorithm sensitivity too high
4. Environmental changes not accounted for

**Solutions**:
```
Step 1: Review thresholds
  - Check ALERT_DEGRADATION_THRESHOLD
  - Verify ALERT_VALIDATION_THRESHOLD
  - Adjust if too strict

Step 2: Update baseline
  - Re-run calibration
  - Update expected values
  - Document new baselines

Step 3: Fine-tune sensitivity
  - Adjust detection confidence
  - Review validation criteria
  - Update quality parameters
```

---

## Frequently Asked Questions

### General Questions

**Q: What happens if I ignore quality warnings?**

A: You risk using unreliable data for validation, which can lead to:
- False positive/negative results
- Inaccurate algorithm performance metrics
- Invalid ground truth data
- Wasted time debugging algorithm issues that are actually data quality problems

**Recommendation**: Always address quality warnings before using data for critical validation.

---

**Q: Can I still use Medium Quality sessions?**

A: Yes, with caution:
- Review the specific warnings
- Understand the impact on your use case
- Document the quality issues
- Consider re-running if the data is critical
- Do NOT use for ground truth validation without review

---

**Q: How often should I check the Quality Dashboard?**

A: It depends on your workflow:
- **Daily**: For active testing environments
- **Weekly**: For stable production systems
- **After each test run**: For critical validation work
- **When issues occur**: For troubleshooting

---

### Technical Questions

**Q: What's the difference between "timing_degraded" and "timing_verified"?**

A:
- **timing_degraded**: The timing data has quality issues (synchronization problems, latency, etc.)
- **timing_verified**: The timing data has been verified against ground truth and is confirmed accurate

A session can have `timing_verified = true` AND `timing_degraded = false` (best case) or `timing_verified = false` AND `timing_degraded = true` (worst case).

---

**Q: What does "usable for validation" mean?**

A: A detection is "usable for validation" if:
- Timing accuracy is within acceptable tolerance
- Detection confidence is above threshold
- Data has been properly synchronized
- No significant quality issues detected

Detections marked as NOT usable should not be used for ground truth validation.

---

**Q: Can I customize the quality thresholds?**

A: Yes, administrators can adjust thresholds in the configuration:

```bash
# In .env file
ALERT_DEGRADATION_THRESHOLD=25.0  # % degraded detections
ALERT_VALIDATION_THRESHOLD=75.0   # % usable detections
ALERT_TIMING_THRESHOLD=50.0       # % timing issues
```

Contact your system administrator to adjust these values.

---

**Q: Why do some sessions have no quality data?**

A: Possible reasons:
1. Session created before quality tracking was deployed
2. Quality analysis failed due to errors
3. Session is still processing
4. Database migration not applied

Contact support if quality data is missing for new sessions.

---

**Q: How is quality level calculated?**

A: Quality level is determined by:

```python
# High Quality
if usable_percentage > 95% and degraded_percentage < 5%:
    quality_level = "high"

# Low Quality
elif usable_percentage < 75% or degraded_percentage > 25%:
    quality_level = "low"

# Medium Quality
else:
    quality_level = "medium"
```

---

### Workflow Questions

**Q: Should I re-run all Low Quality sessions?**

A: It depends:
- **Yes, if**: The data is needed for validation or critical analysis
- **No, if**: The session was for testing/debugging only
- **Maybe**: If you can identify and fix the root cause first

---

**Q: Can I export quality metrics for reporting?**

A: Yes, quality metrics are available via API:

```bash
# Get session quality
GET /api/test-sessions/{session_id}
# Response includes "quality" field

# Get global metrics
GET /api/monitoring/metrics/global
# Response includes quality statistics
```

You can integrate this data into your reporting tools.

---

**Q: What should I do if quality suddenly degrades?**

A: Follow this checklist:

1. **Immediate**:
   - Stop using affected data
   - Check system health
   - Review recent changes

2. **Investigation**:
   - Compare to baseline
   - Check hardware connections
   - Review system logs
   - Identify pattern/timing

3. **Resolution**:
   - Fix identified issues
   - Re-run calibration
   - Verify improvement
   - Document incident

4. **Prevention**:
   - Update procedures
   - Add monitoring
   - Train team
   - Document lessons learned

---

## Getting Help

### Self-Service Resources

- **Configuration Guide**: `/docs/CONFIGURATION_GUIDE.md`
- **API Documentation**: `/docs/API_QUALITY_ENDPOINTS.md`
- **Deployment Guide**: `/docs/FINAL_DEPLOYMENT_GUIDE.md`
- **Architecture Docs**: `/docs/ARCHITECTURE_QUALITY_TRACKING.md`

### Contact Support

**For Quality Issues**:
- Email: quality-support@yourcompany.com
- Slack: #quality-tracking
- Ticket System: Create ticket with tag "quality"

**Include in Support Request**:
1. Session ID with quality issues
2. Screenshots of warnings
3. Quality Dashboard metrics
4. Recent changes to test environment
5. Steps to reproduce (if applicable)

---

**User Guide Version**: 1.0.0
**Last Updated**: 2025-11-19
**Next Review**: 2026-01-19
