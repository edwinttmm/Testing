import React, { useEffect, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Box, Typography, Card, CardContent, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Button } from '@mui/material';
import { apiService } from '../services/api';

type LocalSession = {
  sessionId: string;
  sessionName: string;
  projectId?: string;
  startedAt: string;
  completedAt?: string;
  totals?: { total: number; pass: number; failHighLatency: number; missed: number; avgLatency: number };
};

const Results: React.FC = () => {
  const [rows, setRows] = useState<LocalSession[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const average = (arr: number[]) => (arr.length ? arr.reduce((a, b) => a + (Number.isFinite(b) ? b : 0), 0) / arr.length : 0);
    const load = async () => {
      setLoading(true);
      // Prefer server sessions
      const server = await apiService.getTestSessions().catch(() => []);
      if (Array.isArray(server) && server.length > 0) {
        const mapped: LocalSession[] = server.map((s: any) => ({
          sessionId: s.id,
          sessionName: s.name || `Test ${String(s.id).slice(0, 8)}`,
          projectId: s.projectId,
          startedAt: s.createdAt || s.started_at || new Date().toISOString(),
          completedAt: s.completedAt || s.completed_at,
        }));
        setRows(mapped);
        setLoading(false);
        return;
      }

      // Fallback: local sessions saved by HILTestExecutionPRD
      try {
        const local = JSON.parse(localStorage.getItem('hilLocalSessions') || '[]');
        if (Array.isArray(local)) {
          const mapped: LocalSession[] = local.map((e: any) => {
            const raw = localStorage.getItem(`hilLocalResults:${e.sessionId}`);
            let totals: LocalSession['totals'] | undefined;
            if (raw) {
              const r = JSON.parse(raw);
              const events: any[] = Array.isArray(r.detection_events) ? r.detection_events : [];
              const total = r.total_detections || events.length;
              const pass = r.passed_detections || events.filter(ev => ev.passed === true).length;
              const fail = r.failed_detections || (total - pass);
              const failHighLatency = events.filter(ev => ev.passed === false && (ev.failure_type === 'timing' || String(ev.error_message || '').toLowerCase().includes('threshold'))).length;
              const missed = Math.max(0, fail - failHighLatency);
              const avgLatency = r.average_latency_ms || average(events.map(ev => Number(ev.detection_time_ms)));
              totals = { total, pass, failHighLatency, missed, avgLatency: Number(avgLatency.toFixed ? avgLatency.toFixed(1) : avgLatency) };
            }
            return {
              sessionId: e.sessionId,
              sessionName: e.sessionName || 'HIL Test',
              projectId: e.projectId,
              startedAt: e.startedAt || new Date().toISOString(),
              completedAt: e.completedAt,
              totals,
            };
          });
          setRows(mapped);
        } else {
          setRows([]);
        }
      } catch {
        setRows([]);
      }
      setLoading(false);
    };
    load();
  }, []);

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>HIL Test Results</Typography>
      <Card>
        <CardContent>
          {loading ? (
            <Typography>Loading…</Typography>
          ) : rows.length === 0 ? (
            <Typography color="text.secondary">No test results yet. Run a HIL test and results will appear here.</Typography>
          ) : (
            <TableContainer component={Paper}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Session</TableCell>
                    <TableCell>Started</TableCell>
                    <TableCell align="right">Total</TableCell>
                    <TableCell align="right">Pass</TableCell>
                    <TableCell align="right">High Latency</TableCell>
                    <TableCell align="right">Missed</TableCell>
                    <TableCell align="right">Avg Latency (ms)</TableCell>
                    <TableCell align="right">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.map((r) => (
                    <TableRow key={r.sessionId} hover>
                      <TableCell>{r.sessionName}</TableCell>
                      <TableCell>{new Date(r.startedAt).toLocaleString()}</TableCell>
                      <TableCell align="right">{r.totals?.total ?? '-'}</TableCell>
                      <TableCell align="right">{r.totals?.pass ?? '-'}</TableCell>
                      <TableCell align="right">{r.totals?.failHighLatency ?? '-'}</TableCell>
                      <TableCell align="right">{r.totals?.missed ?? '-'}</TableCell>
                      <TableCell align="right">{r.totals?.avgLatency ?? '-'}</TableCell>
                      <TableCell align="right">
                        <Button size="small" component={RouterLink} to={`/results/${r.sessionId}`}>View</Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};

export default Results;

