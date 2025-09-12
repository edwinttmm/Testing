/**
 * Video Compatibility System Demonstration
 * 
 * This script demonstrates all the video compatibility features:
 * - Format detection and validation
 * - Browser compatibility checking
 * - Video accessibility testing
 * - Debug tools functionality
 */

import { 
  videoFormatValidator,
  validateVideoFormat,
  testVideoPlayability,
  getBrowserCapabilities as getFormatCapabilities
} from '../utils/videoFormatValidator';

import {
  videoCompatibilityChecker,
  performCompatibilityCheck,
  testVideoPlayback,
  getBrowserCapabilities
} from '../utils/videoCompatibilityChecker';

import {
  videoDebugTools,
  startDebugSession,
  testVideo,
  analyzeVideoFormat,
  generateCompatibilityMatrix,
  generateSessionReport
} from '../utils/videoDebugTools';

import {
  videoAccessibilityTester,
  testVideoAccessibility,
  testVideoPermissions,
  generateAccessibilityReport
} from '../utils/videoAccessibilityTester';

/**
 * Demo video URLs for testing
 */
const DEMO_VIDEOS = {
  mp4: 'https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4',
  webm: 'https://sample-videos.com/zip/10/webm/SampleVideo_1280x720_1mb.webm',
  ogg: 'https://sample-videos.com/zip/10/ogg/SampleVideo_1280x720_1mb.ogg',
  mov: 'https://sample-videos.com/zip/10/mov/SampleVideo_1280x720_1mb.mov',
  invalid: 'https://example.com/nonexistent-video.mp4'
};

class VideoCompatibilityDemo {
  
  /**
   * Run complete demonstration
   */
  async runDemo(): Promise<void> {
    console.log('🎥 Video Compatibility System Demo Starting...\n');
    
    try {
      await this.demoFormatValidation();
      await this.demoBrowserCapabilities();
      await this.demoCompatibilityChecking();
      await this.demoAccessibilityTesting();
      await this.demoDebugTools();
      await this.demoRealWorldScenarios();
      
      console.log('✅ Demo completed successfully!');
      
    } catch (error) {
      console.error('❌ Demo failed:', error);
    }
  }

  /**
   * Demo format validation functionality
   */
  async demoFormatValidation(): Promise<void> {
    console.log('📋 1. Format Validation Demo\n');
    
    const testFiles = [
      'video.mp4',
      'video.webm',
      'video.ogg',
      'video.mov',
      'video.avi',
      'video.mkv',
      'stream.m3u8',
      'unknown.xyz'
    ];

    console.log('Testing different video formats:');
    for (const filename of testFiles) {
      const result = validateVideoFormat(filename);
      const status = result.isSupported ? '✅' : '❌';
      
      console.log(`${status} ${filename}: ${result.originalFormat.displayName} (${result.originalFormat.browserSupport})`);
      
      if (result.errorMessage) {
        console.log(`   Error: ${result.errorMessage}`);
      }
      
      if (result.recommendation) {
        console.log(`   💡 ${result.recommendation}`);
      }
    }
    
    console.log('\n' + '='.repeat(50) + '\n');
  }

  /**
   * Demo browser capabilities detection
   */
  async demoBrowserCapabilities(): Promise<void> {
    console.log('🌐 2. Browser Capabilities Demo\n');
    
    const capabilities = getBrowserCapabilities();
    
    console.log('Browser Information:');
    console.log(`- Name: ${capabilities.browser.name} ${capabilities.browser.version}`);
    console.log(`- Engine: ${capabilities.browser.engine}`);
    console.log(`- Platform: ${capabilities.browser.platform}`);
    console.log(`- Mobile: ${capabilities.browser.mobile ? 'Yes' : 'No'}`);
    
    console.log('\nFormat Support:');
    Object.entries(capabilities.formats).forEach(([format, support]) => {
      const icon = support === 'full' ? '✅' : support === 'partial' ? '⚠️' : '❌';
      console.log(`- ${format.toUpperCase()}: ${icon} ${support}`);
    });
    
    console.log('\nCodec Support:');
    Object.entries(capabilities.codecs).forEach(([codec, supported]) => {
      const icon = supported ? '✅' : '❌';
      console.log(`- ${codec.toUpperCase()}: ${icon}`);
    });
    
    console.log('\nFeatures:');
    Object.entries(capabilities.features).forEach(([feature, support]) => {
      const status = typeof support === 'string' ? support : (support ? 'supported' : 'unsupported');
      console.log(`- ${feature}: ${status}`);
    });
    
    console.log('\n' + '='.repeat(50) + '\n');
  }

  /**
   * Demo compatibility checking
   */
  async demoCompatibilityChecking(): Promise<void> {
    console.log('🔍 3. Compatibility Checking Demo\n');
    
    const testCases = [
      { url: DEMO_VIDEOS.mp4, filename: 'sample.mp4' },
      { url: DEMO_VIDEOS.webm, filename: 'sample.webm' },
      { url: DEMO_VIDEOS.ogg, filename: 'sample.ogg' },
      { url: 'https://example.com/video.avi', filename: 'sample.avi' }
    ];

    for (const testCase of testCases) {
      console.log(`Testing: ${testCase.filename}`);
      
      try {
        const result = await performCompatibilityCheck(testCase.url, testCase.filename);
        
        const status = result.isCompatible ? '✅ Compatible' : '⚠️ Issues Found';
        console.log(`Result: ${status}`);
        
        if (result.primaryFormat) {
          console.log(`Primary Format: ${result.primaryFormat.toUpperCase()}`);
        }
        
        if (result.fallbackFormats.length > 0) {
          console.log(`Fallbacks: ${result.fallbackFormats.map(f => f.toUpperCase()).join(', ')}`);
        }
        
        if (result.recommendations.length > 0) {
          console.log('Recommendations:');
          result.recommendations.forEach(rec => console.log(`  💡 ${rec}`));
        }
        
        if (result.unsupportedReasons.length > 0) {
          console.log('Issues:');
          result.unsupportedReasons.forEach(reason => console.log(`  ⚠️ ${reason}`));
        }
        
      } catch (error) {
        console.log(`❌ Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }
      
      console.log('');
    }
    
    console.log('='.repeat(50) + '\n');
  }

  /**
   * Demo accessibility testing
   */
  async demoAccessibilityTesting(): Promise<void> {
    console.log('🔐 4. Accessibility Testing Demo\n');
    
    const testUrls = [
      DEMO_VIDEOS.mp4,
      DEMO_VIDEOS.webm,
      DEMO_VIDEOS.invalid
    ];

    for (const url of testUrls) {
      console.log(`Testing accessibility: ${url}`);
      
      try {
        const suite = await testVideoAccessibility(url);
        
        const status = suite.summary.overallAccessible ? '✅ Accessible' : '❌ Not Accessible';
        console.log(`Result: ${status}`);
        console.log(`Best Method: ${suite.summary.bestMethod.toUpperCase()}`);
        
        // Show individual test results
        Object.entries(suite.results).forEach(([method, result]) => {
          const methodStatus = result.isAccessible ? '✅' : '❌';
          const timing = result.responseTime ? ` (${result.responseTime}ms)` : '';
          console.log(`  ${method.toUpperCase()}: ${methodStatus}${timing}`);
        });
        
        if (suite.summary.issues.length > 0) {
          console.log('Issues:');
          suite.summary.issues.forEach(issue => console.log(`  ⚠️ ${issue}`));
        }
        
        // Test permissions
        const permissions = await testVideoPermissions(url);
        console.log('Permissions:');
        console.log(`  Range Requests: ${permissions.hasRangeRequestSupport ? '✅' : '❌'}`);
        console.log(`  CORS: ${permissions.corsEnabled ? '✅' : '❌'}`);
        
      } catch (error) {
        console.log(`❌ Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }
      
      console.log('');
    }
    
    console.log('='.repeat(50) + '\n');
  }

  /**
   * Demo debug tools
   */
  async demoDebugTools(): Promise<void> {
    console.log('🔧 5. Debug Tools Demo\n');
    
    // Start debug session
    const sessionId = startDebugSession();
    console.log(`Started debug session: ${sessionId}`);
    
    // Test multiple videos
    console.log('\nTesting videos with debug session:');
    
    const testVideos = [
      { url: DEMO_VIDEOS.mp4, format: 'mp4' },
      { url: DEMO_VIDEOS.webm, format: 'webm' },
      { url: DEMO_VIDEOS.invalid, format: 'mp4' }
    ];
    
    for (const video of testVideos) {
      try {
        console.log(`Testing: ${video.format.toUpperCase()}`);
        const result = await testVideo(video.url, video.format, sessionId);
        
        const loadStatus = result.canLoad ? '✅' : '❌';
        const playStatus = result.canPlay ? '✅' : '❌';
        const timing = result.loadTime ? ` (${result.loadTime}ms)` : '';
        
        console.log(`  Load: ${loadStatus} | Play: ${playStatus}${timing}`);
        
        if (result.error) {
          console.log(`  Error: ${result.error}`);
        }
        
        if (result.metadata?.dimensions) {
          console.log(`  Resolution: ${result.metadata.dimensions.width}x${result.metadata.dimensions.height}`);
        }
        
      } catch (error) {
        console.log(`  ❌ Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }
    }
    
    // Generate reports
    console.log('\nGenerating reports:');
    
    try {
      const sessionReport = generateSessionReport(sessionId);
      console.log('📊 Session Report Generated');
      
      const compatibilityMatrix = generateCompatibilityMatrix();
      console.log('📋 Compatibility Matrix Generated');
      
    } catch (error) {
      console.log(`⚠️ Report generation failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
    
    // Cleanup
    videoDebugTools.clearSession(sessionId);
    console.log('🧹 Debug session cleaned up');
    
    console.log('\n' + '='.repeat(50) + '\n');
  }

  /**
   * Demo real-world scenarios
   */
  async demoRealWorldScenarios(): Promise<void> {
    console.log('🌍 6. Real-World Scenarios Demo\n');
    
    // Scenario 1: Mobile user with limited bandwidth
    console.log('Scenario 1: Mobile User with Limited Bandwidth');
    await this.demoMobileScenario();
    
    // Scenario 2: Legacy browser support
    console.log('\nScenario 2: Legacy Browser Support');
    await this.demoLegacyBrowserScenario();
    
    // Scenario 3: Corporate network with restrictions
    console.log('\nScenario 3: Corporate Network with Restrictions');
    await this.demoCorporateScenario();
    
    console.log('='.repeat(50) + '\n');
  }

  /**
   * Demo mobile scenario
   */
  private async demoMobileScenario(): Promise<void> {
    console.log('📱 Testing for mobile compatibility...');
    
    const capabilities = getBrowserCapabilities();
    
    if (capabilities.browser.mobile) {
      console.log('✅ Mobile browser detected');
      console.log('💡 Recommendations:');
      console.log('  - Use lower bitrate videos');
      console.log('  - Enable progressive loading');
      console.log('  - Provide multiple quality options');
      console.log('  - Consider autoplay restrictions');
    } else {
      console.log('🖥️ Desktop browser detected');
      console.log('💡 Mobile simulation recommendations:');
      console.log('  - Test with network throttling');
      console.log('  - Verify touch controls');
      console.log('  - Check orientation handling');
    }
  }

  /**
   * Demo legacy browser scenario
   */
  private async demoLegacyBrowserScenario(): Promise<void> {
    console.log('🕰️ Testing for legacy browser compatibility...');
    
    const capabilities = getBrowserCapabilities();
    
    // Check for modern codec support
    const modernCodecs = ['vp9', 'av1', 'h265'];
    const supportedModern = modernCodecs.filter(codec => 
      capabilities.codecs[codec as keyof typeof capabilities.codecs]
    );
    
    if (supportedModern.length === 0) {
      console.log('⚠️ Limited modern codec support detected');
      console.log('💡 Fallback strategy:');
      console.log('  - Prioritize MP4 (H.264) format');
      console.log('  - Avoid WebM for primary delivery');
      console.log('  - Test fullscreen API fallbacks');
    } else {
      console.log('✅ Modern codec support available');
      console.log(`Supported: ${supportedModern.join(', ').toUpperCase()}`);
    }
  }

  /**
   * Demo corporate scenario
   */
  private async demoCorporateScenario(): Promise<void> {
    console.log('🏢 Testing for corporate network restrictions...');
    
    // Simulate testing a corporate environment
    console.log('🔍 Checking common restrictions:');
    
    const testUrl = DEMO_VIDEOS.mp4;
    
    try {
      const suite = await testVideoAccessibility(testUrl);
      
      // Check for CORS
      if (!suite.summary.overallAccessible) {
        console.log('⚠️ Potential corporate restrictions:');
        suite.summary.issues.forEach(issue => {
          if (issue.toLowerCase().includes('cors')) {
            console.log('  - CORS policy blocking video access');
          }
          if (issue.toLowerCase().includes('forbidden')) {
            console.log('  - Content filtering active');
          }
          if (issue.toLowerCase().includes('timeout')) {
            console.log('  - Network proxy causing delays');
          }
        });
        
        console.log('💡 Corporate environment solutions:');
        console.log('  - Use CDN with proper CORS headers');
        console.log('  - Provide alternative video sources');
        console.log('  - Implement retry mechanisms');
        console.log('  - Consider streaming protocols (HLS)');
      } else {
        console.log('✅ No corporate restrictions detected');
      }
      
    } catch (error) {
      console.log('❌ Network access test failed - likely corporate firewall');
    }
  }

  /**
   * Generate summary report
   */
  generateSummaryReport(): string {
    const capabilities = getBrowserCapabilities();
    const matrix = generateCompatibilityMatrix();
    
    let report = '# Video Compatibility System Summary\n\n';
    report += `**Browser:** ${capabilities.browser.name} ${capabilities.browser.version}\n`;
    report += `**Platform:** ${capabilities.browser.platform}\n`;
    report += `**Mobile:** ${capabilities.browser.mobile ? 'Yes' : 'No'}\n\n`;
    
    report += '## Recommendations\n\n';
    
    // Generate recommendations based on detected capabilities
    if (capabilities.formats.mp4 === 'full') {
      report += '- ✅ Use MP4 (H.264/AAC) as primary format\n';
    }
    
    if (capabilities.formats.webm === 'full' && capabilities.browser.name !== 'safari') {
      report += '- ✅ WebM can be used as alternative format\n';
    } else {
      report += '- ⚠️ WebM support limited - stick to MP4\n';
    }
    
    if (!capabilities.features.fullscreen) {
      report += '- ⚠️ Fullscreen not supported - provide alternative controls\n';
    }
    
    if (capabilities.browser.mobile) {
      report += '- 📱 Mobile optimizations recommended (lower bitrates, touch controls)\n';
    }
    
    if (capabilities.features.autoplay !== 'allowed') {
      report += '- 🔇 Autoplay restricted - always show play button\n';
    }
    
    return report;
  }
}

// Export demo class and create instance
export const videoCompatibilityDemo = new VideoCompatibilityDemo();

// Auto-run demo if this file is executed directly
if (typeof window !== 'undefined' && (window as any).runVideoDemo) {
  videoCompatibilityDemo.runDemo();
}

export default videoCompatibilityDemo;