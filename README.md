# AI Research Assistant

🤖 自动化研究助手 - 每天自动收集学术信息，生成研究报告并发送到飞书

## ✨ 功能特点

- ☁️ **云端自动运行** - 使用 GitHub Actions，24/7 不间断
- 🆓 **完全免费** - GitHub Actions 对公开仓库免费
- 📚 **自动收集** - 每天搜索 arXiv 最新论文
- 📝 **生成报告** - 自动整理生成结构化报告
- 📱 **飞书通知** - 自动发送消息到飞书
- ⏰ **定时执行** - 每天早上 8:00 自动运行
- 🖐️ **手动触发** - 支持随时手动执行

## 🚀 快速开始

### 1. Fork 本仓库

点击右上角「Fork」按钮，将仓库复制到你的账号下。

### 2. 配置 Secrets

进入仓库 → Settings → Secrets and variables → Actions → New repository secret

添加以下 3 个 secrets：

| Secret 名称 | 说明 |
|------------|------|
| `FEISHU_APP_ID` | 飞书应用 ID |
| `FEISHU_APP_SECRET` | 飞书应用密钥 |
| `FEISHU_USER_OPEN_ID` | 接收消息的用户的 Open ID |

### 3. 手动测试

进入 Actions → Daily Research Collection → Run workflow

### 4. 完成！

每天早上 8:00 会自动收集研究信息并发送给你。

## 📁 项目结构

```
.
├── .github/
│   ├── workflows/
│   │   └── daily_research.yml    # GitHub Actions 工作流
│   └── scripts/
│       └── auto_research.py       # 自动化脚本
├── README.md                       # 本文件
└── GITHUB_ACTIONS_SETUP.md       # 详细配置指南
```

## ⚙️ 自定义配置

### 修改研究主题

编辑 `.github/workflows/daily_research.yml`：

```yaml
env:
  TOPIC: '你的研究主题'  # 修改这里
  ARXIV_COUNT: '10'      # 论文数量
```

### 修改执行时间

编辑 workflow 文件中的 cron 表达式：

```yaml
on:
  schedule:
    - cron: '0 0 * * *'  # UTC 0:00 = 北京时间 8:00
```

Cron 格式：`分 时 日 月 周`

## 📱 使用方式

### 自动执行

每天早上 8:00（北京时间）自动执行：
1. 搜索 arXiv 最新论文
2. 生成研究简报
3. 创建飞书文档
4. 发送消息通知

### 手动触发

1. 进入仓库 Actions 页面
2. 选择「Daily Research Collection」
3. 点击「Run workflow」
4. 输入主题和数量
5. 点击运行

## 🔧 技术栈

- **GitHub Actions** - 自动化执行
- **Python 3.11** - 脚本语言
- **lark-oapi** - 飞书 API SDK
- **arXiv API** - 学术论文数据

## 📝 报告内容

生成的报告包含：
- 📊 数据概览（论文数量、来源）
- 📑 论文列表（标题、作者、摘要、链接）
- 🔍 核心发现
- 📅 生成时间

## 🐛 故障排查

### Actions 运行失败

1. 检查 Secrets 是否配置正确
2. 查看 Actions 日志
3. 确认飞书应用权限已开通

### 飞书通知未收到

1. 检查 `FEISHU_USER_OPEN_ID` 是否正确
2. 确认飞书应用有发送消息权限
3. 查看飞书应用是否发布

## 📄 许可证

MIT License

## 🙏 致谢

- 感谢 arXiv 提供开放的学术论文 API
- 感谢飞书提供便捷的办公协作平台
- 感谢 GitHub 提供免费的 Actions 服务

---

**如果这个项目对你有帮助，请给个 Star ⭐**
