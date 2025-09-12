# Frontend Integration Guide - Enhanced Test Workflow

## Overview

This guide provides complete frontend integration instructions for the Enhanced Test Workflow system that enables "click and walk away" automated testing.

## WebSocket Integration

### 1. WebSocket Connection Setup

```typescript
class EnhancedTestWebSocket {
    private ws: WebSocket;
    private workflowId: string;
    private onProgress: (data: WorkflowProgressEvent) => void;
    private onStatusUpdate: (data: WorkflowStatusEvent) => void;
    private onVideoProgress: (data: VideoProgressEvent) => void;
    private onError: (error: any) => void;

    constructor(workflowId: string, callbacks: {
        onProgress: (data: WorkflowProgressEvent) => void;
        onStatusUpdate: (data: WorkflowStatusEvent) => void;
        onVideoProgress: (data: VideoProgressEvent) => void;
        onError: (error: any) => void;
    }) {
        this.workflowId = workflowId;
        this.onProgress = callbacks.onProgress;
        this.onStatusUpdate = callbacks.onStatusUpdate;
        this.onVideoProgress = callbacks.onVideoProgress;
        this.onError = callbacks.onError;
        
        this.connect();
    }

    private connect() {
        const wsUrl = `ws://localhost:8000/api/enhanced-test/workflow/${this.workflowId}/ws`;
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log(`Connected to workflow ${this.workflowId}`);
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
        
        this.ws.onclose = () => {
            console.log(`Disconnected from workflow ${this.workflowId}`);
            // Implement reconnection logic if needed
        };
        
        this.ws.onerror = (error) => {
            this.onError(error);
        };
    }

    private handleMessage(data: any) {
        switch (data.type) {
            case 'workflow_progress':
                this.onProgress(data as WorkflowProgressEvent);
                break;
            case 'workflow_status':
                this.onStatusUpdate(data as WorkflowStatusEvent);
                break;
            case 'video_progress':
                this.onVideoProgress(data as VideoProgressEvent);
                break;
            case 'workflow_error':
                this.onError(data);
                break;
        }
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
    }
}
```

### 2. TypeScript Interfaces

```typescript
interface WorkflowProgressEvent {
    type: 'workflow_progress';
    workflow_id: string;
    progress: {
        total_videos: number;
        completed_videos: number;
        failed_videos: number;
        current_video?: string;
        current_video_progress: number;
        overall_progress: number;
        estimated_completion?: string;
    };
    timestamp: string;
}

interface WorkflowStatusEvent {
    type: 'workflow_status';
    workflow_id: string;
    status: 'initializing' | 'loading_videos' | 'processing_video' | 
             'running_detection' | 'comparing_results' | 'generating_report' |
             'completed' | 'failed' | 'cancelled';
    message?: string;
    timestamp: string;
}

interface VideoProgressEvent {
    type: 'video_progress';
    workflow_id: string;
    video_id: string;
    progress_percentage: number;
    message: string;
    timestamp: string;
}

interface StartWorkflowRequest {
    project_id: string;
    test_session_name: string;
    tolerance_ms?: number;
    parallel_processing?: boolean;
    max_parallel_videos?: number;
    retry_failed_videos?: boolean;
    max_retries?: number;
    timeout_per_video?: number;
    generate_individual_reports?: boolean;
    generate_aggregate_report?: boolean;
    include_visual_evidence?: boolean;
    continue_on_error?: boolean;
    fail_fast?: boolean;
}
```

## React Component Example

### 1. Enhanced Test Dashboard Component

```typescript
import React, { useState, useEffect, useRef } from 'react';
import { EnhancedTestWebSocket } from './EnhancedTestWebSocket';

interface Props {
    projectId: string;
}

export const EnhancedTestDashboard: React.FC<Props> = ({ projectId }) => {
    const [workflowId, setWorkflowId] = useState<string | null>(null);
    const [workflowStatus, setWorkflowStatus] = useState<string>('idle');
    const [overallProgress, setOverallProgress] = useState<number>(0);
    const [currentVideo, setCurrentVideo] = useState<string>('');
    const [videoProgress, setVideoProgress] = useState<number>(0);
    const [completedVideos, setCompletedVideos] = useState<number>(0);
    const [totalVideos, setTotalVideos] = useState<number>(0);
    const [statusMessage, setStatusMessage] = useState<string>('');
    const [isRunning, setIsRunning] = useState<boolean>(false);
    const [results, setResults] = useState<any>(null);
    
    const wsRef = useRef<EnhancedTestWebSocket | null>(null);

    const startTest = async () => {
        try {
            const request: StartWorkflowRequest = {
                project_id: projectId,
                test_session_name: `Test Session ${new Date().toISOString()}`,
                tolerance_ms: 100,
                retry_failed_videos: true,
                generate_individual_reports: true,
                generate_aggregate_report: true,
                continue_on_error: true
            };

            const response = await fetch('/api/enhanced-test/start-workflow', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(request)
            });

            const data = await response.json();
            
            if (response.ok) {
                setWorkflowId(data.workflow_id);
                setIsRunning(true);
                setWorkflowStatus('initializing');
                connectWebSocket(data.workflow_id);
            } else {
                alert(`Failed to start test: ${data.detail}`);
            }
        } catch (error) {
            console.error('Error starting test:', error);
            alert('Failed to start test');
        }
    };

    const connectWebSocket = (workflowId: string) => {
        wsRef.current = new EnhancedTestWebSocket(workflowId, {
            onProgress: (data) => {
                setOverallProgress(data.progress.overall_progress);
                setCompletedVideos(data.progress.completed_videos);
                setTotalVideos(data.progress.total_videos);
                setCurrentVideo(data.progress.current_video || '');
            },
            onStatusUpdate: (data) => {
                setWorkflowStatus(data.status);
                setStatusMessage(data.message || '');
                
                if (data.status === 'completed') {
                    setIsRunning(false);
                    loadResults(workflowId);
                } else if (data.status === 'failed') {
                    setIsRunning(false);
                    alert('Test workflow failed. Check the logs for details.');
                }
            },
            onVideoProgress: (data) => {
                setVideoProgress(data.progress_percentage);
                setStatusMessage(data.message);
            },
            onError: (error) => {
                console.error('WebSocket error:', error);
                setIsRunning(false);
            }
        });
    };

    const loadResults = async (workflowId: string) => {
        try {
            const response = await fetch(`/api/enhanced-test/workflow/${workflowId}/results`);
            const data = await response.json();
            setResults(data);
        } catch (error) {
            console.error('Error loading results:', error);
        }
    };

    const cancelTest = async () => {
        if (!workflowId) return;
        
        try {
            const response = await fetch(`/api/enhanced-test/workflow/${workflowId}/cancel`, {
                method: 'POST'
            });
            
            if (response.ok) {
                setIsRunning(false);
                setWorkflowStatus('cancelled');
            }
        } catch (error) {
            console.error('Error cancelling test:', error);
        }
    };

    const downloadReport = async (reportType: 'final' | 'individual') => {
        if (!workflowId) return;
        
        const url = `/api/enhanced-test/workflow/${workflowId}/report/download?report_type=${reportType}`;
        window.open(url, '_blank');
    };

    useEffect(() => {
        return () => {
            if (wsRef.current) {
                wsRef.current.disconnect();
            }
        };
    }, []);

    return (
        <div className="enhanced-test-dashboard">
            <div className="header">
                <h2>Enhanced Test Workflow</h2>
                <p>Project ID: {projectId}</p>
            </div>

            {!isRunning && !results && (
                <div className="start-section">
                    <button 
                        onClick={startTest} 
                        className="btn-primary btn-large"
                        disabled={isRunning}
                    >
                        🚀 Start Test
                    </button>
                    <p>Click to start automated testing of all project videos</p>
                </div>
            )}

            {isRunning && (
                <div className="progress-section">
                    <div className="status-bar">
                        <h3>Status: {workflowStatus.replace('_', ' ').toUpperCase()}</h3>
                        <p>{statusMessage}</p>
                        <button onClick={cancelTest} className="btn-danger">
                            Cancel Test
                        </button>
                    </div>

                    <div className="overall-progress">
                        <h4>Overall Progress: {overallProgress.toFixed(1)}%</h4>
                        <div className="progress-bar">
                            <div 
                                className="progress-fill" 
                                style={{ width: `${overallProgress}%` }}
                            ></div>
                        </div>
                        <p>{completedVideos} of {totalVideos} videos completed</p>
                    </div>

                    {currentVideo && (
                        <div className="current-video">
                            <h4>Current Video: {currentVideo}</h4>
                            <div className="progress-bar">
                                <div 
                                    className="progress-fill video-progress" 
                                    style={{ width: `${videoProgress}%` }}
                                ></div>
                            </div>
                            <p>{videoProgress.toFixed(1)}% complete</p>
                        </div>
                    )}
                </div>
            )}

            {results && (
                <div className="results-section">
                    <h3>Test Results</h3>
                    
                    <div className="summary-stats">
                        <div className="stat-card">
                            <h4>Total Videos</h4>
                            <p>{results.video_summary?.total_videos || 0}</p>
                        </div>
                        <div className="stat-card">
                            <h4>Success Rate</h4>
                            <p>{((results.video_summary?.success_rate || 0) * 100).toFixed(1)}%</p>
                        </div>
                        <div className="stat-card">
                            <h4>Overall F1 Score</h4>
                            <p>{(results.performance_metrics?.overall_f1_score || 0).toFixed(3)}</p>
                        </div>
                        <div className="stat-card">
                            <h4>Total Detections</h4>
                            <p>{results.detection_summary?.total_detections || 0}</p>
                        </div>
                    </div>

                    <div className="download-section">
                        <button 
                            onClick={() => downloadReport('final')} 
                            className="btn-primary"
                        >
                            📊 Download Final Report
                        </button>
                        <button 
                            onClick={() => downloadReport('individual')} 
                            className="btn-secondary"
                        >
                            📋 Download Individual Reports
                        </button>
                    </div>

                    <div className="video-results">
                        <h4>Individual Video Results</h4>
                        <table>
                            <thead>
                                <tr>
                                    <th>Video</th>
                                    <th>Status</th>
                                    <th>Precision</th>
                                    <th>Recall</th>
                                    <th>F1 Score</th>
                                    <th>Detections</th>
                                </tr>
                            </thead>
                            <tbody>
                                {Object.entries(results.individual_video_results || {}).map(([videoId, result]: [string, any]) => (
                                    <tr key={videoId}>
                                        <td>{result.filename}</td>
                                        <td className={`status-${result.status}`}>{result.status}</td>
                                        <td>{result.metrics?.precision?.toFixed(3) || 'N/A'}</td>
                                        <td>{result.metrics?.recall?.toFixed(3) || 'N/A'}</td>
                                        <td>{result.metrics?.f1_score?.toFixed(3) || 'N/A'}</td>
                                        <td>{result.metrics?.total_detections || 0}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
};
```

### 2. CSS Styles

```css
.enhanced-test-dashboard {
    padding: 20px;
    max-width: 1200px;
    margin: 0 auto;
}

.header {
    text-align: center;
    margin-bottom: 30px;
}

.start-section {
    text-align: center;
    padding: 40px;
    border: 2px dashed #ccc;
    border-radius: 10px;
}

.btn-primary {
    background: #007bff;
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 6px;
    font-size: 16px;
    cursor: pointer;
}

.btn-large {
    padding: 16px 32px;
    font-size: 18px;
}

.progress-section {
    margin: 20px 0;
}

.status-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 15px;
    background: #f8f9fa;
    border-radius: 6px;
    margin-bottom: 20px;
}

.progress-bar {
    width: 100%;
    height: 20px;
    background: #e9ecef;
    border-radius: 10px;
    overflow: hidden;
    margin: 10px 0;
}

.progress-fill {
    height: 100%;
    background: #007bff;
    transition: width 0.3s ease;
}

.video-progress {
    background: #28a745;
}

.current-video {
    background: #fff3cd;
    padding: 15px;
    border-radius: 6px;
    border: 1px solid #ffeaa7;
}

.results-section {
    margin-top: 30px;
}

.summary-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin: 20px 0;
}

.stat-card {
    background: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    text-align: center;
}

.stat-card h4 {
    margin: 0 0 10px 0;
    color: #666;
}

.stat-card p {
    margin: 0;
    font-size: 24px;
    font-weight: bold;
    color: #007bff;
}

.download-section {
    margin: 20px 0;
    text-align: center;
}

.download-section button {
    margin: 0 10px;
}

.video-results table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 20px;
}

.video-results th,
.video-results td {
    border: 1px solid #ddd;
    padding: 12px;
    text-align: left;
}

.video-results th {
    background: #f8f9fa;
    font-weight: bold;
}

.status-completed {
    color: #28a745;
    font-weight: bold;
}

.status-failed {
    color: #dc3545;
    font-weight: bold;
}
```

## API Usage Examples

### 1. Starting a Workflow

```typescript
const startWorkflow = async (projectId: string) => {
    const response = await fetch('/api/enhanced-test/start-workflow', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            project_id: projectId,
            test_session_name: "Automated Test " + new Date().toISOString(),
            tolerance_ms: 100,
            retry_failed_videos: true,
            generate_individual_reports: true,
            generate_aggregate_report: true
        })
    });
    
    return await response.json();
};
```

### 2. Getting Workflow Status

```typescript
const getWorkflowStatus = async (workflowId: string) => {
    const response = await fetch(`/api/enhanced-test/workflow/${workflowId}/status`);
    return await response.json();
};
```

### 3. Getting Results

```typescript
const getWorkflowResults = async (workflowId: string) => {
    const response = await fetch(`/api/enhanced-test/workflow/${workflowId}/results`);
    return await response.json();
};
```

This frontend integration provides a complete "click and walk away" user experience with real-time progress updates and comprehensive results display.