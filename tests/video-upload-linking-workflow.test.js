/**
 * Video Upload/Linking Workflow Test
 * Tests the comprehensive fixes for video upload and linking functionality
 */

const fs = require('fs');
const path = require('path');
const axios = require('axios');
const FormData = require('form-data');

// Test configuration
const API_BASE_URL = 'http://localhost:8000';
const TEST_VIDEO_PATH = path.join(__dirname, 'test-assets', 'sample-video.mp4');

// Create a sample video file for testing if it doesn't exist
function createSampleVideoFile() {
  const testAssetsDir = path.join(__dirname, 'test-assets');
  if (!fs.existsSync(testAssetsDir)) {
    fs.mkdirSync(testAssetsDir, { recursive: true });
  }
  
  if (!fs.existsSync(TEST_VIDEO_PATH)) {
    // Create a minimal MP4 file for testing (just header bytes)
    const mp4Header = Buffer.from([
      0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70, 0x69, 0x73, 0x6F, 0x6D,
      0x00, 0x00, 0x02, 0x00, 0x69, 0x73, 0x6F, 0x6D, 0x69, 0x73, 0x6F, 0x32,
      0x6D, 0x70, 0x34, 0x31, 0x00, 0x00, 0x00, 0x08, 0x66, 0x72, 0x65, 0x65
    ]);
    fs.writeFileSync(TEST_VIDEO_PATH, mp4Header);
  }
}

// Test helper functions
async function apiCall(method, endpoint, data = null, headers = {}) {
  try {
    const response = await axios({
      method,
      url: `${API_BASE_URL}${endpoint}`,
      data,
      headers,
      validateStatus: () => true // Accept all status codes
    });
    return response;
  } catch (error) {
    console.error(`API call failed: ${method} ${endpoint}`, error.message);
    throw error;
  }
}

async function createTestProject() {
  const projectData = {
    name: 'Test Project for Video Linking',
    description: 'Testing video upload and linking workflow',
    cameraModel: 'Test Camera',
    cameraView: 'side_view',
    signalType: 'gpio'
  };
  
  const response = await apiCall('POST', '/api/projects', projectData);
  if (response.status !== 200 && response.status !== 201) {
    throw new Error(`Failed to create test project: ${response.status} - ${JSON.stringify(response.data)}`);
  }
  
  return response.data;
}

async function uploadVideoToCentralStore() {
  const formData = new FormData();
  formData.append('file', fs.createReadStream(TEST_VIDEO_PATH));
  
  const response = await apiCall('POST', '/api/videos', formData, {
    ...formData.getHeaders(),
    'Content-Type': 'multipart/form-data'
  });
  
  if (response.status !== 200 && response.status !== 201) {
    throw new Error(`Failed to upload video to central store: ${response.status} - ${JSON.stringify(response.data)}`);
  }
  
  return response.data;
}

async function getAllVideosFromCentralStore() {
  const response = await apiCall('GET', '/api/videos?unassigned=true');
  if (response.status !== 200) {
    throw new Error(`Failed to get videos from central store: ${response.status} - ${JSON.stringify(response.data)}`);
  }
  
  return response.data;
}

async function linkVideosToProject(projectId, videoIds) {
  const response = await apiCall('POST', `/api/projects/${projectId}/videos/link`, {
    video_ids: videoIds
  });
  
  if (response.status !== 200) {
    throw new Error(`Failed to link videos to project: ${response.status} - ${JSON.stringify(response.data)}`);
  }
  
  return response.data;
}

async function getLinkedVideos(projectId) {
  const response = await apiCall('GET', `/api/projects/${projectId}/videos/linked`);
  if (response.status !== 200) {
    throw new Error(`Failed to get linked videos: ${response.status} - ${JSON.stringify(response.data)}`);
  }
  
  return response.data;
}

async function unlinkVideoFromProject(projectId, videoId) {
  const response = await apiCall('DELETE', `/api/projects/${projectId}/videos/${videoId}/unlink`);
  if (response.status !== 200) {
    throw new Error(`Failed to unlink video from project: ${response.status} - ${JSON.stringify(response.data)}`);
  }
  
  return response.data;
}

// Main test suite
async function runVideoWorkflowTests() {
  console.log('🚀 Starting Video Upload/Linking Workflow Tests...');
  
  let testProject = null;
  let uploadedVideo = null;
  
  try {
    // Setup
    console.log('📁 Creating test assets...');
    createSampleVideoFile();
    
    // Test 1: Create a test project
    console.log('📝 Test 1: Creating test project...');
    testProject = await createTestProject();
    console.log(`✅ Test project created: ${testProject.id}`);
    
    // Test 2: Upload video to central store (no project required)
    console.log('📤 Test 2: Uploading video to central store...');
    uploadedVideo = await uploadVideoToCentralStore();
    console.log(`✅ Video uploaded to central store: ${uploadedVideo.id}`);
    console.log(`   Filename: ${uploadedVideo.filename}`);
    console.log(`   Status: ${uploadedVideo.status}`);
    console.log(`   Project ID: ${uploadedVideo.projectId || 'None (central store)'}`);
    
    // Test 3: Verify video appears in central store
    console.log('📋 Test 3: Verifying video in central store...');
    const centralStoreVideos = await getAllVideosFromCentralStore();
    const foundVideo = centralStoreVideos.videos?.find(v => v.id === uploadedVideo.id);
    if (!foundVideo) {
      throw new Error('Uploaded video not found in central store');
    }
    console.log(`✅ Video found in central store (${centralStoreVideos.videos?.length || 0} unassigned videos)`);
    
    // Test 4: Link video to project
    console.log('🔗 Test 4: Linking video to project...');
    const linkResult = await linkVideosToProject(testProject.id, [uploadedVideo.id]);
    console.log(`✅ Video linked to project: ${linkResult.message}`);
    
    // Test 5: Verify video appears in project's linked videos
    console.log('📋 Test 5: Verifying linked videos...');
    const linkedVideos = await getLinkedVideos(testProject.id);
    const foundLinkedVideo = linkedVideos.find(v => v.id === uploadedVideo.id);
    if (!foundLinkedVideo) {
      throw new Error('Linked video not found in project videos');
    }
    console.log(`✅ Video found in project's linked videos (${linkedVideos.length} total)`);
    
    // Test 6: Verify video no longer appears as unassigned in central store
    console.log('📋 Test 6: Verifying video assignment...');
    const updatedCentralStore = await getAllVideosFromCentralStore();
    const stillUnassigned = updatedCentralStore.videos?.find(v => v.id === uploadedVideo.id);
    if (stillUnassigned) {
      throw new Error('Video still appears as unassigned after linking');
    }
    console.log('✅ Video no longer appears as unassigned');
    
    // Test 7: Unlink video from project
    console.log('🔓 Test 7: Unlinking video from project...');
    const unlinkResult = await unlinkVideoFromProject(testProject.id, uploadedVideo.id);
    console.log(`✅ Video unlinked from project: ${unlinkResult.message}`);
    
    // Test 8: Verify video returns to central store
    console.log('📋 Test 8: Verifying video returned to central store...');
    const finalCentralStore = await getAllVideosFromCentralStore();
    const backInCentralStore = finalCentralStore.videos?.find(v => v.id === uploadedVideo.id);
    if (!backInCentralStore) {
      throw new Error('Video did not return to central store after unlinking');
    }
    console.log('✅ Video successfully returned to central store');
    
    console.log('\n🎉 All tests passed! Video upload/linking workflow is working correctly.');
    
    return {
      success: true,
      results: {
        projectCreated: testProject.id,
        videoUploaded: uploadedVideo.id,
        centralStoreCount: finalCentralStore.videos?.length || 0,
        workflowComplete: true
      }
    };
    
  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
    console.error('Stack trace:', error.stack);
    
    return {
      success: false,
      error: error.message,
      stack: error.stack
    };
  } finally {
    // Cleanup (in a real test, you might want to clean up the test data)
    console.log('\n🧹 Test completed (cleanup may be needed manually)');
    if (testProject) {
      console.log(`   Test project ID: ${testProject.id}`);
    }
    if (uploadedVideo) {
      console.log(`   Uploaded video ID: ${uploadedVideo.id}`);
    }
  }
}

// Health check function
async function healthCheck() {
  try {
    const response = await apiCall('GET', '/health');
    return response.status === 200;
  } catch {
    return false;
  }
}

// Run tests if called directly
if (require.main === module) {
  (async () => {
    console.log('🔍 Performing health check...');
    const isHealthy = await healthCheck();
    if (!isHealthy) {
      console.error('❌ API health check failed. Make sure the backend is running on port 8000.');
      process.exit(1);
    }
    console.log('✅ API health check passed');
    
    const results = await runVideoWorkflowTests();
    process.exit(results.success ? 0 : 1);
  })();
}

module.exports = {
  runVideoWorkflowTests,
  healthCheck,
  createTestProject,
  uploadVideoToCentralStore,
  getAllVideosFromCentralStore,
  linkVideosToProject,
  getLinkedVideos,
  unlinkVideoFromProject
};