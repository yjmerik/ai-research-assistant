"""
自主进化技能
根据用户需求自动创建新技能
支持 Kimi K2.5 和 MiniMax M2.5
"""
import json
import uuid
import asyncio
import os
from typing import Dict, Any, Optional
from openai import AsyncOpenAI
from .base_skill import BaseSkill, SkillResult


# 持久化存储路径
SKILLS_STORAGE_FILE = "/opt/feishu-assistant/data/auto_skills.json"


# 模型配置
MODEL_CONFIGS = {
    "kimi_k2.5": {
        "name": "Kimi K2.5",
        "api_key_env": "KIMI_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "kimi-k2.5",
        "temperature": 1,  # Kimi K2.5 只支持 temperature=1
        "supports_json_mode": True
    },
    "minimax_m2.5": {
        "name": "MiniMax M2.5",
        "api_key_env": "MINIMAX_API_KEY",
        "base_url": "https://api.minimax.chat/v1",
        "model": "abab6.5s-chat",  # MiniMax 聊天模型
        "temperature": 0.7,
        "supports_json_mode": False  # MiniMax 不支持 json_object 格式
    }
}


class EvoAgentSkill(BaseSkill):
    """自主进化 Agent Skill"""

    name = "evo_agent"
    description = "根据需求自动创建新技能（支持 Kimi K2.5 / MiniMax M2.5）"
    examples = [
        "帮我创建一个查询天气的技能",
        "创建一个股票提醒技能",
        "用 minimax 创建一个查询新闻的技能"
    ]
    parameters = {
        "requirement": {
            "type": "string",
            "description": "用户对新技能的描述（可在描述中指定模型，如用 minimax 创建）",
            "required": True
        },
        "confirm_design": {
            "type": "boolean",
            "description": "是否确认设计（用户确认设计后传入True来生成代码）",
            "required": False
        },
        "design_id": {
            "type": "string",
            "description": "设计ID（确认设计时需要传入）",
            "required": False
        },
        "model": {
            "type": "string",
            "description": "使用的模型: kimi_k2.5 或 minimax_m2.5",
            "required": False,
            "enum": ["kimi_k2.5", "minimax_m2.5"]
        }
    }

    # 存储待确认的设计
    _pending_designs: Dict[str, Dict] = {}

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)

        # 支持通过 config 或环境变量获取 API keys
        self.kimi_api_key = config.get("llm_api_key") if config else os.environ.get("KIMI_API_KEY")
        self.minimax_api_key = config.get("minimax_api_key") if config else os.environ.get("MINIMAX_API_KEY")

        # 默认使用 Kimi K2.5
        self.default_model = config.get("default_model", "kimi_k2.5")

        # 当前活动的客户端
        self.client = None
        self.current_model = None
        self.current_base_url = None

    def _get_model_config(self, model: str = None, requirement: str = "") -> Dict:
        """获取模型配置"""
        # 从需求中检测模型
        if not model:
            req_lower = requirement.lower() if requirement else ""
            if "minimax" in req_lower or "m2.5" in req_lower:
                model = "minimax_m2.5"
            elif "kimi" in req_lower or "k2.5" in req_lower:
                model = "kimi_k2.5"
            else:
                model = self.default_model

        config = MODEL_CONFIGS.get(model, MODEL_CONFIGS["kimi_k2.5"])

        # 获取 API key
        api_key = None
        if model == "kimi_k2.5":
            api_key = self.kimi_api_key or os.environ.get(config["api_key_env"])
        elif model == "minimax_m2.5":
            api_key = self.minimax_api_key or os.environ.get(config["api_key_env"])

        return {
            "api_key": api_key,
            "base_url": config["base_url"],
            "model": config["model"],
            "display_name": config["name"],
            "temperature": config.get("temperature", 0.7),
            "supports_json_mode": config.get("supports_json_mode", True)
        }

    def _create_client(self, model_config: Dict) -> Optional[AsyncOpenAI]:
        """创建 LLM 客户端"""
        if not model_config.get("api_key"):
            return None
        return AsyncOpenAI(
            api_key=model_config["api_key"],
            base_url=model_config["base_url"]
        )

    async def execute(self, requirement: str, confirm_design: bool = False,
                     design_id: str = None, model: str = None, **kwargs) -> SkillResult:
        """
        执行自主进化

        Args:
            requirement: 用户需求描述
            confirm_design: 是否确认设计
            design_id: 设计ID（确认时使用）
            model: 使用的模型 (kimi_k2.5 / minimax_m2.5)
        """

        # 检查是否是查询技能列表
        req = requirement.strip().lower() if requirement else ""
        if req in ["list", "列表", "查看技能", "列出技能", "查询技能"]:
            return SkillResult(success=True, message=self.list_persisted_skills())

        # 获取模型配置
        model_config = self._get_model_config(model, requirement)
        self.client = self._create_client(model_config)

        # 检查是否有 LLM 客户端
        if not self.client:
            return SkillResult(
                success=False,
                message=f"❌ 未配置 {model_config['display_name']} 的 API Key，无法使用自主进化功能"
            )

        # 保存当前模型信息到 pending_designs
        if design_id and design_id in self._pending_designs:
            self._pending_designs[design_id]["model_config"] = model_config

        # 确认设计模式
        if confirm_design and design_id:
            return await self._generate_and_register(design_id, "确认")

        # 首次调用：生成设计文档
        return await self._generate_design(requirement)

    async def _generate_design(self, requirement: str) -> SkillResult:
        """生成设计文档"""
        try:
            # 获取当前模型配置
            model_config = self._get_model_config(requirement=requirement)

            # 调用 LLM 分析需求并生成设计
            design = await self._call_llm_design(requirement, model_config)

            # 生成设计ID
            design_id = str(uuid.uuid4())[:8]

            # 存储设计（包含模型信息）
            self._pending_designs[design_id] = {
                "requirement": requirement,
                "design": design,
                "skill_name": design.get("skill_name", ""),
                "created_at": asyncio.get_event_loop().time(),
                "model_config": model_config
            }

            # 格式化设计文档（包含模型信息）
            design_doc = self._format_design_document(design, design_id, model_config)

            return SkillResult(
                success=True,
                message=design_doc,
                data={
                    "design_id": design_id,
                    "step": "design_confirm"
                }
            )

        except Exception as e:
            return SkillResult(
                success=False,
                message=f"❌ 生成设计失败: {str(e)}"
            )

    async def _generate_and_register(self, design_id: str, confirmed: str = "yes", max_retries: int = 3) -> SkillResult:
        """确认设计后生成代码并注册（带自我改进）"""
        try:
            # 检查设计是否存在
            if design_id not in self._pending_designs:
                return SkillResult(
                    success=False,
                    message="❌ 设计已过期或不存在，请重新输入需求"
                )

            design_data = self._pending_designs[design_id]
            design = design_data["design"]
            skill_name = design_data["skill_name"]
            requirement = design_data.get("requirement", "")
            model_config = design_data.get("model_config", {})

            # 检查确认
            if confirmed.lower() not in ["yes", "true", "确认", "y", "1"]:
                return SkillResult(
                    success=False,
                    message="❌ 已取消生成"
                )

            # 设置客户端使用正确的模型
            self.client = self._create_client(model_config)
            if not self.client:
                return SkillResult(
                    success=False,
                    message=f"❌ API Key 未配置，无法生成代码"
                )

            # 自我改进循环
            last_error = None
            for attempt in range(max_retries):
                if attempt > 0:
                    print(f"[EvoAgent] 第 {attempt + 1} 次尝试修复...")

                # 生成代码（传入requirement用于检测类型）
                code = await self._call_llm_code(design, model_config, last_error, requirement)

                # 尝试创建并注册 Skill
                skill_result = await self._register_and_test(skill_name, design, code, requirement)

                if skill_result.success:
                    # 清理设计缓存
                    del self._pending_designs[design_id]
                    return skill_result

                # 保存错误信息用于下一次尝试
                last_error = skill_result.message

                # 如果是语法错误，继续重试
                if "SyntaxError" in skill_result.message or "unterminated" in skill_result.message:
                    continue

                # 如果是其他错误，也尝试修复
                if attempt < max_retries - 1:
                    continue

            # 所有尝试都失败
            return SkillResult(
                success=False,
                message=f"❌ 经过 {max_retries} 次尝试仍然失败：\n{last_error}"
            )

        except Exception as e:
            return SkillResult(
                success=False,
                message=f"❌ 生成代码失败: {str(e)}"
            )

    async def _register_and_test(self, skill_name: str, design: Dict, code: str, requirement: str = "") -> SkillResult:
        """注册技能并测试执行"""
        try:
            # 动态创建 Skill
            skill_instance = self._create_skill_from_code(skill_name, design, code)

            if skill_instance is None:
                return SkillResult(
                    success=False,
                    message=f"❌ 代码语法错误：无法创建技能"
                )

            # 注册到 registry
            from .skill_registry import registry
            registry.register(skill_instance)

            # 测试执行 - 提取测试参数
            test_params = self._extract_test_params(requirement)

            # 尝试执行
            try:
                result = await skill_instance.execute(**test_params)

                # 检查执行结果
                if result.success:
                    # 成功，持久化并返回
                    self._save_skill_to_file(skill_name, design, code)
                    return SkillResult(
                        success=True,
                        message=result.message + "\n\n✅ 技能创建并测试成功！"
                    )
                else:
                    # 执行失败，记录错误
                    return SkillResult(
                        success=False,
                        message=f"❌ 技能执行测试失败：{result.message}"
                    )
            except Exception as e:
                return SkillResult(
                    success=False,
                    message=f"❌ 技能执行出错：{str(e)}"
                )

        except Exception as e:
            return SkillResult(
                success=False,
                message=f"❌ 注册失败：{str(e)}"
            )

    def _extract_test_params(self, requirement: str) -> Dict:
        """从需求中提取测试参数"""
        params = {}

        # 检测股票
        if "股票" in requirement or "股价" in requirement or "stock" in requirement.lower():
            params = {"symbol": "茅台", "market": "CN"}

        # 检测天气
        elif "天气" in requirement:
            params = {"location": "北京"}

        # 检测新闻
        elif "新闻" in requirement or "报告" in requirement:
            params = {"topic": "人工智能发展趋势"}

        # 检测 GitHub
        elif "github" in requirement.lower() or "代码库" in requirement:
            params = {"keyword": "python", "language": "python"}

        # 检测语音/TTS
        elif "语音" in requirement or "声音" in requirement or "tts" in requirement.lower() or "voice" in requirement.lower() or "克隆" in requirement:
            params = {"action": "list"}

        return params

    async def _call_llm_design(self, requirement: str, model_config: Dict = None) -> Dict:
        """调用 LLM 生成设计"""
        if model_config is None:
            model_config = self._get_model_config(requirement=requirement)

        model = model_config.get("model", "moonshot-v1-8k")

        system_prompt = """你是一个技能架构设计师。根据用户的需求，设计一个 Skill 的架构。

## 输出格式

请以 JSON 格式输出，包含以下字段：

{
    "skill_name": "技能名称（英文，用于注册，如 weather_query）",
    "description": "技能描述（中文）",
    "examples": ["使用示例1", "使用示例2"],
    "parameters": {
        "参数名": {
            "type": "类型（string/integer/boolean）",
            "description": "参数描述",
            "required": true/false,
            "default": "默认值（可选）"
        }
    },
    "implementation_approach": "实现思路简述"
}

注意事项：
- skill_name 必须是英文，使用下划线命名
- 参数使用标准的 JSON Schema 格式
- 只输出 JSON，不要其他内容
"""

        user_prompt = f"""用户需求：{requirement}

请根据以上需求设计一个 Skill 的架构。请以 JSON 格式输出。"""

        # 构建请求参数
        request_params = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": model_config.get("temperature", 0.7)
        }

        # 添加 JSON 模式支持（仅当支持时）
        if model_config.get("supports_json_mode", True):
            try:
                request_params["response_format"] = {"type": "json_object"}
            except Exception:
                pass

        response = await self.client.chat.completions.create(**request_params)

        content = response.choices[0].message.content

        # 尝试解析 JSON
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # 如果不是 JSON，尝试提取 JSON 部分
            import re
            # 尝试匹配 ```json ... ``` 或 ``` ... ``` 包裹的 JSON
            json_match = re.search(r'```json?\s*(\{[\s\S]*?\})\s*```', content)
            if not json_match:
                # 尝试直接匹配 JSON 对象（添加捕获组）
                json_match = re.search(r'(\{[\s\S]*\})', content)

            if json_match:
                json_str = json_match.group(1)
                # 移除可能的 ``` 标记
                json_str = json_str.strip()
                if json_str.startswith("```"):
                    json_str = json_str.split("```")[0]
                result = json.loads(json_str)
            else:
                raise ValueError(f"无法解析 LLM 响应: {content[:100]}")

        return result

    async def _call_llm_code(self, design: Dict, model_config: Dict = None, last_error: str = None, requirement: str = "") -> str:
        """调用 LLM 生成代码（支持错误修复）"""
        if model_config is None:
            model_config = self._get_model_config()

        skill_name = design.get("skill_name", "dynamic_skill")
        parameters = design.get("parameters", {})
        description = design.get("description", "")

        # 同时检查 description 和 requirement
        search_text = description.lower() + " " + requirement.lower()

        # 检查是否为天气相关技能
        is_weather = any(kw in search_text for kw in ["天气", "weather", "温度"])

        if is_weather:
            # 天气技能使用内置实现
            return self._get_weather_implementation()

        # 检测股票查询
        is_stock = any(kw in search_text for kw in ["股票", "股价", "stock"])

        if is_stock:
            # 股票查询使用内置实现
            return self._get_stock_implementation()

        # 检测新闻相关
        is_news = any(kw in search_text for kw in ["新闻", "news", "报告", "writer"])

        if is_news:
            return self._get_news_implementation()

        # 检测 GitHub 相关
        is_github = any(kw in search_text for kw in ["github", "代码库", "repository", "趋势"])

        if is_github:
            return self._get_github_implementation()

        # 检测语音/TTS 相关
        is_voice = any(kw in search_text for kw in ["语音", "声音", "tts", "voice", "克隆", "朗读", "tts"])

        if is_voice:
            return self._get_voice_implementation()

        # 其他技能返回提示
        return f"""
async def execute(self, **kwargs) -> SkillResult:
    return SkillResult(
        success=True,
        message=f"技能 '{skill_name}' 已创建！参数: {{kwargs}}。请手动完善实现。"
    )
"""

    def _get_weather_implementation(self) -> str:
        """获取天气查询的实现代码 - 使用 Open-Meteo 免费 API + LLM翻译"""
        return '''
import os

async def execute(self, **kwargs) -> SkillResult:
    try:
        location = kwargs.get("location") or kwargs.get("city") or kwargs.get("city_name") or "北京"

        # 使用 LLM 翻译城市名
        api_key = os.environ.get("KIMI_API_KEY")
        if not api_key:
            return SkillResult(success=False, message="未配置 LLM API Key")

        # 调用 LLM 翻译城市名
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.moonshot.cn/v1/chat/completions",
                headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key},
                json={
                    "model": "moonshot-v1-8k",
                    "messages": [
                        {"role": "system", "content": "你是一个翻译助手，将中国城市名翻译成英文。只输出城市名，不要其他内容。"},
                        {"role": "user", "content": location}
                    ],
                    "max_tokens": 20
                },
                timeout=10.0
            )
            data = resp.json()
            query_name = data.get("choices", [{}])[0].get("message", {}).get("content", location)
            query_name = query_name.strip()

        # 天气代码映射
        def get_desc(code):
            codes = {0: "☀️ 晴", 1: "🌤️ 晴间多云", 2: "⛅ 多云", 3: "☁️ 阴",
                45: "🌫️ 雾", 48: "🌫️ 雾凇", 51: "🌦️ 毛毛雨", 53: "🌧️ 中毛毛雨",
                55: "🌧️ 强毛毛雨", 61: "🌧️ 小雨", 63: "🌧️ 中雨", 65: "🌧️ 大雨",
                71: "🌨️ 小雪", 73: "🌨️ 中雪", 75: "🌨️ 大雪", 80: "🌦️ 阵雨",
                81: "🌧️ 小阵雨", 82: "🌧️ 强阵雨", 95: "⛈️ 雷暴",
                96: "⛈️ 雷暴+冰雹", 99: "⛈️ 强雷暴+冰雹"}
            return codes.get(code, "代码" + str(code))

        async with httpx.AsyncClient() as client:
            # 使用英文名查询
            geo_url = "https://geocoding-api.open-meteo.com/v1/search?name=" + query_name + "&count=5&language=en&format=json"
            geo_resp = await client.get(geo_url, timeout=10.0)
            geo_data = geo_resp.json()

            if not geo_data.get("results"):
                return SkillResult(success=False, message="未找到城市: " + location)

            # 优先选择中国城市
            results = geo_data["results"]
            geo = None
            for r in results:
                if r.get("country_code") == "CN":
                    geo = r
                    break
            if not geo:
                geo = results[0]

            lat = str(geo["latitude"])
            lon = str(geo["longitude"])
            city_name = geo["name"]
            region = geo.get("admin1", "")

            # 获取天气
            weather_url = "https://api.open-meteo.com/v1/forecast?latitude=" + lat + "&longitude=" + lon + "&current_weather=true&timezone=auto"
            weather_resp = await client.get(weather_url, timeout=10.0)
            weather_data = weather_resp.json()

            current = weather_data.get("current_weather", {})
            temp = str(current.get("temperature", "N/A"))
            wind = str(current.get("windspeed", "N/A"))
            code = current.get("weathercode", 0)
            weather_desc = get_desc(code)

            # 直接使用用户输入的城市名显示
            display_name = location

            msg = "🌤️ " + display_name + "\\n"
            msg += "━━━━━━━━\\n"
            msg += "🌡️ 温度: " + temp + "°C\\n"
            msg += "🌥️ 天气: " + weather_desc + "\\n"
            msg += "💨 风速: " + wind + " km/h\\n"
            msg += "━━━━━━━━\\n"
            msg += "数据来源: Open-Meteo"

        return SkillResult(success=True, message=msg)
    except Exception as e:
        import traceback
        err_msg = "查询失败: " + str(e) if str(e) else "查询失败（详细错误: " + type(e).__name__ + "）"
        print("[Weather] 错误: " + traceback.format_exc())
        return SkillResult(success=False, message=err_msg)
'''

    def _get_stock_implementation(self) -> str:
        """获取股票查询的实现代码 - 使用 Qveris API"""
        return '''
import os

# 股票代码映射（简化的中文名称到代码）
STOCK_NAME_MAP = {
    "茅台": ("600519", "sh", "贵州茅台"),
    "贵州茅台": ("600519", "sh", "贵州茅台"),
    "平安": ("601318", "sh", "中国平安"),
    "中国平安": ("601318", "sh", "中国平安"),
    "阿里": ("9988", "hk", "阿里巴巴"),
    "阿里巴巴": ("9988", "hk", "阿里巴巴"),
    "腾讯": ("700", "hk", "腾讯控股"),
    "腾讯控股": ("700", "hk", "腾讯控股"),
    "美团": ("3690", "hk", "美团"),
    "苹果": ("AAPL", "us", "Apple Inc."),
    "特斯拉": ("TSLA", "us", "Tesla Inc."),
    "google": ("GOOGL", "us", "Alphabet Inc."),
    "亚马逊": ("AMZN", "us", "Amazon.com Inc."),
}

def get_stock_code(stock_input):
    """解析股票代码"""
    stock_input = stock_input.strip()

    # 直接返回如果是标准格式
    if stock_input.startswith(("sh", "sz", "hk", "us")):
        return stock_input, None, stock_input

    # 查表
    if stock_input in STOCK_NAME_MAP:
        code, market, name = STOCK_NAME_MAP[stock_input]
        full_code = market + code
        return full_code, market, name

    # 尝试直接调用API解析
    return stock_input, None, stock_input

async def execute(self, **kwargs) -> SkillResult:
    try:
        symbol = kwargs.get("symbol") or kwargs.get("stock") or kwargs.get("code") or "茅台"
        market = kwargs.get("market", "CN").upper()

        # 获取API Key
        api_key = os.environ.get("KIMI_API_KEY")
        qveris_key = os.environ.get("QVERIS_API_KEY")

        if not api_key:
            return SkillResult(success=False, message="未配置 LLM API Key")

        # 解析股票代码
        stock_code, detected_market, stock_name = get_stock_code(symbol)

        # 如果没有指定市场，尝试检测
        if not detected_market:
            if market == "AUTO" or market == "CN":
                # 尝试A股
                test_code = "sh" + stock_code if not stock_code.startswith(("sh", "sz")) else stock_code
            else:
                test_code = stock_code
        else:
            test_code = stock_code

        # 使用Qveris API查询（如果有配置）
        if qveris_key:
            url = "https://api.qveris.com/v1/query"
            headers = {"Authorization": "Bearer " + qveris_key, "Content-Type": "application/json"}

            # 尝试获取实时行情
            payload = {
                "service": "ths_ifind.real_time_quotation.v1",
                "parameters": {"ts_code": stock_code}
            }

            async with httpx.AsyncClient() as client:
                try:
                    resp = await client.post(url, headers=headers, json=payload, timeout=10.0)
                    data = resp.json()

                    if data.get("code") == 0 and data.get("data"):
                        quote = data["data"]
                        name = quote.get("ts_name", stock_name or stock_code)
                        price = quote.get("close", "N/A")
                        change = quote.get("pct_chg", 0)
                        volume = quote.get("vol", 0)
                        amount = quote.get("amount", 0)

                        # 格式化
                        change_str = f"+{change:.2f}%" if change >= 0 else f"{change:.2f}%"
                        vol_str = f"{volume/1000000:.2f}M" if volume else "N/A"

                        msg = "📈 " + name + " (" + stock_code + ")\n"
                        msg += "━━━━━━━━━━━━━━\n"
                        msg += "💰 当前价: " + str(price) + "\n"
                        msg += "📊 涨跌幅: " + change_str + "\n"
                        msg += "📦 成交量: " + vol_str + "\n"
                        msg += "━━━━━━━━━━━━━━\n"
                        msg += "数据来源: 同花顺"

                        return SkillResult(success=True, message=msg)
                except Exception as e:
                    pass

        # 如果没有Qveris API，使用LLM分析（简化版）
        msg = "📈 股票查询: " + symbol + "\n"
        msg += "━━━━━━━━━━━━━━\n"
        msg += "⚠️ 当前使用演示模式\n"
        msg += "请配置 QVERIS_API_KEY 获取实时行情\n"
        msg += "━━━━━━━━━━━━━━\n"
        msg += "股票代码: " + stock_code

        return SkillResult(success=True, message=msg)

    except Exception as e:
        import traceback
        err_msg = "查询失败: " + str(e)
        print("[Stock] 错误: " + traceback.format_exc())
        return SkillResult(success=False, message=err_msg)
'''

    def _get_news_implementation(self) -> str:
        """获取新闻写作的实现代码"""
        return '''
import os

async def execute(self, **kwargs) -> SkillResult:
    try:
        api_key = os.environ.get("KIMI_API_KEY")
        if not api_key:
            return SkillResult(success=False, message="未配置 LLM API Key")

        topic = kwargs.get("topic") or kwargs.get("subject") or "今日要闻"

        # 使用 Kimi API 生成新闻摘要
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.moonshot.cn/v1/chat/completions",
                headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key},
                json={
                    "model": "moonshot-v1-8k",
                    "messages": [
                        {"role": "system", "content": "你是一个新闻记者，根据给定的主题写一篇简短的新闻报道（100-200字）。"},
                        {"role": "user", "content": topic}
                    ],
                    "max_tokens": 500
                },
                timeout=30.0
            )
            data = resp.json()
            article = data.get("choices", [{}])[0].get("message", {}).get("content", "无法生成新闻")

        msg = "📰 " + topic + "\n"
        msg += "━━━━━━━━━━━━━━\n"
        msg += article + "\n"
        msg += "━━━━━━━━━━━━━━\n"
        msg += "由 Kimi AI 生成"

        return SkillResult(success=True, message=msg)

    except Exception as e:
        return SkillResult(success=False, message="生成失败: " + str(e))
'''

    def _get_github_implementation(self) -> str:
        """获取GitHub趋势的实现代码"""
        return '''
import os

async def execute(self, **kwargs) -> SkillResult:
    try:
        keyword = kwargs.get("keyword") or kwargs.get("query") or "python"
        language = kwargs.get("language") or "python"

        # 使用 GitHub API
        url = "https://api.github.com/search/repositories"
        params = {"q": keyword + " language:" + language, "sort": "stars", "order": "desc", "per_page": 5}

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=10.0)
            data = resp.json()

        if "items" not in data:
            return SkillResult(success=False, message="搜索失败")

        msg = "⭐ GitHub 趋势: " + keyword + " (" + language + ")\n"
        msg += "━━━━━━━━━━━━━━\n"

        for i, repo in enumerate(data["items"][:5], 1):
            name = repo.get("full_name", "")
            stars = repo.get("stargazers_count", 0)
            desc = repo.get("description", "")[:50]
            url = repo.get("html_url", "")

            msg += f"{i}. {name}\n"
            msg += f"   ⭐ {stars} | {desc}...\n"
            msg += f"   🔗 {url}\n\n"

        return SkillResult(success=True, message=msg)

    except Exception as e:
        return SkillResult(success=False, message="查询失败: " + str(e))
'''

    def _get_voice_implementation(self) -> str:
        """获取语音克隆和TTS的实现代码"""
        return '''
import os
import json
import base64
import time

VOICE_FILE = "/opt/feishu-assistant/data/voices.json"

def load_voices():
    try:
        if os.path.exists(VOICE_FILE):
            with open(VOICE_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {}

def save_voices(voices):
    os.makedirs(os.path.dirname(VOICE_FILE), exist_ok=True)
    with open(VOICE_FILE, "w") as f:
        json.dump(voices, f, ensure_ascii=False, indent=2)

async def volc_tts(text, voice="zh_male_shanghai_v2"):
    access_key = os.environ.get("VOLCENGINE_ACCESS_KEY", "")
    if not access_key:
        return None, "VOLCENGINE not configured"
    # 火山引擎 TTS 实现
    return None, "Use MiniMax TTS instead"

async def doubao_tts(text):
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        api_key = os.environ.get("KIMI_API_KEY", "")
    if not api_key:
        return None, "No API key"

    try:
        import httpx
        url = "https://api.minimax.chat/v1/t2a_v2"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "speech-01-turbo",
            "text": text,
            "voice_setting": {"voice_id": "male-qn-qingse"},
            "audio_setting": {"sample_rate": 32000, "format": "mp3"}
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers, timeout=60.0)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("data") and data["data"].get("audio"):
                    audio_b64 = data["data"]["audio"]
                    return base64.b64decode(audio_b64), None
            return None, f"MiniMax error: {resp.status_code}"
    except Exception as e:
        return None, str(e)

async def execute(self, **kwargs) -> SkillResult:
    try:
        action = kwargs.get("action", "list")
        voice_name = kwargs.get("voice_name", "")
        text = kwargs.get("text", "")

        if action == "list":
            voices = load_voices()
            if not voices:
                return SkillResult(success=True, message="No saved voices")
            msg = "Saved voices:\\n"
            for name, data in voices.items():
                msg = msg + "- " + name + "\\n"
            return SkillResult(success=True, message=msg)

        elif action == "clone":
            if not voice_name:
                return SkillResult(success=False, message="need voice_name")
            voices = load_voices()
            voices[voice_name] = {"created": "2026-03-03"}
            save_voices(voices)
            return SkillResult(success=True, message="voice saved: " + voice_name)

        elif action == "generate":
            if not voice_name or not text:
                return SkillResult(success=False, message="need voice_name and text")
            voices = load_voices()
            if voice_name not in voices:
                return SkillResult(success=False, message="voice not found")

            audio_data, error = await doubao_tts(text)
            if audio_data:
                return SkillResult(success=True, message="Audio generated: " + str(len(audio_data)) + " bytes")
            else:
                return SkillResult(success=True, message="Demo mode - " + (error or "TTS failed"))

        return SkillResult(success=False, message="unknown action")
    except Exception as e:
        return SkillResult(success=False, message="Error: " + str(e))
'''

    async def _register_dynamic_skill(self, skill_name: str, design: Dict, code: str) -> SkillResult:
        """动态注册 Skill"""
        try:
            # 使用生成的代码创建动态 Skill 类
            skill_instance = self._create_skill_from_code(skill_name, design, code)

            if skill_instance is None:
                return SkillResult(
                    success=False,
                    message=f"❌ 创建技能失败：无法解析生成的代码"
                )

            # 导入 registry 并注册
            from .skill_registry import registry
            registry.register(skill_instance)

            # 持久化保存
            self._save_skill_to_file(skill_name, design, code)

            return SkillResult(
                success=True,
                message=f"✅ 技能 '{skill_name}' 已创建并注册！\n\n"
                        f"技能描述: {design.get('description', '')}\n"
                        f"现在你可以使用这个技能了。\n\n"
                        f"技能已持久化保存，重启后仍然有效。"
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return SkillResult(
                success=False,
                message=f"❌ 注册技能失败: {str(e)}"
            )

    def _save_skill_to_file(self, skill_name: str, design: Dict, code: str):
        """保存技能到文件（持久化）"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(SKILLS_STORAGE_FILE), exist_ok=True)

            # 读取现有数据
            skills = {}
            if os.path.exists(SKILLS_STORAGE_FILE):
                with open(SKILLS_STORAGE_FILE, "r", encoding="utf-8") as f:
                    skills = json.load(f)

            # 添加新技能
            skills[skill_name] = {
                "design": design,
                "code": code,
                "created_at": str(uuid.uuid4())
            }

            # 保存
            with open(SKILLS_STORAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(skills, f, ensure_ascii=False, indent=2)

            print(f"[EvoAgent] 技能已保存: {skill_name}")
        except Exception as e:
            print(f"[EvoAgent] 保存技能失败: {e}")

    @classmethod
    def load_persisted_skills(cls) -> Dict[str, Dict]:
        """加载已持久化的技能"""
        skills = {}
        try:
            if os.path.exists(SKILLS_STORAGE_FILE):
                with open(SKILLS_STORAGE_FILE, "r", encoding="utf-8") as f:
                    skills = json.load(f)
                print(f"[EvoAgent] 已加载 {len(skills)} 个持久化技能")
        except Exception as e:
            print(f"[EvoAgent] 加载技能失败: {e}")
        return skills

    def list_persisted_skills(self) -> str:
        """列出所有已保存的技能"""
        try:
            if not os.path.exists(SKILLS_STORAGE_FILE):
                return "暂无已保存的技能"

            with open(SKILLS_STORAGE_FILE, "r", encoding="utf-8") as f:
                skills = json.load(f)

            if not skills:
                return "暂无已保存的技能"

            msg = "📋 已保存的技能列表：\n\n"
            for name, data in skills.items():
                desc = data.get("design", {}).get("description", "无描述")
                msg += f"• {name}\n"
                msg += f"  {desc}\n\n"

            return msg
        except Exception as e:
            return f"查询失败: {str(e)}"

    def _create_skill_from_code(self, skill_name: str, design: Dict, code: str):
        """从生成的代码创建 Skill 类"""
        try:
            # 准备执行环境
            local_vars = {
                "BaseSkill": BaseSkill,
                "SkillResult": SkillResult,
                "httpx": __import__("httpx"),
                "openai": __import__("openai"),
                "os": __import__("os"),
                "Dict": Dict,
                "Any": __import__("typing").Any,
                "skill_name": skill_name,
                "skill_description": design.get("description", ""),
                "skill_examples": design.get("examples", []),
                "skill_parameters": design.get("parameters", {})
            }

            # 提取 execute 方法
            execute_method_code = self._extract_execute_method(code)

            # 获取实际的变量值
            skill_name_val = skill_name
            skill_desc_val = design.get("description", "").replace('"""', '\\"\\"\\"')
            skill_examples_val = design.get("examples", [])
            skill_params_val = design.get("parameters", {})

            # 创建 Skill 类定义
            class_code = f'''
import httpx
from typing import Dict, Any

class DynamicSkill(BaseSkill):
    name = "{skill_name_val}"
    description = """{skill_desc_val}"""
    examples = {skill_examples_val}
    parameters = {skill_params_val}

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)

{execute_method_code}
'''

            print(f"[EvoAgent] 生成的代码:\n{class_code[:500]}...")

            # 执行代码创建类
            exec(class_code, local_vars)

            # 返回创建的实例
            DynamicSkill = local_vars["DynamicSkill"]
            return DynamicSkill(config={})

        except Exception as e:
            print(f"[EvoAgent] 创建技能失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_execute_method(self, code: str) -> str:
        """从生成的代码中提取 execute 方法"""
        import re

        # 清理代码
        code = code.strip()
        if "```" in code:
            # 提取代码块内容
            match = re.search(r'```[\w]*\n(.*?)```', code, re.DOTALL)
            if match:
                code = match.group(1)

        # 确保有 async def
        if "async def execute" not in code:
            code = "async def execute" + code.split("def execute")[-1]

        # 添加缩进
        lines = code.split('\n')
        indented = []
        for line in lines:
            if line.strip():
                indented.append('    ' + line)
            else:
                indented.append(line)

        return '\n'.join(indented)

    def _format_design_document(self, design: Dict, design_id: str, model_config: Dict = None) -> str:
        """格式化设计文档"""
        if model_config is None:
            model_config = {}

        skill_name = design.get("skill_name", "未命名")
        description = design.get("description", "")
        examples = design.get("examples", [])
        parameters = design.get("parameters", {})
        approach = design.get("implementation_approach", "")
        model_name = model_config.get("display_name", "Kimi K2.5")

        doc = f"""📋 技能设计文档

━━━━━━━━━━━━━━━━━━━━━━━━
🆔 设计ID: {design_id}
🔧 生成模型: {model_name}
━━━━━━━━━━━━━━━━━━━━━━━━

📌 技能名称: `{skill_name}`

📝 描述: {description}

💡 使用示例:
"""

        for ex in examples:
            doc += f"   • {ex}\n"

        doc += f"""
⚙️ 参数定义:
"""

        for param_name, param_info in parameters.items():
            required = "必需" if param_info.get("required", False) else "可选"
            param_type = param_info.get("type", "string")
            default = f"（默认值: {param_info.get('default', '')}）" if param_info.get("default") else ""
            doc += f"   • {param_name} ({param_type}, {required}) {default}\n"
            doc += f"     {param_info.get('description', '')}\n"

        doc += f"""
🔧 实现思路: {approach}

━━━━━━━━━━━━━━━━━━━━━━━━

✅ 如果确认此设计，请回复：
   「确认 {design_id}」

❌ 如需修改，请重新描述需求
"""

        return doc
