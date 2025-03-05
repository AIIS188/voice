#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FastSpeech2与HiFi-GAN模型下载器
该脚本用于下载预训练的TTS模型文件并放置到正确的目录结构中
"""

import os
import sys
import argparse
import requests
import json
import zipfile
import tarfile
import shutil
from tqdm import tqdm
from pathlib import Path

# 模型信息
MODEL_URLS = {
    "fastspeech2": {
        "zh": "https://huggingface.co/TencentGameMate/Chinese_speech_pretrain/resolve/main/model_ckpt.zip",
        "en": "https://github.com/espnet/espnet/releases/download/v202207/kan-bayashi_ljspeech_fastspeech2.zip"
    },
    "hifigan": {
        "zh": "https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/pretrained_v2/hifigan.zip",
        "en": "https://github.com/jik876/hifi-gan/releases/download/v1/generator_universal.pth.tar"
    }
}

def download_file(url, dest_path):
    """下载文件并显示进度条"""
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    
    with open(dest_path, 'wb') as f, tqdm(
        desc=os.path.basename(dest_path),
        total=total_size,
        unit='B',
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for data in response.iter_content(chunk_size=1024):
            size = f.write(data)
            bar.update(size)

def extract_archive(archive_path, extract_to):
    """解压缩文件"""
    if archive_path.endswith('.zip'):
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            for member in tqdm(zip_ref.infolist(), desc="解压缩"):
                zip_ref.extract(member, extract_to)
    elif archive_path.endswith('.tar.gz') or archive_path.endswith('.tgz'):
        with tarfile.open(archive_path, 'r:gz') as tar_ref:
            for member in tqdm(tar_ref.getmembers(), desc="解压缩"):
                tar_ref.extract(member, extract_to)
    elif archive_path.endswith('.tar'):
        with tarfile.open(archive_path, 'r:') as tar_ref:
            for member in tqdm(tar_ref.getmembers(), desc="解压缩"):
                tar_ref.extract(member, extract_to)
    else:
        print(f"不支持的归档格式: {archive_path}")

def setup_fastspeech2(model_dir, language="zh"):
    """下载和设置FastSpeech2模型"""
    fastspeech2_dir = os.path.join(model_dir, "fastspeech2")
    os.makedirs(fastspeech2_dir, exist_ok=True)
    
    url = MODEL_URLS["fastspeech2"][language]
    filename = url.split('/')[-1]
    download_path = os.path.join(fastspeech2_dir, filename)
    
    print(f"下载FastSpeech2模型 ({language})...")
    download_file(url, download_path)
    
    print("解压FastSpeech2模型...")
    temp_dir = os.path.join(fastspeech2_dir, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    extract_archive(download_path, temp_dir)
    
    # 处理不同语言模型的特定文件结构
    if language == "zh":
        # 根据实际文件结构调整
        try:
            # 查找并复制模型文件
            model_files = list(Path(temp_dir).glob("**/model*.pt"))
            if model_files:
                shutil.copy(str(model_files[0]), os.path.join(fastspeech2_dir, "model.pt"))
            
            # 创建配置文件
            config = {
                "model_type": "fastspeech2",
                "language": "zh",
                "sample_rate": 22050,
                "hop_length": 256
            }
            with open(os.path.join(fastspeech2_dir, "config.json"), 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"处理中文FastSpeech2模型时出错: {e}")
    
    elif language == "en":
        # 英文模型处理
        try:
            # 查找并复制模型文件
            model_files = list(Path(temp_dir).glob("**/model*.pt"))
            if model_files:
                shutil.copy(str(model_files[0]), os.path.join(fastspeech2_dir, "model.pt"))
            
            # 查找并复制配置文件
            config_files = list(Path(temp_dir).glob("**/config*.json"))
            if config_files:
                shutil.copy(str(config_files[0]), os.path.join(fastspeech2_dir, "config.json"))
            else:
                # 创建基本配置
                config = {
                    "model_type": "fastspeech2",
                    "language": "en",
                    "sample_rate": 22050,
                    "hop_length": 256
                }
                with open(os.path.join(fastspeech2_dir, "config.json"), 'w') as f:
                    json.dump(config, f, indent=2)
        except Exception as e:
            print(f"处理英文FastSpeech2模型时出错: {e}")
    
    # 清理临时文件
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    
    print(f"FastSpeech2模型 ({language}) 设置完成!")

def setup_hifigan(model_dir, language="zh"):
    """下载和设置HiFi-GAN模型"""
    hifigan_dir = os.path.join(model_dir, "hifigan")
    os.makedirs(hifigan_dir, exist_ok=True)
    
    url = MODEL_URLS["hifigan"][language]
    filename = url.split('/')[-1]
    download_path = os.path.join(hifigan_dir, filename)
    
    print(f"下载HiFi-GAN模型 ({language})...")
    download_file(url, download_path)
    
    # 处理不同格式的文件
    if download_path.endswith('.zip'):
        print("解压HiFi-GAN模型...")
        temp_dir = os.path.join(hifigan_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        extract_archive(download_path, temp_dir)
        
        # 根据实际文件结构调整
        try:
            # 查找并复制模型文件
            model_files = list(Path(temp_dir).glob("**/generator*.pt*"))
            if model_files:
                shutil.copy(str(model_files[0]), os.path.join(hifigan_dir, "generator.pt"))
                
            # 查找并复制配置文件
            config_files = list(Path(temp_dir).glob("**/config*.json"))
            if config_files:
                shutil.copy(str(config_files[0]), os.path.join(hifigan_dir, "config.json"))
            else:
                # 创建基本配置
                config = {
                    "model_type": "hifigan",
                    "language": language,
                    "sample_rate": 22050
                }
                with open(os.path.join(hifigan_dir, "config.json"), 'w') as f:
                    json.dump(config, f, indent=2)
        except Exception as e:
            print(f"处理HiFi-GAN模型时出错: {e}")
        
        # 清理临时文件
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    else:
        # 直接重命名为generator.pt
        shutil.copy(download_path, os.path.join(hifigan_dir, "generator.pt"))
        
        # 创建基本配置
        config = {
            "model_type": "hifigan",
            "language": language,
            "sample_rate": 22050
        }
        with open(os.path.join(hifigan_dir, "config.json"), 'w') as f:
            json.dump(config, f, indent=2)
    
    print(f"HiFi-GAN模型 ({language}) 设置完成!")

def main():
    parser = argparse.ArgumentParser(description='下载FastSpeech2和HiFi-GAN模型')
    parser.add_argument('--dir', type=str, default='../models/weights/tts',
                        help='模型保存目录')
    parser.add_argument('--language', type=str, default='zh', choices=['zh', 'en'],
                        help='模型语言，中文(zh)或英文(en)')
    args = parser.parse_args()
    
    # 创建模型目录
    os.makedirs(args.dir, exist_ok=True)
    
    print("开始下载TTS模型...\n")
    
    # 下载FastSpeech2
    setup_fastspeech2(args.dir, args.language)
    
    print("\n")
    
    # 下载HiFi-GAN
    setup_hifigan(args.dir, args.language)
    
    print("\n所有模型下载完成！模型文件保存在:", args.dir)

if __name__ == '__main__':
    main()