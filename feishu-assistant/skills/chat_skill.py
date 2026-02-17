"""
通用对话技能
处理闲聊和通用对话
"""
from typing import Dict, Any
from .base_skill import BaseSkill, SkillResult


class ChatSkill(BaseSkill):
    """通用对话技能"""
    
    name = "chat"
    description = "通用对话和闲聊，回答用户的一般性问题"
    examples = [
        "你好",
        "今天天气怎么样",
        "帮我分析一下这个问题",
        "什么是人工智能"
    ]
    parameters = {
        "message": {
            "type": "string",
            "description": "用户的消息内容",
            "required": True
        }
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.llm_api_key = config.get("llm_api_key") if config else None
    
    async def execute(self, message: str, **kwargs) -> SkillResult:
        """
        执行对话
        
        Args:
            message: 用户消息
        """
        try:
            # 这里可以接入大模型进行对话
            # 目前先返回帮助信息
            
            response = self._generate_response(message)
            
            return SkillResult(
                success=True,
                message=response,
                data={"input": message}
            )
            
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"对话处理失败: {str(e)}"
            )
    
    def _generate_response(self, message: str) -> str:
        """生成回复"""
        msg_lower = message.lower()
        
        # 简单的规则匹配
        if any(kw in msg_lower for kw in ["你好", "嗨", "hello", "hi"]):
            return "👋 你好！我是你的飞书 AI 助手，可以帮你查询市场、搜索 GitHub 项目或学术论文。发送 /help 查看所有功能！"
        
        if any(kw in msg_lower for kw in ["谢谢", "thanks", "thank you"]):
            return "😊 不客气！有需要随时叫我~"
        
        if any(kw in msg_lower for kw in ["帮助", "help", "怎么用"]):
            return """🤖 我可以帮你：

**查询信息：**
• 发送「查询今天的美股行情」→ 使用市场查询技能
• 发送「搜索 GitHub 上的 AI 项目」→ 使用 GitHub 搜索技能
• 发送「找一下关于 Transformer 的论文」→ 使用论文搜索技能

**快捷命令：**
• /market - 查询市场行情
• /github <关键词> - 搜索 GitHub
• /paper <主题> - 搜索论文

你也可以用自然语言描述你的需求，我会自动识别并执行！"""
        
        # 默认回复
        return f"🤖 收到: {message[:50]}...\n\n我可以帮你查询市场、搜索项目或论文。试试发送「/help」查看所有功能！"
