# 🚨 IMMEDIATE DIAGNOSTIC COMMANDS

The containers are running but backend health endpoint is not responding. Run these commands **on your server**:

## 1. Check Backend Container Logs (CRITICAL)
```bash
# Check backend startup logs for errors
docker logs ai-model-validation-platform-backend-1

# Follow logs in real-time
docker logs -f ai-model-validation-platform-backend-1
```

## 2. Test Internal Container Connectivity
```bash
# Test if backend is responding inside the container
docker exec -it ai-model-validation-platform-backend-1 curl localhost:8000/health

# Test backend from inside the network
docker exec -it ai-model-validation-platform-frontend-1 curl backend:8000/health
```

## 3. Test Direct Server Access
```bash
# Test from the server itself (localhost)
curl localhost:8000/health
curl 127.0.0.1:8000/health

# Test the external IP from server
curl 155.138.239.131:8000/health
```

## 4. Check Port Binding
```bash
# Check if port 8000 is actually bound
netstat -tulpn | grep :8000
# Or use ss if netstat not available
ss -tulpn | grep :8000
```

## 5. Check Container Health
```bash
# Inspect backend container
docker inspect ai-model-validation-platform-backend-1 | grep -A5 "Health"

# Check container processes
docker exec -it ai-model-validation-platform-backend-1 ps aux
```

## 6. Frontend Logs
```bash
# Check frontend logs for specific errors
docker logs ai-model-validation-platform-frontend-1
```

---

**Run commands 1 and 2 first - they'll tell us if the backend is starting up properly or crashing.**

## Expected Results:
- **If backend logs show startup errors**: We need to fix the backend configuration
- **If backend responds on localhost:8000 but not 155.138.239.131:8000**: Port binding issue
- **If backend doesn't respond at all**: Backend crash or startup failure

Please run these commands and share the output!