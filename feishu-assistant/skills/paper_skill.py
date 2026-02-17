"""
论文搜索技能
搜索 arXiv 学术论文
"""
import httpx
import xml.etree.ElementTree as ET
from typing import Dict, Any
from .base_skill import BaseSkill, SkillResult


class PaperSkill(BaseSkill):
    """论文搜索技能"""
    
    name = "search_papers"
    description = "搜索 arXiv 学术论文，支持主题、关键词搜索"
    examples = [
        "搜索关于 Transformer 的最新论文",
        "找找 AI Agent 相关的研究",
        "最近有什么关于大语言模型的论文"
    ]
    parameters = {
        "topic": {
            "type": "string",
            "description": "搜索主题或关键词，如 transformer、AI Agent、LLM 等",
            "required": True
        },
        "max_results": {
            "type": "integer",
            "description": "返回的最大结果数，默认5篇",
            "default": 5,
            "minimum": 1,
            "maximum": 10
        }
    }
    
    async def execute(self, topic: str, max_results: int = 5, **kwargs) -> SkillResult:
        """
        执行论文搜索
        
        Args:
            topic: 搜索主题
            max_results: 最大结果数
        """
        try:
            if not topic or not topic.strip():
                return SkillResult(
                    success=False,
                    message="请提供搜索主题"
                )
            
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "http://export.arxiv.org/api/query",
                    params={
                        "search_query": f"all:{topic}",
                        "start": 0,
                        "max_results": max_results,
                        "sortBy": "submittedDate",
                        "sortOrder": "descending"
                    },
                    timeout=30
                )
                resp.raise_for_status()
            
            papers = self._parse_arxiv_xml(resp.text)
            
            if not papers:
                return SkillResult(
                    success=True,
                    message=f"未找到主题 '{topic}' 相关的论文"
                )
            
            # 格式化结果
            message = self._format_message(topic, papers)
            card = self._format_card(topic, papers)
            
            return SkillResult(
                success=True,
                message=message,
                data={"topic": topic, "papers": papers},
                card_content=card
            )
            
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"搜索失败: {str(e)}"
            )
    
    def _parse_arxiv_xml(self, xml_data: str) -> list:
        """解析 arXiv XML"""
        papers = []
        namespaces = {'atom': 'http://www.w3.org/2005/Atom'}
        
        try:
            root = ET.fromstring(xml_data)
            
            for entry in root.findall('atom:entry', namespaces):
                # 标题
                title_elem = entry.find('atom:title', namespaces)
                title = title_elem.text.strip() if title_elem else "无标题"
                
                # 作者
                authors = []
                for author in entry.findall('atom:author', namespaces):
                    name = author.find('atom:name', namespaces)
                    if name is not None:
                        authors.append(name.text)
                
                # 链接
                url = ""
                for link in entry.findall('atom:link', namespaces):
                    if link.get('type') == 'text/html':
                        url = link.get('href', '')
                        break
                
                # 摘要
                summary_elem = entry.find('atom:summary', namespaces)
                summary = summary_elem.text.strip()[:150] + "..." if summary_elem else ""
                
                # 发布时间
                published = entry.find('atom:published', namespaces)
                date = published.text[:10] if published else ""
                
                papers.append({
                    "title": title,
                    "authors": authors[:3],
                    "url": url,
                    "summary": summary,
                    "date": date
                })
        
        except Exception as e:
            print(f"解析 XML 失败: {e}")
        
        return papers
    
    def _format_message(self, topic: str, papers: list) -> str:
        """格式化文本消息"""
        msg = f"📄 arXiv 论文 - {topic}\n\n"
        
        for i, paper in enumerate(papers, 1):
            msg += f"{i}. **{paper['title'][:80]}**\n"
            msg += f"   👤 {', '.join(paper['authors'])}\n"
            msg += f"   📅 {paper['date']}\n"
            msg += f"   🔗 {paper['url']}\n\n"
        
        return msg
    
    def _format_card(self, topic: str, papers: list) -> Dict:
        """格式化飞书卡片"""
        elements = []
        
        for paper in papers:
            authors = ', '.join(paper['authors'])
            content = f"**{paper['title'][:80]}**\n👤 {authors}  📅 {paper['date']}\n🔗 {paper['url']}"
            
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": content
                }
            })
            if paper != papers[-1]:
                elements.append({"tag": "hr"})
        
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"📄 arXiv: {topic}"},
                "template": "green"
            },
            "elements": elements
        }
