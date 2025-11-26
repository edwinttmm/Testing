#!/usr/bin/env node

/**
 * Verification Script for Duplicate Detection Fix
 *
 * This script helps verify that the deduplication fixes are working correctly.
 * Run this in the browser console when viewing HIL Results page.
 */

console.log('🔍 Starting Duplicate Detection Verification...\n');

// Function to check for duplicates in an array
function findDuplicates(arr, idField = 'id') {
  const seen = new Map();
  const duplicates = [];

  arr.forEach((item, index) => {
    const id = item?.[idField] ?? item?.event_id ?? item?.detection_id;
    if (!id) {
      console.warn(`⚠️ Item at index ${index} has no ID`);
      return;
    }

    if (seen.has(id)) {
      duplicates.push({
        id,
        firstIndex: seen.get(id),
        duplicateIndex: index,
        item
      });
    } else {
      seen.set(id, index);
    }
  });

  return duplicates;
}

// Function to analyze detection data
function analyzeDetections(detections, label = 'Detections') {
  console.log(`\n📊 Analyzing ${label}:`);
  console.log(`   Total count: ${detections.length}`);

  if (detections.length === 0) {
    console.log('   ✅ No detections to analyze');
    return;
  }

  // Check for duplicates
  const duplicates = findDuplicates(detections);

  if (duplicates.length === 0) {
    console.log('   ✅ No duplicates found!');
  } else {
    console.error(`   ❌ Found ${duplicates.length} duplicates:`);
    duplicates.forEach(dup => {
      console.error(`      - ID: ${dup.id}`);
      console.error(`        First at index ${dup.firstIndex}`);
      console.error(`        Duplicate at index ${dup.duplicateIndex}`);
      console.error(`        Latency: ${dup.item?.actual_latency_ms ?? dup.item?.latency_ms ?? 'N/A'}ms`);
      console.error(`        Frame: ${dup.item?.frame_number ?? dup.item?.frameNumber ?? 'N/A'}`);
    });
  }

  // Check ID uniqueness
  const ids = detections.map(d => d?.id ?? d?.event_id ?? d?.detection_id).filter(Boolean);
  const uniqueIds = new Set(ids);

  if (ids.length === uniqueIds.size) {
    console.log(`   ✅ All ${ids.length} IDs are unique`);
  } else {
    console.error(`   ❌ ID collision detected: ${ids.length} detections but only ${uniqueIds.size} unique IDs`);
  }

  // Analyze ID format
  const generatedIds = ids.filter(id => String(id).startsWith('detection-'));
  if (generatedIds.length > 0) {
    console.log(`   📝 ${generatedIds.length} generated IDs detected`);

    // Check for collision-resistant format
    const compositeIds = generatedIds.filter(id => (String(id).match(/-/g) || []).length >= 4);
    if (compositeIds.length === generatedIds.length) {
      console.log(`   ✅ All generated IDs use collision-resistant composite format`);
    } else {
      console.warn(`   ⚠️ ${generatedIds.length - compositeIds.length} IDs use old format (potential collisions)`);
    }
  }
}

// Function to verify specific problematic frames
function verifyProblematicFrames(detections) {
  console.log('\n🎯 Checking Previously Problematic Frames:');

  // Frame 1
  const frame1 = detections.filter(d =>
    (d?.frame_number === 1 || d?.frameNumber === 1) ||
    (d?.timestamp >= 0 && d?.timestamp < 0.1)
  );

  if (frame1.length > 0) {
    console.log(`\n   Frame 1: ${frame1.length} detection(s)`);
    const frame1Dups = findDuplicates(frame1);
    if (frame1Dups.length === 0) {
      console.log('   ✅ No duplicates in Frame 1');
    } else {
      console.error(`   ❌ Found ${frame1Dups.length} duplicates in Frame 1`);
      frame1Dups.forEach(dup => {
        console.error(`      - Latency: ${dup.item?.actual_latency_ms ?? dup.item?.latency_ms}ms`);
      });
    }
  }

  // Frame 5
  const frame5 = detections.filter(d =>
    (d?.frame_number === 5 || d?.frameNumber === 5) ||
    (d?.timestamp >= 0.15 && d?.timestamp < 0.25)
  );

  if (frame5.length > 0) {
    console.log(`\n   Frame 5: ${frame5.length} detection(s)`);
    const frame5Dups = findDuplicates(frame5);
    if (frame5Dups.length === 0) {
      console.log('   ✅ No duplicates in Frame 5');
    } else {
      console.error(`   ❌ Found ${frame5Dups.length} duplicates in Frame 5`);
      frame5Dups.forEach(dup => {
        console.error(`      - Latency: ${dup.item?.actual_latency_ms ?? dup.item?.latency_ms}ms`);
      });
    }
  }
}

// Main verification
console.log('📋 Instructions:');
console.log('   1. Open browser DevTools (F12)');
console.log('   2. Navigate to HIL Results page with a video sequence');
console.log('   3. Copy and paste this entire script into the console');
console.log('   4. Run: verifyHILResults()');
console.log('');

// Export verification function to global scope
window.verifyHILResults = function() {
  console.clear();
  console.log('🔍 HIL Results Deduplication Verification\n');
  console.log('═'.repeat(60));

  try {
    // Try to access React component state through window
    // Note: This may need adjustment based on actual React structure

    // Method 1: Check if detections are in window object
    const detections = window.__detections__ || [];

    if (detections.length === 0) {
      console.warn('⚠️ No detections found in window.__detections__');
      console.log('\n💡 Alternative methods:');
      console.log('   1. Add this to HILResults.tsx useEffect:');
      console.log('      window.__detections__ = allDetections;');
      console.log('   2. Or inspect React DevTools Components tab');
      return;
    }

    analyzeDetections(detections, 'All Detections');
    verifyProblematicFrames(detections);

    console.log('\n═'.repeat(60));
    console.log('✅ Verification complete!\n');

  } catch (error) {
    console.error('❌ Verification failed:', error);
    console.log('\n💡 To enable verification:');
    console.log('   1. Add to HILResults.tsx after allDetections useMemo:');
    console.log('      window.__detections__ = allDetections;');
    console.log('   2. Reload the page');
    console.log('   3. Run verifyHILResults() again');
  }
};

console.log('✅ Script loaded! Run: verifyHILResults()');
