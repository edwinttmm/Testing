// Complete End-to-End Workflow Test
// Tests the entire user workflow from project creation to validation results

const http = require('http');
const fs = require('fs');

function makeRequest(url, options = {}) {
    return new Promise((resolve, reject) => {
        const urlObj = new URL(url);
        const requestOptions = {
            hostname: urlObj.hostname,
            port: urlObj.port,
            path: urlObj.pathname + urlObj.search,
            method: options.method || 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        };
        
        const req = http.request(requestOptions, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => resolve({
                status: res.statusCode,
                headers: res.headers,
                body: data
            }));
        });
        
        req.on('error', reject);
        req.setTimeout(10000, () => {
            req.destroy();
            reject(new Error('Request timeout'));
        });
        
        if (options.body) {
            req.write(typeof options.body === 'string' ? options.body : JSON.stringify(options.body));
        }
        
        req.end();
    });
}

async function testCompleteWorkflow() {
    console.log('🚀 Starting Complete End-to-End Workflow Test...');
    console.log('='.repeat(60));
    
    const results = {
        timestamp: new Date().toISOString(),
        workflow: {},
        success: true,
        errors: [],
        performance: {}
    };
    
    const startTime = Date.now();
    
    try {
        // Step 1: Test System Health
        console.log('🏥 Step 1: Testing System Health...');
        const healthStart = Date.now();
        const health = await makeRequest('http://localhost:8000/health');
        const healthTime = Date.now() - healthStart;
        
        results.workflow.health = {
            status: health.status,
            success: health.status === 200,
            responseTime: healthTime,
            hasStatus: health.body.includes('status'),
            data: health.status === 200 ? JSON.parse(health.body) : null
        };
        console.log(`${health.status === 200 ? '✅' : '❌'} Health Check: ${health.status} (${healthTime}ms)`);
        
        // Step 2: List Existing Projects
        console.log('\n📋 Step 2: Listing Existing Projects...');
        const projectsStart = Date.now();
        const projects = await makeRequest('http://localhost:8000/api/projects');
        const projectsTime = Date.now() - projectsStart;
        
        results.workflow.listProjects = {
            status: projects.status,
            success: projects.status === 200,
            responseTime: projectsTime,
            data: projects.status === 200 ? JSON.parse(projects.body) : null
        };
        console.log(`${projects.status === 200 ? '✅' : '❌'} List Projects: ${projects.status} (${projectsTime}ms)`);
        
        if (projects.status === 200) {
            const projectsData = JSON.parse(projects.body);
            console.log(`   📊 Found ${projectsData.length} existing projects`);
        }
        
        // Step 3: Create New Project
        console.log('\n➕ Step 3: Creating New Project...');
        const createStart = Date.now();
        const newProject = {
            name: `Integration Test Project ${Date.now()}`,
            description: 'Automated integration test project',
            cameraModel: 'Test Camera Model',
            cameraView: 'Front-facing VRU',
            lensType: 'Standard',
            resolution: '1920x1080',
            frameRate: 30,
            signalType: 'GPIO'
        };
        
        const createProject = await makeRequest('http://localhost:8000/api/projects', {
            method: 'POST',
            body: newProject
        });
        const createTime = Date.now() - createStart;
        
        results.workflow.createProject = {
            status: createProject.status,
            success: createProject.status === 200,
            responseTime: createTime,
            data: createProject.status === 200 ? JSON.parse(createProject.body) : null
        };
        console.log(`${createProject.status === 200 ? '✅' : '❌'} Create Project: ${createProject.status} (${createTime}ms)`);
        
        let createdProjectId = null;
        if (createProject.status === 200) {
            const projectData = JSON.parse(createProject.body);
            createdProjectId = projectData.id;
            console.log(`   🆔 Created project ID: ${createdProjectId}`);
        }
        
        // Step 4: Get Project Details
        if (createdProjectId) {
            console.log('\n🔍 Step 4: Getting Project Details...');
            const detailsStart = Date.now();
            const projectDetails = await makeRequest(`http://localhost:8000/api/projects/${createdProjectId}`);
            const detailsTime = Date.now() - detailsStart;
            
            results.workflow.getProject = {
                status: projectDetails.status,
                success: projectDetails.status === 200,
                responseTime: detailsTime,
                data: projectDetails.status === 200 ? JSON.parse(projectDetails.body) : null
            };
            console.log(`${projectDetails.status === 200 ? '✅' : '❌'} Get Project: ${projectDetails.status} (${detailsTime}ms)`);
        }
        
        // Step 5: List Videos for Project
        console.log('\n🎥 Step 5: Listing Videos...');
        const videosStart = Date.now();
        const videos = await makeRequest('http://localhost:8000/api/videos');
        const videosTime = Date.now() - videosStart;
        
        results.workflow.listVideos = {
            status: videos.status,
            success: videos.status === 200,
            responseTime: videosTime,
            data: videos.status === 200 ? JSON.parse(videos.body) : null
        };
        console.log(`${videos.status === 200 ? '✅' : '❌'} List Videos: ${videos.status} (${videosTime}ms)`);
        
        if (videos.status === 200) {
            const videosData = JSON.parse(videos.body);
            console.log(`   📊 Found ${videosData.total || 0} videos`);
        }
        
        // Step 6: Test Ground Truth System
        console.log('\n🎯 Step 6: Testing Ground Truth System...');
        const groundTruthStart = Date.now();
        const groundTruth = await makeRequest('http://localhost:8000/api/ground-truth/');
        const groundTruthTime = Date.now() - groundTruthStart;
        
        results.workflow.groundTruth = {
            status: groundTruth.status,
            success: groundTruth.status === 200 || groundTruth.status === 404, // 404 is acceptable for empty ground truth
            responseTime: groundTruthTime
        };
        console.log(`${results.workflow.groundTruth.success ? '✅' : '❌'} Ground Truth: ${groundTruth.status} (${groundTruthTime}ms)`);
        
        // Step 7: Test Error Handling
        console.log('\n❌ Step 7: Testing Error Handling...');
        const errorStart = Date.now();
        const errorTest = await makeRequest('http://localhost:8000/api/projects/nonexistent-id');
        const errorTime = Date.now() - errorStart;
        
        results.workflow.errorHandling = {
            status: errorTest.status,
            success: errorTest.status === 404, // Should return 404 for non-existent resource
            responseTime: errorTime,
            hasErrorMessage: errorTest.body.includes('error') || errorTest.body.includes('not found')
        };
        console.log(`${results.workflow.errorHandling.success ? '✅' : '❌'} Error Handling: ${errorTest.status} (${errorTime}ms)`);
        
        // Step 8: Test Frontend Integration
        console.log('\n🌐 Step 8: Testing Frontend Integration...');
        const frontendStart = Date.now();
        const frontend = await makeRequest('http://localhost:3000/');
        const frontendTime = Date.now() - frontendStart;
        
        results.workflow.frontend = {
            status: frontend.status,
            success: frontend.status === 200,
            responseTime: frontendTime,
            hasReact: frontend.body.includes('react') || frontend.body.includes('React'),
            hasConfig: frontend.body.includes('config.js'),
            hasHtml: frontend.body.includes('<html')
        };
        console.log(`${frontend.status === 200 ? '✅' : '❌'} Frontend: ${frontend.status} (${frontendTime}ms)`);
        
        // Calculate Performance Metrics
        const totalTime = Date.now() - startTime;
        results.performance = {
            totalTime,
            averageResponseTime: Math.round(
                (results.workflow.health?.responseTime || 0 + 
                 results.workflow.listProjects?.responseTime || 0 + 
                 results.workflow.createProject?.responseTime || 0) / 3
            ),
            slowestRequest: Math.max(
                results.workflow.health?.responseTime || 0,
                results.workflow.listProjects?.responseTime || 0,
                results.workflow.createProject?.responseTime || 0,
                results.workflow.frontend?.responseTime || 0
            )
        };
        
    } catch (error) {
        console.log('❌ Workflow error:', error.message);
        results.errors.push(error.message);
        results.success = false;
    }
    
    // Calculate Overall Success
    const workflowSteps = Object.values(results.workflow);
    const successfulSteps = workflowSteps.filter(step => step.success).length;
    const totalSteps = workflowSteps.length;
    
    results.summary = {
        totalSteps,
        successfulSteps,
        failedSteps: totalSteps - successfulSteps,
        successRate: totalSteps > 0 ? (successfulSteps / totalSteps * 100).toFixed(1) : 0,
        overallSuccess: successfulSteps === totalSteps && results.errors.length === 0
    };
    
    // Display Results
    console.log('\n' + '='.repeat(60));
    console.log('📊 COMPLETE WORKFLOW TEST RESULTS');
    console.log('='.repeat(60));
    console.log(`🕐 Total Time: ${results.performance.totalTime}ms`);
    console.log(`📊 Steps: ${successfulSteps}/${totalSteps} passed (${results.summary.successRate}%)`);
    console.log(`⚡ Average Response: ${results.performance.averageResponseTime}ms`);
    console.log(`🐌 Slowest Request: ${results.performance.slowestRequest}ms`);
    console.log(`${results.summary.overallSuccess ? '✅ PASS' : '❌ FAIL'} Overall: ${results.summary.overallSuccess ? 'All workflow steps completed successfully' : 'Some workflow steps failed'}`);
    
    if (results.errors.length > 0) {
        console.log('\n❌ Errors:');
        results.errors.forEach(error => console.log(`   • ${error}`));
    }
    
    console.log('\n📋 Step Details:');
    Object.entries(results.workflow).forEach(([step, result]) => {
        console.log(`   ${result.success ? '✅' : '❌'} ${step}: ${result.status} (${result.responseTime}ms)`);
    });
    
    return results;
}

// Contract Validation Test
async function testAPIContracts() {
    console.log('\n🔒 Testing API Contract Compliance...');
    
    const contracts = {
        projects: {
            list: { method: 'GET', path: '/api/projects', expectedFields: ['id', 'name', 'description'] },
            create: { method: 'POST', path: '/api/projects', requiredFields: ['name', 'cameraModel', 'signalType'] }
        },
        videos: {
            list: { method: 'GET', path: '/api/videos', expectedStructure: { videos: 'array', total: 'number' } }
        }
    };
    
    const contractResults = {};
    
    try {
        // Test Projects List Contract
        const projectsResponse = await makeRequest('http://localhost:8000/api/projects');
        if (projectsResponse.status === 200) {
            const projects = JSON.parse(projectsResponse.body);
            const hasRequiredFields = Array.isArray(projects) && 
                projects.length > 0 &&
                projects[0].hasOwnProperty('id') &&
                projects[0].hasOwnProperty('name');
            
            contractResults.projectsList = {
                passed: hasRequiredFields,
                message: hasRequiredFields ? 'Contract compliant' : 'Missing required fields'
            };
        }
        
        // Test Videos List Contract
        const videosResponse = await makeRequest('http://localhost:8000/api/videos');
        if (videosResponse.status === 200) {
            const videos = JSON.parse(videosResponse.body);
            const hasCorrectStructure = videos.hasOwnProperty('videos') &&
                videos.hasOwnProperty('total') &&
                Array.isArray(videos.videos);
            
            contractResults.videosList = {
                passed: hasCorrectStructure,
                message: hasCorrectStructure ? 'Contract compliant' : 'Incorrect response structure'
            };
        }
        
    } catch (error) {
        console.log('Contract validation error:', error.message);
    }
    
    console.log('📋 Contract Validation Results:');
    Object.entries(contractResults).forEach(([contract, result]) => {
        console.log(`   ${result.passed ? '✅' : '❌'} ${contract}: ${result.message}`);
    });
    
    return contractResults;
}

// Run Complete Test Suite
async function runCompleteValidation() {
    console.log('🏁 Starting Complete Integration Validation Suite...');
    console.log('=' * 80);
    
    const workflowResults = await testCompleteWorkflow();
    const contractResults = await testAPIContracts();
    
    const finalResults = {
        timestamp: new Date().toISOString(),
        workflow: workflowResults,
        contracts: contractResults,
        overallSuccess: workflowResults.summary.overallSuccess && 
                       Object.values(contractResults).every(r => r.passed)
    };
    
    console.log('\n💾 Saving complete validation results...');
    fs.writeFileSync('complete_workflow_validation.json', JSON.stringify(finalResults, null, 2));
    console.log('✅ Results saved to complete_workflow_validation.json');
    
    console.log('\n🏆 FINAL VALIDATION STATUS:');
    console.log(`${finalResults.overallSuccess ? '✅ PASS' : '❌ FAIL'} Complete system validation ${finalResults.overallSuccess ? 'PASSED' : 'FAILED'}`);
    
    return finalResults;
}

// Run the complete validation
if (require.main === module) {
    runCompleteValidation()
        .then(results => {
            process.exit(results.overallSuccess ? 0 : 1);
        })
        .catch(error => {
            console.error('❌ Validation suite failed:', error);
            process.exit(1);
        });
}

module.exports = { testCompleteWorkflow, testAPIContracts, runCompleteValidation };