import React, { useMemo, useCallback, useState } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  LinearProgress,
  Chip,
  Stack,
  Paper,
  Grid,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
} from '@mui/material';
import {
  Check,
  CheckCircle,
  Warning,
  Info,
  Save,
  Publish,
  RestartAlt,
  Assignment,
  Timeline,
  Verified,
  Error as ErrorIcon,
} from '@mui/icons-material';
import { GroundTruthObject, VideoFile } from '../services/types';

interface ValidationWorkflowPanelProps {
  video: VideoFile;
  groundTruthObjects: GroundTruthObject[];
  isValidated: boolean;
  onValidationComplete: (validated: boolean) => void;
  onSaveProgress: () => void;
  onValidateAllFrame: () => void;
  onValidateAll: () => void;
  onExportValidated: () => void;
}

interface ValidationStats {
  totalObjects: number;
  validatedObjects: number;
  pendingObjects: number;
  validationProgress: number;
  framesCovered: number;
  vruTypeDistribution: Record<string, { total: number; validated: number }>;
  qualityScore: number;
  completionStatus: 'not_started' | 'in_progress' | 'ready_for_validation' | 'validated';
}

const ValidationWorkflowPanel: React.FC<ValidationWorkflowPanelProps> = ({
  video,
  groundTruthObjects,
  isValidated,
  onValidationComplete,
  onSaveProgress,
  onValidateAllFrame,
  onValidateAll,
  onExportValidated,
}) => {
  const [validationDialog, setValidationDialog] = useState(false);
  const [confirmationStep, setConfirmationStep] = useState<'review' | 'confirm' | 'complete'>('review');
  
  // Calculate comprehensive validation statistics
  const validationStats = useMemo<ValidationStats>(() => {
    const totalObjects = groundTruthObjects.length;
    const validatedObjects = groundTruthObjects.filter(obj => obj.validated).length;
    const pendingObjects = totalObjects - validatedObjects;
    const validationProgress = totalObjects > 0 ? (validatedObjects / totalObjects) * 100 : 0;
    
    // Frame coverage
    const uniqueFrames = new Set(groundTruthObjects.map(obj => obj.frameNumber));
    const framesCovered = uniqueFrames.size;
    
    // VRU type distribution
    const vruTypeDistribution = groundTruthObjects.reduce((acc, obj) => {
      if (!acc[obj.vruType]) {
        acc[obj.vruType] = { total: 0, validated: 0 };
      }
      acc[obj.vruType].total++;
      if (obj.validated) {
        acc[obj.vruType].validated++;
      }
      return acc;
    }, {} as Record<string, { total: number; validated: number }>);
    
    // Quality score based on various factors
    let qualityScore = 0;
    if (totalObjects > 0) {
      const validationRatio = validatedObjects / totalObjects;
      const frameSpread = framesCovered / Math.max(video.duration ? Math.floor(video.duration * 30) : 1, 1);
      const typeBalance = Object.keys(vruTypeDistribution).length / 5; // Max 5 VRU types
      
      qualityScore = Math.round((validationRatio * 0.6 + frameSpread * 0.3 + typeBalance * 0.1) * 100);
    }
    
    // Completion status
    let completionStatus: ValidationStats['completionStatus'] = 'not_started';
    if (isValidated) {
      completionStatus = 'validated';
    } else if (validationProgress === 100) {
      completionStatus = 'ready_for_validation';
    } else if (validationProgress > 0) {
      completionStatus = 'in_progress';
    }
    
    return {
      totalObjects,
      validatedObjects,
      pendingObjects,
      validationProgress,
      framesCovered,
      vruTypeDistribution,
      qualityScore,
      completionStatus,
    };
  }, [groundTruthObjects, isValidated, video]);
  
  // Validation requirements checklist
  const validationRequirements = useMemo(() => {
    const requirements = [
      {
        id: 'has_objects',
        title: 'Ground truth objects exist',
        description: 'Video contains at least one annotated VRU object',
        status: validationStats.totalObjects > 0 ? 'passed' : 'failed',
        critical: true,
      },
      {
        id: 'all_validated',
        title: 'All objects validated',
        description: 'Every ground truth object has been reviewed and validated',
        status: validationStats.validationProgress === 100 ? 'passed' : 'failed',
        critical: true,
      },
      {
        id: 'frame_coverage',
        title: 'Adequate frame coverage',
        description: 'Annotations span across multiple frames in the video',
        status: validationStats.framesCovered >= 5 ? 'passed' : 'warning',
        critical: false,
      },
      {
        id: 'vru_diversity',
        title: 'VRU type diversity',
        description: 'Multiple VRU types are represented (recommended)',
        status: Object.keys(validationStats.vruTypeDistribution).length >= 2 ? 'passed' : 'warning',
        critical: false,
      },
      {
        id: 'quality_score',
        title: 'Quality threshold met',
        description: 'Overall annotation quality score meets standards (≥70%)',
        status: validationStats.qualityScore >= 70 ? 'passed' : 'warning',
        critical: false,
      },
    ];
    
    return requirements;
  }, [validationStats]);
  
  const canValidate = validationRequirements
    .filter(req => req.critical)
    .every(req => req.status === 'passed');
  
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'passed': return 'success';
      case 'warning': return 'warning';
      case 'failed': return 'error';
      default: return 'default';
    }
  };
  
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'passed': return <CheckCircle />;
      case 'warning': return <Warning />;
      case 'failed': return <ErrorIcon />;
      default: return <Info />;
    }
  };
  
  const getCompletionStatusInfo = () => {
    switch (validationStats.completionStatus) {
      case 'not_started':
        return {
          color: 'default' as const,
          icon: <Assignment />,
          title: 'Not Started',
          description: 'Begin by creating ground truth annotations',
        };
      case 'in_progress':
        return {
          color: 'primary' as const,
          icon: <Timeline />,
          title: 'In Progress',
          description: `${validationStats.validationProgress.toFixed(1)}% validated`,
        };
      case 'ready_for_validation':
        return {
          color: 'success' as const,
          icon: <Check />,
          title: 'Ready for Validation',
          description: 'All objects validated - ready to mark video as validated',
        };
      case 'validated':
        return {
          color: 'success' as const,
          icon: <Verified />,
          title: 'Validated',
          description: 'Video validation complete',
        };
      default:
        return {
          color: 'default' as const,
          icon: <Info />,
          title: 'Unknown',
          description: '',
        };
    }
  };
  
  const handleValidationStart = useCallback(() => {
    setConfirmationStep('review');
    setValidationDialog(true);
  }, []);
  
  const handleValidationConfirm = useCallback(() => {
    setConfirmationStep('complete');
    onValidationComplete(true);
    setTimeout(() => {
      setValidationDialog(false);
      setConfirmationStep('review');
    }, 2000);
  }, [onValidationComplete]);
  
  const statusInfo = getCompletionStatusInfo();
  
  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Validation Workflow
        </Typography>
        
        {/* Validation Status */}
        <Box sx={{ mb: 3 }}>
          <Chip
            icon={statusInfo.icon}
            label={statusInfo.title}
            color={statusInfo.color}
            size="medium"
            sx={{ mb: 1 }}
          />
          <Typography variant="body2" color="text.secondary">
            {statusInfo.description}
          </Typography>
        </Box>
        
        {/* Validation Progress */}
        <Box sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            <Typography variant="body2" fontWeight="medium">
              Validation Progress
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {validationStats.validatedObjects} / {validationStats.totalObjects} objects
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={validationStats.validationProgress}
            sx={{ 
              height: 8, 
              borderRadius: 4,
              backgroundColor: '#f0f0f0',
              '& .MuiLinearProgress-bar': {
                borderRadius: 4,
              },
            }}
          />
          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
            {validationStats.validationProgress.toFixed(1)}% complete
          </Typography>
        </Box>
        
        {/* Validation Statistics */}
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={4}>
            <Paper sx={{ p: 1.5, textAlign: 'center' }}>
              <Typography variant="h4" color="primary.main">
                {validationStats.totalObjects}
              </Typography>
              <Typography variant="caption">Total Objects</Typography>
            </Paper>
          </Grid>
          <Grid item xs={4}>
            <Paper sx={{ p: 1.5, textAlign: 'center' }}>
              <Typography variant="h4" color="success.main">
                {validationStats.validatedObjects}
              </Typography>
              <Typography variant="caption">Validated</Typography>
            </Paper>
          </Grid>
          <Grid item xs={4}>
            <Paper sx={{ p: 1.5, textAlign: 'center' }}>
              <Typography variant="h4" color="warning.main">
                {validationStats.pendingObjects}
              </Typography>
              <Typography variant="caption">Pending</Typography>
            </Paper>
          </Grid>
        </Grid>
        
        {/* Quality Metrics */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="body2" fontWeight="medium" gutterBottom>
            Quality Metrics
          </Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Chip
              label={`${validationStats.framesCovered} frames covered`}
              size="small"
              variant="outlined"
            />
            <Chip
              label={`${Object.keys(validationStats.vruTypeDistribution).length} VRU types`}
              size="small"
              variant="outlined"
            />
            <Chip
              label={`Quality: ${validationStats.qualityScore}%`}
              size="small"
              color={validationStats.qualityScore >= 70 ? 'success' : 'warning'}
              variant={validationStats.qualityScore >= 70 ? 'filled' : 'outlined'}
            />
          </Stack>
        </Box>
        
        {/* VRU Type Breakdown */}
        {Object.keys(validationStats.vruTypeDistribution).length > 0 && (
          <Box sx={{ mb: 3 }}>
            <Typography variant="body2" fontWeight="medium" gutterBottom>
              VRU Type Validation
            </Typography>
            <Stack spacing={1}>
              {Object.entries(validationStats.vruTypeDistribution).map(([vruType, stats]) => (
                <Box key={vruType} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="body2" sx={{ minWidth: 100, textTransform: 'capitalize' }}>
                    {vruType}:
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={(stats.validated / stats.total) * 100}
                    sx={{ flexGrow: 1, height: 6, borderRadius: 3 }}
                  />
                  <Typography variant="caption" color="text.secondary" sx={{ minWidth: 50 }}>
                    {stats.validated}/{stats.total}
                  </Typography>
                </Box>
              ))}
            </Stack>
          </Box>
        )}
        
        {/* Validation Requirements Checklist */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="body2" fontWeight="medium" gutterBottom>
            Validation Requirements
          </Typography>
          <List dense>
            {validationRequirements.map((req) => (
              <ListItem key={req.id} sx={{ px: 0 }}>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  {React.cloneElement(getStatusIcon(req.status), {
                    color: getStatusColor(req.status),
                    fontSize: 'small',
                  })}
                </ListItemIcon>
                <ListItemText
                  primary={req.title}
                  secondary={req.description}
                  primaryTypographyProps={{ variant: 'body2' }}
                  secondaryTypographyProps={{ variant: 'caption' }}
                />
                {req.critical && (
                  <Chip label="Required" size="small" color="error" variant="outlined" />
                )}
              </ListItem>
            ))}
          </List>
        </Box>
        
        <Divider sx={{ my: 2 }} />
        
        {/* Action Buttons */}
        <Stack spacing={1}>
          {!isValidated && (
            <>
              <Button
                variant="contained"
                fullWidth
                onClick={handleValidationStart}
                disabled={!canValidate}
                startIcon={<Verified />}
                size="large"
              >
                Mark Video as Validated
              </Button>
              
              {!canValidate && (
                <Alert severity="warning" sx={{ mt: 1 }}>
                  Complete all required validation steps before marking video as validated.
                </Alert>
              )}
            </>
          )}
          
          {isValidated && (
            <Alert severity="success" icon={<Verified />}>
              <Typography variant="body2" fontWeight="medium">
                Video Validation Complete
              </Typography>
              <Typography variant="caption">
                This video is ready for use in testing projects.
              </Typography>
            </Alert>
          )}
          
          <Button
            variant="outlined"
            fullWidth
            onClick={onValidateAll}
            startIcon={<CheckCircle />}
            disabled={validationStats.pendingObjects === 0}
          >
            Validate All Remaining ({validationStats.pendingObjects})
          </Button>
          
          <Button
            variant="outlined"
            fullWidth
            onClick={onSaveProgress}
            startIcon={<Save />}
          >
            Save Progress
          </Button>
          
          <Button
            variant="outlined"
            fullWidth
            onClick={onExportValidated}
            startIcon={<Publish />}
            disabled={validationStats.validatedObjects === 0}
          >
            Export Validated Annotations
          </Button>
        </Stack>
      </CardContent>
      
      {/* Validation Confirmation Dialog */}
      <Dialog 
        open={validationDialog} 
        onClose={() => setValidationDialog(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          {confirmationStep === 'review' && 'Review Video Validation'}
          {confirmationStep === 'confirm' && 'Confirm Video Validation'}
          {confirmationStep === 'complete' && 'Validation Complete!'}
        </DialogTitle>
        
        <DialogContent>
          {confirmationStep === 'review' && (
            <Box>
              <Typography gutterBottom>
                You are about to mark this video as <strong>"Validated"</strong> according to PRD Module 1.3 requirements.
              </Typography>
              
              <Alert severity="info" sx={{ my: 2 }}>
                Once validated, this video will be locked for editing and made available for testing projects.
              </Alert>
              
              <Typography variant="h6" gutterBottom sx={{ mt: 3 }}>
                Validation Summary
              </Typography>
              
              <Grid container spacing={2} sx={{ mb: 2 }}>
                <Grid item xs={6}>
                  <Paper sx={{ p: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      Total Objects
                    </Typography>
                    <Typography variant="h4">
                      {validationStats.totalObjects}
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={6}>
                  <Paper sx={{ p: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      Validated Objects
                    </Typography>
                    <Typography variant="h4" color="success.main">
                      {validationStats.validatedObjects}
                    </Typography>
                  </Paper>
                </Grid>
              </Grid>
              
              <Typography variant="body2" gutterBottom>
                <strong>Quality Score:</strong> {validationStats.qualityScore}%
              </Typography>
              <Typography variant="body2" gutterBottom>
                <strong>Frame Coverage:</strong> {validationStats.framesCovered} frames
              </Typography>
              <Typography variant="body2" gutterBottom>
                <strong>VRU Types:</strong> {Object.keys(validationStats.vruTypeDistribution).join(', ')}
              </Typography>
            </Box>
          )}
          
          {confirmationStep === 'confirm' && (
            <Box sx={{ textAlign: 'center', py: 3 }}>
              <CheckCircle sx={{ fontSize: 64, color: 'success.main', mb: 2 }} />
              <Typography variant="h6" gutterBottom>
                Final Confirmation
              </Typography>
              <Typography variant="body1" color="text.secondary">
                This action will permanently mark the video as validated and lock it for editing.
              </Typography>
            </Box>
          )}
          
          {confirmationStep === 'complete' && (
            <Box sx={{ textAlign: 'center', py: 3 }}>
              <Verified sx={{ fontSize: 64, color: 'success.main', mb: 2 }} />
              <Typography variant="h5" gutterBottom color="success.main">
                Video Validation Complete!
              </Typography>
              <Typography variant="body1" color="text.secondary">
                {video.filename} has been successfully validated and is now ready for testing projects.
              </Typography>
            </Box>
          )}
        </DialogContent>
        
        <DialogActions>
          {confirmationStep === 'review' && (
            <>
              <Button onClick={() => setValidationDialog(false)}>
                Cancel
              </Button>
              <Button
                variant="contained"
                onClick={() => setConfirmationStep('confirm')}
                startIcon={<Check />}
              >
                Continue to Confirmation
              </Button>
            </>
          )}
          
          {confirmationStep === 'confirm' && (
            <>
              <Button onClick={() => setConfirmationStep('review')}>
                Back to Review
              </Button>
              <Button
                variant="contained"
                color="success"
                onClick={handleValidationConfirm}
                startIcon={<Verified />}
              >
                Confirm Validation
              </Button>
            </>
          )}
          
          {confirmationStep === 'complete' && (
            <Button
              variant="contained"
              onClick={() => setValidationDialog(false)}
            >
              Close
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Card>
  );
};

export default ValidationWorkflowPanel;