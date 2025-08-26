/**
 * Migration Routes
 * API routes for database migration operations
 */

const express = require('express');
const router = express.Router();

// Middleware for API key authentication (optional)
const authenticate = (req, res, next) => {
    const apiKey = req.headers['x-api-key'] || req.query.apiKey;
    
    // In production, validate against environment variable
    const validApiKey = process.env.MIGRATION_API_KEY;
    
    if (validApiKey && apiKey !== validApiKey) {
        return res.status(401).json({
            success: false,
            error: 'Invalid API key'
        });
    }
    
    next();
};

// Initialize migration controller
const initializeMigrationRoutes = (database) => {
    const MigrationController = require('../controllers/MigrationController');
    const migrationController = new MigrationController(database);

    // Apply authentication middleware to all routes
    if (process.env.MIGRATION_API_KEY) {
        router.use(authenticate);
    }

    /**
     * GET /api/migrations/status
     * Get migration system status and overview
     */
    router.get('/status', async (req, res) => {
        await migrationController.getStatus(req, res);
    });

    /**
     * POST /api/migrations/analyze
     * Analyze database schema for URL columns
     */
    router.post('/analyze', async (req, res) => {
        await migrationController.analyzeSchema(req, res);
    });

    /**
     * POST /api/migrations/execute
     * Execute URL migration with safety checks
     * 
     * Body parameters:
     * - migrationName: string (default: '001_fix_localhost_urls')
     * - dryRun: boolean (default: false)
     * - force: boolean (default: false)
     */
    router.post('/execute', async (req, res) => {
        await migrationController.executeMigration(req, res);
    });

    /**
     * POST /api/migrations/validate
     * Validate migration results
     */
    router.post('/validate', async (req, res) => {
        await migrationController.validateMigration(req, res);
    });

    /**
     * POST /api/migrations/rollback
     * Rollback a specific migration
     * 
     * Body parameters:
     * - migrationName: string (required)
     */
    router.post('/rollback', async (req, res) => {
        await migrationController.rollbackMigration(req, res);
    });

    /**
     * GET /api/migrations/history
     * Get migration execution history
     */
    router.get('/history', async (req, res) => {
        await migrationController.getMigrationHistory(req, res);
    });

    /**
     * POST /api/migrations/backup
     * Create manual backup of affected tables
     * 
     * Body parameters:
     * - name: string (default: 'manual_backup')
     */
    router.post('/backup', async (req, res) => {
        await migrationController.createBackup(req, res);
    });

    /**
     * GET /api/migrations/health
     * Health check endpoint for migration system
     */
    router.get('/health', (req, res) => {
        res.json({
            success: true,
            message: 'Migration system is healthy',
            timestamp: new Date().toISOString(),
            version: '1.0.0'
        });
    });

    /**
     * GET /api/migrations/docs
     * API documentation endpoint
     */
    router.get('/docs', (req, res) => {
        res.json({
            success: true,
            documentation: {
                title: 'Database Migration API',
                version: '1.0.0',
                baseUrl: '/api/migrations',
                endpoints: [
                    {
                        method: 'GET',
                        path: '/status',
                        description: 'Get migration system status and overview'
                    },
                    {
                        method: 'POST',
                        path: '/analyze',
                        description: 'Analyze database schema for URL columns'
                    },
                    {
                        method: 'POST',
                        path: '/execute',
                        description: 'Execute URL migration',
                        parameters: {
                            migrationName: 'string (optional)',
                            dryRun: 'boolean (optional)',
                            force: 'boolean (optional)'
                        }
                    },
                    {
                        method: 'POST',
                        path: '/validate',
                        description: 'Validate migration results'
                    },
                    {
                        method: 'POST',
                        path: '/rollback',
                        description: 'Rollback a migration',
                        parameters: {
                            migrationName: 'string (required)'
                        }
                    },
                    {
                        method: 'GET',
                        path: '/history',
                        description: 'Get migration execution history'
                    },
                    {
                        method: 'POST',
                        path: '/backup',
                        description: 'Create manual backup',
                        parameters: {
                            name: 'string (optional)'
                        }
                    }
                ]
            },
            examples: {
                dryRun: {
                    url: 'POST /api/migrations/execute',
                    body: {
                        migrationName: '001_fix_localhost_urls',
                        dryRun: true
                    }
                },
                execute: {
                    url: 'POST /api/migrations/execute',
                    body: {
                        migrationName: '001_fix_localhost_urls',
                        dryRun: false
                    }
                },
                rollback: {
                    url: 'POST /api/migrations/rollback',
                    body: {
                        migrationName: '001_fix_localhost_urls'
                    }
                }
            }
        });
    });

    return router;
};

module.exports = initializeMigrationRoutes;