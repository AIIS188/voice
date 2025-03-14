"""更新 API 端点以使用我们的新 PaddleSpeech 服务"""




from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Path, Body, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from typing import Optional, List
from app.models.tts import TTSRequest, TTSResponse, TTSTaskStatus

# Import the new PaddleSpeech TTS service
from app.services.paddlespeech_tts import (
    synthesize_speech, 
    synthesize_speech_streaming,
    get_tts_task_status, 
    get_tts_task_result
)

router = APIRouter()

@router.post("/synthesize", response_model=TTSResponse)
async def create_tts_task(
    background_tasks: BackgroundTasks,
    request: TTSRequest = Body(...)
):
    """
    创建文本转语音任务
    """
    # 验证文本长度
    if len(request.text) < 10:
        raise HTTPException(status_code=400, detail="文本太短，至少需要10个字符")
    
    if len(request.text) > 2000:
        raise HTTPException(status_code=400, detail="文本太长，最多支持2000个字符")
    
    # 提交合成任务
    task_id = await synthesize_speech(
        background_tasks, 
        request.text, 
        request.voice_id, 
        request.params.dict()
    )
    
    return TTSResponse(
        task_id=task_id,
        status="pending",
        message="语音合成任务已提交"
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
            
        if 'voice_id' not in request_data:
            await websocket.send_json({"error": "缺少声音ID参数"})
            await websocket.close()
            return
        
        # 提取参数
        text = request_data['text']
        voice_id = request_data['voice_id']
        params = request_data.get('params', {})
        
        # 开始流式合成
        await synthesize_speech_streaming(websocket, text, voice_id, params)
        
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
    查询语音合成任务状态
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
    下载语音合成结果
    """
    result = await get_tts_task_result(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="任务未找到或尚未完成")
    
    if result.status != "completed":
        raise HTTPException(status_code=400, detail=f"任务状态为 {result.status}，无法下载")
    
    return FileResponse(
        result.file_path,
        media_type="audio/wav",
        filename=f"tts_{task_id}.wav"
    )

@router.post("/preview", response_model=TTSResponse)
async def preview_tts(
    background_tasks: BackgroundTasks,
    request: TTSRequest = Body(...)
):
    """
    预览语音合成效果（处理短文本片段）
    """
    # 截取文本前30秒左右的内容（约200字）
    preview_text = request.text[:200]
    
    # 创建预览任务
    params = request.params.dict()
    params["is_preview"] = True
    
    task_id = await synthesize_speech(
        background_tasks,
        preview_text,
        request.voice_id,
        params
    )
    
    return TTSResponse(
        task_id=task_id,
        status="pending",
        message="语音预览任务已提交"
    )