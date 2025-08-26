# 🚀 Quick Start Guide - Database URL Migration

## TL;DR - Fix localhost URLs in 3 Steps

### Step 1: Check Status
```bash
cd /home/user/Testing/ai-model-validation-platform/backend
npm run migrate status
```

### Step 2: Run Migration
```bash
npm run migrate execute --force
```

### Step 3: Verify Results
```bash
npm run migrate validate
```

**That's it! Your localhost URLs are now production URLs (155.138.239.131:8000).**

---

## 📋 What This Migration Does

**BEFORE:**
```
http://localhost:8000/uploads/video1.mp4
http://127.0.0.1:8000/uploads/thumb1.jpg
```

**AFTER:**
```
http://155.138.239.131:8000/uploads/video1.mp4
http://155.138.239.131:8000/uploads/thumb1.jpg
```

---

## 🎯 One-Liner Commands

| Action | Command |
|--------|---------|
| **Check Status** | `npm run migrate status` |
| **Preview Changes** | `npm run migrate dry-run` |
| **Execute Migration** | `npm run migrate execute --force` |
| **Validate Results** | `npm run migrate validate` |
| **Rollback (if needed)** | `npm run migrate rollback 001_fix_localhost_urls` |

---

## 🔧 API Endpoints (155.138.239.131:8001)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/migrations/status` | Check migration status |
| POST | `/api/migrations/execute` | Run migration |
| POST | `/api/migrations/validate` | Verify results |

### Quick API Test:
```bash
# Check status via API
curl http://155.138.239.131:8001/api/migrations/status

# Execute migration via API
curl -X POST http://155.138.239.131:8001/api/migrations/execute \
  -H "Content-Type: application/json" \
  -d '{"dryRun": false}'
```

---

## ⚡ Installation & Setup

### Install Dependencies
```bash
cd /home/user/Testing/ai-model-validation-platform/backend
npm install express sqlite3 sqlite readline
```

### Start Migration Server (Optional)
```bash
node migration-server.js
```
Server will start at `http://155.138.239.131:8001`

---

## 🧪 Test Everything Works

### Run Test Suite
```bash
node test-migration.js
```

Expected output:
```
✅ Schema Analysis - PASSED
✅ Initial Validation - PASSED  
✅ Dry Run Migration - PASSED
✅ Migration Execution - PASSED
✅ Post-Migration Validation - PASSED
✅ Data Integrity Check - PASSED
✅ Migration Rollback - PASSED

🎉 Migration test suite completed successfully!
```

---

## 🔍 Troubleshooting

### Problem: "Migration already executed"
**Solution:** URLs are already migrated. Run `npm run migrate validate` to confirm.

### Problem: "Database not found"
**Solution:** Set correct database path:
```bash
export DATABASE_PATH="/path/to/your/database.db"
npm run migrate status
```

### Problem: "Permission denied"
**Solution:** Make CLI executable:
```bash
chmod +x scripts/migration-cli.js
```

---

## 📊 Expected Results

After successful migration:
- ✅ 0 localhost URLs remaining
- ✅ All URLs point to 155.138.239.131:8000
- ✅ Video playback works from frontend
- ✅ Thumbnail loading works
- ✅ Backup created for safety

---

## 🚨 Safety Features

- **Automatic Backup:** Every migration creates a backup
- **Dry Run:** Preview changes before applying
- **Rollback:** Undo migrations if needed
- **Validation:** Verify results after migration
- **Atomic Operations:** All-or-nothing execution

---

## 📁 Files Created

```
backend/
├── migrations/
│   └── 001_fix_localhost_urls.sql
├── services/
│   └── DatabaseMigrationService.js  
├── controllers/
│   └── MigrationController.js
├── routes/
│   └── migrations.js
├── utils/
│   └── DatabaseValidator.js
├── scripts/
│   └── migration-cli.js
├── docs/
│   └── MIGRATION_GUIDE.md
├── migration-server.js
├── test-migration.js
└── package.json
```

---

## 🎯 Integration with Your Backend

Add to your existing Express app:
```javascript
const migrationRoutes = require('./routes/migrations');
app.use('/api/migrations', migrationRoutes(database));
```

---

## 📞 Support

- **Full Documentation:** `backend/docs/MIGRATION_GUIDE.md`
- **API Docs:** `GET http://155.138.239.131:8001/api/migrations/docs`
- **Help:** `npm run migrate help`

---

**🎉 Your localhost URLs will be production-ready in under 2 minutes!**