import React, { useState } from 'react';
import {
  Box,
  Button,
  Alert,
  CircularProgress,
  Typography,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControlLabel,
  Checkbox,
} from '@mui/material';
import {
  CheckCircle,
  Error as ErrorIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { VideoFile, VideoValidationStatus } from '../services/types';

interface VideoValidationControlsProps {
  video: VideoFile;
  onValidationComplete?: (videoId: string, status: string) => void;
}

const VideoValidationControls: React.FC<VideoValidationControlsProps> = ({
  video,
  onValidationComplete,
}) => {
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [notes, setNotes] = useState('');
  const [force, setForce] = useState(false);
  const [validationAction, setValidationAction] = useState<'validate' | 'invalidate'>('validate');

  const handleValidateVideo = async () => {
    try {
      setProcessing(true);
      setError(null);
      
      const endpoint = validationAction === 'validate' ? 'validate' : 'invalidate';
      const response = await fetch(`/api/videos/${video.id}/${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          notes,
          force,
        }),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }
      
      const result = await response.json();
      
      onValidationComplete?.(video.id, result.status);
      setDialogOpen(false);
      setNotes('');
      setForce(false);
      
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      console.error('Failed to validate video:', err);
      setError(errorMsg);
    } finally {
      setProcessing(false);
    }
  };

  const openValidationDialog = (action: 'validate' | 'invalidate') => {
    setValidationAction(action);
    setDialogOpen(true);
    setError(null);
  };

  const getStatusIcon = () => {
    switch (video.status) {
      case VideoValidationStatus.VALIDATED:
        return <CheckCircle color="success" />;
      case VideoValidationStatus.ANNOTATED:
        return <WarningIcon color="warning" />;
      case VideoValidationStatus.ERROR:
        return <ErrorIcon color="error" />;
      default:
        return null;
    }
  };

  const getStatusColor = (): "success" | "warning" | "error" | "default" => {
    switch (video.status) {
      case VideoValidationStatus.VALIDATED:
        return 'success';
      case VideoValidationStatus.ANNOTATED:
        return 'warning';
      case VideoValidationStatus.ERROR:
        return 'error';
      default:
        return 'default';
    }
  };

  const canValidate = () => {
    return (
      video.status === VideoValidationStatus.ANNOTATED &&
      video.ground_truth_generated &&
      !processing
    );
  };

  const canInvalidate = () => {
    return video.status === VideoValidationStatus.VALIDATED && !processing;
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
        {getStatusIcon()}
        <Chip
          label={`Status: ${video.status}`}
          color={getStatusColor()}
          size="small"
        />
      </Box>
      
      {error && (
        <Alert severity="error" sx={{ mb: 1 }}>
          {error}
        </Alert>
      )}
      
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        {canValidate() && (
          <Button
            size="small"
            variant="contained"
            color="success"
            startIcon={<CheckCircle />}
            onClick={() => openValidationDialog('validate')}
            disabled={processing}
          >
            Validate
          </Button>
        )}
        
        {canInvalidate() && (
          <Button
            size="small"
            variant="outlined"
            color="warning"
            startIcon={<WarningIcon />}
            onClick={() => openValidationDialog('invalidate')}
            disabled={processing}
          >
            Invalidate
          </Button>
        )}
      </Box>
      
      {video.status === VideoValidationStatus.ANNOTATED && !video.ground_truth_generated && (
        <Typography variant="caption" display="block" sx={{ mt: 0.5, color: 'warning.main' }}>
          ⚠️ Ground truth required for validation
        </Typography>
      )}
      
      {video.status === VideoValidationStatus.VALIDATED && (
        <Typography variant="caption" display="block" sx={{ mt: 0.5, color: 'success.main' }}>
          ✅ Video is validated and ready for testing
        </Typography>
      )}

      {/* Validation Dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          {validationAction === 'validate' ? 'Validate Video' : 'Invalidate Video'}
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 2 }}>
            {validationAction === 'validate'
              ? 'Confirm that this video meets validation criteria and is ready for testing.'
              : 'Revert this video back to completed status for further review.'
            }
          </Typography>
          
          <TextField
            fullWidth
            label="Notes (optional)"
            multiline
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            sx={{ mb: 2 }}
          />
          
          {(video.status !== VideoValidationStatus.ANNOTATED && validationAction === 'validate') ||
           (video.status !== VideoValidationStatus.VALIDATED && validationAction === 'invalidate') ? (
            <FormControlLabel
              control={
                <Checkbox
                  checked={force}
                  onChange={(e) => setForce(e.target.checked)}
                />
              }
              label="Force validation (bypass status checks)"
            />
          ) : null}
          
          {!video.ground_truth_generated && validationAction === 'validate' && (
            <Alert severity="warning" sx={{ mt: 1 }}>
              This video has no ground truth data. Check "Force validation" to proceed anyway.
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleValidateVideo}
            disabled={processing}
            variant="contained"
            color={validationAction === 'validate' ? 'success' : 'warning'}
            startIcon={processing ? <CircularProgress size={16} /> : null}
          >
            {processing
              ? 'Processing...'
              : validationAction === 'validate'
              ? 'Validate'
              : 'Invalidate'
            }
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default VideoValidationControls;