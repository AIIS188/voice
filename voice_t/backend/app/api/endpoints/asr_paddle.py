from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Path, Query
from fastapi.responses import FileResponse
from typing import List, Optional
from app.models.replace import VoiceReplaceResponse, VoiceReplaceStatus, SubtitleResponse

# Import the new PaddleSpeech ASR service
from app.services.paddlespeech_asr import (
    transcribe_media,
    get_transcription,
    get_subtitles
)

# Import necessary services from replace_service
from app.services.replace_service import (
    upload_media, 
    replace_voice,
    get_task_status,
    get_task_result
)

router = APIRouter()

@router.post("/upload", response_model=VoiceReplaceResponse)
async def upload_media_file(
    file: UploadFile = File(...),
    name: str = Form(...)
):
    """
    上传需要替换声音或转写的媒体文件
    """
    # 检查文件类型
    allowed_types = [
        "audio/mpeg", "audio/mp3", "audio/mp4", "audio/wav", 
        "video/mp4", "video/mpeg", "video/x-msvideo"
    ]
    
    content_type = file.content_type
    if content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="文件类型不支持，请上传MP3, WAV, MP4或AVI文件")
    
    # 上传媒体文件
    file_id = await upload_media(file, name)
    
    return VoiceReplaceResponse(
        file_id=file_id,
        name=name,
        status="uploaded",
        message="媒体文件上传成功"
    )

@router.post("/transcribe/{file_id}", response_model=VoiceReplaceResponse)
async def transcribe_media_file(
    background_tasks: BackgroundTasks,
    file_id: str = Path(..., title="媒体文件ID")
):
    """
    转写媒体文件内容（使用PaddleSpeech ASR）
    """
    task_id = await transcribe_media(background_tasks, file_id)
    
    return VoiceReplaceResponse(
        file_id=task_id,
        name="",  # 将在处理过程中更新
        status="processing",
        message="媒体转写任务已提交"
    )

@router.post("/process/{task_id}", response_model=VoiceReplaceResponse)
async def process_voice_replacement(
    background_tasks: BackgroundTasks,
    task_id: str = Path(..., title="转写任务ID"),
    voice_id: str = Form(..., title="声音样本ID"),
    speed: float = Form(1.0, ge=0.5, le=2.0, title="语速")
):
    """
    处理声音替换
    """
    replace_task_id = await replace_voice(background_tasks, task_id, voice_id, speed)
    
    return VoiceReplaceResponse(
        file_id=replace_task_id,
        name="",  # 将在处理过程中更新
        status="processing",
        message="声音替换任务已提交"
    )

@router.get("/status/{task_id}", response_model=VoiceReplaceStatus)
async def check_task_status(
    task_id: str = Path(..., title="任务ID")
):
    """
    查询任务状态
    """
    status = await get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="任务未找到")
    
    return status

@router.get("/subtitles/{task_id}", response_model=SubtitleResponse)
async def get_task_subtitles(
    task_id: str = Path(..., title="任务ID"),
    format: str = Query("srt", description="字幕格式: srt, vtt")
):
    """
    获取字幕
    """
    subtitles = await get_subtitles(task_id, format)
    if not subtitles:
        raise HTTPException(status_code=404, detail="任务未找到或尚未完成转写")
    
    return subtitles

@router.get("/download/{task_id}")
async def download_task_result(
    task_id: str = Path(..., title="任务ID")
):
    """
    下载处理后的媒体文件
    """
    result = await get_task_result(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="任务未找到或尚未完成")
    
    if result.status != "completed":
        raise HTTPException(status_code=400, detail=f"任务状态为 {result.status}，无法下载")
    
    return FileResponse(
        result.file_path,
        media_type="application/octet-stream",
        filename=result.output_filename
    )