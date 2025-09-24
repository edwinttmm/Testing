#!/usr/bin/env node
/**
 * Frontend Ground Truth Validation
 * 
 * Tests that the React components properly display ground truth data
 * and validates the fix: "Ground Truth Events: 24" instead of "0"
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

class FrontendGroundTruthValidator {
    constructor(baseUrl = 'http://localhost:3000') {
        this.baseUrl = baseUrl;
        this.testSessionId = 'b8a345a5-582a-4a55-a409-c7a8a06408f9';
        this.results = {
            timestamp: new Date().toISOString(),
            tests: {},
            summary: {}
        };
    }

    logTest(testName, passed, details = {}) {
        this.results.tests[testName] = {
            passed,
            timestamp: new Date().toISOString(),
            details
        };
        
        const status = passed ? '✅ PASS' : '❌ FAIL';
        console.log(`[Frontend] ${testName}: ${status}`);
        if (!passed && details.error) {
            console.log(`  Error: ${details.error}`);
        }
        return passed;
    }

    async testHILResultsPageAccessible(page) {
        try {
            const url = `${this.baseUrl}/hil-results/${this.testSessionId}`;
            console.log(`🔍 Testing HIL Results page: ${url}`);
            
            const response = await page.goto(url, { waitUntil: 'networkidle' });
            
            const accessible = response.status() === 200;
            return this.logTest('hil_results_page_accessible', accessible, {
                url,
                status: response.status()
            });
        } catch (error) {
            return this.logTest('hil_results_page_accessible', false, {
                error: error.message
            });
        }
    }

    async testGroundTruthDisplayNotZero(page) {
        try {
            // Wait for the page to load
            await page.waitForLoadState('networkidle');
            
            // Look for "Ground Truth Events" text
            const gtEventSelectors = [
                'text="Ground Truth Events:"',
                '[data-testid="ground-truth-events"]',
                'text=/Ground Truth Events.*\\d+/',
                'text=/Ground.*Truth.*Events/',
                // More flexible selectors
                'text=/ground.*truth/i',
                'text=/GT.*Events/i'
            ];
            
            let foundGTDisplay = false;
            let gtEventCount = null;
            let selectorUsed = null;
            
            for (const selector of gtEventSelectors) {
                try {
                    const element = await page.locator(selector).first();
                    if (await element.isVisible({ timeout: 5000 })) {
                        foundGTDisplay = true;
                        selectorUsed = selector;
                        const text = await element.textContent();
                        
                        // Extract number from text like "Ground Truth Events: 24"
                        const match = text.match(/(\d+)/);
                        if (match) {
                            gtEventCount = parseInt(match[1]);
                        }
                        break;
                    }
                } catch (e) {
                    // Continue to next selector
                }
            }
            
            // Critical validation: Should show 24, not 0
            const isNotZero = gtEventCount !== null && gtEventCount !== 0;
            const isExpectedValue = gtEventCount === 24;
            
            return this.logTest('ground_truth_events_not_zero', isNotZero && foundGTDisplay, {
                found_gt_display: foundGTDisplay,
                selector_used: selectorUsed,
                gt_event_count: gtEventCount,
                is_not_zero: isNotZero,
                is_expected_24: isExpectedValue,
                critical_fix_validated: isExpectedValue
            });
            
        } catch (error) {
            return this.logTest('ground_truth_events_not_zero', false, {
                error: error.message
            });
        }
    }

    async testEnhancedTimingToggle(page) {
        try {
            // Look for Enhanced Timing toggle/switch
            const toggleSelectors = [
                'text="Enhanced Timing"',
                '[data-testid="enhanced-timing-toggle"]',
                'input[type="checkbox"] + label:has-text("Enhanced Timing")',
                '.MuiSwitch-root:near(:text("Enhanced Timing"))'
            ];
            
            let foundToggle = false;
            let toggleEnabled = false;
            
            for (const selector of toggleSelectors) {
                try {
                    const element = await page.locator(selector).first();
                    if (await element.isVisible({ timeout: 3000 })) {
                        foundToggle = true;
                        
                        // Check if it's a switch/checkbox
                        const inputElement = await element.locator('input[type="checkbox"]').first();
                        if (await inputElement.isVisible()) {
                            toggleEnabled = await inputElement.isChecked();
                        }
                        break;
                    }
                } catch (e) {
                    // Continue
                }
            }
            
            return this.logTest('enhanced_timing_toggle_present', foundToggle, {
                found_toggle: foundToggle,
                toggle_enabled: toggleEnabled
            });
            
        } catch (error) {
            return this.logTest('enhanced_timing_toggle_present', false, {
                error: error.message
            });
        }
    }

    async testTimingSynchronizationDisplay(page) {
        try {
            // Look for timing synchronization/correction information
            const timingSelectors = [
                'text=/Timing.*Synchronization/i',
                'text=/Timing.*Correction/i',
                'text=/Video.*Startup.*Delay/i',
                'text=/Real.*Latency/i',
                'text=/Corrected.*Results/i'
            ];
            
            let foundTimingInfo = false;
            let timingDetails = [];
            
            for (const selector of timingSelectors) {
                try {
                    const elements = await page.locator(selector);
                    const count = await elements.count();
                    
                    if (count > 0) {
                        foundTimingInfo = true;
                        for (let i = 0; i < Math.min(count, 3); i++) {
                            const text = await elements.nth(i).textContent();
                            timingDetails.push(text.trim());
                        }
                    }
                } catch (e) {
                    // Continue
                }
            }
            
            return this.logTest('timing_synchronization_display', foundTimingInfo, {
                found_timing_info: foundTimingInfo,
                timing_details: timingDetails
            });
            
        } catch (error) {
            return this.logTest('timing_synchronization_display', false, {
                error: error.message
            });
        }
    }

    async testGroundTruthComparisonCard(page) {
        try {
            // Look for Ground Truth Comparison card/section
            const comparisonSelectors = [
                'text="Ground Truth Comparison"',
                '[data-testid="ground-truth-comparison"]',
                'text=/Ground.*Truth.*Comparison/i',
                'text=/True.*Positives/i',
                'text=/False.*Positives/i',
                'text=/Precision/i',
                'text=/Recall/i'
            ];
            
            let foundComparison = false;
            let hasMetrics = false;
            let metricsFound = [];
            
            for (const selector of comparisonSelectors) {
                try {
                    const element = await page.locator(selector).first();
                    if (await element.isVisible({ timeout: 3000 })) {
                        foundComparison = true;
                        const text = await element.textContent();
                        metricsFound.push(text.trim());
                        
                        if (text.includes('Precision') || text.includes('Recall') || text.includes('F1')) {
                            hasMetrics = true;
                        }
                    }
                } catch (e) {
                    // Continue
                }
            }
            
            return this.logTest('ground_truth_comparison_card', foundComparison, {
                found_comparison: foundComparison,
                has_metrics: hasMetrics,
                metrics_found: metricsFound
            });
            
        } catch (error) {
            return this.logTest('ground_truth_comparison_card', false, {
                error: error.message
            });
        }
    }

    async testNoErrorMessages(page) {
        try {
            // Check for error messages that indicate issues
            const errorMessages = await page.locator('text=/error|fail|problem|issue/i').all();
            const errorTexts = [];
            
            for (const error of errorMessages.slice(0, 5)) { // Limit to first 5
                try {
                    const text = await error.textContent();
                    // Filter out common false positives
                    if (!text.toLowerCase().includes('error_main') && 
                        !text.toLowerCase().includes('erroricon') &&
                        !text.toLowerCase().includes('failure_type')) {
                        errorTexts.push(text.trim());
                    }
                } catch (e) {
                    // Skip this error element
                }
            }
            
            const hasErrors = errorTexts.length > 0;
            
            return this.logTest('no_error_messages', !hasErrors, {
                has_errors: hasErrors,
                error_texts: errorTexts
            });
            
        } catch (error) {
            return this.logTest('no_error_messages', false, {
                error: error.message
            });
        }
    }

    async testDataLoading(page) {
        try {
            // Wait for data to load - look for loading indicators to disappear
            await page.waitForLoadState('networkidle');
            
            // Check for loading indicators
            const loadingSelectors = [
                'text="Loading"',
                'text="Loading HIL Test Results"',
                '.MuiCircularProgress-root',
                '[data-testid="loading"]'
            ];
            
            let stillLoading = false;
            
            for (const selector of loadingSelectors) {
                try {
                    const element = await page.locator(selector).first();
                    if (await element.isVisible({ timeout: 1000 })) {
                        stillLoading = true;
                        break;
                    }
                } catch (e) {
                    // Continue
                }
            }
            
            // Check for actual data presence
            const dataSelectors = [
                'text=/Session.*Overview/i',
                'text=/Detection.*Events/i',
                'text=/Hardware.*Status/i',
                'table',
                '.MuiCard-root'
            ];
            
            let hasData = false;
            
            for (const selector of dataSelectors) {
                try {
                    const element = await page.locator(selector).first();
                    if (await element.isVisible({ timeout: 2000 })) {
                        hasData = true;
                        break;
                    }
                } catch (e) {
                    // Continue
                }
            }
            
            const dataLoaded = !stillLoading && hasData;
            
            return this.logTest('data_loading_complete', dataLoaded, {
                still_loading: stillLoading,
                has_data: hasData,
                data_loaded: dataLoaded
            });
            
        } catch (error) {
            return this.logTest('data_loading_complete', false, {
                error: error.message
            });
        }
    }

    async runValidation() {
        console.log('🚀 Starting Frontend Ground Truth Validation...');
        console.log(`Frontend URL: ${this.baseUrl}`);
        console.log(`Test Session: ${this.testSessionId}`);
        
        const browser = await chromium.launch({ headless: true });
        const context = await browser.newContext();
        const page = await context.newPage();
        
        try {
            // Run all validation tests
            const testResults = [
                await this.testHILResultsPageAccessible(page),
                await this.testDataLoading(page),
                await this.testGroundTruthDisplayNotZero(page),
                await this.testEnhancedTimingToggle(page),
                await this.testTimingSynchronizationDisplay(page),
                await this.testGroundTruthComparisonCard(page),
                await this.testNoErrorMessages(page)
            ];
            
            // Calculate summary
            const totalTests = testResults.length;
            const passedTests = testResults.filter(result => result).length;
            const passRate = (passedTests / totalTests) * 100;
            
            this.results.summary = {
                total_tests: totalTests,
                passed_tests: passedTests,
                failed_tests: totalTests - passedTests,
                pass_rate: passRate,
                overall_result: passRate >= 80 ? 'PASS' : 'FAIL'
            };
            
            // Print summary
            console.log('\n' + '='.repeat(50));
            console.log('📊 FRONTEND VALIDATION SUMMARY');
            console.log('='.repeat(50));
            
            for (const [testName, result] of Object.entries(this.results.tests)) {
                const status = result.passed ? '✅ PASS' : '❌ FAIL';
                console.log(`${testName.padEnd(30)} : ${status}`);
            }
            
            console.log('-'.repeat(50));
            console.log(`Pass Rate: ${passedTests}/${totalTests} (${passRate.toFixed(1)}%)`);
            
            // Check the critical fix specifically
            const gtTest = this.results.tests['ground_truth_events_not_zero'];
            if (gtTest && gtTest.passed && gtTest.details.critical_fix_validated) {
                console.log('✅ CRITICAL FIX VALIDATED: Ground Truth Events showing correct count (24)');
            } else if (gtTest && gtTest.details.gt_event_count === 0) {
                console.log('❌ CRITICAL BUG STILL PRESENT: Ground Truth Events still showing 0');
            } else {
                console.log('⚠️  CRITICAL FIX STATUS UNCLEAR: Could not verify ground truth count');
            }
            
            console.log('='.repeat(50));
            
        } finally {
            await browser.close();
        }
        
        return this.results;
    }

    saveResults(outputFile = 'frontend_ground_truth_validation.json') {
        fs.writeFileSync(outputFile, JSON.stringify(this.results, null, 2));
        console.log(`\n📄 Results saved to: ${path.resolve(outputFile)}`);
    }
}

async function main() {
    const args = process.argv.slice(2);
    const baseUrl = args.find(arg => arg.startsWith('--base-url='))?.split('=')[1] || 'http://localhost:3000';
    const outputFile = args.find(arg => arg.startsWith('--output='))?.split('=')[1] || 'frontend_ground_truth_validation.json';
    
    const validator = new FrontendGroundTruthValidator(baseUrl);
    const results = await validator.runValidation();
    validator.saveResults(outputFile);
    
    // Exit with appropriate code
    const exitCode = results.summary.overall_result === 'PASS' ? 0 : 1;
    process.exit(exitCode);
}

if (require.main === module) {
    main().catch(error => {
        console.error('❌ Validation failed:', error);
        process.exit(1);
    });
}

module.exports = { FrontendGroundTruthValidator };