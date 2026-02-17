# 会话上下文管理

本目录用于持久化存储开发会话的上下文信息，方便后续继续工作。

## 📁 目录结构

```
context/
├── README.md                      # 本文件
├── TEMPLATE.md                    # Session 模板
├── update_context.sh              # 自动更新脚本
├── session_summary_2026-02-17.md  # 项目总体摘要
├── code_changes_2026-02-17.json   # 代码变更记录
├── resume_session.sh              # 会话恢复脚本
└── sessions/                      # 每日 Session 记录
    ├── session_2026-02-17.md
    └── ...
```

## 🚀 快速使用

### 更新上下文

每次完成重要工作后，运行：

```bash
./context/update_context.sh "描述本次工作内容"
```

例如：

```bash
./context/update_context.sh "新增个股分析技能，支持A股/港股/美股"
```

这将自动：
1. 生成代码变更摘要
2. 更新 Session 文件
3. 提交到 GitHub

### 恢复会话

继续工作前，查看上下文：

```bash
# 查看最新 Session
cat context/sessions/session_$(date +%Y-%m-%d).md

# 查看项目摘要
cat context/session_summary_2026-02-17.md

# 运行恢复脚本
source context/resume_session.sh
```

## 📝 上下文内容

### 项目摘要 (session_summary_*.md)
- 项目概览
- 架构设计
- 已完成功能
- 技术决策
- 部署信息

### 每日 Session (sessions/session_YYYY-MM-DD.md)
- 当日工作内容
- 代码变更统计
- 遇到的问题
- 下次计划

### 代码变更 (code_changes_*.json)
- 文件变更记录
- Skills 列表
- 环境配置

## 🔧 自动化工作流

### 1. 开始新 Session

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 查看上下文
cat context/sessions/session_$(date +%Y-%m-%d).md

# 3. 开始开发...
```

### 2. 开发过程中

```bash
# 修改代码...

# 提交代码
git add -A
git commit -m "feat: xxx"
git push
```

### 3. 结束 Session

```bash
# 更新上下文
./context/update_context.sh "完成 xxx 功能"
```

## 💡 最佳实践

1. **及时更新**: 每次完成重要功能后更新上下文
2. **清晰描述**: 使用简洁明了的描述说明工作内容
3. **定期回顾**: 开始新 Session 前回顾上次记录
4. **保持同步**: 上下文与代码一起提交到 GitHub

## 🔗 相关文件

- [项目 README](../README.md)
- [部署文档](../DEPLOY.md)
- [工作流文档](../WORKFLOW.md)
