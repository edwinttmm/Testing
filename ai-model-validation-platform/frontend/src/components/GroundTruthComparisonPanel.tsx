import React from 'react';
import { Box, Typography, Card, CardContent, Grid, Chip, Alert } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import { GroundTruthComparisonMetrics } from '../types/enhanced-results';

interface GroundTruthComparisonPanelProps {
  comparisonData: GroundTruthComparisonMetrics | null;
  loading?: boolean;
  error?: string | null;
}

const GroundTruthComparisonPanel: React.FC<GroundTruthComparisonPanelProps> = ({
  comparisonData,
  loading = false,
  error = null
}) => {
  if (loading) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Ground Truth Comparison
          </Typography>
          <Typography>Loading ground truth comparison data...</Typography>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Ground Truth Comparison
          </Typography>
          <Alert severity="error">
            <Typography>Error loading ground truth data: {error}</Typography>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (!comparisonData) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Ground Truth Comparison
          </Typography>
          <Alert severity="info">
            <Typography>No ground truth comparison data available. Ensure the enhanced HIL API includes ground truth analysis.</Typography>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const hasMetrics = comparisonData.precision !== undefined;
  const hasTimingQuality = comparisonData.timing_quality_distribution && 
    Object.keys(comparisonData.timing_quality_distribution).length > 0;

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
          <CheckCircleIcon sx={{ mr: 1, color: 'primary.main' }} />
          Ground Truth Comparison
        </Typography>

        {/* Basic Statistics */}
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} md={6}>
            <Typography variant="body1">
              <strong>Ground Truth Events:</strong> {comparisonData.ground_truth_events_available}
            </Typography>
            <Typography variant="body1">
              <strong>Total Detections:</strong> {comparisonData.total_detections}
            </Typography>
            <Typography variant="body1">
              <strong>Events with Matches:</strong> {comparisonData.events_with_matches}
            </Typography>
            <Typography variant="body1">
              <strong>Average Confidence:</strong> {(comparisonData.average_confidence_score * 100).toFixed(1)}%
            </Typography>
          </Grid>
          
          {hasMetrics && (
            <Grid item xs={12} md={6}>
              <Typography variant="body1" sx={{ color: 'success.main' }}>
                <strong>True Positives:</strong> {comparisonData.true_positives}
              </Typography>
              <Typography variant="body1" sx={{ color: 'warning.main' }}>
                <strong>False Positives:</strong> {comparisonData.false_positives}
              </Typography>
              <Typography variant="body1" sx={{ color: 'error.main' }}>
                <strong>False Negatives:</strong> {comparisonData.false_negatives}
              </Typography>
            </Grid>
          )}
        </Grid>

        {/* Performance Metrics */}
        {hasMetrics && (
          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 'bold' }}>
              Performance Metrics
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={4}>
                <Typography variant="body1" sx={{ color: 'info.main' }}>
                  <strong>Precision:</strong> {(comparisonData.precision * 100).toFixed(1)}%
                </Typography>
              </Grid>
              <Grid item xs={4}>
                <Typography variant="body1" sx={{ color: 'info.main' }}>
                  <strong>Recall:</strong> {(comparisonData.recall * 100).toFixed(1)}%
                </Typography>
              </Grid>
              <Grid item xs={4}>
                <Typography variant="body1" sx={{ color: 'success.main' }}>
                  <strong>F1 Score:</strong> {(comparisonData.f1_score * 100).toFixed(1)}%
                </Typography>
              </Grid>
            </Grid>
          </Box>
        )}

        {/* Timing Quality Distribution */}
        {hasTimingQuality && (
          <Box>
            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 'bold' }}>
              Timing Synchronization Quality
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {comparisonData.timing_quality_distribution.excellent > 0 && (
                <Chip 
                  label={`Excellent: ${comparisonData.timing_quality_distribution.excellent}`} 
                  color="success" 
                  size="small" 
                />
              )}
              {comparisonData.timing_quality_distribution.good > 0 && (
                <Chip 
                  label={`Good: ${comparisonData.timing_quality_distribution.good}`} 
                  color="primary" 
                  size="small" 
                />
              )}
              {comparisonData.timing_quality_distribution.fair > 0 && (
                <Chip 
                  label={`Fair: ${comparisonData.timing_quality_distribution.fair}`} 
                  color="warning" 
                  size="small" 
                />
              )}
              {comparisonData.timing_quality_distribution.poor > 0 && (
                <Chip 
                  label={`Poor: ${comparisonData.timing_quality_distribution.poor}`} 
                  color="error" 
                  size="small" 
                />
              )}
            </Box>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default GroundTruthComparisonPanel;