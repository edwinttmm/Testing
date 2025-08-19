#!/usr/bin/env node

/**
 * Dashboard Real-time Updates Demo Script
 * 
 * This script demonstrates the real-time WebSocket functionality
 * implemented in the Dashboard component.
 * 
 * Usage: node dashboard-realtime-demo.js
 */

const { io } = require('socket.io-client');
const chalk = require('chalk');

// Configuration
const WS_URL = process.env.REACT_APP_WS_URL || 'ws://155.138.239.131:8000';
const DEMO_DURATION = 30000; // 30 seconds

console.log(chalk.blue.bold('🚀 Dashboard Real-time Updates Demo'));
console.log(chalk.gray(`Connecting to: ${WS_URL}`));
console.log(chalk.gray(`Demo duration: ${DEMO_DURATION / 1000} seconds`));
console.log('');

// Create WebSocket connection
const socket = io(WS_URL, {
  transports: ['websocket', 'polling'],
  timeout: 20000,
  reconnection: true,
  reconnectionAttempts: 5
});

// Track demo state
let eventCount = 0;
let demoStartTime = Date.now();

// Connection handlers
socket.on('connect', () => {
  console.log(chalk.green('✅ Connected to WebSocket server'));
  console.log(chalk.yellow('📡 Simulating Dashboard real-time events...'));
  console.log('');
  
  startDemo();
});

socket.on('connect_error', (error) => {
  console.log(chalk.red('❌ Connection failed:'), error.message);
  process.exit(1);
});

socket.on('disconnect', (reason) => {
  console.log(chalk.yellow('⚠️ Disconnected:'), reason);
});

// Demo simulation functions
function startDemo() {
  // Subscribe to dashboard events (as the real Dashboard does)
  socket.emit('subscribe_dashboard_updates', {
    clientId: 'dashboard-demo',
    events: [
      'video_uploaded', 'video_processed',
      'project_created', 'project_updated',
      'test_completed', 'test_session_completed',
      'test_started', 'test_session_started',
      'detection_event', 'detection_result',
      'signal_processed', 'signal_processing_result'
    ]
  });

  // Simulate various events that would trigger Dashboard updates
  setTimeout(() => simulateVideoUpload(), 2000);
  setTimeout(() => simulateProjectCreation(), 5000);
  setTimeout(() => simulateTestStart(), 8000);
  setTimeout(() => simulateDetectionEvent(), 12000);
  setTimeout(() => simulateSignalProcessing(), 15000);
  setTimeout(() => simulateTestCompletion(), 18000);
  setTimeout(() => simulateVideoProcessing(), 22000);
  setTimeout(() => simulateProjectUpdate(), 25000);
  
  // End demo
  setTimeout(() => endDemo(), DEMO_DURATION);
}

function simulateVideoUpload() {
  const videoData = {
    id: `video-${Date.now()}`,
    filename: 'demo-traffic-video.mp4',
    projectId: 'project-123',
    size: 15728640,
    status: 'completed'
  };
  
  console.log(chalk.cyan('📹 Simulating video upload event...'));
  socket.emit('video_uploaded', videoData);
  eventCount++;
}

function simulateProjectCreation() {
  const projectData = {
    id: `project-${Date.now()}`,
    name: 'Highway Surveillance Test',
    status: 'active',
    cameraModel: 'Sony IMX334',
    cameraView: 'Front-facing VRU'
  };
  
  console.log(chalk.cyan('📁 Simulating project creation event...'));
  socket.emit('project_created', projectData);
  eventCount++;
}

function simulateTestStart() {
  const testData = {
    id: `test-${Date.now()}`,
    name: 'Pedestrian Detection Test',
    projectId: 'project-123',
    status: 'running',
    startedAt: new Date().toISOString()
  };
  
  console.log(chalk.cyan('🚀 Simulating test start event...'));
  socket.emit('test_started', testData);
  eventCount++;
}

function simulateDetectionEvent() {
  const detectionData = {
    id: `detection-${Date.now()}`,
    testSessionId: 'test-123',
    detectionType: 'pedestrian',
    confidence: 0.92,
    timestamp: Date.now(),
    boundingBox: { x: 120, y: 80, width: 60, height: 140 }
  };
  
  console.log(chalk.cyan('🎯 Simulating detection event...'));
  socket.emit('detection_event', detectionData);
  eventCount++;
}

function simulateSignalProcessing() {
  const signalData = {
    id: `signal-${Date.now()}`,
    signalType: 'CAN_BUS',
    success: true,
    processingTime: 125,
    timestamp: new Date().toISOString()
  };
  
  console.log(chalk.cyan('📡 Simulating signal processing event...'));
  socket.emit('signal_processed', signalData);
  eventCount++;
}

function simulateTestCompletion() {
  const testCompletionData = {
    id: `test-${Date.now()}`,
    name: 'Pedestrian Detection Test',
    status: 'completed',
    completedAt: new Date().toISOString(),
    metrics: {
      accuracy: 89.5,
      precision: 87.2,
      recall: 91.8,
      f1Score: 89.4
    }
  };
  
  console.log(chalk.cyan('🧪 Simulating test completion event...'));
  socket.emit('test_completed', testCompletionData);
  eventCount++;
}

function simulateVideoProcessing() {
  const videoProcessingData = {
    id: `video-processing-${Date.now()}`,
    videoId: 'video-123',
    status: 'completed',
    detectionCount: 47,
    processingTime: 3500
  };
  
  console.log(chalk.cyan('⚙️ Simulating video processing event...'));
  socket.emit('video_processed', videoProcessingData);
  eventCount++;
}

function simulateProjectUpdate() {
  const projectUpdateData = {
    id: 'project-123',
    name: 'Updated Highway Surveillance Test',
    status: 'testing',
    updatedAt: new Date().toISOString()
  };
  
  console.log(chalk.cyan('📝 Simulating project update event...'));
  socket.emit('project_updated', projectUpdateData);
  eventCount++;
}

function endDemo() {
  const duration = Date.now() - demoStartTime;
  
  console.log('');
  console.log(chalk.green.bold('✅ Demo completed successfully!'));
  console.log(chalk.gray(`📊 Events simulated: ${eventCount}`));
  console.log(chalk.gray(`⏱️ Duration: ${duration}ms`));
  console.log('');
  console.log(chalk.blue('🎯 Real-time Dashboard Features Demonstrated:'));
  console.log(chalk.gray('  • WebSocket connection management'));
  console.log(chalk.gray('  • Live video upload tracking'));
  console.log(chalk.gray('  • Real-time project creation updates'));
  console.log(chalk.gray('  • Test session start/completion events'));
  console.log(chalk.gray('  • Detection event streaming'));
  console.log(chalk.gray('  • Signal processing monitoring'));
  console.log(chalk.gray('  • Connection status indicators'));
  console.log(chalk.gray('  • Live statistics updates'));
  console.log('');
  console.log(chalk.yellow('💡 To see these updates in the Dashboard:'));
  console.log(chalk.gray('  1. Start the frontend: npm start'));
  console.log(chalk.gray('  2. Navigate to Dashboard page'));
  console.log(chalk.gray('  3. Run this demo script in another terminal'));
  console.log(chalk.gray('  4. Watch real-time updates appear!'));
  
  // Cleanup
  socket.emit('unsubscribe_dashboard_updates', { clientId: 'dashboard-demo' });
  socket.disconnect();
  process.exit(0);
}

// Handle graceful shutdown
process.on('SIGINT', () => {
  console.log('\n');
  console.log(chalk.yellow('🛑 Demo interrupted by user'));
  endDemo();
});

process.on('SIGTERM', () => {
  console.log('\n');
  console.log(chalk.yellow('🛑 Demo terminated'));
  endDemo();
});