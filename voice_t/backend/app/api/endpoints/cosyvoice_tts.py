"""CosyVoice TTS API端点模块

这个模块提供了CosyVoice TTS服务的API端点，包括:
1. 合成语音
2. 流式合成
3. 获取任务状态
4. 下载合成结果
5. 获取可用音色
"""

from fastapi import APIRouter, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi import Depends, HTTPException, Query, Path, Body, File, UploadFile, Form
from fastapi.responses import FileResponse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.models.tts import TTSRequest, TTSResponse, TTSTaskStatus
from app.services.cosyvoice_tts import (
    synthesize_speech,
    synthesize_speech_streaming,
    get_tts_task_status,
    get_tts_task_result,
    cosyvoice_model
)
import tempfile
import os

router = APIRouter()

class CosyVoiceRequest(BaseModel):
    """CosyVoice TTS请求模型"""
    text: str = Field(..., min_length=1, description="要合成的文本")
    voice_id: Optional[str] = Field(None, description="预训练音色ID")
    prompt_text: Optional[str] = Field(None, description="参考音频对应的文本")
    instruct_text: Optional[str] = Field(None, description="指令文本")
    params: Dict[str, Any] = Field(default_factory=dict, description="合成参数")
    
    class Config:
        schema_extra = {
            "example": {
                "text": "欢迎使用CosyVoice语音合成系统",
                "voice_id": "speaker_0",
                "params": {
                    "mode": "sft",
                    "speed": 1.0,
                    "seed": 123456
                }
            }
        }

@router.post("/synthesize", response_model=TTSResponse)
async def create_tts_task(
    background_tasks: BackgroundTasks,
    request: CosyVoiceRequest = Body(...)
):
    """
    创建CosyVoice语音合成任务
    """
    # 验证文本长度
    if len(request.text) < 1:
        raise HTTPException(status_code=400, detail="文本不能为空")
    
    # 提交合成任务
    task_id = await synthesize_speech(
        background_tasks, 
        request.text, 
        request.voice_id, 
        request.params,
        prompt_text=request.prompt_text,
        instruct_text=request.instruct_text
    )
    
    return TTSResponse(
        task_id=task_id,
        status="pending",
        message="CosyVoice语音合成任务已提交"
    )

@router.post("/synthesize/upload", response_model=TTSResponse)
async def create_upload_tts_task(
    background_tasks: BackgroundTasks,
    text: str = Form(..., description="要合成的文本"),
    voice_id: Optional[str] = Form(None, description="预训练音色ID"),
    prompt_text: Optional[str] = Form(None, description="参考音频对应的文本"),
    instruct_text: Optional[str] = Form(None, description="指令文本"),
    mode: str = Form("sft", description="合成模式(sft/zero_shot/cross_lingual/instruct)"),
    speed: float = Form(1.0, description="语速"),
    prompt_audio: Optional[UploadFile] = File(None, description="参考音频文件")
):
    """
    上传文件并创建CosyVoice语音合成任务
    """
    # 验证文本长度
    if len(text) < 1:
        raise HTTPException(status_code=400, detail="文本不能为空")
    
    prompt_audio_path = None
    
    # 如果上传了参考音频，保存到临时文件
    if prompt_audio:
        try:
            # 创建临时文件保存上传的音频
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                prompt_audio_path = temp_file.name
                # 保存上传的音频
                with open(prompt_audio_path, "wb") as f:
                    f.write(await prompt_audio.read())
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"处理参考音频失败: {str(e)}")
    
    # 构建合成参数
    params = {
        "mode": mode,
        "speed": speed
    }
    
    # 提交合成任务
    task_id = await synthesize_speech(
        background_tasks, 
        text, 
        voice_id, 
        params,
        prompt_audio=prompt_audio_path,
        prompt_text=prompt_text,
        instruct_text=instruct_text
    )
    
    return TTSResponse(
        task_id=task_id,
        status="pending",
        message="CosyVoice语音合成任务已提交"
    )

@router.websocket("/synthesize/stream")
async def websocket_tts_stream(websocket: WebSocket):
    """
    通过WebSocket进行流式语音合成
    """
    await websocket.accept()
    
    try:
        # 从客户端接收请求参数
        request_data = await websocket.receive_json()
        
        # 验证必要参数
        if 'text' not in request_data:
            await websocket.send_json({"error": "缺少文本参数"})
            await websocket.close()
            return
        
        # 提取参数
        text = request_data['text']
        voice_id = request_data.get('voice_id')
        prompt_text = request_data.get('prompt_text')
        instruct_text = request_data.get('instruct_text')
        params = request_data.get('params', {})
        prompt_audio = request_data.get('prompt_audio')
        
        # 开始流式合成
        await synthesize_speech_streaming(
            websocket, 
            text, 
            voice_id, 
            params,
            prompt_audio,
            prompt_text,
            instruct_text
        )
        
    except WebSocketDisconnect:
        print("WebSocket连接已断开")
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
        except:
            pass
        finally:
            try:
                await websocket.close()
            except:
                pass

@router.get("/status/{task_id}", response_model=TTSTaskStatus)
async def check_task_status(
    task_id: str = Path(..., title="任务ID")
):
    """
    查询CosyVoice语音合成任务状态
    """
    status = await get_tts_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="任务未找到")
    
    return status

@router.get("/download/{task_id}")
async def download_tts_result(
    task_id: str = Path(..., title="任务ID")
):
    """
    下载CosyVoice语音合成结果
    """
    result = await get_tts_task_result(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="任务未找到或尚未完成")
    
    if result.status != "completed":
        raise HTTPException(status_code=400, detail=f"任务状态为 {result.status}，无法下载")
    
    return FileResponse(
        result.file_path,
        media_type="audio/wav",
        filename=f"cosyvoice_tts_{task_id}.wav"
    )

@router.get("/preview", response_model=TTSResponse)
async def preview_tts(
    background_tasks: BackgroundTasks,
    text: str = Query(..., description="要合成的文本"),
    voice_id: Optional[str] = Query(None, description="预训练音色ID"),
    mode: str = Query("sft", description="合成模式")
):
    """
    预览CosyVoice语音合成效果（处理短文本片段）
    """
    # 截取文本前200字
    preview_text = text[:200]
    
    # 创建预览任务
    params = {
        "mode": mode,
        "is_preview": True,
        "speed": 1.0
    }
    
    task_id = await synthesize_speech(
        background_tasks,
        preview_text,
        voice_id,
        params
    )
    
    return TTSResponse(
        task_id=task_id,
        status="pending",
        message="CosyVoice语音预览任务已提交"
    )

@router.get("/voices", response_model=List[str])
async def get_available_voices():
    """
    获取可用的预训练音色列表
    """
    if not cosyvoice_model:
        raise HTTPException(status_code=503, detail="CosyVoice服务不可用")
    
    voices = cosyvoice_model.get_available_voices()
    return voices