import os
import json
import time
import asyncio
import numpy as np
import torch
import torchaudio
import librosa
import soundfile as sf
from scipy.ndimage import gaussian_filter1d
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from fastapi import BackgroundTasks
from app.services.voice_clone import voice_cloner
from app.models.tts import TTSTaskDB, TTSTaskStatus, TTSParams
from app.services.voice_service import get_voice_samples
from app.core.config import settings
from app.utils.tts_metrics import create_evaluator



# 检查中文文本处理库
try:
    import pypinyin
    PYPINYIN_AVAILABLE = True
except ImportError:
    PYPINYIN_AVAILABLE = False
    print("警告: pypinyin不可用，中文文本处理可能受限。")

# TTS模型类
class TTSModel:
    def __init__(self, model_dir: str):
        """
        初始化TTS模型：FastSpeech2用于生成mel谱图，HiFi-GAN用于声码转换
        
        Args:
            model_dir: 模型文件目录
        """
        self.model_dir = model_dir
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"使用设备: {self.device}")
        
        # 加载FastSpeech2模型
        self.fastspeech2 = self._load_fastspeech2()
        
        # 加载HiFi-GAN模型
        self.hifigan = self._load_hifigan()
        
        # 加载发音词典或转换器
        self.tokenizer = self._load_tokenizer()
        
        print(f"TTS模型加载完成，运行于{self.device}")
    
    def _load_fastspeech2(self):
        """加载FastSpeech2模型"""
        fastspeech2_path = os.path.join(self.model_dir, "fastspeech2")
        if not os.path.exists(fastspeech2_path):
            os.makedirs(fastspeech2_path, exist_ok=True)
        
        # 检查预训练模型文件
        model_file = os.path.join(fastspeech2_path, "model.pt")
        config_file = os.path.join(fastspeech2_path, "config.json")
        
        if os.path.exists(model_file) and os.path.exists(config_file):
            try:
                # 加载本地模型
                print("从本地加载FastSpeech2模型")
                config = json.load(open(config_file, 'r'))
                model = self._load_local_fastspeech2(model_file, config)
                return model
            except Exception as e:
                print(f"加载本地FastSpeech2模型失败: {e}")
        
        # 尝试使用transformers加载模型
        try:
            from transformers import AutoProcessor, AutoModel
            processor = AutoProcessor.from_pretrained("espnet/fastspeech2")
            model = AutoModel.from_pretrained("espnet/fastspeech2")
            model.to(self.device)
            print("使用transformers加载FastSpeech2模型")
            return {"model": model, "processor": processor}
        except Exception as e:
            print(f"使用transformers加载FastSpeech2模型失败: {e}")
        
        print("将使用占位实现")
        return None
    
    def _load_local_fastspeech2(self, model_file, config):
        """加载本地FastSpeech2模型"""
        # 这里需要根据具体的模型格式实现加载逻辑
        model = torch.load(model_file, map_location=self.device)
        return {"model": model, "config": config}
    
    def _load_hifigan(self):
        """加载HiFi-GAN声码器模型"""
        hifigan_path = os.path.join(self.model_dir, "hifigan")
        if not os.path.exists(hifigan_path):
            os.makedirs(hifigan_path, exist_ok=True)
        
        # 检查预训练模型文件
        model_file = os.path.join(hifigan_path, "generator.pt")
        config_file = os.path.join(hifigan_path, "config.json")
        
        if os.path.exists(model_file) and os.path.exists(config_file):
            try:
                # 加载本地模型
                print("从本地加载HiFi-GAN模型")
                config = json.load(open(config_file, 'r'))
                model = self._load_local_hifigan(model_file, config)
                return model
            except Exception as e:
                print(f"加载本地HiFi-GAN模型失败: {e}")
        
        # 尝试使用torchaudio加载预训练模型
        try:
            vocoder = torchaudio.pipelines.HIFIGAN_VOCODER
            vocoder.to(self.device)
            print("使用torchaudio加载HiFi-GAN模型")
            return vocoder
        except Exception as e:
            print(f"使用torchaudio加载HiFi-GAN模型失败: {e}")
        
        print("HiFi-GAN不可用，将使用替代方法")
        return None
    
    def _load_local_hifigan(self, model_file, config):
        """加载本地HiFi-GAN模型"""
        # 这里需要根据具体的模型格式实现加载逻辑
        model = torch.load(model_file, map_location=self.device)
        return {"model": model, "config": config}
    
    def _load_tokenizer(self):
        """加载文本分词器或音素转换器"""
        tokenizer_path = os.path.join(self.model_dir, "tokenizer")
        if not os.path.exists(tokenizer_path):
            os.makedirs(tokenizer_path, exist_ok=True)
        
        # 使用pypinyin作为中文音素转换器
        if PYPINYIN_AVAILABLE:
            print("使用pypinyin作为中文音素转换器")
            return {"type": "pypinyin"}
        
        return None
    
    def text_to_phonemes(self, text: str, language: str = "zh-CN") -> List[str]:
        """
        将文本转换为音素序列
        
        Args:
            text: 输入文本
            language: 语言代码（如"zh-CN", "en-US"）
            
        Returns:
            音素列表
        """
        # 中文处理
        if language.startswith("zh") and PYPINYIN_AVAILABLE:
            phonemes = []
            for char in text:
                if char.strip():  # 跳过空白符
                    pinyins = pypinyin.pinyin(char, style=pypinyin.TONE3)
                    phonemes.extend([p[0] for p in pinyins])
            return phonemes
        
        # 其他语言（简单实现）
        return list(text)
    
    def synthesize(self, text: str, params: Dict[str, Any], speaker_embedding: Optional[np.ndarray] = None) -> Tuple[np.ndarray, float]:
        """
        使用FastSpeech2和HiFi-GAN合成语音
        
        Args:
            text: 输入文本
            params: 合成参数（语速、音调等）
            speaker_embedding: 说话人嵌入向量（用于声音克隆）
            
        Returns:
            audio: 音频波形
            duration: 音频时长（秒）
        """
        # 尝试使用真实模型
        if self.fastspeech2 is not None and self.hifigan is not None:
            try:
                # 将文本转换为音素（如果支持）
                phonemes = self.text_to_phonemes(text)
                
                # 生成mel谱图
                mel_spectrogram = self._generate_mel_spectrogram(phonemes, params, speaker_embedding)
                
                # 使用HiFi-GAN生成波形
                audio = self._generate_waveform(mel_spectrogram)
                
                # 计算时长
                sample_rate = 22050  # 标准采样率
                duration = len(audio) / sample_rate
                
                # 根据参数进行后处理
                audio = self._apply_params(audio, params, sample_rate)
                
                return audio, duration
                
            except Exception as e:
                print(f"使用真实模型合成失败: {e}")
                print("使用替代实现")
        
        # 如果真实模型不可用或失败，使用替代实现
        return self._placeholder_synthesis(text, params)
    
    def _generate_mel_spectrogram(self, phonemes, params, speaker_embedding):
        """生成mel谱图"""
        # 这里应根据实际的FastSpeech2模型实现
        # 以下是占位代码
        return np.random.rand(80, 100)  # 80梅尔频段，100帧
    
    def _generate_waveform(self, mel_spectrogram):
        """使用HiFi-GAN从mel谱图生成波形"""
        # 这里应根据实际的HiFi-GAN模型实现
        # 以下是占位代码
        sample_rate = 22050
        duration = mel_spectrogram.shape[1] * 0.0125  # 假设每帧12.5ms
        return np.random.rand(int(duration * sample_rate))
    
    def _apply_params(self, audio: np.ndarray, params: Dict[str, Any], sample_rate: int) -> np.ndarray:
        """根据参数处理音频（语速、音调等）"""
        # 语速调整（时间拉伸）
        speed = params.get("speed", 1.0)
        if speed != 1.0:
            audio = librosa.effects.time_stretch(audio, rate=speed)
        
        # 音调调整
        pitch = params.get("pitch", 0.0)
        if pitch != 0.0:
            # 将pitch参数（-1到1）转换为半音（-12到12）
            semitones = pitch * 12
            audio = librosa.effects.pitch_shift(audio, sr=sample_rate, n_steps=semitones)
        
        # 音量调整
        energy = params.get("energy", 1.0)
        audio = audio * energy
        
        # 确保音频归一化
        audio = librosa.util.normalize(audio) * 0.95
        
        return audio
    
    def _placeholder_synthesis(self, text: str, params: Dict[str, Any]) -> Tuple[np.ndarray, float]:
        """当真实模型不可用时的替代合成实现"""
        # 基于文本长度和语速估计时长
        chars = len(text)
        speed = params.get("speed", 1.0)
        chars_per_second = 5 * speed  # 假设每秒约5个汉字
        duration = max(1.0, chars / chars_per_second)
        
        # 创建时间数组
        sample_rate = 22050
        t = np.linspace(0, duration, int(duration * sample_rate))
        
        # 创建基于音高参数的载波
        pitch_param = params.get("pitch", 0)
        base_freq = 170 * (2 ** (pitch_param * 0.5))
        carrier = np.sin(2 * np.pi * base_freq * t)
        
        # 添加谐波增加丰富度
        harmonics = 0
        for i in range(2, 6):
            harmonics += (1/i) * np.sin(2 * np.pi * (base_freq * i) * t)
        
        carrier = 0.7 * carrier + 0.3 * harmonics
        
        # 基于音节创建包络
        syllables = max(1, chars)
        envelope = np.ones_like(t) * 0.1
        
        pause_factor = params.get("pause_factor", 1.0)
        syllable_positions = np.linspace(0, duration * 0.8, syllables)
        syllable_width = 0.15
        
        for pos in syllable_positions:
            idx = (t >= pos) & (t <= pos + syllable_width)
            if np.any(idx):
                envelope[idx] = 0.5 + 0.5 * np.sin(np.pi * (t[idx] - pos) / syllable_width)
        
        envelope = gaussian_filter1d(envelope, sigma=0.01 * sample_rate)
        
        # 应用情感风格
        emotion = params.get("emotion", "neutral")
        if emotion == "happy":
            modulation = 0.1 * np.sin(2 * np.pi * 3 * t / duration)
            carrier = carrier + modulation
            envelope = np.power(envelope, 0.9)
        elif emotion == "sad":
            modulation = 0.05 * np.sin(2 * np.pi * 1 * t / duration)
            carrier = carrier - modulation
            envelope = np.power(envelope, 1.2)
        elif emotion == "serious":
            envelope = np.power(envelope, 1.1)
            envelope = np.clip(envelope, 0, 0.9)
        
        # 应用包络
        audio = carrier * envelope
        
        # 应用音量
        energy = params.get("energy", 1.0)
        audio = audio * energy
        
        # 添加噪声以模拟辅音
        noise = np.random.uniform(-0.05, 0.05, len(audio))
        audio = audio + noise * envelope * 0.3
        
        # 添加音高微小变化
        tremolo = 1.0 + 0.03 * np.sin(2 * np.pi * 5 * t)
        audio = audio * tremolo
        
        # 添加淡入淡出
        fade_len = int(0.05 * sample_rate)
        if len(audio) > 2 * fade_len:
            fade_in = np.linspace(0, 1, fade_len)
            fade_out = np.linspace(1, 0, fade_len)
            audio[:fade_len] = audio[:fade_len] * fade_in
            audio[-fade_len:] = audio[-fade_len:] * fade_out
        
        # 归一化
        max_amp = np.max(np.abs(audio))
        if max_amp > 0:
            audio = audio / max_amp * 0.95
        
        return audio, duration

# 全局变量
TTS_TASKS_DB = []
TTS_TASKS_FILE = os.path.join(settings.UPLOAD_DIR, "tts_tasks.json")
tts_model = None
tts_evaluator = None  # Add this line

# 下载模型文件（如果需要）
async def download_models():
    """下载FastSpeech2和HiFi-GAN模型（如果不存在）"""
    model_dir = os.path.join(settings.MODELS_DIR, "tts")
    os.makedirs(model_dir, exist_ok=True)
    
    # FastSpeech2模型目录
    fastspeech2_dir = os.path.join(model_dir, "fastspeech2")
    os.makedirs(fastspeech2_dir, exist_ok=True)
    
    # HiFi-GAN模型目录
    hifigan_dir = os.path.join(model_dir, "hifigan")
    os.makedirs(hifigan_dir, exist_ok=True)
    
    # 检查是否需要下载模型
    if not os.path.exists(os.path.join(fastspeech2_dir, "model.pt")):
        print("FastSpeech2模型文件不存在，需要从外部获取")
        # 这里可以添加从特定URL下载模型的代码
    
    if not os.path.exists(os.path.join(hifigan_dir, "generator.pt")):
        print("HiFi-GAN模型文件不存在，需要从外部获取")
        # 这里可以添加从特定URL下载模型的代码
    
    print("模型目录检查完成")

# Update in init_tts_service function
async def init_tts_service():
    global TTS_TASKS_DB, tts_model, tts_evaluator  # Add tts_evaluator here
    
    # Ensure directories exist
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "tts_results"), exist_ok=True)
    
    # Check and download models (if needed)
    await download_models()
    
    # Load existing tasks
    if os.path.exists(TTS_TASKS_FILE):
        try:
            with open(TTS_TASKS_FILE, 'r') as f:
                data = json.load(f)
                TTS_TASKS_DB = [TTSTaskDB(**item) for item in data]
        except Exception as e:
            print(f"初始化TTS服务失败: {e}")
    
    # Initialize TTS model
    model_dir = os.path.join(settings.MODELS_DIR, "tts")
    tts_model = TTSModel(model_dir)
    
    # Initialize TTS evaluator
    tts_evaluator = create_evaluator(settings.TTS_METRICS_MODEL_PATH)
    print("TTS 评估器初始化完成")
# 保存任务到文件
async def save_tts_tasks():
    with open(TTS_TASKS_FILE, 'w') as f:
        # 转换为字典列表并保存
        data = [task.dict() for task in TTS_TASKS_DB]
        json.dump(data, f, default=str)

# 创建TTS任务
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
    global tts_model
    
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
            raise ValueError(f"声音样本未找到: {task.voice_id}")
        
        voice_sample = voice_samples[0]
        # 加载声音克隆嵌入向量
        speaker_embedding = voice_cloner.load_voice_embedding(task.voice_id)
        
        # 调整TTS参数
        if speaker_embedding is not None:
            task.params = voice_cloner.adapt_tts_params(speaker_embedding, task.params)
        
        # 使用优化的参数合成语音
        audio, duration = tts_model.synthesize(text, task.params, speaker_embedding)
        
        # 检查是否为预览模式
        is_preview = task.params.get("is_preview", False)
        
        # 文本预处理
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
        
        # 话者嵌入向量（用于声音克隆）
        speaker_embedding = None
        
        # 如果有真实的声音样本，尝试加载用于克隆
        if hasattr(voice_sample, 'embedding_path') and voice_sample.embedding_path:
            try:
                # 如果嵌入存在，加载它
                if os.path.exists(voice_sample.embedding_path):
                    with open(voice_sample.embedding_path, 'r') as f:
                        features = json.load(f)
                        if 'mfcc_fingerprint' in features:
                            speaker_embedding = np.array(features['mfcc_fingerprint'])
            except Exception as e:
                print(f"加载声音嵌入失败: {e}")
                # 继续但不使用嵌入
        
        # 合成语音
        audio, duration = tts_model.synthesize(text, task.params, speaker_embedding)
        
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
        sf.write(output_file, audio, 22050)  # 标准采样率
        # 保存音频文件后，评估质量
        if os.path.exists(output_file):
            # 对于声音克隆任务，可以评估相似度
            if voice_sample and hasattr(voice_sample, 'file_path') and os.path.exists(voice_sample.file_path):
                metrics = tts_evaluator.evaluate_overall(output_file, voice_sample.file_path)
            else:
                metrics = tts_evaluator.evaluate_overall(output_file)
            
            print(f"质量评估: {metrics}")
            
            # 记录评估结果
            task.metrics = metrics
            
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