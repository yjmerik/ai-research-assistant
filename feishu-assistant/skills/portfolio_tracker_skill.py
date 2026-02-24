"""
持仓跟踪和智能交易提醒技能
自动跟踪持仓股票，生成交易分析和建议（含价值投资分析）
"""
import sqlite3
import os
import json
import httpx
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from .base_skill import BaseSkill, SkillResult
from .stock_skill import StockSkill
from .value_investing_analyzer import ValueInvestingAnalyzer, ValuationHistory


class PortfolioTrackerSkill(BaseSkill):
    """持仓跟踪和智能交易提醒技能"""
    
    name = "track_portfolio"
    description = """跟踪持仓股票，根据实时价格和深度分析生成交易建议。
    功能包括：
    1. 实时监控持仓盈亏
    2. 智能交易建议（买入/卖出/持有）
    3. 风险预警通知
    4. 仓位管理建议
    """
    examples = [
        "/track",
        "/追踪",
        "跟踪我的持仓",
        "分析持仓"
    ]
    parameters = {
        "action": {
            "type": "string",
            "description": "操作类型：track(跟踪分析) 或 history(查看历史)",
            "enum": ["track", "history"],
            "default": "track"
        },
        "user_id": {
            "type": "string",
            "description": "用户ID",
            "required": False
        }
    }
    
    # 推送阈值配置
    THRESHOLDS = {
        "profit_alert": 10.0,      # 盈利超过10%提醒
        "loss_alert": -7.0,        # 亏损超过7%提醒
        "price_change": 3.0,       # 价格变动超过3%提醒
        "volume_spike": 2.0,       # 成交量放大2倍提醒
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        config = config or {}
        
        # 数据库路径（复用 portfolio 的数据库）
        self.db_path = config.get("db_path") or os.environ.get(
            "PORTFOLIO_DB_PATH", 
            "/opt/feishu-assistant/data/portfolio.db"
        )
        
        # 状态记录文件（用于判断变化）
        self.state_file = config.get("state_file") or "/opt/feishu-assistant/data/portfolio_tracker_state.json"
        
        # API 配置
        self.kimi_api_key = config.get("kimi_api_key") or os.environ.get("KIMI_API_KEY")
        self.kimi_api_base = "https://api.moonshot.cn/v1"
        
        # 飞书配置
        self.feishu_app_id = config.get("feishu_app_id") or os.environ.get("FEISHU_APP_ID")
        self.feishu_app_secret = config.get("feishu_app_secret") or os.environ.get("FEISHU_APP_SECRET")
        
        # 股票代码解析器
        self.stock_skill = StockSkill(config)
        
        # 价值投资分析器
        self.value_analyzer = ValueInvestingAnalyzer(self.kimi_api_key)
        
        # 估值历史管理
        db_dir = os.path.dirname(self.db_path)
        self.valuation_history = ValuationHistory(os.path.join(db_dir, "valuation_history.db"))
        
        # 确保目录存在
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
    
    async def execute(self, action: str = "track", user_id: str = "default", 
                     **kwargs) -> SkillResult:
        """执行持仓跟踪"""
        try:
            if action == "track":
                return await self._track_portfolio(user_id)
            elif action == "history":
                return await self._get_alert_history(user_id)
            else:
                return SkillResult(
                    success=False,
                    message=f"❓ 未知操作: {action}\n\n支持: track(跟踪), history(历史)"
                )
        except Exception as e:
            print(f"PortfolioTrackerSkill error: {e}")
            import traceback
            traceback.print_exc()
            return SkillResult(
                success=False,
                message=f"❌ 跟踪失败: {str(e)}"
            )
    
    async def _track_portfolio(self, user_id: str) -> SkillResult:
        """跟踪持仓并生成分析报告（含价值投资分析）"""
        # 1. 获取持仓数据
        holdings = await self._get_holdings(user_id)
        if not holdings:
            return SkillResult(
                success=True,
                message="📋 当前没有持仓需要跟踪"
            )
        
        # 2. 获取实时股价
        for holding in holdings:
            current_price = await self._get_current_price(holding)
            holding['current_price'] = current_price
            
            # 计算盈亏
            if current_price and holding['avg_cost'] > 0:
                holding['pnl_amount'] = (current_price - holding['avg_cost']) * holding['total_shares']
                holding['pnl_percent'] = (current_price - holding['avg_cost']) / holding['avg_cost'] * 100
                holding['current_value'] = current_price * holding['total_shares']
            else:
                holding['pnl_amount'] = 0
                holding['pnl_percent'] = 0
                holding['current_value'] = holding['total_cost']
        
        # 3. 判断是否有显著变化
        significant_changes = self._check_significant_changes(holdings)
        
        # 4. 【新增】价值投资分析（仅限股票，不包括基金）
        valuation_reports = []
        for holding in holdings:
            if holding.get('market') not in ['基金'] and holding.get('current_price'):
                try:
                    # 检查是否是首次分析
                    last_valuation = self.valuation_history.get_last_valuation(holding['stock_code'])
                    is_first = last_valuation is None
                    
                    # 执行价值投资分析
                    valuation = await self.value_analyzer.analyze(
                        stock_code=holding['stock_code'],
                        stock_name=holding['stock_name'],
                        current_price=holding['current_price'],
                        market=holding.get('market', 'A股')
                    )
                    
                    # 估值变化分析（如果不是首次）
                    change_analysis = None
                    if not is_first and last_valuation:
                        change_analysis = await self.value_analyzer.analyze_change(valuation, last_valuation)
                        print(f"  📊 {holding['stock_name']} 估值变化: 价格{change_analysis.price_change:+.2%}, "
                              f"内在价值{change_analysis.intrinsic_change:+.2%}, "
                              f"安全边际{change_analysis.mos_change:+.2%}")
                    
                    # 格式化报告（包含变化分析）
                    report = self.value_analyzer.format_analysis_report(
                        valuation, 
                        change_analysis=change_analysis,
                        is_update=not is_first
                    )
                    valuation_reports.append(report)
                    
                    # 保存估值历史
                    self.valuation_history.save_valuation(valuation, is_first)
                    
                    # 将估值结果添加到持仓数据中
                    holding['intrinsic_value'] = valuation.intrinsic_value
                    holding['margin_of_safety'] = valuation.margin_of_safety
                    holding['valuation_recommendation'] = valuation.recommendation
                    if change_analysis:
                        holding['mos_change'] = change_analysis.mos_change
                        holding['price_change_since_last'] = change_analysis.price_change
                    
                except Exception as e:
                    print(f"价值投资分析失败 {holding['stock_code']}: {e}")
                    import traceback
                    traceback.print_exc()
        
        # 5. 生成AI综合分析（原有逻辑）
        analysis = await self._generate_analysis(holdings, significant_changes)
        
        # 6. 保存当前状态
        self._save_state(user_id, holdings)
        
        # 7. 格式化输出（包含价值投资分析）
        message = self._format_tracker_message(holdings, analysis, significant_changes, valuation_reports)
        
        return SkillResult(success=True, message=message, data={
            "holdings": holdings,
            "analysis": analysis,
            "has_changes": len(significant_changes) > 0,
            "valuation_reports": valuation_reports
        })
    
    async def _get_holdings(self, user_id: str) -> List[Dict]:
        """获取用户持仓"""
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
    
    async def _get_current_price(self, holding: Dict) -> Optional[float]:
        """获取股票/基金当前价格"""
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
                    # 6位基金代码
                    if code.startswith(('15', '16')):
                        prefix = "sz"
                    else:
                        prefix = "sh"
            else:
                # A股
                prefix = "sh" if code.startswith('6') else "sz"
            
            tencent_code = f"{prefix}{code}"
            
            # 使用腾讯财经 API
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
            print(f"获取价格失败 {holding.get('stock_code')}: {e}")
            return None
    
    def _check_significant_changes(self, holdings: List[Dict]) -> List[Dict]:
        """检查显著变化"""
        changes = []
        last_state = self._load_last_state()
        
        for holding in holdings:
            stock_code = holding['stock_code']
            current_pnl = holding.get('pnl_percent', 0)
            current_price = holding.get('current_price', 0)
            
            # 检查是否有历史记录
            if stock_code in last_state:
                last = last_state[stock_code]
                last_pnl = last.get('pnl_percent', 0)
                last_price = last.get('current_price', 0)
                
                # 计算变化
                pnl_change = current_pnl - last_pnl
                price_change_pct = abs((current_price - last_price) / last_price * 100) if last_price > 0 else 0
                
                # 判断是否需要提醒
                if abs(pnl_change) >= self.THRESHOLDS['price_change']:
                    changes.append({
                        'stock_code': stock_code,
                        'stock_name': holding['stock_name'],
                        'type': 'price_change',
                        'change': pnl_change,
                        'current_pnl': current_pnl,
                        'message': f"价格变动 {pnl_change:+.2f}%"
                    })
                
                # 触及止盈止损线
                if current_pnl >= self.THRESHOLDS['profit_alert'] and last_pnl < self.THRESHOLDS['profit_alert']:
                    changes.append({
                        'stock_code': stock_code,
                        'stock_name': holding['stock_name'],
                        'type': 'profit_alert',
                        'current_pnl': current_pnl,
                        'message': f"盈利达到 {current_pnl:.2f}%，建议考虑止盈"
                    })
                
                if current_pnl <= self.THRESHOLDS['loss_alert'] and last_pnl > self.THRESHOLDS['loss_alert']:
                    changes.append({
                        'stock_code': stock_code,
                        'stock_name': holding['stock_name'],
                        'type': 'loss_alert',
                        'current_pnl': current_pnl,
                        'message': f"亏损达到 {current_pnl:.2f}%，建议考虑止损"
                    })
            else:
                # 新持仓
                changes.append({
                    'stock_code': stock_code,
                    'stock_name': holding['stock_name'],
                    'type': 'new_position',
                    'message': "新增持仓"
                })
        
        return changes
    
    async def _generate_analysis(self, holdings: List[Dict], changes: List[Dict]) -> Dict[str, Any]:
        """使用大模型生成分析"""
        if not self.kimi_api_key:
            return {"error": "未配置 AI 分析"}
        
        # 构建持仓摘要
        portfolio_summary = []
        total_cost = sum(h['total_cost'] for h in holdings)
        total_value = sum(h.get('current_value', h['total_cost']) for h in holdings)
        total_pnl = total_value - total_cost
        
        for h in holdings:
            summary = {
                "name": h['stock_name'],
                "code": h['stock_code'],
                "shares": h['total_shares'],
                "avg_cost": h['avg_cost'],
                "current_price": h.get('current_price', h['avg_cost']),
                "pnl_percent": h.get('pnl_percent', 0),
                "market": h['market']
            }
            portfolio_summary.append(summary)
        
        prompt = f"""你是一位专业的投资顾问，请对以下持仓进行分析并给出交易建议。

持仓概况:
- 总成本: ¥{total_cost:,.2f}
- 当前市值: ¥{total_value:,.2f}
- 总盈亏: ¥{total_pnl:,.2f} ({total_pnl/total_cost*100 if total_cost > 0 else 0:.2f}%)

持仓明细:
{json.dumps(portfolio_summary, ensure_ascii=False, indent=2)}

显著变化:
{json.dumps(changes, ensure_ascii=False, indent=2)}

请提供:
1. 整体仓位评价（高/中/低）
2. 每只股票的操作建议（买入/卖出/持有/加仓/减仓）及理由
3. 风险提示
4. 仓位调整建议

请以JSON格式输出: {{
    "overall_rating": "评价",
    "risk_level": "高/中/低",
    "recommendations": [
        {{"stock": "股票名", "action": "操作建议", "reason": "理由", "priority": "高/中/低"}}
    ],
    "risk_warnings": ["风险1", "风险2"],
    "position_adjustment": "调整建议"
}}"""
        
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
                            {"role": "system", "content": "你是专业投资顾问，提供客观、谨慎的投资建议。"},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.7,
                        "max_tokens": 1500
                    },
                    timeout=30
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    
                    # 提取 JSON
                    try:
                        # 尝试直接解析
                        result = json.loads(content)
                    except json.JSONDecodeError:
                        # 尝试从文本中提取 JSON
                        import re
                        json_match = re.search(r'\{[^}]*\}', content, re.DOTALL)
                        if json_match:
                            result = json.loads(json_match.group())
                        else:
                            result = {"raw": content}
                    
                    return result
                else:
                    return {"error": f"API 错误: {resp.status_code}"}
                    
        except Exception as e:
            print(f"生成分析失败: {e}")
            return {"error": str(e)}
    
    def _format_tracker_message(self, holdings: List[Dict], analysis: Dict, 
                                changes: List[Dict], valuation_reports: List[str] = None) -> str:
        """格式化跟踪报告（含价值投资分析）"""
        # 计算总计
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
        
        # 添加显著变化提醒
        if changes:
            message += f"\n🔔 重要提醒:\n"
            for change in changes:
                alert_emoji = "🚨" if change['type'] in ['profit_alert', 'loss_alert'] else "📊"
                message += f"{alert_emoji} {change['stock_name']}: {change['message']}\n"
        
        # 添加个股详情（含估值信息）
        message += f"\n📊 持仓明细:\n"
        for i, h in enumerate(holdings, 1):
            pnl_emoji = "📈" if h.get('pnl_percent', 0) >= 0 else "📉"
            message += f"\n{i}. {h['stock_name']} ({h['stock_code']})\n"
            message += f"   • 持仓: {h['total_shares']}股 | 均价: ¥{h['avg_cost']:.2f}\n"
            if h.get('current_price'):
                message += f"   • 现价: ¥{h['current_price']:.2f}\n"
            if h.get('pnl_percent') is not None:
                message += f"   {pnl_emoji} 盈亏: {h['pnl_percent']:+.2f}%\n"
            # 添加价值投资建议
            if h.get('valuation_recommendation'):
                mos = h.get('margin_of_safety', 0)
                mos_emoji = "🟢" if mos > 0.3 else "🟡" if mos > 0 else "🔴"
                message += f"   {mos_emoji} 估值: {h['valuation_recommendation']}"
                if mos > 0:
                    message += f" (安全边际: {mos:.1%})"
                message += "\n"
        
        # 添加价值投资分析报告
        if valuation_reports:
            message += f"\n\n📚 价值投资分析报告\n"
            message += "=" * 40 + "\n"
            for report in valuation_reports:
                message += f"\n{report}\n"
                message += "-" * 40 + "\n"
        
        # 添加 AI 综合分析建议
        if 'recommendations' in analysis:
            message += f"\n🤖 AI 综合交易建议:\n"
            for rec in analysis['recommendations']:
                action_emoji = {
                    '买入': '🟢', '加仓': '🔼', '持有': '➡️',
                    '减仓': '🔽', '卖出': '🔴'
                }.get(rec.get('action', ''), '➡️')
                priority = rec.get('priority', '中')
                message += f"{action_emoji} {rec['stock']}: {rec['action']}"
                if priority == '高':
                    message += " [高优先级]"
                message += f"\n   💡 {rec.get('reason', '无')}\n"
        
        if 'risk_warnings' in analysis and analysis['risk_warnings']:
            message += f"\n⚠️ 风险提示:\n"
            for warning in analysis['risk_warnings'][:3]:
                message += f"• {warning}\n"
        
        message += f"\n⏰ 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message
    
    def _load_last_state(self) -> Dict:
        """加载上次状态"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('holdings', {})
        except Exception as e:
            print(f"加载状态失败: {e}")
        return {}
    
    def _save_state(self, user_id: str, holdings: List[Dict]):
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
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存状态失败: {e}")
    
    async def _get_alert_history(self, user_id: str) -> SkillResult:
        """获取提醒历史"""
        return SkillResult(
            success=True,
            message="📋 提醒历史功能开发中..."
        )
    
    def should_notify(self, holdings: List[Dict], changes: List[Dict]) -> bool:
        """判断是否应该发送通知"""
        # 有显著变化时通知
        if changes:
            return True
        
        # 检查是否有持仓盈亏超过阈值
        for h in holdings:
            pnl = h.get('pnl_percent', 0)
            if pnl >= self.THRESHOLDS['profit_alert'] or pnl <= self.THRESHOLDS['loss_alert']:
                return True
        
        return False
