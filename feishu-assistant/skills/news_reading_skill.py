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

    # 类级别缓存
    _cache: Dict[str, Any] = {}
    _cache_date: str = ""

    # NYT API (需要 API key)
    NYT_API_KEY = os.environ.get("NYT_API_KEY", "")
    # Economist (网页抓取)
    ECONOMIST_URL = "https://www.economist.com"

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.kimi_api_key = config.get("kimi_api_key") if config else os.environ.get("KIMI_API_KEY")
        self.feishu_app_id = os.environ.get("FEISHU_APP_ID")
        self.feishu_app_secret = os.environ.get("FEISHU_APP_SECRET")
        # 火山引擎 API 密钥
        self.volcengine_access_key = os.environ.get("VOLCENGINE_ACCESS_KEY", "pOzMLb-Ez8AvBJ1Ym47m_Fk2l6ULzzRC")
        self.volcengine_secret_key = os.environ.get("VOLCENGINE_SECRET_KEY", "iq-Pa3WVvd4kALTYdiCH48L4n9HqVIX7")
        self.volcengine_app_id = os.environ.get("VOLCENGINE_APP_ID", "5884074284")

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

    async def fetch_daily_news(self, use_cache: bool = True) -> SkillResult:
        """获取每日新闻精读

        Args:
            use_cache: 是否使用缓存（当天内返回相同内容）
        """
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")

        # 检查缓存
        if use_cache and NewsReadingSkill._cache_date == today:
            cached = NewsReadingSkill._cache.get("result")
            if cached:
                print("📦 使用缓存的新闻精读")
                return cached

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
            # 4. 生成播客音频
            print("🎙️ 生成播客音频...")
            podcast_url = await self.generate_podcast(readings)

            # 5. 创建飞书文档
            print("📄 创建飞书文档...")
            doc_url = await self.create_feishu_document(readings, podcast_url)

            # 6. 发送通知
            message = f"📰 每日新闻精读已生成\n\n"
            for i, r in enumerate(readings, 1):
                message += f"{i}. {r['title']}\n"

            message += f"\n📄 文档链接: {doc_url}"
            if podcast_url:
                message += f"\n🎙️ 播客链接: {podcast_url}"

            # 保存到缓存
            result = SkillResult(
                success=True,
                message=message
            )
            NewsReadingSkill._cache_date = today
            NewsReadingSkill._cache["result"] = result
            print("💾 已保存到缓存")

            return result

        except Exception as e:
            import traceback
            traceback.print_exc()
            return SkillResult(
                success=False,
                message=f"获取新闻失败: {str(e)}"
            )

    async def fetch_nyt_news(self) -> List[Dict]:
        """获取当天新闻 - 使用可靠的数据源"""
        news_list = []
        today = datetime.now().strftime("%Y-%m-%d")

        print("开始获取实时新闻...")

        # 方法1: BBC News RSS
        try:
            print("尝试 BBC News...")
            news_list = await self._fetch_from_bbc_news()
            if news_list:
                print(f"BBC News 获取到 {len(news_list)} 条")
        except Exception as e:
            print(f"BBC News 获取失败: {e}")

        # 方法2: Reuters RSS
        if not news_list:
            try:
                print("尝试 Reuters...")
                news_list = await self._fetch_from_reuters_news()
                if news_list:
                    print(f"Reuters 获取到 {len(news_list)} 条")
            except Exception as e:
                print(f"Reuters 获取失败: {e}")

        # 方法3: Al Jazeera RSS
        if not news_list:
            try:
                print("尝试 Al Jazeera...")
                news_list = await self._fetch_from_aljazeera_news()
                if news_list:
                    print(f"Al Jazeera 获取到 {len(news_list)} 条")
            except Exception as e:
                print(f"Al Jazeera 获取失败: {e}")

        # 如果都失败，返回空列表
        if not news_list:
            print("警告: 所有新闻源都获取失败，返回空列表")
            return []

        # 获取文章正文内容
        for news in news_list:
            if news.get("url") and not news.get("content"):
                try:
                    content = await self.fetch_article_content(news["url"])
                    if content:
                        news["content"] = content
                except Exception as e:
                    print(f"获取文章内容失败: {e}")

        return news_list[:3]

    async def _fetch_from_bbc_news(self) -> List[Dict]:
        """从 BBC News 获取新闻"""
        news_list = []
        try:
            async with httpx.AsyncClient() as client:
                url = "http://feeds.bbci.co.uk/news/world/rss.xml"
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = await client.get(url, headers=headers, timeout=15)

                if resp.status_code == 200:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(resp.text.encode('utf-8'))
                    for item in root.findall(".//item")[:5]:
                        title = item.findtext("title", "")
                        link = item.findtext("link", "")
                        desc = item.findtext("description", "")
                        import re
                        desc = re.sub(r'<[^>]+>', '', desc) if desc else ""

                        if title and link:
                            news_list.append({
                                "source": "BBC News",
                                "title": title,
                                "abstract": desc[:500] if desc else "",
                                "url": link,
                                "published_date": datetime.now().strftime("%Y-%m-%d")
                            })
        except Exception as e:
            print(f"BBC News error: {e}")

        return news_list

    async def _fetch_from_reuters_news(self) -> List[Dict]:
        """从 Reuters 获取新闻"""
        news_list = []
        try:
            async with httpx.AsyncClient() as client:
                url = "https://www.reutersagency.com/feed/?best-topics=business-finance"
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = await client.get(url, headers=headers, timeout=15)

                if resp.status_code == 200:
                    import xml.etree.ElementTree as ET
                    try:
                        root = ET.fromstring(resp.text.encode('utf-8'))
                    except:
                        return news_list
                    for item in root.findall(".//item")[:5]:
                        title = item.findtext("title", "")
                        link = item.findtext("link", "")
                        desc = item.findtext("description", "")
                        import re
                        desc = re.sub(r'<[^>]+>', '', desc) if desc else ""

                        if title and link:
                            news_list.append({
                                "source": "Reuters",
                                "title": title,
                                "abstract": desc[:500] if desc else "",
                                "url": link,
                                "published_date": datetime.now().strftime("%Y-%m-%d")
                            })
        except Exception as e:
            print(f"Reuters error: {e}")

        return news_list

    async def _fetch_from_aljazeera_news(self) -> List[Dict]:
        """从 Al Jazeera 获取新闻"""
        news_list = []
        try:
            async with httpx.AsyncClient() as client:
                url = "https://www.aljazeera.com/xml/rss/all.xml"
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = await client.get(url, headers=headers, timeout=15)

                if resp.status_code == 200:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(resp.text.encode('utf-8'))
                    for item in root.findall(".//item")[:5]:
                        title = item.findtext("title", "")
                        link = item.findtext("link", "")
                        desc = item.findtext("description", "")
                        import re
                        desc = re.sub(r'<[^>]+>', '', desc) if desc else ""

                        if title and link:
                            news_list.append({
                                "source": "Al Jazeera",
                                "title": title,
                                "abstract": desc[:500] if desc else "",
                                "url": link,
                                "published_date": datetime.now().strftime("%Y-%m-%d")
                            })
        except Exception as e:
            print(f"Al Jazeera error: {e}")

        return news_list

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
        """获取商业/财经新闻"""
        news_list = []

        print("开始获取财经新闻...")

        # 方法1: CNBC RSS
        try:
            print("尝试 CNBC...")
            news_list = await self._fetch_from_cnbc_news()
            if news_list:
                print(f"CNBC 获取到 {len(news_list)} 条")
        except Exception as e:
            print(f"CNBC 获取失败: {e}")

        # 方法2: Yahoo Finance
        if not news_list:
            try:
                print("尝试 Yahoo Finance...")
                news_list = await self._fetch_from_yahoo_news()
                if news_list:
                    print(f"Yahoo Finance 获取到 {len(news_list)} 条")
            except Exception as e:
                print(f"Yahoo Finance 获取失败: {e}")

        # 方法3: CNBC Technology
        if not news_list:
            try:
                print("尝试 TechCrunch...")
                news_list = await self._fetch_from_techcrunch_news()
                if news_list:
                    print(f"TechCrunch 获取到 {len(news_list)} 条")
            except Exception as e:
                print(f"TechCrunch 获取失败: {e}")

        # 如果都失败，返回空列表
        if not news_list:
            print("警告: 所有财经新闻源都获取失败，返回空列表")
            return []

        # 获取文章正文内容
        for news in news_list:
            if news.get("url") and not news.get("content"):
                try:
                    content = await self.fetch_article_content(news["url"])
                    if content:
                        news["content"] = content
                except Exception as e:
                    print(f"获取文章内容失败: {e}")

        return news_list[:3]

    async def _fetch_from_cnbc_news(self) -> List[Dict]:
        """从 CNBC 获取新闻"""
        news_list = []
        try:
            async with httpx.AsyncClient() as client:
                url = "https://www.cnbc.com/id/100003114/device/rss/rss.html"
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = await client.get(url, headers=headers, timeout=15)

                if resp.status_code == 200:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(resp.text.encode('utf-8'))
                    for item in root.findall(".//item")[:5]:
                        title = item.findtext("title", "")
                        link = item.findtext("link", "")
                        desc = item.findtext("description", "")
                        import re
                        desc = re.sub(r'<[^>]+>', '', desc) if desc else ""

                        if title and link:
                            news_list.append({
                                "source": "CNBC",
                                "title": title,
                                "abstract": desc[:500] if desc else "",
                                "url": link,
                                "published_date": datetime.now().strftime("%Y-%m-%d")
                            })
        except Exception as e:
            print(f"CNBC error: {e}")

        return news_list

    async def _fetch_from_yahoo_news(self) -> List[Dict]:
        """从 Yahoo Finance 获取新闻"""
        news_list = []
        try:
            async with httpx.AsyncClient() as client:
                url = "https://finance.yahoo.com/news/rssindex"
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = await client.get(url, headers=headers, timeout=15)

                if resp.status_code == 200:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(resp.text.encode('utf-8'))
                    for item in root.findall(".//item")[:5]:
                        title = item.findtext("title", "")
                        link = item.findtext("link", "")
                        desc = item.findtext("description", "")
                        import re
                        desc = re.sub(r'<[^>]+>', '', desc) if desc else ""

                        if title and link:
                            news_list.append({
                                "source": "Yahoo Finance",
                                "title": title,
                                "abstract": desc[:500] if desc else "",
                                "url": link,
                                "published_date": datetime.now().strftime("%Y-%m-%d")
                            })
        except Exception as e:
            print(f"Yahoo Finance error: {e}")

        return news_list

    async def _fetch_from_techcrunch_news(self) -> List[Dict]:
        """从 TechCrunch 获取新闻"""
        news_list = []
        try:
            async with httpx.AsyncClient() as client:
                url = "https://techcrunch.com/feed/"
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = await client.get(url, headers=headers, timeout=15)

                if resp.status_code == 200:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(resp.text.encode('utf-8'))
                    for item in root.findall(".//item")[:5]:
                        title = item.findtext("title", "")
                        link = item.findtext("link", "")
                        desc = item.findtext("description", "")
                        import re
                        desc = re.sub(r'<[^>]+>', '', desc) if desc else ""

                        if title and link:
                            news_list.append({
                                "source": "TechCrunch",
                                "title": title,
                                "abstract": desc[:500] if desc else "",
                                "url": link,
                                "published_date": datetime.now().strftime("%Y-%m-%d")
                            })
        except Exception as e:
            print(f"TechCrunch error: {e}")

        return news_list

    async def _fetch_from_economist_rss(self) -> List[Dict]:
        """从 Economist RSS 获取新闻"""
        news_list = []
        try:
            async with httpx.AsyncClient() as client:
                url = "https://www.economist.com/rss"
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = await client.get(url, headers=headers, timeout=15)

                if resp.status_code == 200:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(resp.text)
                    for item in root.findall(".//item")[:3]:
                        title = item.findtext("title", "")
                        link = item.findtext("link", "")
                        desc = item.findtext("description", "")
                        import re
                        desc = re.sub(r'<[^>]+>', '', desc) if desc else ""

                        if title and link:
                            news_list.append({
                                "source": "The Economist",
                                "title": title,
                                "abstract": desc[:500],
                                "url": link,
                                "published_date": datetime.now().strftime("%Y-%m-%d")
                            })
        except Exception as e:
            print(f"Economist RSS error: {e}")

        return news_list

    async def _fetch_business_news(self) -> List[Dict]:
        """从 Bing 获取商业新闻"""
        news_list = []
        try:
            async with httpx.AsyncClient() as client:
                url = "https://www.bing.com/news/search?q=business+economy+technology&form=QBLH"
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = await client.get(url, headers=headers, timeout=15)

                # 由于 Bing 页面是动态加载的，这里返回空
                # 实际可以用 Bing News API
                pass
        except Exception as e:
            print(f"Business news error: {e}")

        return news_list

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

    async def create_feishu_document(self, readings: List[Dict], podcast_url: str = "") -> str:
        """创建飞书文档并发送消息"""
        try:
            token = await self.get_feishu_token()
            doc_url = ""
            doc_created = False

            if token:
                # 尝试创建飞书文档
                date_str = datetime.now().strftime("%Y年%m月%d日")
                doc_title = f"每日新闻精读 - {date_str}"
                doc_content = self._build_document_content(readings, podcast_url)
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

    def _build_document_content(self, readings: List[Dict], podcast_url: str = "") -> str:
        """构建飞书文档内容 (纯文本格式)"""
        lines = []

        # 添加标题
        date_str = datetime.now().strftime("%Y年%m月%d日")
        lines.append(f"# 📰 每日新闻精读 - {date_str}")
        lines.append("")

        # 添加播客链接
        if podcast_url:
            lines.append(f"🎙️ 播客音频: {podcast_url}")
            lines.append("")

        lines.append("来源：纽约时报 + 经济学人")
        lines.append("")
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

        # 注意：不再直接发送消息，由 main_v2.py 通过 SkillResult 统一发送
        # 避免重复发送两条消息

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

    # ==================== 豆包播客 TTS 功能 ====================

    async def generate_podcast(self, readings: List[Dict]) -> str:
        """生成播客音频"""
        try:
            # 合并所有文章的原文和总结作为播客内容
            podcast_text = self._prepare_podcast_text(readings)

            if not podcast_text:
                print("⚠️ 没有内容可生成播客")
                return ""

            print(f"🎙️ 开始生成播客，文本长度: {len(podcast_text)} 字符")

            # 调用豆包播客API（使用同步版本）
            loop = asyncio.get_event_loop()
            audio_url = await loop.run_in_executor(
                None,
                self._generate_podcast_sync,
                podcast_text
            )

            if audio_url:
                print(f"✅ 播客生成成功: {audio_url}")
                return audio_url
            else:
                print("⚠️ 播客生成失败")
                return ""

        except Exception as e:
            print(f"生成播客失败: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def _generate_podcast_sync(self, text: str) -> str:
        """同步生成播客（使用官方示例方式）"""
        import websocket
        import json
        import struct
        import uuid
        import ssl
        import time
        import requests

        WS_URL = "wss://openspeech.bytedance.com/api/v3/sami/podcasttts"

        def build_msg(event, payload, session_id=None):
            """构建 WebSocket 消息"""
            header = bytes([0x11, 0b00010100, 0x10, 0x00])  # type=1, flags=0100
            pl = payload.encode() if isinstance(payload, str) else payload
            parts = [struct.pack('>I', event)]
            if session_id is not None:
                sid = session_id.encode()[:12].ljust(12, b'\x00')
                parts.extend([struct.pack('>I', len(sid)), sid])
            parts.extend([struct.pack('>I', len(pl)), pl])
            return header + b''.join(parts)

        def parse_msg(data):
            """解析 WebSocket 消息"""
            if len(data) < 12:
                return None
            msg_type = (data[1] >> 4) & 0x0F
            event = struct.unpack('>I', data[4:8])[0]
            session_id_len = struct.unpack('>I', data[8:12])[0]
            offset = 12 + session_id_len
            payload_len = struct.unpack('>I', data[offset:offset+4])[0]
            payload = data[offset+4:offset+4+payload_len]
            try:
                payload = json.loads(payload.decode())
            except:
                pass
            return {'msg_type': msg_type, 'event': event, 'payload': payload}

        session_id = str(uuid.uuid4())

        try:
            # 连接 WebSocket
            ws = websocket.create_connection(
                WS_URL,
                header={
                    'X-Api-App-Id': self.volcengine_app_id,
                    'X-Api-Access-Key': self.volcengine_access_key,
                    'X-Api-Resource-Id': 'volc.service_type.10050',
                    'X-Api-App-Key': 'aGjiRDfUWi',
                },
                sslopt={"cert_reqs": ssl.CERT_NONE},
                timeout=180
            )

            # 1. StartConnection
            print("1️⃣  StartConnection...")
            ws.send(build_msg(1, "{}"), opcode=websocket.ABNF.OPCODE_BINARY)
            msg = parse_msg(ws.recv())
            print(f"   ✅ ConnectionStarted (event={msg['event']})\n")

            # 2. StartSession - 注意 event=100
            print("2️⃣  StartSession...")
            params = {
                "input_id": f"news_{int(time.time())}",
                "input_text": text[:5000],  # 限制长度
                "action": 0,
                "use_head_music": True,
                "use_tail_music": False,
                "audio_config": {"format": "mp3", "sample_rate": 24000},
                "speaker_info": {
                    "random_order": True,
                    "speakers": [
                        "zh_male_dayixiansheng_v2_saturn_bigtts",
                        "zh_female_mizaitongxue_v2_saturn_bigtts"
                    ]
                },
                "input_info": {"return_audio_url": True}
            }
            ws.send(build_msg(100, json.dumps(params), session_id), opcode=websocket.ABNF.OPCODE_BINARY)

            # 3. 接收播客数据
            print("\n3️⃣  正在生成播客...\n")
            audio_url = None
            ws.settimeout(300)

            while True:
                try:
                    data = ws.recv()
                    msg = parse_msg(data)
                    if not msg:
                        continue

                    event = msg['event']
                    payload = msg['payload']

                    if event == 150:
                        print("✅ SessionStarted\n")
                    elif event == 360:
                        round_id = payload.get('round_id', 0)
                        if round_id == -1:
                            print("🎵 片头音乐\n")
                        elif round_id == 9999:
                            print("🎵 片尾音乐\n")
                    elif event == 363:
                        audio_url = payload.get('meta_info', {}).get('audio_url')
                        print(f"\n✅ PodcastEnd! 播客生成完成!")
                        break
                    elif event == 152:
                        print("✅ SessionFinished")
                        break

                except websocket.WebSocketTimeoutException:
                    print("⏱️ 超时")
                    break
                except Exception as e:
                    print(f"❌ 错误: {e}")
                    break

            ws.close()

            # 4. 返回公网 URL（不下载到本地，URL 有效期1小时）
            if audio_url:
                print(f"\n✅ 播客音频 URL: {audio_url[:80]}...")
                return audio_url
            else:
                print("\n❌ 未获取到音频URL")
                return ""

        except Exception as e:
            print(f"❌ 播客生成错误: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def _prepare_podcast_text(self, readings: List[Dict]) -> str:
        """准备播客文本"""
        lines = []
        lines.append("大家好，今天为大家带来新闻精读。")

        for i, r in enumerate(readings, 1):
            title = r.get("title", "")
            source = r.get("source", "")
            content = r.get("content", "")[:2000]  # 限制长度
            summary = r.get("summary", "")

            lines.append(f"第{i}篇，{source}报道：")
            lines.append(f"标题：{title}")
            lines.append(f"原文内容：{content}")
            if summary:
                lines.append(f"总结：{summary}")
            lines.append("")

        lines.append("以上就是今天的新闻精读，感谢收听。")
        return "\n".join(lines)

    async def _call_doubao_podcast_api(self, text: str) -> str:
        """调用豆包播客TTS API"""
        import uuid
        import websockets
        from websockets.exceptions import ConnectionClosed

        ws_url = "wss://openspeech.bytedance.com/api/v3/sami/podcasttts"

        # 使用 dict 格式的 headers
        headers = {
            "X-Api-App-Id": self.volcengine_app_id,
            "X-Api-Access-Key": self.volcengine_access_key,
            "X-Api-Resource-Id": "volc.service_type.10050",
            "X-Api-App-Key": "aGjiRDfUWi",
            "X-Api-Request-Id": str(uuid.uuid4())
        }

        # 构建请求参数
        request_payload = {
            "input_id": f"news_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "input_text": text[:8000],  # 限制文本长度
            "action": 0,
            "use_head_music": True,
            "audio_params": {
                "format": "mp3",
                "sample_rate": 24000,
                "speech_rate": 0,
            },
            "speaker_info": {
                "random_order": True,
                "speakers": [
                    "zh_male_dayixiansheng_v2_saturn_bigtts",
                    "zh_female_mizaitongxue_v2_saturn_bigtts"
                ]
            },
            "aigc_watermark": False
        }

        try:
            async with websockets.connect(ws_url, additional_headers=headers) as ws:
                print("🔌 WebSocket 连接成功")

                # 发送 StartSession 帧
                await self._send_start_session(ws, request_payload)

                # 接收响应
                audio_url = await self._receive_podcast_response(ws)

                return audio_url

        except ConnectionClosed as e:
            print(f"WebSocket 连接关闭: {e}")
            return ""
        except Exception as e:
            print(f"WebSocket 错误: {e}")
            import traceback
            traceback.print_exc()
            return ""

    async def _send_start_session(self, ws, payload: dict):
        """发送 StartSession 帧"""
        import json

        session_id = "session_" + str(datetime.now().timestamp())
        payload_json = json.dumps(payload)

        # 构建二进制帧
        # header: 4 bytes
        # [0] = 0b0001_0001 (version=1, header_size=1)
        # [1] = 0b1001_0100 (message_type=9, flags=4)
        # [2] = 0b0001_0000 (serialization=JSON, compression=none)
        # [3] = 0b0000_0000 (reserved)
        header = bytes([0x11, 0x94, 0x10, 0x00])

        # event type: StartSession = 1001 (需要转换为大端 uint32)
        event_type = (1001).to_bytes(4, 'big')

        # session_id
        session_id_bytes = session_id.encode('utf-8')
        session_id_len = len(session_id_bytes).to_bytes(4, 'big')

        # payload
        payload_bytes = payload_json.encode('utf-8')
        payload_len = len(payload_bytes).to_bytes(4, 'big')

        # 组合帧
        frame = header + event_type + session_id_len + session_id_bytes + payload_len + payload_bytes

        await ws.send(frame)
        print(f"📤 已发送 StartSession 帧")

    async def _receive_podcast_response(self, ws) -> str:
        """接收播客响应"""
        audio_data = b""
        audio_url = ""

        while True:
            try:
                message = await ws.recv()

                if isinstance(message, bytes):
                    # 解析二进制帧
                    if len(message) < 8:
                        continue

                    # 解析 header
                    byte0 = message[0]
                    byte1 = message[1]
                    byte2 = message[2]

                    version = (byte0 >> 4) & 0x0F
                    header_size = (byte0 & 0x0F) * 4
                    message_type = (byte1 >> 4) & 0x0F
                    flags = byte1 & 0x0F
                    serialization = (byte2 >> 4) & 0x0F
                    compression = byte2 & 0x0F

                    # 解析 event number (4 bytes)
                    if len(message) >= 12:
                        event_num = int.from_bytes(message[4:8], 'big')

                        # 解析 payload length
                        payload_len = int.from_bytes(message[8:12], 'big')

                        # 解析 payload
                        if len(message) >= 12 + payload_len:
                            payload = message[12:12+payload_len]

                            # event 361: PodcastRoundResponse (音频)
                            # event 363: PodcastEnd (包含 audio_url)
                            if event_num == 363:
                                try:
                                    import json
                                    data = json.loads(payload.decode('utf-8'))
                                    meta_info = data.get("meta_info", {})
                                    audio_url = meta_info.get("audio_url", "")
                                    print(f"📥 收到 audio_url: {audio_url[:50]}..." if audio_url else "没有 audio_url")
                                except:
                                    pass

                            # event 152: SessionFinished
                            elif event_num == 152:
                                print("📥 收到 SessionFinished")
                                break

                elif isinstance(message, str):
                    # 文本消息
                    print(f"📥 收到文本消息: {message[:100]}")

            except Exception as e:
                print(f"接收消息错误: {e}")
                break

        return audio_url

    async def _send_finish_session(self, ws):
        """发送 FinishSession 帧"""
        session_id = "session_" + str(datetime.now().timestamp())

        header = bytes([0x11, 0x94, 0x10, 0x00])
        event_type = (1002).to_bytes(4, 'big')  # FinishSession
        session_id_bytes = session_id.encode('utf-8')
        session_id_len = len(session_id_bytes).to_bytes(4, 'big')
        payload = b"{}"
        payload_len = len(payload).to_bytes(4, 'big')

        frame = header + event_type + session_id_len + session_id_bytes + payload_len + payload

        await ws.send(frame)
        print("📤 已发送 FinishSession 帧")

    async def _send_finish_connection(self, ws):
        """发送 FinishConnection 帧"""
        header = bytes([0x11, 0x94, 0x10, 0x00])
        event_type = (2).to_bytes(4, 'big')  # FinishConnection
        payload = b"{}"
        payload_len = len(payload).to_bytes(4, 'big')

        frame = header + event_type + payload_len + payload

        await ws.send(frame)
        print("📤 已发送 FinishConnection 帧")
