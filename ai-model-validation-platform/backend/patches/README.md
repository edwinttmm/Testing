# Integration Patches

This directory contains Git-style patch files for applying backend integration fixes.

## Status

**TEMPLATE** - Patches will be generated after agent findings are available.

## How to Use Patches

### Automatic Application

The integration scripts will apply patches automatically:

```bash
# Apply all patches automatically
./scripts/integrate_everything.sh

# Or apply backend patches only
./scripts/apply_backend_integration.sh
```

### Manual Application

To apply a specific patch manually:

```bash
# From the backend directory
git apply patches/add_monitoring_router.patch

# Or with more verbose output
git apply --verbose patches/add_monitoring_router.patch

# To check what a patch would do without applying
git apply --check patches/add_monitoring_router.patch
```

### Reverting Patches

To revert a patch:

```bash
# Revert specific patch
git apply -R patches/add_monitoring_router.patch

# Or restore from backup
BACKUP_DIR="$(cat .last_backup)"
cp $BACKUP_DIR/main.py.bak ./main.py
```

## Patch Files

Patches will be created for:

- [ ] **Router Registration Fixes** - `add_monitoring_router.patch`
  - Adds missing router registrations to main.py
  - Fixes router import statements
  - Ensures proper URL prefixes

- [ ] **Service Initialization Fixes** - `fix_service_initialization.patch`
  - Updates service initialization in main.py
  - Adds missing service imports
  - Fixes service configuration

- [ ] **Database Schema Updates** - `update_database_imports.patch`
  - Adds missing database model imports
  - Updates schema references

- [ ] **Additional fixes as identified by agents**

## Patch Format

All patches use standard Git unified diff format:

```diff
--- a/main.py
+++ b/main.py
@@ -123,6 +123,10 @@
 # Existing code

+# New code added by patch
+from routers.monitoring import router as monitoring_router
+app.include_router(monitoring_router, prefix="/api/monitoring")
+
 # More existing code
```

## Creating New Patches

If you need to create a patch manually:

```bash
# After making changes
git diff > patches/my_fix.patch

# Or for specific files
git diff main.py > patches/main_py_fixes.patch
```

## Troubleshooting

### Patch Fails to Apply

If a patch fails with conflicts:

1. **Check if changes already exist**: The patch may already be applied
2. **Check for whitespace issues**: Use `git apply --whitespace=fix`
3. **Apply manually**: Review the patch and make changes by hand
4. **Restore from backup**: Use backup and reapply carefully

### Finding Applied Patches

To see which patches have been applied:

```bash
# Check git log if using version control
git log --oneline

# Or check the integration log
cat integration_*.log | grep -i "patch"
```

## Next Steps After Agent Completion

1. **Agent 1** (Backend Audit) will identify:
   - Missing router registrations
   - Service initialization issues
   - Import statement fixes

2. **Generate Patches**: Based on findings, create:
   ```bash
   # Example patch generation
   git diff main.py > patches/add_monitoring_router.patch
   ```

3. **Test Patches**: Verify patches apply cleanly:
   ```bash
   git apply --check patches/*.patch
   ```

4. **Update Scripts**: Ensure integration scripts reference new patches

---

**Directory Created**: 2025-11-19
**Status**: Awaiting agent findings
**Next Update**: After agents complete their audits
