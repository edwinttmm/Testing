// Optimized Material-UI imports to reduce bundle size
// Instead of importing from '@mui/material', import specific components

// Core components
export { default as Box } from '@mui/material/Box';
export { default as Typography } from '@mui/material/Typography';
export { default as Button } from '@mui/material/Button';
export { default as Card } from '@mui/material/Card';
export { default as CardContent } from '@mui/material/CardContent';
export { default as CardActions } from '@mui/material/CardActions';
export { default as Grid } from '@mui/material/Grid';
export { default as Skeleton } from '@mui/material/Skeleton';
export { default as CircularProgress } from '@mui/material/CircularProgress';
export { default as LinearProgress } from '@mui/material/LinearProgress';
export { default as Alert } from '@mui/material/Alert';

// Form components
export { default as TextField } from '@mui/material/TextField';
export { default as FormControl } from '@mui/material/FormControl';
export { default as InputLabel } from '@mui/material/InputLabel';
export { default as Select } from '@mui/material/Select';
export { default as MenuItem } from '@mui/material/MenuItem';
export { default as Chip } from '@mui/material/Chip';

// Dialog components
export { default as Dialog } from '@mui/material/Dialog';
export { default as DialogTitle } from '@mui/material/DialogTitle';
export { default as DialogContent } from '@mui/material/DialogContent';
export { default as DialogActions } from '@mui/material/DialogActions';

// Navigation components
export { default as IconButton } from '@mui/material/IconButton';
export { default as Menu } from '@mui/material/Menu';

// Theme and styling
export { ThemeProvider, createTheme } from '@mui/material/styles';
export { default as CssBaseline } from '@mui/material/CssBaseline';

// Icons - import only what's needed
export { 
  Add,
  MoreVert,
  Visibility,
  Edit,
  Delete,
  Camera,
  Refresh,
  FolderOpen,
  VideoLibrary,
  Assessment,
  TrendingUp,
} from '@mui/icons-material';