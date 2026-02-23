"""
股票持仓管理技能
记录股票交易记录，管理持仓，支持查询持仓情况
"""
import sqlite3
import os
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from .base_skill import BaseSkill, SkillResult
from .stock_skill import StockSkill


class PortfolioSkill(BaseSkill):
    """股票持仓管理技能"""
    
    name = "manage_portfolio"
    description = """管理股票持仓，记录买卖交易，查询持仓情况。
    支持功能：
    1. 记录交易：买入或卖出股票，自动识别股票代码
    2. 查询持仓：查看当前所有持仓股票的汇总信息
    """
    examples = [
        "买入茅台 100股 价格1500",
        "卖出腾讯 50股 价格400",
        "买入 AAPL 10股 价格180",
        "我的持仓",
        "查询持仓",
        "持仓情况",
        "记录买入宁德时代 200股 220元"
    ]
    parameters = {
        "action": {
            "type": "string",
            "description": "操作类型：record(记录交易) 或 query(查询持仓)",
            "enum": ["record", "query"],
            "required": True
        },
        "stock_name": {
            "type": "string",
            "description": "股票名称或代码，如茅台、腾讯、AAPL、600519",
            "required": False
        },
        "trade_action": {
            "type": "string",
            "description": "交易行为：buy(买入) 或 sell(卖出)",
            "enum": ["buy", "sell"],
            "required": False
        },
        "price": {
            "type": "number",
            "description": "交易价格",
            "required": False
        },
        "shares": {
            "type": "integer",
            "description": "交易股数",
            "required": False
        },
        "user_id": {
            "type": "string",
            "description": "用户ID",
            "required": False
        }
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        # 数据库文件路径
        self.db_path = config.get("db_path") if config else os.environ.get(
            "PORTFOLIO_DB_PATH", 
            "/opt/feishu-assistant/data/portfolio.db"
        )
        # 确保目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        # 初始化数据库
        self._init_db()
        # 股票代码解析器
        self.stock_skill = StockSkill()
    
    def _init_db(self):
        """初始化数据库表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        stock_name TEXT NOT NULL,
                        stock_code TEXT NOT NULL,
                        market TEXT NOT NULL,
                        action TEXT NOT NULL CHECK(action IN ('buy', 'sell')),
                        price REAL NOT NULL,
                        shares INTEGER NOT NULL,
                        total_amount REAL NOT NULL,
                        trade_date TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 创建索引
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_user_stock 
                    ON transactions(user_id, stock_code)
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_trade_date 
                    ON transactions(trade_date)
                ''')
                
                conn.commit()
        except Exception as e:
            print(f"初始化数据库失败: {e}")
            raise
    
    async def execute(self, action: str, user_id: str = "default", 
                      stock_name: str = None, trade_action: str = None,
                      price: float = None, shares: int = None, **kwargs) -> SkillResult:
        """执行持仓管理操作"""
        try:
            if action == "record":
                return await self._record_transaction(
                    user_id, stock_name, trade_action, price, shares
                )
            elif action == "query":
                return await self._query_portfolio(user_id)
            else:
                return SkillResult(
                    success=False,
                    message=f"❓ 未知操作: {action}\n\n支持的操作:\n• record - 记录交易\n• query - 查询持仓"
                )
        except Exception as e:
            print(f"PortfolioSkill error: {e}")
            import traceback
            traceback.print_exc()
            return SkillResult(
                success=False,
                message=f"❌ 操作失败: {str(e)}"
            )
    
    async def _record_transaction(self, user_id: str, stock_name: str, 
                                   trade_action: str, price: float, 
                                   shares: int) -> SkillResult:
        """记录交易"""
        # 参数验证
        if not stock_name:
            return SkillResult(
                success=False,
                message="❓ 请提供股票名称或代码\n\n例如: 买入茅台 100股 价格1500"
            )
        
        if trade_action not in ["buy", "sell"]:
            return SkillResult(
                success=False,
                message="❓ 请指定交易行为: buy(买入) 或 sell(卖出)"
            )
        
        if price is None or price <= 0:
            return SkillResult(
                success=False,
                message="❓ 请提供有效的交易价格"
            )
        
        if shares is None or shares <= 0:
            return SkillResult(
                success=False,
                message="❓ 请提供有效的交易股数"
            )
        
        # 解析股票代码
        tencent_code = self._resolve_stock_code(stock_name)
        if not tencent_code:
            return SkillResult(
                success=False,
                message=f"❓ 未能识别股票「{stock_name}」\n\n请尝试:\n• 输入股票全称\n• 输入股票代码"
            )
        
        # 提取市场信息
        market = self._get_market_from_code(tencent_code)
        stock_code = tencent_code[2:]  # 去掉前缀
        
        # 获取股票真实名称
        real_name = self._get_stock_real_name(tencent_code) or stock_name
        
        # 计算总金额
        total_amount = price * shares
        
        # 保存到数据库
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO transactions 
                    (user_id, stock_name, stock_code, market, action, price, shares, total_amount, trade_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    real_name,
                    stock_code,
                    market,
                    trade_action,
                    price,
                    shares,
                    total_amount,
                    datetime.now().strftime('%Y-%m-%d')
                ))
                conn.commit()
                
                trade_type = "买入" if trade_action == "buy" else "卖出"
                return SkillResult(
                    success=True,
                    message=f"✅ 交易记录成功！\n\n"
                            f"📊 {real_name} ({stock_code})\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"💼 交易类型: {trade_type}\n"
                            f"💰 成交价: ¥{price:.2f}\n"
                            f"📈 股数: {shares}股\n"
                            f"💵 总金额: ¥{total_amount:,.2f}\n"
                            f"🏷️ 市场: {market}\n"
                            f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"❌ 保存交易记录失败: {str(e)}"
            )
    
    async def _query_portfolio(self, user_id: str) -> SkillResult:
        """查询持仓情况"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # 查询该用户的所有交易记录，按股票分组汇总
                cursor.execute('''
                    SELECT 
                        stock_name,
                        stock_code,
                        market,
                        SUM(CASE WHEN action = 'buy' THEN shares ELSE -shares END) as total_shares,
                        SUM(CASE WHEN action = 'buy' THEN total_amount ELSE -total_amount END) as total_cost,
                        COUNT(*) as trade_count
                    FROM transactions
                    WHERE user_id = ?
                    GROUP BY stock_code
                    HAVING total_shares > 0
                    ORDER BY total_cost DESC
                ''', (user_id,))
                
                rows = cursor.fetchall()
                
                if not rows:
                    return SkillResult(
                        success=True,
                        message="📋 当前没有持仓\n\n您可以使用以下格式记录交易:\n"
                                "• 买入茅台 100股 价格1500\n"
                                "• 卖出腾讯 50股 价格400\n"
                                "• 买入 AAPL 10股 180元"
                    )
                
                # 构建持仓报告
                total_value = 0
                total_cost = 0
                holdings = []
                
                for row in rows:
                    holding = dict(row)
                    avg_cost = holding['total_cost'] / holding['total_shares'] if holding['total_shares'] > 0 else 0
                    holding['avg_cost'] = avg_cost
                    holdings.append(holding)
                    total_cost += holding['total_cost']
                
                # 获取当前股价（可选）
                current_prices = await self._get_current_prices(holdings)
                
                # 格式化输出
                message = self._format_portfolio_message(holdings, current_prices, total_cost)
                
                return SkillResult(success=True, message=message)
                
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"❌ 查询持仓失败: {str(e)}"
            )
    
    async def _get_current_prices(self, holdings: List[Dict]) -> Dict[str, float]:
        """获取当前股价"""
        prices = {}
        for holding in holdings:
            try:
                market_prefix = {
                    "A股": "sh" if holding['stock_code'].startswith('6') else "sz",
                    "港股": "hk",
                    "美股": "us"
                }.get(holding['market'], "sh")
                
                tencent_code = f"{market_prefix}{holding['stock_code']}"
                # 复用 StockSkill 获取价格
                # 这里简化处理，不实际调用
                prices[holding['stock_code']] = None
            except:
                prices[holding['stock_code']] = None
        return prices
    
    def _format_portfolio_message(self, holdings: List[Dict], 
                                   current_prices: Dict[str, float],
                                   total_cost: float) -> str:
        """格式化持仓报告"""
        message = "📊 我的持仓\n━━━━━━━━━━━━━━━━━━━━\n\n"
        
        total_stocks = len(holdings)
        total_shares_count = sum(h['total_shares'] for h in holdings)
        
        for i, holding in enumerate(holdings, 1):
            stock_code = holding['stock_code']
            stock_name = holding['stock_name']
            market = holding['market']
            shares = holding['total_shares']
            cost = holding['total_cost']
            avg_cost = holding['avg_cost']
            trade_count = holding['trade_count']
            
            # 如果有当前价格，计算盈亏
            current_price = current_prices.get(stock_code)
            if current_price:
                current_value = current_price * shares
                pnl = current_value - cost
                pnl_pct = (pnl / cost * 100) if cost > 0 else 0
                pnl_emoji = "📈" if pnl >= 0 else "📉"
            else:
                current_value = cost
                pnl = 0
                pnl_pct = 0
                pnl_emoji = "➖"
            
            weight = (cost / total_cost * 100) if total_cost > 0 else 0
            
            message += f"{i}. {stock_name} ({stock_code})\n"
            message += f"   📍 {market} | 持仓: {shares}股\n"
            message += f"   💰 成本: ¥{cost:,.2f} (均价¥{avg_cost:.2f})\n"
            if current_price:
                message += f"   📊 现价: ¥{current_price:.2f}\n"
                message += f"   {pnl_emoji} 盈亏: ¥{pnl:,.2f} ({pnl_pct:+.2f}%)\n"
            message += f"   📎 仓位: {weight:.1f}%\n"
            if i < len(holdings):
                message += "\n"
        
        message += f"\n━━━━━━━━━━━━━━━━━━━━\n"
        message += f"📈 持仓统计:\n"
        message += f"• 持股数量: {total_stocks}只\n"
        message += f"• 总股数: {total_shares_count}股\n"
        message += f"• 总成本: ¥{total_cost:,.2f}\n"
        
        return message
    
    def _resolve_stock_code(self, stock_name: str) -> Optional[str]:
        """解析股票代码"""
        # 复用 StockSkill 的解析逻辑
        return self.stock_skill._resolve_symbol(stock_name, "AUTO")
    
    def _get_market_from_code(self, tencent_code: str) -> str:
        """从腾讯代码获取市场"""
        if tencent_code.startswith('sh') or tencent_code.startswith('sz'):
            return "A股"
        elif tencent_code.startswith('hk'):
            return "港股"
        elif tencent_code.startswith('us'):
            return "美股"
        return "未知"
    
    def _get_stock_real_name(self, tencent_code: str) -> Optional[str]:
        """从映射表获取股票真实名称"""
        for name, code in self.stock_skill.STOCK_NAME_MAP.items():
            if code == tencent_code:
                return name
        return None
    
    def parse_trade_message(self, message: str) -> Optional[Dict[str, Any]]:
        """
        从自然语言消息中解析交易信息
        支持格式：
        - 买入茅台 100股 价格1500
        - 卖出腾讯 50股 400元
        - 买入AAPL 10股 180
        - 记录买入 宁德时代 200股 220元
        """
        message = message.strip()
        
        # 判断是买入还是卖出
        action = None
        action_keyword = None
        for kw in ['买入', 'buy', '购买', '买进']:
            if kw in message:
                action = 'buy'
                action_keyword = kw
                break
        if not action:
            for kw in ['卖出', 'sell', '抛售', '卖掉']:
                if kw in message:
                    action = 'sell'
                    action_keyword = kw
                    break
        
        if not action:
            return None
        
        # 提取数字（股数和价格）
        numbers = re.findall(r'(\d+(?:\.\d+)?)', message)
        if len(numbers) < 2:
            return None
        
        try:
            shares = int(float(numbers[0]))
            price = float(numbers[1])
        except (ValueError, IndexError):
            return None
        
        # 提取股票名称 - 在操作关键词之后、第一个数字之前
        stock_name = None
        
        # 方法1: 找到操作关键词，提取后面的内容直到第一个数字
        action_pos = message.find(action_keyword)
        if action_pos >= 0:
            after_action = message[action_pos + len(action_keyword):].strip()
            # 移除开头的"一下"、"记录"等词
            after_action = re.sub(r'^(一下|记录|个|点)\s*', '', after_action)
            # 提取直到第一个数字之前
            match = re.match(r'^([\u4e00-\u9fa5a-zA-Z]+)\s*\d', after_action)
            if match:
                stock_name = match.group(1).strip()
        
        # 方法2: 如果没找到，尝试其他模式
        if not stock_name:
            # 匹配 买入 xxx 数字 的模式
            match = re.search(r'(?:买入|卖出|buy|sell)\s+([\u4e00-\u9fa5a-zA-Z]{1,10})', message, re.IGNORECASE)
            if match:
                stock_name = match.group(1).strip()
        
        # 方法3: 查找中文字符串或英文代码
        if not stock_name:
            # 排除操作关键词中的字
            cleaned = message
            for kw in ['买入', '卖出', 'buy', 'sell', '购买', '记录', '价格', '元']:
                cleaned = cleaned.replace(kw, ' ')
            
            # 找中文股票名（2-5个汉字）
            match = re.search(r'([\u4e00-\u9fa5]{2,5})', cleaned)
            if match:
                stock_name = match.group(1).strip()
            else:
                # 找英文代码（1-5个大写字母）
                match = re.search(r'([A-Z]{1,5})', cleaned.upper())
                if match:
                    stock_name = match.group(1).strip()
        
        if action and stock_name and shares > 0 and price > 0:
            return {
                'action': action,
                'stock_name': stock_name,
                'shares': shares,
                'price': price
            }
        
        return None
