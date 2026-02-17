"""
GitHub 搜索技能
搜索热门项目和趋势
"""
import httpx
from datetime import datetime, timedelta
from typing import Dict, Any
from .base_skill import BaseSkill, SkillResult


class GitHubSkill(BaseSkill):
    """GitHub 搜索技能"""
    
    name = "search_github"
    description = "搜索 GitHub 热门项目和趋势，支持关键词搜索"
    examples = [
        "搜索 GitHub 上热门的 AI 项目",
        "找找 ai-agent 相关的开源项目",
        "最近有什么新的机器学习项目"
    ]
    parameters = {
        "keywords": {
            "type": "string",
            "description": "搜索关键词，如 ai-agent、机器学习、区块链等",
            "required": True
        },
        "days": {
            "type": "integer",
            "description": "搜索最近几天的项目，默认7天",
            "default": 7,
            "minimum": 1,
            "maximum": 30
        }
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.github_token = config.get("github_token") if config else None
    
    async def execute(self, keywords: str, days: int = 7, **kwargs) -> SkillResult:
        """
        执行 GitHub 搜索
        
        Args:
            keywords: 搜索关键词
            days: 搜索最近几天的项目
        """
        try:
            if not keywords or not keywords.strip():
                return SkillResult(
                    success=False,
                    message="请提供搜索关键词"
                )
            
            # 构建查询
            date_since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            
            async with httpx.AsyncClient() as client:
                headers = {
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Feishu-Assistant"
                }
                if self.github_token:
                    headers["Authorization"] = f"token {self.github_token}"
                
                resp = await client.get(
                    "https://api.github.com/search/repositories",
                    params={
                        "q": f"{keywords} stars:>10 pushed:>{date_since}",
                        "sort": "stars",
                        "order": "desc",
                        "per_page": 5
                    },
                    headers=headers,
                    timeout=30
                )
                
                if resp.status_code == 403:
                    return SkillResult(
                        success=False,
                        message="GitHub API 速率限制，请稍后重试"
                    )
                
                resp.raise_for_status()
                repos = resp.json().get("items", [])
            
            if not repos:
                return SkillResult(
                    success=True,
                    message=f"未找到关键词 '{keywords}' 相关的项目"
                )
            
            # 格式化结果
            message = self._format_message(keywords, repos)
            card = self._format_card(keywords, repos)
            
            return SkillResult(
                success=True,
                message=message,
                data={"keywords": keywords, "repos": repos},
                card_content=card
            )
            
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"搜索失败: {str(e)}"
            )
    
    def _format_message(self, keywords: str, repos: list) -> str:
        """格式化文本消息"""
        msg = f"🚀 GitHub 趋势 - {keywords}\n\n"
        
        for i, repo in enumerate(repos[:5], 1):
            name = repo.get("full_name", "")
            desc = repo.get("description", "") or "无描述"
            stars = repo.get("stargazers_count", 0)
            lang = repo.get("language", "") or "未知"
            url = repo.get("html_url", "")
            
            msg += f"{i}. **{name}** ⭐ {stars}\n"
            msg += f"   📝 {desc[:60]}\n"
            msg += f"   🔗 {url}\n\n"
        
        return msg
    
    def _format_card(self, keywords: str, repos: list) -> Dict:
        """格式化飞书卡片"""
        elements = []
        
        for repo in repos[:5]:
            name = repo.get("full_name", "")
            desc = repo.get("description", "") or "无描述"
            stars = repo.get("stargazers_count", 0)
            lang = repo.get("language", "") or "未知"
            url = repo.get("html_url", "")
            
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**[{name}]({url})** ⭐ {stars} 🔤 {lang}\n{desc[:80]}"
                }
            })
            if repo != repos[-1]:
                elements.append({"tag": "hr"})
        
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"🚀 GitHub: {keywords}"},
                "template": "indigo"
            },
            "elements": elements
        }
