"""
技能基类定义
所有技能都需要继承此类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class SkillResult:
    """技能执行结果"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    card_content: Optional[Dict] = None  # 飞书卡片格式
    

class BaseSkill(ABC):
    """技能基类"""
    
    # 技能元数据
    name: str = "base_skill"
    description: str = "基础技能描述"
    examples: list = []  # 使用示例
    parameters: Dict[str, Any] = {}  # 参数定义
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化技能
        
        Args:
            config: 技能配置，如 API keys 等
        """
        self.config = config or {}
    
    @abstractmethod
    async def execute(self, **kwargs) -> SkillResult:
        """
        执行技能
        
        Args:
            **kwargs: 技能参数
            
        Returns:
            SkillResult: 执行结果
        """
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """
        获取技能的 JSON Schema，用于大模型理解
        """
        return {
            "name": self.name,
            "description": self.description,
            "examples": self.examples,
            "parameters": {
                "type": "object",
                "properties": self.parameters,
                "required": [k for k, v in self.parameters.items() if v.get("required", False)]
            }
        }
    
    def validate_params(self, params: Dict[str, Any]) -> tuple[bool, str]:
        """
        验证参数
        
        Returns:
            (是否有效, 错误信息)
        """
        required = [k for k, v in self.parameters.items() if v.get("required", False)]
        for key in required:
            if key not in params or params[key] is None:
                return False, f"缺少必需参数: {key}"
        return True, ""
