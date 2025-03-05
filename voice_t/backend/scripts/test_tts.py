#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TTS功能测试脚本
该脚本用于测试FastSpeech2+HiFi-GAN TTS系统的功能
"""

import os
import sys
import asyncio
import argparse
from fastapi import BackgroundTasks

# 确保能找到app模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.tts_service import synthesize_speech, get_tts_task_status, get_tts_task_result
from app.core.config import settings

async def test_tts(text, voice_id, language="zh", speed=1.0, pitch=0.0, energy=1.0, emotion="neutral"):
    """测试TTS功能"""
    # 创建BackgroundTasks对象
    bg_tasks = BackgroundTasks()
    
    # 构建TTS参数
    params = {
        "speed": speed,
        "pitch": pitch,
        "energy": energy,
        "emotion": emotion,
        "language": language
    }
    
    print(f"测试文本: {text}")
    print(f"使用语音ID: {voice_id}")
    print(f"参数: {params}")
    
    try:
        # 提交任务
        print("\n步骤1: 提交TTS任务...")
        task_id = await synthesize_speech(bg_tasks, text, voice_id, params)
        print(f"任务ID: {task_id}")
        
        # 手动执行后台任务（因为我们不在FastAPI环境中）
        print("\n步骤2: 执行TTS合成...")
        await bg_tasks()
        
        # 检查任务状态
        print("\n步骤3: 监控任务状态...")
        while True:
            status = await get_tts_task_status(task_id)
            print(f"状态: {status.status}, 进度: {status.progress:.1%}")
            
            if status.status in ["completed", "failed"]:
                break
            
            await asyncio.sleep(1)
        
        # 获取任务结果
        print("\n步骤4: 获取任务结果...")
        if status.status == "completed":
            result = await get_tts_task_result(task_id)
            print(f"✓ 任务完成!")
            print(f"  - 音频文件: {result.file_path}")
            print(f"  - 时长: {result.duration:.2f}秒")
            return True, result.file_path
        else:
            print(f"✗ 任务失败: {status.error}")
            return False, None
    
    except Exception as e:
        print(f"✗ 错误: {e}")
        return False, None

def main():
    parser = argparse.ArgumentParser(description='测试TTS功能')
    parser.add_argument('--text', type=str, default='欢迎使用FastSpeech2结合HiFi-GAN的语音合成系统，这是一个测试。',
                        help='要合成的文本')
    parser.add_argument('--voice', type=str, default='preset_1',
                        help='声音样本ID')
    parser.add_argument('--lang', type=str, default='zh', choices=['zh', 'en'],
                        help='语言')
    parser.add_argument('--speed', type=float, default=1.0,
                        help='语速 (0.5-2.0)')
    parser.add_argument('--pitch', type=float, default=0.0,
                        help='音调 (-1.0-1.0)')
    parser.add_argument('--energy', type=float, default=1.0,
                        help='音量 (0.5-2.0)')
    parser.add_argument('--emotion', type=str, default='neutral',
                        choices=['neutral', 'happy', 'sad', 'serious'],
                        help='情感风格')
    args = parser.parse_args()
    
    # 英文测试文本
    if args.lang == 'en' and args.text == parser.get_default('text'):
        args.text = 'Welcome to the text-to-speech system using FastSpeech2 and HiFi-GAN. This is a test.'
    
    # 运行测试
    success, file_path = asyncio.run(test_tts(
        args.text, args.voice, args.lang, args.speed, args.pitch, args.energy, args.emotion
    ))
    
    # 播放生成的音频（如果成功）
    if success and file_path and os.path.exists(file_path):
        print("\n是否播放生成的音频? (y/n): ", end="")
        choice = input().strip().lower()
        if choice == 'y':
            try:
                # 尝试使用系统默认播放器播放
                import platform
                system = platform.system()
                
                if system == 'Darwin':  # macOS
                    os.system(f"afplay \"{file_path}\"")
                elif system == 'Linux':
                    os.system(f"aplay \"{file_path}\"")
                elif system == 'Windows':
                    os.system(f"start \"{file_path}\"")
                else:
                    print("无法识别的操作系统，请手动播放音频文件。")
            except Exception as e:
                print(f"播放音频时出错: {e}")
                print(f"请手动播放音频文件: {file_path}")

if __name__ == '__main__':
    main()