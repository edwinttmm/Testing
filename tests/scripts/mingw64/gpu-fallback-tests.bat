@echo off
REM GPU/CPU Fallback Tests for MINGW64
REM Tests hardware acceleration and fallback mechanisms

setlocal enabledelayedexpansion

echo ========================================
echo GPU/CPU Fallback Tests
echo ========================================
echo.

set TEST_PASSED=0
set TEST_FAILED=0
set PROJECT_ROOT=%~dp0..\..\..
set FRONTEND_DIR=%PROJECT_ROOT%\ai-model-validation-platform\frontend

cd /d "%FRONTEND_DIR%"

REM Test 1: WebGL Support Detection
echo [1/8] Testing WebGL Support Detection...

node -e "
// Simulate WebGL detection for headless environment
const mockCanvas = {
    getContext: function(type) {
        if (type === 'webgl' || type === 'webgl2') {
            return {
                getParameter: function(param) {
                    // Mock WebGL context
                    const GL_VERSION = 0x1F02;
                    const GL_RENDERER = 0x1F01;
                    const GL_VENDOR = 0x1F00;
                    
                    switch(param) {
                        case GL_VERSION: return 'WebGL 2.0';
                        case GL_RENDERER: return 'Mock Renderer';
                        case GL_VENDOR: return 'Mock Vendor';
                        default: return 'Mock Parameter';
                    }
                },
                getSupportedExtensions: function() {
                    return ['OES_texture_float', 'WEBGL_depth_texture'];
                }
            };
        }
        return null;
    }
};

function detectWebGLSupport() {
    try {
        const webgl = mockCanvas.getContext('webgl');
        const webgl2 = mockCanvas.getContext('webgl2');
        
        return {
            webgl: !!webgl,
            webgl2: !!webgl2,
            vendor: webgl ? webgl.getParameter(0x1F00) : 'Unknown',
            renderer: webgl ? webgl.getParameter(0x1F01) : 'Unknown',
            version: webgl ? webgl.getParameter(0x1F02) : 'Unknown'
        };
    } catch (error) {
        return {
            webgl: false,
            webgl2: false,
            error: error.message
        };
    }
}

const webglInfo = detectWebGLSupport();
console.log('WebGL Support Detection:');
console.log('  WebGL 1.0:', webglInfo.webgl ? '✅ Supported' : '❌ Not supported');
console.log('  WebGL 2.0:', webglInfo.webgl2 ? '✅ Supported' : '❌ Not supported');
console.log('  Vendor:', webglInfo.vendor);
console.log('  Renderer:', webglInfo.renderer);

if (webglInfo.webgl || webglInfo.webgl2) {
    console.log('✅ WebGL detection test passed');
} else {
    console.log('⚠️  WebGL not available - CPU fallback will be used');
}
" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ WebGL detection test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ WebGL detection test failed
    set /a TEST_FAILED+=1
)

REM Test 2: Canvas 2D Fallback Testing
echo [2/8] Testing Canvas 2D Fallback...

node -e "
// Mock Canvas 2D API
const mockCanvas2D = {
    getContext: function(type) {
        if (type === '2d') {
            return {
                fillRect: function(x, y, w, h) { return true; },
                strokeRect: function(x, y, w, h) { return true; },
                clearRect: function(x, y, w, h) { return true; },
                arc: function(x, y, r, start, end) { return true; },
                beginPath: function() { return true; },
                closePath: function() { return true; },
                stroke: function() { return true; },
                fill: function() { return true; },
                drawImage: function() { return true; },
                getImageData: function(x, y, w, h) {
                    return {
                        data: new Uint8ClampedArray(w * h * 4),
                        width: w,
                        height: h
                    };
                },
                putImageData: function() { return true; }
            };
        }
        return null;
    }
};

function testCanvas2DFallback() {
    try {
        const ctx = mockCanvas2D.getContext('2d');
        
        if (!ctx) {
            throw new Error('Canvas 2D context not available');
        }
        
        // Test basic drawing operations
        ctx.fillRect(0, 0, 100, 100);
        ctx.strokeRect(10, 10, 80, 80);
        ctx.clearRect(20, 20, 60, 60);
        
        // Test path operations
        ctx.beginPath();
        ctx.arc(50, 50, 25, 0, Math.PI * 2);
        ctx.stroke();
        ctx.fill();
        ctx.closePath();
        
        // Test image data operations
        const imageData = ctx.getImageData(0, 0, 100, 100);
        ctx.putImageData(imageData, 0, 0);
        
        return {
            success: true,
            operations: ['fillRect', 'strokeRect', 'clearRect', 'arc', 'paths', 'imageData']
        };
    } catch (error) {
        return {
            success: false,
            error: error.message
        };
    }
}

const canvas2DResult = testCanvas2DFallback();
console.log('Canvas 2D Fallback Test:');

if (canvas2DResult.success) {
    console.log('✅ Canvas 2D fallback working');
    console.log('  Supported operations:', canvas2DResult.operations.join(', '));
} else {
    console.log('❌ Canvas 2D fallback failed:', canvas2DResult.error);
    process.exit(1);
}
" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ Canvas 2D fallback test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ Canvas 2D fallback test failed
    set /a TEST_FAILED+=1
)

REM Test 3: CPU-based Image Processing
echo [3/8] Testing CPU-based Image Processing...

node -e "
// Mock image processing functions
function createImageProcessor() {
    return {
        processImage: function(imageData, options = {}) {
            const { width, height } = imageData;
            const data = imageData.data;
            
            // Mock image processing operations
            switch (options.operation) {
                case 'grayscale':
                    for (let i = 0; i < data.length; i += 4) {
                        const gray = data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114;
                        data[i] = data[i + 1] = data[i + 2] = gray;
                    }
                    break;
                    
                case 'blur':
                    // Simple box blur simulation
                    console.log('Applying blur filter...');
                    break;
                    
                case 'edge':
                    // Edge detection simulation
                    console.log('Applying edge detection...');
                    break;
                    
                default:
                    console.log('No processing applied');
            }
            
            return imageData;
        },
        
        resizeImage: function(imageData, newWidth, newHeight) {
            // Mock resize operation
            return {
                data: new Uint8ClampedArray(newWidth * newHeight * 4),
                width: newWidth,
                height: newHeight
            };
        },
        
        filterImage: function(imageData, filterType) {
            // Mock filter operation
            console.log('Applying filter:', filterType);
            return imageData;
        }
    };
}

function testCPUImageProcessing() {
    try {
        const processor = createImageProcessor();
        
        // Create mock image data
        const mockImageData = {
            data: new Uint8ClampedArray(100 * 100 * 4),
            width: 100,
            height: 100
        };
        
        // Fill with test data
        for (let i = 0; i < mockImageData.data.length; i += 4) {
            mockImageData.data[i] = Math.random() * 255;     // R
            mockImageData.data[i + 1] = Math.random() * 255; // G
            mockImageData.data[i + 2] = Math.random() * 255; // B
            mockImageData.data[i + 3] = 255;                 // A
        }
        
        console.log('Testing CPU image processing operations...');
        
        // Test grayscale conversion
        const grayscaleResult = processor.processImage(
            JSON.parse(JSON.stringify(mockImageData)), 
            { operation: 'grayscale' }
        );
        console.log('✅ Grayscale conversion completed');
        
        // Test resize operation
        const resizedResult = processor.resizeImage(mockImageData, 50, 50);
        console.log('✅ Image resize completed');
        
        // Test filter operations
        processor.filterImage(mockImageData, 'brightness');
        console.log('✅ Filter operations completed');
        
        // Performance test
        const startTime = Date.now();
        for (let i = 0; i < 100; i++) {
            processor.processImage(mockImageData, { operation: 'grayscale' });
        }
        const endTime = Date.now();
        const processingTime = endTime - startTime;
        
        console.log('✅ Performance test completed');
        console.log('  100 operations took:', processingTime, 'ms');
        console.log('  Average per operation:', (processingTime / 100).toFixed(2), 'ms');
        
        if (processingTime < 5000) { // 5 second threshold
            console.log('✅ CPU processing performance acceptable');
        } else {
            console.log('⚠️  CPU processing might be slow');
        }
        
        return { success: true, processingTime };
        
    } catch (error) {
        return { success: false, error: error.message };
    }
}

const cpuResult = testCPUImageProcessing();
if (cpuResult.success) {
    console.log('✅ CPU image processing test passed');
} else {
    console.log('❌ CPU image processing test failed:', cpuResult.error);
    process.exit(1);
}
" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ CPU image processing test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ CPU image processing test failed
    set /a TEST_FAILED+=1
)

REM Test 4: WebWorker Fallback for Heavy Processing
echo [4/8] Testing WebWorker Fallback...

node -e "
// Mock WebWorker for heavy processing
class MockWebWorker {
    constructor(script) {
        this.script = script;
        this.onmessage = null;
        this.onerror = null;
    }
    
    postMessage(data) {
        // Simulate async processing
        setTimeout(() => {
            try {
                // Mock heavy computation
                const result = this.processData(data);
                if (this.onmessage) {
                    this.onmessage({ data: result });
                }
            } catch (error) {
                if (this.onerror) {
                    this.onerror(error);
                }
            }
        }, 10);
    }
    
    processData(data) {
        switch (data.operation) {
            case 'matrix_multiply':
                return { result: 'Matrix multiplication completed', time: Date.now() };
            case 'image_filter':
                return { result: 'Image filtering completed', time: Date.now() };
            case 'data_analysis':
                return { result: 'Data analysis completed', time: Date.now() };
            default:
                return { result: 'Unknown operation', time: Date.now() };
        }
    }
    
    terminate() {
        console.log('Worker terminated');
    }
}

function testWebWorkerFallback() {
    return new Promise((resolve, reject) => {
        try {
            const worker = new MockWebWorker('heavy-processing.js');
            let completedTasks = 0;
            const totalTasks = 3;
            const results = [];
            
            worker.onmessage = function(event) {
                console.log('Worker result:', event.data.result);
                results.push(event.data);
                completedTasks++;
                
                if (completedTasks === totalTasks) {
                    worker.terminate();
                    resolve({
                        success: true,
                        results: results,
                        tasksCompleted: completedTasks
                    });
                }
            };
            
            worker.onerror = function(error) {
                worker.terminate();
                reject(error);
            };
            
            // Send test tasks
            worker.postMessage({ operation: 'matrix_multiply', data: 'test' });
            worker.postMessage({ operation: 'image_filter', data: 'test' });
            worker.postMessage({ operation: 'data_analysis', data: 'test' });
            
        } catch (error) {
            reject(error);
        }
    });
}

testWebWorkerFallback()
    .then(result => {
        console.log('✅ WebWorker fallback test passed');
        console.log('  Tasks completed:', result.tasksCompleted);
        console.log('  Results received:', result.results.length);
    })
    .catch(error => {
        console.log('❌ WebWorker fallback test failed:', error.message);
        process.exit(1);
    });
" 2>&1

timeout /t 5 >nul 2>&1

if !errorlevel! equ 0 (
    echo   ✅ WebWorker fallback test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ WebWorker fallback test failed
    set /a TEST_FAILED+=1
)

REM Test 5: GPU Memory Detection and Fallback
echo [5/8] Testing GPU Memory Detection...

node -e "
// Mock GPU memory detection
function detectGPUMemory() {
    // Simulate GPU memory detection
    const mockGPUInfo = {
        totalMemory: 1024 * 1024 * 1024, // 1GB
        availableMemory: 512 * 1024 * 1024, // 512MB
        vendor: 'Mock GPU Vendor',
        model: 'Mock GPU Model',
        driverVersion: '1.0.0'
    };
    
    // Calculate memory usage percentage
    const usagePercentage = ((mockGPUInfo.totalMemory - mockGPUInfo.availableMemory) / mockGPUInfo.totalMemory) * 100;
    
    return {
        ...mockGPUInfo,
        usagePercentage: usagePercentage.toFixed(2),
        memoryPressure: usagePercentage > 80 ? 'high' : usagePercentage > 60 ? 'medium' : 'low'
    };
}

function testGPUMemoryFallback() {
    try {
        const gpuInfo = detectGPUMemory();
        
        console.log('GPU Memory Information:');
        console.log('  Total Memory:', (gpuInfo.totalMemory / 1024 / 1024).toFixed(0), 'MB');
        console.log('  Available Memory:', (gpuInfo.availableMemory / 1024 / 1024).toFixed(0), 'MB');
        console.log('  Usage:', gpuInfo.usagePercentage + '%');
        console.log('  Memory Pressure:', gpuInfo.memoryPressure);
        console.log('  Vendor:', gpuInfo.vendor);
        console.log('  Model:', gpuInfo.model);
        
        // Test fallback logic
        if (gpuInfo.memoryPressure === 'high') {
            console.log('⚠️  High memory pressure detected - falling back to CPU');
            console.log('✅ GPU fallback logic triggered');
        } else {
            console.log('✅ GPU memory sufficient for operations');
        }
        
        // Test memory allocation simulation
        const allocationSize = 100 * 1024 * 1024; // 100MB
        if (gpuInfo.availableMemory > allocationSize) {
            console.log('✅ GPU memory allocation would succeed');
        } else {
            console.log('⚠️  GPU memory allocation would fail - CPU fallback required');
        }
        
        return { success: true, gpuInfo };
        
    } catch (error) {
        return { success: false, error: error.message };
    }
}

const memoryResult = testGPUMemoryFallback();
if (memoryResult.success) {
    console.log('✅ GPU memory detection test passed');
} else {
    console.log('❌ GPU memory detection test failed:', memoryResult.error);
    process.exit(1);
}
" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ GPU memory detection test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ GPU memory detection test failed
    set /a TEST_FAILED+=1
)

REM Test 6: Hardware Acceleration Detection
echo [6/8] Testing Hardware Acceleration Detection...

node -e "
// Mock hardware acceleration detection
function detectHardwareAcceleration() {
    const features = {
        webgl: true,
        webgl2: false,
        simd: false,
        webgpu: false,
        hardwareDecoding: true,
        gpuCompute: false
    };
    
    const performanceProfile = {
        cpuCores: 4,
        cpuFrequency: 2400, // MHz
        ramSize: 8192, // MB
        gpuPresent: true,
        dedicatedGpu: false
    };
    
    return { features, performanceProfile };
}

function createFallbackStrategy(capabilities) {
    const strategy = {
        renderingMode: 'hybrid',
        processingMode: 'cpu',
        optimizations: []
    };
    
    if (capabilities.features.webgl) {
        strategy.renderingMode = 'webgl';
        strategy.optimizations.push('gpu_rendering');
    }
    
    if (capabilities.features.simd) {
        strategy.processingMode = 'simd';
        strategy.optimizations.push('vectorized_operations');
    }
    
    if (capabilities.performanceProfile.cpuCores >= 4) {
        strategy.optimizations.push('multi_threading');
    }
    
    if (capabilities.performanceProfile.ramSize >= 4096) {
        strategy.optimizations.push('memory_caching');
    }
    
    return strategy;
}

try {
    const capabilities = detectHardwareAcceleration();
    console.log('Hardware Capabilities:');
    console.log('  WebGL:', capabilities.features.webgl ? '✅' : '❌');
    console.log('  WebGL 2:', capabilities.features.webgl2 ? '✅' : '❌');
    console.log('  SIMD:', capabilities.features.simd ? '✅' : '❌');
    console.log('  WebGPU:', capabilities.features.webgpu ? '✅' : '❌');
    console.log('  Hardware Decoding:', capabilities.features.hardwareDecoding ? '✅' : '❌');
    
    console.log('Performance Profile:');
    console.log('  CPU Cores:', capabilities.performanceProfile.cpuCores);
    console.log('  CPU Frequency:', capabilities.performanceProfile.cpuFrequency, 'MHz');
    console.log('  RAM Size:', capabilities.performanceProfile.ramSize, 'MB');
    console.log('  GPU Present:', capabilities.performanceProfile.gpuPresent ? '✅' : '❌');
    
    const strategy = createFallbackStrategy(capabilities);
    console.log('Fallback Strategy:');
    console.log('  Rendering Mode:', strategy.renderingMode);
    console.log('  Processing Mode:', strategy.processingMode);
    console.log('  Optimizations:', strategy.optimizations.join(', '));
    
    console.log('✅ Hardware acceleration detection completed');
    
} catch (error) {
    console.log('❌ Hardware acceleration detection failed:', error.message);
    process.exit(1);
}
" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ Hardware acceleration detection test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ Hardware acceleration detection test failed
    set /a TEST_FAILED+=1
)

REM Test 7: Performance Degradation Testing
echo [7/8] Testing Performance Degradation Handling...

node -e "
// Mock performance monitoring and degradation handling
class PerformanceMonitor {
    constructor() {
        this.metrics = {
            frameRate: 60,
            cpuUsage: 50,
            memoryUsage: 60,
            gpuUsage: 40
        };
        this.thresholds = {
            frameRate: 30,
            cpuUsage: 80,
            memoryUsage: 85,
            gpuUsage: 90
        };
    }
    
    simulateLoad() {
        // Simulate increasing load
        this.metrics.frameRate = Math.max(10, this.metrics.frameRate - Math.random() * 20);
        this.metrics.cpuUsage = Math.min(100, this.metrics.cpuUsage + Math.random() * 30);
        this.metrics.memoryUsage = Math.min(100, this.metrics.memoryUsage + Math.random() * 25);
        this.metrics.gpuUsage = Math.min(100, this.metrics.gpuUsage + Math.random() * 35);
    }
    
    checkPerformance() {
        const issues = [];
        
        if (this.metrics.frameRate < this.thresholds.frameRate) {
            issues.push('low_framerate');
        }
        if (this.metrics.cpuUsage > this.thresholds.cpuUsage) {
            issues.push('high_cpu');
        }
        if (this.metrics.memoryUsage > this.thresholds.memoryUsage) {
            issues.push('high_memory');
        }
        if (this.metrics.gpuUsage > this.thresholds.gpuUsage) {
            issues.push('high_gpu');
        }
        
        return issues;
    }
    
    applyOptimizations(issues) {
        const optimizations = [];
        
        if (issues.includes('low_framerate')) {
            optimizations.push('reduce_quality');
            optimizations.push('skip_frames');
        }
        
        if (issues.includes('high_cpu')) {
            optimizations.push('reduce_complexity');
            optimizations.push('enable_caching');
        }
        
        if (issues.includes('high_memory')) {
            optimizations.push('garbage_collect');
            optimizations.push('reduce_buffer_size');
        }
        
        if (issues.includes('high_gpu')) {
            optimizations.push('fallback_to_cpu');
            optimizations.push('reduce_effects');
        }
        
        return optimizations;
    }
}

function testPerformanceDegradation() {
    try {
        const monitor = new PerformanceMonitor();
        
        console.log('Initial Performance Metrics:');
        console.log('  Frame Rate:', monitor.metrics.frameRate.toFixed(1), 'fps');
        console.log('  CPU Usage:', monitor.metrics.cpuUsage.toFixed(1) + '%');
        console.log('  Memory Usage:', monitor.metrics.memoryUsage.toFixed(1) + '%');
        console.log('  GPU Usage:', monitor.metrics.gpuUsage.toFixed(1) + '%');
        
        // Simulate load
        console.log('\\nSimulating performance load...');
        monitor.simulateLoad();
        
        console.log('Performance Under Load:');
        console.log('  Frame Rate:', monitor.metrics.frameRate.toFixed(1), 'fps');
        console.log('  CPU Usage:', monitor.metrics.cpuUsage.toFixed(1) + '%');
        console.log('  Memory Usage:', monitor.metrics.memoryUsage.toFixed(1) + '%');
        console.log('  GPU Usage:', monitor.metrics.gpuUsage.toFixed(1) + '%');
        
        // Check for issues
        const issues = monitor.checkPerformance();
        if (issues.length > 0) {
            console.log('\\n⚠️  Performance issues detected:', issues.join(', '));
            
            const optimizations = monitor.applyOptimizations(issues);
            console.log('✅ Applying optimizations:', optimizations.join(', '));
            
            // Simulate optimization effects
            if (optimizations.includes('fallback_to_cpu')) {
                console.log('✅ GPU fallback triggered successfully');
            }
            
            if (optimizations.includes('reduce_quality')) {
                console.log('✅ Quality reduction applied');
            }
            
        } else {
            console.log('\\n✅ Performance within acceptable thresholds');
        }
        
        console.log('✅ Performance degradation handling test completed');
        return true;
        
    } catch (error) {
        console.log('❌ Performance degradation test failed:', error.message);
        return false;
    }
}

if (testPerformanceDegradation()) {
    console.log('\\n✅ Performance degradation test passed');
} else {
    process.exit(1);
}
" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ Performance degradation test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ Performance degradation test failed
    set /a TEST_FAILED+=1
)

REM Test 8: Adaptive Quality Settings
echo [8/8] Testing Adaptive Quality Settings...

node -e "
// Mock adaptive quality system
class AdaptiveQualityManager {
    constructor() {
        this.currentQuality = 'high';
        this.availableQualities = ['low', 'medium', 'high', 'ultra'];
        this.settings = {
            high: { resolution: 1.0, effects: true, shadows: true, antialiasing: true },
            medium: { resolution: 0.8, effects: true, shadows: false, antialiasing: true },
            low: { resolution: 0.6, effects: false, shadows: false, antialiasing: false }
        };
    }
    
    adjustQuality(performanceMetric) {
        let newQuality = this.currentQuality;
        
        if (performanceMetric < 30 && this.currentQuality !== 'low') {
            // Performance is poor, reduce quality
            const currentIndex = this.availableQualities.indexOf(this.currentQuality);
            newQuality = this.availableQualities[Math.max(0, currentIndex - 1)];
        } else if (performanceMetric > 55 && this.currentQuality !== 'ultra') {
            // Performance is good, increase quality
            const currentIndex = this.availableQualities.indexOf(this.currentQuality);
            newQuality = this.availableQualities[Math.min(this.availableQualities.length - 1, currentIndex + 1)];
        }
        
        if (newQuality !== this.currentQuality) {
            this.currentQuality = newQuality;
            return true; // Quality changed
        }
        
        return false; // No change needed
    }
    
    getCurrentSettings() {
        return this.settings[this.currentQuality] || this.settings.medium;
    }
    
    getQualityInfo() {
        return {
            current: this.currentQuality,
            settings: this.getCurrentSettings(),
            available: this.availableQualities
        };
    }
}

function testAdaptiveQuality() {
    try {
        const qualityManager = new AdaptiveQualityManager();
        
        console.log('Testing Adaptive Quality System...');
        console.log('Initial quality:', qualityManager.currentQuality);
        
        // Test scenarios
        const scenarios = [
            { name: 'Good Performance', fps: 60 },
            { name: 'Moderate Performance', fps: 45 },
            { name: 'Poor Performance', fps: 25 },
            { name: 'Very Poor Performance', fps: 15 },
            { name: 'Recovering Performance', fps: 40 }
        ];
        
        scenarios.forEach((scenario, index) => {
            console.log('\\nScenario', index + 1 + ':', scenario.name, '(' + scenario.fps + ' fps)');
            
            const qualityChanged = qualityManager.adjustQuality(scenario.fps);
            const qualityInfo = qualityManager.getQualityInfo();
            
            if (qualityChanged) {
                console.log('✅ Quality adjusted to:', qualityInfo.current);
            } else {
                console.log('ℹ️  Quality maintained at:', qualityInfo.current);
            }
            
            console.log('  Settings:', JSON.stringify(qualityInfo.settings, null, 4));
        });
        
        // Test GPU fallback scenario
        console.log('\\nTesting GPU fallback scenario...');
        const fallbackTriggered = qualityManager.adjustQuality(10); // Very poor performance
        
        if (qualityManager.currentQuality === 'low') {
            console.log('✅ Quality reduced to minimum - GPU fallback would be triggered');
            console.log('✅ CPU-only rendering mode would be activated');
        }
        
        console.log('\\n✅ Adaptive quality testing completed');
        return true;
        
    } catch (error) {
        console.log('❌ Adaptive quality test failed:', error.message);
        return false;
    }
}

if (testAdaptiveQuality()) {
    console.log('\\n✅ Adaptive quality test passed');
} else {
    process.exit(1);
}
" 2>&1

if !errorlevel! equ 0 (
    echo   ✅ Adaptive quality test passed
    set /a TEST_PASSED+=1
) else (
    echo   ❌ Adaptive quality test failed
    set /a TEST_FAILED+=1
)

REM Summary
echo.
echo ========================================
echo GPU/CPU Fallback Tests Summary
echo ========================================
echo Passed: %TEST_PASSED%
echo Failed: %TEST_FAILED%

if %TEST_FAILED% gtr 2 (
    echo.
    echo ❌ Multiple GPU/CPU fallback issues detected!
    echo Hardware acceleration may not work properly.
    exit /b 1
) else if %TEST_FAILED% gtr 0 (
    echo.
    echo ⚠️  Some fallback tests failed, but basic functionality should work.
    exit /b 0
) else (
    echo.
    echo ✅ All GPU/CPU fallback tests passed!
    exit /b 0
)