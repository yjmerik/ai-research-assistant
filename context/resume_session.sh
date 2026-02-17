#!/bin/bash
# 恢复会话脚本
# 使用方式: source resume_session.sh

echo "🔄 恢复飞书 AI 助手开发会话..."
echo ""

# 项目路径
PROJECT_DIR="/Users/eric/.config/agents/skills/topic-research-assistant/ai-research-assistant"
SERVER_IP="101.37.82.254"
SERVER_DIR="/opt/feishu-assistant"

echo "📂 本地项目: $PROJECT_DIR"
echo "🌐 服务器: $SERVER_IP"
echo ""

# 检查 SSH 配置
echo "🔍 检查 SSH 配置..."
if ! grep -q "Host vps" ~/.ssh/config 2>/dev/null; then
    echo "⚠️  未找到 vps 配置，请确保 ~/.ssh/config 包含:"
    echo ""
    echo "Host vps"
    echo "    HostName 101.37.82.254"
    echo "    User root"
    echo "    IdentityFile ~/.ssh/id_ed25519_vps"
fi

# 快速命令别名
echo ""
echo "📝 快捷命令:"
echo ""
echo "  # 查看服务器日志"
echo "  ssh vps 'journalctl -u feishu-assistant -f'"
echo ""
echo "  # 重启服务"
echo "  ssh vps 'systemctl restart feishu-assistant'"
echo ""
echo "  # 更新代码"
echo "  ssh vps 'cd $SERVER_DIR && ./update.sh'"
echo ""
echo "  # 进入项目目录"
echo "  cd $PROJECT_DIR"
echo ""

# Git 状态
echo "🔍 Git 状态:"
cd $PROJECT_DIR
git log -1 --oneline
git status --short

echo ""
echo "✅ 会话恢复完成！"
echo ""
echo "💡 提示:"
echo "  • 修改代码后: git add -A && git commit -m '...' && git push"
echo "  • 部署到服务器: ssh vps '$SERVER_DIR/update.sh'"
echo "  • 测试命令: /market, 分析一下茅台, AAPL股价"
