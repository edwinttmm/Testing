import React from 'react';
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableContainer, 
  TableHead, 
  TableRow, 
  Paper, 
  Typography,
  Box,
  Chip
} from '@mui/material';
import { EnhancedDetectionEvent } from '../types/enhanced-results';

interface EnhancedDetectionEventsTableProps {
  events: EnhancedDetectionEvent[];
  showTimingSynchronization?: boolean;
  showGroundTruthMatching?: boolean;
}

const EnhancedDetectionEventsTable: React.FC<EnhancedDetectionEventsTableProps> = ({
  events,
  showTimingSynchronization = true,
  showGroundTruthMatching = true
}) => {
  if (!events || events.length === 0) {
    return (
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Enhanced Detection Events
        </Typography>
        <Typography color="text.secondary">
          No enhanced detection events available
        </Typography>
      </Paper>
    );
  }

  const getTimingQualityColor = (quality?: string) => {
    switch (quality) {
      case 'excellent': return 'success';
      case 'good': return 'primary';
      case 'fair': return 'warning';
      case 'poor': return 'error';
      default: return 'default';
    }
  };

  return (
    <Paper>
      <Box sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Enhanced Detection Events ({events.length} events)
        </Typography>
      </Box>
      
      <TableContainer sx={{ maxHeight: 600 }}>
        <Table stickyHeader size="small">
          <TableHead>
            <TableRow>
              <TableCell>Event ID</TableCell>
              <TableCell>Frame</TableCell>
              <TableCell>Timestamp</TableCell>
              <TableCell>Voltage</TableCell>
              <TableCell>Latency (ms)</TableCell>
              {showTimingSynchronization && (
                <>
                  <TableCell>Timing Quality</TableCell>
                  <TableCell>Confidence</TableCell>
                </>
              )}
              {showGroundTruthMatching && (
                <>
                  <TableCell>GT Match</TableCell>
                  <TableCell>Processing Time</TableCell>
                </>
              )}
              <TableCell>Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {events.map((event, index) => (
              <TableRow key={event.id || index}>
                <TableCell>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                    {event.id?.slice(0, 8) || `event_${index}`}
                  </Typography>
                </TableCell>
                
                <TableCell>
                  {event.video_frame || event.frame_number || 0}
                </TableCell>
                
                <TableCell>
                  <Typography variant="body2">
                    {new Date(event.timestamp * 1000).toLocaleTimeString('en-US', {
                      hour12: false,
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                      fractionalSecondDigits: 2
                    })}
                  </Typography>
                </TableCell>
                
                <TableCell>
                  <Typography 
                    color={event.voltage && event.voltage >= 2.5 ? 'success.main' : 'warning.main'}
                    fontWeight="bold"
                  >
                    {event.voltage?.toFixed(2) || 'N/A'}V
                  </Typography>
                </TableCell>
                
                <TableCell>
                  <Box>
                    {event.real_latency_ms !== undefined ? (
                      <>
                        <Typography color="success.main" fontWeight="bold">
                          Real: {event.real_latency_ms.toFixed(0)}ms
                        </Typography>
                        {event.apparent_latency_ms !== undefined && (
                          <Typography variant="caption" color="text.secondary">
                            (Apparent: {event.apparent_latency_ms.toFixed(0)}ms)
                          </Typography>
                        )}
                      </>
                    ) : (
                      <Typography>
                        {event.detection_time_ms?.toFixed(0) || 'N/A'}ms
                      </Typography>
                    )}
                  </Box>
                </TableCell>
                
                {showTimingSynchronization && (
                  <>
                    <TableCell>
                      {event.timing_quality ? (
                        <Chip 
                          label={event.timing_quality} 
                          color={getTimingQualityColor(event.timing_quality) as any}
                          size="small"
                        />
                      ) : (
                        <Typography variant="caption" color="text.secondary">
                          N/A
                        </Typography>
                      )}
                    </TableCell>
                    
                    <TableCell>
                      {event.confidence_score !== undefined ? (
                        <Typography 
                          color={event.confidence_score > 0.8 ? 'success.main' : 
                                event.confidence_score > 0.5 ? 'warning.main' : 'error.main'}
                        >
                          {(event.confidence_score * 100).toFixed(0)}%
                        </Typography>
                      ) : (
                        <Typography variant="caption" color="text.secondary">
                          N/A
                        </Typography>
                      )}
                    </TableCell>
                  </>
                )}
                
                {showGroundTruthMatching && (
                  <>
                    <TableCell>
                      {event.ground_truth_available ? (
                        <Box>
                          <Chip label="Available" color="success" size="small" />
                          {event.match_iou_score !== undefined && (
                            <Typography variant="caption" sx={{ display: 'block' }}>
                              IoU: {event.match_iou_score.toFixed(2)}
                            </Typography>
                          )}
                        </Box>
                      ) : (
                        <Chip label="Not Available" color="default" size="small" />
                      )}
                    </TableCell>
                    
                    <TableCell>
                      {event.processing_time_ms !== undefined ? (
                        <Typography>
                          {event.processing_time_ms.toFixed(0)}ms
                        </Typography>
                      ) : (
                        <Typography variant="caption" color="text.secondary">
                          N/A
                        </Typography>
                      )}
                    </TableCell>
                  </>
                )}
                
                <TableCell>
                  <Chip 
                    label={event.passed ? 'PASS' : 'FAIL'} 
                    color={event.passed ? 'success' : 'error'}
                    size="small"
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
};

export default EnhancedDetectionEventsTable;