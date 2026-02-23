#!/bin/bash
# 持仓跟踪定时任务安装脚本
# 在服务器上运行此脚本设置定时任务

set -e

echo "🚀 设置持仓跟踪定时任务..."
echo "================================"

# 检查是否在服务器上
if [ ! -d "/opt/feishu-assistant" ]; then
    echo "❌ 未找到 /opt/feishu-assistant，请确保在正确的服务器上运行"
    exit 1
fi

cd /opt/feishu-assistant

# 复制脚本
echo "📄 复制跟踪脚本..."
cp scripts/portfolio_tracker_cron.py ./
chmod +x portfolio_tracker_cron.py

# 检查 Python 环境
if [ ! -f "venv/bin/python" ]; then
    echo "❌ 未找到虚拟环境，请先部署飞书助手"
    exit 1
fi

# 测试运行一次
echo "🧪 测试运行..."
venv/bin/python portfolio_tracker_cron.py --force || echo "⚠️ 测试运行失败，请检查配置"

# 添加到 crontab
echo "⏰ 添加定时任务..."
CRON_CMD="*/30 9-11,13-15 * * 1-5 cd /opt/feishu-assistant && venv/bin/python portfolio_tracker_cron.py >> logs/tracker.log 2>&1"

# 检查是否已存在
if crontab -l 2>/dev/null | grep -q "portfolio_tracker_cron"; then
    echo "⚠️ 定时任务已存在，跳过添加"
else
    # 添加新任务
    (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
    echo "✅ 定时任务已添加"
fi

# 显示当前 crontab
echo ""
echo "📋 当前定时任务:"
crontab -l | grep portfolio_tracker || echo "(无)"

echo ""
echo "================================"
echo "✅ 设置完成！"
echo ""
echo "📌 任务运行时间:"
echo "   - 上午: 9:30, 10:00, 10:30, 11:00, 11:30"
echo "   - 下午: 13:00, 13:30, 14:00, 14:30, 15:00"
echo ""
echo "📌 手动运行:"
echo "   cd /opt/feishu-assistant && venv/bin/python portfolio_tracker_cron.py"
echo ""
echo "📌 强制通知（无视变化）:"
echo "   cd /opt/feishu-assistant && venv/bin/python portfolio_tracker_cron.py --force"
echo ""
echo "📌 查看日志:"
echo "   tail -f /opt/feishu-assistant/logs/tracker.log"
