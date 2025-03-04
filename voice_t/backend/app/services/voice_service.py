import os
import json
import asyncio
import librosa
import numpy as np
from datetime import datetime
from typing import List, Optional
from app.models.voice import VoiceSampleCreate, VoiceSampleDB, VoiceSampleResponse
from app.core.config import settings

# 模拟数据库存储
# 在真实项目中会使用MongoDB或其他数据库
VOICE_SAMPLES_DB = []
VOICE_SAMPLES_FILE = os.path.join(settings.UPLOAD_DIR, "voice_samples.json")

# 初始化函数，读取已有的样本记录
async def init_voice_service():
    global VOICE_SAMPLES_DB
    if os.path.exists(VOICE_SAMPLES_FILE):
        try:
            with open(VOICE_SAMPLES_FILE, 'r') as f:
                data = json.load(f)
                VOICE_SAMPLES_DB = [VoiceSampleDB(**item) for item in data]
        except Exception as e:
            print(f"初始化声音样本服务失败: {e}")

# 保存样本记录到文件
async def save_voice_samples():
    with open(VOICE_SAMPLES_FILE, 'w') as f:
        # 转换为字典列表并保存
        data = [sample.dict() for sample in VOICE_SAMPLES_DB]
        json.dump(data, f, default=str)

# 处理声音样本
async def process_voice_sample(sample: VoiceSampleCreate):
    # 创建数据库记录
    db_sample = VoiceSampleDB(**sample.dict(), status="processing")
    
    # 添加到"数据库"
    for i, s in enumerate(VOICE_SAMPLES_DB):
        if s.id == sample.id:
            VOICE_SAMPLES_DB[i] = db_sample
            break
    else:
        VOICE_SAMPLES_DB.append(db_sample)
    
    try:
        # 更新状态
        await save_voice_samples()
        
        # 模拟处理音频文件
        # 1. 加载音频
        print(f"处理音频文件: {sample.file_path}")
        y, sr = librosa.load(sample.file_path, sr=22050)
        
        # 2. 提取特征 (简化版，仅做演示)
        # 检查音频长度是否在5-30秒之间
        duration = librosa.get_duration(y=y, sr=sr)
        if duration < 5 or duration > 30:
            raise ValueError(f"音频长度为 {duration:.2f} 秒，需要在5-30秒之间")
        
        # 计算能量
        energy = np.mean(librosa.feature.rms(y=y)[0])
        
        # 计算音高 (简化版)
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
        pitch_mean = np.mean(pitches[magnitudes > 0.1]) if np.any(magnitudes > 0.1) else 0
        
        # 假设这是声音质量评分
        quality_score = min(0.95, 0.5 + 0.5 * (energy / 0.1) + 0.2 * min(1, pitch_mean / 500))
        
        # 更新样本记录
        for i, s in enumerate(VOICE_SAMPLES_DB):
            if s.id == sample.id:
                VOICE_SAMPLES_DB[i].status = "ready"
                VOICE_SAMPLES_DB[i].quality_score = quality_score
                VOICE_SAMPLES_DB[i].updated_at = datetime.now()
                break
                
        # 保存更新
        await save_voice_samples()
        print(f"声音样本 {sample.id} 处理完成，质量评分: {quality_score:.2f}")
        
    except Exception as e:
        # 处理失败，更新状态
        for i, s in enumerate(VOICE_SAMPLES_DB):
            if s.id == sample.id:
                VOICE_SAMPLES_DB[i].status = "failed"
                VOICE_SAMPLES_DB[i].error = str(e)
                VOICE_SAMPLES_DB[i].updated_at = datetime.now()
                break
        
        await save_voice_samples()
        print(f"处理声音样本 {sample.id} 失败: {e}")

# 获取声音样本列表
async def get_voice_samples(
    skip: int = 0,
    limit: int = 10,
    tags: Optional[List[str]] = None,
    sample_id: Optional[str] = None
) -> List[VoiceSampleResponse]:
    # 过滤样本
    filtered_samples = VOICE_SAMPLES_DB
    
    # 按ID过滤
    if sample_id:
        filtered_samples = [s for s in filtered_samples if s.id == sample_id]
    
    # 按标签过滤
    if tags:
        filtered_samples = [
            s for s in filtered_samples 
            if any(tag in s.tags for tag in tags)
        ]
    
    # 分页
    paginated = filtered_samples[skip:skip+limit]
    
    # 转换为响应模型
    result = []
    for sample in paginated:
        message = None
        if sample.status == "ready":
            message = "声音样本处理完成"
        elif sample.status == "processing":
            message = "声音样本正在处理中"
        elif sample.status == "failed":
            message = "声音样本处理失败"
        
        result.append(VoiceSampleResponse(
            id=sample.id,
            name=sample.name,
            description=sample.description,
            tags=sample.tags,
            created_at=sample.created_at,
            status=sample.status,
            quality_score=sample.quality_score,
            message=message,
            error=sample.error
        ))
    
    return result

# 删除声音样本
async def delete_voice_sample(sample_id: str) -> Optional[VoiceSampleResponse]:
    global VOICE_SAMPLES_DB
    
    # 查找样本
    for i, sample in enumerate(VOICE_SAMPLES_DB):
        if sample.id == sample_id:
            # 删除物理文件
            try:
                if os.path.exists(sample.file_path):
                    os.remove(sample.file_path)
                
                # 从"数据库"中删除
                deleted = VOICE_SAMPLES_DB.pop(i)
                await save_voice_samples()
                
                # 返回删除的样本信息
                return VoiceSampleResponse(
                    id=deleted.id,
                    name=deleted.name,
                    description=deleted.description,
                    tags=deleted.tags,
                    created_at=deleted.created_at,
                    status="deleted",
                    quality_score=deleted.quality_score,
                    message="声音样本已删除"
                )
            except Exception as e:
                print(f"删除声音样本 {sample_id} 失败: {e}")
                return None
    
    return None

# 初始化服务
asyncio.create_task(init_voice_service())