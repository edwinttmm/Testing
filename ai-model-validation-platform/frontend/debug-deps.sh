#!/bin/bash

echo "======================================"
echo "🔍 DEPENDENCY DIAGNOSTIC REPORT"
echo "======================================"
echo

echo "📍 SYSTEM INFORMATION"
echo "---------------------"
echo "Date: $(date)"
echo "Working Directory: $(pwd)"
echo "User: $(whoami)"
echo "OS: $(uname -a)"
echo

echo "📦 NODE.JS ENVIRONMENT"
echo "----------------------"
echo "Node Version: $(node -v 2>/dev/null || echo 'Node.js not found')"
echo "NPM Version: $(npm -v 2>/dev/null || echo 'npm not found')"
echo "NPM Global Path: $(npm root -g 2>/dev/null || echo 'npm root not accessible')"
echo "NPM Cache Path: $(npm config get cache 2>/dev/null || echo 'npm cache not accessible')"
echo

echo "🏗️ PROJECT FILES STATUS"
echo "-----------------------"
echo "Package.json exists: $([ -f package.json ] && echo 'YES' || echo 'NO')"
echo "Package-lock.json exists: $([ -f package-lock.json ] && echo 'YES' || echo 'NO')"
echo "Node_modules exists: $([ -d node_modules ] && echo 'YES' || echo 'NO')"
echo "Dockerfile exists: $([ -f Dockerfile ] && echo 'YES' || echo 'NO')"
echo "Craco.config.js exists: $([ -f craco.config.js ] && echo 'YES' || echo 'NO')"
echo

echo "📋 PACKAGE.JSON ANALYSIS"
echo "------------------------"
if [ -f package.json ]; then
    echo "Package name: $(cat package.json | grep '"name"' | head -1)"
    echo "Package version: $(cat package.json | grep '"version"' | head -1)"
    echo
    echo "🎯 KEY DEPENDENCIES:"
    echo "React: $(cat package.json | grep '"react"' | head -1)"
    echo "React-DOM: $(cat package.json | grep '"react-dom"' | head -1)"
    echo "React-Router-DOM: $(cat package.json | grep '"react-router-dom"' | head -1)"
    echo "React-Scripts: $(cat package.json | grep '"react-scripts"' | head -1)"
    echo "TypeScript: $(cat package.json | grep '"typescript"' | head -1)"
    echo "Craco: $(cat package.json | grep '"@craco/craco"' | head -1)"
    echo
    echo "📜 ALL DEPENDENCIES:"
    cat package.json | sed -n '/"dependencies":/,/},/p'
    echo
    echo "🛠️ DEV DEPENDENCIES:"
    cat package.json | sed -n '/"devDependencies":/,/},/p'
    echo
    echo "🚀 SCRIPTS:"
    cat package.json | sed -n '/"scripts":/,/},/p'
else
    echo "❌ package.json not found!"
fi

echo
echo "🔒 PACKAGE-LOCK.JSON ANALYSIS"
echo "-----------------------------"
if [ -f package-lock.json ]; then
    echo "Lock file version: $(cat package-lock.json | grep '"lockfileVersion"' | head -1)"
    echo "Node version: $(cat package-lock.json | grep '"node"' | head -1)"
    echo "NPM version: $(cat package-lock.json | grep '"npm"' | head -1)"
    echo
    echo "🎯 CRACO IN LOCK FILE:"
    grep -A 5 -B 5 '"@craco/craco"' package-lock.json | head -20
else
    echo "❌ package-lock.json not found!"
fi

echo
echo "📁 NODE_MODULES STATUS"
echo "----------------------"
if [ -d node_modules ]; then
    echo "Node_modules size: $(du -sh node_modules 2>/dev/null || echo 'Cannot calculate size')"
    echo "Direct dependencies count: $(ls -1 node_modules | wc -l 2>/dev/null || echo 'Cannot count')"
    echo
    echo "🎯 KEY PACKAGES STATUS:"
    echo "React: $([ -d node_modules/react ] && echo 'INSTALLED' || echo 'MISSING')"
    echo "React-DOM: $([ -d node_modules/react-dom ] && echo 'INSTALLED' || echo 'MISSING')"
    echo "React-Router-DOM: $([ -d node_modules/react-router-dom ] && echo 'INSTALLED' || echo 'MISSING')"
    echo "React-Scripts: $([ -d node_modules/react-scripts ] && echo 'INSTALLED' || echo 'MISSING')"
    echo "TypeScript: $([ -d node_modules/typescript ] && echo 'INSTALLED' || echo 'MISSING')"
    echo "@craco/craco: $([ -d node_modules/@craco/craco ] && echo 'INSTALLED' || echo 'MISSING')"
    echo
    echo "🔧 BINARY STATUS:"
    echo "Craco binary: $([ -f node_modules/.bin/craco ] && echo 'EXISTS' || echo 'MISSING')"
    if [ -f node_modules/.bin/craco ]; then
        echo "Craco binary permissions: $(ls -la node_modules/.bin/craco)"
    fi
else
    echo "❌ node_modules directory not found!"
fi

echo
echo "🚨 POTENTIAL ISSUES CHECK"
echo "-------------------------"
echo "NPM Cache Issues: $(npm cache verify 2>&1 | grep -i 'error\|warn' | wc -l) warnings/errors"
echo "File Permissions: $(find . -name 'package*.json' -not -readable 2>/dev/null | wc -l) unreadable package files"
echo "Symlink Issues: $(find node_modules -type l 2>/dev/null | wc -l) symlinks in node_modules"

echo
echo "🐳 DOCKER CONTEXT (if applicable)"
echo "--------------------------------"
if [ -f Dockerfile ]; then
    echo "Dockerfile Node version: $(grep '^FROM node' Dockerfile)"
    echo "Dockerfile commands: $(grep -c '^RUN\|^COPY\|^CMD' Dockerfile) commands"
fi

if [ -f ../docker-compose.yml ]; then
    echo "Docker-compose frontend service: $(grep -A 10 'frontend:' ../docker-compose.yml | head -10)"
fi

echo
echo "📊 INSTALLATION RECOMMENDATIONS"
echo "------------------------------"
if [ ! -d node_modules ]; then
    echo "1. Run: npm install"
elif [ ! -f node_modules/.bin/craco ]; then
    echo "1. Craco missing - Run: npm install @craco/craco --save-dev"
else
    echo "1. Dependencies appear to be installed"
fi

echo "2. Clear cache if issues persist: npm cache clean --force"
echo "3. Delete node_modules and reinstall: rm -rf node_modules package-lock.json && npm install"
echo "4. Check Node version compatibility: node -v (should be 20.0.0+)"

echo
echo "======================================"
echo "✅ DIAGNOSTIC COMPLETE"
echo "======================================"