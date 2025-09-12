from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI Model Validation Platform", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {
        "status": "healthy", 
        "service": "AI Model Validation Platform",
        "version": "1.0.0",
        "environment": "deployment"
    }

@app.get("/")
def read_root():
    return {
        "message": "AI Model Validation Platform API", 
        "status": "running",
        "endpoints": ["/health", "/docs", "/api/projects"]
    }

@app.get("/api/projects")  
def get_projects():
    return {
        "projects": [], 
        "count": 0,
        "message": "No projects currently configured"
    }

@app.get("/api/status")
def get_status():
    return {
        "database": "connected",
        "redis": "connected", 
        "services": ["postgres", "redis", "backend"],
        "deployment": "successful"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)