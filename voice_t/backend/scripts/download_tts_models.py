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
import time
from tqdm import tqdm
from pathlib import Path

# 更新后的模型URL
MODEL_URLS = {
    "fastspeech2": {
        # 替代的中文FastSpeech2模型URL
        "zh": "https://huggingface.co/espnet/kan-bayashi_csmsc_tts_train_fastspeech2_raw_phn_pypinyin_g2p_phone_train.loss.ave/resolve/main/model.pth",
        # 替代的英文FastSpeech2模型URL
        "en": "https://huggingface.co/espnet/kan-bayashi_ljspeech_tts_train_fastspeech2_raw_phn_tacotron_g2p_en_no_space_train.loss.ave/resolve/main/exp/tts_train_fastspeech2_raw_phn_tacotron_g2p_en_no_space/train.loss.ave_5best.pth"
    },
    "hifigan": {
        # 替代的中文HiFi-GAN模型URL
        "zh": "https://huggingface.co/espnet/kan-bayashi_csmsc_tts_train_hifigan_raw_phn_pypinyin_g2p_phone_train.total_count.ave/resolve/main/model.pth",
        # 替代的英文HiFi-GAN模型URL
        "en": "https://github.com/jik876/hifi-gan/raw/master/LJ_FT_T2_V1/generator_v1"
    }
}

def download_file(url, dest_path, max_retries=3):
    """下载文件并显示进度条，返回下载是否成功"""
    for retry in range(max_retries):
        try:
            print(f"下载中... 尝试 {retry+1}/{max_retries}")
            print(f"下载URL: {url}")
            
            # 添加请求头，避免被拒绝访问
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            response = requests.get(url, stream=True, headers=headers)
            response.raise_for_status()  # 检查HTTP错误
            
            expected_size = int(response.headers.get('content-length', 0))
            print(f"预期文件大小: {expected_size} 字节")
            
            with open(dest_path, 'wb') as f, tqdm(
                desc=os.path.basename(dest_path),
                total=expected_size if expected_size > 0 else None,  # 有些服务器可能不返回content-length
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for data in response.iter_content(chunk_size=1024):
                    size = f.write(data)
                    bar.update(size)
            
            # 下载后检查文件大小
            actual_size = os.path.getsize(dest_path)
            print(f"实际下载大小: {actual_size} 字节")
            
            if expected_size > 0 and actual_size < expected_size * 0.99:  # 允许1%的误差
                print(f"警告: 下载的文件不完整 ({actual_size}/{expected_size})")
                if retry < max_retries - 1:
                    print("重试下载...")
                    time.sleep(2)  # 等待一会再重试
                    continue
                return False
            return True
        except Exception as e:
            print(f"下载失败: {e}")
            if retry < max_retries - 1:
                print("重试下载...")
                time.sleep(2)  # 等待一会再重试
            else:
                return False
    return False

def extract_archive(archive_path, extract_to):
    """解压缩文件，使用多种方法确保成功"""
    print(f"开始解压: {archive_path} 到 {extract_to}")
    
    # 检查文件是否存在且大小合理
    if not os.path.exists(archive_path):
        print(f"错误: 文件不存在 - {archive_path}")
        return False
    
    file_size = os.path.getsize(archive_path)
    if file_size < 1000:  # 文件太小，可能有问题
        print(f"错误: 文件太小 ({file_size} 字节)，可能不完整")
        return False
    
    # 检查文件类型
    if archive_path.endswith(('.pth', '.pt')):
        print(f"文件 {archive_path} 似乎是一个模型文件，不需要解压")
        return True  # 这是一个模型文件，不需要解压
    
    # 首先尝试使用zipfile/tarfile库解压
    try:
        if archive_path.endswith('.zip'):
            print("使用zipfile库解压...")
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                # 获取文件列表并打印
                file_list = zip_ref.namelist()
                print(f"ZIP文件内容: {len(file_list)} 个文件")
                if len(file_list) < 5:  # 如果文件很少，打印它们
                    print(f"文件列表: {file_list}")
                
                # 逐一解压文件
                for member in tqdm(zip_ref.infolist(), desc="解压缩"):
                    try:
                        zip_ref.extract(member, extract_to)
                    except Exception as e:
                        print(f"解压单个文件失败: {member.filename}, 错误: {e}")
                        # 继续尝试其他文件
            
            print("zipfile解压完成")
            return True
            
        elif archive_path.endswith('.tar.gz') or archive_path.endswith('.tgz'):
            print("使用tarfile库解压...")
            with tarfile.open(archive_path, 'r:gz') as tar_ref:
                # 获取文件列表
                file_list = tar_ref.getnames()
                print(f"TAR文件内容: {len(file_list)} 个文件")
                
                # 逐一解压文件
                for member in tqdm(tar_ref.getmembers(), desc="解压缩"):
                    try:
                        tar_ref.extract(member, extract_to)
                    except Exception as e:
                        print(f"解压单个文件失败: {member.name}, 错误: {e}")
            
            print("tarfile解压完成")
            return True
            
        elif archive_path.endswith('.tar'):
            print("使用tarfile库解压...")
            with tarfile.open(archive_path, 'r:') as tar_ref:
                for member in tqdm(tar_ref.getmembers(), desc="解压缩"):
                    try:
                        tar_ref.extract(member, extract_to)
                    except Exception as e:
                        print(f"解压单个文件失败: {member.name}, 错误: {e}")
            
            print("tarfile解压完成")
            return True
            
        else:
            print(f"警告: 不支持的归档格式: {archive_path}")
            return False
            
    except Exception as e:
        print(f"使用标准库解压失败: {e}")
        print("尝试使用shutil作为备选方案...")
    
    # 如果标准库解压失败，尝试使用shutil
    try:
        print(f"使用shutil解压: {archive_path}")
        shutil.unpack_archive(archive_path, extract_to)
        print("shutil解压完成")
        return True
    except Exception as e:
        print(f"shutil解压也失败: {e}")
        
        # 尝试系统命令作为最后手段
        if archive_path.endswith('.zip'):
            try:
                print("尝试使用系统unzip命令...")
                os.system(f"unzip -o \"{archive_path}\" -d \"{extract_to}\"")
                print("系统命令解压完成")
                return True
            except Exception as e:
                print(f"系统命令解压失败: {e}")
        
        elif archive_path.endswith('.tar.gz') or archive_path.endswith('.tgz'):
            try:
                print("尝试使用系统tar命令...")
                os.system(f"tar -xzf \"{archive_path}\" -C \"{extract_to}\"")
                print("系统命令解压完成")
                return True
            except Exception as e:
                print(f"系统命令解压失败: {e}")
    
    print("所有解压方法都失败")
    return False

def setup_fastspeech2(model_dir, language="zh"):
    """下载和设置FastSpeech2模型"""
    fastspeech2_dir = os.path.join(model_dir, "fastspeech2")
    os.makedirs(fastspeech2_dir, exist_ok=True)
    
    url = MODEL_URLS["fastspeech2"][language]
    filename = url.split('/')[-1]
    download_path = os.path.join(fastspeech2_dir, filename)
    
    print(f"下载FastSpeech2模型 ({language})...")
    download_success = download_file(url, download_path)
    
    if not download_success:
        print(f"下载FastSpeech2模型失败，跳过后续处理")
        return False
    
    # 如果是直接的模型文件（.pth或.pt），直接重命名
    if download_path.endswith(('.pth', '.pt')):
        try:
            model_path = os.path.join(fastspeech2_dir, "model.pt")
            print(f"复制模型文件: {download_path} -> {model_path}")
            shutil.copy(download_path, model_path)
            
            # 创建配置文件
            config = {
                "model_type": "fastspeech2",
                "language": language,
                "sample_rate": 22050,
                "hop_length": 256
            }
            config_path = os.path.join(fastspeech2_dir, "config.json")
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"配置文件已保存: {config_path}")
            
            print(f"FastSpeech2模型 ({language}) 设置成功!")
            return True
        except Exception as e:
            print(f"处理模型文件时出错: {e}")
            return False
    
    # 对于压缩包，需要解压
    print("解压FastSpeech2模型...")
    temp_dir = os.path.join(fastspeech2_dir, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    extract_success = extract_archive(download_path, temp_dir)
    if not extract_success:
        print(f"解压FastSpeech2模型失败，跳过后续处理")
        return False
    
    # 处理不同语言模型的特定文件结构
    try:
        # 打印目录内容以便调试
        print("临时目录内容:")
        for root, dirs, files in os.walk(temp_dir):
            level = root.replace(temp_dir, '').count(os.sep)
            indent = ' ' * 4 * level
            print(f"{indent}{os.path.basename(root)}/")
            sub_indent = ' ' * 4 * (level + 1)
            for f in files:
                print(f"{sub_indent}{f}")
        
        # 查找模型文件 - 尝试多种可能的模式
        model_patterns = ["**/model*.pt*", "**/*.pt*", "**/*.pth*", "**/fastspeech2*.pt*"]
        model_found = False
        
        for pattern in model_patterns:
            model_files = list(Path(temp_dir).glob(pattern))
            if model_files:
                print(f"找到模型文件: {model_files[0]}")
                shutil.copy(str(model_files[0]), os.path.join(fastspeech2_dir, "model.pt"))
                print(f"已复制到 {os.path.join(fastspeech2_dir, 'model.pt')}")
                model_found = True
                break
        
        if not model_found:
            print("未找到任何模型文件")
        
        # 查找配置文件 - 尝试多种可能的模式
        config_patterns = ["**/config*.json", "**/*config*.json", "**/*.json"]
        config_found = False
        
        for pattern in config_patterns:
            config_files = list(Path(temp_dir).glob(pattern))
            if config_files:
                print(f"找到配置文件: {config_files[0]}")
                shutil.copy(str(config_files[0]), os.path.join(fastspeech2_dir, "config.json"))
                print(f"已复制到 {os.path.join(fastspeech2_dir, 'config.json')}")
                config_found = True
                break
        
        if not config_found:
            # 创建基本配置
            print("未找到配置文件，创建默认配置")
            config = {
                "model_type": "fastspeech2",
                "language": language,
                "sample_rate": 22050,
                "hop_length": 256
            }
            config_path = os.path.join(fastspeech2_dir, "config.json")
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"默认配置文件已保存: {config_path}")
        
    except Exception as e:
        print(f"处理FastSpeech2模型时出错: {e}")
        # 继续处理，不阻止脚本运行
    
    # 清理临时文件
    print(f"清理临时目录: {temp_dir}")
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print("临时目录已删除")
    except Exception as e:
        print(f"清理临时目录失败: {e}")
    
    # 检查最终文件是否存在
    model_path = os.path.join(fastspeech2_dir, "model.pt")
    config_path = os.path.join(fastspeech2_dir, "config.json")
    
    if os.path.exists(model_path) and os.path.exists(config_path):
        print(f"FastSpeech2模型 ({language}) 设置成功!")
        return True
    else:
        missing = []
        if not os.path.exists(model_path):
            missing.append("model.pt")
        if not os.path.exists(config_path):
            missing.append("config.json")
        print(f"FastSpeech2模型 ({language}) 设置不完整! 缺少: {', '.join(missing)}")
        return False

def setup_hifigan(model_dir, language="zh"):
    """下载和设置HiFi-GAN模型"""
    hifigan_dir = os.path.join(model_dir, "hifigan")
    os.makedirs(hifigan_dir, exist_ok=True)
    
    url = MODEL_URLS["hifigan"][language]
    filename = os.path.basename(url)
    download_path = os.path.join(hifigan_dir, filename)
    
    print(f"下载HiFi-GAN模型 ({language})...")
    download_success = download_file(url, download_path)
    
    if not download_success:
        print(f"下载HiFi-GAN模型失败，跳过后续处理")
        return False
    
    # 如果是直接的模型文件，直接重命名
    if download_path.endswith(('.pth', '.pt')) or 'generator' in filename:
        try:
            generator_path = os.path.join(hifigan_dir, "generator.pt")
            print(f"复制模型文件: {download_path} -> {generator_path}")
            shutil.copy(download_path, generator_path)
            
            # 创建配置文件
            config = {
                "model_type": "hifigan",
                "language": language,
                "sample_rate": 22050
            }
            config_path = os.path.join(hifigan_dir, "config.json")
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"配置文件已保存: {config_path}")
            
            print(f"HiFi-GAN模型 ({language}) 设置成功!")
            return True
        except Exception as e:
            print(f"处理模型文件时出错: {e}")
            return False
    
    # 对于压缩包，需要解压
    if download_path.endswith(('.zip', '.tar.gz', '.tgz', '.tar')):
        print("解压HiFi-GAN模型...")
        temp_dir = os.path.join(hifigan_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        extract_success = extract_archive(download_path, temp_dir)
        if not extract_success:
            print(f"解压HiFi-GAN模型失败，跳过后续处理")
            return False
        
        # 根据实际文件结构调整
        try:
            # 打印目录内容以便调试
            print("临时目录内容:")
            for root, dirs, files in os.walk(temp_dir):
                level = root.replace(temp_dir, '').count(os.sep)
                indent = ' ' * 4 * level
                print(f"{indent}{os.path.basename(root)}/")
                sub_indent = ' ' * 4 * (level + 1)
                for f in files:
                    print(f"{sub_indent}{f}")
            
            # 查找模型文件 - 尝试多种可能的模式
            model_patterns = ["**/generator*.pt*", "**/*.pt*", "**/*.pth*", "**/hifigan*.pt*", "**/g_*.pt*"]
            model_found = False
            
            for pattern in model_patterns:
                model_files = list(Path(temp_dir).glob(pattern))
                if model_files:
                    print(f"找到模型文件: {model_files[0]}")
                    shutil.copy(str(model_files[0]), os.path.join(hifigan_dir, "generator.pt"))
                    print(f"已复制到 {os.path.join(hifigan_dir, 'generator.pt')}")
                    model_found = True
                    break
            
            if not model_found:
                print("未找到任何模型文件")
            
            # 查找配置文件 - 尝试多种可能的模式
            config_patterns = ["**/config*.json", "**/*config*.json", "**/*.json"]
            config_found = False
            
            for pattern in config_patterns:
                config_files = list(Path(temp_dir).glob(pattern))
                if config_files:
                    print(f"找到配置文件: {config_files[0]}")
                    shutil.copy(str(config_files[0]), os.path.join(hifigan_dir, "config.json"))
                    print(f"已复制到 {os.path.join(hifigan_dir, 'config.json')}")
                    config_found = True
                    break
            
            if not config_found:
                # 创建基本配置
                print("未找到配置文件，创建默认配置")
                config = {
                    "model_type": "hifigan",
                    "language": language,
                    "sample_rate": 22050
                }
                config_path = os.path.join(hifigan_dir, "config.json")
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
                print(f"默认配置文件已保存: {config_path}")
            
        except Exception as e:
            print(f"处理HiFi-GAN模型时出错: {e}")
        
        # 清理临时文件
        print(f"清理临时目录: {temp_dir}")
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                print("临时目录已删除")
        except Exception as e:
            print(f"清理临时目录失败: {e}")
    
    # 检查最终文件是否存在
    model_path = os.path.join(hifigan_dir, "generator.pt")
    config_path = os.path.join(hifigan_dir, "config.json")
    
    if os.path.exists(model_path) and os.path.exists(config_path):
        print(f"HiFi-GAN模型 ({language}) 设置成功!")
        return True
    else:
        missing = []
        if not os.path.exists(model_path):
            missing.append("generator.pt")
        if not os.path.exists(config_path):
            missing.append("config.json")
        print(f"HiFi-GAN模型 ({language}) 设置不完整! 缺少: {', '.join(missing)}")
        return False

def main():
    parser = argparse.ArgumentParser(description='下载FastSpeech2和HiFi-GAN模型')
    parser.add_argument('--dir', type=str, default='../models/weights/tts',
                        help='模型保存目录')
    parser.add_argument('--language', type=str, default='zh', choices=['zh', 'en'],
                        help='模型语言，中文(zh)或英文(en)')
    parser.add_argument('--models', type=str, default='all', choices=['all', 'fastspeech2', 'hifigan'],
                        help='要下载的模型，可选all(全部)、fastspeech2或hifigan')
    args = parser.parse_args()
    
    # 创建模型目录
    os.makedirs(args.dir, exist_ok=True)
    print(f"模型将保存在: {os.path.abspath(args.dir)}")
    
    print("开始下载TTS模型...\n")
    
    success = True
    
    # 下载FastSpeech2
    if args.models in ['all', 'fastspeech2']:
        fs2_success = setup_fastspeech2(args.dir, args.language)
        if not fs2_success:
            success = False
        print("\n")
    
    # 下载HiFi-GAN
    if args.models in ['all', 'hifigan']:
        hifigan_success = setup_hifigan(args.dir, args.language)
        if not hifigan_success:
            success = False
        print("\n")
    
    if success:
        print("所有模型下载完成！模型文件保存在:", os.path.abspath(args.dir))
    else:
        print("部分模型下载或处理失败，请查看上面的错误信息。")
        print("您可以尝试手动下载模型文件并放置到正确位置。")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n下载被用户中断")
    except Exception as e:
        print(f"\n发生错误: {e}")
        import traceback
        traceback.print_exc()