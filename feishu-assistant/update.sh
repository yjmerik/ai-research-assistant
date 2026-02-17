#!/bin/bash
# 飞书 AI 助手 - 自动更新脚本
# 从 GitHub 拉取最新代码并重启服务

set -e

APP_DIR="/opt/feishu-assistant"
REPO_URL="https://github.com/yjmerik/ai-research-assistant.git"
BRANCH="main"

echo "🔄 飞书 AI 助手更新脚本"
echo "========================"
echo ""

# 检查是否安装了 git
if ! command -v git &> /dev/null; then
    echo "📦 安装 git..."
    yum install -y git || apt-get install -y git
fi

# 进入应用目录
cd $APP_DIR

# 备份当前代码
echo "📦 备份当前代码..."
cp main.py main.py.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true

# 如果是首次运行，克隆仓库
if [ ! -d "$APP_DIR/.git" ]; then
    echo "📥 首次运行，克隆仓库..."
    git clone --depth 1 -b $BRANCH $REPO_URL /tmp/feishu-assistant-new
    cp /tmp/feishu-assistant-new/feishu-assistant/* $APP_DIR/
    rm -rf /tmp/feishu-assistant-new
else
    echo "📥 拉取最新代码..."
    git fetch origin $BRANCH
    git reset --hard origin/$BRANCH
    
    # 复制最新代码
    if [ -d "$APP_DIR/feishu-assistant" ]; then
        cp $APP_DIR/feishu-assistant/main.py $APP_DIR/
        cp $APP_DIR/feishu-assistant/requirements.txt $APP_DIR/
    fi
fi

# 安装/更新依赖
echo "📦 更新依赖..."
pip3 install -r $APP_DIR/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet

# 检查环境变量
if [ ! -f "$APP_DIR/.env" ]; then
    echo "⚠️  环境变量文件不存在，请创建 $APP_DIR/.env"
    echo "   参考: cp $APP_DIR/.env.example $APP_DIR/.env"
    exit 1
fi

# 重启服务
echo "🔄 重启服务..."
systemctl restart feishu-assistant

# 检查状态
sleep 2
if systemctl is-active --quiet feishu-assistant; then
    echo ""
    echo "✅ 更新成功！"
    echo ""
    echo "📊 服务状态:"
    systemctl status feishu-assistant --no-pager | head -10
    echo ""
    echo "📜 最新日志:"
    journalctl -u feishu-assistant -n 3 --no-pager
else
    echo ""
    echo "❌ 服务启动失败，正在回滚..."
    # 这里可以添加回滚逻辑
    systemctl status feishu-assistant --no-pager | tail -20
    exit 1
fi
