"""
价值投资分析模块 - 基于巴菲特投资理念
- 内在价值计算（DCF模型）
- 安全边际评估
- 护城河分析
- 财务健康度评分
"""
import httpx
import json
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class ValuationResult:
    """估值结果"""
    stock_code: str
    stock_name: str
    current_price: float
    intrinsic_value: float
    margin_of_safety: float  # 安全边际百分比
    valuation_method: str
    confidence: str  # 高/中/低
    key_metrics: Dict[str, Any]
    analysis_date: str
    
    @property
    def is_undervalued(self) -> bool:
        """是否被低估"""
        return self.margin_of_safety > 0.3  # 30%以上安全边际视为低估
    
    @property
    def recommendation(self) -> str:
        """投资建议"""
        if self.margin_of_safety > 0.5:
            return "强烈买入"
        elif self.margin_of_safety > 0.3:
            return "买入"
        elif self.margin_of_safety > 0.1:
            return "持有"
        elif self.margin_of_safety > -0.1:
            return "观望"
        else:
            return "卖出"


class ValueInvestingAnalyzer:
    """价值投资分析器"""
    
    # 腾讯财经财务数据API
    TENCENT_FINANCE_URL = "http://qt.gtimg.cn/q=ff_{code}"
    
    def __init__(self, kimi_api_key: Optional[str] = None):
        self.kimi_api_key = kimi_api_key
        self.kimi_api_base = "https://api.moonshot.cn/v1"
    
    async def analyze(self, stock_code: str, stock_name: str, 
                      current_price: float, market: str) -> ValuationResult:
        """
        执行价值投资分析
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            current_price: 当前价格
            market: 市场类型（A股/港股/美股/基金）
        """
        # 1. 获取财务数据
        financial_data = await self._get_financial_data(stock_code, market)
        
        # 2. 计算关键指标
        metrics = self._calculate_metrics(financial_data, current_price)
        
        # 3. 计算内在价值（多方法）
        dcf_value = self._dcf_valuation(financial_data, current_price)
        pe_value = self._pe_valuation(financial_data, current_price)
        pb_value = self._pb_valuation(financial_data, current_price)
        
        # 4. 综合估值（加权平均）
        intrinsic_value = self._composite_valuation(dcf_value, pe_value, pb_value, metrics)
        
        # 5. 计算安全边际
        margin_of_safety = (intrinsic_value - current_price) / intrinsic_value if intrinsic_value > 0 else 0
        
        # 6. 评估置信度
        confidence = self._assess_confidence(financial_data, metrics)
        
        return ValuationResult(
            stock_code=stock_code,
            stock_name=stock_name,
            current_price=current_price,
            intrinsic_value=intrinsic_value,
            margin_of_safety=margin_of_safety,
            valuation_method="综合估值（DCF+PE+PB）",
            confidence=confidence,
            key_metrics=metrics,
            analysis_date=datetime.now().strftime('%Y-%m-%d')
        )
    
    async def _get_financial_data(self, stock_code: str, market: str) -> Dict[str, Any]:
        """获取财务数据"""
        data = {
            'eps': 0,  # 每股收益
            'bps': 0,  # 每股净资产
            'roe': 0,  # 净资产收益率
            'roa': 0,  # 总资产收益率
            'pe': 0,   # 市盈率
            'pb': 0,   # 市净率
            'debt_ratio': 0,  # 资产负债率
            'current_ratio': 0,  # 流动比率
            'revenue_growth': 0,  # 营收增长率
            'profit_growth': 0,   # 利润增长率
            'fcf': 0,   # 自由现金流
            'dividend_yield': 0,  # 股息率
            'market_cap': 0,  # 市值
        }
        
        try:
            # 转换代码格式
            if market == "A股":
                prefix = "sh" if stock_code.startswith('6') else "sz"
                tencent_code = f"{prefix}{stock_code}"
            elif market == "港股":
                tencent_code = f"hk{stock_code}"
            elif market == "美股":
                tencent_code = f"us{stock_code}"
            else:
                tencent_code = stock_code
            
            # 从腾讯财经获取基本数据
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
                        data['pb'] = float(values[46]) if len(values) > 46 and values[46] else 0
                        data['market_cap'] = float(values[44]) if values[44] else 0
            
            # 获取财务指标（简化版本，实际需要更详细的财务API）
            # 使用AI估算部分指标
            if self.kimi_api_key:
                ai_metrics = await self._get_ai_estimated_metrics(stock_code, stock_name, market)
                data.update(ai_metrics)
            
        except Exception as e:
            print(f"获取财务数据失败 {stock_code}: {e}")
        
        return data
    
    async def _get_ai_estimated_metrics(self, stock_code: str, stock_name: str, 
                                         market: str) -> Dict[str, float]:
        """使用AI估算财务指标（当无法获取实时数据时）"""
        try:
            prompt = f"""请估算 {stock_name}({stock_code}) 的关键财务指标。

已知信息:
- 股票代码: {stock_code}
- 市场: {market}
- 当前时间: {datetime.now().strftime('%Y-%m-%d')}

请基于公开信息，给出以下指标的合理估算值（仅返回JSON格式）:
{{
    "eps": 每股收益（元）,
    "bps": 每股净资产（元）,
    "roe": 净资产收益率（%）,
    "roa": 总资产收益率（%）,
    "debt_ratio": 资产负债率（%）,
    "current_ratio": 流动比率,
    "revenue_growth": 营收增长率（%）,
    "profit_growth": 净利润增长率（%）,
    "fcf": 每股自由现金流（元）,
    "dividend_yield": 股息率（%）
}}

注意：
1. 使用合理的行业平均值或基于公司公开财报数据
2. 如果不确定，使用保守估计
3. 只返回JSON，不要其他内容"""

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
                            {"role": "system", "content": "你是财务分析专家，擅长估算上市公司财务指标。"},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 500
                    },
                    timeout=30
                )
                
                if resp.status_code == 200:
                    result = resp.json()
                    content = result["choices"][0]["message"]["content"]
                    
                    # 提取JSON
                    try:
                        json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
                        if json_match:
                            metrics = json.loads(json_match.group())
                            # 转换为float
                            return {k: float(v) for k, v in metrics.items()}
                    except:
                        pass
        except Exception as e:
            print(f"AI估算失败: {e}")
        
        # 返回默认值
        return {
            'eps': 1.0,
            'bps': 10.0,
            'roe': 10.0,
            'roa': 5.0,
            'debt_ratio': 50.0,
            'current_ratio': 1.5,
            'revenue_growth': 10.0,
            'profit_growth': 10.0,
            'fcf': 0.5,
            'dividend_yield': 2.0
        }
    
    def _calculate_metrics(self, financial_data: Dict, current_price: float) -> Dict[str, Any]:
        """计算关键价值指标"""
        metrics = {
            # 盈利能力
            'roe': financial_data.get('roe', 0),
            'roa': financial_data.get('roa', 0),
            'profit_margin': financial_data.get('eps', 0) / current_price * 100 if current_price > 0 else 0,
            
            # 成长性
            'revenue_growth': financial_data.get('revenue_growth', 0),
            'profit_growth': financial_data.get('profit_growth', 0),
            
            # 财务健康
            'debt_ratio': financial_data.get('debt_ratio', 0),
            'current_ratio': financial_data.get('current_ratio', 0),
            
            # 估值水平
            'pe': financial_data.get('pe', 0),
            'pb': financial_data.get('pb', 0),
            'dividend_yield': financial_data.get('dividend_yield', 0),
            
            # 价值指标
            'earnings_yield': 1 / financial_data.get('pe', 100) * 100 if financial_data.get('pe', 0) > 0 else 0,
            'price_to_fcf': current_price / financial_data.get('fcf', 1) if financial_data.get('fcf', 0) > 0 else 999,
        }
        
        # 计算综合质量评分（0-100）
        quality_score = 0
        if metrics['roe'] > 15: quality_score += 20
        elif metrics['roe'] > 10: quality_score += 10
        if metrics['roa'] > 8: quality_score += 15
        elif metrics['roa'] > 5: quality_score += 8
        if metrics['debt_ratio'] < 40: quality_score += 15
        elif metrics['debt_ratio'] < 60: quality_score += 8
        if metrics['revenue_growth'] > 15: quality_score += 15
        elif metrics['revenue_growth'] > 8: quality_score += 8
        if metrics['profit_growth'] > 15: quality_score += 15
        elif metrics['profit_growth'] > 8: quality_score += 8
        if metrics['current_ratio'] > 1.5: quality_score += 10
        elif metrics['current_ratio'] > 1.0: quality_score += 5
        if metrics['dividend_yield'] > 3: quality_score += 10
        elif metrics['dividend_yield'] > 1: quality_score += 5
        
        metrics['quality_score'] = min(quality_score, 100)
        metrics['quality_rating'] = '优秀' if quality_score >= 80 else '良好' if quality_score >= 60 else '一般' if quality_score >= 40 else '较差'
        
        return metrics
    
    def _dcf_valuation(self, financial_data: Dict, current_price: float) -> float:
        """
        DCF现金流折现估值（简化版）
        使用戈登增长模型变体
        """
        fcf = financial_data.get('fcf', 0)
        growth_rate = min(financial_data.get('profit_growth', 5) / 100, 0.25)  # 最高25%增长假设
        discount_rate = 0.10  # 10%折现率（要求回报率）
        terminal_growth = 0.03  # 永续增长率3%
        
        if fcf <= 0 or growth_rate <= 0:
            # 无法使用DCF，使用当前价格的1.2倍作为估算
            return current_price * 1.2
        
        # 简化DCF：假设未来5年保持增长，之后永续增长
        # Value = FCF * (1+g) / (r-g)
        if discount_rate <= growth_rate:
            growth_rate = discount_rate - 0.01
        
        intrinsic_value = fcf * (1 + growth_rate) / (discount_rate - terminal_growth)
        
        return max(intrinsic_value, current_price * 0.5)  # 保底50%当前价
    
    def _pe_valuation(self, financial_data: Dict, current_price: float) -> float:
        """PE市盈率估值"""
        eps = financial_data.get('eps', 0)
        current_pe = financial_data.get('pe', 0)
        
        if eps <= 0:
            return current_price
        
        # 根据成长性确定合理PE
        growth = financial_data.get('profit_growth', 5)
        if growth > 20:
            fair_pe = 25
        elif growth > 15:
            fair_pe = 20
        elif growth > 10:
            fair_pe = 15
        else:
            fair_pe = 12
        
        # 考虑ROE调整
        roe = financial_data.get('roe', 10)
        if roe > 15:
            fair_pe += 3
        elif roe < 8:
            fair_pe -= 2
        
        return eps * fair_pe
    
    def _pb_valuation(self, financial_data: Dict, current_price: float) -> float:
        """PB市净率估值"""
        bps = financial_data.get('bps', 0)
        roe = financial_data.get('roe', 10)
        
        if bps <= 0:
            return current_price
        
        # 根据ROE确定合理PB
        # PB = ROE / (r - g) 的简化版本
        if roe > 15:
            fair_pb = 2.5
        elif roe > 12:
            fair_pb = 2.0
        elif roe > 8:
            fair_pb = 1.5
        else:
            fair_pb = 1.0
        
        return bps * fair_pb
    
    def _composite_valuation(self, dcf: float, pe: float, pb: float, 
                             metrics: Dict) -> float:
        """综合估值（加权平均）"""
        # 根据数据质量调整权重
        confidence = metrics.get('quality_score', 50)
        
        if confidence >= 80:
            # 高质量数据，DCF权重更高
            weights = {'dcf': 0.5, 'pe': 0.3, 'pb': 0.2}
        elif confidence >= 60:
            # 中等质量
            weights = {'dcf': 0.4, 'pe': 0.35, 'pb': 0.25}
        else:
            # 低质量数据，更依赖相对估值
            weights = {'dcf': 0.25, 'pe': 0.4, 'pb': 0.35}
        
        intrinsic = dcf * weights['dcf'] + pe * weights['pe'] + pb * weights['pb']
        return intrinsic
    
    def _assess_confidence(self, financial_data: Dict, metrics: Dict) -> str:
        """评估估值置信度"""
        score = 0
        
        # 数据完整性
        if financial_data.get('eps', 0) > 0: score += 20
        if financial_data.get('fcf', 0) > 0: score += 20
        if financial_data.get('roe', 0) > 0: score += 15
        if financial_data.get('pe', 0) > 0: score += 15
        if financial_data.get('pb', 0) > 0: score += 15
        if financial_data.get('debt_ratio', 0) > 0: score += 15
        
        if score >= 80:
            return "高"
        elif score >= 50:
            return "中"
        else:
            return "低"
    
    def format_analysis_report(self, result: ValuationResult, is_update: bool = False) -> str:
        """格式化分析报告"""
        emoji = "📈" if result.is_undervalued else "📉"
        action = result.recommendation
        action_emoji = {
            "强烈买入": "🟢",
            "买入": "🟢",
            "持有": "🟡",
            "观望": "⚪",
            "卖出": "🔴"
        }.get(action, "⚪")
        
        report = f"""{emoji} {'【更新】' if is_update else '【首次】'}价值投资分析报告
━━━━━━━━━━━━━━━━━━━━

📊 {result.stock_name} ({result.stock_code})

💰 估值分析:
• 当前价格: ¥{result.current_price:.2f}
• 内在价值: ¥{result.intrinsic_value:.2f}
• 安全边际: {result.margin_of_safety:+.1%}
• 估值方法: {result.valuation_method}
• 置信度: {result.confidence}

{action_emoji} 投资建议: {action}
"""
        
        # 添加关键指标
        metrics = result.key_metrics
        report += f"""
📈 关键指标:
• 质量评分: {metrics.get('quality_score', 0)}/100 ({metrics.get('quality_rating', '未知')})
• ROE: {metrics.get('roe', 0):.1f}%
• PE: {metrics.get('pe', 0):.1f}
• PB: {metrics.get('pb', 0):.2f}
• 股息率: {metrics.get('dividend_yield', 0):.2f}%
• 负债率: {metrics.get('debt_ratio', 0):.1f}%
"""
        
        # 添加分析说明
        report += f"""
💡 分析说明:
"""
        if result.margin_of_safety > 0.3:
            report += "✅ 当前价格低于内在价值，具有足够的安全边际。\n"
        elif result.margin_of_safety > 0:
            report += "⚠️ 当前价格略低于内在价值，安全边际较小。\n"
        else:
            report += "❌ 当前价格高于内在价值，存在高估风险。\n"
        
        if metrics.get('quality_score', 0) >= 80:
            report += "✅ 公司财务质量优秀，具有护城河优势。\n"
        elif metrics.get('quality_score', 0) >= 60:
            report += "⚠️ 公司财务质量良好，但需关注变化。\n"
        else:
            report += "❌ 公司财务质量一般，需谨慎评估。\n"
        
        report += f"\n⏰ 分析时间: {result.analysis_date}"
        
        return report


# 存储估值历史的简单数据库操作
class ValuationHistory:
    """估值历史管理"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS valuations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT,
                    current_price REAL,
                    intrinsic_value REAL,
                    margin_of_safety REAL,
                    key_metrics TEXT,
                    analysis_date TEXT,
                    is_first_analysis INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
    
    def save_valuation(self, result: ValuationResult, is_first: bool = False):
        """保存估值结果"""
        import sqlite3
        import json
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO valuations 
                (stock_code, stock_name, current_price, intrinsic_value, 
                 margin_of_safety, key_metrics, analysis_date, is_first_analysis)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                result.stock_code,
                result.stock_name,
                result.current_price,
                result.intrinsic_value,
                result.margin_of_safety,
                json.dumps(result.key_metrics, ensure_ascii=False),
                result.analysis_date,
                1 if is_first else 0
            ))
            conn.commit()
    
    def get_last_valuation(self, stock_code: str) -> Optional[Dict]:
        """获取最近一次估值"""
        import sqlite3
        import json
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT * FROM valuations 
                WHERE stock_code = ? 
                ORDER BY created_at DESC 
                LIMIT 1
            ''', (stock_code,))
            row = cursor.fetchone()
            if row:
                return {
                    'stock_code': row[1],
                    'stock_name': row[2],
                    'current_price': row[3],
                    'intrinsic_value': row[4],
                    'margin_of_safety': row[5],
                    'key_metrics': json.loads(row[6]) if row[6] else {},
                    'analysis_date': row[7],
                    'is_first_analysis': row[8]
                }
            return None
