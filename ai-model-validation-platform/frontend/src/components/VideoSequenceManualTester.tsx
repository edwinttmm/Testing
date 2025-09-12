/**
 * Manual Video Sequence Tester Component
 * 
 * This component provides a simple interface for manually testing
 * the video sequence functionality with real user interaction.
 */

import React, { useState, useRef } from 'react';
import SequentialVideoManager from './SequentialVideoManager';
import { VideoFile } from '../services/types';

// Test video data (you can replace these URLs with real test videos)
const manualTestVideos: VideoFile[] = [
  {
    id: 'manual-test-1',
    filename: 'test-video-1.mp4',
    originalName: 'Test Video 1.mp4', 
    url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
    projectId: 'manual-test',
    status: 'completed',
    duration: 10,
    fps: 30,
    size: 5000000,
    fileSize: 5000000,
    processingStatus: 'completed',
    annotationCount: 0,
    createdAt: new Date().toISOString(),
    uploadedAt: new Date().toISOString(),
    groundTruthGenerated: false,
    groundTruthStatus: 'pending',
    processing_status: 'completed',
    detectionCount: 0
  },
  {
    id: 'manual-test-2',
    filename: 'test-video-2.mp4',
    originalName: 'Test Video 2.mp4',
    url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4',
    projectId: 'manual-test',
    status: 'completed',
    duration: 10,
    fps: 30,
    size: 5000000,
    fileSize: 5000000,
    processingStatus: 'completed',
    annotationCount: 0,
    createdAt: new Date().toISOString(),
    uploadedAt: new Date().toISOString(),
    groundTruthGenerated: false,
    groundTruthStatus: 'pending',
    processing_status: 'completed',
    detectionCount: 0
  },
  {
    id: 'manual-test-3',
    filename: 'test-video-3.mp4',
    originalName: 'Test Video 3.mp4',
    url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
    projectId: 'manual-test',
    status: 'completed',
    duration: 10,
    fps: 30,
    size: 5000000,
    fileSize: 5000000,
    createdAt: new Date().toISOString(),
    uploadedAt: new Date().toISOString(),
    groundTruthGenerated: false,
    groundTruthStatus: 'pending',
    processing_status: 'completed',
    detectionCount: 0
  }
];

interface TestLog {
  timestamp: string;
  event: string;
  video: string;
  status: 'success' | 'warning' | 'error' | 'info';
}

const VideoSequenceManualTester: React.FC = () => {
  const [isTestRunning, setIsTestRunning] = useState(false);
  const [testLogs, setTestLogs] = useState<TestLog[]>([]);
  const [currentVideoIndex, setCurrentVideoIndex] = useState<number | null>(null);
  const [testPassed, setTestPassed] = useState<boolean | null>(null);
  const [gapDuration, setGapDuration] = useState(2000); // 2 seconds default
  const logEndRef = useRef<HTMLDivElement>(null);

  const addLog = (event: string, video: string, status: TestLog['status'] = 'info') => {
    const newLog: TestLog = {
      timestamp: new Date().toLocaleTimeString(),
      event,
      video,
      status
    };
    
    setTestLogs(prev => [...prev, newLog]);
    console.log(`[MANUAL TEST] ${event} - ${video}`);
    
    // Auto-scroll to bottom
    setTimeout(() => {
      logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 100);
  };

  const handleVideoChange = (video: VideoFile, index: number) => {
    setCurrentVideoIndex(index);
    
    if (index === 1) {
      addLog('Video 2 loaded successfully', video.filename, 'success');
      addLog('✅ CRITICAL: Video 2 was NOT skipped!', video.filename, 'success');
    } else {
      addLog(`Video ${index + 1} loaded`, video.filename, 'info');
    }
  };

  const handleProgress = (progress: number) => {
    if (progress === 100 && currentVideoIndex !== null) {
      const videoName = manualTestVideos[currentVideoIndex]?.filename || 'Unknown';
      addLog(`Video ${currentVideoIndex + 1} completed (100%)`, videoName, 'success');
      
      if (currentVideoIndex < manualTestVideos.length - 1) {
        addLog(`Starting ${gapDuration/1000}-second gap before next video...`, '', 'info');
      }
    }
  };

  const handlePlaybackComplete = () => {
    addLog('🎉 All videos completed successfully!', 'Full sequence', 'success');
    setTestPassed(true);
    setIsTestRunning(false);
  };

  const handleError = (error: any) => {
    addLog(`❌ Error occurred: ${error.message}`, 'System', 'error');
    setTestPassed(false);
  };

  const startTest = () => {
    setIsTestRunning(true);
    setTestLogs([]);
    setCurrentVideoIndex(null);
    setTestPassed(null);
    addLog('🎬 Starting manual video sequence test', 'System', 'info');
    addLog(`Gap duration: ${gapDuration/1000} seconds`, 'Settings', 'info');
  };

  const resetTest = () => {
    setIsTestRunning(false);
    setTestLogs([]);
    setCurrentVideoIndex(null);
    setTestPassed(null);
  };

  const getStatusColor = (status: TestLog['status']) => {
    switch (status) {
      case 'success': return 'text-green-600';
      case 'warning': return 'text-yellow-600';
      case 'error': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  const getStatusIcon = (status: TestLog['status']) => {
    switch (status) {
      case 'success': return '✅';
      case 'warning': return '⚠️';
      case 'error': return '❌';
      default: return 'ℹ️';
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          🧪 Video Sequence Manual Tester
        </h1>
        <p className="text-gray-600">
          Test the sequential video playback system: Video 1 → Video 2 → Video 3
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Video Player Section */}
        <div className="space-y-4">
          <div className="bg-white rounded-lg shadow-lg p-4">
            <h2 className="text-xl font-semibold mb-4">Video Player</h2>
            
            {/* Controls */}
            <div className="mb-4 space-y-3">
              <div className="flex items-center space-x-4">
                <label className="text-sm font-medium">Gap Duration:</label>
                <select
                  value={gapDuration}
                  onChange={(e) => setGapDuration(Number(e.target.value))}
                  disabled={isTestRunning}
                  className="border rounded px-2 py-1"
                >
                  <option value={1000}>1 second</option>
                  <option value={2000}>2 seconds</option>
                  <option value={3000}>3 seconds</option>
                  <option value={5000}>5 seconds</option>
                </select>
              </div>
              
              <div className="flex space-x-2">
                <button
                  onClick={startTest}
                  disabled={isTestRunning}
                  className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
                >
                  {isTestRunning ? '🎬 Test Running...' : '▶️ Start Test'}
                </button>
                
                <button
                  onClick={resetTest}
                  className="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
                >
                  🔄 Reset
                </button>
              </div>
            </div>

            {/* Test Result Badge */}
            {testPassed !== null && (
              <div className={`mb-4 p-3 rounded-lg ${
                testPassed 
                  ? 'bg-green-100 border border-green-300 text-green-800' 
                  : 'bg-red-100 border border-red-300 text-red-800'
              }`}>
                {testPassed ? '✅ TEST PASSED: All videos played correctly!' : '❌ TEST FAILED: Check logs for issues'}
              </div>
            )}

            {/* Video Manager */}
            {isTestRunning && (
              <div className="border-2 border-gray-300 rounded-lg overflow-hidden">
                <SequentialVideoManager
                  videos={manualTestVideos}
                  onVideoChange={handleVideoChange}
                  onProgress={handleProgress}
                  onPlaybackComplete={handlePlaybackComplete}
                  onError={handleError}
                  autoAdvance={true}
                  latencyMs={gapDuration}
                />
              </div>
            )}

            {!isTestRunning && testLogs.length === 0 && (
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center text-gray-500">
                Click "Start Test" to begin video sequence testing
              </div>
            )}
          </div>
        </div>

        {/* Test Log Section */}
        <div className="space-y-4">
          <div className="bg-white rounded-lg shadow-lg p-4">
            <h2 className="text-xl font-semibold mb-4">Test Log</h2>
            
            {/* Test Instructions */}
            <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <h3 className="font-semibold text-blue-800 mb-2">What to Watch For:</h3>
              <ul className="text-sm text-blue-700 space-y-1">
                <li>• Video 1 should play completely</li>
                <li>• {gapDuration/1000}-second gap should occur</li>
                <li>• <strong>Video 2 should load and play (NEVER skip!)</strong></li>
                <li>• Another {gapDuration/1000}-second gap should occur</li>
                <li>• Video 3 should load and play completely</li>
                <li>• Test should show "PASSED" when complete</li>
              </ul>
            </div>

            {/* Log Display */}
            <div className="h-64 overflow-y-auto border border-gray-300 rounded p-3 bg-gray-50">
              {testLogs.length === 0 ? (
                <p className="text-gray-500 text-center">No test logs yet. Start a test to see progress.</p>
              ) : (
                <div className="space-y-2">
                  {testLogs.map((log, index) => (
                    <div key={index} className="flex items-start space-x-2 text-sm">
                      <span>{getStatusIcon(log.status)}</span>
                      <span className="text-gray-500 font-mono">{log.timestamp}</span>
                      <span className={getStatusColor(log.status)}>{log.event}</span>
                      {log.video && <span className="text-gray-400">({log.video})</span>}
                    </div>
                  ))}
                  <div ref={logEndRef} />
                </div>
              )}
            </div>
          </div>

          {/* Current Status */}
          <div className="bg-white rounded-lg shadow-lg p-4">
            <h3 className="text-lg font-semibold mb-3">Current Status</h3>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span>Test Running:</span>
                <span className={isTestRunning ? 'text-green-600' : 'text-gray-500'}>
                  {isTestRunning ? '✅ Yes' : '⏸️ No'}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Current Video:</span>
                <span>
                  {currentVideoIndex !== null 
                    ? `Video ${currentVideoIndex + 1} of 3` 
                    : 'None'
                  }
                </span>
              </div>
              <div className="flex justify-between">
                <span>Gap Duration:</span>
                <span>{gapDuration/1000} seconds</span>
              </div>
              <div className="flex justify-between">
                <span>Test Result:</span>
                <span>
                  {testPassed === null ? '⏳ In Progress' : 
                   testPassed ? '✅ Passed' : '❌ Failed'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Manual Testing Instructions */}
      <div className="mt-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <h3 className="font-semibold text-yellow-800 mb-2">📋 Manual Testing Instructions</h3>
        <div className="text-sm text-yellow-700">
          <p className="mb-2"><strong>Step-by-Step Testing:</strong></p>
          <ol className="list-decimal list-inside space-y-1">
            <li>Choose your desired gap duration (default: 2 seconds)</li>
            <li>Click "Start Test" to begin the sequence</li>
            <li>Watch Video 1 play completely</li>
            <li>Observe the gap between videos</li>
            <li><strong>Verify Video 2 loads and plays (this is critical!)</strong></li>
            <li>Observe another gap</li>
            <li>Watch Video 3 play completely</li>
            <li>Check that the test shows "PASSED" when complete</li>
            <li>Review the test log for any errors or warnings</li>
          </ol>
          <p className="mt-2"><strong>Key Success Criteria:</strong> Video 2 must never be skipped!</p>
        </div>
      </div>
    </div>
  );
};

export default VideoSequenceManualTester;