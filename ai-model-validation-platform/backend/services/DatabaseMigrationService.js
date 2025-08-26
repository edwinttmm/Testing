/**
 * Database Migration Service
 * Handles safe execution of database migrations with backup and rollback capabilities
 */

const fs = require('fs').promises;
const path = require('path');

class DatabaseMigrationService {
    constructor(database) {
        this.db = database;
        this.migrationsPath = path.join(__dirname, '../migrations');
        this.backupPath = path.join(__dirname, '../backups');
    }

    /**
     * Initialize migration system
     */
    async initialize() {
        try {
            // Ensure backup directory exists
            await fs.mkdir(this.backupPath, { recursive: true });
            
            // Create migration tracking table if not exists
            await this.db.run(`
                CREATE TABLE IF NOT EXISTS migration_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    migration_name VARCHAR(255) UNIQUE NOT NULL,
                    executed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status VARCHAR(50) DEFAULT 'pending',
                    backup_file VARCHAR(255),
                    rollback_available BOOLEAN DEFAULT FALSE,
                    execution_time_ms INTEGER,
                    affected_rows INTEGER DEFAULT 0
                )
            `);
            
            return { success: true, message: 'Migration system initialized' };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    /**
     * Analyze database schema to find URL columns
     */
    async analyzeSchema() {
        try {
            const tables = await this.db.all(`
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            `);

            const urlColumns = [];
            
            for (const table of tables) {
                const columns = await this.db.all(`PRAGMA table_info(${table.name})`);
                
                for (const column of columns) {
                    // Check if column might contain URLs
                    if (column.name.toLowerCase().includes('url') || 
                        column.name.toLowerCase().includes('link') ||
                        column.name.toLowerCase().includes('path')) {
                        
                        // Sample data to verify URL content
                        const sample = await this.db.get(`
                            SELECT ${column.name} 
                            FROM ${table.name} 
                            WHERE ${column.name} LIKE '%localhost%' 
                               OR ${column.name} LIKE '%127.0.0.1%'
                            LIMIT 1
                        `);
                        
                        if (sample) {
                            urlColumns.push({
                                table: table.name,
                                column: column.name,
                                type: column.type,
                                sample: sample[column.name]
                            });
                        }
                    }
                }
            }

            return { success: true, urlColumns };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    /**
     * Create backup before migration
     */
    async createBackup(migrationName) {
        try {
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            const backupFile = `backup_${migrationName}_${timestamp}.sql`;
            const backupPath = path.join(this.backupPath, backupFile);

            // Get all tables that might be affected
            const affectedTables = await this.getAffectedTables();
            let backupSql = `-- Backup created for migration: ${migrationName}\n`;
            backupSql += `-- Created at: ${new Date().toISOString()}\n\n`;

            for (const tableName of affectedTables) {
                const rows = await this.db.all(`SELECT * FROM ${tableName} WHERE url LIKE '%localhost%' OR url LIKE '%127.0.0.1%'`);
                
                if (rows.length > 0) {
                    backupSql += `-- Table: ${tableName}\n`;
                    backupSql += `CREATE TABLE IF NOT EXISTS ${tableName}_backup_${timestamp.slice(0, 10)} AS SELECT * FROM ${tableName} WHERE url LIKE '%localhost%' OR url LIKE '%127.0.0.1%';\n\n`;
                    
                    // Also create INSERT statements for manual restore
                    for (const row of rows) {
                        const columns = Object.keys(row).join(', ');
                        const values = Object.values(row).map(v => 
                            v === null ? 'NULL' : `'${v.toString().replace(/'/g, "''")}'`
                        ).join(', ');
                        backupSql += `INSERT INTO ${tableName} (${columns}) VALUES (${values});\n`;
                    }
                    backupSql += '\n';
                }
            }

            await fs.writeFile(backupPath, backupSql);
            return { success: true, backupFile, backupPath };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    /**
     * Get tables that might be affected by URL migration
     */
    async getAffectedTables() {
        const tables = await this.db.all(`
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        `);
        
        const affectedTables = [];
        for (const table of tables) {
            const hasUrls = await this.db.get(`
                SELECT COUNT(*) as count 
                FROM ${table.name} 
                WHERE url LIKE '%localhost%' OR url LIKE '%127.0.0.1%'
            `);
            
            if (hasUrls && hasUrls.count > 0) {
                affectedTables.push(table.name);
            }
        }
        
        return affectedTables;
    }

    /**
     * Execute migration with safety checks
     */
    async executeMigration(migrationName, dryRun = false) {
        const startTime = Date.now();
        
        try {
            // Check if migration already executed
            const existingMigration = await this.db.get(
                'SELECT * FROM migration_history WHERE migration_name = ?',
                [migrationName]
            );

            if (existingMigration && existingMigration.status === 'completed') {
                return { 
                    success: false, 
                    error: 'Migration already executed',
                    existing: existingMigration 
                };
            }

            // Create backup
            const backupResult = await this.createBackup(migrationName);
            if (!backupResult.success) {
                return { success: false, error: `Backup failed: ${backupResult.error}` };
            }

            // Read migration file
            const migrationPath = path.join(this.migrationsPath, `${migrationName}.sql`);
            const migrationSql = await fs.readFile(migrationPath, 'utf8');

            if (dryRun) {
                // Parse and validate migration without executing
                return {
                    success: true,
                    dryRun: true,
                    migrationName,
                    backupFile: backupResult.backupFile,
                    preview: migrationSql.substring(0, 500) + '...'
                };
            }

            // Record migration start
            await this.db.run(`
                INSERT OR REPLACE INTO migration_history 
                (migration_name, status, backup_file, rollback_available) 
                VALUES (?, 'running', ?, TRUE)
            `, [migrationName, backupResult.backupFile]);

            // Execute migration
            await this.db.exec(migrationSql);

            // Count affected rows
            const affectedRows = await this.countAffectedRows();
            const executionTime = Date.now() - startTime;

            // Update migration status
            await this.db.run(`
                UPDATE migration_history 
                SET status = 'completed', 
                    execution_time_ms = ?,
                    affected_rows = ?
                WHERE migration_name = ?
            `, [executionTime, affectedRows, migrationName]);

            return {
                success: true,
                migrationName,
                executionTime,
                affectedRows,
                backupFile: backupResult.backupFile
            };

        } catch (error) {
            // Mark migration as failed
            if (migrationName) {
                await this.db.run(`
                    UPDATE migration_history 
                    SET status = 'failed' 
                    WHERE migration_name = ?
                `, [migrationName]);
            }

            return { 
                success: false, 
                error: error.message,
                executionTime: Date.now() - startTime 
            };
        }
    }

    /**
     * Count rows affected by URL migration
     */
    async countAffectedRows() {
        try {
            const result = await this.db.get(`
                SELECT COUNT(*) as count 
                FROM migration_logs 
                WHERE migration_name LIKE '%fix_localhost_urls%' 
                AND status = 'completed'
            `);
            return result ? result.count : 0;
        } catch (error) {
            return 0;
        }
    }

    /**
     * Validate migration results
     */
    async validateMigration() {
        try {
            const results = {
                remainingLocalhost: 0,
                updatedUrls: 0,
                validUrls: 0,
                tables: []
            };

            // Check videos table
            const videosCheck = await this.db.all(`
                SELECT 
                    COUNT(*) as total_urls,
                    SUM(CASE WHEN url LIKE '%localhost%' OR url LIKE '%127.0.0.1%' THEN 1 ELSE 0 END) as localhost_count,
                    SUM(CASE WHEN url LIKE '%155.138.239.131%' THEN 1 ELSE 0 END) as production_count
                FROM videos
            `);

            if (videosCheck[0]) {
                results.remainingLocalhost += videosCheck[0].localhost_count;
                results.validUrls += videosCheck[0].production_count;
                results.tables.push({
                    name: 'videos',
                    totalUrls: videosCheck[0].total_urls,
                    localhostUrls: videosCheck[0].localhost_count,
                    productionUrls: videosCheck[0].production_count
                });
            }

            // Check migration logs
            const migrationStats = await this.db.all(`
                SELECT 
                    table_name,
                    column_name,
                    COUNT(*) as records_processed,
                    status
                FROM migration_logs 
                WHERE migration_name LIKE '%fix_localhost_urls%'
                GROUP BY table_name, column_name, status
            `);

            return {
                success: true,
                validation: results,
                migrationStats,
                isValid: results.remainingLocalhost === 0
            };

        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    /**
     * Rollback migration
     */
    async rollbackMigration(migrationName) {
        try {
            const migration = await this.db.get(
                'SELECT * FROM migration_history WHERE migration_name = ?',
                [migrationName]
            );

            if (!migration || !migration.rollback_available) {
                return { 
                    success: false, 
                    error: 'No rollback available for this migration' 
                };
            }

            const backupPath = path.join(this.backupPath, migration.backup_file);
            const backupSql = await fs.readFile(backupPath, 'utf8');

            // Execute rollback
            await this.db.exec(backupSql);

            // Update migration status
            await this.db.run(`
                UPDATE migration_history 
                SET status = 'rolled_back' 
                WHERE migration_name = ?
            `, [migrationName]);

            return {
                success: true,
                message: `Migration ${migrationName} rolled back successfully`,
                backupFile: migration.backup_file
            };

        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    /**
     * Get migration history
     */
    async getMigrationHistory() {
        try {
            const history = await this.db.all(`
                SELECT * FROM migration_history 
                ORDER BY executed_at DESC
            `);

            return { success: true, history };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }
}

module.exports = DatabaseMigrationService;