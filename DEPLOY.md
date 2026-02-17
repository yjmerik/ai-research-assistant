# 🚀 飞书 AI 助手 - 部署指南

## 📋 前置要求

- 阿里云 ECS (2核4G+)
- Ubuntu 22.04 / CentOS 8
- 免费域名 (如 .top, .xyz)
- 飞书企业账号

## 🎯 快速部署 (5分钟)

### 1. 准备域名

在阿里云/腾讯云申请免费域名，添加 A 记录指向 ECS 公网 IP：
```
assistant.yourname.top → 你的ECS_IP
```

### 2. SSH 登录 ECS 并执行部署

```bash
# 登录服务器
ssh root@你的ECS_IP

# 下载部署脚本
curl -fsSL https://raw.githubusercontent.com/yjmerik/ai-research-assistant/main/deploy.sh -o deploy.sh
chmod +x deploy.sh

# 设置环境变量并执行
export DOMAIN="assistant.yourname.top"
export EMAIL="your-email@example.com"
export FEISHU_APP_ID="cli_xxx"
export FEISHU_APP_SECRET="xxx"
export FEISHU_USER_OPEN_ID="ou_xxx"
export KIMI_API_KEY="sk-xxx"
export GITHUB_TOKEN="ghp_xxx"

./deploy.sh
```

### 3. 配置飞书机器人

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用 → 添加机器人
3. 权限管理 → 开通权限：
   - `im:chat:readonly` (读取会话)
   - `im:message:send_as_bot` (发送消息)
4. 事件订阅 → 添加事件：`im.message.receive_v1`
5. 配置请求地址：`https://assistant.yourname.top/webhook/feishu`
6. 发布应用 → 创建版本 → 申请发布

### 4. 测试

在飞书私聊中找到机器人，发送：
```
/help
/market
/github ai-agent
```

## 📁 部署后目录结构

```
/opt/feishu-assistant/
├── docker-compose.yml      # Docker 配置
├── .env                    # 环境变量
├── nginx/
│   ├── nginx.conf          # Nginx 配置
│   ├── ssl/                # SSL 证书
│   └── logs/               # 访问日志
├── data/
│   └── assistant.db        # SQLite 数据库
├── logs/
│   └── assistant.log       # 应用日志
└── assistant/              # 应用代码
    └── app/
```

## 🔧 常用命令

```bash
cd /opt/feishu-assistant

# 查看日志
docker-compose logs -f assistant
docker-compose logs -f nginx

# 重启服务
docker-compose restart

# 更新代码后重建
docker-compose up -d --build

# 查看数据库
sqlite3 data/assistant.db ".tables"

# 备份数据
tar czvf backup-$(date +%Y%m%d).tar.gz data/
```

## 🐛 故障排查

### 证书申请失败
```bash
# 检查域名解析
dig assistant.yourname.top

# 手动申请证书
certbot certonly --standalone -d assistant.yourname.top
```

### 飞书收不到回复
```bash
# 检查服务状态
docker-compose ps
curl http://localhost:8000/health

# 查看应用日志
docker-compose logs assistant | tail -50
```

### Webhook 验证失败
确保飞书平台配置的 URL 使用 HTTPS，且能正常访问：
```bash
curl -I https://assistant.yourname.top/webhook/feishu
```

## 📚 Phase 1 功能清单

| 命令 | 功能 | 示例 |
|------|------|------|
| `/help` | 显示帮助 | `/help` |
| `/market` | 查询市场行情 | `/market`, `/market US` |
| `/github` | 搜索 GitHub 趋势 | `/github ai-agent` |
| `/paper` | 搜索 arXiv 论文 | `/paper transformer` |
| `/clear` | 清除会话历史 | `/clear` |
| `/status` | 查看系统状态 | `/status` |

## 🗓️ Phase 2 计划

- [ ] AI 意图识别（自然语言理解）
- [ ] 任务规划与多步骤执行
- [ ] 定时任务调度
- [ ] 飞书文档生成
- [ ] 对话上下文记忆增强
