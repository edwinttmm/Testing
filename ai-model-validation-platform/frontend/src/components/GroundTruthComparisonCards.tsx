import React from 'react';
import { Grid, Card, CardContent, Typography, Box, Chip } from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
  TrendingUp as TrendingUpIcon,
  Assessment as AssessmentIcon
} from '@mui/icons-material';

interface GroundTruthComparisonCardsProps {
  precision: number;
  recall: number;
  f1Score: number;
  truePositives: number;
  falsePositives: number;
  falseNegatives: number;
  totalGroundTruth?: number;
  title?: string;
}

export const GroundTruthComparisonCards: React.FC<GroundTruthComparisonCardsProps> = ({
  precision,
  recall,
  f1Score,
  truePositives,
  falsePositives,
  falseNegatives,
  totalGroundTruth,
  title = 'Ground Truth Comparison - Model Performance'
}) => {
  const getF1Quality = (score: number) => {
    if (score >= 90) return { label: 'Excellent', color: 'success.main', bgColor: 'success.light' };
    if (score >= 80) return { label: 'Good', color: 'warning.main', bgColor: 'warning.light' };
    return { label: 'Needs Improvement', color: 'error.main', bgColor: 'error.light' };
  };

  const f1Quality = getF1Quality(f1Score);
  const calculatedTotalGroundTruth = totalGroundTruth ?? (truePositives + falseNegatives);

  return (
    <Box sx={{ mb: 4 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
        <AssessmentIcon sx={{ fontSize: 32, mr: 1, color: 'primary.main' }} />
        <Typography variant="h5" fontWeight="bold">
          {title}
        </Typography>
        <Chip
          label={f1Quality.label}
          sx={{
            ml: 2,
            bgcolor: f1Quality.bgColor,
            color: f1Quality.color,
            fontWeight: 'bold'
          }}
        />
      </Box>

      <Grid container spacing={3}>
        {/* F1 Score - PRIMARY METRIC */}
        <Grid item xs={12} md={4}>
          <Card
            elevation={4}
            sx={{
              bgcolor: f1Quality.bgColor,
              borderLeft: 6,
              borderColor: f1Quality.color
            }}
          >
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <TrendingUpIcon sx={{ fontSize: 32, mr: 1, color: f1Quality.color }} />
                <Typography color="textSecondary" variant="overline" fontSize={14} fontWeight="bold">
                  F1 Score
                </Typography>
              </Box>
              <Typography variant="h2" color={f1Quality.color} fontWeight="bold">
                {f1Score.toFixed(1)}
                <Typography component="span" variant="h4" color="textSecondary">%</Typography>
              </Typography>
              <Typography variant="body1" color="textSecondary" sx={{ mt: 1 }}>
                Harmonic mean of Precision and Recall
              </Typography>
              <Typography variant="caption" color="textSecondary">
                {f1Score >= 90 ? 'Outstanding model performance' :
                 f1Score >= 80 ? 'Good model performance' :
                 'Model needs tuning'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Precision */}
        <Grid item xs={12} md={4}>
          <Card
            elevation={4}
            sx={{
              bgcolor: precision >= 95 ? 'success.light' : precision >= 85 ? 'warning.light' : 'error.light',
              borderLeft: 6,
              borderColor: precision >= 95 ? 'success.main' : precision >= 85 ? 'warning.main' : 'error.main'
            }}
          >
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <CheckCircleIcon
                  sx={{
                    fontSize: 32,
                    mr: 1,
                    color: precision >= 95 ? 'success.main' : precision >= 85 ? 'warning.main' : 'error.main'
                  }}
                />
                <Typography color="textSecondary" variant="overline" fontSize={14} fontWeight="bold">
                  Precision
                </Typography>
              </Box>
              <Typography
                variant="h2"
                color={precision >= 95 ? 'success.main' : precision >= 85 ? 'warning.main' : 'error.main'}
                fontWeight="bold"
              >
                {precision.toFixed(1)}
                <Typography component="span" variant="h4" color="textSecondary">%</Typography>
              </Typography>
              <Typography variant="body1" color="textSecondary" sx={{ mt: 1 }}>
                {truePositives} TP / {truePositives + falsePositives} Total Detections
              </Typography>
              <Typography variant="caption" color="textSecondary">
                How many detections were correct
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Recall */}
        <Grid item xs={12} md={4}>
          <Card
            elevation={4}
            sx={{
              bgcolor: recall >= 90 ? 'success.light' : recall >= 80 ? 'warning.light' : 'error.light',
              borderLeft: 6,
              borderColor: recall >= 90 ? 'success.main' : recall >= 80 ? 'warning.main' : 'error.main'
            }}
          >
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <CancelIcon
                  sx={{
                    fontSize: 32,
                    mr: 1,
                    color: recall >= 90 ? 'success.main' : recall >= 80 ? 'warning.main' : 'error.main'
                  }}
                />
                <Typography color="textSecondary" variant="overline" fontSize={14} fontWeight="bold">
                  Recall
                </Typography>
              </Box>
              <Typography
                variant="h2"
                color={recall >= 90 ? 'success.main' : recall >= 80 ? 'warning.main' : 'error.main'}
                fontWeight="bold"
              >
                {recall.toFixed(1)}
                <Typography component="span" variant="h4" color="textSecondary">%</Typography>
              </Typography>
              <Typography variant="body1" color="textSecondary" sx={{ mt: 1 }}>
                {truePositives} TP / {calculatedTotalGroundTruth} Ground Truth Events
              </Typography>
              <Typography variant="caption" color="textSecondary">
                How many GT events were detected
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Confusion Matrix Summary */}
        <Grid item xs={12}>
          <Card elevation={2} sx={{ bgcolor: 'grey.50' }}>
            <CardContent>
              <Typography variant="h6" fontWeight="bold" gutterBottom>
                Detection Breakdown
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={4}>
                  <Box sx={{ p: 2, bgcolor: 'success.light', borderRadius: 2 }}>
                    <Typography variant="overline" color="textSecondary">
                      True Positives
                    </Typography>
                    <Typography variant="h4" color="success.main" fontWeight="bold">
                      {truePositives}
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                      Correct detections matched to ground truth
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Box sx={{ p: 2, bgcolor: 'warning.light', borderRadius: 2 }}>
                    <Typography variant="overline" color="textSecondary">
                      False Positives
                    </Typography>
                    <Typography variant="h4" color="warning.main" fontWeight="bold">
                      {falsePositives}
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                      Detections with no matching ground truth
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Box sx={{ p: 2, bgcolor: 'error.light', borderRadius: 2 }}>
                    <Typography variant="overline" color="textSecondary">
                      False Negatives
                    </Typography>
                    <Typography variant="h4" color="error.main" fontWeight="bold">
                      {falseNegatives}
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                      Ground truth events missed by detection
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};
