import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Box, CircularProgress, Alert, Typography } from '@mui/material';
import AnnotationValidationInterface from '../components/AnnotationValidationInterface';
import { VideoFile, GroundTruthAnnotation } from '../services/types';
import { apiService } from '../services/api';
import { getErrorMessage } from '../utils/errorUtils';

const AnnotationValidation: React.FC = () => {
  const { videoId } = useParams<{ videoId: string }>();
  const navigate = useNavigate();
  
  const [video, setVideo] = useState<VideoFile | null>(null);
  const [annotations, setAnnotations] = useState<GroundTruthAnnotation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Load video and annotations
  useEffect(() => {
    if (!videoId) {
      setError('No video ID provided');
      setLoading(false);
      return;
    }
    
    const loadVideoAndAnnotations = async () => {
      try {
        setLoading(true);
        setError(null);
        
        // Load video details
        const videoData = await apiService.getVideo(videoId);
        setVideo(videoData);
        
        // Load existing annotations
        const annotationsData = await apiService.getAnnotations(videoId);
        setAnnotations(annotationsData);
        
      } catch (err) {
        const errorMessage = getErrorMessage(err);
        console.error('Failed to load video and annotations:', errorMessage);
        setError(`Failed to load video and annotations: ${errorMessage}`);
      } finally {
        setLoading(false);
      }
    };
    
    loadVideoAndAnnotations();
  }, [videoId]);
  
  const handleValidationComplete = useCallback(async (validated: boolean) => {
    if (!video) return;
    
    try {
      // Update video validation status
      await apiService.validateVideo(video.id, validated);
      
      // Navigate back to ground truth page
      navigate('/ground-truth', { 
        state: { 
          message: `Video "${video.filename}" has been ${validated ? 'validated' : 'marked as pending'}` 
        }
      });
      
    } catch (err) {
      console.error('Failed to update validation status:', err);
      setError(`Failed to update validation status: ${getErrorMessage(err)}`);
    }
  }, [video, navigate]);
  
  const handleClose = useCallback(() => {
    navigate('/ground-truth');
  }, [navigate]);
  
  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          gap: 2,
        }}
      >
        <CircularProgress size={60} />
        <Typography variant="h6" color="text.secondary">
          Loading annotation validation interface...
        </Typography>
      </Box>
    );
  }
  
  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
        <Typography variant="body1">
          Please try refreshing the page or go back to the ground truth management page.
        </Typography>
      </Box>
    );
  }
  
  if (!video) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning" sx={{ mb: 2 }}>
          Video not found
        </Alert>
        <Typography variant="body1">
          The requested video could not be found. It may have been deleted or moved.
        </Typography>
      </Box>
    );
  }
  
  return (
    <AnnotationValidationInterface
      video={video}
      initialAnnotations={annotations}
      onValidationComplete={handleValidationComplete}
      onClose={handleClose}
    />
  );
};

export default AnnotationValidation;