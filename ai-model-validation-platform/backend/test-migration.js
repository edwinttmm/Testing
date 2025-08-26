#!/usr/bin/env node

/**
 * Migration Test Suite
 * Comprehensive tests for the database migration system
 */

const path = require('path');
const fs = require('fs').promises;

// Test utilities
async function createTestDatabase() {
    const sqlite3 = require('sqlite3').verbose();
    const { open } = require('sqlite');
    
    const testDbPath = path.join(__dirname, 'test_migration.db');
    
    // Remove existing test database
    try {
        await fs.unlink(testDbPath);
    } catch (error) {
        // File doesn't exist, that's fine
    }
    
    const db = await open({
        filename: testDbPath,
        driver: sqlite3.Database
    });
    
    // Create test tables with localhost URLs
    await db.exec(`
        CREATE TABLE videos (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            thumbnail_url TEXT
        );
        
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            file_url TEXT,
            download_link TEXT
        );
        
        -- Insert test data with localhost URLs
        INSERT INTO videos (title, url, thumbnail_url) VALUES
        ('Test Video 1', 'http://localhost:8000/uploads/video1.mp4', 'http://localhost:8000/uploads/thumb1.jpg'),
        ('Test Video 2', 'http://127.0.0.1:8000/uploads/video2.mp4', 'http://127.0.0.1:8000/uploads/thumb2.jpg'),
        ('Test Video 3', 'http://155.138.239.131:8000/uploads/video3.mp4', 'http://155.138.239.131:8000/uploads/thumb3.jpg'),
        ('Test Video 4', 'http://localhost:8000/uploads/video4.mp4', NULL);
        
        INSERT INTO documents (name, file_url, download_link) VALUES
        ('Doc 1', 'http://localhost:8000/files/doc1.pdf', 'http://localhost:8000/download/doc1'),
        ('Doc 2', 'http://127.0.0.1:8000/files/doc2.pdf', 'http://127.0.0.1:8000/download/doc2'),
        ('Doc 3', 'http://155.138.239.131:8000/files/doc3.pdf', 'http://155.138.239.131:8000/download/doc3');
    `);
    
    return { db, dbPath: testDbPath };
}

const DatabaseMigrationService = require('./services/DatabaseMigrationService');
const DatabaseValidator = require('./utils/DatabaseValidator');

class MigrationTestSuite {
    constructor() {
        this.testResults = [];
        this.db = null;
        this.dbPath = null;
        this.migrationService = null;
        this.validator = null;
    }
    
    async initialize() {
        console.log('🧪 Initializing test database...');
        const { db, dbPath } = await createTestDatabase();
        this.db = db;
        this.dbPath = dbPath;
        
        this.migrationService = new DatabaseMigrationService(db);
        this.validator = new DatabaseValidator(db);
        
        await this.migrationService.initialize();
        console.log('✅ Test database initialized');
    }
    
    async cleanup() {
        if (this.db) {
            await this.db.close();
        }
        
        try {
            await fs.unlink(this.dbPath);
        } catch (error) {
            // File may not exist
        }
    }
    
    async runTest(testName, testFunction) {
        console.log(`\\n🧪 Running test: ${testName}`);
        
        try {
            const startTime = Date.now();
            const result = await testFunction();
            const duration = Date.now() - startTime;
            
            this.testResults.push({
                name: testName,
                status: 'PASSED',
                duration,
                result
            });
            
            console.log(`✅ ${testName} - PASSED (${duration}ms)`);
            return result;
        } catch (error) {
            this.testResults.push({
                name: testName,
                status: 'FAILED',
                error: error.message
            });
            
            console.log(`❌ ${testName} - FAILED: ${error.message}`);
            throw error;
        }
    }
    
    async testSchemaAnalysis() {
        return await this.runTest('Schema Analysis', async () => {
            const result = await this.migrationService.analyzeSchema();
            
            if (!result.success) {
                throw new Error(`Schema analysis failed: ${result.error}`);
            }
            
            // Should find URL columns in videos and documents tables
            const expectedColumns = ['videos.url', 'videos.thumbnail_url', 'documents.file_url', 'documents.download_link'];
            const foundColumns = result.urlColumns.map(col => `${col.table}.${col.column}`);
            
            for (const expected of expectedColumns) {
                if (!foundColumns.includes(expected)) {
                    throw new Error(`Expected column ${expected} not found`);
                }
            }
            
            return {
                totalUrlColumns: result.urlColumns.length,
                foundColumns
            };
        });
    }
    
    async testValidation() {
        return await this.runTest('Initial Validation', async () => {
            const result = await this.migrationService.validateMigration();
            
            if (!result.success) {
                throw new Error(`Validation failed: ${result.error}`);
            }
            
            // Should find localhost URLs that need migration
            if (result.validation.remainingLocalhost === 0) {
                throw new Error('Expected to find localhost URLs in test data');
            }
            
            return {
                localhostUrls: result.validation.remainingLocalhost,
                validUrls: result.validation.validUrls,
                isValid: result.isValid
            };
        });
    }
    
    async testDryRun() {
        return await this.runTest('Dry Run Migration', async () => {
            const result = await this.migrationService.executeMigration('001_fix_localhost_urls', true);
            
            if (!result.success) {
                throw new Error(`Dry run failed: ${result.error}`);
            }
            
            if (!result.dryRun) {
                throw new Error('Expected dry run flag to be true');
            }
            
            return {
                migrationName: result.migrationName,
                backupFile: result.backupFile,
                preview: result.preview ? result.preview.substring(0, 100) + '...' : null
            };
        });
    }
    
    async testMigrationExecution() {
        return await this.runTest('Migration Execution', async () => {
            const result = await this.migrationService.executeMigration('001_fix_localhost_urls', false);
            
            if (!result.success) {
                throw new Error(`Migration execution failed: ${result.error}`);
            }
            
            if (result.affectedRows === 0) {
                throw new Error('Expected some rows to be affected by migration');
            }
            
            return {
                migrationName: result.migrationName,
                executionTime: result.executionTime,
                affectedRows: result.affectedRows,
                backupFile: result.backupFile
            };
        });
    }
    
    async testPostMigrationValidation() {
        return await this.runTest('Post-Migration Validation', async () => {
            const result = await this.migrationService.validateMigration();
            
            if (!result.success) {
                throw new Error(`Post-migration validation failed: ${result.error}`);
            }
            
            // After migration, should have no localhost URLs
            if (result.validation.remainingLocalhost > 0) {
                throw new Error(`Still have ${result.validation.remainingLocalhost} localhost URLs after migration`);
            }
            
            if (!result.isValid) {
                throw new Error('Migration validation should pass after successful migration');
            }
            
            return {
                localhostUrls: result.validation.remainingLocalhost,
                validUrls: result.validation.validUrls,
                isValid: result.isValid
            };
        });
    }
    
    async testDataIntegrity() {
        return await this.runTest('Data Integrity Check', async () => {
            // Check that all URLs have been properly converted
            const videos = await this.db.all('SELECT * FROM videos');
            const documents = await this.db.all('SELECT * FROM documents');
            
            const allUrls = [];
            
            videos.forEach(video => {
                if (video.url) allUrls.push(video.url);
                if (video.thumbnail_url) allUrls.push(video.thumbnail_url);
            });
            
            documents.forEach(doc => {
                if (doc.file_url) allUrls.push(doc.file_url);
                if (doc.download_link) allUrls.push(doc.download_link);
            });
            
            const localhostUrls = allUrls.filter(url => 
                url.includes('localhost') || url.includes('127.0.0.1')
            );
            
            const productionUrls = allUrls.filter(url => 
                url.includes('155.138.239.131:8000')
            );
            
            if (localhostUrls.length > 0) {
                throw new Error(`Found ${localhostUrls.length} localhost URLs after migration: ${localhostUrls.join(', ')}`);
            }
            
            return {
                totalUrls: allUrls.length,
                productionUrls: productionUrls.length,
                localhostUrls: localhostUrls.length,
                sampleUrls: allUrls.slice(0, 3)
            };
        });
    }
    
    async testRollback() {
        return await this.runTest('Migration Rollback', async () => {
            // First, get migration history to find the migration to rollback
            const historyResult = await this.migrationService.getMigrationHistory();
            
            if (!historyResult.success || historyResult.history.length === 0) {
                throw new Error('No migration history found for rollback test');
            }
            
            const lastMigration = historyResult.history[0];
            const result = await this.migrationService.rollbackMigration(lastMigration.migration_name);
            
            if (!result.success) {
                throw new Error(`Rollback failed: ${result.error}`);
            }
            
            // After rollback, should have localhost URLs again
            const validationResult = await this.migrationService.validateMigration();
            
            if (validationResult.validation.remainingLocalhost === 0) {
                throw new Error('Expected localhost URLs after rollback');
            }
            
            return {
                rolledBackMigration: lastMigration.migration_name,
                backupFile: result.backupFile,
                localhostUrlsAfterRollback: validationResult.validation.remainingLocalhost
            };
        });
    }
    
    async runAllTests() {
        console.log('🚀 STARTING MIGRATION TEST SUITE');
        console.log('================================');
        
        try {
            await this.initialize();
            
            // Run tests in sequence
            await this.testSchemaAnalysis();
            await this.testValidation();
            await this.testDryRun();
            await this.testMigrationExecution();
            await this.testPostMigrationValidation();
            await this.testDataIntegrity();
            await this.testRollback();
            
            console.log('\\n✅ ALL TESTS COMPLETED SUCCESSFULLY');
            this.printSummary();
            
        } catch (error) {
            console.log('\\n❌ TEST SUITE FAILED');
            console.log(`Error: ${error.message}`);
            this.printSummary();
            throw error;
        } finally {
            await this.cleanup();
        }
    }
    
    printSummary() {
        console.log('\\n📊 TEST SUMMARY');
        console.log('===============');
        
        const passed = this.testResults.filter(r => r.status === 'PASSED').length;
        const failed = this.testResults.filter(r => r.status === 'FAILED').length;
        const totalDuration = this.testResults.reduce((sum, r) => sum + (r.duration || 0), 0);
        
        console.log(`Total Tests: ${this.testResults.length}`);
        console.log(`Passed: ${passed}`);
        console.log(`Failed: ${failed}`);
        console.log(`Total Duration: ${totalDuration}ms`);
        
        if (failed > 0) {
            console.log('\\n❌ Failed Tests:');
            this.testResults
                .filter(r => r.status === 'FAILED')
                .forEach(r => console.log(`  - ${r.name}: ${r.error}`));
        }
        
        console.log('\\n📋 Detailed Results:');
        this.testResults.forEach(r => {
            const status = r.status === 'PASSED' ? '✅' : '❌';
            const duration = r.duration ? ` (${r.duration}ms)` : '';
            console.log(`  ${status} ${r.name}${duration}`);
        });
    }
}

// Run tests if called directly
if (require.main === module) {
    const testSuite = new MigrationTestSuite();
    
    testSuite.runAllTests()
        .then(() => {
            console.log('\\n🎉 Migration test suite completed successfully!');
            process.exit(0);
        })
        .catch((error) => {
            console.error('\\n💥 Migration test suite failed:', error.message);
            process.exit(1);
        });
}

module.exports = MigrationTestSuite;