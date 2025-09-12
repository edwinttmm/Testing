/**
 * Comprehensive Workflow Testing Script
 * Monitors video detection workflow from start to finish
 * Captures API responses, status changes, and frontend behavior
 */

class WorkflowMonitor {
    constructor() {
        this.logs = [];
        this.apiResponses = [];
        this.statusHistory = [];
        this.errors = [];
        this.originalFetch = window.fetch;
        this.setupInterceptors();
    }

    setupInterceptors() {
        // Intercept all fetch requests
        window.fetch = async (url, options) => {
            const startTime = Date.now();
            console.log(`🌐 API Request: ${options?.method || 'GET'} ${url}`);
            this.log(`API_REQUEST`, { url, method: options?.method || 'GET', body: options?.body });
            
            try {
                const response = await this.originalFetch(url, options);
                const duration = Date.now() - startTime;
                
                const responseClone = response.clone();
                const responseData = await responseClone.text();
                
                console.log(`✅ API Response (${duration}ms):`, response.status, url);
                this.log(`API_RESPONSE`, { 
                    url, 
                    status: response.status, 
                    headers: Object.fromEntries(response.headers.entries()),
                    body: responseData.substring(0, 1000), // First 1KB only
                    duration 
                });

                // Track API responses
                this.apiResponses.push({
                    timestamp: new Date().toISOString(),
                    url,
                    method: options?.method || 'GET',
                    status: response.status,
                    duration,
                    response: responseData.substring(0, 1000)
                });

                return response;
            } catch (error) {
                console.error(`❌ API Error:`, error);
                this.log(`API_ERROR`, { url, error: error.message });
                this.errors.push({ timestamp: new Date().toISOString(), type: 'API_ERROR', url, error: error.message });
                throw error;
            }
        };

        // Intercept console logs
        const originalLog = console.log;
        const originalError = console.error;
        const originalWarn = console.warn;
        
        console.log = (...args) => {
            this.log('CONSOLE_LOG', args);
            originalLog.apply(console, args);
        };
        
        console.error = (...args) => {
            this.log('CONSOLE_ERROR', args);
            this.errors.push({ timestamp: new Date().toISOString(), type: 'CONSOLE_ERROR', message: args.join(' ') });
            originalError.apply(console, args);
        };
        
        console.warn = (...args) => {
            this.log('CONSOLE_WARN', args);
            originalWarn.apply(console, args);
        };
    }

    log(type, data) {
        const entry = {
            timestamp: new Date().toISOString(),
            type,
            data
        };
        this.logs.push(entry);
        
        // Store in localStorage for persistence
        const existingLogs = JSON.parse(localStorage.getItem('workflow_monitor_logs') || '[]');
        existingLogs.push(entry);
        localStorage.setItem('workflow_monitor_logs', JSON.stringify(existingLogs.slice(-1000))); // Keep last 1000 entries
    }

    trackStatusChange(videoId, oldStatus, newStatus) {
        const change = {
            timestamp: new Date().toISOString(),
            videoId,
            oldStatus,
            newStatus
        };
        this.statusHistory.push(change);
        this.log('STATUS_CHANGE', change);
        console.log(`📊 Status Change: ${videoId} ${oldStatus} → ${newStatus}`);
    }

    async monitorVideoWorkflow(videoId) {
        console.log(`🎬 Starting workflow monitoring for video: ${videoId}`);
        this.log('WORKFLOW_START', { videoId });

        let currentStatus = 'unknown';
        let statusCheckCount = 0;
        const maxStatusChecks = 60; // 5 minutes max
        
        const statusCheckInterval = setInterval(async () => {
            statusCheckCount++;
            
            try {
                const response = await fetch(`http://localhost:8000/api/videos/${videoId}`);
                const videoData = await response.json();
                
                if (videoData.status !== currentStatus) {
                    this.trackStatusChange(videoId, currentStatus, videoData.status);
                    currentStatus = videoData.status;
                }

                console.log(`📊 Video Status Check ${statusCheckCount}: ${videoData.status}`);
                this.log('STATUS_CHECK', { videoId, status: videoData.status, check: statusCheckCount });

                // Stop monitoring if completed or failed
                if (videoData.status === 'completed' || videoData.status === 'failed' || statusCheckCount >= maxStatusChecks) {
                    clearInterval(statusCheckInterval);
                    this.log('WORKFLOW_END', { videoId, finalStatus: videoData.status, totalChecks: statusCheckCount });
                    console.log(`🏁 Workflow monitoring completed for ${videoId}. Final status: ${videoData.status}`);
                    this.generateReport();
                }
            } catch (error) {
                console.error(`❌ Status check error:`, error);
                this.log('STATUS_CHECK_ERROR', { videoId, error: error.message, check: statusCheckCount });
            }
        }, 5000); // Check every 5 seconds

        return statusCheckInterval;
    }

    async testVideoUpload() {
        console.log(`🚀 Starting fresh video upload test...`);
        this.log('TEST_START', { testType: 'VIDEO_UPLOAD' });

        try {
            // First check what videos are available
            const videosResponse = await fetch('http://localhost:8000/api/videos');
            const videosData = await videosResponse.json();
            console.log(`📹 Current videos:`, videosData);

            // Create a test file (simulate video upload)
            const testVideoContent = new Blob(['test video content'], { type: 'video/mp4' });
            const formData = new FormData();
            formData.append('file', testVideoContent, 'test-workflow.mp4');

            console.log(`📤 Uploading test video...`);
            const uploadResponse = await fetch('http://localhost:8000/api/videos/upload', {
                method: 'POST',
                body: formData
            });

            if (!uploadResponse.ok) {
                throw new Error(`Upload failed: ${uploadResponse.status}`);
            }

            const uploadResult = await uploadResponse.json();
            console.log(`✅ Upload completed:`, uploadResult);
            
            if (uploadResult.id) {
                this.monitorVideoWorkflow(uploadResult.id);
            }

            return uploadResult;
        } catch (error) {
            console.error(`❌ Upload test failed:`, error);
            this.log('TEST_ERROR', { testType: 'VIDEO_UPLOAD', error: error.message });
            this.errors.push({ timestamp: new Date().toISOString(), type: 'UPLOAD_ERROR', error: error.message });
        }
    }

    async testExistingVideo(videoId) {
        console.log(`🔍 Testing existing video workflow: ${videoId}`);
        this.log('TEST_START', { testType: 'EXISTING_VIDEO', videoId });

        // Trigger detection for existing video
        try {
            const detectionResponse = await fetch(`http://localhost:8000/api/videos/${videoId}/detect`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ confidence_threshold: 0.5 })
            });

            if (!detectionResponse.ok) {
                throw new Error(`Detection trigger failed: ${detectionResponse.status}`);
            }

            const detectionResult = await detectionResponse.json();
            console.log(`🎯 Detection triggered:`, detectionResult);

            // Monitor this video
            this.monitorVideoWorkflow(videoId);

            return detectionResult;
        } catch (error) {
            console.error(`❌ Detection test failed:`, error);
            this.log('TEST_ERROR', { testType: 'EXISTING_VIDEO', videoId, error: error.message });
            this.errors.push({ timestamp: new Date().toISOString(), type: 'DETECTION_ERROR', videoId, error: error.message });
        }
    }

    generateReport() {
        const report = {
            summary: {
                totalLogs: this.logs.length,
                totalApiCalls: this.apiResponses.length,
                totalStatusChanges: this.statusHistory.length,
                totalErrors: this.errors.length,
                testDuration: this.logs.length > 0 ? 
                    new Date(this.logs[this.logs.length - 1].timestamp) - new Date(this.logs[0].timestamp) : 0
            },
            logs: this.logs,
            apiResponses: this.apiResponses,
            statusHistory: this.statusHistory,
            errors: this.errors,
            timestamp: new Date().toISOString()
        };

        console.log(`📋 Workflow Test Report:`, report);
        
        // Store report in localStorage
        localStorage.setItem('workflow_test_report', JSON.stringify(report));
        
        // Display summary
        console.log(`
=== WORKFLOW TEST SUMMARY ===
Total Logs: ${report.summary.totalLogs}
API Calls: ${report.summary.totalApiCalls}
Status Changes: ${report.summary.totalStatusChanges}
Errors: ${report.summary.totalErrors}
Test Duration: ${report.summary.testDuration}ms
===========================
        `);

        return report;
    }

    getStoredReport() {
        const report = localStorage.getItem('workflow_test_report');
        return report ? JSON.parse(report) : null;
    }

    clearStorage() {
        localStorage.removeItem('workflow_monitor_logs');
        localStorage.removeItem('workflow_test_report');
        console.log(`🧹 Monitoring storage cleared`);
    }
}

// Initialize monitor when script loads
window.workflowMonitor = new WorkflowMonitor();
console.log(`🚀 Workflow Monitor initialized. Available commands:`);
console.log(`- workflowMonitor.testVideoUpload() // Test fresh video upload`);
console.log(`- workflowMonitor.testExistingVideo(videoId) // Test existing video`);
console.log(`- workflowMonitor.generateReport() // Generate current report`);
console.log(`- workflowMonitor.getStoredReport() // Get last report`);
console.log(`- workflowMonitor.clearStorage() // Clear monitoring data`);