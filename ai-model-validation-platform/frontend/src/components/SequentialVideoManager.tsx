import React, { useState, useCallback, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  LinearProgress,
  IconButton,
  Tooltip,
  Stack,
  Chip,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Switch,
  FormControlLabel,
  TextField,
  Grid,
  Divider,
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  SkipNext,
  SkipPrevious,
  Shuffle,
  Loop,
  Timeline,
  VideoLibrary,
  Speed,
  Sync,
  FiberManualRecord,
  Stop,
  Settings,
  List as ListIcon,
  GridView,
} from '@mui/icons-material';

import { VideoFile } from '../services/types';
import VideoAnnotationPlayer from './VideoAnnotationPlayer';
import { FixedGrid } from './ui/FixedUIComponents';

interface SequentialVideoManagerProps {
  videos: VideoFile[];
  onVideoChange?: (video: VideoFile, index: number) => void;
  onPlaybackComplete?: () => void;
  onProgress?: (progress: number) => void;
  autoAdvance?: boolean;
  loopPlayback?: boolean;
  randomOrder?: boolean;
  syncExternalSignals?: boolean;
  latencyMs?: number;
}

interface PlaybackState {
  currentIndex: number;
  isPlaying: boolean;
  currentVideo: VideoFile | null;
  playedVideos: string[];
  totalProgress: number;
  videoProgress: Record<string, number>;
  isRecording: boolean;
  playbackOrder: number[];
}

const SequentialVideoManager: React.FC<SequentialVideoManagerProps> = ({
  videos,
  onVideoChange,
  onPlaybackComplete,
  onProgress,
  autoAdvance = true,
  loopPlayback = false,
  randomOrder = false,
  syncExternalSignals = false,
  latencyMs = 100,
}) => {
  const [playbackState, setPlaybackState] = useState<PlaybackState>({
    currentIndex: 0,
    isPlaying: false,
    currentVideo: null,
    playedVideos: [],
    totalProgress: 0,
    videoProgress: {},
    isRecording: false,
    playbackOrder: [],
  });

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [viewMode, setViewMode] = useState<'player' | 'list'>('player');
  const [lastSyncTime, setLastSyncTime] = useState<number>(0);

  // Initialize playback order
  useEffect(() => {
    if (videos.length > 0) {
      const order = randomOrder 
        ? [...Array(videos.length).keys()].sort(() => Math.random() - 0.5)
        : [...Array(videos.length).keys()];
      
      setPlaybackState(prev => ({
        ...prev,
        playbackOrder: order,
        currentVideo: videos[order[0]],
        currentIndex: 0,
      }));
    }
  }, [videos, randomOrder]);

  const getCurrentVideo = useCallback(() => {
    if (playbackState.playbackOrder.length === 0) return null;
    const actualIndex = playbackState.playbackOrder[playbackState.currentIndex];
    return videos[actualIndex] || null;
  }, [videos, playbackState.playbackOrder, playbackState.currentIndex]);

  const advanceToNext = useCallback(() => {
    setPlaybackState(prev => {
      const nextIndex = prev.currentIndex + 1;
      
      if (nextIndex < prev.playbackOrder.length) {
        const actualIndex = prev.playbackOrder[nextIndex];
        const nextVideo = videos[actualIndex];
        
        onVideoChange?.(nextVideo, nextIndex);
        onProgress?.((nextIndex / prev.playbackOrder.length) * 100);
        
        return {
          ...prev,
          currentIndex: nextIndex,
          currentVideo: nextVideo,
          totalProgress: (nextIndex / prev.playbackOrder.length) * 100,
        };
      } else if (loopPlayback) {
        // Loop back to first video
        const firstVideo = videos[prev.playbackOrder[0]];
        onVideoChange?.(firstVideo, 0);
        onProgress?.(0);
        
        return {
          ...prev,
          currentIndex: 0,
          currentVideo: firstVideo,
          totalProgress: 0,
          playedVideos: [],
        };
      } else {
        // End of sequence
        onPlaybackComplete?.();
        
        return {
          ...prev,
          isPlaying: false,
          totalProgress: 100,
        };
      }
    });
  }, [videos, loopPlayback, onVideoChange, onProgress, onPlaybackComplete]);

  const goToPrevious = useCallback(() => {
    setPlaybackState(prev => {
      const prevIndex = Math.max(0, prev.currentIndex - 1);
      const actualIndex = prev.playbackOrder[prevIndex];
      const prevVideo = videos[actualIndex];
      
      onVideoChange?.(prevVideo, prevIndex);
      onProgress?.((prevIndex / prev.playbackOrder.length) * 100);
      
      return {
        ...prev,
        currentIndex: prevIndex,
        currentVideo: prevVideo,
        totalProgress: (prevIndex / prev.playbackOrder.length) * 100,
      };
    });
  }, [videos, onVideoChange, onProgress]);

  const jumpToVideo = useCallback((index: number) => {
    setPlaybackState(prev => {
      if (index >= 0 && index < prev.playbackOrder.length) {
        const actualIndex = prev.playbackOrder[index];
        const video = videos[actualIndex];
        
        onVideoChange?.(video, index);
        onProgress?.((index / prev.playbackOrder.length) * 100);
        
        return {
          ...prev,
          currentIndex: index,
          currentVideo: video,
          totalProgress: (index / prev.playbackOrder.length) * 100,
        };
      }
      return prev;
    });
  }, [videos, onVideoChange, onProgress]);

  const handleVideoEnd = useCallback(() => {
    // Mark current video as played
    const currentVideo = getCurrentVideo();
    if (currentVideo) {
      setPlaybackState(prev => ({
        ...prev,
        playedVideos: [...prev.playedVideos, currentVideo.id],
      }));
    }

    if (autoAdvance) {
      setTimeout(() => {
        advanceToNext();
      }, latencyMs);
    }
  }, [getCurrentVideo, autoAdvance, latencyMs, advanceToNext]);

  const handleTimeUpdate = useCallback((currentTime: number, frameNumber: number) => {
    const currentVideo = getCurrentVideo();
    if (currentVideo) {
      setPlaybackState(prev => ({
        ...prev,
        videoProgress: {
          ...prev.videoProgress,
          [currentVideo.id]: currentTime,
        },
      }));
    }
  }, [getCurrentVideo]);

  const handleSyncRequest = useCallback(() => {
    setLastSyncTime(Date.now());
  }, []);

  const toggleRecording = useCallback((isRecording: boolean) => {
    setPlaybackState(prev => ({ ...prev, isRecording }));
  }, []);

  const shuffleOrder = useCallback(() => {
    setPlaybackState(prev => {
      const newOrder = [...prev.playbackOrder].sort(() => Math.random() - 0.5);
      return {
        ...prev,
        playbackOrder: newOrder,
        currentIndex: 0,
        currentVideo: videos[newOrder[0]],
        totalProgress: 0,
      };
    });
  }, [videos]);

  const currentVideo = getCurrentVideo();

  return (
    <Box>
      {/* Control Header */}
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between">
            <Box>
              <Typography variant="h6">
                Sequential Playback
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Video {playbackState.currentIndex + 1} of {videos.length}
                {playbackState.isRecording && (
                  <Chip 
                    icon={<FiberManualRecord />} 
                    label="Recording" 
                    color="error" 
                    size="small" 
                    sx={{ ml: 1 }} 
                  />
                )}
              </Typography>
            </Box>

            <Stack direction="row" spacing={1}>
              <Tooltip title="Previous Video">
                <IconButton 
                  onClick={goToPrevious}
                  disabled={playbackState.currentIndex === 0}
                >
                  <SkipPrevious />
                </IconButton>
              </Tooltip>

              <Tooltip title="Next Video">
                <IconButton 
                  onClick={advanceToNext}
                  disabled={playbackState.currentIndex === videos.length - 1 && !loopPlayback}
                >
                  <SkipNext />
                </IconButton>
              </Tooltip>

              <Tooltip title="Shuffle Order">
                <IconButton onClick={shuffleOrder}>
                  <Shuffle />
                </IconButton>
              </Tooltip>

              <Tooltip title={viewMode === 'player' ? 'Show Video List' : 'Show Player'}>
                <IconButton onClick={() => setViewMode(prev => prev === 'player' ? 'list' : 'player')}>
                  {viewMode === 'player' ? <ListIcon /> : <GridView />}
                </IconButton>
              </Tooltip>

              <Tooltip title="Settings">
                <IconButton onClick={() => setSettingsOpen(true)}>
                  <Settings />
                </IconButton>
              </Tooltip>
            </Stack>
          </Stack>

          {/* Progress Bar */}
          <Box sx={{ mt: 2 }}>
            <LinearProgress 
              variant="determinate" 
              value={playbackState.totalProgress} 
              sx={{ height: 8, borderRadius: 4 }}
            />
            <Stack direction="row" justifyContent="space-between" sx={{ mt: 0.5 }}>
              <Typography variant="caption">
                Progress: {Math.round(playbackState.totalProgress)}%
              </Typography>
              <Typography variant="caption">
                Played: {playbackState.playedVideos.length} / {videos.length}
              </Typography>
            </Stack>
          </Box>
        </CardContent>
      </Card>

      {/* Main Content */}
      {viewMode === 'player' && currentVideo ? (
        <VideoAnnotationPlayer
          video={currentVideo}
          annotations={[]}
          annotationMode={false}
          frameRate={30}
          onVideoEnd={handleVideoEnd}
          onTimeUpdate={handleTimeUpdate}
          enableFullscreen={true}
          syncIndicator={syncExternalSignals}
          onSyncRequest={syncExternalSignals ? handleSyncRequest : (() => {})}
          recordingMode={playbackState.isRecording}
          onRecordingToggle={toggleRecording}
          externalTimeSync={syncExternalSignals ? lastSyncTime : undefined}
        />
      ) : (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Video Sequence ({videos.length} videos)
            </Typography>
            <List>
              {playbackState.playbackOrder.map((actualIndex, orderIndex) => {
                const video = videos[actualIndex];
                const isPlayed = playbackState.playedVideos.includes(video.id);
                const isCurrent = orderIndex === playbackState.currentIndex;
                const progress = playbackState.videoProgress[video.id] || 0;

                return (
                  <ListItem
                    key={video.id}
                    component="div"
                    onClick={() => jumpToVideo(orderIndex)}
                    sx={{
                      bgcolor: isCurrent ? 'action.selected' : 'transparent',
                      borderRadius: 1,
                      mb: 0.5,
                      cursor: 'pointer',
                      '&:hover': {
                        bgcolor: 'action.hover',
                      },
                    }}
                  >
                    <ListItemIcon>
                      {isCurrent ? (
                        <PlayArrow color="primary" />
                      ) : isPlayed ? (
                        <Timeline color="success" />
                      ) : (
                        <VideoLibrary color="disabled" />
                      )}
                    </ListItemIcon>
                    <ListItemText
                      primary={`${orderIndex + 1}. ${video.filename || video.name}`}
                      secondary={
                        <Box>
                          <Typography variant="caption" display="block">
                            Duration: {video.duration ? `${Math.round(video.duration)}s` : 'Unknown'}
                            {progress > 0 && ` • Played: ${Math.round(progress)}s`}
                          </Typography>
                          {progress > 0 && (
                            <LinearProgress 
                              variant="determinate" 
                              value={(progress / (video.duration || 1)) * 100}
                              sx={{ mt: 0.5, height: 4 }}
                            />
                          )}
                        </Box>
                      }
                    />
                    <ListItemSecondaryAction>
                      <Stack direction="row" spacing={0.5}>
                        {isPlayed && (
                          <Chip label="Played" color="success" size="small" />
                        )}
                        {isCurrent && (
                          <Chip label="Current" color="primary" size="small" />
                        )}
                      </Stack>
                    </ListItemSecondaryAction>
                  </ListItem>
                );
              })}
            </List>
          </CardContent>
        </Card>
      )}

      {/* Settings Dialog */}
      <Dialog open={settingsOpen} onClose={() => setSettingsOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Playback Settings</DialogTitle>
        <DialogContent>
          <FixedGrid container spacing={2} sx={{ mt: 1 }}>
            <FixedGrid xs={12}>
              <FormControlLabel
                control={<Switch checked={autoAdvance} disabled />}
                label="Auto Advance (controlled by parent)"
              />
            </FixedGrid>
            <FixedGrid xs={12}>
              <FormControlLabel
                control={<Switch checked={loopPlayback} disabled />}
                label="Loop Playback (controlled by parent)"
              />
            </FixedGrid>
            <FixedGrid xs={12}>
              <FormControlLabel
                control={<Switch checked={syncExternalSignals} disabled />}
                label="Sync External Signals (controlled by parent)"
              />
            </FixedGrid>
            <FixedGrid xs={12}>
              <TextField
                label="Advance Delay (ms)"
                type="number"
                value={latencyMs}
                disabled
                fullWidth
                helperText="Delay between video transitions (controlled by parent)"
              />
            </FixedGrid>
            <FixedGrid xs={12}>
              <Divider sx={{ my: 1 }} />
              <Typography variant="subtitle2" gutterBottom>
                Current Session Stats
              </Typography>
              <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                <FixedGrid container spacing={1}>
                  <FixedGrid xs={6}>
                    <Typography variant="caption" display="block">
                      Total Videos: {videos.length}
                    </Typography>
                  </FixedGrid>
                  <FixedGrid xs={6}>
                    <Typography variant="caption" display="block">
                      Videos Played: {playbackState.playedVideos.length}
                    </Typography>
                  </FixedGrid>
                  <FixedGrid xs={6}>
                    <Typography variant="caption" display="block">
                      Current Index: {playbackState.currentIndex + 1}
                    </Typography>
                  </FixedGrid>
                  <FixedGrid xs={6}>
                    <Typography variant="caption" display="block">
                      Progress: {Math.round(playbackState.totalProgress)}%
                    </Typography>
                  </FixedGrid>
                </FixedGrid>
              </Paper>
            </FixedGrid>
          </FixedGrid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSettingsOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SequentialVideoManager;