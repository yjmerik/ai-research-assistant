"""
意图识别器
使用大模型理解用户意图并规划技能调用
"""
import json
import re
from typing import Dict, List, Any, Optional
from openai import AsyncOpenAI


class IntentRecognizer:
    """意图识别器"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.moonshot.cn/v1"):
        """
        初始化
        
        Args:
            api_key: Kimi/Moonshot API Key
            base_url: API 基础 URL
        """
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = "moonshot-v1-8k"
    
    async def recognize(self, user_input: str, skills_schema: List[Dict], 
                       context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        识别用户意图并规划技能调用
        
        Args:
            user_input: 用户输入
            skills_schema: 所有技能的 schema
            context: 对话上下文
            
        Returns:
            规划结果，包含要调用的技能和参数
        """
        try:
            # 构建系统提示词
            system_prompt = self._build_system_prompt(skills_schema)
            
            # 构建用户提示词
            user_prompt = self._build_user_prompt(user_input, context)
            
            # 调用大模型
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # 解析结果
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            # 后处理：参数标准化
            result = self._normalize_parameters(result)
            
            return self._validate_result(result, skills_schema)
            
        except Exception as e:
            print(f"意图识别失败: {e}")
            # 失败时返回通用对话技能
            return {
                "intent": "chat",
                "skill": "chat",
                "parameters": {"message": user_input},
                "confidence": 0.5,
                "reasoning": f"识别失败，使用默认对话: {str(e)}"
            }
    
    def _build_system_prompt(self, skills_schema: List[Dict]) -> str:
        """构建系统提示词"""
        
        # 格式化技能列表
        skills_desc = []
        for skill in skills_schema:
            desc = f"- {skill['name']}: {skill['description']}"
            if skill.get('examples'):
                desc += f"\n  示例: {', '.join(skill['examples'][:2])}"
            
            # 添加参数说明和映射规则
            if skill.get('parameters'):
                params = skill['parameters'].get('properties', {})
                desc += "\n  参数映射规则:"
                for param_name, param_info in params.items():
                    enum_vals = param_info.get('enum', [])
                    mapping = param_info.get('mapping', {})
                    if mapping:
                        desc += f"\n    - {param_name}: "
                        mapping_strs = []
                        for standard_val, aliases in mapping.items():
                            mapping_strs.append(f"{standard_val}({', '.join(aliases)})")
                        desc += ", ".join(mapping_strs)
            
            skills_desc.append(desc)
        
        skills_text = "\n".join(skills_desc)
        
        return f"""你是一个智能助手，负责理解用户意图并选择合适的技能来执行。

## 可用技能

{skills_text}

## 任务

1. 分析用户的输入，理解其真实意图
2. 选择最合适的技能（skill 字段）
3. 提取执行该技能所需的参数（parameters 字段）
4. **重要**: 将用户的自然语言参数转换为技能要求的标准参数格式
   - 市场参数: "美股/美国/纳斯达克" → "US", "港股/香港/港交所" → "HK", "A股/中国/上证" → "CN"
   - GitHub搜索: "AI项目" → "ai-agent", "机器学习" → "machine-learning"

## 股票查询特殊说明

当用户询问股票时，提取股票名称或代码作为 `symbol` 参数：
- "茅台股票怎么样" → symbol: "茅台"
- "查询AAPL股价" → symbol: "AAPL"
- "微软股票" → symbol: "微软"
- "腾讯控股如何" → symbol: "腾讯"

不要尝试猜测市场，让技能自动识别（使用 AUTO）。

## 输出格式

请以 JSON 格式输出：

{{
    "intent": "意图描述",
    "skill": "选择的技能名称",
    "parameters": {{
        "参数名": "标准化后的参数值"
    }},
    "confidence": 0.95,
    "reasoning": "为什么选择这个技能以及如何映射参数的"
}}

注意：
- skill 必须是可用技能列表中的名称
- parameters 必须符合技能的参数定义（使用标准化的值，不是原始输入）
- confidence 是置信度（0-1）
- 参数值必须是技能接受的枚举值或格式
- **关键**: 股票查询时，symbol 参数必须包含股票名称或代码
"""
    
    def _build_user_prompt(self, user_input: str, context: Dict[str, Any] = None) -> str:
        """构建用户提示词"""
        prompt = f"用户输入: {user_input}\n\n"
        
        if context and context.get("history"):
            prompt += "对话历史:\n"
            for msg in context["history"][-3:]:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:100]
                prompt += f"{role}: {content}\n"
            prompt += "\n"
        
        prompt += "请分析用户意图并输出 JSON 格式的执行计划。注意将自然语言参数转换为标准格式（如'美股'转为'US'）。"
        
        return prompt
    
    def _normalize_parameters(self, result: Dict) -> Dict:
        """标准化参数值"""
        parameters = result.get("parameters", {})
        
        # 市场参数标准化
        if "market" in parameters:
            market = str(parameters["market"]).upper()
            # 映射表（支持多种常见说法）
            market_mapping = {
                # 美股
                "美股": "US", "美国": "US", "美": "US", "US": "US",
                "美股市场": "US", "纳斯达克": "US", "纽交所": "US",
                "NYSE": "US", "NASDAQ": "US",
                # 港股
                "港股": "HK", "香港": "HK", "港": "HK", "HK": "HK",
                "港股市场": "HK", "港交所": "HK", "香港股市": "HK",
                # A股
                "A股": "CN", "中国股市": "CN", "上证": "CN", "深证": "CN", 
                "CN": "CN", "中国": "CN", "中": "CN",
                "A股市场": "CN", "沪市": "CN", "深市": "CN",
                "SHANGHAI": "CN", "SHENZHEN": "CN",
            }
            parameters["market"] = market_mapping.get(market, market)
        
        # 股票代码参数标准化 - 清理股票名称
        if "symbol" in parameters:
            symbol = str(parameters["symbol"]).strip()
            # 去除常见的后缀词
            suffixes = ["股票", "股价", "怎么样", "如何", "行情", "走势", "分析"]
            for suffix in suffixes:
                if symbol.endswith(suffix):
                    symbol = symbol[:-len(suffix)].strip()
            parameters["symbol"] = symbol
        
        # GitHub 搜索关键词标准化
        if "keywords" in parameters:
            keywords = parameters["keywords"]
            keyword_mapping = {
                "人工智能": "ai",
                "机器学习": "machine-learning",
                "深度学习": "deep-learning",
                "大模型": "llm large-language-model"
            }
            if keywords in keyword_mapping:
                parameters["keywords"] = keyword_mapping[keywords]
        
        result["parameters"] = parameters
        return result
    
    def _validate_result(self, result: Dict, skills_schema: List[Dict]) -> Dict:
        """验证并修正结果"""
        valid_skills = [s["name"] for s in skills_schema]
        
        # 检查技能名称是否有效
        skill_name = result.get("skill", "chat")
        if skill_name not in valid_skills:
            print(f"无效的技能名称: {skill_name}，使用默认 chat")
            result["skill"] = "chat"
            result["parameters"] = {"message": result.get("parameters", {}).get("message", "")}
        
        # 确保有 parameters
        if "parameters" not in result or not isinstance(result["parameters"], dict):
            result["parameters"] = {}
        
        # 确保有 confidence
        if "confidence" not in result:
            result["confidence"] = 0.8
        
        return result
