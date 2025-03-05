import uvicorn
from app.core.init import create_app

# Create the FastAPI application
app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0", 
        port=8000,
        reload=True
    )