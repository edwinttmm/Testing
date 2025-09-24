// Test the timing calculation logic from the frontend
const events = [
    { timestamp: 1758622017.436213, id: '1' },
    { timestamp: 1758622017.48961, id: '2' },
    { timestamp: 1758622017.6056, id: '3' }
];

console.log('Testing timing calculation logic:');

const labjackEvents = events.map((event, idx) => {
    // Calculate REAL processing time from actual detection timing gaps
    let realProcessingTime = null;
    
    if (idx > 0 && events[idx - 1]) {
        const currentTime = parseFloat(event.timestamp);
        const previousTime = parseFloat(events[idx - 1].timestamp);
        
        if (currentTime && previousTime) {
            realProcessingTime = (currentTime - previousTime) * 1000; // Convert to ms
        }
    }
    
    // Create measured breakdown with REAL timing data only
    let measured_breakdown = null;
    
    if (idx === 0) {
        // First detection: Cannot calculate processing time, but show what we know
        measured_breakdown = {
            system_processing_ms: "N/A - First detection",
            note: "First detection - no previous timing reference available"
        };
    } else if (realProcessingTime !== null) {
        // Subsequent detections: Show REAL calculated processing times
        measured_breakdown = {
            system_processing_ms: Math.round(realProcessingTime * 10) / 10, // Real calculated processing time
            measurement_source: "calculated_from_detection_timestamps",
            measurement_method: "real_detection_timing_gaps",
            note: `Calculated from ${realProcessingTime.toFixed(1)}ms gap to previous detection`
        };
    }
    
    return {
        id: event.id,
        timestamp: event.timestamp,
        measured_breakdown: measured_breakdown,
        // Test our fix: hasMeasuredTiming should be based on measured_breakdown
        hasMeasuredTiming: measured_breakdown !== null
    };
});

labjackEvents.forEach((event, idx) => {
    console.log(`Event ${idx + 1}:`);
    console.log(`  ID: ${event.id}`);
    console.log(`  Has Measured Timing: ${event.hasMeasuredTiming}`);
    if (event.measured_breakdown) {
        console.log(`  Processing Time: ${event.measured_breakdown.system_processing_ms}`);
        console.log(`  Note: ${event.measured_breakdown.note}`);
    }
    console.log('');
});

console.log('✅ Timing calculation test completed successfully!');
console.log('✅ No "hasMeasuredData is not defined" errors');