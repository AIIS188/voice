"""CosyVoice TTS 服务模块

这个模块封装了CosyVoice TTS模型的功能，提供了语音合成服务。
"""
import os
import sys
import json
import time
import asyncio
import tempfile
import numpy as np
import torch
import torchaudio
import librosa
import soundfile as sf
from typing import Dict, Any, Optional, List, Tuple, BinaryIO
from datetime import datetime
from pathlib import Path
from fastapi import BackgroundTasks, WebSocket
from app.services.voice_clone import voice_cloner
from app.models.tts import TTSTaskDB, TTSTaskStatus, TTSParams
from app.services.voice_service import get_voice_samples
from app.core.config import settings

# 获取当前目录并添加CosyVoice路径
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COSYVOICE_PATH = os.path.join(ROOT_DIR, "third_party", "CosyVoice")

# 检查CosyVoice路径是否存在
if os.path.exists(COSYVOICE_PATH):
    sys.path.append(COSYVOICE_PATH)
    # 尝试导入CosyVoice
    try:
        from cosyvoice.cli.cosyvoice import CosyVoice, CosyVoice2
        from cosyvoice.utils.file_utils import load_wav, logging
        from cosyvoice.utils.common import set_all_random_seed
        COSYVOICE_AVAILABLE = True
        print("CosyVoice 模块加载成功")
    except ImportError as e:
        print(f"导入 CosyVoice 失败: {e}")
        COSYVOICE_AVAILABLE = False
else:
    print(f"CosyVoice 路径不存在: {COSYVOICE_PATH}")
    COSYVOICE_AVAILABLE = False

# 全局变量
TTS_TASKS_DB = []
TTS_TASKS_FILE = os.path.join(settings.UPLOAD_DIR, "cosyvoice_tts_tasks.json")
cosyvoice_model = None
max_val = 0.8  # 音频归一化最大值

class CosyVoiceTTS:
    """CosyVoice TTS 模型封装类"""
    
    def __init__(self, model_dir=None):
        """初始化 CosyVoice TTS 模型
        
        Args:
            model_dir: 模型目录路径，默认使用配置中的路径
        """
        if not COSYVOICE_AVAILABLE:
            print("CosyVoice 不可用，将使用替代实现")
            self.model = None
            self.sample_rate = 16000
            self.available_spks = []
            self.instruct = False
            return
        
        # 如果未指定模型目录，使用配置中的路径
        if model_dir is None:
            model_dir = settings.COSYVOICE_MODEL_DIR
            
        if not os.path.exists(model_dir):
            print(f"模型目录不存在: {model_dir}")
            try:
                # 尝试从ModelScope下载
                print(f"尝试从ModelScope下载模型: {model_dir}")
                model_dir = model_dir  # 这里可以添加模型下载逻辑
            except Exception as e:
                print(f"模型下载失败: {e}")
                self.model = None
                self.sample_rate = 16000
                self.available_spks = []
                self.instruct = False
                return
        
        try:
            # 尝试加载CosyVoice模型
            self.model = CosyVoice(model_dir)
            print(f"CosyVoice 模型加载成功: {model_dir}")
        except Exception:
            try:
                # 尝试加载CosyVoice2模型
                self.model = CosyVoice2(model_dir)
                print(f"CosyVoice2 模型加载成功: {model_dir}")
            except Exception as e:
                print(f"加载模型失败: {e}")
                self.model = None
                self.sample_rate = 16000
                self.available_spks = []
                self.instruct = False
                return
        
        # 获取模型属性
        self.sample_rate = self.model.sample_rate
        self.available_spks = self.model.list_available_spks()
        if len(self.available_spks) == 0:
            self.available_spks = ['']
        
        # 判断是否支持指令控制
        try:
            self.instruct = self.model.instruct
        except AttributeError:
            # 如果模型没有instruct属性，默认为False
            self.instruct = False
    
    def postprocess(self, speech, top_db=60, hop_length=220, win_length=440):
        """后处理音频信号
        
        Args:
            speech: 音频信号
            top_db: 静音检测分贝阈值
            hop_length: 帧移
            win_length: 窗长
            
        Returns:
            处理后的音频信号
        """
        # 裁剪静音部分
        speech, _ = librosa.effects.trim(
            speech, top_db=top_db,
            frame_length=win_length,
            hop_length=hop_length
        )
        
        # 归一化音量
        if speech.abs().max() > max_val:
            speech = speech / speech.abs().max() * max_val
            
        # 添加尾部空白
        speech = torch.concat([speech, torch.zeros(1, int(self.sample_rate * 0.2))], dim=1)
        
        return speech
    
    def synthesize(self, text: str, params: Dict[str, Any], 
                  voice_id: Optional[str] = None,
                  prompt_audio: Optional[str] = None,
                  prompt_text: Optional[str] = None,
                  instruct_text: Optional[str] = None,
                  output_path: Optional[str] = None) -> Tuple[np.ndarray, float]:
        """
        使用 CosyVoice 合成语音
        
        Args:
            text: 要合成的文本
            params: 合成参数
            voice_id: 预训练音色ID
            prompt_audio: 参考音频文件路径（用于声音克隆）
            prompt_text: 参考音频对应的文本（用于3s极速复刻）
            instruct_text: 指令文本（用于自然语言控制）
            output_path: 输出文件路径（可选）
            
        Returns:
            audio: 音频波形
            duration: 音频时长（秒）
        """
        if not COSYVOICE_AVAILABLE or self.model is None:
            print("CosyVoice 不可用，使用替代实现")
            return self._placeholder_synthesis(text, params)
        
        try:
            # 设置随机种子
            seed = params.get('seed', 0)
            set_all_random_seed(seed)
            
            # 设置推理速度
            speed = params.get('speed', 1.0)
            
            # 确定推理模式
            mode = params.get('mode', 'sft')
            stream = params.get('stream', False)
            
            # 根据模式选择推理方法
            if mode == 'sft':
                # 预训练音色模式
                if voice_id is None or voice_id not in self.available_spks:
                    print(f"无效的预训练音色ID: {voice_id}")
                    voice_id = self.available_spks[0] if self.available_spks else ""
                
                result = next(self.model.inference_sft(
                    text, voice_id, stream=stream, speed=speed
                ))
                
            elif mode == 'zero_shot':
                # 3s极速复刻模式
                if prompt_audio is None:
                    raise ValueError("3s极速复刻模式需要提供参考音频")
                
                if prompt_text is None or prompt_text == "":
                    raise ValueError("3s极速复刻模式需要提供参考文本")
                
                # 加载并处理参考音频
                prompt_speech = self.postprocess(load_wav(prompt_audio, 16000))
                
                result = next(self.model.inference_zero_shot(
                    text, prompt_text, prompt_speech, stream=stream, speed=speed
                ))
                
            elif mode == 'cross_lingual':
                # 跨语种复刻模式
                if prompt_audio is None:
                    raise ValueError("跨语种复刻模式需要提供参考音频")
                
                if self.instruct:
                    print("警告: 跨语种复刻模式不支持指令控制模型")
                
                # 加载并处理参考音频
                prompt_speech = self.postprocess(load_wav(prompt_audio, 16000))
                
                result = next(self.model.inference_cross_lingual(
                    text, prompt_speech, stream=stream, speed=speed
                ))
                
            elif mode == 'instruct':
                # 自然语言控制模式
                if not self.instruct:
                    print("警告: 当前模型不支持指令控制模式")
                    # 退回到预训练音色模式
                    return self.synthesize(text, params, voice_id, prompt_audio, prompt_text, None, output_path)
                
                if instruct_text is None or instruct_text == "":
                    raise ValueError("指令控制模式需要提供指令文本")
                
                if voice_id is None or voice_id not in self.available_spks:
                    print(f"无效的预训练音色ID: {voice_id}")
                    voice_id = self.available_spks[0] if self.available_spks else ""
                
                result = next(self.model.inference_instruct(
                    text, voice_id, instruct_text, stream=stream, speed=speed
                ))
            
            else:
                raise ValueError(f"未知的推理模式: {mode}")
            
            # 获取合成的音频
            speech = result['tts_speech'].numpy().flatten()
            
            # 计算音频时长
            duration = len(speech) / self.sample_rate
            
            # 如果指定了输出路径，保存音频
            if output_path:
                sf.write(output_path, speech, self.sample_rate)
            
            return speech, duration
            
        except Exception as e:
            print(f"CosyVoice 合成失败: {e}")
            # 使用替代实现
            return self._placeholder_synthesis(text, params)
    
    async def synthesize_streaming(self, text: str, params: Dict[str, Any], websocket: WebSocket,
                           voice_id: Optional[str] = None,
                           prompt_audio: Optional[str] = None,
                           prompt_text: Optional[str] = None,
                           instruct_text: Optional[str] = None) -> float:
        """
        流式语音合成并通过 WebSocket 发送
        
        Args:
            text: 输入文本
            params: 合成参数
            websocket: WebSocket 连接
            voice_id: 预训练音色ID
            prompt_audio: 参考音频文件路径
            prompt_text: 参考音频对应的文本
            instruct_text: 指令文本
            
        Returns:
            duration: 音频总时长（秒）
        """
        if not COSYVOICE_AVAILABLE or self.model is None:
            # 使用非流式合成并分块发送
            audio, duration = self._placeholder_synthesis(text, params)
            
            # 发送总块数信息
            chunk_size = 4096
            total_chunks = (len(audio) + chunk_size - 1) // chunk_size
            await websocket.send_json({"type": "info", "total_chunks": total_chunks})
            
            # 逐块发送音频
            for i in range(0, len(audio), chunk_size):
                chunk = audio[i:i+chunk_size].tobytes()
                await websocket.send_bytes(chunk)
                await asyncio.sleep(0.05)
            
            # 发送完成标记
            await websocket.send_json({"type": "complete", "duration": float(duration)})
            
            return duration
        
        try:
            # 设置随机种子和速度
            seed = params.get('seed', 0)
            speed = params.get('speed', 1.0)
            set_all_random_seed(seed)
            
            # 确定推理模式
            mode = params.get('mode', 'sft')
            stream = True  # 强制流式推理
            
            # 获取迭代器
            if mode == 'sft':
                if voice_id is None or voice_id not in self.available_spks:
                    await websocket.send_json({"type": "error", "message": f"无效的预训练音色ID: {voice_id}"})
                    return 0
                
                iterator = self.model.inference_sft(text, voice_id, stream=stream, speed=speed)
                
            elif mode == 'zero_shot':
                if prompt_audio is None:
                    await websocket.send_json({"type": "error", "message": "3s极速复刻模式需要提供参考音频"})
                    return 0
                
                if prompt_text is None or prompt_text == "":
                    await websocket.send_json({"type": "error", "message": "3s极速复刻模式需要提供参考文本"})
                    return 0
                
                # 加载并处理参考音频
                prompt_speech = self.postprocess(load_wav(prompt_audio, 16000))
                
                iterator = self.model.inference_zero_shot(text, prompt_text, prompt_speech, stream=stream, speed=speed)
                
            elif mode == 'cross_lingual':
                if prompt_audio is None:
                    await websocket.send_json({"type": "error", "message": "跨语种复刻模式需要提供参考音频"})
                    return 0
                
                if self.instruct:
                    await websocket.send_json({"type": "warning", "message": "跨语种复刻模式不支持指令控制模型"})
                
                # 加载并处理参考音频
                prompt_speech = self.postprocess(load_wav(prompt_audio, 16000))
                
                iterator = self.model.inference_cross_lingual(text, prompt_speech, stream=stream, speed=speed)
                
            elif mode == 'instruct':
                if not self.instruct:
                    await websocket.send_json({"type": "warning", "message": "当前模型不支持指令控制模式"})
                    # 退回到预训练音色模式
                    return await self.synthesize_streaming(text, {**params, "mode": "sft"}, websocket, voice_id)
                
                if instruct_text is None or instruct_text == "":
                    await websocket.send_json({"type": "error", "message": "指令控制模式需要提供指令文本"})
                    return 0
                
                if voice_id is None or voice_id not in self.available_spks:
                    await websocket.send_json({"type": "warning", "message": f"无效的预训练音色ID: {voice_id}"})
                    voice_id = self.available_spks[0] if self.available_spks else ""
                
                iterator = self.model.inference_instruct(text, voice_id, instruct_text, stream=stream, speed=speed)
            
            else:
                await websocket.send_json({"type": "error", "message": f"未知的推理模式: {mode}"})
                return 0
            
            # 发送开始信息
            await websocket.send_json({"type": "info", "message": "开始合成"})
            
            # 逐个发送音频块
            total_duration = 0
            chunk_index = 0
            
            for result in iterator:
                # 获取音频数据
                speech = result['tts_speech'].numpy().flatten()
                
                # 发送音频块
                await websocket.send_bytes(speech.tobytes())
                
                # 计算时长
                chunk_duration = len(speech) / self.sample_rate
                total_duration += chunk_duration
                
                # 发送进度信息
                await websocket.send_json({
                    "type": "progress",
                    "chunk_index": chunk_index,
                    "duration": chunk_duration
                })
                
                chunk_index += 1
                
                # 短暂延迟
                await asyncio.sleep(0.01)
            
            # 发送完成信息
            await websocket.send_json({
                "type": "complete",
                "duration": total_duration,
                "chunks": chunk_index
            })
            
            return total_duration
            
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
    
    def _placeholder_synthesis(self, text: str, params: Dict[str, Any]) -> Tuple[np.ndarray, float]:
        """CosyVoice 不可用时的替代合成实现"""
        # 基于文本长度和语速估计时长
        chars = len(text)
        speed = params.get("speed", 1.0)
        chars_per_second = 5 * speed  # 假设每秒约5个汉字
        duration = max(1.0, chars / chars_per_second)
        
        # 创建时间数组
        sample_rate = self.sample_rate
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
        
        try:
            from scipy.ndimage import gaussian_filter1d
            envelope = gaussian_filter1d(envelope, sigma=0.01 * sample_rate)
        except ImportError:
            # 如果没有scipy，使用简单平滑
            smooth_window = int(0.01 * sample_rate)
            if smooth_window > 1:
                envelope_smooth = np.zeros_like(envelope)
                for i in range(len(envelope)):
                    start = max(0, i - smooth_window // 2)
                    end = min(len(envelope), i + smooth_window // 2)
                    envelope_smooth[i] = np.mean(envelope[start:end])
                envelope = envelope_smooth
        
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
    
    def get_available_voices(self) -> List[str]:
        """获取可用的预训练音色列表"""
        return self.available_spks

# 初始化 CosyVoice TTS 服务和模型
async def init_cosyvoice_tts_service():
    global TTS_TASKS_DB, cosyvoice_model
    
    # 确保目录存在
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "cosyvoice_results"), exist_ok=True)
    
    # 加载现有任务
    if os.path.exists(TTS_TASKS_FILE):
        try:
            with open(TTS_TASKS_FILE, 'r') as f:
                data = json.load(f)
                TTS_TASKS_DB = [TTSTaskDB(**item) for item in data]
        except Exception as e:
            print(f"初始化 CosyVoice TTS 服务失败: {e}")
    
    # 初始化 CosyVoice TTS 模型
    cosyvoice_model = CosyVoiceTTS()
    
    print("CosyVoice TTS 服务初始化完成")

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
    params: Dict[str, Any],
    prompt_audio: Optional[str] = None,
    prompt_text: Optional[str] = None,
    instruct_text: Optional[str] = None
) -> str:
    """
    创建语音合成任务
    
    Args:
        background_tasks: 后台任务
        text: 要合成的文本
        voice_id: 声音ID
        params: 合成参数
        prompt_audio: 参考音频文件路径
        prompt_text: 参考音频对应的文本
        instruct_text: 指令文本
        
    Returns:
        task_id: 任务ID
    """
    # 验证参数
    if not text:
        raise ValueError("合成文本不能为空")
    
    # 创建任务记录
    task_id = f"cosyvoice_tts_{int(time.time())}_{voice_id[:8] if voice_id else 'default'}"
    
    # 增强参数
    enhanced_params = params.copy()
    if prompt_audio:
        enhanced_params["prompt_audio"] = prompt_audio
    if prompt_text:
        enhanced_params["prompt_text"] = prompt_text
    if instruct_text:
        enhanced_params["instruct_text"] = instruct_text
    
    # 创建任务对象
    task = TTSTaskDB(
        task_id=task_id,
        text=text,
        voice_id=voice_id,
        params=enhanced_params,
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
    params: Dict[str, Any],
    prompt_audio: Optional[str] = None,
    prompt_text: Optional[str] = None,
    instruct_text: Optional[str] = None
):
    """
    通过 WebSocket 进行流式语音合成
    
    Args:
        websocket: WebSocket 连接
        text: 要合成的文本
        voice_id: 声音ID
        params: 合成参数
        prompt_audio: 参考音频文件路径
        prompt_text: 参考音频对应的文本
        instruct_text: 指令文本
    """
    try:
        # 合成参数处理
        streaming_params = params.copy()
        streaming_params["stream"] = True
        
        # 流式合成与发送
        await cosyvoice_model.synthesize_streaming(
            text, 
            streaming_params, 
            websocket, 
            voice_id, 
            prompt_audio, 
            prompt_text, 
            instruct_text
        )
        
    except Exception as e:
        print(f"流式语音合成失败: {e}")
        # 发送错误消息
        await websocket.send_json({"type": "error", "message": str(e)})

# 处理 TTS 任务
async def process_tts_task(task_id: str):
    global cosyvoice_model
    
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
        
        # 提取参数
        prompt_audio = task.params.get("prompt_audio")
        prompt_text = task.params.get("prompt_text")
        instruct_text = task.params.get("instruct_text")
        
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
        output_dir = os.path.join(settings.UPLOAD_DIR, "cosyvoice_results")
        os.makedirs(output_dir, exist_ok=True)
        
        # 设置输出文件路径
        output_file = os.path.join(output_dir, f"{task_id}.wav")
        
        # 使用 CosyVoice 合成语音
        speech, duration = cosyvoice_model.synthesize(
            task.text, 
            task.params, 
            task.voice_id, 
            prompt_audio, 
            prompt_text, 
            instruct_text, 
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
        
        print(f"CosyVoice TTS 任务完成: {task_id}, 文件: {output_file}")
    
    except Exception as e:
        # 更新任务状态为失败
        for t in TTS_TASKS_DB:
            if t.task_id == task_id:
                t.status = "failed"
                t.error = str(e)
                t.updated_at = datetime.now()
                break
        
        await save_tts_tasks()
        print(f"CosyVoice TTS 任务失败: {task_id}, 错误: {e}")