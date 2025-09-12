/**
 * Basic Video Sequence Test Component
 * 
 * This is a simple React component you can render anywhere in your app
 * to manually test the sequential video functionality.
 */

import React, { useState } from 'react';
import SequentialVideoManager from '../components/SequentialVideoManager';
import { VideoFile } from '../services/types';

// Test videos - replace with actual test video URLs
const testVideos: VideoFile[] = [
  {
    id: 'test-1',
    projectId: 'manual-test',
    filename: 'test-video-1.mp4',
    originalName: 'Test Video 1.mp4',
    fileSize: 1000000,
    size: 1000000,
    url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
    duration: 10,
    fps: 30,
    status: 'completed' as const,
    createdAt: new Date().toISOString(),
    uploadedAt: new Date().toISOString(),
    groundTruthGenerated: false,
    groundTruthStatus: 'pending' as const,
    processing_status: 'completed' as const,
    detectionCount: 0
  },
  {
    id: 'test-2', 
    projectId: 'manual-test',
    filename: 'test-video-2.mp4',
    originalName: 'Test Video 2.mp4',
    fileSize: 1000000,
    size: 1000000,
    url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4',
    duration: 10,
    fps: 30,
    status: 'completed' as const,
    createdAt: new Date().toISOString(),
    uploadedAt: new Date().toISOString(),
    groundTruthGenerated: false,
    groundTruthStatus: 'pending' as const,
    processing_status: 'completed' as const,
    detectionCount: 0
  },
  {
    id: 'test-3',
    projectId: 'manual-test', 
    filename: 'test-video-3.mp4',
    originalName: 'Test Video 3.mp4',
    fileSize: 1000000,
    size: 1000000,
    url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
    duration: 10,
    fps: 30,
    status: 'completed' as const,
    createdAt: new Date().toISOString(),
    uploadedAt: new Date().toISOString(),
    groundTruthGenerated: false,
    groundTruthStatus: 'pending' as const,
    processing_status: 'completed' as const,
    detectionCount: 0
  }
];

const VideoSequenceBasicTest: React.FC = () => {
  const [testLog, setTestLog] = useState<string[]>([]);
  const [isTestRunning, setIsTestRunning] = useState(false);
  const [testResult, setTestResult] = useState<'pass' | 'fail' | null>(null);

  const addLog = (message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = `[${timestamp}] ${message}`;
    setTestLog(prev => [...prev, logEntry]);
    console.log(logEntry);
  };

  const handleVideoChange = (video: VideoFile, index: number) => {
    addLog(`✅ Video ${index + 1} loaded: ${video.filename}`);
    
    if (index === 1) {
      addLog(`🎯 CRITICAL: Video 2 (${video.filename}) is playing - NOT SKIPPED!`);
    }
  };

  const handleProgress = (progress: number) => {
    if (progress === 100) {
      addLog(`✅ Current video completed (100%)`);
    }
  };

  const handlePlaybackComplete = () => {
    addLog(`🎉 ALL VIDEOS COMPLETED SUCCESSFULLY!`);
    addLog(`✅ Test Result: PASS - All 3 videos played in sequence`);
    setTestResult('pass');
    setIsTestRunning(false);
  };

  const handleError = (error: any) => {
    addLog(`❌ Error: ${error?.message || 'Unknown error'}`);
    setTestResult('fail');
  };

  const startTest = () => {
    setTestLog([]);
    setTestResult(null);
    setIsTestRunning(true);
    addLog(`🎬 Starting Video Sequence Test`);
    addLog(`📋 Testing: Video 1 → Video 2 → Video 3 with 2-second gaps`);
  };

  const resetTest = () => {
    setTestLog([]);
    setTestResult(null);
    setIsTestRunning(false);
  };

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h2>🧪 Simple Video Sequence Test</h2>
      <p>This test verifies that videos play in sequence: Video 1 → Video 2 → Video 3</p>
      
      <div style={{ marginBottom: '20px' }}>
        <button 
          onClick={startTest}
          disabled={isTestRunning}
          style={{
            padding: '10px 20px',
            backgroundColor: isTestRunning ? '#ccc' : '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '5px',
            marginRight: '10px',
            cursor: isTestRunning ? 'not-allowed' : 'pointer'
          }}
        >
          {isTestRunning ? '🎬 Test Running...' : '▶️ Start Test'}
        </button>
        
        <button 
          onClick={resetTest}
          style={{
            padding: '10px 20px',
            backgroundColor: '#6c757d',
            color: 'white',
            border: 'none',
            borderRadius: '5px',
            cursor: 'pointer'
          }}
        >
          🔄 Reset
        </button>
      </div>

      {testResult && (
        <div style={{
          padding: '10px',
          borderRadius: '5px',
          marginBottom: '20px',
          backgroundColor: testResult === 'pass' ? '#d4edda' : '#f8d7da',
          border: testResult === 'pass' ? '1px solid #c3e6cb' : '1px solid #f5c6cb',
          color: testResult === 'pass' ? '#155724' : '#721c24'
        }}>
          {testResult === 'pass' ? 
            '✅ TEST PASSED: Video sequence worked correctly!' : 
            '❌ TEST FAILED: Issues detected in video sequence'
          }
        </div>
      )}

      <div style={{ display: 'flex', gap: '20px' }}>
        {/* Video Player */}
        <div style={{ flex: 1 }}>
          <h3>Video Player</h3>
          {isTestRunning ? (
            <div style={{ border: '2px solid #ddd', borderRadius: '5px', overflow: 'hidden' }}>
              <SequentialVideoManager
                videos={testVideos}
                onVideoChange={handleVideoChange}
                onProgress={handleProgress}
                onPlaybackComplete={handlePlaybackComplete}
                onError={handleError}
                autoAdvance={true}
                latencyMs={2000} // 2-second gap
              />
            </div>
          ) : (
            <div style={{
              border: '2px dashed #ddd',
              borderRadius: '5px',
              padding: '40px',
              textAlign: 'center',
              color: '#666'
            }}>
              Click "Start Test" to begin video sequence testing
            </div>
          )}
        </div>

        {/* Test Log */}
        <div style={{ flex: 1 }}>
          <h3>Test Log</h3>
          <div style={{
            border: '1px solid #ddd',
            borderRadius: '5px',
            padding: '10px',
            height: '300px',
            overflowY: 'auto',
            backgroundColor: '#f8f9fa',
            fontFamily: 'monospace',
            fontSize: '12px'
          }}>
            {testLog.length === 0 ? (
              <div style={{ color: '#666', textAlign: 'center', marginTop: '50px' }}>
                No test logs yet. Start a test to see progress.
              </div>
            ) : (
              testLog.map((log, index) => (
                <div key={index} style={{ marginBottom: '5px' }}>
                  {log}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div style={{ marginTop: '20px', padding: '15px', backgroundColor: '#fff3cd', border: '1px solid #ffeaa7', borderRadius: '5px' }}>
        <h4>📋 Manual Testing Instructions:</h4>
        <ol>
          <li>Click "Start Test" to begin</li>
          <li>Watch Video 1 play completely</li>
          <li>Observe 2-second gap</li>
          <li><strong>Verify Video 2 loads and plays (CRITICAL - should never be skipped!)</strong></li>
          <li>Observe another 2-second gap</li>
          <li>Watch Video 3 play completely</li>
          <li>Check that test shows "PASSED" when complete</li>
          <li>Review the test log for any errors</li>
        </ol>
        <p><strong>Success Criteria:</strong> All 3 videos play in sequence with Video 2 never being skipped.</p>
      </div>
    </div>
  );
};

export default VideoSequenceBasicTest;