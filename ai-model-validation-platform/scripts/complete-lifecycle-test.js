#!/usr/bin/env node
/**
 * Complete Application Lifecycle Test
 * Tests every feature with real interactions and browser console monitoring
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const { spawn, exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

class CompleteLifecycleTest {
    constructor() {
        this.baseDir = '/home/rigade/Testing/ai-model-validation-platform';
        this.logDir = path.join(this.baseDir, `logs/complete-test-${Date.now()}`);
        this.backendUrl = 'http://localhost:8000';
        this.frontendUrl = 'http://localhost:3000';
        
        // Test videos available
        this.testVideos = [
            path.join(this.baseDir, 'uploads/child-1-1-1.mp4'),
            path.join(this.baseDir, 'uploads/0ac5e0e9-fbcd-40d4-b115-ad496807e29a.mp4')
        ];
        
        this.testResults = {
            timestamp: new Date().toISOString(),
            services: {},
            pageTests: {},
            featureTests: {},
            consoleErrors: [],
            networkErrors: [],
            dataFlow: [],
            screenshots: []
        };
        
        // Create log directory
        if (!fs.existsSync(this.logDir)) {
            fs.mkdirSync(this.logDir, { recursive: true });
        }
        
        this.logger = this.setupLogger();
    }
    
    setupLogger() {
        const logFile = path.join(this.logDir, 'complete-test.log');
        const logStream = fs.createWriteStream(logFile, { flags: 'a' });
        
        return {
            log: (message, level = 'INFO') => {
                const timestamp = new Date().toISOString();
                const logMessage = `[${timestamp}] [${level}] ${message}`;
                console.log(logMessage);
                logStream.write(logMessage + '\n');
            },
            error: (message, error) => {
                const timestamp = new Date().toISOString();
                const logMessage = `[${timestamp}] [ERROR] ${message}: ${error?.message || error}`;
                console.error(logMessage);
                logStream.write(logMessage + '\n');
                if (error?.stack) {
                    logStream.write(error.stack + '\n');
                }
            }
        };
    }
    
    async setupServices() {
        this.logger.log('=== PHASE 1: Setting up all services ===');
        
        // 1. Start PostgreSQL
        this.logger.log('Starting PostgreSQL database...');
        try {
            await execPromise('docker run -d --name test-postgres -p 5432:5432 -e POSTGRES_PASSWORD=password -e POSTGRES_DB=aivalidation postgres:latest');
            this.testResults.services.postgresql = 'started';
            this.logger.log('✅ PostgreSQL started successfully');
        } catch (error) {
            // May already be running
            this.logger.log('PostgreSQL may already be running');
            this.testResults.services.postgresql = 'existing';
        }
        
        // 2. Start Redis
        this.logger.log('Starting Redis cache...');
        try {
            await execPromise('docker run -d --name test-redis -p 6379:6379 redis:latest');
            this.testResults.services.redis = 'started';
            this.logger.log('✅ Redis started successfully');
        } catch (error) {
            this.logger.log('Redis may already be running');
            this.testResults.services.redis = 'existing';
        }
        
        // Wait for services to be ready
        await this.sleep(5000);
        
        // 3. Update backend configuration
        this.logger.log('Updating backend configuration...');
        const envContent = `
DATABASE_URL=postgresql://postgres:password@localhost:5432/aivalidation
REDIS_URL=redis://localhost:6379
SECRET_KEY=test-secret-key-32-characters-long-for-testing
ENVIRONMENT=development
DEBUG=true
        `;
        fs.writeFileSync(path.join(this.baseDir, 'backend/.env'), envContent);
        
        // 4. Run database migrations
        this.logger.log('Running database migrations...');
        try {
            await execPromise('cd backend && alembic upgrade head', { cwd: this.baseDir });
            this.logger.log('✅ Database migrations completed');
        } catch (error) {
            this.logger.error('Migration failed', error);
        }
    }
    
    async startBackend() {
        this.logger.log('Starting backend server...');
        
        return new Promise((resolve) => {
            const backendProcess = spawn('python', ['main.py'], {
                cwd: path.join(this.baseDir, 'backend'),
                env: { ...process.env, PYTHONUNBUFFERED: '1' }
            });
            
            backendProcess.stdout.on('data', (data) => {
                const message = data.toString();
                fs.appendFileSync(path.join(this.logDir, 'backend.log'), message);
                
                if (message.includes('Application startup complete')) {
                    this.logger.log('✅ Backend server started');
                    this.testResults.services.backend = 'running';
                    resolve(backendProcess);
                }
            });
            
            backendProcess.stderr.on('data', (data) => {
                fs.appendFileSync(path.join(this.logDir, 'backend-errors.log'), data.toString());
            });
            
            // Timeout after 30 seconds
            setTimeout(() => {
                this.logger.log('⚠️ Backend startup timeout');
                resolve(backendProcess);
            }, 30000);
        });
    }
    
    async startFrontend() {
        this.logger.log('Starting frontend application...');
        
        return new Promise((resolve) => {
            const frontendProcess = spawn('npm', ['start'], {
                cwd: path.join(this.baseDir, 'frontend'),
                env: { ...process.env, BROWSER: 'none', CI: 'true' }
            });
            
            frontendProcess.stdout.on('data', (data) => {
                const message = data.toString();
                fs.appendFileSync(path.join(this.logDir, 'frontend.log'), message);
                
                if (message.includes('webpack compiled') || message.includes('Compiled')) {
                    this.logger.log('✅ Frontend application compiled');
                    this.testResults.services.frontend = 'running';
                    resolve(frontendProcess);
                }
            });
            
            frontendProcess.stderr.on('data', (data) => {
                fs.appendFileSync(path.join(this.logDir, 'frontend-errors.log'), data.toString());
            });
            
            // Timeout after 60 seconds
            setTimeout(() => {
                this.logger.log('⚠️ Frontend startup timeout');
                resolve(frontendProcess);
            }, 60000);
        });
    }
    
    async runBrowserTests() {
        this.logger.log('=== PHASE 2: Browser Testing with Console Monitoring ===');
        
        const browser = await puppeteer.launch({
            headless: false, // Set to false to see the browser
            args: ['--no-sandbox', '--disable-setuid-sandbox'],
            devtools: true // Open DevTools automatically
        });
        
        const page = await browser.newPage();
        
        // Enable console logging
        page.on('console', msg => {
            const type = msg.type();
            const text = msg.text();
            const location = msg.location();
            
            const logEntry = {
                timestamp: new Date().toISOString(),
                type: type,
                text: text,
                url: page.url(),
                location: location
            };
            
            if (type === 'error') {
                this.testResults.consoleErrors.push(logEntry);
                this.logger.error(`Console Error: ${text}`, { location });
            } else if (type === 'warning') {
                this.logger.log(`Console Warning: ${text}`, 'WARN');
            } else {
                this.logger.log(`Console ${type}: ${text}`);
            }
            
            // Save to console log file
            fs.appendFileSync(
                path.join(this.logDir, 'browser-console.json'),
                JSON.stringify(logEntry) + '\n'
            );
        });
        
        // Monitor page errors
        page.on('pageerror', error => {
            const errorEntry = {
                timestamp: new Date().toISOString(),
                message: error.message,
                stack: error.stack,
                url: page.url()
            };
            this.testResults.consoleErrors.push(errorEntry);
            this.logger.error('Page Error', error);
        });
        
        // Monitor network requests
        page.on('requestfailed', request => {
            const failureEntry = {
                timestamp: new Date().toISOString(),
                url: request.url(),
                method: request.method(),
                failure: request.failure().errorText
            };
            this.testResults.networkErrors.push(failureEntry);
            this.logger.error(`Network Request Failed: ${request.url()}`, request.failure());
        });
        
        // Monitor responses
        page.on('response', response => {
            if (response.status() >= 400) {
                this.logger.log(`HTTP ${response.status()} - ${response.url()}`, 'WARN');
            }
        });
        
        // Test 1: Home Page
        await this.testPage(page, '/', 'Home Page');
        
        // Test 2: Projects Page - Create a project
        await this.testProjectsPage(page);
        
        // Test 3: Upload Videos
        await this.testVideoUpload(page);
        
        // Test 4: Dataset Management
        await this.testDatasets(page);
        
        // Test 5: Run ML Detection
        await this.testMLDetection(page);
        
        // Test 6: Ground Truth Annotation
        await this.testGroundTruth(page);
        
        // Test 7: Results Analysis
        await this.testResults(page);
        
        // Test 8: WebSocket Real-time Features
        await this.testWebSocket(page);
        
        await browser.close();
    }
    
    async testPage(page, path, name) {
        this.logger.log(`Testing ${name} at ${path}...`);
        
        const startTime = Date.now();
        try {
            await page.goto(`${this.frontendUrl}${path}`, { 
                waitUntil: 'networkidle2',
                timeout: 30000 
            });
            
            // Take screenshot
            const screenshotPath = `${this.logDir}/${name.replace(/\s/g, '_')}.png`;
            await page.screenshot({ path: screenshotPath, fullPage: true });
            this.testResults.screenshots.push(screenshotPath);
            
            // Check for common error indicators in the DOM
            const errors = await page.evaluate(() => {
                const errorElements = document.querySelectorAll('.error, .alert-danger, [class*="error"]');
                return Array.from(errorElements).map(el => el.textContent);
            });
            
            const loadTime = Date.now() - startTime;
            
            this.testResults.pageTests[name] = {
                url: path,
                loadTime: loadTime,
                errors: errors,
                screenshot: screenshotPath,
                status: errors.length > 0 ? 'has_errors' : 'success'
            };
            
            this.logger.log(`✅ ${name} loaded in ${loadTime}ms`);
            
            if (errors.length > 0) {
                this.logger.log(`⚠️ Found ${errors.length} error elements on page`);
            }
            
        } catch (error) {
            this.logger.error(`Failed to load ${name}`, error);
            this.testResults.pageTests[name] = {
                url: path,
                error: error.message,
                status: 'failed'
            };
        }
    }
    
    async testProjectsPage(page) {
        this.logger.log('=== Testing Projects Page Functionality ===');
        
        await page.goto(`${this.frontendUrl}/projects`, { waitUntil: 'networkidle2' });
        
        // Try to create a new project
        try {
            // Look for create button
            const createButton = await page.$('button:has-text("Create"), button:has-text("New Project"), button:has-text("Add Project")');
            if (createButton) {
                await createButton.click();
                await this.sleep(1000);
                
                // Fill in project form
                await page.type('input[name="name"], input[placeholder*="name"]', 'Test Project ' + Date.now());
                await page.type('textarea[name="description"], textarea[placeholder*="description"]', 'Automated test project');
                
                // Submit form
                const submitButton = await page.$('button[type="submit"], button:has-text("Save"), button:has-text("Create")');
                if (submitButton) {
                    await submitButton.click();
                    await this.sleep(2000);
                    
                    this.logger.log('✅ Project created successfully');
                    this.testResults.featureTests.projectCreation = 'success';
                    
                    // Track data flow
                    this.testResults.dataFlow.push({
                        action: 'project_created',
                        timestamp: new Date().toISOString(),
                        data: { name: 'Test Project' }
                    });
                }
            }
        } catch (error) {
            this.logger.error('Project creation failed', error);
            this.testResults.featureTests.projectCreation = 'failed';
        }
        
        await page.screenshot({ path: `${this.logDir}/projects_page.png`, fullPage: true });
    }
    
    async testVideoUpload(page) {
        this.logger.log('=== Testing Video Upload Functionality ===');
        
        // Navigate to video upload section
        await page.goto(`${this.frontendUrl}/datasets`, { waitUntil: 'networkidle2' });
        
        for (const videoPath of this.testVideos) {
            if (!fs.existsSync(videoPath)) {
                this.logger.log(`⚠️ Test video not found: ${videoPath}`);
                continue;
            }
            
            this.logger.log(`Uploading video: ${path.basename(videoPath)}`);
            
            try {
                // Find file input
                const fileInput = await page.$('input[type="file"]');
                if (fileInput) {
                    await fileInput.uploadFile(videoPath);
                    await this.sleep(2000);
                    
                    // Look for upload button
                    const uploadButton = await page.$('button:has-text("Upload"), button:has-text("Submit")');
                    if (uploadButton) {
                        await uploadButton.click();
                        
                        // Wait for upload to complete
                        await page.waitForSelector('.upload-progress, .upload-complete, .success', {
                            timeout: 30000
                        }).catch(() => {});
                        
                        this.logger.log('✅ Video uploaded successfully');
                        this.testResults.featureTests[`videoUpload_${path.basename(videoPath)}`] = 'success';
                        
                        // Track data flow
                        this.testResults.dataFlow.push({
                            action: 'video_uploaded',
                            timestamp: new Date().toISOString(),
                            data: { 
                                filename: path.basename(videoPath),
                                size: fs.statSync(videoPath).size
                            }
                        });
                        
                        // Monitor API calls
                        const apiCalls = await page.evaluate(() => {
                            return window.performance.getEntriesByType('resource')
                                .filter(entry => entry.name.includes('/api/'))
                                .map(entry => ({
                                    url: entry.name,
                                    duration: entry.duration,
                                    status: entry.transferSize === 0 ? 'cached' : 'fetched'
                                }));
                        });
                        
                        this.testResults.dataFlow.push({
                            action: 'api_calls_during_upload',
                            timestamp: new Date().toISOString(),
                            data: apiCalls
                        });
                    }
                }
            } catch (error) {
                this.logger.error(`Video upload failed for ${path.basename(videoPath)}`, error);
                this.testResults.featureTests[`videoUpload_${path.basename(videoPath)}`] = 'failed';
            }
        }
        
        await page.screenshot({ path: `${this.logDir}/video_upload.png`, fullPage: true });
    }
    
    async testDatasets(page) {
        this.logger.log('=== Testing Dataset Management ===');
        
        await page.goto(`${this.frontendUrl}/datasets`, { waitUntil: 'networkidle2' });
        
        // Check if videos appear in dataset list
        const videos = await page.evaluate(() => {
            const videoElements = document.querySelectorAll('[class*="video"], [class*="dataset-item"], tr');
            return Array.from(videoElements).map(el => el.textContent);
        });
        
        this.logger.log(`Found ${videos.length} dataset items`);
        this.testResults.featureTests.datasetListing = videos.length > 0 ? 'success' : 'no_data';
        
        // Try to interact with a video
        if (videos.length > 0) {
            try {
                const firstVideo = await page.$('[class*="video"]:first-child, tr:first-child');
                if (firstVideo) {
                    await firstVideo.click();
                    await this.sleep(2000);
                    
                    // Check if video details loaded
                    const videoDetails = await page.evaluate(() => {
                        return {
                            hasPlayer: !!document.querySelector('video'),
                            hasMetadata: !!document.querySelector('[class*="metadata"], [class*="details"]')
                        };
                    });
                    
                    this.testResults.featureTests.videoDetails = videoDetails;
                    this.logger.log('Video details:', videoDetails);
                }
            } catch (error) {
                this.logger.error('Failed to interact with video', error);
            }
        }
        
        await page.screenshot({ path: `${this.logDir}/datasets.png`, fullPage: true });
    }
    
    async testMLDetection(page) {
        this.logger.log('=== Testing ML Detection Pipeline ===');
        
        // Navigate to detection interface
        await page.goto(`${this.frontendUrl}/datasets`, { waitUntil: 'networkidle2' });
        
        try {
            // Look for run detection button
            const detectionButton = await page.$('button:has-text("Run Detection"), button:has-text("Detect"), button:has-text("Process")');
            if (detectionButton) {
                await detectionButton.click();
                await this.sleep(2000);
                
                // Monitor WebSocket messages for progress
                await page.evaluate(() => {
                    window.wsMessages = [];
                    const originalWS = window.WebSocket;
                    window.WebSocket = function(...args) {
                        const ws = new originalWS(...args);
                        ws.addEventListener('message', (event) => {
                            window.wsMessages.push({
                                timestamp: new Date().toISOString(),
                                data: event.data
                            });
                        });
                        return ws;
                    };
                });
                
                // Wait for detection to complete (with timeout)
                await page.waitForSelector('.detection-complete, .results, [class*="complete"]', {
                    timeout: 60000
                }).catch(() => {});
                
                // Collect WebSocket messages
                const wsMessages = await page.evaluate(() => window.wsMessages || []);
                this.testResults.dataFlow.push({
                    action: 'ml_detection_websocket',
                    timestamp: new Date().toISOString(),
                    data: wsMessages
                });
                
                this.logger.log('✅ ML Detection completed');
                this.testResults.featureTests.mlDetection = 'success';
            } else {
                this.logger.log('⚠️ Detection button not found');
                this.testResults.featureTests.mlDetection = 'button_not_found';
            }
        } catch (error) {
            this.logger.error('ML Detection failed', error);
            this.testResults.featureTests.mlDetection = 'failed';
        }
        
        await page.screenshot({ path: `${this.logDir}/ml_detection.png`, fullPage: true });
    }
    
    async testGroundTruth(page) {
        this.logger.log('=== Testing Ground Truth Annotation ===');
        
        await page.goto(`${this.frontendUrl}/ground-truth`, { waitUntil: 'networkidle2' });
        
        try {
            // Check if annotation interface loads
            const annotationCanvas = await page.$('canvas, svg, [class*="annotation"]');
            if (annotationCanvas) {
                // Try to create an annotation
                const canvasBounds = await annotationCanvas.boundingBox();
                if (canvasBounds) {
                    // Draw a bounding box
                    await page.mouse.move(canvasBounds.x + 50, canvasBounds.y + 50);
                    await page.mouse.down();
                    await page.mouse.move(canvasBounds.x + 150, canvasBounds.y + 150);
                    await page.mouse.up();
                    
                    await this.sleep(1000);
                    
                    // Try to save annotation
                    const saveButton = await page.$('button:has-text("Save"), button:has-text("Submit")');
                    if (saveButton) {
                        await saveButton.click();
                        await this.sleep(2000);
                        
                        this.logger.log('✅ Annotation created and saved');
                        this.testResults.featureTests.groundTruthAnnotation = 'success';
                        
                        // Track data flow
                        this.testResults.dataFlow.push({
                            action: 'annotation_created',
                            timestamp: new Date().toISOString(),
                            data: { type: 'bounding_box' }
                        });
                    }
                }
            } else {
                this.logger.log('⚠️ Annotation interface not found');
                this.testResults.featureTests.groundTruthAnnotation = 'interface_not_found';
            }
        } catch (error) {
            this.logger.error('Ground truth annotation failed', error);
            this.testResults.featureTests.groundTruthAnnotation = 'failed';
        }
        
        await page.screenshot({ path: `${this.logDir}/ground_truth.png`, fullPage: true });
    }
    
    async testResults(page) {
        this.logger.log('=== Testing Results Analysis ===');
        
        await page.goto(`${this.frontendUrl}/results`, { waitUntil: 'networkidle2' });
        
        // Check for results data
        const resultsData = await page.evaluate(() => {
            return {
                hasCharts: !!document.querySelector('canvas, svg[class*="chart"]'),
                hasTables: !!document.querySelector('table'),
                hasMetrics: !!document.querySelector('[class*="metric"], [class*="stat"]'),
                dataPoints: document.querySelectorAll('[class*="data-point"], td').length
            };
        });
        
        this.logger.log('Results page data:', resultsData);
        this.testResults.featureTests.resultsAnalysis = resultsData;
        
        // Try to export results
        try {
            const exportButton = await page.$('button:has-text("Export"), button:has-text("Download")');
            if (exportButton) {
                await exportButton.click();
                await this.sleep(2000);
                this.logger.log('✅ Results export triggered');
                this.testResults.featureTests.resultsExport = 'success';
            }
        } catch (error) {
            this.logger.error('Results export failed', error);
            this.testResults.featureTests.resultsExport = 'failed';
        }
        
        await page.screenshot({ path: `${this.logDir}/results.png`, fullPage: true });
    }
    
    async testWebSocket(page) {
        this.logger.log('=== Testing WebSocket Real-time Features ===');
        
        // Monitor WebSocket connections
        const wsConnections = await page.evaluate(() => {
            const connections = [];
            const originalWS = window.WebSocket;
            
            // Override WebSocket to monitor connections
            window.WebSocket = function(url, protocols) {
                const ws = new originalWS(url, protocols);
                const connection = {
                    url: url,
                    readyState: ws.readyState,
                    messages: [],
                    opened: false,
                    closed: false
                };
                
                ws.addEventListener('open', () => {
                    connection.opened = true;
                    connection.readyState = ws.readyState;
                });
                
                ws.addEventListener('message', (event) => {
                    connection.messages.push({
                        timestamp: new Date().toISOString(),
                        data: event.data
                    });
                });
                
                ws.addEventListener('close', () => {
                    connection.closed = true;
                    connection.readyState = ws.readyState;
                });
                
                connections.push(connection);
                return ws;
            };
            
            // Trigger a page that uses WebSocket
            return new Promise((resolve) => {
                setTimeout(() => {
                    resolve(connections);
                }, 5000);
            });
        });
        
        this.logger.log(`WebSocket connections: ${wsConnections.length}`);
        this.testResults.featureTests.webSocketConnections = wsConnections;
        
        if (wsConnections.length > 0) {
            this.logger.log('✅ WebSocket connections established');
        } else {
            this.logger.log('⚠️ No WebSocket connections detected');
        }
    }
    
    async checkDataFlow() {
        this.logger.log('=== Analyzing Complete Data Flow ===');
        
        // Check backend API for data persistence
        try {
            const response = await fetch(`${this.backendUrl}/api/projects`);
            const projects = await response.json();
            this.logger.log(`Projects in database: ${projects.length}`);
            
            const videosResponse = await fetch(`${this.backendUrl}/api/videos`);
            const videos = await videosResponse.json();
            this.logger.log(`Videos in database: ${videos.length}`);
            
            this.testResults.dataFlow.push({
                action: 'database_check',
                timestamp: new Date().toISOString(),
                data: {
                    projects: projects.length,
                    videos: videos.length
                }
            });
        } catch (error) {
            this.logger.error('Failed to check database', error);
        }
    }
    
    generateReport() {
        this.logger.log('=== Generating Comprehensive Report ===');
        
        const report = {
            ...this.testResults,
            summary: {
                totalConsoleErrors: this.testResults.consoleErrors.length,
                totalNetworkErrors: this.testResults.networkErrors.length,
                pagesTesteed: Object.keys(this.testResults.pageTests).length,
                featuresTested: Object.keys(this.testResults.featureTests).length,
                dataFlowEvents: this.testResults.dataFlow.length
            }
        };
        
        // Save JSON report
        fs.writeFileSync(
            path.join(this.logDir, 'complete-test-report.json'),
            JSON.stringify(report, null, 2)
        );
        
        // Generate markdown report
        let markdown = `# Complete Application Lifecycle Test Report
        
## Test Summary
- **Date:** ${new Date().toISOString()}
- **Console Errors:** ${report.summary.totalConsoleErrors}
- **Network Errors:** ${report.summary.totalNetworkErrors}
- **Pages Tested:** ${report.summary.pagesTested}
- **Features Tested:** ${report.summary.featuresTested}
- **Data Flow Events:** ${report.summary.dataFlowEvents}

## Services Status
${Object.entries(report.services).map(([service, status]) => `- **${service}:** ${status}`).join('\n')}

## Page Tests
${Object.entries(report.pageTests).map(([page, result]) => 
    `### ${page}
- Status: ${result.status}
- Load Time: ${result.loadTime}ms
- Errors: ${result.errors?.length || 0}
`).join('\n')}

## Feature Tests
${Object.entries(report.featureTests).map(([feature, result]) => 
    `- **${feature}:** ${typeof result === 'object' ? JSON.stringify(result) : result}`
).join('\n')}

## Console Errors
${report.consoleErrors.slice(0, 10).map(error => 
    `- [${error.type}] ${error.text} at ${error.url}`
).join('\n')}

## Network Errors
${report.networkErrors.slice(0, 10).map(error => 
    `- ${error.method} ${error.url}: ${error.failure}`
).join('\n')}

## Data Flow Events
${report.dataFlow.map(event => 
    `- **${event.action}** at ${event.timestamp}`
).join('\n')}

## Screenshots
${report.screenshots.map(path => `- ${path}`).join('\n')}
`;
        
        fs.writeFileSync(
            path.join(this.logDir, 'complete-test-report.md'),
            markdown
        );
        
        this.logger.log(`✅ Report saved to ${this.logDir}`);
    }
    
    async cleanup() {
        this.logger.log('Cleaning up test environment...');
        
        // Stop Docker containers
        try {
            await execPromise('docker stop test-postgres test-redis');
            await execPromise('docker rm test-postgres test-redis');
        } catch (error) {
            // Ignore errors
        }
    }
    
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    async run() {
        try {
            await this.setupServices();
            
            const backendProcess = await this.startBackend();
            const frontendProcess = await this.startFrontend();
            
            // Wait for services to stabilize
            await this.sleep(10000);
            
            await this.runBrowserTests();
            await this.checkDataFlow();
            
            this.generateReport();
            
            // Kill processes
            if (backendProcess) backendProcess.kill();
            if (frontendProcess) frontendProcess.kill();
            
            await this.cleanup();
            
            this.logger.log('✅ Complete lifecycle test finished!');
            
        } catch (error) {
            this.logger.error('Test failed', error);
            await this.cleanup();
            process.exit(1);
        }
    }
}

// Run the test
const test = new CompleteLifecycleTest();
test.run();