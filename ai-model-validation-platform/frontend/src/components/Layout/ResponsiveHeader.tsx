import React from 'react';
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
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  Notifications,
  AccountCircle,
  Person,
  Menu as MenuIcon,
} from '@mui/icons-material';

interface ResponsiveHeaderProps {
  onMobileMenuToggle: () => void;
}

const ResponsiveHeader: React.FC<ResponsiveHeaderProps> = ({ onMobileMenuToggle }) => {
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

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

  const handleLogout = () => {
    handleClose();
    // No authentication - just close menu
  };

  // Handle keyboard navigation for menu
  const handleMenuKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Escape') {
      handleClose();
    }
  };

  const handleProfileKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleProfile();
    }
  };

  return (
    <AppBar 
      position="static" 
      color="transparent" 
      elevation={0}
      sx={{ 
        mb: 3, 
        borderBottom: '1px solid #e0e0e0',
        width: '100%',
      }}
    >
      <Toolbar sx={{ justifyContent: 'space-between', minHeight: '64px !important' }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          {isMobile && (
            <IconButton
              color="inherit"
              aria-label="Open navigation menu"
              edge="start"
              onClick={onMobileMenuToggle}
              sx={{ 
                mr: 2,
                '&:focus': {
                  outline: `2px solid ${theme.palette.primary.main}`,
                  outlineOffset: 2,
                }
              }}
            >
              <MenuIcon />
            </IconButton>
          )}
          
          <Typography 
            variant={isMobile ? "h6" : "h5"} 
            component="div" 
            sx={{ 
              flexGrow: 1,
              fontWeight: 600,
              color: theme.palette.text.primary,
            }}
          >
            {isMobile ? "VRU Platform" : "AI Model Validation Platform"}
          </Typography>
        </Box>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <IconButton 
            size="large" 
            color="inherit"
            aria-label="View notifications (4 unread)"
            sx={{
              '&:focus': {
                outline: `2px solid ${theme.palette.primary.main}`,
                outlineOffset: 2,
              }
            }}
          >
            <Badge badgeContent={4} color="error">
              <Notifications />
            </Badge>
          </IconButton>
          
          <IconButton
            size="large"
            onClick={handleMenu}
            onKeyDown={handleMenuKeyDown}
            color="inherit"
            aria-label="Open user menu"
            aria-controls={anchorEl ? 'user-menu' : undefined}
            aria-haspopup="true"
            aria-expanded={anchorEl ? 'true' : 'false'}
            sx={{
              '&:focus': {
                outline: `2px solid ${theme.palette.primary.main}`,
                outlineOffset: 2,
              }
            }}
          >
            <Avatar 
              sx={{ 
                width: 32, 
                height: 32, 
                bgcolor: 'primary.main',
                fontSize: '1rem',
              }}
              alt="Demo User Avatar"
            >
              <AccountCircle />
            </Avatar>
          </IconButton>
          
          <Menu
            id="user-menu"
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
            onKeyDown={handleMenuKeyDown}
            PaperProps={{
              sx: { 
                minWidth: 200,
                mt: 1,
                boxShadow: theme.shadows[3],
              },
              role: 'menu',
            }}
            MenuListProps={{
              'aria-labelledby': 'user-menu-button',
              role: 'menu',
            }}
          >
            <Box sx={{ px: 2, py: 1 }}>
              <Typography 
                variant="subtitle1" 
                fontWeight="medium"
                sx={{ color: theme.palette.text.primary }}
              >
                Demo User
              </Typography>
              <Typography 
                variant="body2" 
                color="text.secondary"
                sx={{ wordBreak: 'break-word' }}
              >
                demo@example.com
              </Typography>
            </Box>
            <Divider />
            <MenuItem 
              onClick={handleProfile}
              onKeyDown={handleProfileKeyDown}
              role="menuitem"
              sx={{
                '&:focus': {
                  backgroundColor: theme.palette.action.focus,
                }
              }}
            >
              <Person sx={{ mr: 1 }} aria-hidden="true" />
              Profile & Settings
            </MenuItem>
          </Menu>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default ResponsiveHeader;