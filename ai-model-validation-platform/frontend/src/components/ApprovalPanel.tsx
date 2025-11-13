import React, { useState } from 'react';
import {
  Box,
  Button,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip,
  Typography,
  Stack,
  Alert
} from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import { approveTestSession } from '../services/api';

interface ApprovalPanelProps {
  sessionId: string;
  approvalStatus: 'pending' | 'approved' | 'rejected';
  approvedBy?: string;
  approvedAt?: string;
  approvalComments?: string;
  rejectionReason?: string;
  onApprovalChange: (status: string) => void;
  currentUserId?: string;  // Optional: user ID for approver tracking
}

export const ApprovalPanel: React.FC<ApprovalPanelProps> = ({
  sessionId,
  approvalStatus,
  approvedBy,
  approvedAt,
  approvalComments,
  rejectionReason,
  onApprovalChange,
  currentUserId = 'system'
}) => {
  const [comments, setComments] = useState('');
  const [showRejectDialog, setShowRejectDialog] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleApprove = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await approveTestSession(sessionId, {
        approverId: currentUserId,
        action: 'approve',
        comments: comments || undefined
      });

      onApprovalChange(response.approvalStatus);
      setComments('');  // Clear comments after successful approval
    } catch (err) {
      console.error('Approval failed:', err);
      setError('Failed to approve session. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) {
      setError('Rejection reason is required');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await approveTestSession(sessionId, {
        approverId: currentUserId,
        action: 'reject',
        comments: comments || undefined,
        rejectionReason: rejectReason
      });

      onApprovalChange(response.approvalStatus);
      setShowRejectDialog(false);
      setComments('');
      setRejectReason('');
    } catch (err) {
      console.error('Rejection failed:', err);
      setError('Failed to reject session. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenRejectDialog = () => {
    setShowRejectDialog(true);
    setError(null);
  };

  const handleCloseRejectDialog = () => {
    setShowRejectDialog(false);
    setRejectReason('');
    setError(null);
  };

  const formatDateTime = (dateString?: string): string => {
    if (!dateString) return '';
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return dateString;
    }
  };

  // Display approved state
  if (approvalStatus === 'approved') {
    return (
      <Box sx={{ mt: 3, p: 2, backgroundColor: '#f1f8f4', borderRadius: 1 }}>
        <Stack direction="row" spacing={2} alignItems="center">
          <Chip
            icon={<CheckIcon />}
            label="Approved"
            color="success"
            size="large"
          />
          <Box>
            {approvedBy && (
              <Typography variant="body2" color="text.secondary">
                Approved by: {approvedBy}
              </Typography>
            )}
            {approvedAt && (
              <Typography variant="body2" color="text.secondary">
                Date: {formatDateTime(approvedAt)}
              </Typography>
            )}
            {approvalComments && (
              <Typography variant="body2" sx={{ mt: 1 }}>
                Comments: {approvalComments}
              </Typography>
            )}
          </Box>
        </Stack>
      </Box>
    );
  }

  // Display rejected state
  if (approvalStatus === 'rejected') {
    return (
      <Box sx={{ mt: 3, p: 2, backgroundColor: '#fef1f1', borderRadius: 1 }}>
        <Stack direction="row" spacing={2} alignItems="center">
          <Chip
            icon={<CloseIcon />}
            label="Rejected"
            color="error"
            size="large"
          />
          <Box>
            {approvedBy && (
              <Typography variant="body2" color="text.secondary">
                Rejected by: {approvedBy}
              </Typography>
            )}
            {approvedAt && (
              <Typography variant="body2" color="text.secondary">
                Date: {formatDateTime(approvedAt)}
              </Typography>
            )}
            {rejectionReason && (
              <Typography variant="body2" sx={{ mt: 1, color: 'error.main' }}>
                Reason: {rejectionReason}
              </Typography>
            )}
            {approvalComments && (
              <Typography variant="body2" sx={{ mt: 1 }}>
                Comments: {approvalComments}
              </Typography>
            )}
          </Box>
        </Stack>
      </Box>
    );
  }

  // Display pending state with approval actions
  return (
    <Box sx={{ mt: 3, p: 2, border: '1px solid #e0e0e0', borderRadius: 1 }}>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Approval Required
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <TextField
        label="Approval Comments (optional)"
        multiline
        rows={3}
        value={comments}
        onChange={(e) => setComments(e.target.value)}
        fullWidth
        sx={{ mb: 2 }}
        placeholder="Add any comments about this test session..."
      />

      <Stack direction="row" spacing={2} justifyContent="center">
        <Button
          variant="contained"
          color="success"
          size="large"
          onClick={handleApprove}
          startIcon={<CheckIcon />}
          disabled={loading}
        >
          {loading ? 'Approving...' : 'Approve Results'}
        </Button>
        <Button
          variant="contained"
          color="error"
          size="large"
          onClick={handleOpenRejectDialog}
          startIcon={<CloseIcon />}
          disabled={loading}
        >
          Reject Results
        </Button>
      </Stack>

      {/* Rejection Dialog */}
      <Dialog
        open={showRejectDialog}
        onClose={handleCloseRejectDialog}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Reject Test Session</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 2 }}>
            Please provide a reason for rejecting this test session.
          </Typography>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          <TextField
            label="Rejection Reason (required)"
            multiline
            rows={4}
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            fullWidth
            required
            autoFocus
            placeholder="e.g., Detection accuracy below acceptable threshold, timing issues detected, etc."
            error={error !== null && !rejectReason.trim()}
            helperText={error !== null && !rejectReason.trim() ? "Rejection reason is required" : ""}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseRejectDialog} disabled={loading}>
            Cancel
          </Button>
          <Button
            onClick={handleReject}
            color="error"
            variant="contained"
            disabled={loading || !rejectReason.trim()}
            startIcon={<CloseIcon />}
          >
            {loading ? 'Rejecting...' : 'Confirm Rejection'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ApprovalPanel;
