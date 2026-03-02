# 飞书 AI 助手

基于飞书长连接模式的个人 AI 助理，无需域名即可部署。

## 功能

- `/help` - 显示帮助
- `/market` - 查询市场行情
- `/github <关键词>` - 搜索 GitHub 趋势
- `/paper <主题>` - 搜索 arXiv 论文
- `/status` - 系统状态
- `/clear` - 清除会话
- `/evo` 或 `/create` - 创建新技能（EvoAgent）

### EvoAgent 自主进化技能

使用 Kimi K2.5 或 MiniMax M2.5 大模型，根据用户需求自动创建新技能。

**使用方式：**
1. 发送 `/evo 帮我创建一个查询天气的技能`
2. 确认设计（发送 `确认 {design_id}`）
3. 使用新创建的技能

**查询已保存的技能：**
- 发送 `/evo list` 或 `/evo 列出技能`

**持久化：**
- 技能保存到 `/opt/feishu-assistant/data/auto_skills.json`
- 重启后自动加载已保存的技能

**支持的模型：**
- Kimi K2.5（默认）
- MiniMax M2.5（在需求中指定 "用 minimax"）

## 部署

### 1. 克隆代码

```bash
git clone https://github.com/yjmerik/ai-research-assistant.git
cd ai-research-assistant/feishu-assistant
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的配置
```

### 3. 安装依赖

```bash
pip3 install -r requirements.txt
```

### 4. 运行

```bash
python3 main.py
```

## 服务器部署

```bash
# 一键更新并重启
./update.sh
```

## 飞书配置

1. 访问 https://open.feishu.cn/app 创建企业自建应用
2. 启用机器人能力
3. 事件订阅添加 `im.message.receive_v1`
4. 开通权限：`im:chat:readonly`, `im:message:send_as_bot`
5. 发布应用

## 更新

推送代码到 GitHub 后，服务器自动拉取：

```bash
ssh vps
./update.sh
```
