/**
 * Migration Server
 * Standalone server for database migration operations
 * Run this alongside your main backend to provide migration endpoints
 */

const express = require('express');
const cors = require('cors');
const path = require('path');

// Database connection setup
const sqlite3 = require('sqlite3').verbose();
const { open } = require('sqlite');

const app = express();
const PORT = process.env.MIGRATION_PORT || 8001;

// Middleware
app.use(cors());
app.use(express.json());

// Database connection
let database;

async function initializeDatabase() {
    try {
        // Adjust path based on your database location
        const dbPath = process.env.DATABASE_PATH || path.join(__dirname, 'ai_validation.db');
        
        database = await open({
            filename: dbPath,
            driver: sqlite3.Database
        });
        
        console.log(`📄 Connected to database: ${dbPath}`);
        return database;
    } catch (error) {
        console.error('❌ Database connection failed:', error.message);
        process.exit(1);
    }
}

// Initialize migration routes
async function setupRoutes() {
    const migrationRoutes = require('./routes/migrations');
    const migrationRoutesHandler = migrationRoutes(database);
    
    app.use('/api/migrations', migrationRoutesHandler);
    
    // Health check endpoint
    app.get('/health', (req, res) => {
        res.json({
            success: true,
            message: 'Migration server is healthy',
            timestamp: new Date().toISOString(),
            database: database ? 'connected' : 'disconnected'
        });
    });
    
    // Root endpoint
    app.get('/', (req, res) => {
        res.json({
            success: true,
            message: 'Database Migration API Server',
            version: '1.0.0',
            endpoints: {
                health: 'GET /health',
                migrations: 'GET|POST /api/migrations/*',
                documentation: 'GET /api/migrations/docs'
            }
        });
    });
}

// Error handling middleware
app.use((error, req, res, next) => {
    console.error('❌ Server error:', error);
    
    res.status(500).json({
        success: false,
        error: 'Internal server error',
        message: process.env.NODE_ENV === 'development' ? error.message : 'Something went wrong'
    });
});

// 404 handler
app.use('*', (req, res) => {
    res.status(404).json({
        success: false,
        error: 'Endpoint not found',
        availableEndpoints: {
            health: 'GET /health',
            migrations: 'GET|POST /api/migrations/*'
        }
    });
});

// Graceful shutdown
process.on('SIGTERM', async () => {
    console.log('🔄 Graceful shutdown initiated...');
    
    if (database) {
        await database.close();
        console.log('📄 Database connection closed');
    }
    
    process.exit(0);
});

process.on('SIGINT', async () => {
    console.log('\\n🔄 Graceful shutdown initiated...');
    
    if (database) {
        await database.close();
        console.log('📄 Database connection closed');
    }
    
    process.exit(0);
});

// Start server
async function startServer() {
    try {
        await initializeDatabase();
        await setupRoutes();
        
        app.listen(PORT, '0.0.0.0', () => {
            console.log('🚀 DATABASE MIGRATION SERVER STARTED');
            console.log('=====================================');
            console.log(`📡 Server: http://localhost:${PORT}`);
            console.log(`🌐 External: http://155.138.239.131:${PORT}`);
            console.log(`📄 Database: ${process.env.DATABASE_PATH || 'ai_validation.db'}`);
            console.log('\\n📋 Available Endpoints:');
            console.log(`  Health Check: GET /health`);
            console.log(`  Migration Status: GET /api/migrations/status`);
            console.log(`  Execute Migration: POST /api/migrations/execute`);
            console.log(`  API Documentation: GET /api/migrations/docs`);
            console.log('\\n🛠️  CLI Usage:');
            console.log(`  npm run migrate status`);
            console.log(`  npm run migrate dry-run`);
            console.log(`  npm run migrate execute`);
            console.log('=====================================');
        });
        
    } catch (error) {
        console.error('❌ Failed to start migration server:', error.message);
        process.exit(1);
    }
}

// Start the server
if (require.main === module) {
    startServer();
}

module.exports = { app, initializeDatabase };