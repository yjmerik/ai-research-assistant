#!/usr/bin/env python3
"""
使用 Kimi API 分析 GitHub Trends 项目

对每个项目进行 AI 总结
"""

import os
import sys
import json
import urllib.request
import urllib.error

# Kimi API 配置
KIMI_API_BASE = "https://api.moonshot.cn/v1"


class KimiAnalyzer:
    """Kimi 项目分析器"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get('KIMI_API_KEY')
        
    def _request(self, endpoint, data):
        """发送 HTTP 请求"""
        url = f"{KIMI_API_BASE}{endpoint}"
        
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
    
    def analyze_project(self, project):
        """分析单个项目"""
        name = project.get('full_name', 'N/A')
        description = project.get('description', 'No description')
        language = project.get('language', 'Unknown')
        topics = project.get('topics', [])
        url = project.get('url', '')
        
        prompt = f"""请对以下 GitHub 项目进行简要分析：

项目名称: {name}
描述: {description}
主要语言: {language}
标签: {', '.join(topics)}
GitHub地址: {url}

请用中文输出以下内容：
1. 一句话概括这个项目的核心功能
2. 这个项目解决了什么问题
3. 主要技术特点
4. 适用场景
5. 值得关注的亮点

字数控制在 150 字以内，简洁明了。"""

        data = {
            "model": "moonshot-v1-8k",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一位技术分析师，擅长快速理解开源项目并给出简洁准确的总结。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        result = self._request('/chat/completions', data)
        
        if 'error' in result:
            print(f"   ⚠️  API 错误: {result['error']}")
            return None
        
        try:
            content = result['choices'][0]['message']['content']
            return content
        except Exception as e:
            print(f"   ⚠️  解析失败: {e}")
            return None
    
    def analyze_projects_batch(self, projects):
        """批量分析项目"""
        print(f"🤖 使用 Kimi API 分析 {len(projects)} 个项目...")
        print()
        
        results = []
        
        for i, project in enumerate(projects, 1):
            print(f"[{i}/{len(projects)}] 分析 {project['full_name']}...")
            
            analysis = self.analyze_project(project)
            
            if analysis:
                results.append({
                    'project': project,
                    'analysis': analysis
                })
            else:
                # 如果 API 失败，使用基本信息
                results.append({
                    'project': project,
                    'analysis': f"项目描述: {project.get('description', 'N/A')}\n主要语言: {project.get('language', 'Unknown')}\n⭐ Stars: {project.get('stars', 0)}"
                })
            
            # 每 5 个项目暂停一下，避免 API 限制
            if i % 5 == 0 and i < len(projects):
                print("   ⏳ 暂停 1 秒...")
                import time
                time.sleep(1)
        
        print(f"\n✅ 完成 {len(results)} 个项目分析")
        return results


def load_projects():
    """加载项目数据"""
    try:
        with open('latest_github_trends.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        pass
    
    import glob
    files = glob.glob('github_trends_*.json')
    if files:
        latest = max(files, key=os.path.getctime)
        with open(latest, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    return None


def generate_analysis_report(results, since='daily'):
    """生成分析报告"""
    from datetime import datetime
    
    lines = []
    lines.append(f"# 🤖 AI Agent GitHub Trends AI 分析报告 - {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append(f"📅 **生成日期**: {datetime.now().strftime('%Y年%m月%d日')}")
    lines.append(f"📊 **时间范围**: {since}")
    lines.append(f"🔢 **项目数量**: {len(results)}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("🤖 **AI 分析**: 本报告由 Kimi AI 自动生成")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    for i, result in enumerate(results, 1):
        project = result['project']
        analysis = result['analysis']
        
        lines.append(f"## {i}. {project['full_name']}")
        lines.append("")
        lines.append(f"⭐ **Stars**: {project['stars']:,}")
        lines.append("")
        lines.append(f"🔧 **语言**: {project['language']}")
        lines.append("")
        
        if project['topics']:
            lines.append(f"🏷️ **标签**: {', '.join(project['topics'])}")
            lines.append("")
        
        lines.append("### 🤖 AI 总结")
        lines.append("")
        lines.append(analysis)
        lines.append("")
        
        lines.append("### 🔗 链接")
        lines.append("")
        lines.append(f"- **GitHub**: {project['url']}")
        
        if project['homepage']:
            lines.append(f"- **官网**: {project['homepage']}")
        
        lines.append("")
        lines.append("──────────")
        lines.append("")
    
    report = '\n'.join(lines)
    
    # 保存报告
    timestamp = datetime.now().strftime('%Y%m%d')
    filename = f"github_trends_analysis_{timestamp}.md"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    # 同时保存为最新文件
    with open('latest_github_trends_analysis.md', 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"💾 分析报告已保存: {filename}")
    return report


def main():
    print("=" * 70)
    print("🤖 GitHub Trends AI 分析")
    print("=" * 70)
    
    # 获取环境变量
    api_key = os.environ.get('KIMI_API_KEY')
    
    if not api_key:
        print("❌ 缺少 KIMI_API_KEY 环境变量")
        return 1
    
    # 加载项目数据
    data = load_projects()
    if not data:
        print("❌ 没有找到项目数据")
        return 1
    
    projects = data.get('projects', [])
    since = data.get('since', 'daily')
    
    print(f"时间范围: {since}")
    print(f"项目数量: {len(projects)}")
    print()
    
    # 创建分析器
    analyzer = KimiAnalyzer(api_key)
    
    # 分析项目
    results = analyzer.analyze_projects_batch(projects)
    
    # 生成报告
    report = generate_analysis_report(results, since)
    
    # 设置 GitHub Actions 输出
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"analysis_file=latest_github_trends_analysis.md\n")
            f.write(f"analysis_length={len(report)}\n")
    
    print("\n✅ AI 分析完成")
    return 0


if __name__ == '__main__':
    sys.exit(main())
