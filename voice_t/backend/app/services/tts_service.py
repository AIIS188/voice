import os
import json
import time
import asyncio
import numpy as np
import librosa
import soundfile as sf
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import BackgroundTasks
from app.models.tts import TTSTaskDB, TTSTaskStatus, TTSParams
from app.services.voice_service import get_voice_samples
from app.core.config import settings

# 模拟数据库存储
TTS_TASKS_DB = []
TTS_TASKS_FILE = os.path.join(settings.UPLOAD_DIR, "tts_tasks.json")

# 初始化函数，读取已有的任务记录
async def init_tts_service():
    global TTS_TASKS_DB
    if os.path.exists(TTS_TASKS_FILE):
        try:
            with open(TTS_TASKS_FILE, 'r') as f:
                data = json.load(f)
                TTS_TASKS_DB = [TTSTaskDB(**item) for item in data]
        except Exception as e:
            print(f"初始化TTS服务失败: {e}")

# 保存任务记录到文件
async def save_tts_tasks():
    with open(TTS_TASKS_FILE, 'w') as f:
        # 转换为字典列表并保存
        data = [task.dict() for task in TTS_TASKS_DB]
        json.dump(data, f, default=str)

# 创建语音合成任务
async def synthesize_speech(
    background_tasks: BackgroundTasks,
    text: str,
    voice_id: str,
    params: Dict[str, Any]
) -> str:
    # 验证声音样本是否存在
    voice_samples = await get_voice_samples(0, 1, None, voice_id)
    if not voice_samples:
        raise ValueError("声音样本不存在")
    
    # 创建任务记录
    task_id = f"tts_{int(time.time())}_{voice_id[:8]}"
    task = TTSTaskDB(
        task_id=task_id,
        text=text,
        voice_id=voice_id,
        params=params,
        status="pending",
        progress=0.0,
        created_at=datetime.now()
    )
    
    # 添加到"数据库"
    TTS_TASKS_DB.append(task)
    await save_tts_tasks()
    
    # 异步执行合成任务
    background_tasks.add_task(process_tts_task, task_id)
    
    return task_id

# 处理TTS任务
async def process_tts_task(task_id: str):
    # 查找任务
    task = None
    for t in TTS_TASKS_DB:
        if t.task_id == task_id:
            task = t
            break
    
    if not task:
        print(f"任务未找到: {task_id}")
        return
    
    try:
        # 更新状态为处理中
        task.status = "processing"
        task.progress = 0.1
        task.updated_at = datetime.now()
        await save_tts_tasks()
        
        # 获取声音样本信息
        voice_samples = await get_voice_samples(0, 1, None, task.voice_id)
        if not voice_samples:
            raise ValueError(f"声音样本不存在: {task.voice_id}")
        
        voice_sample = voice_samples[0]
        
        # 模拟TTS处理过程
        # 注意：这里使用简单的文本长度来模拟处理时间，实际项目中会使用真实的TTS模型
        
        is_preview = task.params.get("is_preview", False)
        process_time = 0.5 if is_preview else 2.0  # 预览模式更快
        
        # 更新进度
        task.progress = 0.3
        task.updated_at = datetime.now()
        await save_tts_tasks()
        
        await asyncio.sleep(process_time)  # 模拟处理时间
        
        # 文本处理（简单示例）
        text = task.text
        
        # 基于文本长度估算音频时长（简单示例）
        # 假设平均每个字符0.2秒
        estimated_duration = len(text) * 0.2
        
        # 应用语速参数
        speed = task.params.get("speed", 1.0)
        actual_duration = estimated_duration / speed
        
        # 创建输出目录
        output_dir = os.path.join(settings.UPLOAD_DIR, "tts_results")
        os.makedirs(output_dir, exist_ok=True)
        
        # 设置输出文件路径
        output_file = os.path.join(output_dir, f"{task_id}.wav")
        
        # 更新进度
        task.progress = 0.6
        task.updated_at = datetime.now()
        await save_tts_tasks()
        
        # 模拟合成过程
        await asyncio.sleep(process_time)  # 再次模拟处理时间
        
        # 生成示例音频（简单白噪声，仅做演示）
        sample_rate = 22050
        audio_length = int(actual_duration * sample_rate)
        
        # 创建白噪声，然后应用包络使其听起来像语音
        noise = np.random.uniform(-0.1, 0.1, audio_length)
        
        # 生成简单的振幅包络，模拟语音的起伏
        envelope = np.sin(np.linspace(0, 20 * np.pi, audio_length)) * 0.5 + 0.5
        envelope = envelope ** 0.5  # 使包络更加陡峭
        
        # 应用包络
        audio = noise * envelope
        
        # 应用音量参数
        energy = task.params.get("energy", 1.0)
        audio = audio * energy
        
        # 保存音频文件
        sf.write(output_file, audio, sample_rate)
        
        # 更新任务状态
        task.status = "completed"
        task.progress = 1.0
        task.updated_at = datetime.now()
        task.file_path = output_file
        task.duration = actual_duration
        await save_tts_tasks()
        
        print(f"TTS任务完成: {task_id}, 文件: {output_file}")
        
    except Exception as e:
        # 更新任务状态为失败
        for t in TTS_TASKS_DB:
            if t.task_id == task_id:
                t.status = "failed"
                t.error = str(e)
                t.updated_at = datetime.now()
                break
        
        await save_tts_tasks()
        print(f"TTS任务失败: {task_id}, 错误: {e}")

# 获取任务状态
async def get_tts_task_status(task_id: str) -> Optional[TTSTaskStatus]:
    for task in TTS_TASKS_DB:
        if task.task_id == task_id:
            message = None
            if task.status == "pending":
                message = "任务等待处理"
            elif task.status == "processing":
                message = "任务处理中"
            elif task.status == "completed":
                message = "任务已完成"
            elif task.status == "failed":
                message = "任务处理失败"
            
            return TTSTaskStatus(
                task_id=task.task_id,
                status=task.status,
                progress=task.progress,
                created_at=task.created_at,
                updated_at=task.updated_at,
                message=message,
                error=task.error,
                duration=task.duration
            )
    
    return None

# 获取任务结果
async def get_tts_task_result(task_id: str) -> Optional[TTSTaskStatus]:
    status = await get_tts_task_status(task_id)
    if status and status.status == "completed":
        # 找到对应任务获取文件路径
        for task in TTS_TASKS_DB:
            if task.task_id == task_id:
                if os.path.exists(task.file_path):
                    return status
    
    return None

# 初始化服务
asyncio.create_task(init_tts_service())