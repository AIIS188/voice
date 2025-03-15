import os
from typing import List, Dict, Any
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    # API配置
    API_V1_STR: str = "/v1"
    PROJECT_NAME: str = "声教助手"
    
    # CORS配置
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # 数据库配置
    MONGODB_URL: str = Field(default="mongodb://localhost:27017")
    DATABASE_NAME: str = Field(default="voice_assistant")
    
    # 安全配置
    SECRET_KEY: str = Field(default="your-secret-key-here")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天
    
    # 文件存储配置
    UPLOAD_DIR: str = Field(default="./uploads")
    MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024  # 20MB
    
    # 模型配置 - 必须在使用它之前定义
    MODELS_DIR: str = Field(default="./models/weights")
    
    # TTS模型配置
    TTS_MODELS_DIR: str = ""
    TTS_VOICE_ENCODER_PATH: str = ""
    TTS_METRICS_MODEL_PATH: str = ""
    TTS_DEFAULT_PARAMS: Dict[str, Any] = {
        "speed": 1.0,
        "pitch": 0.0,
        "energy": 1.0,
        "emotion": "neutral",
        "pause_factor": 1.0,
        "language": "zh-CN"
    }
    
    # 算法配置
    ALGORITHM: str = "HS256"
    
    class Config:
        env_file = ".env"

    def __init__(self, **data):
        super().__init__(**data)
        # 设置派生字段
        self.TTS_MODELS_DIR = os.path.join(self.MODELS_DIR, "tts")
        self.TTS_VOICE_ENCODER_PATH = os.path.join(self.MODELS_DIR, "voice_encoder/encoder.pt")
        self.TTS_METRICS_MODEL_PATH = os.path.join(self.MODELS_DIR, "metrics/mosnet.pt")

settings = Settings()

# 确保上传目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)