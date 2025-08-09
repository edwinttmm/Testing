import React from 'react';
import { useParams } from 'react-router-dom';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  Button,
  Tab,
  Tabs,
} from '@mui/material';
import {
  PlayArrow,
  VideoLibrary,
  Assessment,
  Edit,
} from '@mui/icons-material';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`simple-tabpanel-${index}`}
      aria-labelledby={`simple-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

const ProjectDetail: React.FC = () => {
  const { id } = useParams();
  const [tabValue, setTabValue] = React.useState(0);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4">Highway VRU Detection</Typography>
          <Typography variant="body1" color="text.secondary">
            Testing front-facing camera detection on highway scenarios
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<Edit />}>
          Edit Project
        </Button>
      </Box>

      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 3 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Camera Details
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                <strong>Model:</strong> Sony IMX390
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                <strong>View:</strong> Front-facing VRU
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                <strong>Signal:</strong> GPIO
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                <strong>Resolution:</strong> 1920x1080
              </Typography>
              <Typography variant="body2">
                <strong>Frame Rate:</strong> 30 FPS
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 3 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Test Statistics
              </Typography>
              <Typography variant="h4" color="primary" gutterBottom>
                15
              </Typography>
              <Typography variant="body2" sx={{ mb: 2 }}>
                Total Tests Completed
              </Typography>
              <Chip label="Active" color="success" size="small" />
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 3 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Accuracy
              </Typography>
              <Typography variant="h4" color="success.main" gutterBottom>
                94.2%
              </Typography>
              <Typography variant="body2">
                Average Detection Accuracy
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 3 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Last Test
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                2 hours ago
              </Typography>
              <Typography variant="body2" color="success.main">
                92.5% accuracy
              </Typography>
              <Button
                size="small"
                startIcon={<PlayArrow />}
                sx={{ mt: 1 }}
              >
                Run New Test
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Card>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={tabValue} onChange={handleTabChange}>
            <Tab label="Ground Truth Videos" />
            <Tab label="Test Results" />
            <Tab label="Settings" />
          </Tabs>
        </Box>
        
        <TabPanel value={tabValue} index={0}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
            <VideoLibrary />
            <Typography variant="h6">Ground Truth Videos</Typography>
            <Button variant="outlined" size="small">
              Upload Video
            </Button>
          </Box>
          <Typography variant="body2" color="text.secondary">
            Ground truth videos and their processed detection data will be displayed here.
          </Typography>
        </TabPanel>
        
        <TabPanel value={tabValue} index={1}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
            <Assessment />
            <Typography variant="h6">Test Results</Typography>
          </Box>
          <Typography variant="body2" color="text.secondary">
            Historical test results and performance metrics will be displayed here.
          </Typography>
        </TabPanel>
        
        <TabPanel value={tabValue} index={2}>
          <Typography variant="h6" gutterBottom>
            Project Settings
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Project configuration and advanced settings will be displayed here.
          </Typography>
        </TabPanel>
      </Card>
    </Box>
  );
};

export default ProjectDetail;