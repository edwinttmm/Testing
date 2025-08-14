import React, { useState, useEffect } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Badge,
  Avatar,
  Menu,
  MenuItem,
  Box,
  Divider,
} from '@mui/material';
import {
  Notifications,
  AccountCircle,
  Person,
} from '@mui/icons-material';
import { apiService } from '../../services/api';

const Header: React.FC = () => {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [notificationCount, setNotificationCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);

  const handleMenu = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleProfile = () => {
    handleClose();
    // Navigate to settings - placeholder
    window.location.href = '/settings';
  };

  // Load notification count from API
  useEffect(() => {
    const loadNotifications = async () => {
      try {
        setLoading(true);
        // Try to get notification count from dashboard stats
        const stats = await apiService.getDashboardStats();
        // For now, calculate from active tests or use a default
        setNotificationCount(stats.activeTests || 0);
      } catch (error) {
        console.error('Failed to load notifications:', error);
        // Fallback to 0 if API fails
        setNotificationCount(0);
      } finally {
        setLoading(false);
      }
    };
    
    loadNotifications();
  }, []);


  return (
    <AppBar 
      position="static" 
      color="transparent" 
      elevation={0}
      sx={{ mb: 3, borderBottom: '1px solid #e0e0e0' }}
    >
      <Toolbar sx={{ justifyContent: 'space-between' }}>
        <Typography variant="h5" component="div" sx={{ flexGrow: 1 }}>
          AI Model Validation Platform
        </Typography>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <IconButton size="large" color="inherit">
            <Badge badgeContent={loading ? 0 : notificationCount} color="error">
              <Notifications />
            </Badge>
          </IconButton>
          
          <IconButton
            size="large"
            onClick={handleMenu}
            color="inherit"
          >
            <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.main' }}>
              <AccountCircle />
            </Avatar>
          </IconButton>
          
          <Menu
            anchorEl={anchorEl}
            anchorOrigin={{
              vertical: 'bottom',
              horizontal: 'right',
            }}
            keepMounted
            transformOrigin={{
              vertical: 'top',
              horizontal: 'right',
            }}
            open={Boolean(anchorEl)}
            onClose={handleClose}
            PaperProps={{
              sx: { minWidth: 200 }
            }}
          >
            <Box sx={{ px: 2, py: 1 }}>
              <Typography variant="subtitle1" fontWeight="medium">
                Demo User
              </Typography>
              <Typography variant="body2" color="text.secondary">
                demo@example.com
              </Typography>
            </Box>
            <Divider />
            <MenuItem onClick={handleProfile}>
              <Person sx={{ mr: 1 }} />
              Profile & Settings
            </MenuItem>
          </Menu>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Header;