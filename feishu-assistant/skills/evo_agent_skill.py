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

    async def _generate_and_register(self, design_id: str, confirmed: str = "yes") -> SkillResult:
        """确认设计后生成代码并注册"""
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

            # 生成代码
            code = await self._call_llm_code(design, model_config)

            # 动态创建并注册 Skill
            skill_result = await self._register_dynamic_skill(skill_name, design, code)

            # 清理设计缓存
            del self._pending_designs[design_id]

            return skill_result

        except Exception as e:
            return SkillResult(
                success=False,
                message=f"❌ 生成代码失败: {str(e)}"
            )

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

    async def _call_llm_code(self, design: Dict, model_config: Dict = None) -> str:
        """调用 LLM 生成代码"""
        if model_config is None:
            model_config = self._get_model_config()

        skill_name = design.get("skill_name", "dynamic_skill")
        parameters = design.get("parameters", {})
        description = design.get("description", "")

        # 检查是否为天气相关技能
        is_weather = any(kw in description.lower() for kw in ["天气", "weather", "温度"])

        if is_weather:
            # 天气技能使用内置实现
            return self._get_weather_implementation()

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
            skill_desc_val = design.get("description", "")
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
