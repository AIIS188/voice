import os
import json
import asyncio
import time
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import UploadFile, BackgroundTasks
from app.models.replace import MediaFileDB, TranscriptionTaskDB, ReplaceTaskDB, Transcription, Segment, VoiceReplaceStatus, SubtitleResponse
from app.core.config import settings

# 模拟数据库存储
MEDIA_FILES_DB = []
TRANSCRIPTION_TASKS_DB = []
REPLACE_TASKS_DB = []
MEDIA_FILES_FILE = os.path.join(settings.UPLOAD_DIR, "media_files.json")
TRANSCRIPTION_TASKS_FILE = os.path.join(settings.UPLOAD_DIR, "transcription_tasks.json")
REPLACE_TASKS_FILE = os.path.join(settings.UPLOAD_DIR, "replace_tasks.json")

# 初始化函数
async def init_replace_service():
    global MEDIA_FILES_DB, TRANSCRIPTION_TASKS_DB, REPLACE_TASKS_DB
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "media"), exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "transcriptions"), exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "replaced_media"), exist_ok=True)
    
    if os.path.exists(MEDIA_FILES_FILE):
        try:
            with open(MEDIA_FILES_FILE, 'r') as f:
                data = json.load(f)
                MEDIA_FILES_DB = [MediaFileDB(**item) for item in data]
        except Exception as e:
            print(f"初始化媒体文件服务失败: {e}")
    
    if os.path.exists(TRANSCRIPTION_TASKS_FILE):
        try:
            with open(TRANSCRIPTION_TASKS_FILE, 'r') as f:
                data = json.load(f)
                TRANSCRIPTION_TASKS_DB = [TranscriptionTaskDB(**item) for item in data]
        except Exception as e:
            print(f"初始化转写任务服务失败: {e}")
    
    if os.path.exists(REPLACE_TASKS_FILE):
        try:
            with open(REPLACE_TASKS_FILE, 'r') as f:
                data = json.load(f)
                REPLACE_TASKS_DB = [ReplaceTaskDB(**item) for item in data]
        except Exception as e:
            print(f"初始化替换任务服务失败: {e}")

# 保存到文件
async def save_media_files_db():
    with open(MEDIA_FILES_FILE, 'w') as f:
        data = [item.dict() for item in MEDIA_FILES_DB]
        json.dump(data, f, default=str)

async def save_transcription_tasks_db():
    with open(TRANSCRIPTION_TASKS_FILE, 'w') as f:
        data = [item.dict() for item in TRANSCRIPTION_TASKS_DB]
        json.dump(data, f, default=str)

async def save_replace_tasks_db():
    with open(REPLACE_TASKS_FILE, 'w') as f:
        data = [item.dict() for item in REPLACE_TASKS_DB]
        json.dump(data, f, default=str)

# 上传媒体文件
async def upload_media(file: UploadFile, name: str) -> str:
    # 生成唯一文件ID
    file_id = f"media_{int(time.time())}_{hash(file.filename) % 10000:04d}"
    
    # 创建存储目录
    media_dir = os.path.join(settings.UPLOAD_DIR, "media")
    os.makedirs(media_dir, exist_ok=True)
    
    # 保存文件
    file_path = os.path.join(media_dir, f"{file_id}_{file.filename}")
    
    # 获取文件大小
    file.file.seek(0, 2)  # 移到文件末尾
    file_size = file.file.tell()  # 获取位置（即文件大小）
    file.file.seek(0)  # 回到文件开始
    
    # 写入文件
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 判断是否为视频文件
    is_video = file.content_type.startswith("video/")
    
    # 创建记录
    media_file = MediaFileDB(
        file_id=file_id,
        name=name,
        original_filename=file.filename,
        file_path=file_path,
        content_type=file.content_type,
        file_size=file_size,
        is_video=is_video,
        created_at=datetime.now()
    )
    
    # 添加到"数据库"
    MEDIA_FILES_DB.append(media_file)
    await save_media_files_db()
    
    return file_id

# 转写媒体文件
async def transcribe_media(background_tasks: BackgroundTasks, file_id: str) -> str:
    # 查找媒体文件
    media_file = None
    for mf in MEDIA_FILES_DB:
        if mf.file_id == file_id:
            media_file = mf
            break
    
    if not media_file:
        raise ValueError("媒体文件未找到")
    
    # 创建转写任务
    task_id = f"transcribe_{int(time.time())}_{file_id[-6:]}"
    task = TranscriptionTaskDB(
        task_id=task_id,
        file_id=file_id,
        name=media_file.name,
        status="processing",
        progress=0.0,
        created_at=datetime.now()
    )
    
    # 添加到"数据库"
    TRANSCRIPTION_TASKS_DB.append(task)
    await save_transcription_tasks_db()
    
    # 异步处理任务
    background_tasks.add_task(process_transcription_task, task_id)
    
    return task_id

# 处理转写任务
async def process_transcription_task(task_id: str):
    # 查找任务
    task = None
    for t in TRANSCRIPTION_TASKS_DB:
        if t.task_id == task_id:
            task = t
            break
    
    if not task:
        print(f"任务未找到: {task_id}")
        return
    
    try:
        # 查找媒体文件
        media_file = None
        for mf in MEDIA_FILES_DB:
            if mf.file_id == task.file_id:
                media_file = mf
                break
        
        if not media_file:
            raise ValueError(f"媒体文件未找到: {task.file_id}")
        
        # 更新状态
        for i, t in enumerate(TRANSCRIPTION_TASKS_DB):
            if t.task_id == task_id:
                TRANSCRIPTION_TASKS_DB[i].status = "processing"
                TRANSCRIPTION_TASKS_DB[i].progress = 0.1
                TRANSCRIPTION_TASKS_DB[i].updated_at = datetime.now()
                break
        
        await save_transcription_tasks_db()
        
        # 创建输出目录
        output_dir = os.path.join(settings.UPLOAD_DIR, "transcriptions")
        os.makedirs(output_dir, exist_ok=True)
        
        # 模拟转写过程
        # 注意：实际项目中会使用Whisper等模型进行语音识别
        
        # 假设一个模拟的转写时间（基于文件大小）
        process_time = min(3.0, media_file.file_size / (5 * 1024 * 1024))
        
        # 更新进度
        for i, t in enumerate(TRANSCRIPTION_TASKS_DB):
            if t.task_id == task_id:
                TRANSCRIPTION_TASKS_DB[i].progress = 0.3
                TRANSCRIPTION_TASKS_DB[i].updated_at = datetime.now()
                break
        
        await save_transcription_tasks_db()
        
        # 模拟处理时间
        await asyncio.sleep(process_time)
        
        # 模拟转写结果
        # 假设媒体时长是文件大小的一个函数（仅用于演示）
        duration = media_file.file_size / (500 * 1024)  # 假设每500KB约1秒
        
        # 更新媒体文件的时长
        for i, mf in enumerate(MEDIA_FILES_DB):
            if mf.file_id == media_file.file_id:
                MEDIA_FILES_DB[i].duration = duration
                MEDIA_FILES_DB[i].updated_at = datetime.now()
                break
        
        await save_media_files_db()
        
        # 生成模拟的转写段落
        segments = []
        segment_count = max(3, int(duration / 10))  # 每10秒一个段落，至少3个段落
        
        segment_duration = duration / segment_count
        for i in range(segment_count):
            start_time = i * segment_duration
            end_time = (i + 1) * segment_duration
            
            # 生成示例文本
            if i == 0:
                text = f"这是{media_file.name}的开头部分，我们在介绍主要内容。"
            elif i == segment_count - 1:
                text = f"这是{media_file.name}的结尾部分，总结了主要观点。"
            else:
                text = f"这是第{i+1}个内容段落，包含了重要的信息和观点解析。"
            
            segments.append(Segment(
                start=start_time,
                end=end_time,
                text=text
            ))
        
        # 创建转写对象
        transcription = Transcription(
            segments=segments,
            language="zh-CN",
            total_duration=duration
        )
        
        # 生成SRT字幕文件
        srt_path = os.path.join(output_dir, f"{task_id}.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments):
                f.write(f"{i+1}\n")
                
                # 格式化时间码 (HH:MM:SS,mmm)
                start_h = int(segment.start / 3600)
                start_m = int((segment.start % 3600) / 60)
                start_s = int(segment.start % 60)
                start_ms = int((segment.start % 1) * 1000)
                
                end_h = int(segment.end / 3600)
                end_m = int((segment.end % 3600) / 60)
                end_s = int(segment.end % 60)
                end_ms = int((segment.end % 1) * 1000)
                
                time_str = f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms:03d} --> "
                time_str += f"{end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms:03d}"
                
                f.write(f"{time_str}\n")
                f.write(f"{segment.text}\n\n")
        
        # 生成VTT字幕文件
        vtt_path = os.path.join(output_dir, f"{task_id}.vtt")
        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            
            for i, segment in enumerate(segments):
                # 格式化时间码 (HH:MM:SS.mmm)
                start_h = int(segment.start / 3600)
                start_m = int((segment.start % 3600) / 60)
                start_s = int(segment.start % 60)
                start_ms = int((segment.start % 1) * 1000)
                
                end_h = int(segment.end / 3600)
                end_m = int((segment.end % 3600) / 60)
                end_s = int(segment.end % 60)
                end_ms = int((segment.end % 1) * 1000)
                
                time_str = f"{start_h:02d}:{start_m:02d}:{start_s:02d}.{start_ms:03d} --> "
                time_str += f"{end_h:02d}:{end_m:02d}:{end_s:02d}.{end_ms:03d}"
                
                f.write(f"{time_str}\n")
                f.write(f"{segment.text}\n\n")
        
        # 更新任务状态
        for i, t in enumerate(TRANSCRIPTION_TASKS_DB):
            if t.task_id == task_id:
                TRANSCRIPTION_TASKS_DB[i].status = "completed"
                TRANSCRIPTION_TASKS_DB[i].progress = 1.0
                TRANSCRIPTION_TASKS_DB[i].updated_at = datetime.now()
                TRANSCRIPTION_TASKS_DB[i].transcription = transcription
                TRANSCRIPTION_TASKS_DB[i].subtitles_path = {
                    "srt": srt_path,
                    "vtt": vtt_path
                }
                break
        
        await save_transcription_tasks_db()
        print(f"转写任务完成: {task_id}")
        
    except Exception as e:
        # 更新任务状态为失败
        for i, t in enumerate(TRANSCRIPTION_TASKS_DB):
            if t.task_id == task_id:
                TRANSCRIPTION_TASKS_DB[i].status = "failed"
                TRANSCRIPTION_TASKS_DB[i].error = str(e)
                TRANSCRIPTION_TASKS_DB[i].updated_at = datetime.now()
                break
        
        await save_transcription_tasks_db()
        print(f"转写任务失败: {task_id}, 错误: {e}")

# 替换声音
async def replace_voice(
    background_tasks: BackgroundTasks,
    transcription_task_id: str,
    voice_id: str,
    speed: float = 1.0
) -> str:
    # 查找转写任务
    transcription_task = None
    for tt in TRANSCRIPTION_TASKS_DB:
        if tt.task_id == transcription_task_id:
            transcription_task = tt
            break
    
    if not transcription_task:
        raise ValueError("转写任务未找到")
    
    if transcription_task.status != "completed":
        raise ValueError(f"转写任务状态 {transcription_task.status} 不是 completed")
    
    # 创建替换任务
    task_id = f"replace_{int(time.time())}_{transcription_task_id[-6:]}"
    task = ReplaceTaskDB(
        task_id=task_id,
        transcription_task_id=transcription_task_id,
        name=transcription_task.name,
        voice_id=voice_id,
        params={"speed": speed},
        status="processing",
        progress=0.0,
        created_at=datetime.now()
    )
    
    # 添加到"数据库"
    REPLACE_TASKS_DB.append(task)
    await save_replace_tasks_db()
    
    # 异步处理任务
    background_tasks.add_task(process_replace_task, task_id)
    
    return task_id

# 处理替换任务
async def process_replace_task(task_id: str):
    # 查找任务
    task = None
    for t in REPLACE_TASKS_DB:
        if t.task_id == task_id:
            task = t
            break
    
    if not task:
        print(f"任务未找到: {task_id}")
        return
    
    try:
        # 查找转写任务
        transcription_task = None
        for tt in TRANSCRIPTION_TASKS_DB:
            if tt.task_id == task.transcription_task_id:
                transcription_task = tt
                break
        
        if not transcription_task:
            raise ValueError(f"转写任务未找到: {task.transcription_task_id}")
        
        # 查找媒体文件
        media_file = None
        for mf in MEDIA_FILES_DB:
            if mf.file_id == transcription_task.file_id:
                media_file = mf
                break
        
        if not media_file:
            raise ValueError(f"媒体文件未找到: {transcription_task.file_id}")
        
        # 更新状态
        for i, t in enumerate(REPLACE_TASKS_DB):
            if t.task_id == task_id:
                REPLACE_TASKS_DB[i].status = "processing"
                REPLACE_TASKS_DB[i].progress = 0.1
                REPLACE_TASKS_DB[i].updated_at = datetime.now()
                break
        
        await save_replace_tasks_db()
        
        # 创建输出目录
        output_dir = os.path.join(settings.UPLOAD_DIR, "replaced_media")
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成输出文件名
        file_ext = Path(media_file.original_filename).suffix.lower()
        output_filename = f"替换后_{media_file.name}{file_ext}"
        output_path = os.path.join(output_dir, f"{task_id}_{output_filename}")
        
        # 更新任务输出文件名
        for i, t in enumerate(REPLACE_TASKS_DB):
            if t.task_id == task_id:
                REPLACE_TASKS_DB[i].output_filename = output_filename
                break
        
        await save_replace_tasks_db()
        
        # 模拟声音替换过程
        # 注意：实际项目中会使用TTS生成新的语音，然后使用FFmpeg替换原始音频
        
        # 假设处理时间与媒体时长相关
        if not media_file.duration:
            duration = media_file.file_size / (500 * 1024)  # 假设每500KB约1秒
        else:
            duration = media_file.duration
        
        process_time = min(5.0, duration / 30)  # 最长5秒模拟处理时间
        
        # 更新进度
        for i, t in enumerate(REPLACE_TASKS_DB):
            if t.task_id == task_id:
                REPLACE_TASKS_DB[i].progress = 0.3
                REPLACE_TASKS_DB[i].updated_at = datetime.now()
                break
        
        await save_replace_tasks_db()
        
        # 模拟处理时间
        await asyncio.sleep(process_time)
        
        # 更新进度
        for i, t in enumerate(REPLACE_TASKS_DB):
            if t.task_id == task_id:
                REPLACE_TASKS_DB[i].progress = 0.6
                REPLACE_TASKS_DB[i].updated_at = datetime.now()
                break
        
        await save_replace_tasks_db()
        
        # 再次模拟处理时间
        await asyncio.sleep(process_time)
        
        # 模拟创建替换后的媒体文件（为简化，这里只是复制原始文件）
        shutil.copy2(media_file.file_path, output_path)
        
        # 更新任务完成状态
        for i, t in enumerate(REPLACE_TASKS_DB):
            if t.task_id == task_id:
                REPLACE_TASKS_DB[i].status = "completed"
                REPLACE_TASKS_DB[i].progress = 1.0
                REPLACE_TASKS_DB[i].updated_at = datetime.now()
                REPLACE_TASKS_DB[i].file_path = output_path
                break
        
        await save_replace_tasks_db()
        print(f"替换任务完成: {task_id}, 文件: {output_path}")
        
    except Exception as e:
        # 更新任务状态为失败
        for i, t in enumerate(REPLACE_TASKS_DB):
            if t.task_id == task_id:
                REPLACE_TASKS_DB[i].status = "failed"
                REPLACE_TASKS_DB[i].error = str(e)
                REPLACE_TASKS_DB[i].updated_at = datetime.now()
                break
        
        await save_replace_tasks_db()
        print(f"替换任务失败: {task_id}, 错误: {e}")

# 获取任务状态
async def get_task_status(task_id: str) -> Optional[VoiceReplaceStatus]:
    # 尝试查找转写任务
    for task in TRANSCRIPTION_TASKS_DB:
        if task.task_id == task_id:
            # 查找对应的媒体文件获取时长
            original_duration = None
            for mf in MEDIA_FILES_DB:
                if mf.file_id == task.file_id:
                    original_duration = mf.duration
                    break
            
            return VoiceReplaceStatus(
                task_id=task.task_id,
                name=task.name,
                status=task.status,
                task_type="transcribe",
                progress=task.progress,
                created_at=task.created_at,
                updated_at=task.updated_at,
                original_duration=original_duration,
                error=task.error
            )
    
    # 尝试查找替换任务
    for task in REPLACE_TASKS_DB:
        if task.task_id == task_id:
            return VoiceReplaceStatus(
                task_id=task.task_id,
                name=task.name,
                status=task.status,
                task_type="replace",
                progress=task.progress,
                created_at=task.created_at,
                updated_at=task.updated_at,
                output_filename=task.output_filename,
                error=task.error
            )
    
    return None

# 获取字幕
async def get_subtitles(task_id: str, format: str = "srt") -> Optional[SubtitleResponse]:
    # 查找转写任务
    for task in TRANSCRIPTION_TASKS_DB:
        if task.task_id == task_id and task.status == "completed" and task.subtitles_path:
            if format in task.subtitles_path and os.path.exists(task.subtitles_path[format]):
                with open(task.subtitles_path[format], "r", encoding="utf-8") as f:
                    content = f.read()
                
                return SubtitleResponse(
                    task_id=task.task_id,
                    content=content,
                    format=format,
                    language=task.transcription.language if task.transcription else "zh-CN",
                    segments_count=len(task.transcription.segments) if task.transcription else 0
                )
    
    return None

# 获取任务结果
async def get_task_result(task_id: str) -> Optional[VoiceReplaceStatus]:
    status = await get_task_status(task_id)
    if status and status.status == "completed" and status.task_type == "replace":
        # 找到对应任务获取文件路径
        for task in REPLACE_TASKS_DB:
            if task.task_id == task_id:
                if os.path.exists(task.file_path):
                    return status
    
    return None

# 初始化服务
asyncio.create_task(init_replace_service())