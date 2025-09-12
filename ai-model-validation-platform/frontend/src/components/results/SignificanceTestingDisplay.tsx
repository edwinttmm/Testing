import React from 'react';
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
  LinearProgress,
  Tooltip
} from '@mui/material';
import {
  TTestResult,
  MannWhitneyUResult,
  KolmogorovSmirnovResult,
  ChiSquareResult
} from '../../types/enhanced-results';

interface SignificanceTestingDisplayProps {
  tTest: TTestResult;
  mannWhitney: MannWhitneyUResult;
  kolmogorov: KolmogorovSmirnovResult;
  chiSquare: ChiSquareResult;
}

export const SignificanceTestingDisplay: React.FC<SignificanceTestingDisplayProps> = ({
  tTest,
  mannWhitney,
  kolmogorov,
  chiSquare
}) => {
  // Helper function to get significance color and label
  const getSignificanceInfo = (pValue: number, isSignificant: boolean) => {
    if (pValue < 0.001) return { color: 'success', label: 'Highly Significant (p<0.001)', level: 'high' };
    if (pValue < 0.01) return { color: 'success', label: 'Very Significant (p<0.01)', level: 'high' };
    if (pValue < 0.05) return { color: 'info', label: 'Significant (p<0.05)', level: 'medium' };
    if (pValue < 0.1) return { color: 'warning', label: 'Marginally Significant (p<0.1)', level: 'low' };
    return { color: 'error', label: 'Not Significant (p≥0.1)', level: 'none' };
  };

  // Helper function to format p-values
  const formatPValue = (pValue: number) => {
    if (pValue < 0.001) return '<0.001';
    if (pValue < 0.01) return pValue.toFixed(4);
    return pValue.toFixed(3);
  };

  // Prepare comparison data
  const testResults = [
    {
      name: 'Student\'s t-Test',
      description: 'Parametric test comparing means of two groups',
      statistic: tTest.statistic.toFixed(4),
      statisticLabel: 't-statistic',
      pValue: tTest.pValue,
      isSignificant: tTest.isSignificant,
      additionalInfo: `df=${tTest.degreesOfFreedom}, CI=[${tTest.confidenceInterval[0].toFixed(3)}, ${tTest.confidenceInterval[1].toFixed(3)}]`,
      assumptions: ['Normal distribution', 'Equal variances', 'Independent samples']
    },
    {
      name: 'Mann-Whitney U Test',
      description: 'Non-parametric alternative to t-test',
      statistic: mannWhitney.uStatistic.toFixed(2),
      statisticLabel: 'U-statistic',
      pValue: mannWhitney.pValue,
      isSignificant: mannWhitney.isSignificant,
      additionalInfo: `z=${mannWhitney.zScore.toFixed(4)}, Rank sums: ${mannWhitney.rankSums.group1.toFixed(1)}, ${mannWhitney.rankSums.group2.toFixed(1)}`,
      assumptions: ['Independent samples', 'Ordinal data']
    },
    {
      name: 'Kolmogorov-Smirnov Test',
      description: 'Tests for differences in distributions',
      statistic: kolmogorov.kStatistic.toFixed(4),
      statisticLabel: 'K-statistic',
      pValue: kolmogorov.pValue,
      isSignificant: kolmogorov.isSignificant,
      additionalInfo: `Critical value=${kolmogorov.criticalValue.toFixed(4)}, Max divergence=${kolmogorov.maxDivergence.toFixed(4)}`,
      assumptions: ['Continuous distributions', 'Independent samples']
    },
    {
      name: 'Chi-Square Test',
      description: 'Tests for independence or goodness of fit',
      statistic: chiSquare.chiSquareStatistic.toFixed(4),
      statisticLabel: 'χ²-statistic',
      pValue: chiSquare.pValue,
      isSignificant: chiSquare.isSignificant,
      additionalInfo: `df=${chiSquare.degreesOfFreedom}`,
      assumptions: ['Expected frequencies ≥5', 'Independent observations']
    }
  ];

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Statistical Tests Comparison
        </Typography>
        
        {/* Summary Overview */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" gutterBottom>
            Test Results Summary
          </Typography>
          <Grid container spacing={1}>
            {testResults.map((test) => {
              const sigInfo = getSignificanceInfo(test.pValue, test.isSignificant);
              return (
                <Grid item xs={6} md={3} key={test.name}>
                  <Card variant="outlined" sx={{ p: 1, height: '100%' }}>
                    <Typography variant="caption" color="text.secondary">
                      {test.name}
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', mt: 0.5 }}>
                      <Chip
                        size="small"
                        color={sigInfo.color as any}
                        label={test.isSignificant ? 'Sig' : 'NS'}
                      />
                      <Typography variant="body2" sx={{ ml: 1 }}>
                        p={formatPValue(test.pValue)}
                      </Typography>
                    </Box>
                  </Card>
                </Grid>
              );
            })}
          </Grid>
        </Box>

        {/* Detailed Results Table */}
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell><strong>Test</strong></TableCell>
                <TableCell align="center"><strong>Statistic</strong></TableCell>
                <TableCell align="center"><strong>P-Value</strong></TableCell>
                <TableCell align="center"><strong>Significance</strong></TableCell>
                <TableCell align="center"><strong>Strength</strong></TableCell>
                <TableCell><strong>Additional Info</strong></TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {testResults.map((test) => {
                const sigInfo = getSignificanceInfo(test.pValue, test.isSignificant);
                return (
                  <TableRow key={test.name} hover>
                    <TableCell>
                      <Box>
                        <Typography variant="subtitle2">
                          {test.name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {test.description}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell align="center">
                      <Typography variant="body2">
                        {test.statisticLabel.split('-')[0]}: {test.statistic}
                      </Typography>
                    </TableCell>
                    <TableCell align="center">
                      <Typography 
                        variant="body2" 
                        fontWeight="bold"
                        color={`${sigInfo.color}.main`}
                      >
                        {formatPValue(test.pValue)}
                      </Typography>
                    </TableCell>
                    <TableCell align="center">
                      <Chip
                        size="small"
                        color={sigInfo.color as any}
                        label={test.isSignificant ? 'Significant' : 'Not Significant'}
                      />
                    </TableCell>
                    <TableCell align="center">
                      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Box sx={{ width: '60px', mr: 1 }}>
                          <LinearProgress
                            variant="determinate"
                            value={Math.max(0, Math.min(100, (1 - test.pValue) * 100))}
                            color={sigInfo.color as any}
                            sx={{ height: 8, borderRadius: 1 }}
                          />
                        </Box>
                        <Typography variant="caption">
                          {sigInfo.level === 'high' ? 'Strong' : 
                           sigInfo.level === 'medium' ? 'Moderate' : 
                           sigInfo.level === 'low' ? 'Weak' : 'None'}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption">
                        {test.additionalInfo}
                      </Typography>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>

        {/* Test Assumptions and Recommendations */}
        <Box sx={{ mt: 3 }}>
          <Typography variant="subtitle2" gutterBottom>
            Test Assumptions & Recommendations
          </Typography>
          <Grid container spacing={2}>
            {testResults.map((test) => {
              const sigInfo = getSignificanceInfo(test.pValue, test.isSignificant);
              return (
                <Grid item xs={12} md={6} key={test.name}>
                  <Card variant="outlined" sx={{ height: '100%' }}>
                    <CardContent sx={{ pb: 2 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                        <Typography variant="subtitle2">
                          {test.name}
                        </Typography>
                        <Chip
                          size="small"
                          color={sigInfo.color as any}
                          label={sigInfo.level}
                          sx={{ ml: 'auto' }}
                        />
                      </Box>
                      
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Key Assumptions:
                      </Typography>
                      <Box sx={{ mb: 2 }}>
                        {test.assumptions.map((assumption, index) => (
                          <Typography key={index} variant="caption" sx={{ display: 'block' }}>
                            • {assumption}
                          </Typography>
                        ))}
                      </Box>

                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Recommendation:
                      </Typography>
                      <Typography variant="caption">
                        {test.name === 'Student\'s t-Test' && (
                          test.isSignificant 
                            ? 'Strong evidence for difference in means if normality assumptions hold.'
                            : 'No evidence for difference. Consider effect size and power analysis.'
                        )}
                        {test.name === 'Mann-Whitney U Test' && (
                          test.isSignificant
                            ? 'Robust non-parametric evidence for difference in distributions.'
                            : 'No evidence for distributional differences. Less sensitive to outliers.'
                        )}
                        {test.name === 'Kolmogorov-Smirnov Test' && (
                          test.isSignificant
                            ? 'Evidence for differences in distribution shape/location.'
                            : 'Distributions appear similar. Consider specific distribution tests.'
                        )}
                        {test.name === 'Chi-Square Test' && (
                          test.isSignificant
                            ? 'Evidence against independence or goodness of fit.'
                            : 'No evidence against null hypothesis. Check expected frequencies.'
                        )}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              );
            })}
          </Grid>
        </Box>

        {/* Interpretation Guidelines */}
        <Box sx={{ mt: 3, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom>
            Interpretation Guidelines
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <Typography variant="caption" gutterBottom>
                <strong>P-Value Significance Levels:</strong>
              </Typography>
              <Box sx={{ ml: 1 }}>
                <Typography variant="caption" sx={{ display: 'block' }}>
                  • p &lt; 0.001: Highly significant (strong evidence)
                </Typography>
                <Typography variant="caption" sx={{ display: 'block' }}>
                  • p &lt; 0.01: Very significant (convincing evidence)
                </Typography>
                <Typography variant="caption" sx={{ display: 'block' }}>
                  • p &lt; 0.05: Significant (moderate evidence)
                </Typography>
                <Typography variant="caption" sx={{ display: 'block' }}>
                  • p &lt; 0.10: Marginally significant (weak evidence)
                </Typography>
                <Typography variant="caption" sx={{ display: 'block' }}>
                  • p ≥ 0.10: Not significant (insufficient evidence)
                </Typography>
              </Box>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="caption" gutterBottom>
                <strong>Test Selection Guidelines:</strong>
              </Typography>
              <Box sx={{ ml: 1 }}>
                <Typography variant="caption" sx={{ display: 'block' }}>
                  • Use t-test when data is normally distributed
                </Typography>
                <Typography variant="caption" sx={{ display: 'block' }}>
                  • Use Mann-Whitney when assumptions are violated
                </Typography>
                <Typography variant="caption" sx={{ display: 'block' }}>
                  • Use K-S test for distribution shape differences
                </Typography>
                <Typography variant="caption" sx={{ display: 'block' }}>
                  • Use Chi-square for categorical data analysis
                </Typography>
                <Typography variant="caption" sx={{ display: 'block' }}>
                  • Consider multiple tests for robust conclusions
                </Typography>
              </Box>
            </Grid>
          </Grid>
        </Box>
      </CardContent>
    </Card>
  );
};