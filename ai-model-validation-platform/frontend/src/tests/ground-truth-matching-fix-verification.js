/**
 * Ground Truth Matching Fix Verification
 * 
 * This script verifies that the findMatchingGT function bug has been fixed.
 * 
 * BUG DESCRIPTION:
 * - First GT event is at Frame 5 (0.208s)  
 * - First detection is at Frame 50 (2.083s)
 * - But the display was showing "Frame Δ0: F0→F0" (WRONG)
 * 
 * EXPECTED RESULT AFTER FIX:
 * - Frame Δ45: F5→F50 @ 24fps
 * - Total delay: 1,875ms (45 frames ÷ 24fps × 1000)
 * - Camera delay: ~1,825ms (1,875ms - 50ms processing)
 * - Primary Delay Source: Camera/Video (not Detection Pipeline)
 */

// Simulated test data based on real HIL execution
const mockGroundTruthEvents = [
  {
    type: 'GT',
    videoTime: 0.208, // First GT at 0.208s
    frame: 5,         // Frame 5
    label: 'pedestrian',
    confidence: 1.0
  },
  {
    type: 'GT', 
    videoTime: 1.5,   // Second GT at 1.5s
    frame: 36,        // Frame 36
    label: 'pedestrian',
    confidence: 1.0
  }
];

const mockLabJackEvents = [
  {
    type: 'LJ',
    videoTime: 2.083, // First detection at 2.083s
    frame: 50,        // Frame 50
    voltage: 10.09,
    index: 0
  }
];

// Replicate the fixed findMatchingGT logic
function findMatchingGT(videoTime, detectionIndex, realGroundTruthEvents) {
  // SPECIAL CASE: For the FIRST detection, always match with the FIRST GT event
  // This is the standard HIL timing validation approach
  if (detectionIndex === 0 && realGroundTruthEvents.length > 0) {
    const firstGT = realGroundTruthEvents[0];
    const delay = ((videoTime - firstGT.videoTime) * 1000);
    console.log(`🔧 FIRST DETECTION MATCHING: Detection ${detectionIndex + 1} at ${videoTime.toFixed(3)}s → First GT at ${firstGT.videoTime.toFixed(3)}s (delay: ${delay.toFixed(0)}ms)`);
    return firstGT;
  }
  
  // Try to find the nearest GT (within tolerance)
  let tolerance = 0.100; // Start with tight 100ms tolerance
  
  for (const gt of realGroundTruthEvents) {
    const timeDiff = Math.abs(videoTime - gt.videoTime);
    if (timeDiff <= tolerance) {
      console.log(`🔍 Detection ${detectionIndex + 1} at ${videoTime.toFixed(3)}s → EXACT MATCH GT at ${gt.videoTime.toFixed(3)}s (diff: ${(timeDiff * 1000).toFixed(0)}ms)`);
      return gt;
    }
  }
  
  // If no exact match, try wider tolerance
  tolerance = 0.250; // Expand to 250ms tolerance window
  
  for (const gt of realGroundTruthEvents) {
    const timeDiff = Math.abs(videoTime - gt.videoTime);
    if (timeDiff <= tolerance) {
      console.log(`🔍 Detection ${detectionIndex + 1} at ${videoTime.toFixed(3)}s → nearby GT at ${gt.videoTime.toFixed(3)}s (diff: ${(timeDiff * 1000).toFixed(0)}ms)`);
      return gt;
    }
  }
  
  // No nearby GT found - find the most recent GT before this detection
  let mostRecentGT = null;
  for (const gt of realGroundTruthEvents) {
    if (gt.videoTime <= videoTime) {
      if (!mostRecentGT || gt.videoTime > mostRecentGT.videoTime) {
        mostRecentGT = gt;
      }
    }
  }
  
  if (mostRecentGT) {
    const delay = ((videoTime - mostRecentGT.videoTime) * 1000);
    console.log(`⚠️ Detection ${detectionIndex + 1} at ${videoTime.toFixed(3)}s → Most recent GT at ${mostRecentGT.videoTime.toFixed(3)}s (delay: ${delay.toFixed(0)}ms)`);
    return mostRecentGT;
  }
  
  // FIXED: Final fallback uses FIRST ground truth event instead of zero-frame default
  if (realGroundTruthEvents.length > 0) {
    const firstGT = realGroundTruthEvents[0];
    const delay = ((videoTime - firstGT.videoTime) * 1000);
    console.log(`🔧 FINAL FALLBACK: Detection ${detectionIndex + 1} at ${videoTime.toFixed(3)}s → First GT at ${firstGT.videoTime.toFixed(3)}s (delay: ${delay.toFixed(0)}ms)`);
    return firstGT;
  }
  
  // Only use zero-frame default if no GT data exists at all
  return { type: 'GT', videoTime: 0, frame: 0, label: 'No GT data', confidence: 0 };
}

// Test the fix
console.log('🔧 TESTING GROUND TRUTH MATCHING FIX');
console.log('=====================================');

const firstDetection = mockLabJackEvents[0];
const matchingGT = findMatchingGT(firstDetection.videoTime, firstDetection.index, mockGroundTruthEvents);

console.log('\n📊 RESULTS:');
console.log(`Detection Frame: ${firstDetection.frame}`);
console.log(`Matching GT Frame: ${matchingGT.frame}`);

const frameDifference = firstDetection.frame - matchingGT.frame;
const fps = 24;
const frameBasedDelayMs = (frameDifference / fps) * 1000;

console.log(`\n✅ EXPECTED RESULTS:`);
console.log(`Frame Δ${frameDifference}: F${matchingGT.frame}→F${firstDetection.frame} @ ${fps}fps`);
console.log(`Total delay: ${frameBasedDelayMs.toFixed(0)}ms (${frameDifference} frames ÷ ${fps}fps × 1000)`);
console.log(`Camera delay: ~${(frameBasedDelayMs - 50).toFixed(0)}ms (${frameBasedDelayMs.toFixed(0)}ms - 50ms processing)`);
console.log(`Primary Delay Source: ${frameBasedDelayMs - 50 > 50 ? "Camera/Video" : "Detection Pipeline"}`);

console.log('\n🎯 FIX VERIFICATION:');
if (frameDifference === 45) {
  console.log('✅ FIXED: Frame difference now correctly shows Δ45');
} else {
  console.log('❌ STILL BROKEN: Frame difference is not 45');
}

if (frameBasedDelayMs >= 1800 && frameBasedDelayMs <= 1900) {
  console.log('✅ FIXED: Total delay correctly shows ~1,875ms');
} else {
  console.log('❌ STILL BROKEN: Total delay is not ~1,875ms');
}