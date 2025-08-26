# AI Model Validation Platform - Deployment Scripts

This directory contains comprehensive build and deployment scripts that coordinate between backend database fixes and frontend rebuild to ensure a complete solution.

## 🚀 Quick Start

### Full Deployment
```bash
# Run complete deployment pipeline
./scripts/utils/deployment-runner.sh

# Or run the main deployment script directly  
./scripts/deployment/deploy.sh
```

### Individual Components
```bash
# Database migration only
./scripts/database/migrate.sh

# Clear caches only
./scripts/frontend/clear-cache.sh

# Frontend build only
./scripts/frontend/build.sh

# Validation only
./scripts/validation/validate.sh

# Emergency rollback
./scripts/rollback/rollback.sh
```

## 📁 Directory Structure

```
scripts/
├── deployment/
│   └── deploy.sh           # Main orchestration script
├── database/
│   └── migrate.sh          # Database migration and URL fixes
├── frontend/
│   ├── clear-cache.sh      # Comprehensive cache clearing
│   └── build.sh            # Optimized production build
├── validation/
│   └── validate.sh         # Deployment verification
├── rollback/
│   └── rollback.sh         # Emergency rollback capability
├── config/
│   └── deployment.config.json  # Configuration settings
├── utils/
│   ├── progress-reporter.sh    # Progress reporting utilities
│   └── deployment-runner.sh    # Central orchestration tool
└── README.md               # This file
```

## 🔄 Deployment Flow

The deployment process follows these coordinated steps:

1. **Pre-deployment Validation**
   - Environment checks
   - Tool availability
   - Disk space verification
   - Git status check

2. **Database Migration** 
   - URL optimization fixes
   - Schema updates
   - Localhost port corrections
   - Cache table creation

3. **Cache Clearing**
   - npm/yarn cache cleaning
   - node_modules cache removal
   - Build directory clearing
   - Temporary file cleanup

4. **Frontend Build**
   - Production environment setup
   - Optimized compilation
   - Bundle analysis
   - Asset optimization

5. **Deployment Validation**
   - Build integrity checks
   - URL fix verification
   - Component integration tests
   - Performance validation
   - Security scanning

6. **Post-deployment**
   - Report generation
   - Metadata saving
   - Cleanup tasks

## 🔧 Configuration

### Deployment Configuration
Edit `scripts/config/deployment.config.json` to customize:
- Timeout values
- Retry attempts
- Validation thresholds
- Environment variables
- Hook configurations

### Environment Variables
```bash
export NODE_ENV=production
export GENERATE_SOURCEMAP=false
export INLINE_RUNTIME_CHUNK=false
export NODE_OPTIONS="--max-old-space-size=8192"
```

## 🚨 Emergency Procedures

### Rollback Process
```bash
# Auto-detect latest backup and rollback
./scripts/rollback/rollback.sh

# Use specific backup directory
./scripts/rollback/rollback.sh /path/to/backup

# Force rollback without confirmation
./scripts/rollback/rollback.sh /path/to/backup true
```

### Rollback includes:
- Build directory restoration
- Configuration file recovery
- Cache restoration
- Database rollback (if applicable)
- Dependency reinstallation

## 📊 Monitoring & Logs

### Log Locations
- Main logs: `logs/`
- Deployment reports: `logs/deployment_report_*.md`
- Validation reports: `logs/validation_report_*.md`
- Cache clearing reports: `logs/cache_clearing_report_*.md`

### Progress Monitoring
The scripts provide real-time progress updates with:
- Step-by-step progress bars
- Performance metrics
- Resource usage monitoring
- Time estimation
- Colored output for easy reading

## 🔗 Integration with Claude Flow

### Hooks Integration
The scripts automatically integrate with Claude Flow hooks:

```bash
# Pre-task hooks
npx claude-flow@alpha hooks pre-task --description "deployment-validation"

# Progress notifications
npx claude-flow@alpha hooks notify --description "database-migration-completed"

# Post-task completion
npx claude-flow@alpha hooks post-task --description "deployment-completed"
```

### Memory Coordination
- Session management across deployment phases
- Memory store for sharing state between scripts
- Metrics export for performance analysis

## 🎯 URL Fixes Applied

The deployment specifically addresses these URL issues:

### Database Level
- Fix `localhost:undefined` → `localhost:8000`
- Convert relative paths to absolute URLs
- Create URL validation cache table
- Implement cache expiration

### Frontend Level  
- Video URL optimization
- Enhanced error handling
- URL validation utilities
- Cache management

### Configuration Level
- Update `public/config.js`
- Environment variable handling
- API endpoint configuration
- WebSocket URL fixes

## 🧪 Testing

### Validation Categories
- ✅ Build validation (critical files exist)
- ✅ URL fix verification (localhost corrections)
- ✅ Component integration (all components load)
- ✅ Service layer (API/WebSocket services)
- ✅ TypeScript compilation
- ✅ Test suite execution
- ✅ Performance checks (bundle size, timing)
- ✅ Security scanning (npm audit, sensitive data)
- ✅ Configuration validation
- ✅ Integration testing (smoke tests)

### Success Criteria
- All critical tests must pass
- Success rate ≥ 90%
- Build size ≤ 50MB
- No source maps in production
- No critical security vulnerabilities

## 🔒 Security Features

### Validation Checks
- No API keys in build files
- No development URLs in production
- Source map verification
- Dependency vulnerability scanning
- Sensitive information detection

### Safe Deployment
- Automatic backup creation
- Rollback capability
- Verification before proceeding
- Error handling and recovery
- Signal handling (CTRL+C safe)

## 📈 Performance Optimizations

### Build Optimizations
- Bundle splitting
- Tree shaking
- Code minification
- Asset compression
- Cache optimization

### Deployment Optimizations
- Parallel task execution
- Progress estimation
- Resource monitoring
- Timeout management
- Retry mechanisms

## 🆘 Troubleshooting

### Common Issues

#### Build Fails
```bash
# Check dependencies
npm audit
npm outdated

# Clear all caches
./scripts/frontend/clear-cache.sh

# Manual dependency reinstall
rm -rf node_modules package-lock.json
npm install
```

#### Database Migration Issues
```bash
# Check backend directory
ls -la ../backend/

# Verify Python environment
source ../backend/venv/bin/activate
pip list
```

#### Validation Failures
```bash
# Run individual validation
./scripts/validation/validate.sh

# Check build directory
ls -la build/

# Verify essential files
ls -la build/index.html build/static/
```

#### Performance Issues
```bash
# Monitor resource usage
free -h
df -h

# Check for memory leaks
npm run build:analyze

# Monitor build performance
time npm run build
```

## 📚 Additional Resources

### Related Files
- `src/utils/videoUrlFixer.ts` - URL optimization logic
- `src/config/environment.ts` - Environment configuration
- `public/config.js` - Public configuration
- `package.json` - Build scripts and dependencies

### Documentation
- [Video URL Optimization Summary](../docs/video-url-optimization-summary.md)
- [API Integration Specification](../docs/api-integration-specification.md)
- [Validation Reports](../docs/validation/)

---

## ⚡ Quick Reference

| Command | Purpose | Time | Retries |
|---------|---------|------|---------|
| `deploy.sh` | Full deployment | ~10min | N/A |
| `migrate.sh` | Database migration | ~2min | 2x |
| `clear-cache.sh` | Cache clearing | ~1min | 1x |
| `build.sh` | Frontend build | ~5min | 1x |
| `validate.sh` | Validation | ~3min | 1x |
| `rollback.sh` | Emergency rollback | ~2min | N/A |

**Total estimated deployment time: 10-15 minutes**

---

*Generated for AI Model Validation Platform*  
*Last updated: $(date)*