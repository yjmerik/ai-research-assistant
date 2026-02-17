# 飞书 AI 助手 - 开发与部署工作流

## 📋 项目结构

```
ai-research-assistant/
├── feishu-assistant/           # 飞书助手核心代码
│   ├── main.py                 # 主程序
│   ├── requirements.txt        # Python 依赖
│   ├── update.sh               # 服务器更新脚本
│   ├── .env.example            # 环境变量示例
│   └── README.md               # 项目说明
├── .github/                    # GitHub Actions
└── ...
```

## 🔄 开发工作流

### 1. 本地开发

```bash
# 克隆仓库
git clone https://github.com/yjmerik/ai-research-assistant.git
cd ai-research-assistant/feishu-assistant

# 安装依赖
pip3 install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入配置

# 本地运行测试
python3 main.py
```

### 2. 提交代码到 GitHub

```bash
# 修改代码...
vim main.py

# 提交并推送
git add -A
git commit -m "feat: 添加新功能"
git push origin main
```

### 3. 服务器更新（自动部署）

```bash
# SSH 登录服务器
ssh vps

# 一键更新
feishu-update

# 或者手动执行
/opt/feishu-assistant/update.sh
```

## 🚀 服务器配置

- **服务器**: 阿里云 ECS (101.37.82.254)
- **部署目录**: `/opt/feishu-assistant`
- **服务管理**: systemd (`feishu-assistant.service`)

### 快捷命令

| 命令 | 功能 |
|------|------|
| `feishu-update` | 从 GitHub 拉取最新代码并重启 |
| `feishu-logs` | 查看实时日志 |
| `feishu-status` | 查看服务状态 |
| `feishu-restart` | 重启服务 |

### 系统服务命令

```bash
# 查看状态
systemctl status feishu-assistant

# 查看日志
journalctl -u feishu-assistant -f

# 重启服务
systemctl restart feishu-assistant

# 停止服务
systemctl stop feishu-assistant
```

## 📝 更新流程示例

### 场景：添加新命令 `/weather`

1. **本地修改**
   ```bash
   vim feishu-assistant/main.py
   # 添加 weather 处理函数
   ```

2. **本地测试**
   ```bash
   python3 feishu-assistant/main.py
   # 测试新功能
   ```

3. **提交代码**
   ```bash
   git add feishu-assistant/main.py
   git commit -m "feat: 添加天气查询命令 /weather"
   git push origin main
   ```

4. **服务器更新**
   ```bash
   ssh vps
   feishu-update
   ```

5. **验证**
   - 在飞书发送 `/weather` 测试

## 🛡️ 安全注意事项

1. **不要在 GitHub 提交 `.env` 文件**（已添加到 .gitignore）
2. **敏感信息存储在服务器本地** `/opt/feishu-assistant/.env`
3. **GitHub Token 等密钥只在服务器环境变量中设置**

## 🔧 故障排查

### 服务无法启动

```bash
# 查看错误日志
journalctl -u feishu-assistant -n 50

# 手动运行查看错误
cd /opt/feishu-assistant
python3 main.py
```

### 更新失败

```bash
# 手动更新
cd /opt/feishu-assistant
git fetch origin main
git reset --hard origin/main
cp feishu-assistant/main.py ./
systemctl restart feishu-assistant
```

### 消息无法接收

1. 检查飞书应用是否已发布
2. 检查事件订阅是否添加 `im.message.receive_v1`
3. 检查权限是否开通 `im:message:send_as_bot`
4. 查看服务日志 `feishu-logs`
