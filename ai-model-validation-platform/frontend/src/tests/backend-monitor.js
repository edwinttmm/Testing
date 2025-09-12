/**
 * Backend API Endpoint Testing Script
 * Tests individual endpoints and monitors responses
 */

class BackendMonitor {
    constructor() {
        this.baseUrl = 'http://localhost:8000';
        this.testResults = [];
    }

    async testEndpoint(endpoint, method = 'GET', data = null) {
        const startTime = Date.now();
        const url = `${this.baseUrl}${endpoint}`;
        
        console.log(`🧪 Testing ${method} ${endpoint}`);
        
        try {
            const options = {
                method,
                headers: {
                    'Content-Type': 'application/json'
                }
            };
            
            if (data) {
                options.body = JSON.stringify(data);
            }
            
            const response = await fetch(url, options);
            const duration = Date.now() - startTime;
            const responseText = await response.text();
            
            let responseData;
            try {
                responseData = JSON.parse(responseText);
            } catch {
                responseData = responseText;
            }
            
            const result = {
                timestamp: new Date().toISOString(),
                endpoint,
                method,
                url,
                status: response.status,
                duration,
                success: response.ok,
                headers: Object.fromEntries(response.headers.entries()),
                response: responseData,
                request: data
            };
            
            this.testResults.push(result);
            
            console.log(`${response.ok ? '✅' : '❌'} ${method} ${endpoint} - ${response.status} (${duration}ms)`);
            
            return result;
        } catch (error) {
            const result = {
                timestamp: new Date().toISOString(),
                endpoint,
                method,
                url,
                error: error.message,
                duration: Date.now() - startTime,
                success: false,
                request: data
            };
            
            this.testResults.push(result);
            console.error(`❌ ${method} ${endpoint} - ERROR: ${error.message}`);
            
            return result;
        }
    }

    async runComprehensiveTests() {
        console.log(`🚀 Starting comprehensive backend API tests...`);
        
        // Basic health checks
        await this.testEndpoint('/health');
        await this.testEndpoint('/api/docs');
        
        // Video API tests
        await this.testEndpoint('/api/videos');
        await this.testEndpoint('/api/videos/stats');
        
        // Get first video for detailed testing
        const videosResult = await this.testEndpoint('/api/videos');
        if (videosResult.success && videosResult.response.length > 0) {
            const videoId = videosResult.response[0].id;
            console.log(`🎬 Testing with video ID: ${videoId}`);
            
            // Test individual video endpoints
            await this.testEndpoint(`/api/videos/${videoId}`);
            await this.testEndpoint(`/api/videos/${videoId}/annotations`);
            await this.testEndpoint(`/api/videos/${videoId}/detections`);
            await this.testEndpoint(`/api/videos/${videoId}/status`);
            
            // Test detection trigger (this might show Manual status issue)
            await this.testEndpoint(`/api/videos/${videoId}/detect`, 'POST', { 
                confidence_threshold: 0.5 
            });
            
            // Wait a moment then check status again
            await new Promise(resolve => setTimeout(resolve, 2000));
            await this.testEndpoint(`/api/videos/${videoId}`);
            await this.testEndpoint(`/api/videos/${videoId}/status`);
        }
        
        // Project API tests
        await this.testEndpoint('/api/projects');
        
        // Test session API
        await this.testEndpoint('/api/test-sessions');
        
        console.log(`✅ Comprehensive API tests completed. Results:`, this.testResults);
        return this.testResults;
    }

    async testManualStatusIssue() {
        console.log(`🔍 Testing Manual Status Issue specifically...`);
        
        // Get all videos
        const videosResult = await this.testEndpoint('/api/videos');
        if (!videosResult.success) {
            console.error(`❌ Cannot fetch videos for Manual status test`);
            return;
        }
        
        const videos = videosResult.response;
        console.log(`📹 Found ${videos.length} videos`);
        
        // Check each video's status from different endpoints
        for (const video of videos.slice(0, 3)) { // Test first 3 videos
            console.log(`\n🎬 Testing video ${video.id} (${video.filename})`);
            console.log(`   Current status from /api/videos: ${video.status}`);
            
            // Test individual video endpoint
            const individualResult = await this.testEndpoint(`/api/videos/${video.id}`);
            if (individualResult.success) {
                console.log(`   Status from /api/videos/${video.id}: ${individualResult.response.status}`);
            }
            
            // Test status endpoint
            const statusResult = await this.testEndpoint(`/api/videos/${video.id}/status`);
            if (statusResult.success) {
                console.log(`   Status from /api/videos/${video.id}/status: ${JSON.stringify(statusResult.response)}`);
            }
            
            // Test detections endpoint
            const detectionsResult = await this.testEndpoint(`/api/videos/${video.id}/detections`);
            if (detectionsResult.success) {
                const detections = detectionsResult.response;
                console.log(`   Detections found: ${detections.length}`);
                if (detections.length > 0) {
                    console.log(`   First detection status: ${detections[0].status || 'no status field'}`);
                }
            }
            
            // Check if there's a mismatch
            if (individualResult.success && statusResult.success) {
                const videoStatus = individualResult.response.status;
                const statusEndpointResult = statusResult.response;
                
                if (videoStatus === 'Manual' || JSON.stringify(statusEndpointResult).includes('Manual')) {
                    console.log(`🚨 MANUAL STATUS DETECTED for video ${video.id}`);
                    console.log(`   Video object status: ${videoStatus}`);
                    console.log(`   Status endpoint response:`, statusEndpointResult);
                    
                    // Trigger detection to see if it changes
                    console.log(`   Triggering detection to test status change...`);
                    await this.testEndpoint(`/api/videos/${video.id}/detect`, 'POST', { 
                        confidence_threshold: 0.5 
                    });
                    
                    // Wait and check again
                    await new Promise(resolve => setTimeout(resolve, 3000));
                    const afterDetectionResult = await this.testEndpoint(`/api/videos/${video.id}`);
                    if (afterDetectionResult.success) {
                        console.log(`   Status after detection trigger: ${afterDetectionResult.response.status}`);
                    }
                }
            }
        }
    }

    generateReport() {
        const report = {
            timestamp: new Date().toISOString(),
            totalTests: this.testResults.length,
            successfulTests: this.testResults.filter(r => r.success).length,
            failedTests: this.testResults.filter(r => !r.success).length,
            averageResponseTime: this.testResults.reduce((sum, r) => sum + r.duration, 0) / this.testResults.length,
            results: this.testResults,
            manualStatusIssues: this.testResults.filter(r => 
                r.response && JSON.stringify(r.response).toLowerCase().includes('manual')
            )
        };
        
        console.log(`📊 Backend Test Report:`, report);
        localStorage.setItem('backend_test_report', JSON.stringify(report));
        
        return report;
    }
}

// Initialize backend monitor
window.backendMonitor = new BackendMonitor();
console.log(`🚀 Backend Monitor initialized. Available commands:`);
console.log(`- backendMonitor.runComprehensiveTests() // Run all API tests`);
console.log(`- backendMonitor.testManualStatusIssue() // Focus on Manual status issue`);
console.log(`- backendMonitor.testEndpoint(endpoint, method, data) // Test specific endpoint`);
console.log(`- backendMonitor.generateReport() // Generate test report`);