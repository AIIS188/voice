#!/bin/bash

# 声教助手启动脚本 (Conda版)

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# 日志函数
log() {
    echo -e "${GREEN}[声教助手] $1${NC}"
}

error() {
    echo -e "${RED}[错误] $1${NC}" >&2
    exit 1
}

# Conda 环境名称
CONDA_ENV_NAME="voice_assistant"

# 检查 Conda 是否已安装
check_conda() {
    if ! command -v conda &> /dev/null; then
        error "Conda 未安装，请先安装 Anaconda 或 Miniconda"
    fi
}

# 创建或激活 Conda 环境
setup_conda_env() {
    # 检查环境是否存在
    if ! conda env list | grep -q "$CONDA_ENV_NAME"; then
        log "创建 Conda 虚拟环境：$CONDA_ENV_NAME"
        conda create -n "$CONDA_ENV_NAME" python=3.10 -y
    fi

    # 激活环境
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate "$CONDA_ENV_NAME"
}

# 安装后端依赖
setup_backend_deps() {
    log "安装后端依赖"
    
    # 使用 conda 安装系统级依赖
    conda install -y \
        numpy \
        scipy \
        pandas \
        scikit-learn \
        matplotlib \
        ffmpeg \
        libsndfile

    # 使用 pip 安装 Python 特定依赖
    pip install --upgrade pip

    # 安装核心依赖
    pip install \
        fastapi \
        uvicorn \
        pydantic \
        pydantic-settings \
        sqlalchemy \
        alembic

    # 音频处理依赖
    pip install \
        librosa \
        soundfile \
        torch \
        torchaudio

    # PaddlePaddle 及 PaddleSpeech
    pip install \
        paddlepaddle \
        paddlespeech

    # 其他依赖
    pip install \
        python-jose \
        passlib \
        python-multipart
}

# 启动后端服务
start_backend() {
    log "启动后端服务"
    cd backend
    python run.py > ../logs/backend.log 2>&1 &
    BACKEND_PID=$!
    cd ..
}

# 启动前端服务
start_frontend() {
    log "启动前端服务"
    cd frontend
    npm install
    npm run dev > ../logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    cd ..
}

# 主启动流程
main() {
    # 创建日志目录
    mkdir -p logs

    # 检查并设置 Conda 环境
    check_conda
    setup_conda_env

    # 安装依赖
    setup_backend_deps

    # 启动服务
    start_backend
    start_frontend

    # 等待并处理中断
    trap "conda deactivate; kill $BACKEND_PID $FRONTEND_PID; exit" SIGINT SIGTERM
    wait
}

# 执行主流程
main

log "声教助手已启动！"
echo "前端服务地址: http://localhost:3000"
echo "后端服务地址: http://localhost:8000"