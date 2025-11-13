import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Alert,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider,
  CircularProgress,
} from '@mui/material';
import {
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';

export interface GroundTruthValidationData {
  has_issues: boolean;
  videos_without_gt: Array<{
    video_id: string;
    video_name: string;
    reason: string;
  }>;
  videos_with_gt: Array<{
    video_id: string;
    video_name: string;
    detection_count: number;
  }>;
  summary: {
    total_videos: number;
    videos_with_ground_truth: number;
    videos_without_ground_truth: number;
    total_ground_truth_events: number;
  };
}

interface GroundTruthValidationWarningDialogProps {
  open: boolean;
  onClose: () => void;
  onStartAnyway: () => void;
  validationData: GroundTruthValidationData | null;
  loading: boolean;
}

const GroundTruthValidationWarningDialog: React.FC<GroundTruthValidationWarningDialogProps> = ({
  open,
  onClose,
  onStartAnyway,
  validationData,
  loading,
}) => {
  if (!open) return null;

  if (loading) {
    return (
      <Dialog
        open={open}
        onClose={onClose}
        maxWidth="sm"
        fullWidth
        aria-labelledby="gt-validation-loading-title"
        aria-describedby="gt-validation-loading-description"
      >
        <DialogTitle id="gt-validation-loading-title">
          Validating Ground Truth
        </DialogTitle>
        <DialogContent>
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              py: 4,
            }}
          >
            <CircularProgress size={48} sx={{ mb: 2 }} />
            <Typography
              id="gt-validation-loading-description"
              variant="body2"
              color="text.secondary"
              align="center"
            >
              Checking ground truth availability for selected videos...
            </Typography>
          </Box>
        </DialogContent>
      </Dialog>
    );
  }

  if (!validationData || !validationData.has_issues) {
    return null;
  }

  const { videos_without_gt, videos_with_gt, summary } = validationData;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      aria-labelledby="gt-validation-warning-title"
      aria-describedby="gt-validation-warning-description"
    >
      <DialogTitle
        id="gt-validation-warning-title"
        sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
      >
        <WarningIcon color="warning" />
        <Typography variant="h6" component="span">
          Ground Truth Validation Warning
        </Typography>
      </DialogTitle>

      <DialogContent>
        <Alert severity="warning" sx={{ mb: 3 }}>
          <Typography variant="body2" id="gt-validation-warning-description">
            Some videos are missing ground truth data. Starting the test without ground truth
            will limit result accuracy and validation capabilities.
          </Typography>
        </Alert>

        {/* Summary Statistics */}
        <Box sx={{ mb: 3, p: 2, bgcolor: 'background.paper', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
          <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600 }}>
            Summary
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, mt: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Total Videos:
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              {summary.total_videos}
            </Typography>

            <Typography variant="body2" color="success.main">
              With Ground Truth:
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 500, color: 'success.main' }}>
              {summary.videos_with_ground_truth} ({summary.total_ground_truth_events} events)
            </Typography>

            <Typography variant="body2" color="error.main">
              Missing Ground Truth:
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 500, color: 'error.main' }}>
              {summary.videos_without_ground_truth}
            </Typography>
          </Box>
        </Box>

        {/* Videos WITH Ground Truth */}
        {videos_with_gt.length > 0 && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'success.main' }}>
              <CheckCircleIcon fontSize="small" />
              Videos with Ground Truth ({videos_with_gt.length})
            </Typography>
            <List dense sx={{ bgcolor: 'background.paper', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
              {videos_with_gt.map((video, index) => (
                <React.Fragment key={video.video_id}>
                  <ListItem>
                    <ListItemIcon>
                      <CheckCircleIcon color="success" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText
                      primary={video.video_name}
                      secondary={`${video.detection_count} ground truth events available`}
                      primaryTypographyProps={{ variant: 'body2' }}
                      secondaryTypographyProps={{ variant: 'caption' }}
                    />
                  </ListItem>
                  {index < videos_with_gt.length - 1 && <Divider variant="inset" component="li" />}
                </React.Fragment>
              ))}
            </List>
          </Box>
        )}

        {/* Videos WITHOUT Ground Truth */}
        {videos_without_gt.length > 0 && (
          <Box>
            <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'error.main' }}>
              <ErrorIcon fontSize="small" />
              Videos Missing Ground Truth ({videos_without_gt.length})
            </Typography>
            <List dense sx={{ bgcolor: 'background.paper', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
              {videos_without_gt.map((video, index) => (
                <React.Fragment key={video.video_id}>
                  <ListItem>
                    <ListItemIcon>
                      <ErrorIcon color="error" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText
                      primary={video.video_name}
                      secondary={video.reason}
                      primaryTypographyProps={{ variant: 'body2' }}
                      secondaryTypographyProps={{ variant: 'caption', color: 'error' }}
                    />
                  </ListItem>
                  {index < videos_without_gt.length - 1 && <Divider variant="inset" component="li" />}
                </React.Fragment>
              ))}
            </List>
          </Box>
        )}

        <Alert severity="info" sx={{ mt: 3 }}>
          <Typography variant="body2">
            <strong>Recommendation:</strong> Upload ground truth data for all videos before starting
            the test to ensure accurate validation and latency measurement.
          </Typography>
        </Alert>
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button
          onClick={onClose}
          variant="outlined"
          aria-label="Cancel and go back to fix ground truth issues"
        >
          Cancel
        </Button>
        <Button
          onClick={onStartAnyway}
          variant="contained"
          color="warning"
          aria-label="Start test anyway despite missing ground truth"
        >
          Start Anyway
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default GroundTruthValidationWarningDialog;
