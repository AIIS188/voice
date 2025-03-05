import os
import json
import asyncio
import time
import shutil
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import UploadFile, BackgroundTasks
from app.models.course import CoursewareDB, CoursewareTaskDB, CoursewareTextExtraction, CoursewareTaskStatus, SlideContent
from app.services.tts_service import synthesize_speech, get_tts_task_status, get_tts_task_result
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

# 模拟从PPT提取文本的函数
def extract_text_from_ppt(file_path):
    """
    模拟从PPT文件提取文本的函数
    实际项目中可使用python-pptx库处理PPT文件
    """
    # 检查文件类型
    ext = Path(file_path).suffix.lower()
    if ext not in ['.ppt', '.pptx', '.pdf']:
        raise ValueError(f"不支持的文件类型: {ext}")
    
    # 生成随机数量的幻灯片 (8-15页)
    import random
    slides_count = random.randint(8, 15)
    
    # 获取课件名称
    courseware_name = Path(file_path).stem
    
    # 生成模拟文本内容
    slides = []
    
    # 课程标题模板
    course_titles = [
        "课程介绍与学习目标",
        "基础概念与理论框架",
        "核心原理解析",
        "应用场景与案例分析",
        "进阶技巧与方法论",
        "实践操作指南",
        "常见问题与解决方案",
        "总结与展望"
    ]
    
    # 内容模板
    content_templates = [
        "本章将介绍{subject}的基本概念和重要性。通过学习，你将掌握{keyword1}和{keyword2}的核心知识。",
        "{subject}是{field}领域的重要组成部分。它包含了{keyword1}、{keyword2}和{keyword3}等关键要素。",
        "在实际应用中，{subject}可以帮助我们解决{problem}问题。具体步骤包括：\n1. 分析{keyword1}\n2. 运用{keyword2}方法\n3. 评估{keyword3}结果",
        "研究表明，{percent}%的{field}问题可以通过正确应用{subject}得到有效解决。这要求我们必须深入理解{keyword1}和{keyword2}之间的关系。",
        "{subject}的发展历程可以追溯到{year}年。从那时起，它经历了{keyword1}阶段、{keyword2}阶段和{keyword3}阶段的演变。",
        "总结来说，{subject}的核心价值在于它能够{benefit1}和{benefit2}。未来，随着{trend}的发展，它将发挥更加重要的作用。"
    ]
    
    # 笔记模板
    notes_templates = [
        "详细讲解{keyword1}的定义和应用场景，强调与{keyword2}的区别。",
        "可以结合学生熟悉的{example}作为例子，增强理解。",
        "这部分内容较难，需要放慢节奏，多举例说明。",
        "提问学生对{subject}的理解，引导讨论。",
        "强调这是考试重点内容，建议学生课后复习。",
        None  # 有些幻灯片没有笔记
    ]
    
    # 课程相关词汇
    subjects = ["人工智能", "机器学习", "深度学习", "自然语言处理", "计算机视觉", "语音识别", "知识图谱"]
    keywords = ["算法", "模型", "数据", "特征", "训练", "推理", "优化", "评估", "应用", "框架"]
    fields = ["科技", "教育", "医疗", "金融", "工业", "交通", "安防"]
    problems = ["效率低下", "准确率不足", "资源浪费", "用户体验差", "安全隐患", "扩展性受限"]
    benefits = ["提高效率", "降低成本", "增强体验", "优化流程", "提升安全性", "促进创新"]
    trends = ["5G技术", "物联网", "边缘计算", "区块链", "量子计算", "生物技术"]
    years = ["1950", "1970", "1980", "1990", "2000", "2010", "2015"]
    percents = ["60", "75", "82", "90", "95"]
    examples = ["智能手机应用", "自动驾驶", "语音助手", "推荐系统", "人脸识别", "智能客服"]
    
    # 随机选择一个主题
    main_subject = random.choice(subjects)
    
    # 第一页：课程封面
    slides.append(SlideContent(
        slide_id=1,
        title=f"{main_subject}技术与应用",
        content=f"{main_subject}技术与应用\n课程讲解\n\n作者：教师\n日期：{datetime.now().strftime('%Y-%m-%d')}",
        notes="介绍课程大纲和教学目标，引起学生兴趣。"
    ))
    
    # 生成内容页
    for i in range(2, slides_count):
        # 随机选择标题和内容模板
        if i-2 < len(course_titles):
            title = course_titles[i-2]
        else:
            title = f"{main_subject}的{random.choice(keywords)}与{random.choice(keywords)}"
        
        content_template = random.choice(content_templates)
        
        # 填充内容模板
        content = content_template.format(
            subject=main_subject,
            keyword1=random.choice(keywords),
            keyword2=random.choice(keywords),
            keyword3=random.choice(keywords) if "{keyword3}" in content_template else "",
            field=random.choice(fields),
            problem=random.choice(problems),
            percent=random.choice(percents),
            year=random.choice(years),
            benefit1=random.choice(benefits),
            benefit2=random.choice(benefits),
            trend=random.choice(trends)
        )
        
        # 随机决定是否有笔记
        notes_template = random.choice(notes_templates)
        notes = None
        if notes_template:
            notes = notes_template.format(
                keyword1=random.choice(keywords),
                keyword2=random.choice(keywords),
                subject=main_subject,
                example=random.choice(examples)
            )
        
        slides.append(SlideContent(
            slide_id=i,
            title=title,
            content=content,
            notes=notes
        ))
    
    # 最后一页：总结
    slides.append(SlideContent(
        slide_id=slides_count,
        title="总结与展望",
        content=f"通过本课程的学习，我们掌握了{main_subject}的核心知识和应用技能。\n\n未来，随着技术的发展，{main_subject}将在{random.choice(fields)}、{random.choice(fields)}等领域发挥越来越重要的作用。\n\n感谢大家的参与！",
        notes="总结关键点，强调学以致用，鼓励学生进一步探索。"
    ))
    
    return slides_count, slides

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
    
    try:
        # 从PPT提取文本
        slides_count, extracted_text = extract_text_from_ppt(courseware.file_path)
        
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
    except Exception as e:
        print(f"提取文本失败: {e}")
        return None

# 将文本分段，便于语音合成
def split_text_into_chunks(text, max_length=500):
    """将长文本分成适合TTS处理的小段"""
    # 按句子分割
    sentences = re.split(r'(?<=[。！？.!?])', text)
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if not sentence.strip():
            continue
            
        # 如果当前块加上这个句子不超过最大长度，则添加到当前块
        if len(current_chunk) + len(sentence) <= max_length:
            current_chunk += sentence
        else:
            # 如果当前块不为空，添加到结果中
            if current_chunk:
                chunks.append(current_chunk)
            # 开始新的块
            current_chunk = sentence
    
    # 添加最后一个块
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

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
        extraction_result = await extract_text(file_id)
        if not extraction_result:
            raise ValueError("文本提取失败")
        
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
        slides_total = len(courseware.extracted_text)
        
        for i, slide in enumerate(courseware.extracted_text):
            # 更新进度
            progress = 0.1 + (0.8 * ((i+1) / slides_total))
            for j, t in enumerate(COURSEWARE_TASKS_DB):
                if t.task_id == task_id:
                    COURSEWARE_TASKS_DB[j].progress = progress
                    COURSEWARE_TASKS_DB[j].slides_processed = i + 1
                    COURSEWARE_TASKS_DB[j].updated_at = datetime.now()
                    break
            
            await save_courseware_tasks_db()
            
            # 准备幻灯片文本
            slide_text = ""
            if slide.title:
                slide_text += f"{slide.title}。\n"
            slide_text += slide.content
            
            if slide.notes:
                slide_text += f"\n\n讲解要点：{slide.notes}"
            
            # 将长文本分段
            text_chunks = split_text_into_chunks(slide_text)
            
            # 为每个文本块生成语音
            chunk_tasks = []
            for chunk_idx, chunk in enumerate(text_chunks):
                # 设置TTS参数
                tts_params = {
                    "speed": task.params.get("speed", 1.0),
                    "pitch": 0,
                    "energy": 1.0,
                    "emotion": "neutral",
                    "pause_factor": 1.0
                }
                
                # 提交TTS任务
                try:
                    # 使用临时的BackgroundTasks对象，因为我们需要等待TTS完成
                    temp_bg_tasks = BackgroundTasks()
                    tts_task_id = await synthesize_speech(
                        temp_bg_tasks, 
                        chunk, 
                        task.voice_id, 
                        tts_params
                    )
                    
                    # 手动启动TTS任务处理
                    await temp_bg_tasks()
                    
                    # 等待TTS任务完成
                    await asyncio.sleep(1)  # 等待一会，让TTS任务启动
                    
                    while True:
                        tts_status = await get_tts_task_status(tts_task_id)
                        if tts_status and tts_status.status in ["completed", "failed"]:
                            break
                        await asyncio.sleep(0.5)
                    
                    if tts_status and tts_status.status == "completed":
                        # 获取TTS结果
                        tts_result = await get_tts_task_result(tts_task_id)
                        
                        if tts_result:
                            # 复制TTS生成的音频文件到课件音频目录
                            chunk_audio_file = os.path.join(audio_dir, f"slide_{slide.slide_id}_chunk_{chunk_idx}.wav")
                            
                            tts_output_file = tts_result.file_path
                            shutil.copy2(tts_output_file, chunk_audio_file)
                            
                            chunk_tasks.append({
                                "chunk_id": chunk_idx,
                                "audio_file": chunk_audio_file
                            })
                    else:
                        print(f"TTS任务失败: {tts_task_id}")
                except Exception as e:
                    print(f"处理文本块失败: {e}")
            
            # 保存幻灯片任务信息
            tts_tasks.append({
                "slide_id": slide.slide_id,
                "title": slide.title,
                "chunks": chunk_tasks
            })
        
        # 更新进度
        for i, t in enumerate(COURSEWARE_TASKS_DB):
            if t.task_id == task_id:
                COURSEWARE_TASKS_DB[i].progress = 0.9
                COURSEWARE_TASKS_DB[i].slides_processed = slides_total
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