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
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';

const drawerWidth = 240;

const menuItems = [
  { text: 'Dashboard', icon: <Dashboard />, path: '/' },
  { text: 'Projects', icon: <FolderOpen />, path: '/projects' },
  { text: 'Ground Truth', icon: <VideoLibrary />, path: '/ground-truth' },
  { text: 'Test Execution', icon: <PlayArrow />, path: '/test-execution' },
  { text: 'Results', icon: <Assessment />, path: '/results' },
  { text: 'Datasets', icon: <Dataset />, path: '/datasets' },
  { text: 'Audit Logs', icon: <Security />, path: '/audit-logs' },
  { text: 'Settings', icon: <Settings />, path: '/settings' },
];

const Sidebar: React.FC = () => {
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
          <VideoLibrary color="primary" />
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