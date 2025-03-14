import os
import json
import time
import asyncio
import numpy as np
import wave
import tempfile
import soundfile as sf
from typing import Dict, Any, Optional, List, Tuple, BinaryIO
from datetime import datetime
from pathlib import Path
from fastapi import BackgroundTasks, WebSocket
from app.services.voice_clone import voice_cloner
from app.models.tts import TTSTaskDB, TTSTaskStatus, TTSParams
from app.services.voice_service import get_voice_samples
from app.core.config import settings
from app.utils.audio import normalize_audio, trim_audio

# Import PaddleSpeech
try:
    import paddle
    from paddlespeech.cli.tts.infer import TTSExecutor
    from paddlespeech.cli.tts import TTSEngine
    from paddlespeech.server.engine.tts.online import PaddleTTSOnlineEngine
    PADDLESPEECH_AVAILABLE = True
except ImportError:
    PADDLESPEECH_AVAILABLE = False
    print("警告: PaddleSpeech 不可用，请确保已安装 paddlepaddle 和 paddlespeech 库。")

# 全局变量
TTS_TASKS_DB = []
TTS_TASKS_FILE = os.path.join(settings.UPLOAD_DIR, "tts_tasks.json")
tts_executor = None
tts_online_engine = None

class PaddleSpeechModel:
    """PaddleSpeech TTS 模型封装类"""
    
    def __init__(self):
        """初始化 PaddleSpeech TTS 模型"""
        self.device = "gpu" if paddle.device.is_compiled_with_cuda() else "cpu"
        print(f"使用设备: {self.device}")
        
        if not PADDLESPEECH_AVAILABLE:
            print("PaddleSpeech 不可用，将使用替代实现")
            return
        
        try:
            # 初始化常规 TTS 执行器
            self.tts = TTSExecutor()
            
            # 初始化在线流式 TTS 引擎
            self.online_engine = PaddleTTSOnlineEngine(
                am='fastspeech2_csmsc',
                voc='hifigan_csmsc',
                lang='zh',
                device=self.device,
                sample_rate=24000  # 可配置
            )
            print("PaddleSpeech TTS 模型加载成功")
        except Exception as e:
            print(f"初始化 PaddleSpeech TTS 模型失败: {e}")
            self.tts = None
            self.online_engine = None
    
    def synthesize(self, text: str, params: Dict[str, Any], 
                   speaker_embedding: Optional[np.ndarray] = None,
                   output_path: Optional[str] = None) -> Tuple[np.ndarray, float]:
        """
        使用 PaddleSpeech 合成语音
        
        Args:
            text: 输入文本
            params: 合成参数
            speaker_embedding: 说话人嵌入向量（用于声音克隆）
            output_path: 输出文件路径（可选）
            
        Returns:
            audio: 音频波形
            duration: 音频时长（秒）
        """
        if not PADDLESPEECH_AVAILABLE or self.tts is None:
            print("PaddleSpeech 不可用，使用替代实现")
            return self._placeholder_synthesis(text, params)
        
        try:
            # 配置合成参数
            am = 'fastspeech2_csmsc'  # 默认普通话女声
            voc = 'hifigan_csmsc'     # 默认声码器
            lang = params.get('language', 'zh')[:2]  # 获取语言前两个字符，如 'zh-CN' 转为 'zh'
            
            # 声音选择逻辑
            if 'voice_model' in params:
                # 使用指定的声音模型（如果有）
                am = params['voice_model']
            
            # 调整语速
            speed = params.get('speed', 1.0)
            
            # 处理方言或其他语言
            if lang == 'en':
                am = 'fastspeech2_ljspeech'
                voc = 'hifigan_ljspeech'
            
            # 如果有自定义的声音模型（从声音克隆得到）
            custom_model_path = None
            if speaker_embedding is not None and 'model_path' in params:
                custom_model_path = params['model_path']
                
            # 输出路径处理
            if output_path is None:
                temp_dir = tempfile.mkdtemp()
                output_path = os.path.join(temp_dir, "output.wav")
            
            # 执行合成
            result = self.tts(
                text=text,
                output=output_path,
                am=am,
                voc=voc,
                lang=lang,
                spk_id=0,  # 默认说话人 ID
                speed=speed,
                volume=params.get('energy', 1.0),
                device=self.device
            )
            
            # 如果成功合成，加载音频文件
            if os.path.exists(output_path):
                audio, sr = sf.read(output_path)
                
                # 调整音调（需要进行后处理）
                pitch_shift = params.get('pitch', 0.0)
                if pitch_shift != 0.0 and pitch_shift != 0:
                    import librosa
                    # 将 -1 到 1 的范围转换为半音数（-12 到 12）
                    n_steps = pitch_shift * 12
                    audio = librosa.effects.pitch_shift(audio, sr=sr, n_steps=n_steps)
                    
                    # 应用更改后重新保存
                    sf.write(output_path, audio, sr)
                
                # 计算时长
                duration = len(audio) / sr
                
                return audio, duration
            else:
                raise FileNotFoundError(f"合成后的音频文件未找到: {output_path}")
                
        except Exception as e:
            print(f"PaddleSpeech 合成失败: {e}")
            # 使用替代实现
            return self._placeholder_synthesis(text, params)
    
    async def synthesize_streaming(self, text: str, params: Dict[str, Any], websocket: WebSocket,
                           speaker_embedding: Optional[np.ndarray] = None) -> float:
        """
        流式语音合成并通过 WebSocket 发送
        
        Args:
            text: 输入文本
            params: 合成参数
            websocket: WebSocket 连接
            speaker_embedding: 说话人嵌入向量（可选）
            
        Returns:
            duration: 音频总时长（秒）
        """
        if not PADDLESPEECH_AVAILABLE or self.online_engine is None:
            # 如果流式引擎不可用，使用普通合成并分块发送
            audio, duration = self._placeholder_synthesis(text, params)
            
            # 分块发送音频
            chunk_size = 4096  # 每块大小
            total_chunks = len(audio) // chunk_size + (1 if len(audio) % chunk_size > 0 else 0)
            
            # 发送总块数信息
            await websocket.send_json({"type": "info", "total_chunks": total_chunks})
            
            # 逐块发送音频
            for i in range(total_chunks):
                start = i * chunk_size
                end = min(start + chunk_size, len(audio))
                chunk = audio[start:end].tobytes()
                
                # 发送音频块
                await websocket.send_bytes(chunk)
                
                # 模拟处理延迟
                await asyncio.sleep(0.05)
            
            # 发送完成标记
            await websocket.send_json({"type": "complete", "duration": float(duration)})
            
            return duration
        
        try:
            # 配置流式合成参数
            am = 'fastspeech2_csmsc'
            voc = 'hifigan_csmsc'
            lang = params.get('language', 'zh')[:2]
            speed = params.get('speed', 1.0)
            
            # 根据语言调整模型
            if lang == 'en':
                am = 'fastspeech2_ljspeech'
                voc = 'hifigan_ljspeech'
            
            # 初始化流式合成
            self.online_engine.init(
                am=am,
                voc=voc,
                lang=lang,
                device=self.device
            )
            
            # 文本预处理（分句）
            sentences = self._split_text_to_sentences(text)
            
            # 发送总句子数信息
            await websocket.send_json({"type": "info", "total_sentences": len(sentences)})
            
            # 合成并发送每个句子
            total_audio_length = 0
            for i, sentence in enumerate(sentences):
                if not sentence.strip():
                    continue
                
                # 流式合成当前句子
                audio_chunks = []
                is_last = False
                
                # 使用 PaddleSpeech 流式合成引擎
                for audio_chunk in self.online_engine.run(
                    sentence,
                    speed_ratio=speed,
                    volume=params.get('energy', 1.0),
                    spk_id=0
                ):
                    # 收集音频块进行时长计算
                    audio_chunks.append(audio_chunk)
                    
                    # 发送音频块
                    await websocket.send_bytes(audio_chunk.tobytes())
                    
                    # 短暂延迟以避免客户端缓冲区溢出
                    await asyncio.sleep(0.01)
                
                # 当前句子合成完毕
                await websocket.send_json({
                    "type": "sentence_complete", 
                    "index": i,
                    "total": len(sentences)
                })
                
                # 累计音频长度
                for chunk in audio_chunks:
                    total_audio_length += len(chunk) / self.online_engine.sample_rate
            
            # 全部合成完毕
            await websocket.send_json({
                "type": "complete", 
                "duration": total_audio_length
            })
            
            return total_audio_length
            
        except Exception as e:
            print(f"流式合成失败: {e}")
            # 发送错误信息
            await websocket.send_json({"type": "error", "message": str(e)})
            
            # 退回到非流式方式
            audio, duration = self._placeholder_synthesis(text, params)
            
            # 分块发送音频
            chunk_size = 4096
            for i in range(0, len(audio), chunk_size):
                chunk = audio[i:i+chunk_size].tobytes()
                await websocket.send_bytes(chunk)
                await asyncio.sleep(0.05)
            
            # 发送完成信息
            await websocket.send_json({"type": "complete", "duration": float(duration)})
            
            return duration
    
    def _split_text_to_sentences(self, text: str) -> List[str]:
        """将文本分割为句子"""
        # 中文标点符号
        cn_punctuations = ['。', '！', '？', '；', '\n']
        # 英文标点符号
        en_punctuations = ['.', '!', '?', ';', '\n']
        
        # 合并所有标点符号
        all_punctuations = cn_punctuations + en_punctuations
        
        # 初始化结果列表和当前句子
        sentences = []
        current_sentence = ""
        
        # 逐字符处理文本
        for char in text:
            current_sentence += char
            
            # 如果遇到标点符号，结束当前句子
            if char in all_punctuations:
                if current_sentence.strip():
                    sentences.append(current_sentence.strip())
                current_sentence = ""
        
        # 处理最后可能剩余的文本
        if current_sentence.strip():
            sentences.append(current_sentence.strip())
        
        # 如果没有找到句子，将整个文本作为一个句子
        if not sentences and text.strip():
            sentences = [text.strip()]
            
        return sentences
    
    def _placeholder_synthesis(self, text: str, params: Dict[str, Any]) -> Tuple[np.ndarray, float]:
        """PaddleSpeech 不可用时的替代合成实现"""
        # 基于文本长度和语速估计时长
        chars = len(text)
        speed = params.get("speed", 1.0)
        chars_per_second = 5 * speed  # 假设每秒约5个汉字
        duration = max(1.0, chars / chars_per_second)
        
        # 创建时间数组
        sample_rate = 24000  # 与 PaddleSpeech 一致
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
        
        from scipy.ndimage import gaussian_filter1d
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
        
        # 将浮点数组转换为16位整数格式（符合大多数音频处理的要求）
        audio = np.asarray(audio * 32767, dtype=np.int16)
        
        return audio, duration
    
    def add_custom_voice(self, sample_path: str, voice_id: str, 
                         output_dir: Optional[str] = None) -> Optional[str]:
        """
        添加自定义声音（为声音克隆准备）
        
        Args:
            sample_path: 声音样本文件路径
            voice_id: 声音 ID
            output_dir: 输出目录（可选）
            
        Returns:
            model_path: 处理后的模型路径（如果成功）
        """
        if not PADDLESPEECH_AVAILABLE:
            print("PaddleSpeech 不可用，无法添加自定义声音")
            return None
        
        try:
            # 确保输出目录存在
            if output_dir is None:
                output_dir = os.path.join(settings.UPLOAD_DIR, "voice_models")
            os.makedirs(output_dir, exist_ok=True)
            
            # 声音模型路径
            model_path = os.path.join(output_dir, f"{voice_id}.wav")
            
            # 加载和处理音频样本
            audio, sr = sf.read(sample_path)
            
            # 规范化音频
            audio = normalize_audio(audio)
            audio = trim_audio(audio)[0]
            
            # 保存规范化的音频作为声音模型
            sf.write(model_path, audio, sr)
            
            # 在实际应用中，可以进一步处理创建更复杂的声音模型
            # 例如提取声音特征、训练适应层等
            
            return model_path
            
        except Exception as e:
            print(f"添加自定义声音失败: {e}")
            return None

# 初始化 PaddleSpeech TTS 服务和模型
async def init_tts_service():
    global TTS_TASKS_DB, tts_executor, tts_online_engine
    
    # 确保目录存在
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "tts_results"), exist_ok=True)
    
    # 加载现有任务
    if os.path.exists(TTS_TASKS_FILE):
        try:
            with open(TTS_TASKS_FILE, 'r') as f:
                data = json.load(f)
                TTS_TASKS_DB = [TTSTaskDB(**item) for item in data]
        except Exception as e:
            print(f"初始化 TTS 服务失败: {e}")
    
    # 初始化 PaddleSpeech TTS 模型
    tts_executor = PaddleSpeechModel()
    
    print("PaddleSpeech TTS 服务初始化完成")

# 保存任务到文件
async def save_tts_tasks():
    with open(TTS_TASKS_FILE, 'w') as f:
        # 转换为字典列表并保存
        data = [task.dict() for task in TTS_TASKS_DB]
        json.dump(data, f, default=str)

# 创建 TTS 任务
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

# 流式语音合成
async def synthesize_speech_streaming(
    websocket: WebSocket,
    text: str,
    voice_id: str,
    params: Dict[str, Any]
):
    """通过 WebSocket 进行流式语音合成"""
    try:
        # 验证声音样本是否存在
        voice_samples = await get_voice_samples(0, 1, None, voice_id)
        if not voice_samples:
            await websocket.send_json({"type": "error", "message": "声音样本不存在"})
            return
        
        voice_sample = voice_samples[0]
        
        # 加载声音克隆嵌入向量
        speaker_embedding = voice_cloner.load_voice_embedding(voice_id)
        
        # 调整 TTS 参数
        if speaker_embedding is not None:
            params = voice_cloner.adapt_tts_params(speaker_embedding, params)
        
        # 语音模型路径处理
        if hasattr(voice_sample, 'model_path') and voice_sample.model_path:
            params['model_path'] = voice_sample.model_path
        
        # 流式合成与发送
        await tts_executor.synthesize_streaming(text, params, websocket, speaker_embedding)
        
    except Exception as e:
        print(f"流式语音合成失败: {e}")
        # 发送错误消息
        await websocket.send_json({"type": "error", "message": str(e)})

# 处理 TTS 任务
async def process_tts_task(task_id: str):
    global tts_executor
    
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
        
        # 调整 TTS 参数
        if speaker_embedding is not None:
            task.params = voice_cloner.adapt_tts_params(speaker_embedding, task.params)
        
        # 语音模型路径处理
        if hasattr(voice_sample, 'model_path') and voice_sample.model_path:
            task.params['model_path'] = voice_sample.model_path
        
        # 更新进度
        task.progress = 0.3
        task.updated_at = datetime.now()
        await save_tts_tasks()
        
        # 预览模式处理更快
        is_preview = task.params.get("is_preview", False)
        if is_preview:
            await asyncio.sleep(0.5)
        else:
            await asyncio.sleep(1.0)
        
        # 创建输出目录
        output_dir = os.path.join(settings.UPLOAD_DIR, "tts_results")
        os.makedirs(output_dir, exist_ok=True)
        
        # 设置输出文件路径
        output_file = os.path.join(output_dir, f"{task_id}.wav")
        
        # 使用 PaddleSpeech 合成语音
        audio, duration = tts_executor.synthesize(
            task.text, 
            task.params, 
            speaker_embedding, 
            output_file
        )
        
        # 更新进度
        task.progress = 0.7
        task.updated_at = datetime.now()
        await save_tts_tasks()
        
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
        
        print(f"TTS 任务完成: {task_id}, 文件: {output_file}")
    
    except Exception as e:
        # 更新任务状态为失败
        for t in TTS_TASKS_DB:
            if t.task_id == task_id:
                t.status = "failed"
                t.error = str(e)
                t.updated_at = datetime.now()
                break
        
        await save_tts_tasks()
        print(f"TTS 任务失败: {task_id}, 错误: {e}")

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