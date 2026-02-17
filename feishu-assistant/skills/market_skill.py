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
        "港股今天怎么样"
    ]
    parameters = {
        "market": {
            "type": "string",
            "description": "市场类型: US(美股), HK(港股), CN(A股)",
            "enum": ["US", "HK", "CN"],
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
            "深证成指": "399001.SZ"
        }
    }
    
    async def execute(self, market: str = "US", **kwargs) -> SkillResult:
        """
        执行市场查询
        
        Args:
            market: 市场类型 (US/HK/CN)
        """
        try:
            market = market.upper() if market else "US"
            if market not in self.INDICES:
                return SkillResult(
                    success=False,
                    message=f"不支持的市场: {market}，支持 US/HK/CN"
                )
            
            # 查询数据
            indices = await self._fetch_market_data(market)
            
            # 格式化结果
            message = self._format_message(market, indices)
            card = self._format_card(market, indices)
            
            return SkillResult(
                success=True,
                message=message,
                data={"market": market, "indices": indices},
                card_content=card
            )
            
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"查询失败: {str(e)}"
            )
    
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
        msg = f"📊 {market_names.get(market, market)}行情 {datetime.now().strftime('%m-%d %H:%M')}\n\n"
        
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
