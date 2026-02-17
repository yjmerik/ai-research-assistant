"""
意图识别器
使用大模型理解用户意图并规划技能调用
"""
import json
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
                temperature=0.3,  # 较低的创造性，更确定性的输出
                response_format={"type": "json_object"}
            )
            
            # 解析结果
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
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
            skills_desc.append(desc)
        
        skills_text = "\n".join(skills_desc)
        
        return f"""你是一个智能助手，负责理解用户意图并选择合适的技能来执行。

## 可用技能

{skills_text}

## 任务

1. 分析用户的输入，理解其真实意图
2. 选择最合适的技能（skill 字段）
3. 提取执行该技能所需的参数（parameters 字段）
4. 如果用户的请求不明确或需要多个步骤，进行合理的规划

## 输出格式

请以 JSON 格式输出：

{{
    "intent": "意图描述",
    "skill": "选择的技能名称",
    "parameters": {{
        "参数名": "参数值"
    }},
    "confidence": 0.95,
    "reasoning": "为什么选择这个技能",
    "follow_up": "可选，如果需要进一步确认或提供建议"
}}

注意：
- skill 必须是可用技能列表中的名称
- parameters 必须匹配技能的参数定义
- confidence 是置信度（0-1）
"""
    
    def _build_user_prompt(self, user_input: str, context: Dict[str, Any] = None) -> str:
        """构建用户提示词"""
        prompt = f"用户输入: {user_input}\n\n"
        
        if context and context.get("history"):
            prompt += "对话历史:\n"
            for msg in context["history"][-3:]:  # 只保留最近3轮
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:100]
                prompt += f"{role}: {content}\n"
            prompt += "\n"
        
        prompt += "请分析用户意图并输出 JSON 格式的执行计划。"
        
        return prompt
    
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
