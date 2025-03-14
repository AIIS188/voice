from fastapi import APIRouter
from app.api.endpoints import voice, course, replace

# Import new PaddleSpeech-based endpoints
from app.api.endpoints import tts_paddle, asr_paddle

api_router = APIRouter()

# 声音样本管理
api_router.include_router(voice.router, prefix="/voice", tags=["声音样本"])

# 使用PaddleSpeech TTS服务
api_router.include_router(tts_paddle.router, prefix="/tts", tags=["语音合成"])

# 课件处理
api_router.include_router(course.router, prefix="/course", tags=["课件处理"])

# 使用PaddleSpeech ASR服务
api_router.include_router(asr_paddle.router, prefix="/replace", tags=["声音置换与字幕"])