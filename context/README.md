# 上下文管理

本目录用于持久化存储开发会话的上下文信息，方便 Kimi CLI 继续工作。

## 快速开始

### 继续工作前

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 查看项目信息
cat AGENTS.md                              # 项目说明和架构
cat context/session_summary_2026-02-17.md   # 完整项目摘要

# 3. 查看今日 Session
cat context/sessions/session_$(date +%Y-%m-%d).md
```

### 完成工作后

```bash
# 更新上下文（自动提交到 GitHub）
./context/update_context.sh "描述本次工作内容"
```

## 目录结构

```
context/
├── README.md                      # 本文件
├── AGENTS.md                      # Kimi CLI 项目说明 (上级目录)
├── TEMPLATE.md                    # Session 模板
├── update_context.sh              # 自动更新脚本
├── resume_session.sh              # 会话恢复脚本
├── session_summary_2026-02-17.md  # 项目总体摘要
├── code_changes_2026-02-17.json   # 代码变更记录
└── sessions/                      # 每日 Session 记录
    └── session_YYYY-MM-DD.md
```

## 关键文件说明

| 文件 | 用途 | 何时查看 |
|------|------|----------|
| `AGENTS.md` | 项目架构、技术栈、开发规范 | 每次开始工作时 |
| `session_summary_*.md` | 完整项目摘要和历史 | 需要了解整体状态时 |
| `sessions/session_*.md` | 当日工作记录 | 查看今日/上次进展 |
| `code_changes_*.json` | 代码变更结构化记录 | 需要详细变更信息 |

## 工作流

```
开始工作
   ↓
git pull origin main          # 拉取最新代码和上下文
   ↓
cat AGENTS.md                 # 回顾项目架构
   ↓
cat context/sessions/...      # 查看上次进展
   ↓
开发编码...
   ↓
git add -A && git commit      # 提交代码
   ↓
./context/update_context.sh   # 更新上下文
   ↓
结束工作
```

## 提示

- `AGENTS.md` 位于项目根目录，包含完整的项目说明
- 每次开始工作前阅读 `AGENTS.md` 和最新 Session 文件
- 使用 `./context/update_context.sh` 保持上下文同步
