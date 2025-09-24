import React, { useState, useEffect } from 'react';
import { Box, Typography, Card, CardContent, Button, CircularProgress, Alert, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Chip } from '@mui/material';
import { apiService } from '../services/api';

interface HILTestPageProps {}

const HILTestPage: React.FC<HILTestPageProps> = () => {
  const [loading, setLoading] = useState(false);
  const [latestSession, setLatestSession] = useState<any>(null);
  const [sessionResults, setSessionResults] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchLatestSession = async () => {
    setLoading(true);
    setError(null);
    try {
      console.log('🔍 Fetching latest session with events...');
      const session = await apiService.get<any>('/api/test-sessions/latest-with-events');
      setLatestSession(session);
      console.log('✅ Latest session:', session);
      
      if (session && session.session_id) {
        console.log(`🔍 Fetching results for session ${session.session_id}...`);
        const results = await apiService.get<any>(`/api/test-sessions/${session.session_id}/results`);
        setSessionResults(results);
        console.log('✅ Session results:', results);
      }
    } catch (err: any) {
      console.error('❌ Error fetching HIL data:', err);
      setError(err.message || 'Failed to fetch HIL data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLatestSession();
  }, []);

  const formatTimestamp = (timestamp: any) => {
    if (!timestamp) return 'N/A';
    try {
      if (typeof timestamp === 'string') {
        return new Date(timestamp).toLocaleString();
      }
      if (typeof timestamp === 'number') {
        // Handle Unix timestamps (both seconds and milliseconds)
        const date = timestamp > 1000000000000 ? new Date(timestamp) : new Date(timestamp * 1000);
        return date.toLocaleString();
      }
      return timestamp.toString();
    } catch {
      return timestamp.toString();
    }
  };

  const formatVoltage = (voltage: any) => {
    if (voltage === null || voltage === undefined) return 'N/A';
    const num = parseFloat(voltage);
    return isNaN(num) ? 'N/A' : `${num.toFixed(2)}V`;
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        HIL Test Results - Debug View
      </Typography>
      
      <Button 
        variant="contained" 
        onClick={fetchLatestSession} 
        disabled={loading}
        sx={{ mb: 3 }}
      >
        {loading ? <CircularProgress size={20} /> : 'Refresh Data'}
      </Button>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Error: {error}
        </Alert>
      )}

      {/* Latest Session Info */}
      {latestSession && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>Latest Session with Events</Typography>
            <Typography><strong>Session ID:</strong> {latestSession.session_id}</Typography>
            <Typography><strong>Name:</strong> {latestSession.name}</Typography>
            <Typography><strong>Status:</strong> {latestSession.status}</Typography>
            <Typography><strong>Event Count:</strong> {latestSession.event_count}</Typography>
            <Typography><strong>Latest Event:</strong> {formatTimestamp(latestSession.latest_event_time)}</Typography>
          </CardContent>
        </Card>
      )}

      {/* Session Results */}
      {sessionResults && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>Session Results Summary</Typography>
            <Typography><strong>Total Detections:</strong> {sessionResults.total_detections || 0}</Typography>
            <Typography><strong>Passed Detections:</strong> {sessionResults.passed_detections || 0}</Typography>
            <Typography><strong>Failed Detections:</strong> {sessionResults.failed_detections || 0}</Typography>
            <Typography><strong>Pass Rate:</strong> {sessionResults.pass_rate?.toFixed(1) || 0}%</Typography>
            <Typography><strong>Status:</strong> {sessionResults.status}</Typography>
          </CardContent>
        </Card>
      )}

      {/* Detection Events Table */}
      {sessionResults && sessionResults.detection_events && sessionResults.detection_events.length > 0 && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Detection Events ({sessionResults.detection_events.length})
            </Typography>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Event ID</TableCell>
                    <TableCell>Timestamp</TableCell>
                    <TableCell align="right">Voltage</TableCell>
                    <TableCell>Channel</TableCell>
                    <TableCell>Result</TableCell>
                    <TableCell>Session</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {sessionResults.detection_events.slice(0, 20).map((event: any, idx: number) => (
                    <TableRow key={event.event_id || idx}>
                      <TableCell>{(event.event_id || 'N/A').substring(0, 8)}...</TableCell>
                      <TableCell>{formatTimestamp(event.timestamp || event.detection_time)}</TableCell>
                      <TableCell align="right">
                        <Typography 
                          color={
                            (event.voltage_level || 0) >= 2.5 
                              ? 'success.main' 
                              : 'warning.main'
                          }
                          fontWeight="bold"
                        >
                          {formatVoltage(event.voltage_level)}
                        </Typography>
                      </TableCell>
                      <TableCell>{event.channel || 'AIN0'}</TableCell>
                      <TableCell>
                        <Chip 
                          label={event.result || 'unknown'} 
                          color={event.result === 'pass' ? 'success' : 'error'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>{(event.session_id || 'N/A').substring(0, 8)}...</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            {sessionResults.detection_events.length > 20 && (
              <Typography variant="caption" sx={{ mt: 1 }}>
                Showing first 20 of {sessionResults.detection_events.length} events
              </Typography>
            )}
          </CardContent>
        </Card>
      )}

      {/* No Events Message */}
      {sessionResults && (!sessionResults.detection_events || sessionResults.detection_events.length === 0) && (
        <Alert severity="info">
          No detection events found in the session results.
        </Alert>
      )}
    </Box>
  );
};

export default HILTestPage;