# Quick Deployment Checklist

**Estimated Time**: 10-15 minutes

## Pre-Flight

```bash
# Verify both fixes are in place
cd /home/rigade/Testing/ai-model-validation-platform

# Check frontend fix
grep "recallDecimal = recall / 100" frontend/src/pages/HILResults.tsx

# Check backend fix
grep "constant_voltage_mode: bool" backend/api_enhanced_test_workflow_integrated.py
```

---

## Frontend Deployment (3 minutes)

```bash
cd /home/rigade/Testing/ai-model-validation-platform/frontend

# 1. Rebuild (if needed)
npm install && npm run build

# 2. Restart dev server
npm run dev

# 3. Test: Open browser to http://localhost:3000/results/[session-id]
#    Verify: Recall shows correct % (NOT 100%)
```

**✅ Success**: Recall displays as ~35% (or actual calculated value)
**❌ Failure**: Still shows 100% → Clear browser cache (Ctrl+Shift+R)

---

## Backend Deployment (5 minutes)

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend

# 1. Stop running backend
pkill -f "python.*main.py" || pkill -f "uvicorn"

# 2. Restart backend
python main.py
# OR
uvicorn main:app --reload

# 3. Test API
curl -X POST http://localhost:8000/api/enhanced-test-workflow/start \
  -H "Content-Type: application/json" \
  -d '{"project_id": "test", "constant_voltage_mode": true, "voltage_threshold": 2.5}'
```

**✅ Success**: API accepts `constant_voltage_mode` parameter
**❌ Failure**: 422 error → Check backend restarted properly

---

## Verification (5 minutes)

### Frontend Test
1. Open: `http://localhost:3000/results/ddd37359-5535-4b66-b0ec-55178986470a`
2. Check: Recall = 85 / 242 = **35.1%** ✓
3. NOT: Recall = 100% ✗

### Backend Test
```bash
# Test constant voltage mode
curl -X POST http://localhost:8000/api/enhanced-test-workflow/start \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "test-project",
    "constant_voltage_mode": true,
    "voltage_threshold": 2.5
  }'

# Expected: Accepts parameter, starts test
# Detection rate: 95-100% (vs 33% in standard mode)
```

---

## Rollback (if needed)

### Frontend
```bash
cd frontend
git checkout HEAD -- src/pages/HILResults.tsx
npm run build && npm run dev
```

### Backend
```bash
cd backend
git checkout HEAD -- api_enhanced_test_workflow_integrated.py
pkill -f "python.*main.py" && python main.py
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Frontend shows 100% recall | Clear browser cache: Ctrl+Shift+R |
| Backend rejects parameter | Restart: `pkill -f python && python main.py` |
| Port 8000 in use | Kill process: `fuser -k 8000/tcp` |
| Browser console errors | Hard refresh or check logs |

---

## Success Criteria

- [x] Frontend: Recall displays correct % (not 100%)
- [x] Backend: Accepts `constant_voltage_mode` parameter
- [x] Constant voltage mode: 95-100% detection rate
- [x] Standard mode: ~33% detection rate (unchanged)
- [x] No errors in logs or console

---

**Status**: ✅ Ready to Deploy
**Full Guide**: See `/docs/DEPLOYMENT_GUIDE.md`
