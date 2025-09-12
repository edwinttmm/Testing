#!/bin/bash
# CVAT Redis Authentication Fix Script
# This script patches the CVAT container to support Redis authentication

set -e

echo "🔧 Applying CVAT Redis Authentication Fix..."

# Check if we're running inside the CVAT container
if [[ ! -f "/home/django/supervisord.conf" ]]; then
    echo "❌ Error: Not running inside CVAT container or supervisord.conf not found"
    exit 1
fi

# Backup original supervisord.conf
cp /home/django/supervisord.conf /home/django/supervisord.conf.backup
echo "✅ Backed up original supervisord.conf"

# Stop existing RQ processes
echo "🛑 Stopping existing RQ processes..."
supervisorctl stop rqscheduler rqworker_default_0 rqworker_default_1 rqworker_low 2>/dev/null || true

# Update supervisord.conf to include Redis authentication
echo "🔧 Updating supervisord configuration..."

# Replace rqscheduler section
sed -i '/\[program:rqscheduler\]/,/^$/c\
[program:rqscheduler]\
command=%(ENV_HOME)s/wait-for-it.sh %(ENV_CVAT_REDIS_HOST)s:6379 -t 0 -- bash -ic \\\
    "python3 /opt/venv/bin/rqscheduler --host %(ENV_CVAT_REDIS_HOST)s --password %(ENV_CVAT_REDIS_PASSWORD)s -i 30"\
environment=SSH_AUTH_SOCK="/tmp/ssh-agent.sock"\
numprocs=1\
priority=950\
' /home/django/supervisord.conf

# Replace rqworker sections to use RQ_REDIS_URL environment variable
sed -i '/\[program:rqworker_default_0\]/,/^$/c\
[program:rqworker_default_0]\
command=%(ENV_HOME)s/wait-for-it.sh %(ENV_CVAT_REDIS_HOST)s:6379 -t 0 -- bash -ic \\\
    "python3 ~/manage.py rqworker default --worker-class cvat.rqworker.SimpleWorker"\
environment=SSH_AUTH_SOCK="/tmp/ssh-agent.sock",RQ_REDIS_URL="redis://:%(ENV_CVAT_REDIS_PASSWORD)s@%(ENV_CVAT_REDIS_HOST)s:6379/0"\
numprocs=1\
priority=920\
' /home/django/supervisord.conf

sed -i '/\[program:rqworker_default_1\]/,/^$/c\
[program:rqworker_default_1]\
command=%(ENV_HOME)s/wait-for-it.sh %(ENV_CVAT_REDIS_HOST)s:6379 -t 0 -- bash -ic \\\
    "python3 ~/manage.py rqworker default --worker-class cvat.rqworker.SimpleWorker"\
environment=SSH_AUTH_SOCK="/tmp/ssh-agent.sock",RQ_REDIS_URL="redis://:%(ENV_CVAT_REDIS_PASSWORD)s@%(ENV_CVAT_REDIS_HOST)s:6379/0"\
numprocs=1\
priority=920\
' /home/django/supervisord.conf

sed -i '/\[program:rqworker_low\]/,/^$/c\
[program:rqworker_low]\
command=%(ENV_HOME)s/wait-for-it.sh %(ENV_CVAT_REDIS_HOST)s:6379 -t 0 -- bash -ic \\\
    "python3 ~/manage.py rqworker low --worker-class cvat.rqworker.SimpleWorker"\
environment=SSH_AUTH_SOCK="/tmp/ssh-agent.sock",RQ_REDIS_URL="redis://:%(ENV_CVAT_REDIS_PASSWORD)s@%(ENV_CVAT_REDIS_HOST)s:6379/0"\
numprocs=1\
priority=920\
' /home/django/supervisord.conf

echo "✅ Updated supervisord configuration"

# Reload supervisord configuration
echo "🔄 Reloading supervisord configuration..."
supervisorctl reread
supervisorctl update

# Start the updated processes
echo "🚀 Starting Redis-authenticated processes..."
supervisorctl start rqscheduler rqworker_default_0 rqworker_default_1 rqworker_low

# Check process status
echo "📊 Process Status:"
supervisorctl status | grep -E "(rqscheduler|rqworker)"

echo "✅ CVAT Redis Authentication Fix Applied Successfully!"
echo "🔍 Check logs for any remaining authentication errors."