#!/usr/bin/env python3
"""
持仓跟踪定时任务 - 服务器本地运行（含价值投资分析）
添加到 crontab: */30 9-11,13-15 * * 1-5 /usr/bin/python3.11 /opt/feishu-assistant/portfolio_tracker_cron.py
"""
import os
import sys
import asyncio
import json
import httpx
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

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


# ==================== 价值投资分析模块 ====================

class ValueInvestingAnalyzer:
    """简化版价值投资分析器"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.api_base = "https://api.moonshot.cn/v1"
    
    async def analyze(self, stock_code: str, stock_name: str, 
                      current_price: float, market: str) -> Dict[str, Any]:
        """执行价值投资分析"""
        # 获取财务数据
        financial_data = await self._get_financial_data(stock_code, stock_name, current_price, market)
        
        # 计算估值
        intrinsic_value = self._calculate_intrinsic_value(
            financial_data, current_price
        )
        
        margin_of_safety = (intrinsic_value - current_price) / intrinsic_value if intrinsic_value > 0 else 0
        
        # 投资建议
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
            # 转换代码
            if market == "A股":
                prefix = "sh" if stock_code.startswith('6') else "sz"
                tencent_code = f"{prefix}{stock_code}"
            elif market == "港股":
                tencent_code = f"hk{stock_code}"
            elif market == "美股":
                tencent_code = f"us{stock_code}"
            else:
                tencent_code = stock_code
            
            # 获取数据
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
                        # 估算EPS
                        if data['pe'] > 0 and current_price > 0:
                            data['eps'] = current_price / data['pe']
            
            # 使用AI估算
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
        """计算内在价值（简化DCF+PE）"""
        eps = financial_data.get('eps', 1)
        growth = financial_data.get('profit_growth', 10) / 100
        
        # PE估值
        if growth > 0.2:
            fair_pe = 25
        elif growth > 0.15:
            fair_pe = 20
        elif growth > 0.10:
            fair_pe = 15
        else:
            fair_pe = 12
        
        pe_value = eps * fair_pe
        
        # 与当前价格加权
        intrinsic = pe_value * 0.7 + current_price * 0.3
        
        return max(intrinsic, current_price * 0.5)
    
    def analyze_change(self, current: Dict, previous: Dict) -> Dict[str, Any]:
        """分析估值变化"""
        prev_price = previous.get('current_price', current['current_price'])
        prev_intrinsic = previous.get('intrinsic_value', current['intrinsic_value'])
        prev_mos = previous.get('margin_of_safety', current['margin_of_safety'])
        prev_date = previous.get('analysis_date', current['analysis_date'])
        
        # 计算变化
        price_change = (current['current_price'] - prev_price) / prev_price if prev_price > 0 else 0
        intrinsic_change = (current['intrinsic_value'] - prev_intrinsic) / prev_intrinsic if prev_intrinsic > 0 else 0
        mos_change = current['margin_of_safety'] - prev_mos
        
        # 计算天数差
        try:
            prev_dt = datetime.strptime(prev_date, '%Y-%m-%d')
            curr_dt = datetime.strptime(current['analysis_date'], '%Y-%m-%d')
            days = (curr_dt - prev_dt).days
        except:
            days = 0
        
        # 判断驱动因素
        price_driven = abs(price_change) > abs(intrinsic_change) * 2
        fundamental_driven = abs(intrinsic_change) > 0.05
        
        # 生成结论
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
        
        # 投资建议
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


# ==================== 原有功能模块 ====================

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


async def get_holdings(user_id: str) -> List[Dict]:
    """获取用户持仓"""
    import sqlite3
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
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


def check_trading_hours() -> bool:
    """检查交易时间"""
    now = datetime.now()
    weekday = now.weekday()
    hour, minute = now.hour, now.minute
    time_val = hour * 60 + minute
    
    if weekday >= 5:
        return False
    if 570 <= time_val <= 690:  # 9:30-11:30
        return True
    if 780 <= time_val <= 900:  # 13:00-15:00
        return True
    return False


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


async def main():
    """主函数"""
    print(f"🚀 持仓跟踪任务 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查配置
    if not all([FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_USER_OPEN_ID]):
        print("❌ 缺少配置")
        return 1
    
    if not DB_PATH.exists():
        print(f"❌ 数据库不存在")
        return 1
    
    # 检查交易时间（强制模式跳过）
    force = len(sys.argv) > 1 and sys.argv[1] == "--force"
    if not force and not check_trading_hours():
        print("⏸️ 非交易时间")
        return 0
    
    # 初始化
    analyzer = ValueInvestingAnalyzer(KIMI_API_KEY)
    history = ValuationHistory(VALUATION_DB)
    
    # 获取持仓
    holdings = await get_holdings(FEISHU_USER_OPEN_ID)
    if not holdings:
        print("📌 没有持仓")
        return 0
    
    print(f"📊 持仓数量: {len(holdings)}")
    
    # 分析每个持仓
    total_cost = 0
    total_value = 0
    valuation_reports = []
    
    for h in holdings:
        code = h['stock_code']
        market = h.get('market', 'A股')
        
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
    
    # 生成报告
    pnl = total_value - total_cost
    pnl_pct = (pnl / total_cost * 100) if total_cost > 0 else 0
    emoji = "📈" if pnl >= 0 else "📉"
    
    message = f"""{emoji} 持仓跟踪报告
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
            # 显示安全边际变化
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
    
    # 检查是否需要发送通知
    has_valuation_change = any('mos_change' in h and abs(h['mos_change']) > 0.1 for h in holdings)
    
    if force or abs(pnl_pct) > 3 or has_valuation_change:
        reason = []
        if force:
            reason.append("强制模式")
        if abs(pnl_pct) > 3:
            reason.append(f"盈亏变化 {pnl_pct:+.2f}%")
        if has_valuation_change:
            reason.append("估值显著变化")
        print(f"📤 发送通知 ({', '.join(reason)})...")
        success = await send_feishu_message(message)
        print("✅ 发送成功" if success else "❌ 发送失败")
    else:
        print("📌 无显著变化，跳过通知")
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
