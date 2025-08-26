import React from 'react';
import {
  Drawer,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemButton,
  Toolbar,
  Typography,
  Box,
} from '@mui/material';
import {
  Dashboard,
  FolderOpen,
  VideoLibrary,
  PlayArrow,
  Assessment,
  Dataset,
  Security,
  Settings,
  PlayCircle,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';

const drawerWidth = 240;

// Create icon elements outside of component for better performance
const DashboardIcon = React.createElement(Dashboard);
const FolderOpenIcon = React.createElement(FolderOpen);
const VideoLibraryIcon = React.createElement(VideoLibrary);
const PlayArrowIcon = React.createElement(PlayArrow);
const PlayCircleIcon = React.createElement(PlayCircle);
const AssessmentIcon = React.createElement(Assessment);
const DatasetIcon = React.createElement(Dataset);
const SecurityIcon = React.createElement(Security);
const SettingsIcon = React.createElement(Settings);
const VideoLibraryPrimaryIcon = React.createElement(VideoLibrary, { color: 'primary' });

const menuItems = [
  { text: 'Dashboard', icon: DashboardIcon, path: '/' },
  { text: 'Projects', icon: FolderOpenIcon, path: '/projects' },
  { text: 'Ground Truth', icon: VideoLibraryIcon, path: '/ground-truth' },
  { text: 'Test Execution', icon: PlayArrowIcon, path: '/test-execution' },
  { text: 'Enhanced Test', icon: PlayCircleIcon, path: '/enhanced-test-execution' },
  { text: 'Results', icon: AssessmentIcon, path: '/results' },
  { text: 'Datasets', icon: DatasetIcon, path: '/datasets' },
  { text: 'Audit Logs', icon: SecurityIcon, path: '/audit-logs' },
  { text: 'Settings', icon: SettingsIcon, path: '/settings' },
];

const Sidebar = () => {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: drawerWidth,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: drawerWidth,
          boxSizing: 'border-box',
        },
      }}
    >
      <Toolbar>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {VideoLibraryPrimaryIcon}
          <Typography variant="h6" noWrap component="div">
            VRU Validation
          </Typography>
        </Box>
      </Toolbar>
      <List>
        {menuItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton
              selected={location.pathname === item.path}
              onClick={() => navigate(item.path)}
            >
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </Drawer>
  );
};

export default Sidebar;