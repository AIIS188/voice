from fastapi import APIRouter
from app.api.endpoints import voice, tts, course, replace

api_router = APIRouter()

api_router.include_router(voice.router, prefix="/voice", tags=["声音样本"])
api_router.include_router(tts.router, prefix="/tts", tags=["语音合成"])
api_router.include_router(course.router, prefix="/course", tags=["课件处理"])
api_router.include_router(replace.router, prefix="/replace", tags=["声音置换"])