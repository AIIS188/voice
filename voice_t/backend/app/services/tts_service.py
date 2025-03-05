import os
import json
import time
import asyncio
import numpy as np
import librosa
import soundfile as sf
from scipy.ndimage import gaussian_filter1d
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
    # 确保目录存在
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "tts_results"), exist_ok=True)
    
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

# 生成更真实的语音音频
def generate_speech_audio(text, params, sample_rate=22050):
    """
    生成更逼真的语音音频，基于文本内容和参数。
    这仍然是一个模拟，但比白噪声更接近真实语音。
    """
    # 根据文本长度和语速计算时长
    words = len(text.split())
    chars = len(text)
    
    # 平均语速：~150字/分钟
    # 根据speed参数调整
    speed = params.get("speed", 1.0)
    chars_per_second = (5 * speed)  # 中文大约每秒5个字
    
    # 估计时长（添加一些填充）
    base_duration = (chars / chars_per_second) + 1.0
    duration = max(1.0, base_duration)  # 确保至少1秒
    
    # 创建时间数组
    t = np.linspace(0, duration, int(duration * sample_rate))
    
    # 基本载波频率（基频 - 模拟音高）
    pitch_param = params.get("pitch", 0)  # -1 到 1
    # 男声~120Hz，女声~220Hz，根据pitch参数调整
    base_freq = 170 * (2 ** (pitch_param * 0.5))
    
    # 创建载波（模拟声带振动）
    carrier = np.sin(2 * np.pi * base_freq * t)
    
    # 添加谐波以增加丰富度
    harmonics = 0
    for i in range(2, 6):
        harmonics += (1/i) * np.sin(2 * np.pi * (base_freq * i) * t)
    
    carrier = 0.7 * carrier + 0.3 * harmonics
    
    # 创建语音包络（振幅调制）
    # 将文本分解为模拟音节
    syllables = max(1, chars)  # 中文每个字符视为一个音节
    
    # 创建带有音节变化的包络
    envelope = np.ones_like(t) * 0.1  # 背景电平
    
    # 计算停顿因子影响下的音节间距
    pause_factor = params.get("pause_factor", 1.0)
    syllable_spacing = duration * 0.8 / syllables * pause_factor
    syllable_positions = np.linspace(0, duration * 0.8, syllables)
    syllable_width = 0.15  # 每个音节的宽度（秒）
    
    for pos in syllable_positions:
        # 为每个音节创建一个峰值
        idx = (t >= pos) & (t <= pos + syllable_width)
        if np.any(idx):
            envelope[idx] = 0.5 + 0.5 * np.sin(np.pi * (t[idx] - pos) / syllable_width)
    
    # 平滑包络
    envelope = gaussian_filter1d(envelope, sigma=0.01 * sample_rate)
    
    # 应用情感风格
    emotion = params.get("emotion", "neutral")
    if emotion == "happy":
        # 增加音高变化，更快的节奏
        modulation = 0.1 * np.sin(2 * np.pi * 3 * t / duration)
        carrier = carrier + modulation
        envelope = np.power(envelope, 0.9)  # 更尖锐的包络
    elif emotion == "sad":
        # 降低音高，更慢的节奏
        modulation = 0.05 * np.sin(2 * np.pi * 1 * t / duration)
        carrier = carrier - modulation
        envelope = np.power(envelope, 1.2)  # 更圆滑的包络
    elif emotion == "serious":
        # 稳定的音高，清晰的发音
        envelope = np.power(envelope, 1.1)
        envelope = np.clip(envelope, 0, 0.9)  # 限制最大音量
    
    # 将包络应用于载波
    audio = carrier * envelope
    
    # 应用能量/音量
    energy = params.get("energy", 1.0)
    audio = audio * energy
    
    # 添加少量白噪声模拟辅音
    noise = np.random.uniform(-0.05, 0.05, len(audio))
    audio = audio + noise * envelope * 0.3
    
    # 添加一些语音特有的变化
    # 1. 添加微小的振幅变化
    tremolo = 1.0 + 0.03 * np.sin(2 * np.pi * 5 * t)
    audio = audio * tremolo
    
    # 2. 语音开始和结束的淡入淡出
    fade_len = int(0.05 * sample_rate)
    if len(audio) > 2 * fade_len:
        fade_in = np.linspace(0, 1, fade_len)
        fade_out = np.linspace(1, 0, fade_len)
        audio[:fade_len] = audio[:fade_len] * fade_in
        audio[-fade_len:] = audio[-fade_len:] * fade_out
    
    # 归一化
    max_amp = np.max(np.abs(audio))
    if max_amp > 0:
        audio = audio / max_amp * 0.9
    
    return audio, duration

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
        
        # 检查是否为预览模式
        is_preview = task.params.get("is_preview", False)
        
        # 文本预处理（分段、清理等）
        text = task.text
        
        # 更新进度
        task.progress = 0.3
        task.updated_at = datetime.now()
        await save_tts_tasks()
        
        # 预览模式处理更快
        if is_preview:
            await asyncio.sleep(0.5)
        else:
            await asyncio.sleep(1.0)
        
        # 基于声音样本特征和参数生成音频
        sample_rate = 22050  # 标准采样率
        audio, duration = generate_speech_audio(text, task.params, sample_rate)
        
        # 更新进度
        task.progress = 0.7
        task.updated_at = datetime.now()
        await save_tts_tasks()
        
        # 创建输出目录
        output_dir = os.path.join(settings.UPLOAD_DIR, "tts_results")
        os.makedirs(output_dir, exist_ok=True)
        
        # 设置输出文件路径
        output_file = os.path.join(output_dir, f"{task_id}.wav")
        
        # 保存音频文件
        sf.write(output_file, audio, sample_rate)
        
        # 预览模式更快完成
        if is_preview:
            await asyncio.sleep(0.3)
        else:
            await asyncio.sleep(0.7)
        
        # 更新任务状态
        task.status = "completed"
        task.progress = 1.0
        task.updated_at = datetime.now()
        task.file_path = output_file
        task.duration = duration
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