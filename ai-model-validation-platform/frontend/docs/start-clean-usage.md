# Stable React Development Server - Usage Guide

## Overview

The `start-clean.sh` script provides a stable, single-instance React development server that eliminates the auto-refresh/auto-opening issue by addressing the root cause: **process proliferation from multiple development servers**.

## Root Cause Analysis (5 Why)

1. **Why does localhost:3000 auto-refresh/auto-open?**
   → Multiple development servers running simultaneously

2. **Why are multiple development servers running?**
   → Previous sessions not properly terminated

3. **Why weren't previous sessions terminated?**
   → No comprehensive cleanup mechanism

4. **Why no cleanup mechanism?**
   → Scripts didn't handle process management

5. **Why didn't scripts handle process management?**
   → No single, stable startup solution existed

**ROOT CAUSE**: Process proliferation from multiple development servers
**SOLUTION**: Comprehensive cleanup + single stable instance

## Quick Start

```bash
# Navigate to frontend directory
cd /home/rigade/Testing/ai-model-validation-platform/frontend

# Run the stable startup script
./start-clean.sh
```

## What the Script Does

### 1. Comprehensive Process Cleanup
- Kills all existing Node.js processes (npm, webpack, craco)
- Frees up development ports (3000-3005, 8080)
- Ensures complete process termination

### 2. Port Availability Check
- Verifies port 3000 is available
- Force-kills any stubborn processes
- Validates port is truly free

### 3. Environment Setup
- Creates stable `.env.local` configuration
- Disables browser auto-opening (`BROWSER=none`)
- Optimizes for development stability
- Configures memory management

### 4. Dependency Verification
- Checks for `node_modules`
- Installs dependencies if missing
- Ensures project is ready to run

### 5. Process Lock Creation
- Creates lock file to prevent multiple instances
- Tracks process ID for proper cleanup
- Prevents server proliferation

### 6. Single Stable Server
- Starts one development server only
- Uses optimized configuration
- Provides clean shutdown on Ctrl+C

## Configuration Details

The script configures these critical environment variables:

```bash
# Browser Control - PREVENTS AUTO-OPENING
BROWSER=none
REACT_APP_BROWSER=none

# Development Optimizations
SKIP_PREFLIGHT_CHECK=true
DISABLE_ESLINT_PLUGIN=true
TSC_COMPILE_ON_ERROR=true
ESLINT_NO_DEV_ERRORS=true
GENERATE_SOURCEMAP=false

# Performance & Stability
FAST_REFRESH=false
NODE_OPTIONS=--max-old-space-size=2048
CHOKIDAR_USEPOLLING=false
WATCHPACK_POLLING=false
```

## Usage Scenarios

### Normal Development
```bash
./start-clean.sh
# Navigate to http://localhost:3000 manually
```

### After System Issues
```bash
# If you have multiple servers running or browser auto-opening
./start-clean.sh
# Script will clean up everything and start fresh
```

### Debugging Server Issues
```bash
# Check what processes are running on port 3000
lsof -i :3000

# Run the cleanup script
./start-clean.sh
```

## Features

✅ **Process Cleanup**: Kills all existing Node.js development processes
✅ **Single Instance**: Ensures only one development server runs
✅ **Auto-Browser Disabled**: Prevents automatic browser opening
✅ **Stable Configuration**: Uses consistent environment variables
✅ **Port Conflict Prevention**: Handles port conflicts gracefully
✅ **Memory Optimization**: Configures appropriate memory limits
✅ **Lock File Protection**: Prevents multiple script instances
✅ **Clean Shutdown**: Proper cleanup on Ctrl+C

## Troubleshooting

### Port Still in Use
If you get port errors after running the script:
```bash
# Manually check what's using the port
sudo lsof -i :3000

# Kill the process manually
sudo kill -9 <PID>

# Run the script again
./start-clean.sh
```

### Permission Issues
If you get permission errors:
```bash
# Make sure script is executable
chmod +x start-clean.sh

# Run with proper permissions
sudo ./start-clean.sh
```

### Dependencies Missing
If dependencies are missing:
```bash
# The script will automatically install them, but you can also run manually
npm install

# Then run the script
./start-clean.sh
```

## Comparison with Other Methods

| Method | Browser Auto-Open | Process Cleanup | Stability | Performance |
|--------|------------------|----------------|-----------|-------------|
| `npm start` | ❌ Opens browser | ❌ No cleanup | ❌ Unstable | ⚠️ Variable |
| `BROWSER=none npm start` | ✅ Disabled | ❌ No cleanup | ⚠️ May conflict | ⚠️ Variable |
| `./start-clean.sh` | ✅ Disabled | ✅ Complete cleanup | ✅ Stable | ✅ Optimized |

## Files Created/Modified

The script creates or modifies these files:

- `.env.local` - Stable development configuration
- `/tmp/react-dev-server.lock` - Process lock file
- `/tmp/react-dev-server.pid` - Process ID tracking

## Expected Output

When running the script, you should see:

```
==============================================================================
          STABLE REACT DEVELOPMENT SERVER STARTUP SCRIPT
==============================================================================

Step 1: Comprehensive Process Cleanup
  → Killing all node processes...
  → Killing processes on development ports...
  → Waiting for processes to terminate...
  → Final cleanup of any remaining processes...
✓ Process cleanup completed

Step 2: Port Availability Check
✓ Port 3000 is available

Step 3: Environment Setup
✓ Environment configuration created

Step 4: Dependency Check
  → Dependencies already installed
✓ Dependencies verified

Step 5: Process Lock Creation
✓ Process lock created

Step 6: Starting Single Development Server

Configuration:
  → Port: 3000
  → Browser Auto-Open: DISABLED
  → Hot Reload: DISABLED (for stability)
  → ESLint: DISABLED (for performance)
  → Source Maps: DISABLED (for performance)
  → Memory Limit: 2GB

Starting React development server...
Navigate to http://localhost:3000 manually in your browser
Press Ctrl+C to stop the server
```

## Security Notes

- The script uses `sudo` for process cleanup to ensure complete termination
- Lock files are created in `/tmp` directory
- No sensitive information is logged or stored
- Processes are properly cleaned up on exit

## Performance Benefits

- **Faster startup**: No conflicting processes
- **Stable operation**: Single server instance
- **Reduced memory usage**: Optimized configuration
- **No browser interference**: Manual navigation only
- **Clean environment**: Fresh start every time

## Support

If you encounter issues with the script:

1. Check the console output for specific error messages
2. Verify you have the necessary permissions
3. Ensure Node.js and npm are properly installed
4. Try running the cleanup steps manually if needed

The script is designed to be robust and handle most common development server issues automatically.