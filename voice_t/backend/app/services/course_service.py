import os
import json
import asyncio
import time
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import UploadFile, BackgroundTasks
from app.models.course import CoursewareDB, CoursewareTaskDB, CoursewareTextExtraction, CoursewareTaskStatus, SlideContent
from app.services.tts_service import synthesize_speech, get_tts_task_status
from app.core.config import settings

# 模拟数据库存储
COURSEWARE_DB = []
COURSEWARE_TASKS_DB = []
COURSEWARE_FILE = os.path.join(settings.UPLOAD_DIR, "courseware.json")
COURSEWARE_TASKS_FILE = os.path.join(settings.UPLOAD_DIR, "courseware_tasks.json")

# 初始化函数
async def init_course_service():
    global COURSEWARE_DB, COURSEWARE_TASKS_DB
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "courseware"), exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "voiced_courseware"), exist_ok=True)
    
    if os.path.exists(COURSEWARE_FILE):
        try:
            with open(COURSEWARE_FILE, 'r') as f:
                data = json.load(f)
                COURSEWARE_DB = [CoursewareDB(**item) for item in data]
        except Exception as e:
            print(f"初始化课件服务失败: {e}")
    
    if os.path.exists(COURSEWARE_TASKS_FILE):
        try:
            with open(COURSEWARE_TASKS_FILE, 'r') as f:
                data = json.load(f)
                COURSEWARE_TASKS_DB = [CoursewareTaskDB(**item) for item in data]
        except Exception as e:
            print(f"初始化课件任务服务失败: {e}")

# 保存到文件
async def save_courseware_db():
    with open(COURSEWARE_FILE, 'w') as f:
        data = [item.dict() for item in COURSEWARE_DB]
        json.dump(data, f, default=str)

async def save_courseware_tasks_db():
    with open(COURSEWARE_TASKS_FILE, 'w') as f:
        data = [item.dict() for item in COURSEWARE_TASKS_DB]
        json.dump(data, f, default=str)

# 上传课件
async def upload_courseware(file: UploadFile, name: str) -> str:
    # 生成唯一文件ID
    file_id = f"course_{int(time.time())}_{hash(file.filename) % 10000:04d}"
    
    # 创建存储目录
    courseware_dir = os.path.join(settings.UPLOAD_DIR, "courseware")
    os.makedirs(courseware_dir, exist_ok=True)
    
    # 保存文件
    file_path = os.path.join(courseware_dir, f"{file_id}_{file.filename}")
    
    # 获取文件大小
    file.file.seek(0, 2)  # 移到文件末尾
    file_size = file.file.tell()  # 获取位置（即文件大小）
    file.file.seek(0)  # 回到文件开始
    
    # 写入文件
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 创建记录
    courseware = CoursewareDB(
        file_id=file_id,
        name=name,
        original_filename=file.filename,
        file_path=file_path,
        content_type=file.content_type,
        file_size=file_size,
        created_at=datetime.now()
    )
    
    # 添加到"数据库"
    COURSEWARE_DB.append(courseware)
    await save_courseware_db()
    
    return file_id

# 提取课件文本
async def extract_text(file_id: str) -> Optional[CoursewareTextExtraction]:
    # 查找课件
    courseware = None
    for cw in COURSEWARE_DB:
        if cw.file_id == file_id:
            courseware = cw
            break
    
    if not courseware:
        return None
    
    # 如果已经提取过文本，直接返回
    if courseware.slides_count > 0 and courseware.extracted_text:
        return CoursewareTextExtraction(
            file_id=courseware.file_id,
            name=courseware.name,
            slides_count=courseware.slides_count,
            extracted_text=courseware.extracted_text,
            total_text_length=sum(len(slide.content) for slide in courseware.extracted_text)
        )
    
    # 模拟提取文本
    # 注意：实际项目中会使用python-pptx等库解析PPT文件
    
    # 根据文件类型生成模拟数据
    file_ext = Path(courseware.original_filename).suffix.lower()
    slides_count = 10  # 假设有10页
    
    extracted_text = []
    for i in range(1, slides_count + 1):
        # 生成模拟的幻灯片内容
        if i == 1:
            title = "课程介绍"
            content = f"欢迎学习使用{courseware.name}课程。本课程将介绍主要内容和学习目标。"
            notes = "介绍课程大纲和教学目标，引起学生兴趣。"
        elif i == slides_count:
            title = "总结与回顾"
            content = "通过本课程的学习，我们掌握了重要的知识点和技能。希望大家在实践中能够灵活应用。"
            notes = "总结关键点，强调学以致用。"
        else:
            title = f"第{i-1}章：知识点{i-1}"
            content = f"这是第{i}页幻灯片的内容。它包含了本章的核心知识点和例子。\n\n" + \
                     f"要点{i}.1: 这是第一个要点的详细解释，包括概念和应用场景。\n" + \
                     f"要点{i}.2: 这是第二个要点，我们需要重点掌握这部分内容。"
            notes = f"讲解要点{i}.1和{i}.2的联系，可以举例说明实际应用。" if i % 2 == 0 else None
        
        extracted_text.append(SlideContent(
            slide_id=i,
            title=title,
            content=content,
            notes=notes
        ))
    
    # 更新课件记录
    for i, cw in enumerate(COURSEWARE_DB):
        if cw.file_id == file_id:
            COURSEWARE_DB[i].slides_count = slides_count
            COURSEWARE_DB[i].extracted_text = extracted_text
            COURSEWARE_DB[i].updated_at = datetime.now()
            break
    
    await save_courseware_db()
    
    return CoursewareTextExtraction(
        file_id=courseware.file_id,
        name=courseware.name,
        slides_count=slides_count,
        extracted_text=extracted_text,
        total_text_length=sum(len(slide.content) for slide in extracted_text)
    )

# 生成有声课件
async def generate_voiced_courseware(
    background_tasks: BackgroundTasks,
    file_id: str,
    voice_id: str,
    speed: float = 1.0
) -> str:
    # 查找课件
    courseware = None
    for cw in COURSEWARE_DB:
        if cw.file_id == file_id:
            courseware = cw
            break
    
    if not courseware:
        raise ValueError("课件未找到")
    
    # 提取文本（如果尚未提取）
    if courseware.slides_count == 0 or not courseware.extracted_text:
        await extract_text(file_id)
        # 重新获取更新后的课件
        for cw in COURSEWARE_DB:
            if cw.file_id == file_id:
                courseware = cw
                break
    
    # 创建任务
    task_id = f"course_task_{int(time.time())}_{file_id[-6:]}"
    task = CoursewareTaskDB(
        task_id=task_id,
        file_id=file_id,
        name=courseware.name,
        voice_id=voice_id,
        params={"speed": speed},
        status="processing",
        progress=0.0,
        slides_processed=0,
        total_slides=courseware.slides_count,
        created_at=datetime.now()
    )
    
    # 添加到"数据库"
    COURSEWARE_TASKS_DB.append(task)
    await save_courseware_tasks_db()
    
    # 异步处理任务
    background_tasks.add_task(process_courseware_task, task_id)
    
    return task_id

# 处理课件任务
async def process_courseware_task(task_id: str):
    # 查找任务
    task = None
    for t in COURSEWARE_TASKS_DB:
        if t.task_id == task_id:
            task = t
            break
    
    if not task:
        print(f"任务未找到: {task_id}")
        return
    
    try:
        # 查找课件
        courseware = None
        for cw in COURSEWARE_DB:
            if cw.file_id == task.file_id:
                courseware = cw
                break
        
        if not courseware:
            raise ValueError(f"课件未找到: {task.file_id}")
        
        # 更新状态
        for i, t in enumerate(COURSEWARE_TASKS_DB):
            if t.task_id == task_id:
                COURSEWARE_TASKS_DB[i].status = "processing"
                COURSEWARE_TASKS_DB[i].progress = 0.1
                COURSEWARE_TASKS_DB[i].updated_at = datetime.now()
                break
        
        await save_courseware_tasks_db()
        
        # 创建输出目录
        output_dir = os.path.join(settings.UPLOAD_DIR, "voiced_courseware")
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成输出文件名
        file_ext = Path(courseware.original_filename).suffix.lower()
        output_filename = f"有声_{courseware.name}{file_ext}"
        output_path = os.path.join(output_dir, f"{task_id}_{output_filename}")
        
        # 更新任务输出文件名
        for i, t in enumerate(COURSEWARE_TASKS_DB):
            if t.task_id == task_id:
                COURSEWARE_TASKS_DB[i].output_filename = output_filename
                break
        
        await save_courseware_tasks_db()
        
        # 创建音频目录
        audio_dir = os.path.join(output_dir, f"{task_id}_audio")
        os.makedirs(audio_dir, exist_ok=True)
        
        # 处理每张幻灯片
        tts_tasks = []
        
        # 模拟为每张幻灯片生成语音
        for i, slide in enumerate(courseware.extracted_text):
            # 更新进度
            progress = 0.1 + (0.8 * (i / courseware.slides_count))
            for j, t in enumerate(COURSEWARE_TASKS_DB):
                if t.task_id == task_id:
                    COURSEWARE_TASKS_DB[j].progress = progress
                    COURSEWARE_TASKS_DB[j].slides_processed = i
                    COURSEWARE_TASKS_DB[j].updated_at = datetime.now()
                    break
            
            await save_courseware_tasks_db()
            
            # 为当前幻灯片生成语音内容
            slide_text = slide.content
            if slide.title:
                slide_text = f"{slide.title}。\n{slide_text}"
            
            if slide.notes:
                slide_text = f"{slide_text}\n\n备注：{slide.notes}"
            
            # 模拟生成语音
            # 简单休眠代替实际TTS处理
            await asyncio.sleep(0.5)
            
            # 生成音频文件路径
            audio_file = os.path.join(audio_dir, f"slide_{slide.slide_id}.wav")
            
            # 模拟保存音频文件（实际项目中会调用真实的TTS服务）
            # 创建简单的文本文件模拟音频
            with open(audio_file, "w") as f:
                f.write(f"Slide {slide.slide_id} audio content:\n{slide_text}")
            
            tts_tasks.append({
                "slide_id": slide.slide_id,
                "audio_file": audio_file
            })
        
        # 更新进度
        for i, t in enumerate(COURSEWARE_TASKS_DB):
            if t.task_id == task_id:
                COURSEWARE_TASKS_DB[i].progress = 0.9
                COURSEWARE_TASKS_DB[i].slides_processed = courseware.slides_count
                COURSEWARE_TASKS_DB[i].updated_at = datetime.now()
                break
        
        await save_courseware_tasks_db()
        
        # 模拟创建有声课件（复制原始文件）
        # 注意：实际项目中会使用python-pptx等库修改PPT，嵌入音频
        shutil.copy2(courseware.file_path, output_path)
        
        # 创建包含幻灯片和音频路径的清单文件
        manifest_path = os.path.join(output_dir, f"{task_id}_manifest.json")
        with open(manifest_path, "w") as f:
            manifest = {
                "task_id": task_id,
                "courseware": {
                    "file_id": courseware.file_id,
                    "name": courseware.name,
                    "original_filename": courseware.original_filename
                },
                "output_file": output_path,
                "slides": tts_tasks
            }
            json.dump(manifest, f, default=str)
        
        # 更新任务完成状态
        for i, t in enumerate(COURSEWARE_TASKS_DB):
            if t.task_id == task_id:
                COURSEWARE_TASKS_DB[i].status = "completed"
                COURSEWARE_TASKS_DB[i].progress = 1.0
                COURSEWARE_TASKS_DB[i].updated_at = datetime.now()
                COURSEWARE_TASKS_DB[i].file_path = output_path
                break
        
        await save_courseware_tasks_db()
        print(f"课件处理任务完成: {task_id}, 文件: {output_path}")
        
    except Exception as e:
        # 更新任务状态为失败
        for i, t in enumerate(COURSEWARE_TASKS_DB):
            if t.task_id == task_id:
                COURSEWARE_TASKS_DB[i].status = "failed"
                COURSEWARE_TASKS_DB[i].error = str(e)
                COURSEWARE_TASKS_DB[i].updated_at = datetime.now()
                break
        
        await save_courseware_tasks_db()
        print(f"课件处理任务失败: {task_id}, 错误: {e}")

# 获取任务状态
async def get_task_status(task_id: str) -> Optional[CoursewareTaskStatus]:
    for task in COURSEWARE_TASKS_DB:
        if task.task_id == task_id:
            return CoursewareTaskStatus(
                task_id=task.task_id,
                name=task.name,
                status=task.status,
                progress=task.progress,
                created_at=task.created_at,
                updated_at=task.updated_at,
                slides_processed=task.slides_processed,
                total_slides=task.total_slides,
                output_filename=task.output_filename,
                error=task.error
            )
    
    return None

# 获取任务结果
async def get_task_result(task_id: str) -> Optional[CoursewareTaskStatus]:
    status = await get_task_status(task_id)
    if status and status.status == "completed":
        # 找到对应任务获取文件路径
        for task in COURSEWARE_TASKS_DB:
            if task.task_id == task_id:
                if os.path.exists(task.file_path):
                    return status
    
    return None

# 初始化服务
asyncio.create_task(init_course_service())