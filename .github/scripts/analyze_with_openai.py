#!/usr/bin/env python3
"""
使用 OpenAI API 进行论文 AI 解读

直接调用 OpenAI API，生成通俗易懂的中文解读
"""

import os
import sys
import json
import urllib.request
import urllib.error

# OpenAI API 配置
OPENAI_API_BASE = "https://api.openai.com/v1"


class OpenAIAnalyzer:
    """OpenAI 论文解读器"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        
    def _request(self, endpoint, data):
        """发送 HTTP 请求"""
        url = f"{OPENAI_API_BASE}{endpoint}"
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(url, data=json_data, headers=headers, method='POST')
        
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            print(f"HTTP Error {e.code}: {error_body}")
            return {'error': error_body}
        except Exception as e:
            return {'error': str(e)}
    
    def analyze_papers(self, papers_data):
        """分析论文并生成解读"""
        topic = papers_data.get('topic', 'AI Agent')
        papers = papers_data.get('papers', [])
        
        print(f"🤖 使用 GPT-4o 进行论文解读...")
        print(f"   主题: {topic}")
        print(f"   论文数: {len(papers)}")
        
        # 构建 prompt
        prompt = self._build_analysis_prompt(topic, papers)
        
        # 调用 OpenAI API
        data = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一位专业的AI研究解读专家，擅长将复杂的学术论文转化为通俗易懂的中文解读。你的使命是让每个人都能轻松理解最前沿的AI研究！"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.8,
            "max_tokens": 4000
        }
        
        result = self._request('/chat/completions', data)
        
        if 'error' in result:
            print(f"❌ API 错误: {result['error']}")
            return None
        
        try:
            content = result['choices'][0]['message']['content']
            return content
        except Exception as e:
            print(f"❌ 解析结果失败: {e}")
            return None
    
    def _build_analysis_prompt(self, topic, papers):
        """构建分析 prompt"""
        prompt = f"""请对以下关于「{topic}」的 {len(papers)} 篇论文进行深度解读。

请按照以下格式为每篇论文提供通俗易懂的解读：

"""
        
        for i, paper in enumerate(papers, 1):
            prompt += f"""
--- 论文 {i} ---

标题: {paper.get('title', 'N/A')}
作者: {', '.join(paper.get('authors', [])[:3])}
发表日期: {paper.get('published', 'N/A')}
摘要: {paper.get('summary', 'N/A')[:1000]}
链接: {paper.get('url', 'N/A')}

"""
        
        prompt += f"""
请按照以下格式输出（使用中文，通俗易懂）：

# {topic} - AI解读版研究简报

## 🌟 今日亮点
用 2-3 句话总结这些论文的核心价值和亮点

## 📖 论文深度解读

"""
        
        for i in range(1, len(papers) + 1):
            prompt += f"""### 论文 {i}

#### 📄 标题
[保留原文标题]

#### 🎯 一句话概括
用一句话通俗地解释这篇论文做了什么（让非专业人士也能听懂）

#### 💡 核心创新点
- 这项技术解决了什么问题？
- 相比之前的方法有什么突破？

#### 🔬 技术原理（通俗版）
用类比、比喻等方式解释技术原理，避免过多专业术语

#### 🎁 实际应用价值
- 这项技术可以用在哪些场景？
- 对普通人/开发者有什么帮助？

---

"""
        
        prompt += """
## 📊 趋势洞察

### 研究热点
列出 3-5 个当前热门研究方向

### 技术趋势
分析技术发展的主要趋势

### 值得关注
推荐最值得深入阅读的 2-3 篇论文及原因

---

要求：
1. 用中文输出，语言通俗易懂
2. 像给朋友讲解一样，使用类比和比喻
3. 适当使用 emoji 增加可读性
4. 突出每篇论文的实际应用价值
5. 避免堆砌专业术语，必要时解释
"""
        
        return prompt


def load_papers():
    """加载论文数据"""
    try:
        with open('latest_papers.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"❌ 加载论文失败: {e}")
        return None


def save_analysis(analysis, topic):
    """保存解读结果"""
    from datetime import datetime
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 保存 Markdown 格式
    md_filename = f"analysis_{timestamp}.md"
    with open(md_filename, 'w', encoding='utf-8') as f:
        f.write(analysis)
    
    print(f"💾 解读已保存: {md_filename}")
    
    # 同时保存为最新文件
    with open('latest_analysis.md', 'w', encoding='utf-8') as f:
        f.write(analysis)
    
    return md_filename


def main():
    print("=" * 70)
    print("🤖 OpenAI 论文解读")
    print("=" * 70)
    
    # 获取环境变量
    api_key = os.environ.get('OPENAI_API_KEY')
    topic = os.environ.get('TOPIC', 'AI Agent')
    
    if not api_key:
        print("❌ 缺少 OPENAI_API_KEY 环境变量")
        return 1
    
    # 加载论文
    papers_data = load_papers()
    if not papers_data:
        print("❌ 没有找到论文数据")
        return 1
    
    print(f"主题: {papers_data.get('topic', topic)}")
    print(f"论文数量: {papers_data.get('count', 0)}")
    print()
    
    # 创建分析器
    analyzer = OpenAIAnalyzer(api_key)
    
    # 分析论文
    analysis = analyzer.analyze_papers(papers_data)
    
    if analysis:
        print("\n" + "=" * 70)
        print("📥 解读结果预览")
        print("=" * 70)
        preview = analysis[:1000] + "..." if len(analysis) > 1000 else analysis
        print(preview)
        print()
        
        # 保存结果
        filename = save_analysis(analysis, papers_data.get('topic', topic))
        
        # 设置 GitHub Actions 输出
        github_output = os.environ.get('GITHUB_OUTPUT')
        if github_output:
            with open(github_output, 'a') as f:
                f.write(f"analysis_file={filename}\n")
                f.write(f"analysis_length={len(analysis)}\n")
        
        print("✅ 解读完成")
        return 0
    else:
        print("❌ 解读失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
