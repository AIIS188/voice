import os
from typing import List
from pydantic import BaseSettings

class Settings(BaseSettings):
    # API配置
    API_V1_STR: str = "/v1"
    PROJECT_NAME: str = "声教助手"
    
    # CORS配置
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # 数据库配置
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "voice_assistant")
    
    # 安全配置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天
    
    # 文件存储配置
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024  # 20MB
    
    # 模型配置
    MODELS_DIR: str = os.getenv("MODELS_DIR", "../models/weights")
    
    class Config:
        env_file = ".env"

settings = Settings()

# 确保上传目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)