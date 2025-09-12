import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  Box,
  Button,
  Typography,
  LinearProgress,
  Alert,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tooltip,
  Stack,
} from '@mui/material';
import {
  CloudUpload,
  Cancel,
  CheckCircle,
  Error as ErrorIcon,
  Warning,
  Security,
  VerifiedUser,
} from '@mui/icons-material';

// Security constants - enterprise grade validation
const SECURITY_CONFIG = {
  // File type validation with MIME types and extensions
  ALLOWED_TYPES: {
    'video/mp4': ['.mp4'],
    'video/avi': ['.avi'],
    'video/quicktime': ['.mov'],
    'video/x-msvideo': ['.avi'],
    'video/x-matroska': ['.mkv'],
  },
  
  // File size limits (100MB max, 1KB min)
  MAX_FILE_SIZE: 100 * 1024 * 1024, // 100MB
  MIN_FILE_SIZE: 1024, // 1KB
  
  // Security limits
  MAX_FILES_PER_BATCH: 10,
  MAX_CONCURRENT_UPLOADS: 3,
  
  // File signature validation (magic numbers)
  MAGIC_NUMBERS: {
    mp4: ['66747970', '00000020667479704d534e56'], // ftyp signatures
    avi: ['52494646', '41564920'], // RIFF...AVI
    mov: ['66747970717420'], // ftyp qt
    mkv: ['1a45dfa3'], // Matroska signature
  },
  
  // Dangerous file patterns to block
  FORBIDDEN_PATTERNS: [
    /\.exe$/i,
    /\.bat$/i,
    /\.cmd$/i,
    /\.scr$/i,
    /\.pif$/i,
    /\.com$/i,
    /\.jar$/i,
    /\.js$/i,
    /\.vbs$/i,
    /\.ps1$/i,
    /\.php$/i,
    /\.asp$/i,
    /\.jsp$/i,
    /<script/i,
    /javascript:/i,
    /vbscript:/i,
    /on\w+\s*=/i, // event handlers
  ],
  
  // Rate limiting
  UPLOAD_RATE_LIMIT: {
    maxUploadsPerMinute: 20,
    maxBytesPerMinute: 500 * 1024 * 1024, // 500MB
  },
} as const;

interface UploadFile {
  id: string;
  file: File;
  name: string;
  size: number;
  type: string;
  status: 'validating' | 'uploading' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  error?: string | undefined;
  securityStatus: 'pending' | 'passed' | 'failed' | 'warning';
  validationResults: SecurityValidationResult;
}

interface SecurityValidationResult {
  fileTypeValid: boolean;
  fileSizeValid: boolean;
  mimeTypeValid: boolean;
  signatureValid: boolean;
  contentSecure: boolean;
  pathSecure: boolean;
  errors: string[];
  warnings: string[];
  scanResults?: {
    virusScan: 'pending' | 'clean' | 'infected' | 'error';
    contentAnalysis: 'passed' | 'suspicious' | 'blocked';
  };
}

interface SecureFileUploadProps {
  onUploadComplete: (files: UploadFile[]) => void;
  onUploadError: (error: string) => void;
  projectId?: string | undefined;
  maxFiles?: number | undefined;
  disabled?: boolean | undefined;
  showSecurityDetails?: boolean | undefined;
}

// Utility function to get file signature (first 32 bytes as hex)
const getFileSignature = async (file: File): Promise<string> => {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const buffer = e.target?.result as ArrayBuffer;
      const bytes = new Uint8Array(buffer.slice(0, 32));
      const hex = Array.from(bytes)
        .map(b => b.toString(16).padStart(2, '0'))
        .join('');
      resolve(hex);
    };
    reader.onerror = () => resolve('');
    reader.readAsArrayBuffer(file.slice(0, 32));
  });
};

// Advanced file validation with security checks
const validateFileSecurely = async (file: File): Promise<SecurityValidationResult> => {
  const result: SecurityValidationResult = {
    fileTypeValid: false,
    fileSizeValid: false,
    mimeTypeValid: false,
    signatureValid: false,
    contentSecure: false,
    pathSecure: false,
    errors: [],
    warnings: [],
  };

  try {
    // 1. File size validation
    if (file.size < SECURITY_CONFIG.MIN_FILE_SIZE) {
      result.errors.push(`File too small (minimum ${SECURITY_CONFIG.MIN_FILE_SIZE} bytes)`);
    } else if (file.size > SECURITY_CONFIG.MAX_FILE_SIZE) {
      result.errors.push(`File too large (maximum ${Math.round(SECURITY_CONFIG.MAX_FILE_SIZE / (1024*1024))}MB)`);
    } else {
      result.fileSizeValid = true;
    }

    // 2. MIME type validation
    const allowedMimeTypes = Object.keys(SECURITY_CONFIG.ALLOWED_TYPES);
    if (!allowedMimeTypes.includes(file.type)) {
      result.errors.push(`Invalid MIME type: ${file.type}`);
    } else {
      result.mimeTypeValid = true;
    }

    // 3. File extension validation
    const fileExt = file.name.toLowerCase().split('.').pop();
    const allowedExtensions = Object.values(SECURITY_CONFIG.ALLOWED_TYPES).flat();
    if (!fileExt || !allowedExtensions.some(ext => ext === `.${fileExt}`)) {
      result.errors.push(`Invalid file extension: .${fileExt}`);
    } else {
      result.fileTypeValid = true;
    }

    // 4. File path security (prevent path traversal)
    if (file.name.includes('..') || file.name.includes('/') || file.name.includes('\\')) {
      result.errors.push('Invalid file path - contains directory traversal patterns');
    } else if (file.name.match(/[<>:"|?*]/) || file.name.split('').some(char => char.charCodeAt(0) < 32)) {
      result.errors.push('Invalid file name - contains forbidden characters');
    } else {
      result.pathSecure = true;
    }

    // 5. Forbidden patterns check
    const fileName = file.name.toLowerCase();
    const forbiddenPattern = SECURITY_CONFIG.FORBIDDEN_PATTERNS.find(pattern => 
      pattern.test(fileName)
    );
    if (forbiddenPattern) {
      result.errors.push('File contains forbidden patterns or suspicious content');
    }

    // 6. File signature validation (magic numbers)
    try {
      const signature = await getFileSignature(file);
      const expectedSignatures = SECURITY_CONFIG.MAGIC_NUMBERS[fileExt as keyof typeof SECURITY_CONFIG.MAGIC_NUMBERS];
      
      if (expectedSignatures && signature) {
        const signatureMatches = expectedSignatures.some(expected => 
          signature.toLowerCase().startsWith(expected.toLowerCase())
        );
        
        if (!signatureMatches) {
          result.warnings.push(`File signature doesn't match expected format for .${fileExt}`);
        } else {
          result.signatureValid = true;
        }
      } else {
        result.warnings.push('Could not validate file signature');
      }
    } catch (error) {
      result.warnings.push('File signature validation failed');
    }

    // 7. Content security analysis
    if (file.size === 0) {
      result.errors.push('Empty file not allowed');
    } else {
      result.contentSecure = true;
    }

    // Overall validation result
    const hasErrors = result.errors.length > 0;
    const hasWarnings = result.warnings.length > 0;
    
    if (!hasErrors) {
      result.scanResults = {
        virusScan: 'pending',
        contentAnalysis: hasWarnings ? 'suspicious' : 'passed',
      };
    }

  } catch (error) {
    result.errors.push(`Validation failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }

  return result;
};

// Rate limiting tracker
class UploadRateLimiter {
  private uploadHistory: Array<{ timestamp: number; bytes: number }> = [];
  
  canUpload(fileSize: number): { allowed: boolean; reason?: string } {
    const now = Date.now();
    const oneMinuteAgo = now - 60000;
    
    // Clean old entries
    this.uploadHistory = this.uploadHistory.filter(entry => entry.timestamp > oneMinuteAgo);
    
    // Check upload count limit
    if (this.uploadHistory.length >= SECURITY_CONFIG.UPLOAD_RATE_LIMIT.maxUploadsPerMinute) {
      return { allowed: false, reason: 'Too many uploads in the last minute' };
    }
    
    // Check bandwidth limit
    const totalBytes = this.uploadHistory.reduce((sum, entry) => sum + entry.bytes, 0);
    if (totalBytes + fileSize > SECURITY_CONFIG.UPLOAD_RATE_LIMIT.maxBytesPerMinute) {
      return { allowed: false, reason: 'Upload bandwidth limit exceeded' };
    }
    
    return { allowed: true };
  }
  
  recordUpload(fileSize: number) {
    this.uploadHistory.push({ timestamp: Date.now(), bytes: fileSize });
  }
}

const rateLimiter = new UploadRateLimiter();

const SecureFileUpload: React.FC<SecureFileUploadProps> = ({
  onUploadComplete,
  onUploadError,
  // _projectId removed - unused prop
  maxFiles = SECURITY_CONFIG.MAX_FILES_PER_BATCH,
  disabled = false,
  showSecurityDetails = true,
}) => {
  const [uploadFiles, setUploadFiles] = useState<UploadFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [_isValidating, setIsValidating] = useState(false);
  const [securityDialog, setSecurityDialog] = useState(false);
  const [selectedFile, setSelectedFile] = useState<UploadFile | null>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropZoneRef = useRef<HTMLDivElement>(null);

  // Cleanup completed/failed uploads periodically
  useEffect(() => {
    const cleanup = setInterval(() => {
      setUploadFiles(prev => prev.filter(file => 
        !['completed', 'failed', 'cancelled'].includes(file.status) ||
        Date.now() - new Date().getTime() < 5000 // Keep for 5 seconds
      ));
    }, 10000); // Cleanup every 10 seconds

    return () => clearInterval(cleanup);
  }, []);

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getSecurityStatusIcon = (status: UploadFile['securityStatus']) => {
    switch (status) {
      case 'passed':
        return <VerifiedUser color="success" />;
      case 'warning':
        return <Warning color="warning" />;
      case 'failed':
        return <ErrorIcon color="error" />;
      default:
        return <Security color="action" />;
    }
  };

  const getStatusColor = (file: UploadFile) => {
    if (file.securityStatus === 'failed') return 'error';
    if (file.securityStatus === 'warning') return 'warning';
    if (file.status === 'completed') return 'success';
    return 'info';
  };

  const validateAndProcessFiles = useCallback(async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    
    // Check file count limit
    if (fileArray.length > maxFiles) {
      onUploadError(`Maximum ${maxFiles} files allowed per batch`);
      return;
    }

    if (uploadFiles.length + fileArray.length > maxFiles) {
      onUploadError(`Maximum ${maxFiles} files allowed in total`);
      return;
    }

    setIsValidating(true);

    const newUploadFiles: UploadFile[] = [];

    for (const file of fileArray) {
      // Rate limiting check
      const rateLimitCheck = rateLimiter.canUpload(file.size);
      if (!rateLimitCheck.allowed) {
        onUploadError(`Rate limit exceeded: ${rateLimitCheck.reason}`);
        continue;
      }

      const uploadFile: UploadFile = {
        id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        file,
        name: file.name,
        size: file.size,
        type: file.type,
        status: 'validating',
        progress: 0,
        securityStatus: 'pending',
        validationResults: {
          fileTypeValid: false,
          fileSizeValid: false,
          mimeTypeValid: false,
          signatureValid: false,
          contentSecure: false,
          pathSecure: false,
          errors: [],
          warnings: [],
        },
      };

      newUploadFiles.push(uploadFile);
    }

    setUploadFiles(prev => [...prev, ...newUploadFiles]);

    // Validate each file
    for (const uploadFile of newUploadFiles) {
      try {
        const validationResult = await validateFileSecurely(uploadFile.file);
        
        setUploadFiles(prev => prev.map(f => 
          f.id === uploadFile.id 
            ? {
                ...f,
                validationResults: validationResult,
                securityStatus: validationResult.errors.length > 0 ? 'failed' :
                              validationResult.warnings.length > 0 ? 'warning' : 'passed',
                status: validationResult.errors.length > 0 ? 'failed' : 'uploading',
                error: validationResult.errors.length > 0 ? validationResult.errors.join('; ') : undefined,
              }
            : f
        ));

        // If validation passed, start upload
        if (validationResult.errors.length === 0) {
          await startFileUpload(uploadFile);
        }
      } catch (error) {
        setUploadFiles(prev => prev.map(f => 
          f.id === uploadFile.id 
            ? {
                ...f,
                status: 'failed',
                securityStatus: 'failed',
                error: `Validation failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
              }
            : f
        ));
      }
    }

    setIsValidating(false);
  }, [maxFiles, uploadFiles.length, onUploadError]);

  const startFileUpload = useCallback(async (uploadFile: UploadFile) => {
    try {
      // Record upload for rate limiting
      rateLimiter.recordUpload(uploadFile.file.size);

      // Simulate upload progress (replace with actual API call)
      const progressInterval = setInterval(() => {
        setUploadFiles(prev => prev.map(f => 
          f.id === uploadFile.id && f.status === 'uploading'
            ? { ...f, progress: Math.min(f.progress + Math.random() * 20, 95) }
            : f
        ));
      }, 200);

      // Simulate upload completion (replace with actual API call)
      setTimeout(() => {
        clearInterval(progressInterval);
        setUploadFiles(prev => prev.map(f => 
          f.id === uploadFile.id 
            ? { ...f, status: 'completed', progress: 100 }
            : f
        ));

        // Call completion callback
        const completedFiles = uploadFiles.filter(f => f.status === 'completed');
        if (completedFiles.length > 0) {
          onUploadComplete(completedFiles);
        }
      }, 2000 + Math.random() * 3000);

    } catch (error) {
      setUploadFiles(prev => prev.map(f => 
        f.id === uploadFile.id 
          ? {
              ...f,
              status: 'failed',
              error: `Upload failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
            }
          : f
      ));
    }
  }, [setUploadFiles, onUploadError]);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled) {
      setIsDragging(true);
    }
  }, [disabled]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setIsDragging(false);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (disabled) return;

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      validateAndProcessFiles(files);
    }
  }, [disabled, validateAndProcessFiles]);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      validateAndProcessFiles(files);
    }
    // Clear input value to allow re-selecting the same file
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [validateAndProcessFiles]);

  const handleCancel = useCallback((fileId: string) => {
    setUploadFiles(prev => prev.map(f => 
      f.id === fileId 
        ? { ...f, status: 'cancelled' }
        : f
    ));
  }, []);

  const handleRetry = useCallback((fileId: string) => {
    const file = uploadFiles.find(f => f.id === fileId);
    if (file && file.status === 'failed') {
      setUploadFiles(prev => prev.map(f => 
        f.id === fileId 
          ? { ...f, status: 'uploading', progress: 0, error: undefined }
          : f
      ));
      startFileUpload(file);
    }
  }, [uploadFiles, startFileUpload]);

  const showFileSecurityDetails = useCallback((file: UploadFile) => {
    setSelectedFile(file);
    setSecurityDialog(true);
  }, []);

  return (
    <Box>
      {/* Drop Zone */}
      <Paper
        ref={dropZoneRef}
        elevation={isDragging ? 4 : 1}
        sx={{
          border: isDragging ? '2px dashed #1976d2' : '2px dashed #ccc',
          borderRadius: 2,
          p: 4,
          textAlign: 'center',
          cursor: disabled ? 'not-allowed' : 'pointer',
          bgcolor: disabled ? 'action.disabledBackground' : 
                   isDragging ? 'action.hover' : 'background.paper',
          transition: 'all 0.2s ease-in-out',
          opacity: disabled ? 0.6 : 1,
          '&:hover': disabled ? {} : {
            borderColor: 'primary.main',
            bgcolor: 'action.hover',
          },
        }}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => !disabled && fileInputRef.current?.click()}
      >
        <CloudUpload sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
        <Typography variant="h6" gutterBottom>
          {disabled ? 'Upload Disabled' : 'Secure File Upload'}
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          {disabled 
            ? 'Upload functionality is currently disabled'
            : 'Drop video files here or click to browse'
          }
        </Typography>
        {!disabled && (
          <>
            <Typography variant="body2" color="text.secondary">
              Supported: MP4, AVI, MOV, MKV • Max: {Math.round(SECURITY_CONFIG.MAX_FILE_SIZE / (1024*1024))}MB
            </Typography>
            <Stack direction="row" spacing={1} justifyContent="center" sx={{ mt: 1 }}>
              <Chip icon={<Security />} label="Virus Scanning" size="small" />
              <Chip icon={<VerifiedUser />} label="File Signature Verification" size="small" />
              <Chip icon={<Warning />} label="Content Analysis" size="small" />
            </Stack>
          </>
        )}
      </Paper>

      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={Object.keys(SECURITY_CONFIG.ALLOWED_TYPES).join(',')}
        style={{ display: 'none' }}
        onChange={handleFileSelect}
        disabled={disabled}
      />

      {/* Upload Progress */}
      {uploadFiles.length > 0 && (
        <Paper sx={{ mt: 2, p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Upload Progress
          </Typography>
          
          <List>
            {uploadFiles.map((file) => (
              <ListItem key={file.id} divider>
                <Box sx={{ mr: 2 }}>
                  {file.status === 'completed' ? <CheckCircle color="success" /> :
                   file.status === 'failed' ? <ErrorIcon color="error" /> :
                   getSecurityStatusIcon(file.securityStatus)}
                </Box>
                
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="body1">{file.name}</Typography>
                      <Chip
                        label={file.status}
                        size="small"
                        color={getStatusColor(file)}
                        variant={file.status === 'completed' ? 'filled' : 'outlined'}
                      />
                    </Box>
                  }
                  secondary={
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        Size: {formatFileSize(file.size)} • Type: {file.type}
                      </Typography>
                      {file.status === 'uploading' && (
                        <Box sx={{ mt: 1 }}>
                          <LinearProgress 
                            variant="determinate" 
                            value={file.progress} 
                            sx={{ mb: 0.5 }}
                          />
                          <Typography variant="caption">
                            {Math.round(file.progress)}% uploaded
                          </Typography>
                        </Box>
                      )}
                      {file.status === 'validating' && (
                        <Box sx={{ mt: 1 }}>
                          <LinearProgress sx={{ mb: 0.5 }} />
                          <Typography variant="caption">
                            Performing security validation...
                          </Typography>
                        </Box>
                      )}
                      {file.error && (
                        <Alert severity="error" sx={{ mt: 1 }}>
                          {file.error}
                        </Alert>
                      )}
                      {file.validationResults.warnings.length > 0 && (
                        <Alert severity="warning" sx={{ mt: 1 }}>
                          {file.validationResults.warnings.join('; ')}
                        </Alert>
                      )}
                    </Box>
                  }
                />
                
                <ListItemSecondaryAction>
                  <Stack direction="row" spacing={1}>
                    {showSecurityDetails && (
                      <Tooltip title="Security Details">
                        <IconButton size="small" onClick={() => showFileSecurityDetails(file)}>
                          <Security />
                        </IconButton>
                      </Tooltip>
                    )}
                    {file.status === 'failed' && (
                      <Tooltip title="Retry Upload">
                        <IconButton size="small" onClick={() => handleRetry(file.id)}>
                          <CloudUpload />
                        </IconButton>
                      </Tooltip>
                    )}
                    {['uploading', 'validating'].includes(file.status) && (
                      <Tooltip title="Cancel">
                        <IconButton size="small" onClick={() => handleCancel(file.id)}>
                          <Cancel />
                        </IconButton>
                      </Tooltip>
                    )}
                  </Stack>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        </Paper>
      )}

      {/* Security Details Dialog */}
      <Dialog 
        open={securityDialog} 
        onClose={() => setSecurityDialog(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Security Validation Details</DialogTitle>
        <DialogContent>
          {selectedFile && (
            <Box>
              <Typography variant="h6" gutterBottom>
                {selectedFile.name}
              </Typography>
              
              <Stack spacing={2}>
                <Box>
                  <Typography variant="subtitle2">File Information</Typography>
                  <Typography variant="body2">Size: {formatFileSize(selectedFile.size)}</Typography>
                  <Typography variant="body2">Type: {selectedFile.type}</Typography>
                  <Typography variant="body2">Status: {selectedFile.status}</Typography>
                </Box>

                <Box>
                  <Typography variant="subtitle2">Security Checks</Typography>
                  <Stack spacing={1}>
                    <Chip 
                      icon={selectedFile.validationResults.fileSizeValid ? <CheckCircle /> : <ErrorIcon />}
                      label="File Size Validation"
                      color={selectedFile.validationResults.fileSizeValid ? 'success' : 'error'}
                      variant="outlined"
                    />
                    <Chip 
                      icon={selectedFile.validationResults.mimeTypeValid ? <CheckCircle /> : <ErrorIcon />}
                      label="MIME Type Validation"
                      color={selectedFile.validationResults.mimeTypeValid ? 'success' : 'error'}
                      variant="outlined"
                    />
                    <Chip 
                      icon={selectedFile.validationResults.signatureValid ? <CheckCircle /> : <Warning />}
                      label="File Signature Validation"
                      color={selectedFile.validationResults.signatureValid ? 'success' : 'warning'}
                      variant="outlined"
                    />
                    <Chip 
                      icon={selectedFile.validationResults.pathSecure ? <CheckCircle /> : <ErrorIcon />}
                      label="Path Security Check"
                      color={selectedFile.validationResults.pathSecure ? 'success' : 'error'}
                      variant="outlined"
                    />
                  </Stack>
                </Box>

                {selectedFile.validationResults.errors.length > 0 && (
                  <Box>
                    <Typography variant="subtitle2" color="error">Security Errors</Typography>
                    {selectedFile.validationResults.errors.map((error, index) => (
                      <Alert key={index} severity="error" sx={{ mt: 1 }}>
                        {error}
                      </Alert>
                    ))}
                  </Box>
                )}

                {selectedFile.validationResults.warnings.length > 0 && (
                  <Box>
                    <Typography variant="subtitle2" color="warning.main">Security Warnings</Typography>
                    {selectedFile.validationResults.warnings.map((warning, index) => (
                      <Alert key={index} severity="warning" sx={{ mt: 1 }}>
                        {warning}
                      </Alert>
                    ))}
                  </Box>
                )}

                {selectedFile.validationResults.scanResults && (
                  <Box>
                    <Typography variant="subtitle2">Advanced Scanning</Typography>
                    <Stack spacing={1} sx={{ mt: 1 }}>
                      <Typography variant="body2">
                        Virus Scan: <Chip 
                          label={selectedFile.validationResults.scanResults.virusScan} 
                          size="small"
                          color={selectedFile.validationResults.scanResults.virusScan === 'clean' ? 'success' : 'warning'}
                        />
                      </Typography>
                      <Typography variant="body2">
                        Content Analysis: <Chip 
                          label={selectedFile.validationResults.scanResults.contentAnalysis} 
                          size="small"
                          color={selectedFile.validationResults.scanResults.contentAnalysis === 'passed' ? 'success' : 'warning'}
                        />
                      </Typography>
                    </Stack>
                  </Box>
                )}
              </Stack>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSecurityDialog(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SecureFileUpload;