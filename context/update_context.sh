#!/bin/bash
# 自动更新 Session 上下文脚本
# 使用方法: ./context/update_context.sh "简要描述本次工作内容"

set -e

# 配置
CONTEXT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$CONTEXT_DIR")"
SESSION_ID=$(date +"%Y-%m-%d")
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
GIT_MSG="${1:-更新上下文}"

echo "📝 更新 Session 上下文..."
echo "   Session ID: $SESSION_ID"
echo "   时间: $TIMESTAMP"
echo ""

# 1. 生成代码变更摘要
echo "📊 生成代码变更摘要..."
cd "$PROJECT_ROOT"

# 获取最近的 Git 变更
LATEST_COMMITS=$(git log --oneline -5 2>/dev/null || echo "无提交")
GIT_CHANGES=$(git diff --stat HEAD~3..HEAD 2>/dev/null | head -20 || echo "无变更")

# 2. 创建/更新当前 session 文件
SESSION_FILE="$CONTEXT_DIR/sessions/session_${SESSION_ID}.md"

echo "📝 更新 Session 文件: $SESSION_FILE"

# 如果文件存在，追加更新；否则创建新文件
if [ -f "$SESSION_FILE" ]; then
    # 追加更新记录
    cat >> "$SESSION_FILE" << EOF

---

## 更新记录: $TIMESTAMP

**描述**: $GIT_MSG

### 代码变更
\`\`\`
$LATEST_COMMITS
\`\`\`

### 文件变更
\`\`\`
$GIT_CHANGES
\`\`\`
EOF
else
    # 创建新 Session 文件
    cat > "$SESSION_FILE" << EOF
# Session $SESSION_ID: 飞书 AI 助手开发

## 本次会话目标

$GIT_MSG

---

## 已完成工作

### 代码变更
\`\`\`
$LATEST_COMMITS
\`\`\`

### 文件变更
\`\`\`
$GIT_CHANGES
\`\`\`

---

## 关键信息

### 当前活跃技能
- query_market - 市场指数查询
- analyze_stock - 个股分析
- search_github - GitHub 搜索
- search_papers - arXiv 论文
- chat - 通用对话

### 技术状态
- 版本: v2.1.0
- 连接: WebSocket 长连接
- 数据: 腾讯财经 API
- 模型: Moonshot (Kimi)

---

## 快速恢复

\`\`\`bash
# 查看项目信息
cat AGENTS.md
cat context/session_summary_2026-02-17.md

# 查看今日进度
cat context/sessions/session_\$(date +%Y-%m-%d).md

# 连接服务器
ssh vps
journalctl -u feishu-assistant -f
\`\`\`

---

## 待办事项

- [ ] 根据用户需求继续开发

---

**Session ID**: $SESSION_ID  
**开始时间**: $TIMESTAMP
EOF
fi

# 3. 提交到 GitHub
echo ""
echo "📤 提交到 GitHub..."
cd "$PROJECT_ROOT"

git add context/
git add AGENTS.md 2>/dev/null || true
git commit -m "context: ${GIT_MSG} [${TIMESTAMP}]" || echo "⚠️  无变更需要提交"

# 检查是否需要推送
if git diff --quiet origin/main..HEAD 2>/dev/null; then
    echo "✅ 已是最新，无需推送"
else
    git push origin main
    echo "✅ 已推送到 GitHub"
fi

echo ""
echo "✅ 上下文更新完成！"
echo ""
echo "📖 快速查看:"
echo "   cat AGENTS.md                    # 项目说明"
echo "   cat context/sessions/session_${SESSION_ID}.md  # 本次记录"
echo ""
