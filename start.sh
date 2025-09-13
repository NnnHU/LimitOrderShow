#!/bin/bash

# 币安市场深度监控系统启动脚本

# 设置错误时退出
set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 输出启动信息
echo "正在启动币安市场深度监控系统..."
echo "工作目录: $SCRIPT_DIR"
echo "时间: $(date)"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3"
    exit 1
fi

# 检查依赖文件
if [ ! -f "requirements.txt" ]; then
    echo "错误: 未找到 requirements.txt"
    exit 1
fi

if [ ! -f "main.py" ]; then
    echo "错误: 未找到 main.py"
    exit 1
fi

# 检查是否安装了依赖
echo "检查Python依赖..."
python3 -c "
import websocket
import json
import threading
import time
import asyncio
print('依赖检查通过')
" || {
    echo "正在安装依赖..."
    pip3 install -r requirements.txt
}

# 启动应用
echo "启动监控系统..."
if [ -f "server_start.py" ]; then
    # 如果存在服务器启动脚本，使用它
    python3 server_start.py
else
    # 否则使用main.py的--no-input参数
    python3 main.py --no-input
fi 