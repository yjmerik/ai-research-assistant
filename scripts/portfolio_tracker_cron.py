#!/usr/bin/env python3
"""
持仓跟踪定时任务 - 服务器本地运行
添加到 crontab: */30 9-11,13-15 * * 1-5 /usr/bin/python3.11 /opt/feishu-assistant/portfolio_tracker_cron.py
"""
import os
import sys
import asyncio
import json
from datetime import datetime
from pathlib import Path

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

# 手动导入技能（避免路径问题）
import sqlite3
import httpx
import re
from typing import Dict, Any, Optional, List

# 数据库路径
DB_PATH = SCRIPT_DIR / "data" / "portfolio.db"
STATE_FILE = SCRIPT_DIR / "data" / "portfolio_tracker_state.json"

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
FEISHU_USER_OPEN_ID = os.environ.get("FEISHU_USER_OPEN_ID")
KIMI_API_KEY = os.environ.get("KIMI_API_KEY")


async def get_current_price(stock_code: str, market: str) -> Optional[float]:
    """获取股票当前价格"""
    try:
        market_prefix = {
            "A股": "sh" if stock_code.startswith('6') else "sz",
            "港股": "hk",
            "美股": "us"
        }.get(market, "sh")
        
        tencent_code = f"{market_prefix}{stock_code}"
        url = f"http://qt.gtimg.cn/q={tencent_code}"
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10)
            resp.encoding = 'gbk'
            data = resp.text
        
        if '="' not in data:
            return None
        
        parts = data.split('="')
        if len(parts) < 2:
            return None
        
        values_str = parts[1].rstrip('"').rstrip(';')
        values = values_str.split('~')
        
        if len(values) < 4:
            return None
        
        return float(values[3]) if values[3] else None
        
    except Exception as e:
        print(f"获取股价失败 {stock_code}: {e}")
        return None


async def get_holdings(user_id: str) -> List[Dict]:
    """获取用户持仓"""
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    stock_name,
                    stock_code,
                    market,
                    SUM(CASE WHEN action = 'buy' THEN shares ELSE -shares END) as total_shares,
                    SUM(CASE WHEN action = 'buy' THEN total_amount ELSE -total_amount END) as total_cost,
                    MAX(trade_date) as last_trade_date
                FROM transactions
                WHERE user_id = ?
                GROUP BY stock_code
                HAVING total_shares > 0
                ORDER BY total_cost DESC
            ''', (user_id,))
            
            rows = cursor.fetchall()
            holdings = []
            
            for row in rows:
                holding = dict(row)
                holding['avg_cost'] = holding['total_cost'] / holding['total_shares'] if holding['total_shares'] > 0 else 0
                holdings.append(holding)
            
            return holdings
    except Exception as e:
        print(f"获取持仓失败: {e}")
        return []


def load_last_state() -> Dict:
    """加载上次状态"""
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('holdings', {})
    except Exception as e:
        print(f"加载状态失败: {e}")
    return {}


def save_state(user_id: str, holdings: List[Dict]):
    """保存当前状态"""
    try:
        state = {
            'user_id': user_id,
            'timestamp': datetime.now().isoformat(),
            'holdings': {
                h['stock_code']: {
                    'current_price': h.get('current_price', 0),
                    'pnl_percent': h.get('pnl_percent', 0),
                    'current_value': h.get('current_value', 0)
                }
                for h in holdings
            }
        }
        
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存状态失败: {e}")


def check_trading_hours() -> bool:
    """检查是否在交易时间（中国大陆）"""
    now = datetime.now()
    weekday = now.weekday()
    hour = now.hour
    minute = now.minute
    
    print(f"⏰ 当前时间: {now.strftime('%Y-%m-%d %H:%M')} 星期{weekday+1}")
    
    # 周末不交易
    if weekday >= 5:
        print("📅 周末休市")
        return False
    
    time_val = hour * 60 + minute
    
    # A股上午: 9:30-11:30 (570-690)
    if 570 <= time_val <= 690:
        print("📈 A股上午交易时段")
        return True
    
    # A股下午: 13:00-15:00 (780-900)
    if 780 <= time_val <= 900:
        print("📈 A股下午交易时段")
        return True
    
    # 港股下午延长到 16:00 (960)
    if 780 <= time_val <= 960:
        print("📈 港股交易时段")
        return True
    
    print("⏸️ 非交易时间")
    return False


async def send_feishu_message(message: str) -> bool:
    """发送飞书消息"""
    try:
        # 1. 获取 access_token
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
        async with httpx.AsyncClient() as client:
            resp = await client.post(token_url, json={
                "app_id": FEISHU_APP_ID,
                "app_secret": FEISHU_APP_SECRET
            }, timeout=10)
            data = resp.json()
            token = data.get("tenant_access_token")
            
            if not token:
                print(f"❌ 获取 token 失败: {data}")
                return False
            
            # 2. 发送消息
            msg_url = "https://open.feishu.cn/open-apis/im/v1/messages"
            resp = await client.post(
                msg_url,
                headers={"Authorization": f"Bearer {token}"},
                params={"receive_id_type": "open_id"},
                json={
                    "receive_id": FEISHU_USER_OPEN_ID,
                    "msg_type": "text",
                    "content": json.dumps({"text": message})
                },
                timeout=10
            )
            
            if resp.status_code == 200:
                result = resp.json()
                if result.get("code") == 0:
                    print(f"✅ 消息发送成功")
                    return True
                else:
                    print(f"❌ API 错误: {result}")
                    return False
            else:
                print(f"❌ HTTP 错误: {resp.status_code} - {resp.text}")
                return False
                
    except Exception as e:
        print(f"❌ 发送异常: {e}")
        import traceback
        traceback.print_exc()
        return False


async def generate_ai_analysis(holdings: List[Dict]) -> str:
    """使用 AI 生成分析"""
    if not KIMI_API_KEY:
        return "⚠️ 未配置 AI 分析"
    
    total_cost = sum(h['total_cost'] for h in holdings)
    total_value = sum(h.get('current_value', h['total_cost']) for h in holdings)
    total_pnl = total_value - total_cost
    
    summary = []
    for h in holdings:
        summary.append({
            "name": h['stock_name'],
            "code": h['stock_code'],
            "shares": h['total_shares'],
            "avg_cost": h['avg_cost'],
            "current_price": h.get('current_price', h['avg_cost']),
            "pnl_percent": h.get('pnl_percent', 0)
        })
    
    prompt = f"""你是一位专业投资顾问，请对以下持仓给出简要交易建议（100字以内）。

持仓概况:
- 总成本: ¥{total_cost:,.2f}
- 当前市值: ¥{total_value:,.2f}
- 总盈亏: ¥{total_pnl:,.2f} ({total_pnl/total_cost*100 if total_cost > 0 else 0:.2f}%)

持仓明细:
{json.dumps(summary, ensure_ascii=False, indent=2)}

请给出:
1. 整体评价
2. 需要关注的股票
3. 操作建议"""

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.moonshot.cn/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {KIMI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "moonshot-v1-8k",
                    "messages": [
                        {"role": "system", "content": "你是专业投资顾问，提供简洁客观的建议。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 500
                },
                timeout=30
            )
            
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"AI 分析失败: {e}")
    
    return "⚠️ AI 分析暂时不可用"


def format_message(holdings: List[Dict], ai_analysis: str) -> str:
    """格式化消息"""
    total_cost = sum(h['total_cost'] for h in holdings)
    total_value = sum(h.get('current_value', h['total_cost']) for h in holdings)
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
    
    emoji = "📈" if total_pnl >= 0 else "📉"
    
    message = f"""{emoji} 持仓跟踪报告
━━━━━━━━━━━━━━━━━━━━

💰 整体概况:
• 总成本: ¥{total_cost:,.2f}
• 当前市值: ¥{total_value:,.2f}
• 总盈亏: ¥{total_pnl:,.2f} ({total_pnl_pct:+.2f}%)
"""
    
    # 检查是否有重要提醒
    alerts = []
    for h in holdings:
        pnl = h.get('pnl_percent', 0)
        if pnl >= 10:
            alerts.append(f"🟢 {h['stock_name']}: 盈利 {pnl:.1f}%，建议止盈")
        elif pnl <= -7:
            alerts.append(f"🔴 {h['stock_name']}: 亏损 {pnl:.1f}%，建议止损")
    
    if alerts:
        message += "\n🚨 交易提醒:\n" + "\n".join(alerts) + "\n"
    
    # 个股详情
    message += "\n📊 持仓明细:\n"
    for i, h in enumerate(holdings, 1):
        pnl_emoji = "📈" if h.get('pnl_percent', 0) >= 0 else "📉"
        message += f"\n{i}. {h['stock_name']} ({h['stock_code']})\n"
        message += f"   • 持仓: {h['total_shares']}股 | 成本: ¥{h['avg_cost']:.2f}\n"
        if h.get('current_price'):
            message += f"   • 现价: ¥{h['current_price']:.2f}\n"
        if h.get('pnl_percent') is not None:
            message += f"   {pnl_emoji} 盈亏: {h['pnl_percent']:+.2f}%\n"
    
    # AI 分析
    if ai_analysis:
        message += f"\n🤖 AI 建议:\n{ai_analysis}\n"
    
    message += f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    return message


async def main():
    """主函数"""
    print("=" * 60)
    print(f"🚀 持仓跟踪任务 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 检查交易时间
    if not check_trading_hours():
        print("📌 跳过执行（非交易时间）")
        return 0
    
    # 检查必要配置
    if not all([FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_USER_OPEN_ID]):
        print("❌ 缺少飞书配置")
        return 1
    
    # 检查数据库是否存在
    if not DB_PATH.exists():
        print(f"❌ 数据库不存在: {DB_PATH}")
        return 1
    
    # 获取持仓
    user_id = FEISHU_USER_OPEN_ID
    holdings = await get_holdings(user_id)
    
    if not holdings:
        print("📌 没有持仓")
        return 0
    
    print(f"📊 持仓数量: {len(holdings)}")
    
    # 获取实时价格
    for h in holdings:
        current_price = await get_current_price(h['stock_code'], h['market'])
        h['current_price'] = current_price
        
        if current_price and h['avg_cost'] > 0:
            h['pnl_amount'] = (current_price - h['avg_cost']) * h['total_shares']
            h['pnl_percent'] = (current_price - h['avg_cost']) / h['avg_cost'] * 100
            h['current_value'] = current_price * h['total_shares']
        else:
            h['pnl_amount'] = 0
            h['pnl_percent'] = 0
            h['current_value'] = h['total_cost']
    
    # 检查变化
    last_state = load_last_state()
    has_changes = False
    
    for h in holdings:
        code = h['stock_code']
        current_pnl = h.get('pnl_percent', 0)
        
        if code in last_state:
            last_pnl = last_state[code].get('pnl_percent', 0)
            if abs(current_pnl - last_pnl) >= 3:
                has_changes = True
                break
        else:
            has_changes = True
        
        # 检查是否触及止盈止损
        if current_pnl >= 10 or current_pnl <= -7:
            has_changes = True
    
    # 生成 AI 分析
    ai_analysis = await generate_ai_analysis(holdings)
    
    # 保存状态
    save_state(user_id, holdings)
    
    # 检查是否需要通知
    force_notify = len(sys.argv) > 1 and sys.argv[1] == "--force"
    
    if not has_changes and not force_notify:
        print("📌 无显著变化，跳过通知")
        return 0
    
    # 发送通知
    message = format_message(holdings, ai_analysis)
    success = await send_feishu_message(message)
    
    if success:
        print("✅ 通知发送成功")
    else:
        print("❌ 通知发送失败")
    
    print("=" * 60)
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
