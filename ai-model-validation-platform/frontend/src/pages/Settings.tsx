import React from 'react';
import { Box, Typography } from '@mui/material';

const Settings: React.FC = () => {
  return (
    <Box>
      <Typography variant="h4">Settings</Typography>
      <Typography variant="body1" sx={{ mt: 2 }}>
        System settings and configuration will be implemented here.
      </Typography>
    </Box>
  );
};

export default Settings;