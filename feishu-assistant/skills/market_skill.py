"""
市场查询技能 - 使用腾讯数据源
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
            "default": "US"
        }
    }
    
    # 腾讯财经 API 代码映射
    # 格式: 腾讯代码 -> 显示名称
    TENCENT_CODES = {
        "US": {
            "usDJI": "道琼斯",
            "usIXIC": "纳斯达克",
            "usINX": "标普500"
        },
        "HK": {
            "hkHSI": "恒生指数",
            "hkHSTECH": "恒生科技"
        },
        "CN": {
            "sh000001": "上证指数",
            "sz399001": "深证成指",
            "sz399006": "创业板指"
        }
    }
    
    # 中文到代码的映射
    MARKET_MAPPING = {
        "美股": "US", "美国": "US", "美": "US",
        "纳斯达克": "US", "标普": "US", "道琼斯": "US",
        "US": "US", "USA": "US",
        "港股": "HK", "香港": "HK", "港": "HK",
        "恒生": "HK", "恒指": "HK",
        "HK": "HK",
        "A股": "CN", "a股": "CN", "中国": "CN", "中": "CN",
        "上证": "CN", "深证": "CN", "沪深": "CN",
        "CN": "CN"
    }
    
    async def execute(self, market: str = "US", **kwargs) -> SkillResult:
        """执行市场查询"""
        try:
            # 标准化市场参数
            normalized_market = self._normalize_market(market)
            
            if normalized_market not in self.TENCENT_CODES:
                return SkillResult(
                    success=False,
                    message=f"❓ 我不太明白您要查询哪个市场。\n\n支持的市场:\n"
                            f"🇺🇸 美股 - 标普500、纳斯达克、道琼斯\n"
                            f"🇭🇰 港股 - 恒生指数、恒生科技\n"
                            f"🇨🇳 A股 - 上证指数、深证成指\n\n"
                            f"请尝试说「美股行情」或「查询港股」"
                )
            
            # 查询数据
            indices = await self._fetch_market_data(normalized_market)
            
            if not indices:
                return SkillResult(
                    success=False,
                    message="❌ 暂时无法获取市场数据，请稍后重试"
                )
            
            # 格式化结果
            message = self._format_message(normalized_market, indices)
            
            return SkillResult(
                success=True,
                message=message,
                data={"market": normalized_market, "indices": indices},
                card_content=None  # 暂时使用文本格式
            )
            
        except Exception as e:
            print(f"MarketSkill execute error: {e}")
            import traceback
            traceback.print_exc()
            return SkillResult(
                success=False,
                message=f"❌ 查询失败: {str(e)}"
            )
    
    def _normalize_market(self, market: str) -> str:
        """标准化市场参数"""
        if not market:
            return "US"
        
        market_clean = str(market).strip().upper()
        
        # 直接映射
        if market_clean in self.MARKET_MAPPING:
            return self.MARKET_MAPPING[market_clean]
        
        # 模糊匹配
        for key, value in self.MARKET_MAPPING.items():
            if key.upper() in market_clean or market_clean in key.upper():
                return value
        
        # 关键词匹配
        if any(kw in market_clean for kw in ["美", "US", "纳指", "标普", "道"]):
            return "US"
        if any(kw in market_clean for kw in ["港", "HK", "恒生"]):
            return "HK"
        if any(kw in market_clean for kw in ["中", "CN", "A股", "上证", "深证", "沪深"]):
            return "CN"
        
        return market_clean
    
    async def _fetch_market_data(self, market: str) -> Dict[str, Dict]:
        """从腾讯财经获取市场数据"""
        indices = {}
        codes = self.TENCENT_CODES[market]
        
        try:
            # 构建请求
            code_str = ",".join(codes.keys())
            url = f"http://qt.gtimg.cn/q={code_str}"
            
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10)
                resp.encoding = 'gbk'  # 腾讯返回GBK编码
                data = resp.text
            
            # 解析返回数据
            # 格式: v_代码="数据字段..."
            for line in data.strip().split(';'):
                line = line.strip()
                if not line or '="' not in line:
                    continue
                
                # 提取代码和数据
                parts = line.split('="')
                if len(parts) < 2:
                    continue
                
                code_key = parts[0].replace('v_', '')
                values_str = parts[1].rstrip('"')
                
                if code_key not in codes:
                    continue
                
                values = values_str.split('~')
                if len(values) < 45:
                    continue
                
                # 腾讯数据字段说明:
                # 1: 市场代码, 2: 名称, 3: 代码, 4: 当前价格, 5: 昨收, ...
                # 32: 涨跌幅%, 33: 涨跌额
                try:
                    name = codes[code_key]
                    current = float(values[3]) if values[3] else 0
                    prev_close = float(values[4]) if values[4] else 0
                    change_percent = float(values[32]) if values[32] else 0
                    
                    indices[name] = {
                        "price": round(current, 2),
                        "change": round(change_percent, 2),
                        "prev_close": round(prev_close, 2)
                    }
                except (ValueError, IndexError) as e:
                    print(f"解析 {code_key} 数据失败: {e}")
                    continue
                    
        except Exception as e:
            print(f"获取市场数据失败: {e}")
            import traceback
            traceback.print_exc()
        
        return indices
    
    def _format_message(self, market: str, indices: Dict) -> str:
        """格式化文本消息"""
        market_names = {"US": "美股", "HK": "港股", "CN": "A股"}
        market_emojis = {"US": "🇺🇸", "HK": "🇭🇰", "CN": "🇨🇳"}
        
        msg = f"{market_emojis.get(market, '📊')} {market_names.get(market, market)}行情 {datetime.now().strftime('%m-%d %H:%M')}\n\n"
        
        for name, data in indices.items():
            emoji = "🟢" if data.get("change", 0) >= 0 else "🔴"
            msg += f"{emoji} {name}: {data['price']} ({data['change']:+.2f}%)\n"
        
        return msg
