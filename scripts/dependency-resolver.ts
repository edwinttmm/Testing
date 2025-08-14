/**
 * Automated Dependency Conflict Resolution System
 * Resolves version mismatches between package.json and package-lock.json
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { execSync } from 'child_process';
import * as path from 'path';

export interface DependencyConflict {
  name: string;
  packageJsonVersion: string;
  lockFileVersion: string;
  recommendedVersion: string;
  severity: 'critical' | 'major' | 'minor';
  reason: string;
}

export interface ResolutionStrategy {
  strategy: 'upgrade' | 'downgrade' | 'force' | 'manual';
  reason: string;
  commands: string[];
}

export interface DependencyAnalysis {
  conflicts: DependencyConflict[];
  resolutions: Map<string, ResolutionStrategy>;
  riskAssessment: {
    breakingChanges: string[];
    compatibilityRisks: string[];
    performanceImpact: string[];
  };
}

class DependencyResolver {
  private projectRoot: string;
  private packageJsonPath: string;
  private packageLockPath: string;

  constructor(projectRoot: string = process.cwd()) {
    this.projectRoot = projectRoot;
    this.packageJsonPath = path.join(projectRoot, 'package.json');
    this.packageLockPath = path.join(projectRoot, 'package-lock.json');
  }

  /**
   * Analyze dependency conflicts and generate resolution strategies
   */
  async analyzeDependencies(): Promise<DependencyAnalysis> {
    console.log('🔍 Analyzing dependency conflicts...');

    const packageJson = this.readPackageJson();
    const packageLock = this.readPackageLock();
    
    const conflicts = this.detectConflicts(packageJson, packageLock);
    const resolutions = this.generateResolutions(conflicts);
    const riskAssessment = this.assessRisks(conflicts);

    return {
      conflicts,
      resolutions,
      riskAssessment,
    };
  }

  /**
   * Automatically resolve dependencies based on analysis
   */
  async resolveDependencies(analysis: DependencyAnalysis, options: {
    autoFix: boolean;
    backup: boolean;
    dryRun: boolean;
  } = { autoFix: false, backup: true, dryRun: true }): Promise<void> {
    console.log('🔧 Resolving dependency conflicts...');

    if (options.backup) {
      this.createBackup();
    }

    if (options.dryRun) {
      console.log('📋 DRY RUN - Changes that would be made:');
      this.printResolutionPlan(analysis);
      return;
    }

    // Execute critical fixes first
    const criticalConflicts = analysis.conflicts.filter(c => c.severity === 'critical');
    for (const conflict of criticalConflicts) {
      const resolution = analysis.resolutions.get(conflict.name);
      if (resolution && options.autoFix) {
        await this.executeResolution(conflict, resolution);
      }
    }

    // Execute major fixes
    const majorConflicts = analysis.conflicts.filter(c => c.severity === 'major');
    for (const conflict of majorConflicts) {
      const resolution = analysis.resolutions.get(conflict.name);
      if (resolution && options.autoFix) {
        await this.executeResolution(conflict, resolution);
      }
    }

    // Rebuild lock file
    if (options.autoFix) {
      console.log('🔄 Rebuilding package-lock.json...');
      this.rebuildLockFile();
    }
  }

  /**
   * Detect conflicts between package.json and package-lock.json
   */
  private detectConflicts(packageJson: any, packageLock: any): DependencyConflict[] {
    const conflicts: DependencyConflict[] = [];
    const allDeps = {
      ...packageJson.dependencies,
      ...packageJson.devDependencies,
    };

    for (const [name, version] of Object.entries(allDeps)) {
      const lockEntry = packageLock.packages?.['']?.dependencies?.[name] || 
                       packageLock.packages?.['']?.devDependencies?.[name];
      
      if (lockEntry && lockEntry !== version) {
        const conflict = this.analyzeConflict(name, version as string, lockEntry);
        if (conflict) {
          conflicts.push(conflict);
        }
      }
    }

    // Special checks for known problematic combinations
    conflicts.push(...this.detectSpecialConflicts(packageJson, packageLock));

    return conflicts;
  }

  /**
   * Analyze individual conflict and determine severity
   */
  private analyzeConflict(name: string, packageVersion: string, lockVersion: string): DependencyConflict | null {
    const severity = this.determineSeverity(name, packageVersion, lockVersion);
    const recommendedVersion = this.getRecommendedVersion(name, packageVersion, lockVersion);
    
    return {
      name,
      packageJsonVersion: packageVersion,
      lockFileVersion: lockVersion,
      recommendedVersion,
      severity,
      reason: this.getConflictReason(name, packageVersion, lockVersion),
    };
  }

  /**
   * Detect special conflicts (React 19 + react-scripts, etc.)
   */
  private detectSpecialConflicts(packageJson: any, packageLock: any): DependencyConflict[] {
    const conflicts: DependencyConflict[] = [];

    // React 19 + react-scripts 5.0.1 conflict
    if (packageJson.dependencies?.react?.includes('19.') && 
        packageJson.dependencies?.['react-scripts'] === '5.0.1') {
      conflicts.push({
        name: 'react-scripts',
        packageJsonVersion: '5.0.1',
        lockFileVersion: '5.0.1',
        recommendedVersion: '6.0.0-beta.1 || vite',
        severity: 'major',
        reason: 'react-scripts 5.0.1 has limited React 19 support. Consider migrating to Vite.',
      });
    }

    // TypeScript version conflicts
    const tsInPackage = packageJson.dependencies?.typescript || packageJson.devDependencies?.typescript;
    const tsInLock = packageLock.packages?.['']?.dependencies?.typescript || 
                    packageLock.packages?.['']?.devDependencies?.typescript;
    
    if (tsInPackage && tsInLock && tsInPackage !== tsInLock) {
      const [packageMajor] = tsInPackage.replace('^', '').split('.');
      const [lockMajor] = tsInLock.replace('^', '').split('.');
      
      if (parseInt(packageMajor) !== parseInt(lockMajor)) {
        conflicts.push({
          name: 'typescript',
          packageJsonVersion: tsInPackage,
          lockFileVersion: tsInLock,
          recommendedVersion: tsInPackage,
          severity: 'critical',
          reason: 'Major TypeScript version mismatch can cause build failures.',
        });
      }
    }

    return conflicts;
  }

  /**
   * Generate resolution strategies for conflicts
   */
  private generateResolutions(conflicts: DependencyConflict[]): Map<string, ResolutionStrategy> {
    const resolutions = new Map<string, ResolutionStrategy>();

    for (const conflict of conflicts) {
      const resolution = this.createResolutionStrategy(conflict);
      resolutions.set(conflict.name, resolution);
    }

    return resolutions;
  }

  /**
   * Create resolution strategy for individual conflict
   */
  private createResolutionStrategy(conflict: DependencyConflict): ResolutionStrategy {
    switch (conflict.name) {
      case 'typescript':
        return {
          strategy: 'upgrade',
          reason: 'Upgrade to latest TypeScript for React 19 compatibility',
          commands: [
            'npm install --save-dev typescript@latest',
            'npm install --save-dev @types/node@latest',
          ],
        };

      case 'react-scripts':
        return {
          strategy: 'manual',
          reason: 'Manual migration to Vite recommended for React 19',
          commands: [
            '# Consider migrating to Vite for better React 19 support',
            '# npm create vite@latest . -- --template react-ts',
          ],
        };

      case '@testing-library/user-event':
        return {
          strategy: 'upgrade',
          reason: 'Upgrade to latest for React 19 compatibility',
          commands: [
            'npm install --save-dev @testing-library/user-event@latest',
          ],
        };

      case '@types/node':
        return {
          strategy: 'upgrade',
          reason: 'Upgrade for Node.js compatibility',
          commands: [
            'npm install --save-dev @types/node@latest',
          ],
        };

      default:
        if (conflict.severity === 'critical') {
          return {
            strategy: 'force',
            reason: 'Force resolution for critical conflicts',
            commands: [
              `npm install ${conflict.name}@${conflict.recommendedVersion} --force`,
            ],
          };
        } else {
          return {
            strategy: 'upgrade',
            reason: 'Standard upgrade resolution',
            commands: [
              `npm install ${conflict.name}@${conflict.recommendedVersion}`,
            ],
          };
        }
    }
  }

  /**
   * Assess risks of proposed changes
   */
  private assessRisks(conflicts: DependencyConflict[]): {
    breakingChanges: string[];
    compatibilityRisks: string[];
    performanceImpact: string[];
  } {
    const risks = {
      breakingChanges: [],
      compatibilityRisks: [],
      performanceImpact: [],
    };

    for (const conflict of conflicts) {
      switch (conflict.name) {
        case 'typescript':
          if (conflict.severity === 'critical') {
            risks.breakingChanges.push('TypeScript major version upgrade may require code changes');
          }
          break;

        case 'react-scripts':
          risks.compatibilityRisks.push('react-scripts 5.0.1 has limited React 19 support');
          risks.performanceImpact.push('May have slower build times with React 19');
          break;

        case '@types/node':
          risks.compatibilityRisks.push('Node.js type definitions may affect compilation');
          break;
      }
    }

    return risks;
  }

  /**
   * Execute individual resolution
   */
  private async executeResolution(conflict: DependencyConflict, resolution: ResolutionStrategy): Promise<void> {
    console.log(`🔧 Resolving ${conflict.name}: ${resolution.reason}`);

    for (const command of resolution.commands) {
      if (command.startsWith('#')) {
        console.log(`💡 ${command}`);
        continue;
      }

      try {
        console.log(`📦 Executing: ${command}`);
        execSync(command, { 
          cwd: this.projectRoot, 
          stdio: 'inherit',
          timeout: 300000, // 5 minutes
        });
      } catch (error) {
        console.error(`❌ Failed to execute: ${command}`);
        console.error(error);
      }
    }
  }

  /**
   * Utility methods
   */
  private readPackageJson(): any {
    if (!existsSync(this.packageJsonPath)) {
      throw new Error('package.json not found');
    }
    return JSON.parse(readFileSync(this.packageJsonPath, 'utf8'));
  }

  private readPackageLock(): any {
    if (!existsSync(this.packageLockPath)) {
      throw new Error('package-lock.json not found');
    }
    return JSON.parse(readFileSync(this.packageLockPath, 'utf8'));
  }

  private createBackup(): void {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const backupDir = path.join(this.projectRoot, '.dependency-backups', timestamp);
    
    execSync(`mkdir -p "${backupDir}"`, { cwd: this.projectRoot });
    execSync(`cp package.json "${backupDir}/"`, { cwd: this.projectRoot });
    execSync(`cp package-lock.json "${backupDir}/"`, { cwd: this.projectRoot });
    
    console.log(`📦 Backup created at: ${backupDir}`);
  }

  private rebuildLockFile(): void {
    try {
      execSync('rm -f package-lock.json node_modules/.package-lock.json', { cwd: this.projectRoot });
      execSync('npm install', { cwd: this.projectRoot, stdio: 'inherit' });
    } catch (error) {
      console.error('Failed to rebuild lock file:', error);
    }
  }

  private printResolutionPlan(analysis: DependencyAnalysis): void {
    console.log('\n📋 Resolution Plan:');
    console.log('==================');
    
    for (const conflict of analysis.conflicts) {
      const resolution = analysis.resolutions.get(conflict.name);
      console.log(`\n🔧 ${conflict.name}`);
      console.log(`   Current: ${conflict.lockFileVersion}`);
      console.log(`   Expected: ${conflict.packageJsonVersion}`);
      console.log(`   Recommended: ${conflict.recommendedVersion}`);
      console.log(`   Severity: ${conflict.severity}`);
      console.log(`   Strategy: ${resolution?.strategy || 'none'}`);
      console.log(`   Reason: ${conflict.reason}`);
    }

    console.log('\n⚠️  Risk Assessment:');
    console.log('===================');
    if (analysis.riskAssessment.breakingChanges.length > 0) {
      console.log('💥 Breaking Changes:');
      analysis.riskAssessment.breakingChanges.forEach(risk => console.log(`   - ${risk}`));
    }
    if (analysis.riskAssessment.compatibilityRisks.length > 0) {
      console.log('🔶 Compatibility Risks:');
      analysis.riskAssessment.compatibilityRisks.forEach(risk => console.log(`   - ${risk}`));
    }
    if (analysis.riskAssessment.performanceImpact.length > 0) {
      console.log('⚡ Performance Impact:');
      analysis.riskAssessment.performanceImpact.forEach(risk => console.log(`   - ${risk}`));
    }
  }

  private determineSeverity(name: string, packageVersion: string, lockVersion: string): 'critical' | 'major' | 'minor' {
    // Critical packages that must match exactly
    const criticalPackages = ['typescript', 'react', 'react-dom'];
    if (criticalPackages.includes(name)) {
      return 'critical';
    }

    // Check for major version differences
    const packageMajor = this.extractMajorVersion(packageVersion);
    const lockMajor = this.extractMajorVersion(lockVersion);
    
    if (packageMajor !== lockMajor) {
      return 'major';
    }

    return 'minor';
  }

  private extractMajorVersion(version: string): number {
    const match = version.match(/(\d+)/);
    return match ? parseInt(match[1]) : 0;
  }

  private getRecommendedVersion(name: string, packageVersion: string, lockVersion: string): string {
    // For most packages, prefer the package.json version
    return packageVersion;
  }

  private getConflictReason(name: string, packageVersion: string, lockVersion: string): string {
    const packageMajor = this.extractMajorVersion(packageVersion);
    const lockMajor = this.extractMajorVersion(lockVersion);
    
    if (packageMajor > lockMajor) {
      return `Package.json specifies newer version (${packageVersion}) than lock file (${lockVersion})`;
    } else if (packageMajor < lockMajor) {
      return `Lock file has newer version (${lockVersion}) than package.json (${packageVersion})`;
    } else {
      return `Minor version mismatch between package.json (${packageVersion}) and lock file (${lockVersion})`;
    }
  }
}

/**
 * CLI interface for dependency resolution
 */
export async function resolveDependenciesCommand(options: {
  projectRoot?: string;
  autoFix?: boolean;
  backup?: boolean;
  dryRun?: boolean;
} = {}): Promise<void> {
  const resolver = new DependencyResolver(options.projectRoot);
  
  try {
    const analysis = await resolver.analyzeDependencies();
    
    console.log(`\n🔍 Analysis Results:`);
    console.log(`   Conflicts found: ${analysis.conflicts.length}`);
    console.log(`   Critical: ${analysis.conflicts.filter(c => c.severity === 'critical').length}`);
    console.log(`   Major: ${analysis.conflicts.filter(c => c.severity === 'major').length}`);
    console.log(`   Minor: ${analysis.conflicts.filter(c => c.severity === 'minor').length}`);

    await resolver.resolveDependencies(analysis, {
      autoFix: options.autoFix || false,
      backup: options.backup !== false,
      dryRun: options.dryRun !== false,
    });

    console.log('\n✅ Dependency analysis complete!');
  } catch (error) {
    console.error('❌ Dependency resolution failed:', error);
    process.exit(1);
  }
}

/**
 * Export resolver for programmatic use
 */
export { DependencyResolver };