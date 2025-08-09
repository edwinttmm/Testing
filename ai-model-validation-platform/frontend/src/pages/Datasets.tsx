import React from 'react';
import { Box, Typography } from '@mui/material';

const Datasets: React.FC = () => {
  return (
    <Box>
      <Typography variant="h4">Dataset Management</Typography>
      <Typography variant="body1" sx={{ mt: 2 }}>
        Dataset management and annotation workflow will be implemented here.
      </Typography>
    </Box>
  );
};

export default Datasets;