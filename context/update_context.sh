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
GIT_CHANGES=$(git diff --stat HEAD~5..HEAD 2>/dev/null || echo "无变更")
LATEST_COMMITS=$(git log --oneline -5 2>/dev/null || echo "无提交")

# 2. 创建/更新当前 session 文件
SESSION_FILE="$CONTEXT_DIR/sessions/session_${SESSION_ID}.md"

echo "📝 更新 Session 文件: $SESSION_FILE"

cat > "$SESSION_FILE" << EOF
# Session ${SESSION_ID}

## 基本信息
- **日期**: ${TIMESTAMP}
- **Session ID**: ${SESSION_ID}
- **Git 消息**: ${GIT_MSG}

## 代码变更
\`\`\`
${LATEST_COMMITS}
\`\`\`

### 文件变更统计
\`\`\`
${GIT_CHANGES}
\`\`\`

## 功能状态
$(cat "$CONTEXT_DIR/session_summary_2026-02-17.md" | grep -A 50 "已完成功能" | head -30 || echo "参见 session_summary_2026-02-17.md")

## 待办事项
- [ ] 根据用户需求继续开发

## 快速链接
- [完整项目摘要](./session_summary_2026-02-17.md)
- [代码变更记录](./code_changes_2026-02-17.json)

---
**更新时间**: ${TIMESTAMP}
EOF

# 3. 更新主上下文文件
echo "🔄 更新主上下文文件..."

# 添加更新记录到摘要文件
echo "" >> "$CONTEXT_DIR/session_summary_2026-02-17.md"
echo "---" >> "$CONTEXT_DIR/session_summary_2026-02-17.md"
echo "" >> "$CONTEXT_DIR/session_summary_2026-02-17.md"
echo "## 更新记录" >> "$CONTEXT_DIR/session_summary_2026-02-17.md"
echo "" >> "$CONTEXT_DIR/session_summary_2026-02-17.md"
echo "- **${TIMESTAMP}**: ${GIT_MSG}" >> "$CONTEXT_DIR/session_summary_2026-02-17.md"

# 4. 提交到 GitHub
echo ""
echo "📤 提交到 GitHub..."
cd "$PROJECT_ROOT"

git add context/
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
echo "   文件: $SESSION_FILE"
echo ""
