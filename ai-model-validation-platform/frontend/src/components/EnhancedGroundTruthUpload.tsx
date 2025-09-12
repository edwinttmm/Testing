import React, { useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Switch,
  FormControlLabel,
  Alert,
  Chip,
  Stack,
} from '@mui/material';
import {
  CloudUpload,
  Security,
  VerifiedUser,
} from '@mui/icons-material';
import SecureFileUpload from './SecureFileUpload';

interface EnhancedUploadFile {
  id: string;
  name: string;
  size: number;
  type: string;
  data: string; // base64 encoded
  secure: boolean;
}

// Use EnhancedUploadFile throughout this component to avoid conflicts
type UploadFile = EnhancedUploadFile;

interface EnhancedGroundTruthUploadProps {
  open: boolean;
  onClose: () => void;
  onUploadComplete: (files: UploadFile[]) => void;
  onUploadError: (error: string) => void;
  projectId?: string;
}

const EnhancedGroundTruthUpload: React.FC<EnhancedGroundTruthUploadProps> = ({
  open,
  onClose,
  onUploadComplete,
  onUploadError,
  projectId,
}) => {
  const [useSecureUpload, setUseSecureUpload] = useState(true);
  const [securityDetails, setSecurityDetails] = useState(true);

  const handleUploadComplete = useCallback((files: Array<{ id?: string; name: string; size: number; type: string; data?: string; secure?: boolean }>) => {
    // Convert files to EnhancedUploadFile format
    const enhancedFiles: EnhancedUploadFile[] = files.map(file => ({
      id: file.id || Date.now().toString(),
      name: file.name,
      size: file.size,
      type: file.type,
      data: file.data || '',
      secure: file.secure !== undefined ? file.secure : true
    }));
    onUploadComplete(enhancedFiles);
    onClose();
  }, [onUploadComplete, onClose]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Stack direction="row" alignItems="center" spacing={2}>
          <CloudUpload />
          <Typography variant="h6">
            Enhanced Secure Video Upload
          </Typography>
          <Chip
            icon={<Security />}
            label="Enterprise Security"
            color="primary"
            size="small"
          />
        </Stack>
      </DialogTitle>
      
      <DialogContent>
        <Box sx={{ mb: 3 }}>
          <Alert severity="info" sx={{ mb: 2 }}>
            This upload system includes comprehensive security validation:
            file signature verification, malware scanning, content analysis,
            and real-time threat detection.
          </Alert>
          
          <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={useSecureUpload}
                  onChange={(e) => setUseSecureUpload(e.target.checked)}
                />
              }
              label="Enable Security Validation"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={securityDetails}
                  onChange={(e) => setSecurityDetails(e.target.checked)}
                />
              }
              label="Show Security Details"
            />
          </Stack>

          {useSecureUpload ? (
            <SecureFileUpload
              onUploadComplete={handleUploadComplete}
              onUploadError={onUploadError}
              projectId={projectId}
              maxFiles={10}
              disabled={false}
              showSecurityDetails={securityDetails}
            />
          ) : (
            <Card sx={{ p: 3, textAlign: 'center', border: '2px dashed #ccc' }}>
              <Typography variant="h6" color="warning.main" gutterBottom>
                Security Validation Disabled
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Enable security validation for enterprise-grade protection
              </Typography>
            </Card>
          )}
        </Box>

        {useSecureUpload && (
          <Card sx={{ mt: 2, bgcolor: 'success.50' }}>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>
                Security Features Active:
              </Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                <Chip icon={<VerifiedUser />} label="File Signature Validation" size="small" />
                <Chip icon={<Security />} label="Malware Scanning" size="small" />
                <Chip icon={<Security />} label="Content Analysis" size="small" />
                <Chip icon={<Security />} label="Path Traversal Protection" size="small" />
                <Chip icon={<Security />} label="Rate Limiting" size="small" />
                <Chip icon={<Security />} label="Real-time Monitoring" size="small" />
              </Stack>
            </CardContent>
          </Card>
        )}
      </DialogContent>
      
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button 
          variant="contained" 
          startIcon={<CloudUpload />}
          disabled={!useSecureUpload}
        >
          Start Secure Upload
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default EnhancedGroundTruthUpload;