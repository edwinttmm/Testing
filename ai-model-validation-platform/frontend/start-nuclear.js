#!/usr/bin/env node

const { buildAndServe } = require('./webpack.nuclear.js');

console.log('🚀 Starting nuclear webpack build (NO WebSocket client)...');
console.log('🛡️  This will completely eliminate all WebSocket connections!');
console.log('');

buildAndServe();