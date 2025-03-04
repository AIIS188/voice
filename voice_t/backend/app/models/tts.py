from pydantic import BaseModel, Field
from typing import Dict, Optional, Any, List
from datetime import datetime
import uuid

class TTSParams(BaseModel):
    speed: float = Field(1.0, ge=0.5, le=2.0, description="语速，范围0.5-2.0")
    pitch: float = Field(0.0, ge=-1.0, le=1.0, description="音调，范围-1.0-1.0")
    energy: float = Field(1.0, ge=0.5, le=2.0, description="音量能量，范围0.5-2.0")
    emotion: str = Field("neutral", description="情感风格：neutral, happy, sad, serious")
    pause_factor: float = Field(1.0, ge=0.5, le=2.0, description="停顿因子，范围0.5-2.0")
    is_preview: bool = Field(False, description="是否为预览模式")

class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000, description="要合成的文本内容")
    voice_id: str = Field(..., description="声音样本ID")
    params: TTSParams = Field(default_factory=TTSParams, description="合成参数")
    
    class Config:
        schema_extra = {
            "example": {
                "text": "欢迎使用声教助手，这是一段示例文本，用于演示语音合成功能。",
                "voice_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "params": {
                    "speed": 1.0,
                    "pitch": 0.0,
                    "energy": 1.0,
                    "emotion": "neutral",
                    "pause_factor": 1.0
                }
            }
        }

class TTSResponse(BaseModel):
    task_id: str
    status: str  # pending, processing, completed, failed
    message: Optional[str] = None
    error: Optional[str] = None

class TTSTaskStatus(BaseModel):
    task_id: str
    status: str  # pending, processing, completed, failed
    progress: float = Field(0.0, ge=0.0, le=1.0)
    created_at: datetime
    updated_at: Optional[datetime] = None
    message: Optional[str] = None
    error: Optional[str] = None
    duration: Optional[float] = None  # 合成音频的时长（秒）

class TTSTaskDB(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    voice_id: str
    params: Dict[str, Any]
    status: str = "pending"  # pending, processing, completed, failed
    progress: float = 0.0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    file_path: Optional[str] = None
    error: Optional[str] = None
    duration: Optional[float] = None