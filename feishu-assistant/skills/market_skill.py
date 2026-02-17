"""
市场查询技能
查询美股、港股、A股等市场行情
"""
import httpx
from datetime import datetime
from typing import Dict, Any
from .base_skill import BaseSkill, SkillResult


class MarketSkill(BaseSkill):
    """市场查询技能"""
    
    name = "query_market"
    description = "查询金融市场行情，包括美股、港股、A股等指数"
    examples = [
        "查询今天的美股行情",
        "看看纳斯达克涨了多少",
        "港股今天怎么样",
        "A股走势如何"
    ]
    parameters = {
        "market": {
            "type": "string",
            "description": "市场类型: US(美股), HK(港股), CN(A股)",
            "enum": ["US", "HK", "CN"],
            "mapping": {
                "US": ["美股", "美国", "美股", "纳斯达克", "标普", "道琼斯", "美"],
                "HK": ["港股", "香港", "恒生", "港"],
                "CN": ["A股", "中国", "上证", "深证", "沪深", "中"]
            },
            "default": "US"
        }
    }
    
    # 指数代码映射
    INDICES = {
        "US": {
            "标普500": "^GSPC",
            "纳斯达克": "^IXIC", 
            "道琼斯": "^DJI"
        },
        "HK": {
            "恒生指数": "^HSI",
            "恒生科技": "^HSTECH"
        },
        "CN": {
            "上证指数": "000001.SS",
            "深证成指": "399001.SZ",
            "创业板指": "399006.SZ"
        }
    }
    
    # 中文到代码的映射
    MARKET_MAPPING = {
        # 美股
        "美股": "US", "美国": "US", "美": "US", "美股市": "US",
        "纳斯达克": "US", "标普": "US", "道琼斯": "US",
        "US": "US", "USA": "US",
        # 港股
        "港股": "HK", "香港": "HK", "港": "HK", "港股市": "HK",
        "恒生": "HK", "恒指": "HK",
        "HK": "HK",
        # A股/中国
        "A股": "CN", "a股": "CN", "中国": "CN", "中": "CN", "中股市": "CN",
        "上证": "CN", "深证": "CN", "沪深": "CN",
        "CN": "CN"
    }
    
    async def execute(self, market: str = "US", **kwargs) -> SkillResult:
        """
        执行市场查询
        
        Args:
            market: 市场类型 (US/HK/CN)，支持中英文
        """
        try:
            # 标准化市场参数
            normalized_market = self._normalize_market(market)
            
            if normalized_market not in self.INDICES:
                available = ", ".join(self.INDICES.keys())
                # 提供更友好的错误提示
                market_names = {"US": "美股", "HK": "港股", "CN": "A股"}
                return SkillResult(
                    success=False,
                    message=f"❓ 我不太明白您要查询哪个市场。\n\n您说的是「{market}」吗？\n\n支持的市场:\n"
                            f"🇺🇸 美股 (US) - 标普500、纳斯达克、道琼斯\n"
                            f"🇭🇰 港股 (HK) - 恒生指数、恒生科技\n"
                            f"🇨🇳 A股 (CN) - 上证指数、深证成指\n\n"
                            f"请尝试说「美股行情」或「查询港股」"
                )
            
            # 查询数据
            indices = await self._fetch_market_data(normalized_market)
            
            # 格式化结果
            message = self._format_message(normalized_market, indices)
            card = self._format_card(normalized_market, indices)
            
            return SkillResult(
                success=True,
                message=message,
                data={"market": normalized_market, "indices": indices},
                card_content=card
            )
            
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"❌ 查询失败: {str(e)}"
            )
    
    def _normalize_market(self, market: str) -> str:
        """标准化市场参数"""
        if not market:
            return "US"
        
        # 转换为大写并去除空格
        market_clean = str(market).strip().upper()
        
        # 直接映射
        if market_clean in self.MARKET_MAPPING:
            return self.MARKET_MAPPING[market_clean]
        
        # 尝试模糊匹配
        for key, value in self.MARKET_MAPPING.items():
            if key.upper() in market_clean or market_clean in key.upper():
                return value
        
        # 如果包含特定关键词
        if any(kw in market_clean for kw in ["美", "US", "纳指", "标普"]):
            return "US"
        if any(kw in market_clean for kw in ["港", "HK", "恒生"]):
            return "HK"
        if any(kw in market_clean for kw in ["中", "CN", "A股", "上证", "深证"]):
            return "CN"
        
        # 默认返回原始值（可能是无效的）
        return market_clean
    
    async def _fetch_market_data(self, market: str) -> Dict[str, Dict]:
        """获取市场数据"""
        indices = {}
        
        async with httpx.AsyncClient() as client:
            for name, symbol in self.INDICES[market].items():
                try:
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
                    resp = await client.get(
                        url,
                        headers={"User-Agent": "Mozilla/5.0"},
                        timeout=10
                    )
                    data = resp.json()
                    
                    meta = data["chart"]["result"][0]["meta"]
                    prev_close = meta.get("previousClose", 0)
                    current = meta.get("regularMarketPrice", 0)
                    
                    change = 0
                    if prev_close > 0:
                        change = ((current - prev_close) / prev_close) * 100
                    
                    indices[name] = {
                        "price": round(current, 2),
                        "change": round(change, 2),
                        "prev_close": prev_close
                    }
                except Exception as e:
                    indices[name] = {"price": "-", "change": 0, "error": str(e)}
        
        return indices
    
    def _format_message(self, market: str, indices: Dict) -> str:
        """格式化文本消息"""
        market_names = {"US": "美股", "HK": "港股", "CN": "A股"}
        market_emojis = {"US": "🇺🇸", "HK": "🇭🇰", "CN": "🇨🇳"}
        
        msg = f"{market_emojis.get(market, '📊')} {market_names.get(market, market)}行情 {datetime.now().strftime('%m-%d %H:%M')}\n\n"
        
        for name, data in indices.items():
            if "error" in data:
                continue
            emoji = "🟢" if data.get("change", 0) >= 0 else "🔴"
            msg += f"{emoji} {name}: {data['price']} ({data['change']:+.2f}%)\n"
        
        return msg
    
    def _format_card(self, market: str, indices: Dict) -> Dict:
        """格式化飞书卡片"""
        market_names = {"US": "🇺🇸 美股", "HK": "🇭🇰 港股", "CN": "🇨🇳 A股"}
        
        elements = []
        for name, data in indices.items():
            if "error" in data:
                continue
            emoji = "🟢" if data.get("change", 0) >= 0 else "🔴"
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"{emoji} **{name}**: {data['price']} ({data['change']:+.2f}%)"
                }
            })
        
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"{market_names.get(market, market)}行情 {datetime.now().strftime('%m-%d %H:%M')}"
                },
                "template": "blue"
            },
            "elements": elements
        }
