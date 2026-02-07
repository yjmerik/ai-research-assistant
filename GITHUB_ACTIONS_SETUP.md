# GitHub Actions 自动化部署指南

## 📋 概述

使用 GitHub Actions 实现完全免费的云端自动化：
- ☁️ **云端运行** - 无需本地电脑，24/7 自动执行
- 🆓 **完全免费** - GitHub Actions 对公开仓库免费
- ⏰ **定时触发** - 每天早上 8:00 自动运行
- 📱 **飞书通知** - 自动发送消息到飞书

---

## 🚀 部署步骤

### 第一步：创建 GitHub 仓库

1. 访问 https://github.com/new
2. 仓库名称：`ai-research-assistant`
3. 选择「Public」（公开仓库 Actions 免费）
4. 点击「Create repository」

---

### 第二步：上传代码

#### 方式 1: 使用命令行

```bash
# 克隆仓库（替换为你的用户名）
git clone https://github.com/你的用户名/ai-research-assistant.git
cd ai-research-assistant

# 创建目录结构
mkdir -p .github/workflows
mkdir -p .github/scripts

# 复制文件
cp ~/.config/agents/skills/topic-research-assistant/.github/workflows/daily_research.yml .github/workflows/
cp ~/.config/agents/skills/topic-research-assistant/.github/scripts/auto_research.py .github/scripts/

# 提交代码
git add .
git commit -m "Initial commit: GitHub Actions workflow"
git push origin main
```

#### 方式 2: 直接在 GitHub 网页上传

1. 进入你的仓库
2. 点击「Add file」→「Create new file」
3. 创建文件：`.github/workflows/daily_research.yml`
4. 复制下文中的 workflow 内容
5. 创建文件：`.github/scripts/auto_research.py`
6. 复制脚本内容

---

### 第三步：配置 Secrets

在 GitHub 仓库中配置飞书应用凭证：

1. 进入仓库 → 「Settings」→ 「Secrets and variables」→ 「Actions」
2. 点击「New repository secret」
3. 添加以下 secrets：

| Secret 名称 | 值 | 说明 |
|------------|---|------|
| `FEISHU_APP_ID` | `cli_a90c14b297f85bcb` | 飞书应用 ID |
| `FEISHU_APP_SECRET` | `vhK2lyuiBIzd7W9b9cb8KgN8bMHNLAnU` | 飞书应用密钥 |
| `FEISHU_USER_OPEN_ID` | `ou_58af23946f2fffb4260cbf51f49c9620` | 你的 Open ID |

---

### 第四步：手动触发测试

1. 进入仓库 → 「Actions」标签
2. 点击「Daily Research Collection」
3. 点击「Run workflow」
4. 输入参数（可选）：
   - Topic: `AI Agent`
   - arxiv_count: `10`
5. 点击「Run workflow」

等待 1-2 分钟，查看运行结果。

---

### 第五步：验证结果

1. 查看 Actions 运行日志
2. 检查飞书是否收到消息通知
3. 查看飞书文档是否创建成功

---

## 📁 文件结构

```
ai-research-assistant/
├── .github/
│   ├── workflows/
│   │   └── daily_research.yml    # GitHub Actions 工作流
│   └── scripts/
│       └── auto_research.py       # 自动化脚本
├── README.md                       # 项目说明
└── .gitignore                      # Git 忽略文件
```

---

## ⚙️ 配置说明

### 定时配置

修改 `.github/workflows/daily_research.yml` 中的 cron 表达式：

```yaml
on:
  schedule:
    # UTC 时间 0:00 = 北京时间 8:00
    - cron: '0 0 * * *'
```

Cron 表达式格式：
```
分 时 日 月 周
```

常用示例：
- `0 0 * * *` - 每天 UTC 0:00（北京时间 8:00）
- `0 12 * * *` - 每天 UTC 12:00（北京时间 20:00）
- `0 0 * * 1` - 每周一 UTC 0:00
- `0 0 1 * *` - 每月 1 号 UTC 0:00

---

### 修改研究主题

在 workflow 文件中修改默认主题：

```yaml
env:
  TOPIC: ${{ github.event.inputs.topic || '你的主题' }}
```

或在手动触发时输入主题。

---

## 📱 使用方式

### 自动执行

每天早上 8:00（北京时间），GitHub Actions 会自动：
1. 搜索 arXiv 最新论文
2. 生成研究简报
3. 创建飞书文档
4. 发送消息通知

### 手动触发

需要立即收集时：
1. 进入仓库 → Actions
2. 选择「Daily Research Collection」
3. 点击「Run workflow」
4. 输入主题和数量
5. 点击运行

---

## 🔧 故障排查

### Actions 运行失败

1. 进入 Actions 页面查看日志
2. 检查 Secrets 是否配置正确
3. 确认飞书应用权限已开通

### 飞书通知未收到

1. 检查 `FEISHU_USER_OPEN_ID` 是否正确
2. 确认飞书应用有发送消息权限
3. 查看飞书应用是否发布

### arXiv 搜索失败

1. 可能是网络超时，GitHub Actions 会自动重试
2. 检查 arXiv API 是否可用
3. 增加超时时间（修改脚本中的 timeout 参数）

---

## 📊 监控与日志

### 查看运行历史

1. 进入仓库 → Actions
2. 查看所有运行记录
3. 点击单次运行查看详细日志

### 下载报告

Actions 会自动上传报告文件：
- `research_report.md` - 生成的报告
- `doc_info.json` - 文档信息

在运行详情页的「Artifacts」中下载。

---

## 🎨 进阶配置

### 多主题支持

创建多个 workflow 文件：

```yaml
# .github/workflows/ai_agent.yml
name: AI Agent Research
on:
  schedule:
    - cron: '0 0 * * *'  # 每天 8:00
env:
  TOPIC: 'AI Agent'
  
# .github/workflows/llm.yml  
name: LLM Research
on:
  schedule:
    - cron: '0 6 * * *'  # 每天 14:00
env:
  TOPIC: 'Large Language Model'
```

### 添加更多数据源

在 `auto_research.py` 中添加：
- 搜索 Google Scholar
- 抓取技术博客
- 监控 GitHub 趋势

### 推送报告到其他地方

修改脚本，支持：
- 发送到钉钉
- 发送到企业微信
- 发送到 Slack
- 推送到 Notion

---

## 💰 费用说明

GitHub Actions 对**公开仓库完全免费**！

免费额度：
- 每月 2,000 分钟运行时间
- 本工作流每次运行约 1-2 分钟
- 每天运行一次，每月约 30-60 分钟
- **完全在免费额度内**

---

## ✅ 完成检查清单

- [ ] 创建了 GitHub 仓库
- [ ] 上传了 workflow 文件
- [ ] 上传了 Python 脚本
- [ ] 配置了 3 个 Secrets
- [ ] 手动触发测试成功
- [ ] 收到了飞书通知
- [ ] 定时任务正常运行

---

## 🎉 恭喜！

现在你已经拥有了一个完全免费的云端自动化研究助手：
- ☁️ 每天自动收集最新论文
- 📄 自动生成研究报告
- 📱 自动发送飞书通知
- 🆓 完全免费，无需维护

---

**有帮助？** 给仓库点个 Star ⭐ 吧！
