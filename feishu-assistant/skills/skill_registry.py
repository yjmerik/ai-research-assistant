"""
技能注册表
管理所有可用的技能
"""
from typing import Dict, Type, List, Any
from .base_skill import BaseSkill


class SkillRegistry:
    """技能注册表"""
    
    _instance = None
    _skills: Dict[str, BaseSkill] = {}
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(self, skill_instance: BaseSkill) -> None:
        """
        注册技能
        
        Args:
            skill_instance: 技能实例
        """
        self._skills[skill_instance.name] = skill_instance
        print(f"✅ 技能已注册: {skill_instance.name}")
    
    def get(self, name: str) -> BaseSkill:
        """
        获取技能
        
        Args:
            name: 技能名称
            
        Returns:
            技能实例
            
        Raises:
            KeyError: 技能不存在
        """
        if name not in self._skills:
            raise KeyError(f"技能不存在: {name}")
        return self._skills[name]
    
    def list_skills(self) -> List[str]:
        """获取所有技能名称"""
        return list(self._skills.keys())
    
    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """获取所有技能的 schema（用于大模型）"""
        return [skill.get_schema() for skill in self._skills.values()]
    
    def get_skills_description(self) -> str:
        """获取所有技能的描述文本"""
        descriptions = []
        for name, skill in self._skills.items():
            desc = f"- {name}: {skill.description}"
            if skill.examples:
                desc += f"\n  示例: {', '.join(skill.examples[:2])}"
            descriptions.append(desc)
        return "\n".join(descriptions)


# 全局注册表实例
registry = SkillRegistry()
