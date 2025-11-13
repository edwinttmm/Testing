import React from 'react';
import { Box, FormControl, InputLabel, Select, MenuItem, Typography, Chip } from '@mui/material';
import { VideoLibrary as VideoLibraryIcon } from '@mui/icons-material';

interface VideoSequenceSelectorProps {
  videos: Array<{
    id: string;
    name: string;
    order: number;
    status: 'pass' | 'fail';
    detectionCount?: number;
  }>;
  selectedVideo: string | null;
  onVideoChange: (event: any) => void;
}

export const VideoSequenceSelector: React.FC<VideoSequenceSelectorProps> = ({
  videos,
  selectedVideo,
  onVideoChange
}) => {
  if (!videos || videos.length === 0) {
    return null;
  }

  return (
    <Box sx={{ mb: 3, p: 2, bgcolor: 'background.paper', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
      <Box display="flex" alignItems="center" mb={2}>
        <VideoLibraryIcon sx={{ mr: 1, color: 'primary.main' }} />
        <Typography variant="h6">
          Multi-Video Sequence
        </Typography>
        <Chip
          label={`${videos.length} videos`}
          size="small"
          color="primary"
          sx={{ ml: 2 }}
        />
      </Box>

      <FormControl fullWidth>
        <InputLabel>Select Video</InputLabel>
        <Select
          value={selectedVideo || ''}
          onChange={onVideoChange}
          label="Select Video"
        >
          {videos.map((video, index) => (
            <MenuItem key={video.id} value={video.id}>
              <Box display="flex" alignItems="center" justifyContent="space-between" width="100%">
                <Typography>
                  {index + 1}. {video.name}
                </Typography>
                <Box display="flex" gap={1}>
                  {video.detectionCount !== undefined && (
                    <Chip
                      label={`${video.detectionCount} detections`}
                      size="small"
                      variant="outlined"
                    />
                  )}
                  <Chip
                    label={video.status.toUpperCase()}
                    size="small"
                    color={video.status === 'pass' ? 'success' : 'error'}
                  />
                </Box>
              </Box>
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </Box>
  );
};
