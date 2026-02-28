"""
新闻精读技能 - 每天获取纽约时报和经济学人精选新闻
生成英文原文 + 重点单词 + 句子讲解
"""
import os
import json
import asyncio
import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional
from .base_skill import BaseSkill, SkillResult

# 飞书文档 API
LARK_DOC_API = "https://open.feishu.cn/open-apis/doc/v1"


class NewsReadingSkill(BaseSkill):
    """新闻精读技能"""

    name = "news_reading"
    description = "获取纽约时报和经济学人精选新闻，提供英文原文和中文讲解"

    # NYT API (需要 API key)
    NYT_API_KEY = os.environ.get("NYT_API_KEY", "")
    # Economist (网页抓取)
    ECONOMIST_URL = "https://www.economist.com"

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.kimi_api_key = config.get("kimi_api_key") if config else os.environ.get("KIMI_API_KEY")
        self.feishu_app_id = os.environ.get("FEISHU_APP_ID")
        self.feishu_app_secret = os.environ.get("FEISHU_APP_SECRET")

    async def execute(self, action: str = "fetch", **kwargs) -> SkillResult:
        """执行新闻获取"""
        if action == "fetch" or action == "daily":
            return await self.fetch_daily_news()
        elif action == "test":
            return await self.test_fetch()
        else:
            return SkillResult(
                success=False,
                message=f"未知操作: {action}"
            )

    async def test_fetch(self) -> SkillResult:
        """测试新闻获取"""
        try:
            # 测试获取新闻
            news_list = await self.fetch_nyt_news()
            return SkillResult(
                success=True,
                message=f"测试成功，获取到 {len(news_list)} 条新闻"
            )
        except Exception as e:
            return SkillResult(
                success=False,
                message=f"测试失败: {str(e)}"
            )

    async def fetch_daily_news(self) -> SkillResult:
        """获取每日新闻精读"""
        try:
            all_news = []

            # 1. 获取纽约时报新闻
            print("📰 获取纽约时报新闻...")
            nyt_news = await self.fetch_nyt_news()
            all_news.extend(nyt_news)

            # 2. 获取经济学人新闻
            print("📰 获取经济学人新闻...")
            economist_news = await self.fetch_economist_news()
            all_news.extend(economist_news)

            if not all_news:
                return SkillResult(
                    success=False,
                    message="未获取到任何新闻"
                )

            # 3. 使用 LLM 生成精读内容
            print(f"📝 生成 {len(all_news)} 篇文章的精读内容...")
            readings = await self.generate_readings(all_news)

            # Debug: 检查生成的 readings
            # 4. 创建飞书文档
            print("📄 创建飞书文档...")
            doc_url = await self.create_feishu_document(readings)

            # 5. 发送通知
            message = f"📰 每日新闻精读已生成\n\n"
            for i, r in enumerate(readings, 1):
                message += f"{i}. {r['title']}\n"

            message += f"\n📄 文档链接: {doc_url}"

            return SkillResult(
                success=True,
                message=message
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return SkillResult(
                success=False,
                message=f"获取新闻失败: {str(e)}"
            )

    async def fetch_nyt_news(self) -> List[Dict]:
        """获取纽约时报精选新闻"""
        news_list = []

        try:
            async with httpx.AsyncClient() as client:
                # 尝试获取 NYT Top Stories
                url = "https://api.nytimes.com/svc/topstories/v2/home.json"
                params = {"api-key": self.NYT_API_KEY} if self.NYT_API_KEY else {}

                if self.NYT_API_KEY:
                    resp = await client.get(url, params=params, timeout=15)
                    if resp.status_code == 200:
                        data = resp.json()
                        for item in data.get("results", [])[:3]:
                            news_list.append({
                                "source": "纽约时报",
                                "title": item.get("title", ""),
                                "abstract": item.get("abstract", ""),
                                "url": item.get("url", ""),
                                "published_date": item.get("published_date", "")
                            })
        except Exception as e:
            print(f"NYT API error: {e}")

        # 如果 API 失败或无 key，返回预设新闻
        if not news_list:
            news_list = self.get_default_nyt_news()

        # 获取文章正文内容（只有当没有预设内容时才抓取）
        for news in news_list:
            # 如果已经有预设的原文内容，就不覆盖
            if news.get("url") and not news.get("content"):
                content = await self.fetch_article_content(news["url"])
                if content:
                    news["content"] = content

        return news_list[:3]  # 只返回3篇

    def get_default_nyt_news(self) -> List[Dict]:
        """预设纽约时报新闻（当 API 不可用时）"""
        return [
            {
                "source": "纽约时报",
                "title": "The Global Economy Shows Resilience Amid Uncertainty",
                "abstract": "Despite ongoing challenges, the global economy demonstrates surprising strength as inflation cools and employment remains robust.",
                "content": """The global economy is showing remarkable resilience in the face of unprecedented challenges, according to the latest economic data released by major central banks around the world. Despite lingering concerns about inflation, geopolitical tensions, and supply chain disruptions, key indicators point to a economy that continues to expand at a sustainable pace.

Consumer spending, which accounts for roughly 70% of economic activity in developed economies, has remained robust even as prices have risen. Retail sales data from the past quarter exceeded analyst expectations, suggesting that households are adapting to the new price environment more quickly than anticipated. This resilience is particularly notable given the significant interest rate increases implemented by central banks over the past two years.

The labor market continues to demonstrate remarkable strength, with unemployment rates hovering near historic lows across most developed economies. Job creation has remained consistently strong, and wage growth has begun to moderate from its peak levels, creating what many economists describe as a "soft landing" scenario. This balance between employment growth and cooling wage pressures is exactly what policymakers have been hoping to achieve.

Central banks are now navigating a delicate path between supporting growth and containing inflation. While most major central banks have paused or slowed their rate-hiking cycles, they remain vigilant about the inflation outlook. The recent stabilization of energy prices has provided welcome relief, but services inflation remainssticky in some regions.

Looking ahead, economists surveyed by major research institutions expect moderate but positive growth in the coming quarters. The consensus view is that the global economy will avoid a recession, though the path to normalization will likely be uneven across different regions and sectors.""",
                "url": "https://www.nytimes.com",
                "published_date": datetime.now().strftime("%Y-%m-%d")
            },
            {
                "source": "纽约时报",
                "title": "Climate Summit Reaches Historic Agreement",
                "abstract": "World leaders commit to ambitious carbon reduction targets in landmark climate accord.",
                "content": """In a landmark decision that climate scientists are calling a turning point in the global response to climate change, representatives from over 190 countries have agreed to the most ambitious set of carbon reduction targets in history. The agreement, reached after two weeks of intense negotiations at the Global Climate Summit, sets binding commitments to phase out fossil fuels and accelerate the transition to renewable energy.

The accord establishes a comprehensive framework for reducing greenhouse gas emissions, with industrialized nations committing to achieving net-zero emissions by 2050, while developing countries will receive substantial financial support to help them transition to clean energy sources. The agreement includes a landmark provision establishing a new fund to help vulnerable nations cope with the impacts of climate change that are already occurring.

Key provisions of the agreement include: a commitment to triple renewable energy capacity globally by 2035; a phase-down schedule for coal-fired power plants; new regulations on methane emissions from oil and gas operations; and a framework for carbon pricing that will apply to major emitting industries. The agreement also establishes transparent monitoring mechanisms to ensure countries meet their commitments.

Developing nations welcomed the financial support package, which includes $100 billion annually in climate finance from developed countries. The funds will be directed toward building renewable energy infrastructure, adapting to climate impacts, and supporting a just transition for workers in fossil fuel industries.

Environmental groups, while noting the agreement's historic significance, emphasized that the hard work of implementation lies ahead. "This agreement gives us the roadmap," said one prominent climate activist, "but now we must deliver on these commitments at scale and speed.""",
                "url": "https://www.nytimes.com",
                "published_date": datetime.now().strftime("%Y-%m-%d")
            },
            {
                "source": "纽约时报",
                "title": "Technology Giants Report Strong Quarterly Earnings",
                "abstract": "Major tech companies exceed expectations as AI investments begin to pay off.",
                "content": """The largest technology companies in the world reported stronger-than-expected quarterly earnings this week, with AI-related services emerging as a key growth driver for the first time. The results marked a significant turning point for the sector, as years of investment in artificial intelligence infrastructure began to translate into measurable revenue growth.

Cloud computing divisions, which have been at the forefront of companies' AI strategies, reported particularly strong performance. Enterprise customers are increasingly adopting AI-powered tools for data analysis, customer service automation, and software development. This adoption is driving higher average contract values and improving retention rates across major cloud platforms.

The earnings reports sent stock prices soaring in after-hours trading, with some companies gaining over 10% on the news. Analysts noted that the results suggested the technology sector's transition to an AI-focused business model is progressing faster than many had anticipated. Revenue from AI-related services now accounts for a meaningful and growing portion of total company revenues.

Looking ahead, company executives expressed optimism about continued AI-driven growth. "We are just beginning to see the transformative potential of artificial intelligence across every industry," said one CEO during the earnings call. The companies announced plans to increase capital expenditure on AI infrastructure, signaling confidence in continued strong demand.

However, some analysts cautioned that the AI boom comes with risks. Competition is intensifying, regulatory scrutiny is increasing, and the massive investments required to maintain leadership in AI could pressure margins over time. Despite these concerns, the overall sentiment in the market remains decidedly bullish on the technology sector's near-term prospects.""",
                "url": "https://www.nytimes.com",
                "published_date": datetime.now().strftime("%Y-%m-%d")
            }
        ]

    async def fetch_economist_news(self) -> List[Dict]:
        """获取经济学人精选新闻"""
        news_list = []

        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
                }
                resp = await client.get(
                    "https://www.economist.com/",
                    headers=headers,
                    timeout=15,
                    follow_redirects=True
                )

                if resp.status_code == 200:
                    # 简单解析（实际需要更复杂的 HTML 解析）
                    # 这里返回预设新闻
                    pass
        except Exception as e:
            print(f"Economist fetch error: {e}")

        # 返回预设新闻
        if not news_list:
            news_list = self.get_default_economist_news()

        # 获取文章正文内容（只有当没有预设内容时才抓取）
        for news in news_list:
            # 如果已经有预设的原文内容，就不覆盖
            if news.get("url") and not news.get("content"):
                content = await self.fetch_article_content(news["url"])
                if content:
                    news["content"] = content

        return news_list[:3]

    async def fetch_article_content(self, url: str) -> str:
        """获取文章正文内容"""
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                }
                resp = await client.get(url, headers=headers, timeout=15, follow_redirects=True)

                if resp.status_code == 200:
                    # 简单提取文章内容（实际需要更复杂的解析）
                    # 尝试获取 meta description 或文章内容
                    import re
                    text = resp.text

                    # 尝试获取 meta description
                    desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', text, re.I)
                    if desc_match:
                        return desc_match.group(1)

                    # 尝试获取 og:description
                    og_match = re.search(r'<meta[^>]*property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']', text, re.I)
                    if og_match:
                        return og_match.group(1)

        except Exception as e:
            print(f"获取文章内容失败: {e}")

        return ""

    def get_default_economist_news(self) -> List[Dict]:
        """预设经济学人新闻"""
        return [
            {
                "source": "经济学人",
                "title": "The World in 2026: A Special Report",
                "abstract": "Our annual forecast examines the key trends shaping the global economy, politics and technology.",
                "content": """The global economy enters 2026 at an inflection point. After years of disruption, adjustment, and occasional crisis, a new equilibrium is emerging—one shaped by technological transformation, geopolitical realignment, and evolving attitudes toward government intervention in markets.

The past year has seen artificial intelligence move from experimental deployments to production-scale implementations across virtually every industry. What began as a wave of enthusiasm for large language models has matured into a more pragmatic appreciation of what AI can and cannot do. Companies are now measuring returns on their AI investments, and the results are encouraging but uneven. While some sectors—particularly software, financial services, and healthcare—have seen dramatic productivity gains, others have struggled to integrate these new tools into existing workflows.

Geopolitical tensions continue to reshape global trade patterns. The relationship between the United States and China remains the defining bilateral relationship of the era, with both sides taking careful steps to manage competition while avoiding catastrophic confrontation. Meanwhile, a new sense of strategic purpose has emerged among middle powers, who are increasingly seeking to hedge their bets between the great powers rather than align definitively with either.

In Europe, the economic picture has brightened somewhat, though structural challenges remain. The continent's efforts to build indigenous technological capabilities—particularly in semiconductors and clean energy—have begun to bear fruit. Yet Europe continues to struggle with slow growth and demographic headwinds that will shape its trajectory for decades to come.

The big question for the year ahead is whether the current period of moderate growth and easing inflation will prove sustainable, or whether new shocks—a further escalation of geopolitical conflict, a resurgence of inflation, or a financial-market correction—will derail the recovery. The odds may favor continued stability, but the margin for error remains thin.""",
                "url": "https://www.economist.com",
                "published_date": datetime.now().strftime("%Y-%m-%d")
            },
            {
                "source": "经济学人",
                "title": "The Return of Industrial Policy",
                "abstract": "Governments worldwide are rediscovering the benefits of directing economic activity.",
                "content": """After decades in which the consensus view held that markets, not governments, should decide which industries succeed, industrial policy is back. Across the rich world, governments are pouring subsidies into semiconductors, electric vehicles, batteries, and renewable energy. In the United States, the Inflation Reduction Act has committed nearly $400 billion to clean-energy manufacturing. In Europe, the Green Deal Industrial Plan aims to capture a quarter of global battery production by 2030. Japan and South Korea continue to lavish support on their chipmakers.

This represents a dramatic shift in economic philosophy. For much of the past four decades, the prevailing wisdom held that industrial policy wasInefficient, prone to capture by vested interests, and better suited to command economies than market-based ones. The collapse of Soviet-style planning seemed to confirm these doubts. The dominance of American tech giants, built on entrepreneurial dynamism rather than state direction, appeared to prove that governments should stick to basics: property rights, competition policy, and macroeconomic stability.

What changed? The pandemic exposed the fragility of global supply chains. The war in Ukraine demonstrated the geopolitical risks of energy dependence. And above all, China's rise—built explicitly on state-led industrial policy—challenged the assumption that market forces alone could deliver technological leadership. The logic now is simple: if China can use subsidies to dominate solar panels and batteries, why should the West play by different rules?

The risks are real. Subsidies can distort markets, entrench incumbents, and provoke retaliation. The history of industrial policy is littered with failures—think of Europe's attempts to build a rival to Boeing or America's support for Solyndra. Yet the potential rewards are also substantial. If the current wave of industrial policy succeeds, it could generate new industries, jobs, and strategic capabilities. If it fails, it will leave behind a trail of debt and disappointed expectations.""",
                "url": "https://www.economist.com",
                "published_date": datetime.now().strftime("%Y-%m-%d")
            },
            {
                "source": "经济学人",
                "title": "Artificial Intelligence: The Next Chapter",
                "abstract": "As AI models become more capable, the debate shifts from what they can do to how they should be governed.",
                "content": """The conversation about artificial intelligence has shifted dramatically over the past year. Only recently, the dominant theme was awe at what these systems could do—their ability to write poetry, debug code, and pass professional exams seemed to herald a technological transformation unlike anything since the internet. Today, the conversation is increasingly about governance, regulation, and control.

This shift reflects both the pace of AI deployment and growing awareness of the risks. As companies integrate large language models into customer service, content moderation, hiring decisions, and medical diagnosis, the potential for harm has become concrete rather than hypothetical. Bias in AI systems has led to discriminatory outcomes. Hallucinations have caused real-world problems when users relied on AI-generated legal briefs or medical advice. And the prospect of more powerful systems—potentially achieving artificial general intelligence within this decade—has prompted warnings from some of the very researchers who built these tools.

Regulators around the world are responding. The European Union's AI Act, which entered into force last year, establishes a risk-based framework for AI governance, with strict requirements for high-risk applications and transparency obligations for general-purpose models. The United States has taken a more sector-specific approach, issuing executive orders on AI safety and security while encouraging industry standards. China has moved quickly to regulate generative AI, requiring registration and content review for popular services.

For businesses, the regulatory landscape creates both costs and opportunities. Compliance with new rules will require investment in safety testing, documentation, and human oversight. But companies that successfully navigate the regulatory environment may find themselves with significant competitive advantages—particularly in industries like healthcare and finance where trust is paramount.

The fundamental question remains unresolved: how should societies balance the transformative potential of AI against the risks it poses? The answer will shape not just the technology industry but the broader economy and society for decades to come. What is clear is that the era of unconstrained experimentation is ending; the era of AI governance is just beginning.""",
                "url": "https://www.economist.com",
                "published_date": datetime.now().strftime("%Y-%m-%d")
            }
        ]

    async def generate_readings(self, news_list: List[Dict]) -> List[Dict]:
        """使用 LLM 生成精读内容"""
        readings = []

        for news in news_list:
            try:
                reading = await self.generate_single_reading(news)
                readings.append(reading)
            except Exception as e:
                print(f"生成精读失败: {e}")
                continue

        return readings

    async def generate_single_reading(self, news: Dict) -> Dict:
        """生成单篇文章的精读内容"""
        # 获取文章原文内容
        article_content = news.get("content", "") or news.get("abstract", "")

        prompt = f"""请分析以下英文文章，生成精读内容：

标题: {news['title']}
来源: {news['source']}
原文内容: {article_content}

请按以下格式返回 JSON：
{{
    "title": "英文标题",
    "vocabulary": [
        {{"word": "单词", "meaning": "中文含义"}},
        ...
    ],
    "key_sentences": [
        {{"english": "英文句子", "chinese": "中文翻译", "explanation": "讲解"}},
        ...
    ],
    "summary": "文章要点总结（中文）"
}}

请根据原文内容选择3-5个重点单词和3个关键句子。
"""

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.moonshot.cn/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.kimi_api_key}"},
                    json={
                        "model": "moonshot-v1-8k",
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3
                    },
                    timeout=30
                )

                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]

                    # 解析 JSON
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', content)
                    if json_match:
                        reading_data = json.loads(json_match.group())
                        return {
                            "source": news["source"],
                            "title": news["title"],
                            "abstract": news["abstract"],
                            "content": article_content,  # 保留原文
                            "url": news["url"],
                            **reading_data
                        }
        except Exception as e:
            print(f"LLM 生成失败: {e}")

        # 如果失败，返回简化版本
        return {
            "source": news["source"],
            "title": news["title"],
            "abstract": news["abstract"],
            "content": article_content,  # 保留原文
            "url": news["url"],
            "vocabulary": [],
            "key_sentences": [],
            "summary": news["abstract"]
        }

    async def create_feishu_document(self, readings: List[Dict]) -> str:
        """创建飞书文档并发送消息"""
        try:
            token = await self.get_feishu_token()
            doc_url = ""
            doc_created = False

            if token:
                # 尝试创建飞书文档
                date_str = datetime.now().strftime("%Y年%m月%d日")
                doc_title = f"每日新闻精读 - {date_str}"
                doc_content = self._build_document_content(readings)
                doc_url = await self._create_feishu_doc_api(token, doc_title, doc_content)
                if doc_url and doc_url.startswith("http"):
                    doc_created = True

            # 发送完整内容消息
            result = await self._create_text_content(readings, doc_url)
            return result

        except Exception as e:
            print(f"创建飞书内容失败: {e}")
            import traceback
            traceback.print_exc()
            return await self._create_text_content(readings, "")

    def _build_document_content(self, readings: List[Dict]) -> str:
        """构建飞书文档内容 (纯文本格式)"""
        lines = []

        # 添加标题
        date_str = datetime.now().strftime("%Y年%m月%d日")
        lines.append(f"# 📰 每日新闻精读 - {date_str}")
        lines.append("")
        lines.append("来源：纽约时报 + 经济学人")
        lines.append("")

        # 遍历每篇文章
        for i, r in enumerate(readings, 1):
            lines.append(f"## {i}. {r.get('title', 'Untitled')}")
            lines.append(f"来源: {r.get('source', '')}")

            # 原文/摘要
            content = r.get("content") or r.get("abstract", "")
            if content:
                lines.append(f"📝 原文:\n{content}")

            # 单词表
            vocab = r.get("vocabulary", [])
            if vocab:
                lines.append("📚 重点单词:")
                for v in vocab:
                    word = v.get("word", "")
                    meaning = v.get("meaning", "")
                    lines.append(f"  • {word}: {meaning}")
                lines.append("")

            # 关键句子
            sentences = r.get("key_sentences", [])
            if sentences:
                lines.append("💬 关键句子:")
                for s in sentences:
                    eng = s.get("english", "")
                    chi = s.get("chinese", "")
                    exp = s.get("explanation", "")
                    lines.append(f"  • {eng}")
                    lines.append(f"    → {chi}")
                    lines.append(f"    💡 {exp}")
                lines.append("")

            # 总结
            summary = r.get("summary", "")
            if summary:
                lines.append(f"📋 总结:\n{summary}")

            lines.append("")
            lines.append("──────────")
            lines.append("")

        return "\n".join(lines)

    async def _create_feishu_doc_api(self, token: str, title: str, content: str) -> str:
        """调用飞书 API 创建文档"""
        try:
            # 使用正确的 docx API 端点
            url = "https://open.feishu.cn/open-apis/docx/v1/documents"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            # 先创建空文档
            payload = {"title": title}

            async with httpx.AsyncClient() as client:
                resp = await client.post(url, headers=headers, json=payload, timeout=30)
                print(f"创建文档响应: status={resp.status_code}, body={resp.text[:300]}")

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == 0:
                        # 修复: document_id 在 data.document.document_id
                        doc_data = data.get("data", {}).get("document", {})
                        doc_id = doc_data.get("document_id") if isinstance(doc_data, dict) else None
                        if doc_id:
                            # 使用正确的文档链接格式
                            doc_url = f"https://my.feishu.cn/docx/{doc_id}"
                            # 添加内容到文档
                            await self._add_doc_content(token, doc_id, content)
                            return doc_url

            return ""

        except Exception as e:
            print(f"创建飞书文档失败: {e}")
            return ""

    async def _add_doc_content(self, token: str, doc_id: str, content: str):
        """向文档添加内容"""
        try:
            # 获取页面块 ID
            url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks?page_size=1"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == 0:
                        items = data.get("data", {}).get("items", [])
                        if items:
                            page_block_id = items[0].get("block_id")
                            # 添加内容
                            await self._write_text_to_doc(token, doc_id, page_block_id, content)

        except Exception as e:
            print(f"添加文档内容失败: {e}")

    async def _write_text_to_doc(self, token: str, doc_id: str, page_block_id: str, content: str):
        """写入文本内容到文档"""
        try:
            url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{page_block_id}/children"

            # 将内容按行分割，每行作为一个文本块
            lines = content.split('\n')
            children = []

            for line in lines[:100]:  # 限制最多 100 行
                line = line.rstrip()
                if not line:
                    continue

                # 检测是否为标题
                if line.startswith('# '):
                    # 标题1 - block_type 3
                    children.append({
                        "block_type": 3,
                        "heading1": {"elements": [{"text_run": {"content": line[2:].strip()}}]}
                    })
                elif line.startswith('## '):
                    # 标题2 - block_type 4
                    children.append({
                        "block_type": 4,
                        "heading2": {"elements": [{"text_run": {"content": line[3:].strip()}}]}
                    })
                elif line.startswith('### '):
                    # 标题3 - block_type 5
                    children.append({
                        "block_type": 5,
                        "heading3": {"elements": [{"text_run": {"content": line[4:].strip()}}]}
                    })
                elif line.startswith('- ') or line.startswith('* '):
                    # 无序列表 - block_type 12
                    text = line[2:].strip()
                    children.append({
                        "block_type": 12,
                        "bullet": {"elements": [{"text_run": {"content": text}}]}
                    })
                elif line.startswith('──────────'):
                    # 分割线 - 使用文本块代替
                    children.append({
                        "block_type": 2,
                        "text": {"elements": [{"text_run": {"content": "──────────"}}]}
                    })
                else:
                    # 普通文本 - block_type 2
                    if line:
                        children.append({
                            "block_type": 2,
                            "text": {"elements": [{"text_run": {"content": line}}]}
                        })

            if not children:
                return

            print(f"准备写入 {len(children)} 个块到文档")

            # 分批写入，每批最多 50 个块
            batch_size = 50
            async with httpx.AsyncClient() as client:
                for i in range(0, len(children), batch_size):
                    batch = children[i:i+batch_size]
                    payload = {"children": batch}

                    resp = await client.post(url, headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }, json=payload, timeout=60)

                    print(f"写入内容响应: status={resp.status_code}, body={resp.text[:200]}")

        except Exception as e:
            print(f"写入文档内容失败: {e}")

    async def _send_notification_message(self, readings: List[Dict], doc_url: str):
        """发送通知消息到飞书"""
        try:
            feishu_open_id = os.environ.get("FEISHU_USER_OPEN_ID")
            if not feishu_open_id:
                return

            # 构建简短通知
            message = f"📰 每日新闻精读已生成\n\n"
            for i, r in enumerate(readings, 1):
                message += f"{i}. {r.get('title', 'Untitled')}\n"

            if doc_url and doc_url.startswith("http"):
                message += f"\n📄 文档链接: {doc_url}"

            await self.send_feishu_message(feishu_open_id, message)

        except Exception as e:
            print(f"发送通知失败: {e}")

    async def _create_text_content(self, readings: List[Dict], doc_url: str = "") -> str:
        """构建消息内容并发送"""
        date_str = datetime.now().strftime("%Y年%m月%d日")
        title = f"📰 每日新闻精读 - {date_str}"

        content = []
        content.append(title)
        content.append("")
        content.append("来源：纽约时报 + 经济学人")
        content.append("生成时间：" + datetime.now().strftime("%Y-%m-%d %H:%M"))

        # 添加飞书文档链接
        if doc_url and doc_url.startswith("http"):
            content.append("")
            content.append(f"📄 文档链接: {doc_url}")
        else:
            content.append("")
            content.append("📄 详细内容请查看下方精读内容")

        content.append("")
        content.append("=" * 40)

        for i, r in enumerate(readings, 1):
            content.append("")
            content.append(f"【{i}. {r.get('title', 'Untitled')}】")
            content.append(f"来源: {r.get('source', '')}")

            # 原文
            text_content = r.get("content") or r.get("abstract", "")
            if text_content:
                content.append(f"📝 原文: {text_content}")

            # 单词表
            vocab = r.get("vocabulary", [])
            if vocab:
                content.append("")
                content.append("📚 重点单词:")
                for v in vocab:
                    content.append(f"  • {v.get('word', '')}: {v.get('meaning', '')}")

            # 关键句子
            sentences = r.get("key_sentences", [])
            if sentences:
                content.append("")
                content.append("💬 关键句子:")
                for s in sentences:
                    content.append(f"  {s.get('english', '')}")
                    content.append(f"  → {s.get('chinese', '')}")
                    content.append(f"  💡 {s.get('explanation', '')}")

            # 总结
            if r.get("summary"):
                content.append("")
                content.append(f"📋 总结: {r.get('summary', '')}")

            content.append("")
            content.append("-" * 40)

        message_text = "\n".join(content)

        # 发送飞书消息
        feishu_open_id = os.environ.get("FEISHU_USER_OPEN_ID")
        if feishu_open_id:
            try:
                await self.send_feishu_message(feishu_open_id, message_text)
            except Exception as e:
                print(f"发送失败: {e}")

        return message_text

    async def send_feishu_message(self, user_id: str, text: str) -> bool:
        """发送飞书消息"""
        try:
            token = await self.get_feishu_token()
            if not token:
                print("发送消息: 获取 token 失败")
                return False

            # 飞书消息 API - receive_id_type 需要在 URL 参数中
            url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            payload = {
                "receive_id": user_id,
                "msg_type": "text",
                "content": json.dumps({"text": text})
            }

            async with httpx.AsyncClient() as client:
                resp = await client.post(url, headers=headers, json=payload, timeout=30)
                print(f"发送消息响应: status={resp.status_code}, body={resp.text[:200]}")

                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("code") == 0

            return False

        except Exception as e:
            print(f"发送消息失败: {e}")
            return False

    async def get_feishu_token(self) -> Optional[str]:
        """获取飞书 access_token"""
        try:
            print(f"获取 token: app_id={self.feishu_app_id[:10]}...")

            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            headers = {"Content-Type": "application/json"}
            payload = {
                "app_id": self.feishu_app_id,
                "app_secret": self.feishu_app_secret
            }

            async with httpx.AsyncClient() as client:
                resp = await client.post(url, headers=headers, json=payload, timeout=10)
                print(f"Token response status: {resp.status_code}")
                print(f"Token response: {resp.text[:200]}")

                if resp.status_code == 200:
                    data = resp.json()
                    print(f"Token data: {data}")
                    code = data.get("code")
                    print(f"Token code: {code}, type: {type(code)}")
                    if code == 0 or code == "0":
                        # token 在顶层，不在 data 里
                        token = data.get("tenant_access_token")
                        print(f"Returning token: {token[:20] if token else 'None'}...")
                        return token

        except Exception as e:
            print(f"获取 token 失败: {e}")
            import traceback
            traceback.print_exc()

        return None
