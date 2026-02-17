"""
个股分析技能
查询个股实时行情和基础分析
支持 A股、港股、美股
"""
import httpx
import re
from datetime import datetime
from typing import Dict, Any, Optional
from .base_skill import BaseSkill, SkillResult


class StockSkill(BaseSkill):
    """个股分析技能"""
    
    name = "analyze_stock"
    description = "分析个股行情，查询股票价格、涨跌幅、成交量等信息，支持A股、港股、美股"
    examples = [
        "分析一下茅台的股票",
        "腾讯控股现在多少钱",
        "AAPL股价怎么样",
        "查询宁德时代股票",
        "阿里巴巴港股行情"
    ]
    parameters = {
        "symbol": {
            "type": "string",
            "description": "股票代码或名称，如茅台、腾讯、AAPL、600519",
            "required": True
        },
        "market": {
            "type": "string",
            "description": "市场类型: CN(A股), HK(港股), US(美股)。可选，会自动识别",
            "enum": ["CN", "HK", "US", "AUTO"],
            "default": "AUTO"
        }
    }
    
    # 常见股票名称映射（名称 -> 腾讯代码）
    STOCK_NAME_MAP = {
        # A股
        "茅台": "sh600519", "贵州茅台": "sh600519",
        "五粮液": "sz000858",
        "宁德时代": "sz300750", "宁王": "sz300750",
        "比亚迪": "sz002594",
        "招商银行": "sh600036", "招行": "sh600036",
        "中国平安": "sh601318", "平安": "sh601318",
        "中信证券": "sh600030",
        "东方财富": "sz300059", "东财": "sz300059",
        "中芯国际": "sh688981",
        "海康威视": "sz002415",
        "美的集团": "sz000333", "美的": "sz000333",
        "格力电器": "sz000651", "格力": "sz000651",
        "隆基绿能": "sh601012", "隆基": "sh601012",
        "药明康德": "sh603259",
        "迈瑞医疗": "sz300760",
        "恒瑞医药": "sh600276",
        "立讯精密": "sz002475",
        "顺丰控股": "sz002352", "顺丰": "sz002352",
        "三一重工": "sh600031",
        "伊利股份": "sh600887", "伊利": "sh600887",
        "牧原股份": "sz002714",
        "泸州老窖": "sz000568",
        "海天味业": "sh603288",
        "长江电力": "sh600900",
        "中国中免": "sh601888", "中免": "sh601888",
        "金山办公": "sh688111",
        "韦尔股份": "sh603501",
        "京东方": "sz000725", "京东方A": "sz000725",
        "紫金矿业": "sh601899",
        "工业富联": "sh601138",
        "山西汾酒": "sh600809",
        "五浪液": "sz000858",
        "海光信息": "sh688041",
        "科大讯飞": "sz002230",
        "中际旭创": "sz300308",
        "东方雨虹": "sz002271",
        "盐湖股份": "sz000792",
        "分众传媒": "sz002027",
        " TCL": "sz000100",
        "中国建筑": "sh601668",
        "保利发展": "sh600048",
        "海尔智家": "sh600690",
        "上汽集团": "sh600104",
        "中国建筑": "sh601668",
        "中国国航": "sh601111",
        "南方航空": "sh600029",
        
        # 港股
        "腾讯": "hk00700", "腾讯控股": "hk00700",
        "阿里巴巴": "hk09988", "阿里": "hk09988",
        "美团": "hk03690", "美团点评": "hk03690",
        "小米": "hk01810", "小米集团": "hk01810",
        "京东": "hk09618", "京东集团": "hk09618",
        "百度": "hk09888", "百度集团": "hk09888",
        "网易": "hk09999", "网易-S": "hk09999",
        "快手": "hk01024", "快手-W": "hk01024",
        "比亚迪股份": "hk01211",
        "中国移动": "hk00941",
        "中国平安港股": "hk02318",
        "港交所": "hk00388", "香港交易所": "hk00388",
        "李宁": "hk02331",
        "安踏": "hk02020", "安踏体育": "hk02020",
        "海底捞": "hk06862",
        "药明生物": "hk02269",
        "百济神州": "hk06160",
        "理想汽车": "hk02015", "理想": "hk02015",
        "小鹏汽车": "hk09868", "小鹏": "hk09868",
        "蔚来": "hk09866", "蔚来-SW": "hk09866",
        "中芯国际港股": "hk00981",
        "联想": "hk00992", "联想集团": "hk00992",
        "舜宇光学": "hk02382",
        "招商银行港股": "hk03968",
        
        # 美股
        "苹果": "usAAPL", "Apple": "usAAPL", "AAPL": "usAAPL",
        "微软": "usMSFT", "Microsoft": "usMSFT", "MSFT": "usMSFT",
        "谷歌": "usGOOGL", "Google": "usGOOGL", "GOOGL": "usGOOGL",
        "亚马逊": "usAMZN", "Amazon": "usAMZN", "AMZN": "usAMZN",
        "特斯拉": "usTSLA", "Tesla": "usTSLA", "TSLA": "usTSLA",
        "Meta": "usMETA", "Facebook": "usMETA", "FB": "usMETA",
        "英伟达": "usNVDA", "NVIDIA": "usNVDA", "NVDA": "usNVDA",
        "AMD": "usAMD",
        "英特尔": "usINTC", "Intel": "usINTC", "INTC": "usINTC",
        "台积电": "usTSM", "TSMC": "usTSM", "TSM": "usTSM",
        "阿里巴巴美股": "usBABA", "BABA": "usBABA",
        "京东美股": "usJD", "JD": "usJD",
        "拼多多": "usPDD", "PDD": "usPDD",
        "百度美股": "usBIDU", "BIDU": "usBIDU",
        "网易美股": "usNTES", "NTES": "usNTES",
        "理想汽车美股": "usLI", "LI": "usLI",
        "小鹏汽车美股": "usXPEV", "XPEV": "usXPEV",
        "蔚来美股": "usNIO", "NIO": "usNIO",
        "哔哩哔哩": "usBILI", "B站": "usBILI", "BILI": "usBILI",
        "爱奇艺": "usIQ", "IQ": "usIQ",
        "贝壳": "usBEKE", "BEKE": "usBEKE",
        "富途": "usFUTU", "FUTU": "usFUTU",
        "老虎证券": "usTIGR", "TIGR": "usTIGR",
        "滴滴": "usDIDI", "DIDI": "usDIDI",
        "新东方": "usEDU", "EDU": "usEDU",
        "好未来": "usTAL", "TAL": "usTAL",
        "腾讯音乐": "usTME", "TME": "usTME",
        "唯品会": "usVIPS", "VIPS": "usVIPS",
        "微博": "usWB", "WB": "usWB",
        "携程": "usTCOM", "TCOM": "usTCOM",
        " Salesforce": "usCRM", "CRM": "usCRM",
        "甲骨文": "usORCL", "Oracle": "usORCL", "ORCL": "usORCL",
        "Adobe": "usADBE", "ADBE": "usADBE",
        "思科": "usCSCO", "Cisco": "usCSCO", "CSCO": "usCSCO",
        "奈飞": "usNFLX", "Netflix": "usNFLX", "NFLX": "usNFLX",
        "迪士尼": "usDIS", "Disney": "usDIS", "DIS": "usDIS",
        "沃尔玛": "usWMT", "Walmart": "usWMT", "WMT": "usWMT",
        "可口可乐": "usKO", "Coca-Cola": "usKO", "KO": "usKO",
        "麦当劳": "usMCD", "McDonald": "usMCD", "MCD": "usMCD",
        "星巴克": "usSBUX", "Starbucks": "usSBUX", "SBUX": "usSBUX",
        "耐克": "usNKE", "Nike": "usNKE", "NKE": "usNKE",
        "波音": "usBA", "Boeing": "usBA", "BA": "usBA",
        "万事达": "usMA", "Mastercard": "usMA", "MA": "usMA",
        "Visa": "usV", "V": "usV",
        "JP摩根": "usJPM", "JPM": "usJPM",
        "高盛": "usGS", "Goldman": "usGS", "GS": "usGS",
        "摩根士丹利": "usMS", "Morgan": "usMS", "MS": "usMS",
        "美国银行": "usBAC", "BAC": "usBAC",
        "花旗": "usC", "Citigroup": "usC", "C": "usC",
        "富国银行": "usWFC", "WFC": "usWFC",
        "伯克希尔": "usBRK", "BRK": "usBRK", "巴菲特": "usBRK",
        "强生": "usJNJ", "JNJ": "usJNJ",
        "辉瑞": "usPFE", "Pfizer": "usPFE", "PFE": "usPFE",
        "默沙东": "usMRK", "MRK": "usMRK",
        "艾伯维": "usABBV", "ABBV": "usABBV",
        "礼来": "usLLY", "LLY": "usLLY",
        "诺和诺德": "usNVO", "NVO": "usNVO",
        "联合健康": "usUNH", "UNH": "usUNH",
        "埃克森美孚": "usXOM", "XOM": "usXOM",
        "雪佛龙": "usCVX", "CVX": "usCVX",
        "壳牌": "usSHEL", "SHEL": "usSHEL",
        "BP": "usBP", "英国石油": "usBP",
    }
    
    # 市场识别模式
    MARKET_PATTERNS = {
        "CN": [r"^\d{6}$", r"^(sh|sz)\d{6}$"],  # A股代码
        "HK": [r"^0\d{4}$", r"^hk\d{5}$"],  # 港股代码
        "US": [r"^[A-Z]{1,5}$", r"^us[A-Z]{1,5}$"],  # 美股代码
    }
    
    async def execute(self, symbol: str, market: str = "AUTO", **kwargs) -> SkillResult:
        """
        执行个股分析
        
        Args:
            symbol: 股票代码或名称
            market: 市场类型 (CN/HK/US/AUTO)
        """
        try:
            if not symbol or not symbol.strip():
                return SkillResult(
                    success=False,
                    message="❓ 请提供股票代码或名称\n\n例如:\n• 茅台\n• 腾讯\n• AAPL\n• 600519"
                )
            
            symbol = symbol.strip()
            
            # 识别股票代码
            tencent_code = self._resolve_symbol(symbol, market)
            
            if not tencent_code:
                return SkillResult(
                    success=False,
                    message=f"❓ 未能识别股票「{symbol}」\n\n请尝试:\n"
                            f"• 输入股票全称（如「贵州茅台」）\n"
                            f"• 输入股票代码（如「600519」或「AAPL」）\n"
                            f"• 指定市场后重试"
                )
            
            # 获取数据
            stock_data = await self._fetch_stock_data(tencent_code)
            
            if not stock_data:
                return SkillResult(
                    success=False,
                    message=f"❌ 暂时无法获取「{symbol}」的数据，请稍后重试"
                )
            
            # 生成分析
            analysis = self._analyze_stock(stock_data)
            
            # 格式化输出
            message = self._format_message(stock_data, analysis)
            
            return SkillResult(
                success=True,
                message=message,
                data={"stock": stock_data, "analysis": analysis},
                card_content=None
            )
            
        except Exception as e:
            print(f"StockSkill error: {e}")
            import traceback
            traceback.print_exc()
            return SkillResult(
                success=False,
                message=f"❌ 分析失败: {str(e)}"
            )
    
    def _resolve_symbol(self, symbol: str, market: str) -> Optional[str]:
        """解析股票代码"""
        symbol_clean = symbol.strip()
        
        # 1. 直接匹配名称映射
        if symbol_clean in self.STOCK_NAME_MAP:
            return self.STOCK_NAME_MAP[symbol_clean]
        
        # 2. 尝试匹配名称（忽略大小写）
        symbol_lower = symbol_clean.lower()
        for name, code in self.STOCK_NAME_MAP.items():
            if symbol_lower == name.lower() or symbol_lower in name.lower():
                return code
        
        # 3. 根据模式识别代码格式
        # A股: 6位数字
        if re.match(r'^\d{6}$', symbol_clean):
            if symbol_clean.startswith('6'):
                return f"sh{symbol_clean}"
            else:
                return f"sz{symbol_clean}"
        
        # 已经是腾讯格式
        if re.match(r'^(sh|sz|hk|us)[A-Z0-9]+$', symbol_clean.lower()):
            return symbol_clean.lower()
        
        # 美股代码（纯字母）
        if re.match(r'^[A-Z]{1,5}$', symbol_clean.upper()):
            return f"us{symbol_clean.upper()}"
        
        return None
    
    async def _fetch_stock_data(self, tencent_code: str) -> Optional[Dict]:
        """从腾讯财经获取股票数据"""
        try:
            url = f"http://qt.gtimg.cn/q={tencent_code}"
            
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10)
                resp.encoding = 'gbk'
                data = resp.text
            
            # 解析数据
            # 格式: v_代码="数据~数据~..."
            if '="' not in data:
                return None
            
            parts = data.split('="')
            if len(parts) < 2:
                return None
            
            values_str = parts[1].rstrip('"').rstrip(';')
            values = values_str.split('~')
            
            if len(values) < 45:
                return None
            
            # 提取关键数据
            # 字段说明: 
            # 1: 市场, 2: 名称, 3: 代码, 4: 当前价, 5: 昨收, 
            # 6: 今开, 7: 成交量, 8: 外盘, 9: 内盘,
            # 10-18: 买1-买5价格和数量, 19-27: 卖1-卖5价格和数量,
            # 32: 涨跌幅%, 33: 涨跌额, 34: 最高价, 35: 最低价,
            # 36: 成交量, 37: 成交额, 38: 换手率, 39: 市盈率,
            # 43: 振幅%,  44: 流通市值, 45: 总市值
            
            market_type = values[0]
            name = values[1]
            code = values[2]
            current = float(values[3]) if values[3] else 0
            prev_close = float(values[4]) if values[4] else 0
            open_price = float(values[5]) if values[5] else 0
            high = float(values[33]) if values[33] else 0
            low = float(values[34]) if values[34] else 0
            change_percent = float(values[32]) if values[32] else 0
            change_amount = float(values[31]) if values[31] else 0
            volume = float(values[36]) if values[36] else 0  # 手
            amount = float(values[37]) if values[37] else 0  # 万元
            turnover_rate = float(values[38]) if values[38] else 0
            pe = float(values[39]) if values[39] else 0
            amplitude = float(values[43]) if values[43] else 0
            market_cap = float(values[44]) if values[44] else 0  # 亿元
            
            # 确定市场类型
            market = "未知"
            if tencent_code.startswith('sh') or tencent_code.startswith('sz'):
                market = "A股"
            elif tencent_code.startswith('hk'):
                market = "港股"
            elif tencent_code.startswith('us'):
                market = "美股"
            
            return {
                "name": name,
                "code": code,
                "tencent_code": tencent_code,
                "market": market,
                "current": current,
                "prev_close": prev_close,
                "open": open_price,
                "high": high,
                "low": low,
                "change_percent": change_percent,
                "change_amount": change_amount,
                "volume": volume,  # 单位：手
                "amount": amount,  # 单位：万元
                "turnover_rate": turnover_rate,
                "pe": pe,
                "amplitude": amplitude,
                "market_cap": market_cap,
                "update_time": datetime.now().strftime('%H:%M:%S')
            }
            
        except Exception as e:
            print(f"获取股票数据失败: {e}")
            return None
    
    def _analyze_stock(self, data: Dict) -> Dict:
        """分析股票数据"""
        analysis = {
            "trend": "平",
            "trend_emoji": "⚪",
            "volume_status": "正常",
            "suggestion": "观望"
        }
        
        # 涨跌趋势
        change = data.get("change_percent", 0)
        if change >= 5:
            analysis["trend"] = "大涨"
            analysis["trend_emoji"] = "🚀"
        elif change >= 2:
            analysis["trend"] = "上涨"
            analysis["trend_emoji"] = "📈"
        elif change > 0:
            analysis["trend"] = "小涨"
            analysis["trend_emoji"] = "🟢"
        elif change <= -5:
            analysis["trend"] = "大跌"
            analysis["trend_emoji"] = "📉"
        elif change <= -2:
            analysis["trend"] = "下跌"
            analysis["trend_emoji"] = "🔴"
        elif change < 0:
            analysis["trend"] = "小跌"
            analysis["trend_emoji"] = "🔴"
        
        # 建议
        if change > 5:
            analysis["suggestion"] = "涨幅较大，注意风险"
        elif change > 2:
            analysis["suggestion"] = "表现强势"
        elif change < -5:
            analysis["suggestion"] = "跌幅较大，谨慎操作"
        elif change < -2:
            analysis["suggestion"] = "表现弱势"
        else:
            analysis["suggestion"] = "波动不大，观望为主"
        
        return analysis
    
    def _format_message(self, data: Dict, analysis: Dict) -> str:
        """格式化输出"""
        emoji = analysis.get("trend_emoji", "📊")
        trend = analysis.get("trend", "")
        
        # 格式化成交量
        volume_str = ""
        if data.get("volume", 0) > 0:
            volume = data["volume"]
            if volume >= 10000:
                volume_str = f"{volume/10000:.2f}万手"
            else:
                volume_str = f"{volume:.0f}手"
        
        # 格式化市值
        cap_str = ""
        if data.get("market_cap", 0) > 0:
            cap = data["market_cap"]
            if cap >= 10000:
                cap_str = f"{cap/10000:.2f}万亿"
            else:
                cap_str = f"{cap:.2f}亿"
        
        # 涨跌幅显示
        change = data.get("change_percent", 0)
        change_str = f"+{change:.2f}%" if change >= 0 else f"{change:.2f}%"
        amount_str = f"+{data.get('change_amount', 0):.2f}" if data.get('change_amount', 0) >= 0 else f"{data.get('change_amount', 0):.2f}"
        
        msg = f"""{emoji} {data['name']} ({data['code']}) {data['market']}
━━━━━━━━━━━━━━━━━━━━
💰 当前价格: {data['current']:.2f}  {change_str} ({amount_str})

📊 今日行情:
• 今开: {data['open']:.2f}
• 最高: {data['high']:.2f}
• 最低: {data['low']:.2f}
• 昨收: {data['prev_close']:.2f}

📈 交易数据:
• 成交量: {volume_str}
• 换手率: {data.get('turnover_rate', 0):.2f}%
"""
        
        # 添加市盈率（如果有）
        if data.get("pe", 0) > 0:
            msg += f"• 市盈率: {data['pe']:.2f}\n"
        
        # 添加市值（如果有）
        if cap_str:
            msg += f"• 流通市值: {cap_str}\n"
        
        msg += f"""
💡 分析: {analysis.get('suggestion', '')}
⏰ 更新时间: {data.get('update_time', '')}
"""
        
        return msg
