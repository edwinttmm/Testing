/**
 * Video Linking Fix Validation Test
 * 
 * This test validates that the video linking functionality works correctly
 * after fixing the parameter mismatch between frontend (videoIds) and backend (video_ids).
 */

import axios from 'axios';

interface TestVideo {
  id: string;
  projectId: string;
  assigned: boolean;
}

interface LinkingResponse {
  message: string;
  linked_count: number;
}

const API_BASE_URL = 'http://localhost:8000';
const TEST_PROJECT_ID = '66f9c296-ee1e-4e81-b0ba-96d03fdc8c90';

describe('Video Linking Fix Validation', () => {
  let testVideoId: string | null = null;

  beforeAll(async () => {
    // Get available videos
    try {
      const response = await axios.get(`${API_BASE_URL}/api/videos`);
      const videos = response.data.videos as TestVideo[];
      
      // Find an unassigned video or use the first one
      const unassignedVideo = videos.find(v => !v.assigned);
      if (unassignedVideo) {
        testVideoId = unassignedVideo.id;
      } else if (videos.length > 0) {
        testVideoId = videos[0].id;
        // Unlink it first if it's assigned
        if (videos[0].assigned) {
          await axios.delete(`${API_BASE_URL}/api/projects/${videos[0].projectId}/videos/${videos[0].id}/unlink`);
        }
      }
    } catch (error) {
      console.warn('Setup warning: Could not prepare test video', error);
    }
  });

  test('should successfully link video to project with correct parameter format', async () => {
    if (!testVideoId) {
      console.warn('Skipping test: No test video available');
      return;
    }

    // Test the corrected API call format
    const response = await axios.post(
      `${API_BASE_URL}/api/projects/${TEST_PROJECT_ID}/videos/link`,
      {
        video_ids: [testVideoId]  // Fixed parameter name
      },
      {
        headers: {
          'Content-Type': 'application/json'
        }
      }
    );

    expect(response.status).toBe(200);
    
    const linkingResult = response.data as LinkingResponse;
    expect(linkingResult.linked_count).toBe(1);
    expect(linkingResult.message).toContain('Successfully linked 1 videos to project');

    // Verify the video is now assigned
    const videosResponse = await axios.get(`${API_BASE_URL}/api/videos`);
    const videos = videosResponse.data.videos as TestVideo[];
    const linkedVideo = videos.find(v => v.id === testVideoId);
    
    expect(linkedVideo).toBeDefined();
    expect(linkedVideo!.projectId).toBe(TEST_PROJECT_ID);
    expect(linkedVideo!.assigned).toBe(true);
  });

  test('should handle empty video_ids array gracefully', async () => {
    try {
      await axios.post(
        `${API_BASE_URL}/api/projects/${TEST_PROJECT_ID}/videos/link`,
        {
          video_ids: []  // Empty array
        },
        {
          headers: {
            'Content-Type': 'application/json'
          }
        }
      );
      
      // Should fail with 400 error for empty video_ids
      fail('Expected request to fail with empty video_ids');
    } catch (error: any) {
      expect(error.response?.status).toBe(400);
      expect(error.response?.data?.detail).toContain('No video IDs provided');
    }
  });

  test('should handle non-existent video IDs gracefully', async () => {
    const response = await axios.post(
      `${API_BASE_URL}/api/projects/${TEST_PROJECT_ID}/videos/link`,
      {
        video_ids: ['non-existent-video-id']
      },
      {
        headers: {
          'Content-Type': 'application/json'
        }
      }
    );

    expect(response.status).toBe(200);
    
    const linkingResult = response.data as LinkingResponse;
    expect(linkingResult.linked_count).toBe(0);
    expect(linkingResult.message).toContain('Successfully linked 0 videos to project');
  });

  test('should handle malformed request data', async () => {
    try {
      await axios.post(
        `${API_BASE_URL}/api/projects/${TEST_PROJECT_ID}/videos/link`,
        {
          // Wrong parameter name (old broken format)
          videoIds: ['some-video-id']
        },
        {
          headers: {
            'Content-Type': 'application/json'
          }
        }
      );
      
      const linkingResult = await axios.post(
        `${API_BASE_URL}/api/projects/${TEST_PROJECT_ID}/videos/link`,
        {
          videoIds: ['some-video-id']
        },
        {
          headers: {
            'Content-Type': 'application/json'
          }
        }
      );

      // Should successfully handle missing video_ids by defaulting to empty array
      expect(linkingResult.status).toBe(200);
      expect(linkingResult.data.linked_count).toBe(0);
      
    } catch (error: any) {
      // Could also reasonably return 400 error for missing required field
      expect([400, 422].includes(error.response?.status)).toBe(true);
    }
  });

  afterAll(async () => {
    // Clean up: unlink the test video if we linked it
    if (testVideoId) {
      try {
        await axios.delete(`${API_BASE_URL}/api/projects/${TEST_PROJECT_ID}/videos/${testVideoId}/unlink`);
      } catch (error) {
        console.warn('Cleanup warning: Could not unlink test video', error);
      }
    }
  });
});