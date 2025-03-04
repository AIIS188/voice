@echo off
TITLE 声教助手启动脚本
chcp 65001 >nul

echo 正在启动声教助手...

REM 启动后端服务
echo 启动后端服务...
cd backend
if not exist venv (
    echo 创建Python虚拟环境...
    python -m venv venv
)
call venv\Scripts\activate
pip install -r requirements.txt
start python run.py
cd ..

REM 启动前端服务
echo 启动前端服务...
cd frontend
call npm install
start npm run dev

echo 声教助手已启动！
echo 前端服务地址: http://localhost:3000
echo 后端服务地址: http://localhost:8000

pause