import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Button,
  Tabs,
  Tab,
  Alert,
  LinearProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Tooltip,
  IconButton
} from '@mui/material';
import {
  ExpandMore,
  TrendingUp,
  Assessment,
  Science,
  ShowChart,
  InfoOutlined,
  FileDownload
} from '@mui/icons-material';

export interface StatisticalTest {
  name: string;
  type: 'parametric' | 'non-parametric';
  pValue: number;
  statisticValue: number;
  criticalValue?: number;
  confidenceLevel: number;
  isSignificant: boolean;
  effectSize?: number;
  powerAnalysis?: {
    power: number;
    recommendedSampleSize: number;
  };
  interpretation: string;
}

export interface ConfidenceInterval {
  metric: string;
  value: number;
  lowerBound: number;
  upperBound: number;
  confidenceLevel: number;
  method: 'bootstrap' | 'normal' | 'student-t' | 'exact';
  marginOfError: number;
}

export interface StatisticalValidationData {
  sessionId: string;
  sampleSize: number;
  confidenceIntervals: ConfidenceInterval[];
  hypothesisTests: StatisticalTest[];
  normality: {
    shapiroWilkTest: StatisticalTest;
    andersonDarlingTest: StatisticalTest;
    kolmogorovSmirnovTest: StatisticalTest;
    isNormallyDistributed: boolean;
  };
  descriptiveStats: {
    mean: number;
    median: number;
    standardDeviation: number;
    variance: number;
    skewness: number;
    kurtosis: number;
    iqr: number;
    outliers: number[];
  };
  recommendations: string[];
}

interface StatisticalValidationPanelProps {
  sessionId: string;
  data?: StatisticalValidationData;
  loading?: boolean;
}

export const StatisticalValidationPanel: React.FC<StatisticalValidationPanelProps> = ({
  sessionId,
  data,
  loading = false
}) => {
  const [currentTab, setCurrentTab] = useState(0);
  const [selectedMetric, setSelectedMetric] = useState<string>('accuracy');
  const [confidenceLevel, setConfidenceLevel] = useState<number>(95);

  // Mock data for demonstration - would be replaced with API call
  const mockData: StatisticalValidationData = useMemo(() => ({
    sessionId,
    sampleSize: 1250,
    confidenceIntervals: [
      {
        metric: 'accuracy',
        value: 94.2,
        lowerBound: 92.1,
        upperBound: 96.3,
        confidenceLevel: 95,
        method: 'student-t',
        marginOfError: 2.1
      },
      {
        metric: 'precision',
        value: 91.5,
        lowerBound: 88.9,
        upperBound: 94.1,
        confidenceLevel: 95,
        method: 'bootstrap',
        marginOfError: 2.6
      },
      {
        metric: 'recall',
        value: 87.3,
        lowerBound: 84.2,
        upperBound: 90.4,
        confidenceLevel: 95,
        method: 'exact',
        marginOfError: 3.1
      },
      {
        metric: 'f1Score',
        value: 89.3,
        lowerBound: 86.7,
        upperBound: 91.9,
        confidenceLevel: 95,
        method: 'normal',
        marginOfError: 2.6
      }
    ],
    hypothesisTests: [
      {
        name: 'One-Sample t-test (Accuracy ≥ 85%)',
        type: 'parametric',
        pValue: 0.001,
        statisticValue: 8.34,
        criticalValue: 1.96,
        confidenceLevel: 95,
        isSignificant: true,
        effectSize: 1.82,
        powerAnalysis: {
          power: 0.95,
          recommendedSampleSize: 850
        },
        interpretation: 'Strong evidence that accuracy significantly exceeds 85% threshold'
      },
      {
        name: 'Mann-Whitney U Test (vs. Baseline)',
        type: 'non-parametric',
        pValue: 0.0032,
        statisticValue: 234.5,
        confidenceLevel: 95,
        isSignificant: true,
        effectSize: 0.72,
        powerAnalysis: {
          power: 0.88,
          recommendedSampleSize: 1100
        },
        interpretation: 'Significant improvement over baseline performance'
      },
      {
        name: 'Kolmogorov-Smirnov Test (Distribution)',
        type: 'non-parametric',
        pValue: 0.156,
        statisticValue: 0.089,
        criticalValue: 0.125,
        confidenceLevel: 95,
        isSignificant: false,
        interpretation: 'No significant difference from expected distribution'
      },
      {
        name: 'Chi-square Test (Class Distribution)',
        type: 'non-parametric',
        pValue: 0.045,
        statisticValue: 9.78,
        criticalValue: 7.815,
        confidenceLevel: 95,
        isSignificant: true,
        effectSize: 0.28,
        interpretation: 'Significant association between predicted and actual classes'
      }
    ],
    normality: {
      shapiroWilkTest: {
        name: 'Shapiro-Wilk Test',
        type: 'parametric',
        pValue: 0.234,
        statisticValue: 0.976,
        confidenceLevel: 95,
        isSignificant: false,
        interpretation: 'Data appears normally distributed'
      },
      andersonDarlingTest: {
        name: 'Anderson-Darling Test',
        type: 'parametric',
        pValue: 0.189,
        statisticValue: 0.445,
        confidenceLevel: 95,
        isSignificant: false,
        interpretation: 'Data follows normal distribution'
      },
      kolmogorovSmirnovTest: {
        name: 'Kolmogorov-Smirnov Test',
        type: 'non-parametric',
        pValue: 0.312,
        statisticValue: 0.067,
        confidenceLevel: 95,
        isSignificant: false,
        interpretation: 'Normal distribution assumption valid'
      },
      isNormallyDistributed: true
    },
    descriptiveStats: {
      mean: 94.2,
      median: 94.8,
      standardDeviation: 3.4,
      variance: 11.56,
      skewness: -0.23,
      kurtosis: 2.87,
      iqr: 4.2,
      outliers: [78.2, 79.1, 98.9, 99.2]
    },
    recommendations: [
      'Sample size is adequate for reliable statistical inference',
      'Normal distribution assumption is satisfied - parametric tests appropriate',
      'Consider investigating outliers for potential data quality issues',
      'Statistical power analysis suggests current sample size is sufficient',
      'Confidence intervals indicate robust performance above acceptance criteria'
    ]
  }), [sessionId]);

  const activeData = data || mockData;

  const getSignificanceColor = (pValue: number): 'success' | 'warning' | 'error' => {
    if (pValue < 0.01) return 'success';
    if (pValue < 0.05) return 'warning';
    return 'error';
  };

  const getEffectSizeInterpretation = (effectSize?: number): string => {
    if (!effectSize) return 'N/A';
    if (effectSize < 0.2) return 'Small';
    if (effectSize < 0.5) return 'Medium';
    if (effectSize < 0.8) return 'Large';
    return 'Very Large';
  };

  const tabContent = [
    {
      label: 'Confidence Intervals',
      icon: <TrendingUp />,
      content: (
        <Box>
          <Typography variant="h6" gutterBottom>
            95% Confidence Intervals
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Metric</TableCell>
                  <TableCell align="right">Value</TableCell>
                  <TableCell align="right">Lower Bound</TableCell>
                  <TableCell align="right">Upper Bound</TableCell>
                  <TableCell align="right">Margin of Error</TableCell>
                  <TableCell>Method</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {activeData.confidenceIntervals.map((ci, index) => (
                  <TableRow key={index}>
                    <TableCell>
                      <Typography variant="subtitle2">
                        {ci.metric.charAt(0).toUpperCase() + ci.metric.slice(1)}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Typography variant="body1" fontWeight="bold">
                        {ci.value.toFixed(1)}%
                      </Typography>
                    </TableCell>
                    <TableCell align="right">{ci.lowerBound.toFixed(1)}%</TableCell>
                    <TableCell align="right">{ci.upperBound.toFixed(1)}%</TableCell>
                    <TableCell align="right">±{ci.marginOfError.toFixed(1)}%</TableCell>
                    <TableCell>
                      <Chip
                        label={ci.method}
                        size="small"
                        color={ci.method === 'exact' ? 'success' : 'default'}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )
    },
    {
      label: 'Hypothesis Tests',
      icon: <Science />,
      content: (
        <Box>
          <Typography variant="h6" gutterBottom>
            Statistical Hypothesis Testing
          </Typography>
          {activeData.hypothesisTests.map((test, index) => (
            <Accordion key={index}>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                  <Typography variant="subtitle1">{test.name}</Typography>
                  <Chip
                    label={test.isSignificant ? 'Significant' : 'Not Significant'}
                    color={getSignificanceColor(test.pValue)}
                    size="small"
                  />
                  <Typography variant="caption" color="text.secondary">
                    p = {test.pValue.toFixed(4)}
                  </Typography>
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                <Grid container spacing={2}>
                  <Grid item xs={12} md={6}>
                    <Paper sx={{ p: 2 }} variant="outlined">
                      <Typography variant="subtitle2" gutterBottom>Test Statistics</Typography>
                      <Typography>Type: {test.type}</Typography>
                      <Typography>Test Statistic: {test.statisticValue.toFixed(3)}</Typography>
                      {test.criticalValue && (
                        <Typography>Critical Value: {test.criticalValue.toFixed(3)}</Typography>
                      )}
                      <Typography>p-value: {test.pValue.toFixed(4)}</Typography>
                      <Typography>Confidence Level: {test.confidenceLevel}%</Typography>
                    </Paper>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Paper sx={{ p: 2 }} variant="outlined">
                      <Typography variant="subtitle2" gutterBottom>Effect Size & Power</Typography>
                      {test.effectSize && (
                        <>
                          <Typography>Effect Size: {test.effectSize.toFixed(3)}</Typography>
                          <Typography>Interpretation: {getEffectSizeInterpretation(test.effectSize)}</Typography>
                        </>
                      )}
                      {test.powerAnalysis && (
                        <>
                          <Typography>Statistical Power: {(test.powerAnalysis.power * 100).toFixed(1)}%</Typography>
                          <Typography>Recommended Sample: {test.powerAnalysis.recommendedSampleSize}</Typography>
                        </>
                      )}
                    </Paper>
                  </Grid>
                  <Grid item xs={12}>
                    <Alert severity="info">
                      <Typography variant="body2">{test.interpretation}</Typography>
                    </Alert>
                  </Grid>
                </Grid>
              </AccordionDetails>
            </Accordion>
          ))}
        </Box>
      )
    },
    {
      label: 'Descriptive Statistics',
      icon: <Assessment />,
      content: (
        <Box>
          <Typography variant="h6" gutterBottom>
            Descriptive Statistics Summary
          </Typography>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="subtitle1" gutterBottom>Central Tendency</Typography>
                  <Table size="small">
                    <TableBody>
                      <TableRow>
                        <TableCell>Mean</TableCell>
                        <TableCell align="right">{activeData.descriptiveStats.mean.toFixed(2)}%</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Median</TableCell>
                        <TableCell align="right">{activeData.descriptiveStats.median.toFixed(2)}%</TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="subtitle1" gutterBottom>Dispersion</Typography>
                  <Table size="small">
                    <TableBody>
                      <TableRow>
                        <TableCell>Standard Deviation</TableCell>
                        <TableCell align="right">{activeData.descriptiveStats.standardDeviation.toFixed(2)}</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Interquartile Range</TableCell>
                        <TableCell align="right">{activeData.descriptiveStats.iqr.toFixed(2)}</TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="subtitle1" gutterBottom>Distribution Shape</Typography>
                  <Table size="small">
                    <TableBody>
                      <TableRow>
                        <TableCell>Skewness</TableCell>
                        <TableCell align="right">{activeData.descriptiveStats.skewness.toFixed(3)}</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Kurtosis</TableCell>
                        <TableCell align="right">{activeData.descriptiveStats.kurtosis.toFixed(3)}</TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="subtitle1" gutterBottom>Data Quality</Typography>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Sample Size: {activeData.sampleSize.toLocaleString()}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Outliers Detected: {activeData.descriptiveStats.outliers.length}
                  </Typography>
                  {activeData.descriptiveStats.outliers.length > 0 && (
                    <Typography variant="caption" color="text.secondary">
                      Values: {activeData.descriptiveStats.outliers.map(o => o.toFixed(1)).join(', ')}
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Box>
      )
    },
    {
      label: 'Recommendations',
      icon: <InfoOutlined />,
      content: (
        <Box>
          <Typography variant="h6" gutterBottom>
            Statistical Analysis Recommendations
          </Typography>
          {activeData.recommendations.map((rec, index) => (
            <Alert key={index} severity="info" sx={{ mb: 2 }}>
              {rec}
            </Alert>
          ))}
          
          <Card sx={{ mt: 3 }}>
            <CardContent>
              <Typography variant="subtitle1" gutterBottom>
                Summary Assessment
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" color="success.main">
                      {activeData.sampleSize >= 1000 ? 'Excellent' : 'Good'}
                    </Typography>
                    <Typography variant="caption">Sample Size Adequacy</Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" color={activeData.normality.isNormallyDistributed ? 'success.main' : 'warning.main'}>
                      {activeData.normality.isNormallyDistributed ? 'Valid' : 'Caution'}
                    </Typography>
                    <Typography variant="caption">Distribution Assumptions</Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" color="primary.main">
                      {activeData.hypothesisTests.filter(t => t.isSignificant).length}
                    </Typography>
                    <Typography variant="caption">Significant Tests</Typography>
                  </Box>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Box>
      )
    }
  ];

  return (
    <Box sx={{ height: '100%' }}>
      {loading && <LinearProgress />}
      
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs
          value={currentTab}
          onChange={(_, newValue) => setCurrentTab(newValue)}
          variant="scrollable"
          scrollButtons="auto"
        >
          {tabContent.map((tab, index) => (
            <Tab
              key={index}
              label={tab.label}
              icon={tab.icon}
              iconPosition="start"
              sx={{ textTransform: 'none' }}
            />
          ))}
        </Tabs>
      </Box>

      <Box sx={{ mt: 2 }}>
        {tabContent[currentTab]?.content}
      </Box>

      <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
        <Button
          variant="outlined"
          startIcon={<FileDownload />}
          onClick={() => {
            // Export statistical analysis
            console.log('Exporting statistical analysis for session:', sessionId);
          }}
        >
          Export Analysis
        </Button>
      </Box>
    </Box>
  );
};

export default StatisticalValidationPanel;