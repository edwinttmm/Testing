#!/bin/bash

# Process Cleanup Script for Frontend Development
# Kills all hanging Node/React/webpack processes and frees up ports

echo "🧹 Starting comprehensive process cleanup..."

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 1. Kill all Node.js processes related to React/webpack/CRACO
log "Killing all React/webpack/CRACO processes..."
pkill -f "node.*craco" 2>/dev/null || true
pkill -f "npm start" 2>/dev/null || true
pkill -f "fork-ts-checker" 2>/dev/null || true
pkill -f "tsc --noEmit" 2>/dev/null || true
pkill -f "webpack" 2>/dev/null || true
pkill -f "react-scripts" 2>/dev/null || true

# 2. Force kill processes on critical ports
log "Freeing up ports 3000-3002, 8080, 8000..."
for port in 3000 3001 3002 8080 8000; do
    lsof -ti:$port 2>/dev/null | xargs -r kill -9 2>/dev/null || true
done

# 3. Clean up Node.js temporary files
log "Clearing Node.js cache and temporary files..."
rm -rf /tmp/.tmp* 2>/dev/null || true
rm -rf /tmp/npm-* 2>/dev/null || true
rm -rf ~/.npm/_logs/* 2>/dev/null || true

# 4. Clear build cache
log "Clearing build cache..."
rm -rf node_modules/.cache 2>/dev/null || true
rm -rf .eslintcache 2>/dev/null || true

# 5. Clear package manager caches
log "Clearing package manager caches..."
npm cache clean --force 2>/dev/null || true
yarn cache clean 2>/dev/null || true

# 6. Wait for processes to fully terminate
log "Waiting for processes to terminate..."
sleep 3

# 7. Verify cleanup
log "Verifying cleanup..."
REMAINING_PROCESSES=$(ps aux | grep -E "(node.*craco|npm start|fork-ts-checker)" | grep -v grep | wc -l)
OCCUPIED_PORTS=$(netstat -tulpn 2>/dev/null | grep -E ":(3000|3001|3002)" | wc -l)

if [ "$REMAINING_PROCESSES" -eq 0 ] && [ "$OCCUPIED_PORTS" -eq 0 ]; then
    log "✅ Cleanup successful! All processes killed and ports freed."
    exit 0
else
    log "⚠️  Some processes or ports may still be occupied:"
    log "   Remaining processes: $REMAINING_PROCESSES"
    log "   Occupied ports: $OCCUPIED_PORTS"
    exit 1
fi