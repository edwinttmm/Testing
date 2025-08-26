#!/usr/bin/env node

/**
 * Migration CLI Tool
 * Command-line interface for database URL migration
 */

const path = require('path');
const fs = require('fs').promises;

// Database connection (adjust path as needed)
const getDatabaseConnection = async () => {
    const sqlite3 = require('sqlite3').verbose();
    const { open } = require('sqlite');
    
    // Adjust database path based on your project structure
    const dbPath = process.env.DATABASE_PATH || path.join(__dirname, '../database/videos.db');
    
    return await open({
        filename: dbPath,
        driver: sqlite3.Database
    });
};

const DatabaseMigrationService = require('../services/DatabaseMigrationService');
const DatabaseValidator = require('../utils/DatabaseValidator');

class MigrationCLI {
    constructor() {
        this.commands = {
            'status': this.getStatus.bind(this),
            'analyze': this.analyzeSchema.bind(this),
            'dry-run': this.dryRun.bind(this),
            'execute': this.executeMigration.bind(this),
            'validate': this.validateMigration.bind(this),
            'rollback': this.rollbackMigration.bind(this),
            'history': this.getHistory.bind(this),
            'backup': this.createBackup.bind(this),
            'help': this.showHelp.bind(this)
        };
    }

    async run() {
        const args = process.argv.slice(2);
        const command = args[0] || 'help';
        const params = args.slice(1);

        if (!this.commands[command]) {
            console.error(`Unknown command: ${command}`);
            this.showHelp();
            process.exit(1);
        }

        try {
            const db = await getDatabaseConnection();
            this.migrationService = new DatabaseMigrationService(db);
            this.validator = new DatabaseValidator(db);
            
            await this.migrationService.initialize();
            await this.commands[command](params);
            
            await db.close();
        } catch (error) {
            console.error('Error:', error.message);
            process.exit(1);
        }
    }

    async getStatus(params) {
        console.log('🔍 Checking migration status...\n');

        const history = await this.migrationService.getMigrationHistory();
        const validation = await this.migrationService.validateMigration();
        const schema = await this.migrationService.analyzeSchema();

        console.log('📊 MIGRATION STATUS');
        console.log('==================');
        console.log(`Last Migration: ${history.success && history.history[0] ? history.history[0].migration_name : 'None'}`);
        console.log(`Status: ${history.success && history.history[0] ? history.history[0].status : 'Not initialized'}`);
        console.log(`URL Columns Found: ${schema.success ? schema.urlColumns.length : 'Unknown'}`);
        console.log(`Localhost URLs: ${validation.validation ? validation.validation.remainingLocalhost : 'Unknown'}`);
        console.log(`Production URLs: ${validation.validation ? validation.validation.validUrls : 'Unknown'}`);

        if (schema.success && schema.urlColumns.length > 0) {
            console.log('\n📋 URL COLUMNS DETECTED');
            console.log('=======================');
            schema.urlColumns.forEach(col => {
                console.log(`${col.table}.${col.column}: ${col.sample ? col.sample.substring(0, 50) + '...' : 'No sample'}`);
            });
        }

        const needsMigration = validation.validation && validation.validation.remainingLocalhost > 0;
        console.log(`\n${needsMigration ? '⚠️  MIGRATION REQUIRED' : '✅ NO MIGRATION NEEDED'}`);
    }

    async analyzeSchema(params) {
        console.log('🔍 Analyzing database schema for URL columns...\n');

        const result = await this.migrationService.analyzeSchema();
        
        if (result.success) {
            console.log('📊 SCHEMA ANALYSIS RESULTS');
            console.log('==========================');
            console.log(`URL Columns Found: ${result.urlColumns.length}\n`);

            if (result.urlColumns.length > 0) {
                result.urlColumns.forEach((col, index) => {
                    console.log(`${index + 1}. Table: ${col.table}`);
                    console.log(`   Column: ${col.column}`);
                    console.log(`   Type: ${col.type}`);
                    console.log(`   Sample: ${col.sample ? col.sample : 'No localhost URLs found'}`);
                    console.log('');
                });

                const tables = [...new Set(result.urlColumns.map(col => col.table))];
                console.log(`📋 Affected Tables: ${tables.join(', ')}`);
            } else {
                console.log('✅ No localhost URL references found in database');
            }
        } else {
            console.error('❌ Schema analysis failed:', result.error);
        }
    }

    async dryRun(params) {
        const migrationName = params[0] || '001_fix_localhost_urls';
        
        console.log(`🧪 Running dry-run for migration: ${migrationName}\n`);

        const result = await this.migrationService.executeMigration(migrationName, true);
        
        if (result.success) {
            console.log('✅ DRY RUN SUCCESSFUL');
            console.log('===================');
            console.log(`Migration: ${result.migrationName}`);
            console.log(`Backup File: ${result.backupFile}`);
            console.log('\n📋 Migration Preview:');
            console.log('---------------------');
            console.log(result.preview);
            console.log('\n💡 Run with "execute" command to apply changes');
        } else {
            console.error('❌ DRY RUN FAILED:', result.error);
        }
    }

    async executeMigration(params) {
        const migrationName = params[0] || '001_fix_localhost_urls';
        const force = params.includes('--force');
        
        console.log(`🚀 Executing migration: ${migrationName}\n`);

        if (!force) {
            console.log('⚠️  This will modify your database. Make sure you have a backup!');
            console.log('   Use --force flag to skip this warning\n');
            
            // In a real CLI, you'd want to prompt for confirmation
            const readline = require('readline');
            const rl = readline.createInterface({
                input: process.stdin,
                output: process.stdout
            });

            const answer = await new Promise(resolve => {
                rl.question('Continue? (y/N): ', resolve);
            });
            
            rl.close();
            
            if (answer.toLowerCase() !== 'y' && answer.toLowerCase() !== 'yes') {
                console.log('❌ Migration cancelled');
                return;
            }
        }

        const result = await this.migrationService.executeMigration(migrationName, false);
        
        if (result.success) {
            console.log('✅ MIGRATION COMPLETED');
            console.log('=====================');
            console.log(`Migration: ${result.migrationName}`);
            console.log(`Execution Time: ${result.executionTime}ms`);
            console.log(`Affected Rows: ${result.affectedRows}`);
            console.log(`Backup File: ${result.backupFile}`);
            
            // Run validation
            console.log('\n🔍 Validating results...');
            const validation = await this.migrationService.validateMigration();
            
            if (validation.success && validation.isValid) {
                console.log('✅ Validation passed - all URLs migrated successfully');
            } else {
                console.log('⚠️  Validation warnings detected - check results manually');
            }
        } else {
            console.error('❌ MIGRATION FAILED:', result.error);
            console.error(`Execution Time: ${result.executionTime}ms`);
        }
    }

    async validateMigration(params) {
        console.log('🔍 Validating migration results...\n');

        const result = await this.migrationService.validateMigration();
        
        if (result.success) {
            console.log('📊 VALIDATION RESULTS');
            console.log('====================');
            console.log(`Total URLs: ${result.validation.validUrls + result.validation.remainingLocalhost}`);
            console.log(`Production URLs: ${result.validation.validUrls}`);
            console.log(`Localhost URLs: ${result.validation.remainingLocalhost}`);
            console.log(`Status: ${result.isValid ? '✅ PASSED' : '⚠️  NEEDS ATTENTION'}`);

            if (result.validation.tables.length > 0) {
                console.log('\n📋 TABLE BREAKDOWN');
                console.log('==================');
                result.validation.tables.forEach(table => {
                    console.log(`${table.name}:`);
                    console.log(`  Total URLs: ${table.totalUrls}`);
                    console.log(`  Localhost URLs: ${table.localhostUrls}`);
                    console.log(`  Production URLs: ${table.productionUrls}`);
                });
            }

            if (result.migrationStats && result.migrationStats.length > 0) {
                console.log('\n📈 MIGRATION STATISTICS');
                console.log('=======================');
                result.migrationStats.forEach(stat => {
                    console.log(`${stat.table_name}.${stat.column_name}: ${stat.records_processed} records (${stat.status})`);
                });
            }
        } else {
            console.error('❌ Validation failed:', result.error);
        }
    }

    async rollbackMigration(params) {
        const migrationName = params[0];
        
        if (!migrationName) {
            console.error('❌ Migration name required for rollback');
            console.log('Usage: npm run migrate rollback <migration-name>');
            return;
        }

        console.log(`🔄 Rolling back migration: ${migrationName}\n`);

        const result = await this.migrationService.rollbackMigration(migrationName);
        
        if (result.success) {
            console.log('✅ ROLLBACK COMPLETED');
            console.log('====================');
            console.log(result.message);
            console.log(`Backup File: ${result.backupFile}`);
        } else {
            console.error('❌ ROLLBACK FAILED:', result.error);
        }
    }

    async getHistory(params) {
        console.log('📚 Migration History\n');

        const result = await this.migrationService.getMigrationHistory();
        
        if (result.success && result.history.length > 0) {
            console.log('📊 MIGRATION HISTORY');
            console.log('===================');
            
            result.history.forEach((migration, index) => {
                console.log(`${index + 1}. ${migration.migration_name}`);
                console.log(`   Status: ${migration.status}`);
                console.log(`   Executed: ${migration.executed_at}`);
                console.log(`   Duration: ${migration.execution_time_ms || 'Unknown'}ms`);
                console.log(`   Affected Rows: ${migration.affected_rows || 0}`);
                console.log(`   Rollback: ${migration.rollback_available ? 'Available' : 'Not Available'}`);
                console.log('');
            });
        } else {
            console.log('📝 No migration history found');
        }
    }

    async createBackup(params) {
        const backupName = params[0] || 'manual_backup';
        
        console.log(`💾 Creating backup: ${backupName}\n`);

        const result = await this.migrationService.createBackup(backupName);
        
        if (result.success) {
            console.log('✅ BACKUP CREATED');
            console.log('================');
            console.log(`Backup File: ${result.backupFile}`);
            console.log(`Location: ${result.backupPath}`);
        } else {
            console.error('❌ BACKUP FAILED:', result.error);
        }
    }

    showHelp() {
        console.log('🛠️  Database URL Migration CLI');
        console.log('===============================\n');
        
        console.log('USAGE:');
        console.log('  npm run migrate <command> [options]\n');
        
        console.log('COMMANDS:');
        console.log('  status      - Show migration status and overview');
        console.log('  analyze     - Analyze database schema for URL columns');
        console.log('  dry-run     - Preview migration changes without applying');
        console.log('  execute     - Execute migration (use --force to skip confirmation)');
        console.log('  validate    - Validate migration results');
        console.log('  rollback    - Rollback a specific migration');
        console.log('  history     - Show migration execution history');
        console.log('  backup      - Create manual backup');
        console.log('  help        - Show this help message\n');
        
        console.log('EXAMPLES:');
        console.log('  npm run migrate status');
        console.log('  npm run migrate dry-run');
        console.log('  npm run migrate execute --force');
        console.log('  npm run migrate rollback 001_fix_localhost_urls');
        console.log('  npm run migrate backup my_backup_name\n');
        
        console.log('ENVIRONMENT VARIABLES:');
        console.log('  DATABASE_PATH    - Path to SQLite database file');
        console.log('  MIGRATION_API_KEY - API key for web endpoints (optional)\n');
    }
}

// Run CLI if called directly
if (require.main === module) {
    const cli = new MigrationCLI();
    cli.run().catch(error => {
        console.error('Fatal error:', error.message);
        process.exit(1);
    });
}

module.exports = MigrationCLI;