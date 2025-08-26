/**
 * Migration Controller
 * Handles HTTP endpoints for database migration operations
 */

const DatabaseMigrationService = require('../services/DatabaseMigrationService');

class MigrationController {
    constructor(database) {
        this.migrationService = new DatabaseMigrationService(database);
        
        // Initialize migration service
        this.migrationService.initialize().then(result => {
            console.log('Migration service initialized:', result);
        });
    }

    /**
     * GET /api/migrations/status
     * Get overall migration system status
     */
    async getStatus(req, res) {
        try {
            const history = await this.migrationService.getMigrationHistory();
            const schemaAnalysis = await this.migrationService.analyzeSchema();
            const validation = await this.migrationService.validateMigration();

            res.json({
                success: true,
                status: {
                    initialized: true,
                    lastMigration: history.success ? history.history[0] : null,
                    urlColumnsFound: schemaAnalysis.success ? schemaAnalysis.urlColumns.length : 0,
                    validationStatus: validation.isValid ? 'clean' : 'needs_migration',
                    remainingLocalhostUrls: validation.validation ? validation.validation.remainingLocalhost : 0
                },
                history: history.success ? history.history : [],
                schemaAnalysis: schemaAnalysis.success ? schemaAnalysis.urlColumns : []
            });
        } catch (error) {
            res.status(500).json({
                success: false,
                error: 'Failed to get migration status',
                details: error.message
            });
        }
    }

    /**
     * POST /api/migrations/analyze
     * Analyze database schema for URL columns
     */
    async analyzeSchema(req, res) {
        try {
            const result = await this.migrationService.analyzeSchema();
            
            if (result.success) {
                res.json({
                    success: true,
                    message: `Found ${result.urlColumns.length} URL columns`,
                    urlColumns: result.urlColumns,
                    recommendations: this.generateRecommendations(result.urlColumns)
                });
            } else {
                res.status(500).json({
                    success: false,
                    error: 'Schema analysis failed',
                    details: result.error
                });
            }
        } catch (error) {
            res.status(500).json({
                success: false,
                error: 'Schema analysis failed',
                details: error.message
            });
        }
    }

    /**
     * POST /api/migrations/execute
     * Execute URL migration
     */
    async executeMigration(req, res) {
        try {
            const { migrationName = '001_fix_localhost_urls', dryRun = false, force = false } = req.body;

            // Validate migration name
            if (!migrationName.match(/^[\w_-]+$/)) {
                return res.status(400).json({
                    success: false,
                    error: 'Invalid migration name format'
                });
            }

            // Check if migration is safe to run
            if (!force && !dryRun) {
                const validation = await this.migrationService.validateMigration();
                if (validation.validation && validation.validation.remainingLocalhost === 0) {
                    return res.json({
                        success: true,
                        message: 'No migration needed - all URLs are already updated',
                        validation: validation.validation
                    });
                }
            }

            const result = await this.migrationService.executeMigration(migrationName, dryRun);

            if (result.success) {
                const response = {
                    success: true,
                    migrationName,
                    dryRun,
                    executionTime: result.executionTime,
                    affectedRows: result.affectedRows,
                    backupFile: result.backupFile
                };

                if (dryRun) {
                    response.message = 'Dry run completed successfully';
                    response.preview = result.preview;
                } else {
                    response.message = 'Migration executed successfully';
                    
                    // Run validation after migration
                    const validation = await this.migrationService.validateMigration();
                    response.validation = validation;
                }

                res.json(response);
            } else {
                res.status(400).json({
                    success: false,
                    error: 'Migration failed',
                    details: result.error,
                    executionTime: result.executionTime
                });
            }
        } catch (error) {
            res.status(500).json({
                success: false,
                error: 'Migration execution failed',
                details: error.message
            });
        }
    }

    /**
     * POST /api/migrations/validate
     * Validate migration results
     */
    async validateMigration(req, res) {
        try {
            const result = await this.migrationService.validateMigration();

            if (result.success) {
                res.json({
                    success: true,
                    validation: result.validation,
                    migrationStats: result.migrationStats,
                    isValid: result.isValid,
                    message: result.isValid ? 
                        'All URLs successfully migrated' : 
                        `${result.validation.remainingLocalhost} localhost URLs still need migration`,
                    recommendations: this.generateValidationRecommendations(result)
                });
            } else {
                res.status(500).json({
                    success: false,
                    error: 'Validation failed',
                    details: result.error
                });
            }
        } catch (error) {
            res.status(500).json({
                success: false,
                error: 'Validation failed',
                details: error.message
            });
        }
    }

    /**
     * POST /api/migrations/rollback
     * Rollback a migration
     */
    async rollbackMigration(req, res) {
        try {
            const { migrationName } = req.body;

            if (!migrationName) {
                return res.status(400).json({
                    success: false,
                    error: 'Migration name is required'
                });
            }

            const result = await this.migrationService.rollbackMigration(migrationName);

            if (result.success) {
                res.json({
                    success: true,
                    message: result.message,
                    backupFile: result.backupFile
                });
            } else {
                res.status(400).json({
                    success: false,
                    error: result.error
                });
            }
        } catch (error) {
            res.status(500).json({
                success: false,
                error: 'Rollback failed',
                details: error.message
            });
        }
    }

    /**
     * GET /api/migrations/history
     * Get migration history
     */
    async getMigrationHistory(req, res) {
        try {
            const result = await this.migrationService.getMigrationHistory();

            if (result.success) {
                res.json({
                    success: true,
                    history: result.history,
                    summary: this.generateHistorySummary(result.history)
                });
            } else {
                res.status(500).json({
                    success: false,
                    error: 'Failed to get migration history',
                    details: result.error
                });
            }
        } catch (error) {
            res.status(500).json({
                success: false,
                error: 'Failed to get migration history',
                details: error.message
            });
        }
    }

    /**
     * POST /api/migrations/backup
     * Create manual backup
     */
    async createBackup(req, res) {
        try {
            const { name = 'manual_backup' } = req.body;
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            const backupName = `${name}_${timestamp}`;

            const result = await this.migrationService.createBackup(backupName);

            if (result.success) {
                res.json({
                    success: true,
                    message: 'Backup created successfully',
                    backupFile: result.backupFile,
                    backupPath: result.backupPath
                });
            } else {
                res.status(500).json({
                    success: false,
                    error: 'Backup creation failed',
                    details: result.error
                });
            }
        } catch (error) {
            res.status(500).json({
                success: false,
                error: 'Backup creation failed',
                details: error.message
            });
        }
    }

    /**
     * Generate recommendations based on schema analysis
     */
    generateRecommendations(urlColumns) {
        const recommendations = [];

        if (urlColumns.length === 0) {
            recommendations.push('No URL columns found with localhost references');
            return recommendations;
        }

        recommendations.push(`Found ${urlColumns.length} columns with localhost URLs`);
        
        const tables = [...new Set(urlColumns.map(col => col.table))];
        recommendations.push(`Affected tables: ${tables.join(', ')}`);

        if (urlColumns.some(col => col.column.includes('thumbnail'))) {
            recommendations.push('Thumbnail URLs detected - ensure image files are accessible at new location');
        }

        recommendations.push('Recommended: Create backup before running migration');
        recommendations.push('Recommended: Run dry-run first to preview changes');

        return recommendations;
    }

    /**
     * Generate validation recommendations
     */
    generateValidationRecommendations(validationResult) {
        const recommendations = [];
        const validation = validationResult.validation;

        if (validation.remainingLocalhost === 0) {
            recommendations.push('✅ All localhost URLs successfully migrated');
            recommendations.push('✅ No further action required');
        } else {
            recommendations.push(`⚠️  ${validation.remainingLocalhost} localhost URLs still exist`);
            recommendations.push('Recommended: Review migration logs and re-run if necessary');
        }

        if (validation.validUrls > 0) {
            recommendations.push(`✅ ${validation.validUrls} URLs correctly pointing to production server`);
        }

        return recommendations;
    }

    /**
     * Generate history summary
     */
    generateHistorySummary(history) {
        if (!history || history.length === 0) {
            return { totalMigrations: 0, lastStatus: 'none' };
        }

        const summary = {
            totalMigrations: history.length,
            completed: history.filter(h => h.status === 'completed').length,
            failed: history.filter(h => h.status === 'failed').length,
            rolledBack: history.filter(h => h.status === 'rolled_back').length,
            lastStatus: history[0].status,
            lastExecuted: history[0].executed_at,
            totalAffectedRows: history.reduce((sum, h) => sum + (h.affected_rows || 0), 0)
        };

        return summary;
    }
}

module.exports = MigrationController;