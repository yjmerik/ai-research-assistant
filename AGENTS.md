# 飞书 AI 助手 (Feishu Assistant)

基于飞书长连接模式的个人 AI 助理系统，支持大模型意图识别和模块化 Skills 系统。

## 项目概述

**技术栈**: Python 3.11 + FastAPI + lark-oapi (飞书 SDK)
**部署环境**: 阿里云 ECS (Alibaba Cloud Linux 3)
**大模型**: Moonshot (Kimi) v1
**连接方式**: WebSocket 长连接

## 架构设计

### 目录结构

```
feishu-assistant/
├── core/                       # 核心模块
│   ├── __init__.py
│   └── intent_recognizer.py    # 大模型意图识别
├── skills/                     # 技能系统
│   ├── __init__.py
│   ├── base_skill.py           # 技能基类
│   ├── skill_registry.py       # 技能注册表
│   ├── market_skill.py         # 市场指数查询 (腾讯API)
│   ├── stock_skill.py          # 个股分析
│   ├── github_skill.py         # GitHub趋势搜索
│   ├── paper_skill.py          # arXiv论文搜索
│   └── chat_skill.py           # 通用对话
├── services/
│   └── __init__.py
├── main_v2.py                  # 主程序入口 (WebSocket模式)
├── main.py                     # 旧版入口
└── requirements.txt
```

### 核心流程

```
用户消息 → 意图识别(IntentRecognizer) → 技能路由(SkillRegistry) → 执行技能
                                              ↓
                                         返回结果 → 飞书消息
```

### 已注册技能

| 技能名称 | 功能 | 关键参数 |
|----------|------|----------|
| `query_market` | 市场指数查询 | `market`: US/HK/CN |
| `analyze_stock` | 个股分析 | `stock_name_or_code`, `market` |
| `manage_portfolio` | 持仓管理 | `action`, `stock_name`, `price`, `shares` |
| `search_github` | GitHub趋势 | `query`, `language`, `since` |
| `search_papers` | arXiv论文 | `query`, `max_results` |
| `chat` | 通用对话 | `message` |

## 关键 API 和依赖

### 数据来源

| 功能 | API | 说明 |
|------|-----|------|
| 市场指数 | `qt.gtimg.cn` | 腾讯财经，国内稳定 |
| 个股数据 | `qt.gtimg.cn` | 支持 A股/港股/美股 |
| 意图识别 | Moonshot API | 中文理解能力强 |

### 参数映射

**市场名称标准化**:
- `美股`, `美国` → `US`
- `港股`, `香港` → `HK`
- `A股`, `中国`, `内地` → `CN`

**股票代码映射** (部分示例):
```python
CN: {"茅台": "600519", "宁德时代": "300750", "比亚迪": "002594"}
HK: {"腾讯": "00700", "美团": "03690", "小米": "01810"}
US: {"苹果": "AAPL", "特斯拉": "TSLA", "英伟达": "NVDA"}
```

## 部署信息

### 服务器配置

```yaml
服务器: 101.37.82.254 (阿里云 ECS)
系统: Alibaba Cloud Linux 3
部署目录: /opt/feishu-assistant/
服务: feishu-assistant.service (systemd)
```

### 关键文件路径

**本地开发**:
```
/Users/eric/.config/agents/skills/topic-research-assistant/ai-research-assistant/
```

**服务器部署**:
```
/opt/feishu-assistant/
├── app/               # 运行代码
├── .env              # 环境变量
├── update.sh         # 更新脚本
└── venv/             # Python 虚拟环境
```

### 常用命令

```bash
# SSH 登录
ssh vps

# 查看日志
journalctl -u feishu-assistant -f

# 更新代码
cd /opt/feishu-assistant && ./update.sh

# 重启服务
systemctl restart feishu-assistant
systemctl status feishu-assistant
```

### 更新流程

1. 本地开发 → 提交到 GitHub
2. 服务器执行 `./update.sh`
3. 自动拉取代码并重启服务

```bash
# Git 打标签
git tag -a v2.1.0 -m "新增个股分析技能"
git push origin v2.1.0
```

## 开发规范

### 新增技能步骤

1. **继承基类**:
```python
from skills.base_skill import BaseSkill, SkillResult

class NewSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "new_skill_name"
    
    @property
    def description(self) -> str:
        return "技能描述"
    
    async def execute(self, **kwargs) -> SkillResult:
        # 实现逻辑
        return SkillResult(success=True, message="结果")
```

2. **注册技能**:
```python
# 在 main_v2.py 的 init_components() 中
registry.register(NewSkill())
```

3. **意图识别自动适配**:
   - IntentRecognizer 会自动从技能注册表生成 schema
   - 无需修改意图识别代码

### 代码风格

- 使用 `async/await` 异步编程
- 类型注解: `str`, `int`, `Optional[Dict]`, `SkillResult`
- 错误处理: 返回 `SkillResult(success=False, message=错误信息)`
- 日志: 使用 `logging` 模块

## 环境变量

```bash
# 飞书配置
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_USER_OPEN_ID=ou_xxx

# API Keys
KIMI_API_KEY=sk-xxx
GITHUB_TOKEN=ghp_xxx

# 可选: 调试模式
DEBUG=false
```

## 测试命令

### 市场查询
```
/market              # 查询美股
/market US           # 美股
/market 港股         # 港股
/market A股          # A股
今天美股行情怎么样   # 自然语言
```

### 个股分析
```
分析一下茅台
腾讯控股股价多少
AAPL股价怎么样
查询宁德时代
```

### 持仓管理
```
买入茅台 100股 价格1500    # 记录买入交易
卖出腾讯 50股 400元        # 记录卖出交易
/portfolio                 # 查询持仓
/持仓                       # 查询持仓（中文命令）
```

### 其他
```
/github ai-agent
/paper transformer
/help
```

## 已知问题和待办

### 进行中
- [ ] 卡片显示问题 - 暂时禁用卡片，使用文本消息
- [ ] 上下文持久化 - 已建立 context/ 系统

### 待实现
- [ ] 定时任务调度（每日市场报告）
- [ ] 飞书文档自动创建
- [ ] 更多技术指标
- [ ] 价格预警通知
- [ ] 持仓盈亏实时计算（接入实时股价）
- [ ] 交易历史查询
- [ ] 多用户数据隔离优化

## 相关链接

- GitHub: https://github.com/yjmerik/ai-research-assistant
- 飞书开放平台: https://open.feishu.cn/app
- 上下文记录: `context/session_summary_2026-02-17.md`

---

**当前版本**: v2.2.0  
**最后更新**: 2026-02-20
