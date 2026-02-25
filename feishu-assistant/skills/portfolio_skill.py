"""
股票持仓管理技能
记录股票交易记录，管理持仓，支持查询持仓情况
"""
import sqlite3
import os
import re
import json
import httpx
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
        config = config or {}
        # 数据库文件路径
        self.db_path = config.get("db_path") or os.environ.get(
            "PORTFOLIO_DB_PATH", 
            "/opt/feishu-assistant/data/portfolio.db"
        )
        # LLM API 配置
        self.kimi_api_key = config.get("kimi_api_key") or os.environ.get("KIMI_API_KEY")
        self.kimi_api_base = "https://api.moonshot.cn/v1"
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
                        currency TEXT DEFAULT 'CNY',
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
                      price: float = None, shares: int = None,
                      currency: str = "CNY", **kwargs) -> SkillResult:
        """执行持仓管理操作"""
        try:
            if action == "record":
                return await self._record_transaction(
                    user_id, stock_name, trade_action, price, shares, currency
                )
            elif action == "query":
                return await self._query_portfolio(user_id)
            elif action == "reset":
                return await self._reset_portfolio(user_id, kwargs.get('confirm', False))
            else:
                return SkillResult(
                    success=False,
                    message=f"❓ 未知操作: {action}\n\n支持的操作:\n• record - 记录交易\n• query - 查询持仓\n• reset - 重置/清零持仓"
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
                                   shares: int, currency: str = "CNY") -> SkillResult:
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
        
        # 币种符号
        currency_symbol = {'CNY': '¥', 'USD': '$', 'HKD': 'HK$'}.get(currency, '¥')
        
        # 保存到数据库
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO transactions 
                    (user_id, stock_name, stock_code, market, action, price, currency, shares, total_amount, trade_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    real_name,
                    stock_code,
                    market,
                    trade_action,
                    price,
                    currency,
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
                            f"💰 成交价: {currency_symbol}{price:.2f} ({currency})\n"
                            f"📈 股数: {shares}股\n"
                            f"💵 总金额: {currency_symbol}{total_amount:,.2f}\n"
                            f"🏷️ 市场: {market}\n"
                            f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"❌ 保存交易记录失败: {str(e)}"
            )
    
    async def _reset_portfolio(self, user_id: str, confirm: bool = False) -> SkillResult:
        """
        重置/清零持仓
        需要二次确认
        """
        if not confirm:
            # 先查询当前持仓
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT 
                            stock_name,
                            stock_code,
                            market,
                            SUM(CASE WHEN action = 'buy' THEN shares ELSE -shares END) as total_shares,
                            SUM(CASE WHEN action = 'buy' THEN total_amount ELSE -total_amount END) as total_cost
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
                            message="📋 当前没有持仓需要重置\n\n您的持仓已经为空。"
                        )
                    
                    # 显示持仓概览
                    holdings_info = []
                    total_value = 0
                    for row in rows:
                        holdings_info.append(f"• {row['stock_name']} ({row['stock_code']}): {row['total_shares']}股")
                        total_value += row['total_cost']
                    
                    return SkillResult(
                        success=False,
                        message=f"⚠️ 重置持仓确认\n\n"
                                f"您当前有以下 {len(rows)} 只持仓:\n"
                                + "\n".join(holdings_info) +
                                f"\n\n💰 总成本: ¥{total_value:,.2f}\n\n"
                                f"⚠️ 确定要清空所有持仓吗？\n\n"
                                f"请输入「/reset 确认」或「/reset confirm」来执行重置操作。\n"
                                f"此操作不可恢复！"
                    )
            except Exception as e:
                return SkillResult(
                    success=False,
                    message=f"❌ 查询持仓失败: {str(e)}"
                )
        
        # 执行重置
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 获取重置前的统计
                cursor.execute('''
                    SELECT 
                        COUNT(DISTINCT stock_code) as stock_count,
                        SUM(CASE WHEN action = 'buy' THEN shares ELSE -shares END) as total_shares,
                        SUM(CASE WHEN action = 'buy' THEN total_amount ELSE -total_amount END) as total_cost
                    FROM transactions
                    WHERE user_id = ?
                ''', (user_id,))
                
                row = cursor.fetchone()
                stock_count = row[0] or 0
                total_shares = row[1] or 0
                total_cost = row[2] or 0
                
                # 删除所有交易记录
                cursor.execute('DELETE FROM transactions WHERE user_id = ?', (user_id,))
                deleted_count = cursor.rowcount
                conn.commit()
                
                return SkillResult(
                    success=True,
                    message=f"✅ 持仓已重置/清零\n\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"📊 重置前持仓:\n"
                            f"• 股票数量: {stock_count}只\n"
                            f"• 总股数: {total_shares}股\n"
                            f"• 总成本: ¥{total_cost:,.2f}\n"
                            f"• 删除记录: {deleted_count}条\n\n"
                            f"🗑️ 所有持仓记录已清空\n"
                            f"⏰ 重置时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                            f"💡 提示: 您可以开始记录新的交易了"
                )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"❌ 重置持仓失败: {str(e)}"
            )
    
    async def _query_portfolio(self, user_id: str) -> SkillResult:
        """查询持仓情况（支持多币种显示）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # 查询该用户的所有交易记录，按股票和币种分组汇总
                cursor.execute('''
                    SELECT 
                        stock_name,
                        stock_code,
                        market,
                        COALESCE(MAX(currency), 'CNY') as currency,
                        SUM(CASE WHEN action = 'buy' THEN shares ELSE -shares END) as total_shares,
                        SUM(CASE WHEN action = 'buy' THEN total_amount ELSE -total_amount END) as total_cost,
                        COUNT(*) as trade_count
                    FROM transactions
                    WHERE user_id = ?
                    GROUP BY stock_code, currency
                    HAVING total_shares > 0
                    ORDER BY currency, total_cost DESC
                ''', (user_id,))
                
                rows = cursor.fetchall()
                
                if not rows:
                    return SkillResult(
                        success=True,
                        message="📋 当前没有持仓\n\n您可以使用以下格式记录交易:\n"
                                "• 买入茅台 100股 价格1500\n"
                                "• 卖出腾讯 50股 价格400港币\n"
                                "• 买入 AAPL 10股 180美元"
                    )
                
                # 按币种分组
                holdings_by_currency = {}
                for row in rows:
                    holding = dict(row)
                    currency = holding.get('currency', 'CNY')
                    avg_cost = holding['total_cost'] / holding['total_shares'] if holding['total_shares'] > 0 else 0
                    holding['avg_cost'] = avg_cost
                    
                    if currency not in holdings_by_currency:
                        holdings_by_currency[currency] = []
                    holdings_by_currency[currency].append(holding)
                
                # 获取当前股价（可选）- 扁平化所有持仓
                all_holdings = []
                for currency, holdings_list in holdings_by_currency.items():
                    all_holdings.extend(holdings_list)
                current_prices = await self._get_current_prices(all_holdings)
                
                # 格式化输出
                message = self._format_portfolio_by_currency(holdings_by_currency, current_prices)
                
                return SkillResult(success=True, message=message)
                
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"❌ 查询持仓失败: {str(e)}"
            )
    
    async def _get_current_prices(self, holdings: List[Dict]) -> Dict[str, float]:
        """获取当前价格（支持股票和基金）"""
        prices = {}
        for holding in holdings:
            try:
                code = holding['stock_code']
                market = holding.get('market', 'A股')
                
                # 判断市场前缀
                if market == "港股":
                    prefix = "hk"
                elif market == "美股":
                    prefix = "us"
                elif market == "基金":
                    # 基金：5位代码或特定6位代码
                    if len(code) == 5:
                        # 5位ETF代码
                        if code.startswith(('51', '56', '58', '60', '50')):
                            prefix = "sh"
                        else:
                            prefix = "sz"
                    else:
                        # 6位基金代码，根据开头判断
                        if code.startswith(('15', '16')):
                            prefix = "sz"
                        else:
                            prefix = "sh"
                else:
                    # A股
                    prefix = "sh" if code.startswith('6') else "sz"
                
                tencent_code = f"{prefix}{code}"
                
                # 调用腾讯财经获取价格
                import httpx
                url = f"http://qt.gtimg.cn/q={tencent_code}"
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, timeout=10)
                    resp.encoding = 'gbk'
                    data = resp.text
                
                if '="' in data:
                    parts = data.split('="')
                    if len(parts) >= 2:
                        values_str = parts[1].rstrip('"').rstrip(';')
                        values = values_str.split('~')
                        if len(values) >= 4 and values[3]:
                            prices[code] = float(values[3])
                            continue
                
                prices[code] = None
            except Exception as e:
                print(f"获取价格失败 {holding.get('stock_code')}: {e}")
                prices[holding['stock_code']] = None
        
        return prices
    
    def _format_portfolio_by_currency(self, 
                                       holdings_by_currency: Dict[str, List[Dict]],
                                       current_prices: Dict[str, float]) -> str:
        """格式化持仓报告（按币种分组）"""
        message = "📊 我的持仓\n━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # 币种符号映射
        currency_symbols = {
            'CNY': '¥',
            'USD': '$',
            'HKD': 'HK$'
        }
        
        total_all_stocks = 0
        currency_totals = {}
        
        # 按币种分组显示
        currency_order = ['CNY', 'HKD', 'USD']  # 显示顺序
        
        for currency in currency_order:
            if currency not in holdings_by_currency:
                continue
                
            holdings = holdings_by_currency[currency]
            symbol = currency_symbols.get(currency, currency)
            currency_name = {'CNY': '人民币', 'USD': '美元', 'HKD': '港币'}.get(currency, currency)
            
            total_cost_currency = sum(h['total_cost'] for h in holdings)
            currency_totals[currency] = total_cost_currency
            total_all_stocks += len(holdings)
            
            message += f"【{currency_name}账户】\n"
            
            for i, holding in enumerate(holdings, 1):
                stock_code = holding['stock_code']
                stock_name = holding['stock_name']
                market = holding['market']
                shares = holding['total_shares']
                cost = holding['total_cost']
                avg_cost = holding['avg_cost']
                
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
                
                weight = (cost / total_cost_currency * 100) if total_cost_currency > 0 else 0
                
                message += f"{i}. {stock_name} ({stock_code})\n"
                message += f"   📍 {market} | 持仓: {shares}股\n"
                message += f"   💰 成本: {symbol}{cost:,.2f} (均价{symbol}{avg_cost:.2f})\n"
                if current_price:
                    message += f"   📊 现价: {symbol}{current_price:.2f}\n"
                    message += f"   {pnl_emoji} 盈亏: {symbol}{pnl:,.2f} ({pnl_pct:+.2f}%)\n"
                message += f"   📎 仓位: {weight:.1f}%\n"
                if i < len(holdings):
                    message += "\n"
            
            message += f"\n💵 {currency_name}小计: {symbol}{total_cost_currency:,.2f} | {len(holdings)}只持仓\n"
            message += "\n"
        
        message += f"━━━━━━━━━━━━━━━━━━━━\n"
        message += f"📈 总持仓统计:\n"
        message += f"• 总持股: {total_all_stocks}只\n"
        for currency, total in currency_totals.items():
            symbol = currency_symbols.get(currency, currency)
            currency_name = {'CNY': '人民币', 'USD': '美元', 'HKD': '港币'}.get(currency, currency)
            message += f"• {currency_name}: {symbol}{total:,.2f}\n"
        
        return message
    
    def _resolve_stock_code(self, stock_name: str) -> Optional[str]:
        """解析股票代码"""
        # 复用 StockSkill 的解析逻辑
        return self.stock_skill._resolve_symbol(stock_name, "AUTO")
    
    def _get_market_from_code(self, tencent_code: str) -> str:
        """从腾讯代码获取市场（支持股票和基金）"""
        code = tencent_code[2:] if len(tencent_code) > 2 else ""
        
        if tencent_code.startswith('hk'):
            return "港股"
        elif tencent_code.startswith('us'):
            return "美股"
        elif tencent_code.startswith(('sh', 'sz')):
            # 判断是否为基金
            if len(code) == 5:
                return "基金"  # 5位ETF代码
            elif code.startswith(('15', '16', '50', '51', '56', '58', '60')):
                return "基金"  # LOF或特定ETF
            else:
                return "A股"
        return "未知"
    
    def _get_stock_real_name(self, tencent_code: str) -> Optional[str]:
        """从映射表获取股票/基金真实名称"""
        # 先查股票映射
        for name, code in self.stock_skill.STOCK_NAME_MAP.items():
            if code == tencent_code:
                return name
        # 再查基金映射
        for name, code in self.stock_skill.FUND_NAME_MAP.items():
            if code == tencent_code:
                return name
        return None
    
    def parse_trade_message(self, message: str) -> Optional[Dict[str, Any]]:
        """
        从自然语言消息中解析交易信息
        支持格式：
        - 买入茅台 100股 价格1500
        - 卖出腾讯 50股 400元
        - 买入AAPL 10股 180美元
        - 买入腾讯 100股 400港币
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
            for kw in ['买入', '卖出', 'buy', 'sell', '购买', '记录', '价格', '元', '美元', '港币', '人民币']:
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
        
        # 识别币种
        currency = self._detect_currency(message, stock_name)
        
        if action and stock_name and shares > 0 and price > 0:
            return {
                'action': action,
                'stock_name': stock_name,
                'shares': shares,
                'price': price,
                'currency': currency
            }
        
        return None
    
    def _detect_currency(self, message: str, stock_name: str) -> str:
        """
        检测交易币种
        支持人民币(CNY)、美元(USD)、港币(HKD)
        """
        message_upper = message.upper()
        
        # 1. 直接识别币种关键词
        if any(kw in message for kw in ['美元', 'USD', '$', '美金']):
            return 'USD'
        if any(kw in message for kw in ['港币', '港元', 'HKD', 'HK$']):
            return 'HKD'
        if any(kw in message for kw in ['人民币', 'CNY', 'RMB', '¥']):
            return 'CNY'
        
        # 2. 根据股票名称推断（如果未明确指定币种）
        # 美股常用代码
        us_stocks = ['AAPL', 'GOOGL', 'GOOG', 'MSFT', 'AMZN', 'TSLA', 'META', 'NVDA', 
                     'NFLX', 'AMD', 'INTC', 'BABA', 'JD', 'PDD', 'NIO', 'LI', 'XPEV',
                     '苹果', '微软', '谷歌', '亚马逊', '特斯拉', 'Meta', '英伟达',
                     '奈飞', '英特尔', '阿里巴巴', '拼多多', '蔚来', '理想', '小鹏']
        
        # 港股常用代码
        hk_stocks = ['腾讯', '美团', '小米', '阿里', '京东', '百度', '网易', '快手',
                     '比亚迪', '港交所', '中国移动', '联想', '李宁', '安踏', '海底捞',
                     '00700', '03690', '01810', '09988', '09618', '09888', '09999']
        
        if stock_name.upper() in us_stocks or any(s in stock_name for s in us_stocks):
            return 'USD'
        
        if stock_name in hk_stocks or any(s in stock_name for s in hk_stocks):
            return 'HKD'
        
        # 3. 默认人民币
        return 'CNY'
    
    async def parse_with_llm(self, message: str) -> Optional[Dict[str, Any]]:
        """
        使用大模型解析交易消息
        当正则解析失败时使用此方法
        """
        if not self.kimi_api_key:
            return None
        
        prompt = f"""请从以下消息中解析股票交易信息。

用户消息: "{message}"

请提取以下字段（JSON格式）:
- action: "buy" 或 "sell" (买入/卖出)
- stock_name: 股票名称或代码（如：茅台、腾讯、AAPL、美团）
- shares: 股数（整数）
- price: 价格（数字）

如果这不是交易消息，返回 null。

只返回JSON，不要其他内容。示例:
{{"action": "buy", "stock_name": "美团", "shares": 6300, "price": 98.71}}
"""
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.kimi_api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.kimi_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "moonshot-v1-8k",
                        "messages": [
                            {"role": "system", "content": "你是一个股票交易信息提取助手，擅长从自然语言中解析交易数据。"},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.1,
                        "max_tokens": 200
                    },
                    timeout=10
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    
                    # 提取 JSON
                    try:
                        # 尝试直接解析
                        result = json.loads(content)
                    except json.JSONDecodeError:
                        # 尝试从文本中提取 JSON
                        import re
                        json_match = re.search(r'\{[^}]+\}', content)
                        if json_match:
                            result = json.loads(json_match.group())
                        else:
                            return None
                    
                    # 验证结果
                    if result and all(k in result for k in ['action', 'stock_name', 'shares', 'price']):
                        return {
                            'action': result['action'],
                            'stock_name': str(result['stock_name']),
                            'shares': int(result['shares']),
                            'price': float(result['price'])
                        }
                        
        except Exception as e:
            print(f"LLM 解析交易消息失败: {e}")
        
        return None
    
    async def smart_parse_trade(self, message: str) -> Optional[Dict[str, Any]]:
        """
        智能解析交易消息
        先尝试正则解析，失败则使用大模型
        """
        # 首先尝试正则解析（更快）
        result = self.parse_trade_message(message)
        if result:
            return result
        
        # 如果看起来像交易消息但正则失败，尝试大模型
        trade_keywords = ['买入', '卖出', 'buy', 'sell', '购买', '抛售']
        if any(kw in message for kw in trade_keywords):
            # 检查是否包含数字（可能是价格和股数）
            if re.search(r'\d+', message):
                return await self.parse_with_llm(message)
        
        return None
