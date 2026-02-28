# 飞书 AI 助手 - Agent 开发指南

## 项目概述

基于飞书长连接模式的个人 AI 助理，支持大模型意图识别和 Skills 系统。

## 项目结构

```
feishu-assistant/
├── app/
│   ├── main_v2.py          # 主程序入口 (WebSocket 连接)
│   └── core/
│       └── intent_recognizer.py  # 大模型意图识别
├── skills/
│   ├── skill_registry.py   # 技能注册表
│   ├── base_skill.py      # 技能基类
│   ├── market_skill.py    # 市场行情技能
│   ├── github_skill.py    # GitHub 趋势技能
│   ├── paper_skill.py     # 论文搜索技能
│   ├── chat_skill.py      # 对话技能
│   ├── stock_skill.py     # 股票分析技能 (核心)
│   ├── portfolio_skill.py       # 持仓管理技能
│   └── portfolio_tracker_skill.py # 持仓追踪技能
└── .env                   # 环境变量配置
```

## 核心技能详解

### 1. stock_skill.py - 股票深度分析

**功能**：
- 实时行情查询（A股/港股/美股）
- 估值数据分析（PE/PB/股息率）
- 财务数据查询
- DCF 估值计算
- AI 深度分析报告

**支持的股票代码格式**：
- A股: `sh600519` (上海), `sz000001` (深圳)
- 港股: `hk00700`, `hk9988`
- 美股: `usAAPL`, `usMSFT`

**关键方法**：
```python
# 数据获取
async def _fetch_quote_qveris(tencent_code)  # 实时行情
async def _fetch_financial_qveris(tencent_code) # 财务数据
async def _fetch_valuation_data(tencent_code)   # 估值数据

# 数据格式化
def _format_deep_analysis_message()  # 深度分析报告
```

**市值单位处理**：
- API 返回：百万美元 (million USD)
- 转换：除以 1000 → 十亿美元 (billion USD)
- 显示逻辑：
  - ≥ 1000 billion → 万亿美元 (trillion)
  - ≥ 1 billion → 十亿美元 (billion)
  - < 1 billion → 亿美元

**缓存策略**：
- 实时行情：交易时间内5分钟，非交易时间持续缓存
- 估值数据：4小时（交易时间）/ 24小时（非交易时间）
- 财务数据：24小时
- 公司信息：48小时

### 2. portfolio_skill.py - 持仓管理

**功能**：
- 记录买入/卖出交易
- 查询持仓情况
- 计算持仓成本

**命令**：
- `/持仓` - 查看持仓
- `/reset` - 重置持仓

### 3. portfolio_tracker_skill.py - 持仓追踪

**功能**：
- 自动追踪持仓股票价格
- 计算内在价值和安全边际
- 定时发送通知

## 技能注册与调用

### 注册技能 (main_v2.py)
```python
registry.register(StockSkill(config={"kimi_api_key": KIMI_API_KEY, "qveris_api_key": QVERIS_API_KEY}))
registry.register(PortfolioSkill(config={"kimi_api_key": KIMI_API_KEY}))
```

### 调用技能
```python
skill = registry.get("analyze_stock")
result = await skill.execute(stock_name="苹果", market="美股")
```

## 快捷命令

| 命令 | 功能 |
|------|------|
| `/m` | 市场查询 |
| `/g` | GitHub 趋势 |
| `/p` | 论文搜索 |
| `/po` | 持仓查询 |
| `/h` | 帮助 |

## 环境变量 (.env)

```
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret
KIMI_API_KEY=your_kimi_api_key
QVERIS_API_KEY=your_qveris_api_key
GITHUB_TOKEN=your_github_token
```

## 服务部署

### 部署路径
- 代码目录：`/opt/feishu-assistant/app/`
- 日志目录：`/opt/feishu-assistant/logs/`

### 启动服务
```bash
cd /opt/feishu-assistant
source .env
/usr/bin/python3.11 app/main_v2.py >> logs/app.log 2>&1 &
```

### 部署更新
```bash
# 本地修改后
scp skills/stock_skill.py vps:/opt/feishu-assistant/app/skills/
# 重启服务
ssh vps 'pkill -f "main_v2.py"; sleep 2; cd /opt/feishu-assistant && source .env && /usr/bin/python3.11 app/main_v2.py >> logs/app.log 2>&1 &'
```

## Qveris API

### 股票数据 API
- `ths_ifind.real_time_quotation.v1` - 实时行情（A股/港股）
- `finnhub.quote.retrieve.v1.f72cf5ef` - 美股行情
- `finnhub.company.profile.v2.get.v1` - 公司信息
- `finnhub.company.metrics.get.v1` - 公司估值指标
- `ths_ifind.financial_statements.v1` - 财务报表

### API 返回数据处理
- marketCapitalization: 百万美元 → 除以1000 = 十亿美元
- dividend_yield: 百分比形式（如0.3865表示0.3865%）
- PE/PB: 直接使用，无需转换

## 常见问题

### 1. 市值显示错误
- 检查 API 返回单位（百万美元 vs 十亿美元）
- 确认显示阈值逻辑（≥1000 billion → trillion）

### 2. 服务无法启动
- 检查 .env 环境变量
- 检查 Python 版本（需 3.11+）
- 检查依赖安装

### 3. 日志无输出
- 检查日志文件权限
- 确认重定向正确 (`>> logs/app.log 2>&1`)
