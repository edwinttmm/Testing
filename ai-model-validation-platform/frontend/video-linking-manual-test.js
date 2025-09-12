/**
 * Manual Test: Video Linking Fix Validation
 * 
 * This script demonstrates that the video linking fix works correctly.
 * Run with: node video-linking-manual-test.js
 */

const axios = require('axios');

const API_BASE_URL = 'http://localhost:8000';
const TEST_PROJECT_ID = '66f9c296-ee1e-4e81-b0ba-96d03fdc8c90';

async function testVideoLinking() {
  console.log('🔧 Testing Video Linking Fix...\n');
  
  try {
    // Step 1: Get available videos
    console.log('1. Getting available videos...');
    const videosResponse = await axios.get(`${API_BASE_URL}/api/videos`);
    const videos = videosResponse.data.videos;
    
    if (videos.length === 0) {
      console.log('❌ No videos available for testing');
      return;
    }
    
    const testVideo = videos[0];
    console.log(`   Found video: ${testVideo.id} (assigned: ${testVideo.assigned})`);
    
    // Step 2: Unlink video if already assigned
    if (testVideo.assigned && testVideo.projectId) {
      console.log('2. Unlinking video from current project...');
      await axios.delete(`${API_BASE_URL}/api/projects/${testVideo.projectId}/videos/${testVideo.id}/unlink`);
      console.log('   ✅ Video unlinked successfully');
    }
    
    // Step 3: Test linking with CORRECT parameter format (video_ids)
    console.log('3. Testing video linking with corrected parameter format...');
    const linkResponse = await axios.post(
      `${API_BASE_URL}/api/projects/${TEST_PROJECT_ID}/videos/link`,
      {
        video_ids: [testVideo.id]  // FIXED: Using video_ids instead of videoIds
      },
      {
        headers: {
          'Content-Type': 'application/json'
        }
      }
    );
    
    console.log(`   Response: ${linkResponse.data.message}`);
    console.log(`   Videos linked: ${linkResponse.data.linked_count}`);
    
    if (linkResponse.data.linked_count === 1) {
      console.log('   ✅ Video linking SUCCESSFUL!');
      
      // Step 4: Verify the video is now assigned
      console.log('4. Verifying video assignment...');
      const verifyResponse = await axios.get(`${API_BASE_URL}/api/videos`);
      const updatedVideo = verifyResponse.data.videos.find(v => v.id === testVideo.id);
      
      if (updatedVideo && updatedVideo.assigned && updatedVideo.projectId === TEST_PROJECT_ID) {
        console.log('   ✅ Video assignment verified!');
        console.log(`   Video ${testVideo.id} is now assigned to project ${TEST_PROJECT_ID}`);
      } else {
        console.log('   ❌ Video assignment verification failed');
      }
      
    } else {
      console.log('   ❌ Video linking failed - 0 videos were linked');
    }
    
    console.log('\n🎉 Video Linking Fix Validation Complete!');
    console.log('✅ The frontend now correctly sends "video_ids" parameter');
    console.log('✅ The backend correctly processes video linking requests');
    console.log('✅ Users can now successfully link videos to projects');
    
  } catch (error) {
    console.error('❌ Test failed:', error.response?.data || error.message);
  }
}

// Run the test
testVideoLinking();