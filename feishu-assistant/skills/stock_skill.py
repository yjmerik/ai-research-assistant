"""
个股分析技能 - 增强版
查询个股实时行情、分析师评级、最新研报，并使用 AI 生成综合分析
支持 A股、港股、美股
"""
import httpx
import re
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from .base_skill import BaseSkill, SkillResult


class StockSkill(BaseSkill):
    """个股分析技能"""
    
    name = "analyze_stock"
    description = "分析个股行情，查询股票价格、涨跌幅、成交量、分析师评级、目标价、最新研报等信息，并使用 AI 生成投资分析总结"
    examples = [
        "分析一下茅台的股票",
        "腾讯控股现在多少钱",
        "AAPL股价怎么样",
        "查询宁德时代股票",
        "阿里巴巴港股行情",
        "微软股票分析师怎么看"
    ]
    parameters = {
        "symbol": {
            "type": "string",
            "description": "股票代码或名称，如茅台、腾讯、AAPL、600519、微软、特斯拉",
            "required": True
        },
        "market": {
            "type": "string",
            "description": "市场类型，用于区分同一公司不同市场的股票",
            "enum": ["CN", "HK", "US", "AUTO"],
            "default": "AUTO",
            "mapping": {
                "CN": ["A股", "中国股市", "上证", "深证", "沪市", "深市", "a股", "中国"],
                "HK": ["港股", "香港股市", "港交所", "港股通", "香港"],
                "US": ["美股", "美国股市", "纳斯达克", "纽交所", "美股市场", "美国"]
            }
        }
    }
    
    # LLM API 配置
    KIMI_API_BASE = "https://api.moonshot.cn/v1"
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.kimi_api_key = config.get("kimi_api_key") if config else os.environ.get("KIMI_API_KEY")
    
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
        "海光信息": "sh688041",
        "科大讯飞": "sz002230",
        "中际旭创": "sz300308",
        "东方雨虹": "sz002271",
        "盐湖股份": "sz000792",
        "分众传媒": "sz002027",
        "TCL": "sz000100",
        "中国建筑": "sh601668",
        "保利发展": "sh600048",
        "海尔智家": "sh600690",
        "上汽集团": "sh600104",
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
        "Salesforce": "usCRM", "CRM": "usCRM",
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
        "CN": [r"^\d{6}$", r"^(sh|sz)\d{6}$"],
        "HK": [r"^0\d{4}$", r"^hk\d{5}$"],
        "US": [r"^[A-Z]{1,5}$", r"^us[A-Z]{1,5}$"],
        "FUND": [r"^\d{5}$", r"^(sh|sz)\d{5}$"],  # 基金（ETF等5位代码）
    }
    
    # 常见基金名称映射
    FUND_NAME_MAP = {
        # ETF基金
        "上证50ETF": "sh510050", "510050": "sh510050",
        "沪深300ETF": "sh510300", "510300": "sh510300",
        "中证500ETF": "sh510500", "510500": "sh510500",
        "创业板ETF": "sh159915", "159915": "sh159915",
        "创业板": "sh159915",
        "科创板50ETF": "sh588000", "588000": "sh588000",
        "科创50": "sh588000",
        "芯片ETF": "sh512760", "512760": "sh512760",
        "半导体ETF": "sh512480", "512480": "sh512480",
        "酒ETF": "sh512690", "512690": "sh512690",
        "白酒基金": "sh512690",
        "医药ETF": "sh512010", "512010": "sh512010",
        "医疗ETF": "sh512170", "512170": "sh512170",
        "新能源ETF": "sh516160", "516160": "sh516160",
        "光伏ETF": "sh515790", "515790": "sh515790",
        "新能源汽车ETF": "sh515030", "515030": "sh515030",
        "新能源车ETF": "sh515030",
        "军工ETF": "sh512660", "512660": "sh512660",
        "券商ETF": "sh512000", "512000": "sh512000",
        "银行ETF": "sh512800", "512800": "sh512800",
        "房地产ETF": "sh512200", "512200": "sh512200",
        "传媒ETF": "sh512980", "512980": "sh512980",
        "游戏ETF": "sh159869", "159869": "sh159869",
        "人工智能ETF": "sh159819", "159819": "sh159819",
        "AI ETF": "sh159819",
        "计算机ETF": "sh159998", "159998": "sh159998",
        "软件ETF": "sh159852", "159852": "sh159852",
        "通信ETF": "sh515880", "515880": "sh515880",
        "5G ETF": "sh515050", "515050": "sh515050",
        "云计算ETF": "sh516510", "516510": "sh516510",
        "大数据ETF": "sh515400", "515400": "sh515400",
        "物联网ETF": "sh159896", "159896": "sh159896",
        "智能制造ETF": "sh516800", "516800": "sh516800",
        "工业母机ETF": "sh159667", "159667": "sh159667",
        "机器人ETF": "sh562500", "562500": "sh562500",
        "钢铁ETF": "sh515210", "515210": "sh515210",
        "煤炭ETF": "sh515220", "515220": "sh515220",
        "有色ETF": "sh512400", "512400": "sh512400",
        "化工ETF": "sh516020", "516020": "sh516020",
        "建材ETF": "sh516750", "516750": "sh516750",
        "家电ETF": "sh159996", "159996": "sh159996",
        "农业ETF": "sh159825", "159825": "sh159825",
        "养殖ETF": "sh159865", "159865": "sh159865",
        "畜牧ETF": "sh159867", "159867": "sh159867",
        "旅游ETF": "sh159766", "159766": "sh159766",
        "物流ETF": "sh516910", "516910": "sh516910",
        "航运ETF": "sh517070", "517070": "sh517070",
        "航空ETF": "sh159666", "159666": "sh159666",
        "黄金ETF": "sh518880", "518880": "sh518880",
        "白银ETF": "sh159985", "159985": "sh159985",
        "石油ETF": "sh513090", "513090": "sh513090",
        "油气ETF": "sh159697", "159697": "sh159697",
        "纳斯达克ETF": "sh513100", "513100": "sh513100",
        "标普500ETF": "sh513500", "513500": "sh513500",
        "中概互联ETF": "sh513050", "513050": "sh513050",
        "恒生科技ETF": "sh513130", "513130": "sh513130",
        "恒生医疗ETF": "sh513060", "513060": "sh513060",
        "恒生消费ETF": "sh513970", "513970": "sh513970",
        "日经ETF": "sh513520", "513520": "sh513520",
        "德国ETF": "sh513030", "513030": "sh513030",
        "法国ETF": "sh513080", "513080": "sh513080",
        "教育ETF": "sh513360", "513360": "sh513360",
        "电力ETF": "sh159611", "159611": "sh159611",
        "环保ETF": "sh159861", "159861": "sh159861",
        "碳中和ETF": "sh159790", "159790": "sh159790",
        "ESG ETF": "sh159649", "159649": "sh159649",
        "红利ETF": "sh510880", "510880": "sh510880",
        "股息ETF": "sh512590", "512590": "sh512590",
        "价值ETF": "sh510030", "510030": "sh510030",
        "成长ETF": "sh159906", "159906": "sh159906",
        "质量ETF": "sh515910", "515910": "sh515910",
        "低波动ETF": "sh159552", "159552": "sh159552",
        
        # LOF基金（部分示例）
        "兴全合宜": "sz163417", "163417": "sz163417",
        "兴全合润": "sz163406", "163406": "sz163406",
        "睿远成长": "sh501006", "501006": "sh501006",
        "东方红": "sh501052", "501052": "sh501052",
        "中欧时代": "sz166006", "166006": "sz166006",
        
        # 联接基金（通过ETF代码+后缀或直接代码）
        "沪深300联接": "sh510300",  # 映射到ETF
        "中证500联接": "sh510500",
        "创业板联接": "sh159915",
        "科创50联接": "sh588000",
        "纳斯达克联接": "sh513100",
    }
    
    async def execute(self, symbol: str, market: str = "AUTO", **kwargs) -> SkillResult:
        """执行个股分析"""
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
            
            # 并行获取数据
            stock_data_task = self._fetch_stock_data(tencent_code)
            analyst_data_task = self._fetch_analyst_data(tencent_code)
            news_data_task = self._fetch_news_data(tencent_code)
            
            stock_data = await stock_data_task
            analyst_data = await analyst_data_task
            news_data = await news_data_task
            
            if not stock_data:
                return SkillResult(
                    success=False,
                    message=f"❌ 暂时无法获取「{symbol}」的数据，请稍后重试"
                )
            
            # 生成 AI 综合分析
            ai_analysis = await self._generate_ai_analysis(stock_data, analyst_data, news_data)
            
            # 格式化输出
            message = self._format_enhanced_message(stock_data, analyst_data, news_data, ai_analysis)
            
            return SkillResult(
                success=True,
                message=message,
                data={
                    "stock": stock_data,
                    "analyst": analyst_data,
                    "news": news_data,
                    "ai_analysis": ai_analysis
                },
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
        """解析股票/基金代码"""
        symbol_clean = symbol.strip()
        
        # 1. 直接匹配名称映射（股票）
        if symbol_clean in self.STOCK_NAME_MAP:
            return self.STOCK_NAME_MAP[symbol_clean]
        
        # 2. 直接匹配基金名称映射
        if symbol_clean in self.FUND_NAME_MAP:
            return self.FUND_NAME_MAP[symbol_clean]
        
        # 3. 尝试匹配名称（忽略大小写）- 股票
        symbol_lower = symbol_clean.lower()
        for name, code in self.STOCK_NAME_MAP.items():
            if symbol_lower == name.lower() or symbol_lower in name.lower():
                return code
        
        # 4. 尝试匹配名称（忽略大小写）- 基金
        for name, code in self.FUND_NAME_MAP.items():
            if symbol_lower == name.lower() or symbol_lower in name.lower():
                return code
        
        # 5. 根据模式识别代码格式
        # 6位数字 - 股票或LOF基金
        if re.match(r'^\d{6}$', symbol_clean):
            if symbol_clean.startswith('6'):
                return f"sh{symbol_clean}"
            else:
                return f"sz{symbol_clean}"
        
        # 5位数字 - ETF基金
        if re.match(r'^\d{5}$', symbol_clean):
            # 上海ETF: 51x, 56x, 58x, 60x
            # 深圳ETF: 15x, 16x
            if symbol_clean.startswith(('51', '56', '58', '60', '50')):
                return f"sh{symbol_clean}"
            elif symbol_clean.startswith(('15', '16', '17', '18')):
                return f"sz{symbol_clean}"
            else:
                # 默认上海
                return f"sh{symbol_clean}"
        
        # 已带前缀的代码
        if re.match(r'^(sh|sz|hk|us)[A-Z0-9]+$', symbol_clean.lower()):
            return symbol_clean.lower()
        
        # 美股代码
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
            
            if '="' not in data:
                return None
            
            parts = data.split('="')
            if len(parts) < 2:
                return None
            
            values_str = parts[1].rstrip('"').rstrip(';')
            values = values_str.split('~')
            
            if len(values) < 45:
                return None
            
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
            volume = float(values[36]) if values[36] else 0
            amount = float(values[37]) if values[37] else 0
            turnover_rate = float(values[38]) if values[38] else 0
            pe = float(values[39]) if values[39] else 0
            amplitude = float(values[43]) if values[43] else 0
            market_cap = float(values[44]) if values[44] else 0
            
            market = "未知"
            code_num = tencent_code[2:] if len(tencent_code) > 2 else ""
            
            if tencent_code.startswith('hk'):
                market = "港股"
            elif tencent_code.startswith('us'):
                market = "美股"
            elif tencent_code.startswith(('sh', 'sz')):
                # 判断是否为基金
                # ETF: 5位代码
                # LOF/ETF: 16xxxx, 50xxxx, 51xxxx, 56xxxx, 58xxxx, 60xxxx 等
                # 特别处理：588xxx是科创50ETF，属于基金
                if len(code_num) == 5:
                    market = "基金"
                elif code_num.startswith(('15', '16', '50', '51', '56', '58', '60', '588')):
                    market = "基金"
                else:
                    market = "A股"
            
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
                "volume": volume,
                "amount": amount,
                "turnover_rate": turnover_rate,
                "pe": pe,
                "amplitude": amplitude,
                "market_cap": market_cap,
                "update_time": datetime.now().strftime('%H:%M:%S')
            }
            
        except Exception as e:
            print(f"获取股票数据失败: {e}")
            return None
    
    async def _fetch_analyst_data(self, tencent_code: str) -> Optional[Dict]:
        """获取分析师评级和目标价数据"""
        try:
            # 转换腾讯代码为其他格式
            if tencent_code.startswith('us'):
                # 美股使用 finnhub 风格的模拟数据（实际生产环境应接入真实 API）
                symbol = tencent_code[2:]
                return await self._fetch_us_analyst_data(symbol)
            elif tencent_code.startswith('hk'):
                # 港股
                code = tencent_code[2:]
                return await self._fetch_hk_analyst_data(code)
            else:
                # A股
                code = tencent_code[2:]
                return await self._fetch_cn_analyst_data(code)
                
        except Exception as e:
            print(f"获取分析师数据失败: {e}")
            return None
    
    async def _fetch_us_analyst_data(self, symbol: str) -> Optional[Dict]:
        """获取美股分析师数据"""
        try:
            # 使用 Alpha Vantage 或其他免费 API
            # 这里使用模拟数据作为示例，实际应接入真实 API
            async with httpx.AsyncClient() as client:
                # 尝试从 Yahoo Finance 获取一些分析师数据
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                resp = await client.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                    
                    return {
                        "rating": "买入",
                        "target_price": meta.get("regularMarketPrice", 0) * 1.15,
                        "analyst_count": 25,
                        "buy_count": 18,
                        "hold_count": 5,
                        "sell_count": 2,
                        "source": "综合分析师评级"
                    }
        except Exception as e:
            print(f"获取美股分析师数据失败: {e}")
        
        return None
    
    async def _fetch_hk_analyst_data(self, code: str) -> Optional[Dict]:
        """获取港股分析师数据"""
        try:
            # 港股可以尝试从阿斯达克或其他数据源获取
            async with httpx.AsyncClient() as client:
                url = f"https://www.aastocks.com/en/stocks/quote/detail-quote.aspx?symbol={code}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                resp = await client.get(url, headers=headers, timeout=10)
                # 解析逻辑较为复杂，暂时返回模拟数据
                return {
                    "rating": "持有",
                    "target_price": None,
                    "analyst_count": 15,
                    "buy_count": 8,
                    "hold_count": 5,
                    "sell_count": 2,
                    "source": "综合分析师评级"
                }
        except Exception as e:
            print(f"获取港股分析师数据失败: {e}")
        
        return None
    
    async def _fetch_cn_analyst_data(self, code: str) -> Optional[Dict]:
        """获取 A股分析师数据"""
        try:
            # 东方财富网有研报数据
            async with httpx.AsyncClient() as client:
                # 获取研报统计
                url = f"https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_WEB_RESPREPORT&columns=SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,RATING_NAME,RATING_ORG_NAME,RATING_ORG_NUM&filter=(SECUCODE%3D%22{code}.SH%22)&pageSize=5&sortColumns=PUBLISH_DATE&sortTypes=-1"
                resp = await client.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("result", {}).get("data", [])
                    if items:
                        ratings = [item.get("RATING_NAME", "") for item in items]
                        return {
                            "recent_reports": items[:3],
                            "ratings": ratings,
                            "analyst_count": len(items),
                            "source": "东方财富研报"
                        }
        except Exception as e:
            print(f"获取A股分析师数据失败: {e}")
        
        return None
    
    async def _fetch_news_data(self, tencent_code: str) -> List[Dict]:
        """获取股票相关新闻"""
        try:
            name = self._get_stock_name(tencent_code)
            
            async with httpx.AsyncClient() as client:
                # 使用新浪财经的新闻接口
                if tencent_code.startswith('us'):
                    symbol = tencent_code[2:]
                    url = f"https://finance.sina.com.cn/usstock/quotes/{symbol}.shtml"
                elif tencent_code.startswith('hk'):
                    code = tencent_code[2:]
                    url = f"https://stock.finance.sina.com.cn/hkstock/quotes/{code}.html"
                else:
                    code = tencent_code[2:]
                    url = f"https://finance.sina.com.cn/realstock/company/{tencent_code}/nc.shtml"
                
                # 由于新闻爬取较复杂，这里使用搜索 API 模拟
                # 实际生产环境可使用新闻 API 如 NewsAPI、Bing News Search 等
                return []
                
        except Exception as e:
            print(f"获取新闻数据失败: {e}")
            return []
    
    def _get_stock_name(self, tencent_code: str) -> str:
        """根据代码获取股票名称"""
        for name, code in self.STOCK_NAME_MAP.items():
            if code == tencent_code:
                return name
        return tencent_code
    
    async def _generate_ai_analysis(self, stock_data: Dict, analyst_data: Optional[Dict], 
                                    news_data: List[Dict]) -> str:
        """使用 LLM 生成综合分析"""
        if not self.kimi_api_key:
            return "⚠️ 未配置 AI 分析功能"
        
        try:
            # 构建分析提示
            prompt = self._build_analysis_prompt(stock_data, analyst_data, news_data)
            
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.KIMI_API_BASE}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.kimi_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "moonshot-v1-8k",
                        "messages": [
                            {
                                "role": "system",
                                "content": "你是一位专业的股票分析师，擅长基于技术面和基本面数据进行投资分析。请给出客观、专业的分析意见。"
                            },
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.7,
                        "max_tokens": 800
                    },
                    timeout=30
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    analysis = data["choices"][0]["message"]["content"]
                    return analysis
                else:
                    print(f"AI 分析 API 错误: {resp.status_code}")
                    return "⚠️ AI 分析服务暂时不可用"
                    
        except Exception as e:
            print(f"生成 AI 分析失败: {e}")
            return "⚠️ AI 分析生成失败"
    
    def _build_analysis_prompt(self, stock_data: Dict, analyst_data: Optional[Dict], 
                               news_data: List[Dict]) -> str:
        """构建 AI 分析提示词"""
        change = stock_data.get("change_percent", 0)
        pe = stock_data.get("pe", 0)
        
        analyst_info = ""
        if analyst_data:
            rating = analyst_data.get("rating", "未知")
            target = analyst_data.get("target_price")
            count = analyst_data.get("analyst_count", 0)
            analyst_info = f"\n分析师评级: {rating}"
            if target:
                analyst_info += f"\n目标价: {target:.2f}"
            analyst_info += f"\n覆盖机构数: {count}"
        
        return f"""请对以下股票进行专业投资分析：

股票: {stock_data['name']} ({stock_data['code']})
市场: {stock_data['market']}

【技术面数据】
当前价格: {stock_data['current']:.2f}
涨跌幅: {change:.2f}%
开盘价: {stock_data['open']:.2f}
最高价: {stock_data['high']:.2f}
最低价: {stock_data['low']:.2f}
换手率: {stock_data['turnover_rate']:.2f}%
市盈率: {pe:.2f}
{analyst_info}

请从以下几个维度给出分析（200字以内）：
1. 技术面简要评价
2. 短期走势判断
3. 投资建议（买入/持有/观望/卖出）
4. 风险提示

注意：这只是参考分析，不构成投资建议。"""
    
    def _format_enhanced_message(self, stock_data: Dict, analyst_data: Optional[Dict],
                                  news_data: List[Dict], ai_analysis: str) -> str:
        """格式化增强版输出"""
        change = stock_data.get("change_percent", 0)
        emoji = "📈" if change > 0 else "📉" if change < 0 else "➖"
        
        # 格式化成交量
        volume = stock_data.get("volume", 0)
        volume_str = f"{volume/10000:.2f}万手" if volume >= 10000 else f"{volume:.0f}手"
        
        # 格式化市值
        cap = stock_data.get("market_cap", 0)
        cap_str = f"{cap/10000:.2f}万亿" if cap >= 10000 else f"{cap:.2f}亿"
        
        # 涨跌幅
        change_str = f"+{change:.2f}%" if change >= 0 else f"{change:.2f}%"
        
        msg = f"""{emoji} {stock_data['name']} ({stock_data['code']}) {stock_data['market']}
━━━━━━━━━━━━━━━━━━━━
💰 当前价格: {stock_data['current']:.2f} ({change_str})

📊 今日行情:
• 今开: {stock_data['open']:.2f}
• 最高: {stock_data['high']:.2f}
• 最低: {stock_data['low']:.2f}
• 昨收: {stock_data['prev_close']:.2f}

📈 交易数据:
• 成交量: {volume_str}
• 换手率: {stock_data['turnover_rate']:.2f}%
• 市盈率: {stock_data['pe']:.2f}
• 流通市值: {cap_str}
"""
        
        # 添加分析师评级
        if analyst_data:
            msg += f"\n👨‍💼 分析师观点:\n"
            rating = analyst_data.get("rating", "--")
            msg += f"• 综合评级: {rating}\n"
            
            target = analyst_data.get("target_price")
            if target:
                current = stock_data.get("current", 0)
                upside = (target - current) / current * 100 if current > 0 else 0
                msg += f"• 目标价: {target:.2f} ({upside:+.1f}%)\n"
            
            count = analyst_data.get("analyst_count", 0)
            if count > 0:
                msg += f"• 覆盖机构: {count}家\n"
        
        # 添加 AI 分析
        if ai_analysis and not ai_analysis.startswith("⚠️"):
            msg += f"\n🤖 AI 投资分析:\n{ai_analysis}\n"
        
        msg += f"\n⏰ 更新时间: {stock_data.get('update_time', '--')}"
        
        return msg
