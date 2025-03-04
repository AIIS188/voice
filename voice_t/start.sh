#!/bin/bash

# 声教助手启动脚本

echo "正在启动声教助手..."

# 判断操作系统类型
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    # Windows环境
    echo "检测到Windows环境"
    
    # 启动后端服务
    echo "启动后端服务..."
    cd backend
    if [ ! -d "venv" ]; then
        echo "创建Python虚拟环境..."
        python -m venv venv
    fi
    source venv/Scripts/activate
    pip install -r requirements.txt
    start python run.py
    cd ..
    
    # 启动前端服务
    echo "启动前端服务..."
    cd frontend
    npm install
    start npm run dev
    
else
    # Unix/Linux/MacOS环境
    echo "检测到Unix/Linux/MacOS环境"
    
    # 启动后端服务
    echo "启动后端服务..."
    cd backend
    if [ ! -d "venv" ]; then
        echo "创建Python虚拟环境..."
        python3 -m venv venv
    fi
    source venv/bin/activate
    pip install -r requirements.txt
    python run.py &
    BACKEND_PID=$!
    cd ..
    
    # 启动前端服务
    echo "启动前端服务..."
    cd frontend
    npm install
    npm run dev &
    FRONTEND_PID=$!
    
    # 设置退出处理
    trap "kill $BACKEND_PID $FRONTEND_PID; exit" SIGINT SIGTERM
    
    # 等待子进程
    wait
fi

echo "声教助手已启动！"
echo "前端服务地址: http://localhost:3000"
echo "后端服务地址: http://localhost:8000"