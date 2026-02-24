#!/bin/bash
# 多市场分时持仓跟踪定时任务安装脚本
# 自动配置crontab，按市场开盘时间分别运行

set -e

echo "🚀 设置多市场分时持仓跟踪定时任务..."
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
if [ ! -f "/usr/bin/python3.11" ]; then
    echo "❌ 未找到 Python 3.11"
    exit 1
fi

# 备份原有crontab
echo "💾 备份原有 crontab..."
crontab -l > crontab.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true

# 创建新的crontab配置
CRON_CONFIG=$(cat << 'EOF'
# 飞书持仓跟踪定时任务 - 按市场开盘时间分别运行
# 作者: AI Assistant
# 更新日期: 2026-02-24

# ==================== A股追踪 ====================
# A股上午: 9:30, 10:00, 10:30, 11:00, 11:30
# A股下午: 13:00, 13:30, 14:00, 14:30, 15:00
*/30 9-11,13-15 * * 1-5 cd /opt/feishu-assistant && /usr/bin/python3.11 portfolio_tracker_cron.py --market A股 >> logs/tracker_A股.log 2>&1

# ==================== 港股追踪 ====================
# 港股上午: 9:30, 10:00, 10:30, 11:00, 11:30, 12:00
# 港股下午: 13:00, 13:30, 14:00, 14:30, 15:00, 15:30, 16:00
*/30 9-11 * * 1-5 cd /opt/feishu-assistant && /usr/bin/python3.11 portfolio_tracker_cron.py --market 港股 >> logs/tracker_港股.log 2>&1
30 12 * * 1-5 cd /opt/feishu-assistant && /usr/bin/python3.11 portfolio_tracker_cron.py --market 港股 >> logs/tracker_港股.log 2>&1
*/30 13-15 * * 1-5 cd /opt/feishu-assistant && /usr/bin/python3.11 portfolio_tracker_cron.py --market 港股 >> logs/tracker_港股.log 2>&1

# ==================== 美股追踪 ====================
# 美股夏令时: 北京时间 21:30-04:00
# 美股冬令时: 北京时间 22:30-05:00
# 这里使用 21:30-05:00 覆盖两种情况

# 美股晚上时段 (21:30, 22:00, 22:30, 23:00, 23:30)
30,00 21-23 * * 1-5 cd /opt/feishu-assistant && /usr/bin/python3.11 portfolio_tracker_cron.py --market 美股 >> logs/tracker_美股.log 2>&1

# 美股凌晨时段 (00:00, 00:30, 01:00, 01:30, 02:00, 02:30, 03:00, 03:30, 04:00, 04:30)
# 周一到周五的凌晨（对应美股周日到周四晚上）
*/30 0-4 * * 2-6 cd /opt/feishu-assistant && /usr/bin/python3.11 portfolio_tracker_cron.py --market 美股 >> logs/tracker_美股.log 2>&1

# 美股周五晚上 (跨到周六凌晨)
30,00 21-23 * * 5 cd /opt/feishu-assistant && /usr/bin/python3.11 portfolio_tracker_cron.py --market 美股 >> logs/tracker_美股.log 2>&1
*/30 0-4 * * 6 cd /opt/feishu-assistant && /usr/bin/python3.11 portfolio_tracker_cron.py --market 美股 >> logs/tracker_美股.log 2>&1

EOF
)

# 删除旧的持仓追踪任务（如果存在）
echo "🧹 清理旧任务..."
crontab -l 2>/dev/null | grep -v "portfolio_tracker_cron" > crontab_temp.txt || true

# 添加新任务
echo "$CRON_CONFIG" >> crontab_temp.txt

# 安装新crontab
crontab crontab_temp.txt
rm -f crontab_temp.txt

echo "✅ 定时任务已安装"
echo ""

# 显示当前crontab
echo "📋 当前持仓跟踪定时任务:"
echo "================================"
crontab -l | grep -A1 "===.*追踪 ===" | grep -v "^--$"

echo ""
echo "📊 日志文件位置:"
echo "  - A股: /opt/feishu-assistant/logs/tracker_A股.log"
echo "  - 港股: /opt/feishu-assistant/logs/tracker_港股.log"
echo "  - 美股: /opt/feishu-assistant/logs/tracker_美股.log"

echo ""
echo "================================"
echo "✅ 设置完成！"
echo ""
echo "📌 各市场交易时间（北京时间）:"
echo "  A股:  09:30-11:30, 13:00-15:00 (周一到周五)"
echo "  港股: 09:30-12:00, 13:00-16:00 (周一到周五)"
echo "  美股: 21:30-04:00/05:00 (夏令时/冬令时, 周一到周五)"
echo ""
echo "📌 手动运行测试:"
echo "  # 追踪A股"
echo "  cd /opt/feishu-assistant && python3.11 portfolio_tracker_cron.py --market A股"
echo ""
echo "  # 追踪港股"
echo "  cd /opt/feishu-assistant && python3.11 portfolio_tracker_cron.py --market 港股"
echo ""
echo "  # 追踪美股"
echo "  cd /opt/feishu-assistant && python3.11 portfolio_tracker_cron.py --market 美股"
echo ""
echo "  # 追踪所有市场"
echo "  cd /opt/feishu-assistant && python3.11 portfolio_tracker_cron.py --all"
echo ""
echo "📌 查看日志:"
echo "  tail -f /opt/feishu-assistant/logs/tracker_A股.log"
echo "  tail -f /opt/feishu-assistant/logs/tracker_港股.log"
echo "  tail -f /opt/feishu-assistant/logs/tracker_美股.log"
