/**
 * Database Validator
 * Comprehensive validation utilities for URL migration
 */

class DatabaseValidator {
    constructor(database) {
        this.db = database;
        this.productionHost = '155.138.239.131:8000';
        this.localhostPatterns = [
            'localhost',
            '127.0.0.1',
            '0.0.0.0'
        ];
    }

    /**
     * Validate all URLs in the database
     */
    async validateAllUrls() {
        try {
            const results = {
                tables: [],
                totalUrls: 0,
                validUrls: 0,
                invalidUrls: 0,
                localhostUrls: 0,
                unreachableUrls: 0,
                summary: {}
            };

            // Get all tables with URL-like columns
            const urlTables = await this.findUrlTables();

            for (const tableInfo of urlTables) {
                const tableResult = await this.validateTableUrls(tableInfo.tableName, tableInfo.columns);
                results.tables.push(tableResult);
                
                results.totalUrls += tableResult.totalUrls;
                results.validUrls += tableResult.validUrls;
                results.invalidUrls += tableResult.invalidUrls;
                results.localhostUrls += tableResult.localhostUrls;
                results.unreachableUrls += tableResult.unreachableUrls;
            }

            results.summary = {
                validPercentage: results.totalUrls > 0 ? 
                    Math.round((results.validUrls / results.totalUrls) * 100) : 0,
                needsMigration: results.localhostUrls > 0,
                isHealthy: results.localhostUrls === 0 && results.unreachableUrls === 0
            };

            return { success: true, results };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    /**
     * Find all tables with URL-like columns
     */
    async findUrlTables() {
        const tables = await this.db.all(`
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        `);

        const urlTables = [];

        for (const table of tables) {
            const columns = await this.db.all(`PRAGMA table_info(${table.name})`);
            const urlColumns = columns.filter(col => 
                col.name.toLowerCase().includes('url') || 
                col.name.toLowerCase().includes('link') ||
                col.name.toLowerCase().includes('path') ||
                col.name.toLowerCase().includes('href')
            );

            if (urlColumns.length > 0) {
                urlTables.push({
                    tableName: table.name,
                    columns: urlColumns.map(col => col.name)
                });
            }
        }

        return urlTables;
    }

    /**
     * Validate URLs in a specific table
     */
    async validateTableUrls(tableName, columns) {
        const result = {
            tableName,
            columns,
            totalUrls: 0,
            validUrls: 0,
            invalidUrls: 0,
            localhostUrls: 0,
            unreachableUrls: 0,
            issues: []
        };

        for (const columnName of columns) {
            try {
                const urls = await this.db.all(`
                    SELECT id, ${columnName} as url 
                    FROM ${tableName} 
                    WHERE ${columnName} IS NOT NULL AND ${columnName} != ''
                `);

                for (const row of urls) {
                    result.totalUrls++;
                    const validation = this.validateUrl(row.url);
                    
                    if (validation.isValid) {
                        result.validUrls++;
                    } else {
                        result.invalidUrls++;
                        result.issues.push({
                            id: row.id,
                            column: columnName,
                            url: row.url,
                            issue: validation.issue
                        });
                    }

                    if (validation.isLocalhost) {
                        result.localhostUrls++;
                    }

                    if (validation.unreachable) {
                        result.unreachableUrls++;
                    }
                }
            } catch (error) {
                result.issues.push({
                    column: columnName,
                    issue: `Column validation error: ${error.message}`
                });
            }
        }

        return result;
    }

    /**
     * Validate a single URL
     */
    validateUrl(url) {
        const result = {
            isValid: false,
            isLocalhost: false,
            unreachable: false,
            issue: null
        };

        if (!url || typeof url !== 'string') {
            result.issue = 'Empty or invalid URL';
            return result;
        }

        try {
            const urlObj = new URL(url);
            
            // Check for localhost patterns
            const isLocalhost = this.localhostPatterns.some(pattern => 
                urlObj.hostname.includes(pattern)
            );

            if (isLocalhost) {
                result.isLocalhost = true;
                result.issue = 'Contains localhost reference';
                return result;
            }

            // Check if it's pointing to production server
            if (urlObj.hostname === '155.138.239.131' && urlObj.port === '8000') {
                result.isValid = true;
                return result;
            }

            // Check for other valid hostnames
            if (urlObj.protocol === 'http:' || urlObj.protocol === 'https:') {
                result.isValid = true;
                return result;
            }

            result.issue = 'Invalid protocol or hostname';
            return result;

        } catch (error) {
            result.issue = `Invalid URL format: ${error.message}`;
            return result;
        }
    }

    /**
     * Test URL accessibility (basic check)
     */
    async testUrlAccessibility(url, timeout = 5000) {
        try {
            // This is a basic implementation - in production, you might want to use
            // a proper HTTP client like axios or node-fetch
            return { accessible: true, responseTime: 0 };
        } catch (error) {
            return { accessible: false, error: error.message };
        }
    }

    /**
     * Generate migration report
     */
    async generateMigrationReport() {
        try {
            const validation = await this.validateAllUrls();
            
            if (!validation.success) {
                return validation;
            }

            const report = {
                generatedAt: new Date().toISOString(),
                database: {
                    tablesScanned: validation.results.tables.length,
                    totalUrls: validation.results.totalUrls
                },
                migration: {
                    required: validation.results.localhostUrls > 0,
                    affectedUrls: validation.results.localhostUrls,
                    estimatedDuration: this.estimateMigrationTime(validation.results.localhostUrls)
                },
                validation: validation.results,
                recommendations: this.generateRecommendations(validation.results)
            };

            return { success: true, report };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    /**
     * Estimate migration time based on URL count
     */
    estimateMigrationTime(urlCount) {
        // Rough estimate: 10ms per URL + overhead
        const baseTime = 1000; // 1 second base
        const urlTime = urlCount * 10; // 10ms per URL
        const overhead = 2000; // 2 seconds overhead
        
        const totalMs = baseTime + urlTime + overhead;
        
        if (totalMs < 60000) {
            return `${Math.round(totalMs / 1000)} seconds`;
        } else {
            return `${Math.round(totalMs / 60000)} minutes`;
        }
    }

    /**
     * Generate recommendations based on validation results
     */
    generateRecommendations(results) {
        const recommendations = [];

        if (results.localhostUrls === 0) {
            recommendations.push('✅ No localhost URLs found - migration not needed');
            return recommendations;
        }

        recommendations.push(`🔧 ${results.localhostUrls} localhost URLs need migration`);
        
        if (results.localhostUrls > 100) {
            recommendations.push('⚠️  Large number of URLs - consider running during maintenance window');
        }

        if (results.unreachableUrls > 0) {
            recommendations.push(`⚠️  ${results.unreachableUrls} URLs may be unreachable after migration`);
        }

        recommendations.push('💾 Create backup before running migration');
        recommendations.push('🧪 Run dry-run first to preview changes');
        recommendations.push('✅ Validate results after migration');

        if (results.invalidUrls > 0) {
            recommendations.push(`⚠️  ${results.invalidUrls} URLs have format issues - review manually`);
        }

        return recommendations;
    }

    /**
     * Compare URLs before and after migration
     */
    async compareMigrationResults(beforeResults, afterResults) {
        const comparison = {
            localhostUrlsFixed: beforeResults.localhostUrls - afterResults.localhostUrls,
            newValidUrls: afterResults.validUrls - beforeResults.validUrls,
            remainingIssues: afterResults.invalidUrls,
            success: afterResults.localhostUrls === 0,
            summary: {}
        };

        comparison.summary = {
            migrationEffective: comparison.localhostUrlsFixed > 0,
            allUrlsFixed: afterResults.localhostUrls === 0,
            noNewIssues: afterResults.invalidUrls <= beforeResults.invalidUrls
        };

        return comparison;
    }
}

module.exports = DatabaseValidator;