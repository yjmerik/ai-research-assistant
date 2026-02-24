#!/usr/bin/env python3
"""
持仓跟踪定时任务 - 按市场开盘时间分别追踪
支持 A股、港股、美股在不同时段分别运行

用法:
  # 自动判断当前市场并追踪
  /usr/bin/python3.11 portfolio_tracker_cron.py
  
  # 强制追踪指定市场
  /usr/bin/python3.11 portfolio_tracker_cron.py --market A股
  /usr/bin/python3.11 portfolio_tracker_cron.py --market 港股
  /usr/bin/python3.11 portfolio_tracker_cron.py --market 美股
  
  # 强制追踪所有市场
  /usr/bin/python3.11 portfolio_tracker_cron.py --all

Crontab 配置示例:
  # A股时段 (9:30-11:30, 13:00-15:00)
  */30 9-11,13-15 * * 1-5 /usr/bin/python3.11 /opt/feishu-assistant/portfolio_tracker_cron.py --market A股
  
  # 港股时段 (9:30-12:00, 13:00-16:00)
  */30 9-11,13-15 * * 1-5 /usr/bin/python3.11 /opt/feishu-assistant/portfolio_tracker_cron.py --market 港股
  30 12 * * 1-5 /usr/bin/python3.11 /opt/feishu-assistant/portfolio_tracker_cron.py --market 港股
  
  # 美股时段 (21:30-23:30, 0:00-5:00)
  30,00 21-23 * * 1-5 /usr/bin/python3.11 /opt/feishu-assistant/portfolio_tracker_cron.py --market 美股
  */30 0-5 * * 2-6 /usr/bin/python3.11 /opt/feishu-assistant/portfolio_tracker_cron.py --market 美股
"""
import os
import sys
import asyncio
import json
import httpx
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

# 添加项目路径
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR / "app"))

# 加载环境变量
env_file = SCRIPT_DIR / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

# 配置
DB_PATH = SCRIPT_DIR / "data" / "portfolio.db"
STATE_FILE = SCRIPT_DIR / "data" / "portfolio_tracker_state.json"
VALUATION_DB = SCRIPT_DIR / "data" / "valuation_history.db"

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
FEISHU_USER_OPEN_ID = os.environ.get("FEISHU_USER_OPEN_ID")
KIMI_API_KEY = os.environ.get("KIMI_API_KEY")


# ==================== 市场时间判断模块 ====================

class MarketTradingHours:
    """市场交易时间管理"""
    
    # 各市场交易时间（北京时间）
    MARKET_HOURS = {
        "A股": {
            "weekdays": [0, 1, 2, 3, 4],  # 周一到周五
            "sessions": [
                (9, 30, 11, 30),   # 上午 9:30-11:30
                (13, 0, 15, 0),    # 下午 13:00-15:00
            ],
            "timezone": "Asia/Shanghai",
        },
        "港股": {
            "weekdays": [0, 1, 2, 3, 4],  # 周一到周五
            "sessions": [
                (9, 30, 12, 0),    # 上午 9:30-12:00
                (13, 0, 16, 0),    # 下午 13:00-16:00
            ],
            "timezone": "Asia/Hong_Kong",
        },
        "美股": {
            "weekdays": [0, 1, 2, 3, 4],  # 周一到周五（北京时间对应美股周日晚上到周五晚上）
            "sessions": [
                # 夏令时 21:30-04:00, 冬令时 22:30-05:00
                # 这里使用合并时段 21:30-05:00 覆盖两种情况
                (21, 30, 23, 59),  # 晚上 21:30-23:59
                (0, 0, 5, 0),      # 凌晨 00:00-05:00（次日）
            ],
            "timezone": "America/New_York",
            "note": "美股跨天，周一美股对应北京时间周一晚上到周二凌晨"
        },
    }
    
    @classmethod
    def is_trading_time(cls, market: str, dt: Optional[datetime] = None) -> bool:
        """
        判断指定市场当前是否处于交易时间
        
        Args:
            market: 市场名称 (A股/港股/美股)
            dt: 指定时间，默认为当前时间
        """
        if dt is None:
            dt = datetime.now()
        
        if market not in cls.MARKET_HOURS:
            return False
        
        config = cls.MARKET_HOURS[market]
        
        # 检查星期
        weekday = dt.weekday()
        
        # 美股特殊处理：美股周一 = 北京时间周一晚上到周二凌晨
        if market == "美股":
            # 美股交易日是周日晚上到周五晚上（北京时间）
            # 但这里我们按照北京时间的工作日来判断
            # 周一凌晨（0-5点）实际上对应美股周日晚上
            if weekday == 0 and dt.hour < 5:
                # 周一凌晨，属于美股周日晚上，美股不开市
                return False
            if weekday == 4 and dt.hour >= 21:
                # 周五晚上，美股开市
                pass
            if weekday == 5 and dt.hour < 5:
                # 周六凌晨，美股周五晚上，开市
                pass
        
        if weekday not in config["weekdays"]:
            # 周末检查美股跨天情况
            if market == "美股":
                # 周六凌晨0-5点，美股周五晚上仍开市
                if weekday == 5 and dt.hour < 5:
                    pass
                else:
                    return False
            else:
                return False
        
        # 检查时段
        hour, minute = dt.hour, dt.minute
        time_val = hour * 60 + minute
        
        for start_h, start_m, end_h, end_m in config["sessions"]:
            start_val = start_h * 60 + start_m
            end_val = end_h * 60 + end_m
            
            if start_val <= time_val <= end_val:
                return True
        
        return False
    
    @classmethod
    def get_current_trading_markets(cls, dt: Optional[datetime] = None) -> List[str]:
        """获取当前处于交易时间的所有市场"""
        if dt is None:
            dt = datetime.now()
        
        trading_markets = []
        for market in cls.MARKET_HOURS.keys():
            if cls.is_trading_time(market, dt):
                trading_markets.append(market)
        
        return trading_markets
    
    @classmethod
    def get_market_status(cls, dt: Optional[datetime] = None) -> Dict[str, str]:
        """获取所有市场状态"""
        if dt is None:
            dt = datetime.now()
        
        status = {}
        for market in cls.MARKET_HOURS.keys():
            if cls.is_trading_time(market, dt):
                status[market] = "🟢 交易中"
            else:
                status[market] = "⚪ 休市"
        
        return status


# ==================== 价值投资分析模块 ====================

class ValueInvestingAnalyzer:
    """简化版价值投资分析器"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.api_base = "https://api.moonshot.cn/v1"
    
    async def analyze(self, stock_code: str, stock_name: str, 
                      current_price: float, market: str) -> Dict[str, Any]:
        """执行价值投资分析"""
        financial_data = await self._get_financial_data(stock_code, stock_name, current_price, market)
        
        intrinsic_value = self._calculate_intrinsic_value(financial_data, current_price)
        
        margin_of_safety = (intrinsic_value - current_price) / intrinsic_value if intrinsic_value > 0 else 0
        
        if margin_of_safety > 0.5:
            recommendation = "强烈买入"
        elif margin_of_safety > 0.3:
            recommendation = "买入"
        elif margin_of_safety > 0.1:
            recommendation = "持有"
        elif margin_of_safety > -0.1:
            recommendation = "观望"
        else:
            recommendation = "卖出"
        
        return {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "current_price": current_price,
            "intrinsic_value": intrinsic_value,
            "margin_of_safety": margin_of_safety,
            "recommendation": recommendation,
            "financial_data": financial_data,
            "analysis_date": datetime.now().strftime('%Y-%m-%d')
        }
    
    async def _get_financial_data(self, stock_code: str, stock_name: str, current_price: float, market: str) -> Dict:
        """获取财务数据"""
        data = {
            'eps': 0, 'bps': 0, 'roe': 0, 'pe': 0, 'pb': 0,
            'debt_ratio': 50, 'revenue_growth': 10, 'profit_growth': 10
        }
        
        try:
            if market == "A股":
                prefix = "sh" if stock_code.startswith('6') else "sz"
                tencent_code = f"{prefix}{stock_code}"
            elif market == "港股":
                tencent_code = f"hk{stock_code}"
            elif market == "美股":
                tencent_code = f"us{stock_code}"
            else:
                tencent_code = stock_code
            
            url = f"http://qt.gtimg.cn/q={tencent_code}"
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10)
                resp.encoding = 'gbk'
                text = resp.text
            
            if '="' in text:
                parts = text.split('="')
                if len(parts) >= 2:
                    values = parts[1].rstrip('"').rstrip(';').split('~')
                    if len(values) >= 45:
                        data['pe'] = float(values[39]) if values[39] else 0
                        if data['pe'] > 0 and current_price > 0:
                            data['eps'] = current_price / data['pe']
            
            if self.api_key:
                ai_data = await self._ai_estimate_metrics(stock_name, stock_code)
                data.update(ai_data)
                
        except Exception as e:
            print(f"获取财务数据失败 {stock_code}: {e}")
        
        return data
    
    async def _ai_estimate_metrics(self, stock_name: str, stock_code: str) -> Dict:
        """AI估算财务指标"""
        try:
            prompt = f"估算{stock_name}({stock_code})的ROE(%)、营收增长率(%)、净利润增长率(%)，只返回JSON: {{'roe': x, 'revenue_growth': y, 'profit_growth': z}}"
            
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": "moonshot-v1-8k",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 200
                    },
                    timeout=10
                )
                
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    json_match = re.search(r'\{[^}]+\}', content)
                    if json_match:
                        return json.loads(json_match.group())
        except:
            pass
        
        return {'roe': 12, 'revenue_growth': 10, 'profit_growth': 10}
    
    def _calculate_intrinsic_value(self, financial_data: Dict, current_price: float) -> float:
        """计算内在价值"""
        eps = financial_data.get('eps', 1)
        growth = financial_data.get('profit_growth', 10) / 100
        
        if growth > 0.2:
            fair_pe = 25
        elif growth > 0.15:
            fair_pe = 20
        elif growth > 0.10:
            fair_pe = 15
        else:
            fair_pe = 12
        
        pe_value = eps * fair_pe
        intrinsic = pe_value * 0.7 + current_price * 0.3
        
        return max(intrinsic, current_price * 0.5)
    
    def analyze_change(self, current: Dict, previous: Dict) -> Dict[str, Any]:
        """分析估值变化"""
        prev_price = previous.get('current_price', current['current_price'])
        prev_intrinsic = previous.get('intrinsic_value', current['intrinsic_value'])
        prev_mos = previous.get('margin_of_safety', current['margin_of_safety'])
        prev_date = previous.get('analysis_date', current['analysis_date'])
        
        price_change = (current['current_price'] - prev_price) / prev_price if prev_price > 0 else 0
        intrinsic_change = (current['intrinsic_value'] - prev_intrinsic) / prev_intrinsic if prev_intrinsic > 0 else 0
        mos_change = current['margin_of_safety'] - prev_mos
        
        try:
            prev_dt = datetime.strptime(prev_date, '%Y-%m-%d')
            curr_dt = datetime.strptime(current['analysis_date'], '%Y-%m-%d')
            days = (curr_dt - prev_dt).days
        except:
            days = 0
        
        price_driven = abs(price_change) > abs(intrinsic_change) * 2
        fundamental_driven = abs(intrinsic_change) > 0.05
        
        conclusion = []
        if abs(price_change) > 0.1:
            direction = "上涨" if price_change > 0 else "下跌"
            conclusion.append(f"股价大幅{direction} {abs(price_change):.1%}")
        
        if fundamental_driven:
            direction = "提升" if intrinsic_change > 0 else "下降"
            conclusion.append(f"内在价值{direction} {abs(intrinsic_change):.1%}")
        
        if mos_change > 0.1:
            conclusion.append(f"安全边际扩大 {mos_change:.1%}")
        elif mos_change < -0.1:
            conclusion.append(f"安全边际收窄 {abs(mos_change):.1%}")
        
        recommendation = current['recommendation']
        if mos_change > 0.15:
            if '买入' in recommendation:
                recommendation += "（安全边际改善，可加仓）"
            else:
                recommendation = "关注（安全边际改善）"
        elif mos_change < -0.15:
            if '卖出' in recommendation:
                recommendation += "（安全边际收窄，考虑止损）"
            else:
                recommendation = "谨慎持有（安全边际收窄）"
        
        return {
            'price_change': price_change,
            'intrinsic_change': intrinsic_change,
            'mos_change': mos_change,
            'days': days,
            'price_driven': price_driven,
            'fundamental_driven': fundamental_driven,
            'conclusion': '，'.join(conclusion) if conclusion else "估值基本稳定",
            'recommendation': recommendation
        }


# ==================== 估值历史管理 ====================

class ValuationHistory:
    """估值历史管理"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        import sqlite3
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS valuations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT,
                    current_price REAL,
                    intrinsic_value REAL,
                    margin_of_safety REAL,
                    recommendation TEXT DEFAULT '',
                    analysis_date TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
    
    def save(self, data: Dict):
        import sqlite3
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute('''
                INSERT INTO valuations 
                (stock_code, stock_name, current_price, intrinsic_value, 
                 margin_of_safety, recommendation, analysis_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['stock_code'], data['stock_name'], data['current_price'],
                data['intrinsic_value'], data['margin_of_safety'],
                data['recommendation'], data['analysis_date']
            ))
            conn.commit()
    
    def get_last(self, stock_code: str) -> Optional[Dict]:
        import sqlite3
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                'SELECT * FROM valuations WHERE stock_code = ? ORDER BY created_at DESC LIMIT 1',
                (stock_code,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'stock_code': row[1], 'stock_name': row[2],
                    'current_price': row[3], 'intrinsic_value': row[4],
                    'margin_of_safety': row[5], 'recommendation': row[6],
                    'analysis_date': row[7]
                }
            return None


# ==================== 持仓数据获取 ====================

async def get_current_price(stock_code: str, market: str) -> Optional[float]:
    """获取股票/基金当前价格"""
    try:
        if market == "港股":
            prefix = "hk"
        elif market == "美股":
            prefix = "us"
        elif market == "基金":
            if len(stock_code) == 5:
                prefix = "sh" if stock_code.startswith(('51', '56', '58', '60', '50')) else "sz"
            else:
                prefix = "sz" if stock_code.startswith(('15', '16')) else "sh"
        else:
            prefix = "sh" if stock_code.startswith('6') else "sz"
        
        tencent_code = f"{prefix}{stock_code}"
        url = f"http://qt.gtimg.cn/q={tencent_code}"
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10)
            resp.encoding = 'gbk'
            data = resp.text
        
        if '="' in data:
            parts = data.split('="')
            if len(parts) >= 2:
                values = parts[1].rstrip('"').rstrip(';').split('~')
                if len(values) >= 4 and values[3]:
                    return float(values[3])
    except Exception as e:
        print(f"获取价格失败 {stock_code}: {e}")
    return None


def get_holdings(user_id: str, market_filter: Optional[str] = None) -> List[Dict]:
    """
    获取用户持仓，支持按市场过滤
    
    Args:
        user_id: 用户ID
        market_filter: 市场过滤条件 (A股/港股/美股/基金)，None表示所有
    """
    import sqlite3
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if market_filter:
                cursor.execute('''
                    SELECT stock_name, stock_code, market,
                        SUM(CASE WHEN action = 'buy' THEN shares ELSE -shares END) as total_shares,
                        SUM(CASE WHEN action = 'buy' THEN total_amount ELSE -total_amount END) as total_cost
                    FROM transactions
                    WHERE user_id = ? AND market = ?
                    GROUP BY stock_code
                    HAVING total_shares > 0
                    ORDER BY total_cost DESC
                ''', (user_id, market_filter))
            else:
                cursor.execute('''
                    SELECT stock_name, stock_code, market,
                        SUM(CASE WHEN action = 'buy' THEN shares ELSE -shares END) as total_shares,
                        SUM(CASE WHEN action = 'buy' THEN total_amount ELSE -total_amount END) as total_cost
                    FROM transactions
                    WHERE user_id = ?
                    GROUP BY stock_code
                    HAVING total_shares > 0
                    ORDER BY total_cost DESC
                ''', (user_id,))
            
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"获取持仓失败: {e}")
        return []


def get_holdings_by_markets(user_id: str, markets: List[str]) -> Dict[str, List[Dict]]:
    """
    按市场分组获取持仓
    
    Returns:
        Dict[str, List[Dict]]: {市场名称: 持仓列表}
    """
    result = {market: [] for market in markets}
    
    for market in markets:
        holdings = get_holdings(user_id, market)
        result[market] = holdings
    
    return result


# ==================== 飞书消息发送 ====================

async def send_feishu_message(message: str) -> bool:
    """发送飞书消息"""
    try:
        async with httpx.AsyncClient() as client:
            # 获取token
            resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/",
                json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
                timeout=10
            )
            token = resp.json().get("tenant_access_token")
            if not token:
                return False
            
            # 发送消息
            resp = await client.post(
                "https://open.feishu.cn/open-apis/im/v1/messages",
                headers={"Authorization": f"Bearer {token}"},
                params={"receive_id_type": "open_id"},
                json={
                    "receive_id": FEISHU_USER_OPEN_ID,
                    "msg_type": "text",
                    "content": json.dumps({"text": message})
                },
                timeout=10
            )
            return resp.status_code == 200 and resp.json().get("code") == 0
    except Exception as e:
        print(f"发送失败: {e}")
        return False


# ==================== 持仓追踪核心逻辑 ====================

async def track_market(market: str, analyzer: ValueInvestingAnalyzer, 
                       history: ValuationHistory) -> Tuple[bool, str]:
    """
    追踪指定市场的持仓
    
    Returns:
        (是否有持仓, 报告消息)
    """
    print(f"\n{'='*60}")
    print(f"📊 追踪市场: {market}")
    print(f"{'='*60}")
    
    # 获取该市场的持仓
    holdings = get_holdings(FEISHU_USER_OPEN_ID, market)
    
    if not holdings:
        print(f"📌 {market} 没有持仓")
        return False, f"📌 {market} 当前没有持仓"
    
    print(f"📈 {market} 持仓数量: {len(holdings)}")
    
    # 分析每个持仓
    total_cost = 0
    total_value = 0
    valuation_reports = []
    
    for h in holdings:
        code = h['stock_code']
        
        # 获取价格
        price = await get_current_price(code, market)
        h['current_price'] = price
        
        if price:
            h['current_value'] = price * h['total_shares']
            h['pnl'] = h['current_value'] - h['total_cost']
            total_cost += h['total_cost']
            total_value += h['current_value']
        
        # 价值投资分析（仅股票）
        if market not in ['基金'] and price and KIMI_API_KEY:
            try:
                print(f"  📈 分析 {h['stock_name']}...")
                last = history.get_last(code)
                
                result = await analyzer.analyze(code, h['stock_name'], price, market)
                history.save(result)
                
                # 估值变化分析
                is_first = last is None
                change_analysis = None
                if not is_first:
                    change_analysis = analyzer.analyze_change(result, last)
                    print(f"    价格变化: {change_analysis['price_change']:+.2%}, "
                          f"内在价值变化: {change_analysis['intrinsic_change']:+.2%}, "
                          f"安全边际变化: {change_analysis['mos_change']:+.2%}")
                
                # 格式化报告
                prefix = "【首次】" if is_first else "【更新】"
                report = f"""{prefix}价值投资分析 - {h['stock_name']}
• 当前价格: ¥{result['current_price']:.2f}
• 内在价值: ¥{result['intrinsic_value']:.2f}
• 安全边际: {result['margin_of_safety']:+.1%}
• 投资建议: {result['recommendation']}
• ROE: {result['financial_data'].get('roe', 0):.1f}%
• 增长率: {result['financial_data'].get('profit_growth', 0):.1f}%"""
                
                # 添加变化分析
                if change_analysis:
                    report += f"""

📊 估值变化分析 (距上次 {change_analysis['days']} 天):
• 价格变化: {change_analysis['price_change']:+.2%}
• 内在价值变化: {change_analysis['intrinsic_change']:+.2%}
• 安全边际变化: {change_analysis['mos_change']:+.2%}
• 分析结论: {change_analysis['conclusion']}
• 操作建议: {change_analysis['recommendation']}

💡 变化原因:
"""
                    if change_analysis['price_driven']:
                        report += "- 主要由市场情绪/价格波动驱动\n"
                    if change_analysis['fundamental_driven']:
                        report += "- 公司基本面发生变化\n"
                    if not change_analysis['price_driven'] and not change_analysis['fundamental_driven']:
                        report += "- 估值变化较小，保持观察\n"
                
                valuation_reports.append(report)
                
                h['intrinsic_value'] = result['intrinsic_value']
                h['margin_of_safety'] = result['margin_of_safety']
                h['valuation_rec'] = result['recommendation']
                if change_analysis:
                    h['mos_change'] = change_analysis['mos_change']
                
            except Exception as e:
                print(f"  ⚠️ 分析失败: {e}")
                import traceback
                traceback.print_exc()
    
    # 生成市场报告
    pnl = total_value - total_cost
    pnl_pct = (pnl / total_cost * 100) if total_cost > 0 else 0
    emoji = "📈" if pnl >= 0 else "📉"
    
    message = f"""{emoji} {market} 持仓跟踪报告
━━━━━━━━━━━━━━━━━━━━

💰 整体概况:
• 总成本: ¥{total_cost:,.2f}
• 当前市值: ¥{total_value:,.2f}
• 总盈亏: ¥{pnl:,.2f} ({pnl_pct:+.2f}%)

📊 持仓明细:
"""
    for i, h in enumerate(holdings, 1):
        pnl_emoji = "📈" if h.get('pnl', 0) >= 0 else "📉"
        message += f"\n{i}. {h['stock_name']} ({h['stock_code']})\n"
        message += f"   • 持仓: {h['total_shares']}股 | 成本: ¥{h['total_cost']/h['total_shares']:.2f}\n"
        if h.get('current_price'):
            message += f"   • 现价: ¥{h['current_price']:.2f}\n"
            message += f"   {pnl_emoji} 盈亏: {h.get('pnl', 0)/h['total_cost']*100:+.2f}%\n"
        if h.get('valuation_rec'):
            mos = h.get('margin_of_safety', 0)
            mos_emoji = "🟢" if mos > 0.3 else "🟡" if mos > 0 else "🔴"
            message += f"   {mos_emoji} 估值: {h['valuation_rec']}"
            if mos > 0:
                message += f" (安全边际 {mos:.1%})"
            if 'mos_change' in h:
                change = h['mos_change']
                change_emoji = "📈" if change > 0 else "📉"
                message += f" {change_emoji} {change:+.1%}"
            message += "\n"
    
    # 添加价值投资报告
    if valuation_reports:
        message += "\n\n📚 价值投资分析\n" + "=" * 40 + "\n\n"
        message += "\n\n".join(valuation_reports)
    
    message += f"\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    return True, message


# ==================== 主函数 ====================

async def main():
    """主函数"""
    now = datetime.now()
    print(f"🚀 持仓跟踪任务 - {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查配置
    if not all([FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_USER_OPEN_ID]):
        print("❌ 缺少配置")
        return 1
    
    if not DB_PATH.exists():
        print(f"❌ 数据库不存在")
        return 1
    
    # 解析命令行参数
    args = sys.argv[1:]
    force_all = "--all" in args
    force_market = None
    
    for i, arg in enumerate(args):
        if arg == "--market" and i + 1 < len(args):
            force_market = args[i + 1]
            break
    
    # 初始化
    analyzer = ValueInvestingAnalyzer(KIMI_API_KEY)
    history = ValuationHistory(VALUATION_DB)
    
    # 确定要追踪的市场
    if force_all:
        # 强制追踪所有市场
        markets_to_track = ["A股", "港股", "美股"]
        print(f"📢 强制追踪所有市场: {', '.join(markets_to_track)}")
    elif force_market:
        # 强制追踪指定市场
        if force_market not in ["A股", "港股", "美股", "基金"]:
            print(f"❌ 未知市场: {force_market}")
            print("支持的市场: A股, 港股, 美股, 基金")
            return 1
        markets_to_track = [force_market]
        print(f"📢 强制追踪市场: {force_market}")
    else:
        # 自动判断当前交易中的市场
        markets_to_track = MarketTradingHours.get_current_trading_markets(now)
        if not markets_to_track:
            # 显示市场状态
            status = MarketTradingHours.get_market_status(now)
            print("⏸️ 当前没有市场处于交易时间")
            print("市场状态:")
            for market, status_text in status.items():
                print(f"  {market}: {status_text}")
            return 0
        print(f"📢 当前交易市场: {', '.join(markets_to_track)}")
    
    # 追踪每个市场
    all_messages = []
    has_any_holdings = False
    
    for market in markets_to_track:
        has_holdings, message = await track_market(market, analyzer, history)
        if has_holdings:
            has_any_holdings = True
            all_messages.append(message)
    
    if not has_any_holdings:
        print("\n📌 所有市场均无持仓")
        return 0
    
    # 合并发送消息
    full_message = "\n\n" + "="*60 + "\n".join(all_messages)
    
    # 检查是否需要发送通知
    should_notify = force_all or force_market or len(markets_to_track) > 0
    
    if should_notify:
        print(f"\n{'='*60}")
        print("📤 发送通知...")
        success = await send_feishu_message(full_message)
        print("✅ 发送成功" if success else "❌ 发送失败")
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
