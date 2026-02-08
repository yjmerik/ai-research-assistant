#!/usr/bin/env python3
"""
获取 GitHub Trends Top 50 项目

使用 GitHub API 获取趋势项目
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta


def get_trending_repositories(language=None, since='daily', count=50):
    """
    获取与 AI Agent 相关的 GitHub Trending 项目
    
    使用 GitHub Search API 搜索 AI Agent 相关的热门项目
    """
    print(f"🔍 获取 AI Agent GitHub Trends (语言: {language or 'All'}, 时间: {since})...")
    
    # 计算日期范围
    if since == 'daily':
        days_ago = 1
    elif since == 'weekly':
        days_ago = 7
    else:
        days_ago = 30
    
    date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
    
    # 构建 AI Agent 相关的关键词查询（限制在5个以内）
    # GitHub API 限制: 最多5个 AND/OR/NOT 操作符
    query = f"(agent in:name,description OR ai-agent in:name,description OR llm-agent in:name,description) created:>{date}"
    
    if language:
        query += f" language:{language}"
    
    # GitHub Search API
    url = f"https://api.github.com/search/repositories"
    params = f"?q={urllib.parse.quote(query)}&sort=stars&order=desc&per_page={count}"
    
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'GitHub-Trends-Bot'
    }
    
    # 如果有 GitHub Token，添加到请求头（提高 API 限制）
    github_token = os.environ.get('GH_TOKEN')
    if github_token:
        headers['Authorization'] = f'token {github_token}'
    
    try:
        req = urllib.request.Request(url + params, headers=headers, method='GET')
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
        
        items = result.get('items', [])
        print(f"✅ 找到 {len(items)} 个项目")
        
        # 简化项目信息
        projects = []
        for item in items:
            projects.append({
                'name': item.get('name', 'N/A'),
                'full_name': item.get('full_name', 'N/A'),
                'description': item.get('description', 'No description'),
                'url': item.get('html_url', ''),
                'stars': item.get('stargazers_count', 0),
                'language': item.get('language', 'Unknown'),
                'created_at': item.get('created_at', '')[:10],
                'topics': item.get('topics', [])[:5],  # 只取前5个话题
                'owner': item.get('owner', {}).get('login', ''),
                'homepage': item.get('homepage', '')
            })
        
        return projects
        
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"❌ HTTP 错误 {e.code}: {error_body[:500]}")
        return []
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return []


def save_projects(projects, since='daily'):
    """保存项目到文件"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"github_trends_{since}_{timestamp}.json"
    
    data = {
        'date': datetime.now().isoformat(),
        'since': since,
        'count': len(projects),
        'projects': projects
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 项目数据已保存: {filename}")
    
    # 同时保存为最新文件
    with open('latest_github_trends.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return filename


def generate_markdown_report(projects, since='daily'):
    """生成 Markdown 格式报告"""
    from datetime import datetime
    
    lines = []
    lines.append(f"# 🤖 AI Agent GitHub Trends Top {len(projects)} - {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append(f"📅 **收集日期**: {datetime.now().strftime('%Y年%m月%d日')}")
    lines.append(f"📊 **时间范围**: {since}")
    lines.append(f"⭐ **项目数量**: {len(projects)}")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    for i, project in enumerate(projects, 1):
        lines.append(f"## {i}. {project['full_name']}")
        lines.append("")
        lines.append(f"⭐ **Stars**: {project['stars']:,}")
        lines.append("")
        lines.append(f"📝 **描述**: {project['description']}")
        lines.append("")
        lines.append(f"🔧 **语言**: {project['language']}")
        lines.append("")
        lines.append(f"📅 **创建日期**: {project['created_at']}")
        lines.append("")
        
        if project['topics']:
            lines.append(f"🏷️ **标签**: {', '.join(project['topics'])}")
            lines.append("")
        
        lines.append(f"🔗 **GitHub**: {project['url']}")
        
        if project['homepage']:
            lines.append("")
            lines.append(f"🌐 **主页**: {project['homepage']}")
        
        lines.append("")
        lines.append("---")
        lines.append("")
    
    report = '\n'.join(lines)
    
    # 保存报告
    filename = f"github_trends_report_{datetime.now().strftime('%Y%m%d')}.md"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    # 同时保存为最新文件
    with open('latest_github_trends.md', 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"💾 报告已保存: {filename}")
    return report


def main():
    print("=" * 70)
    print("🔥 GitHub Trends 收集器")
    print("=" * 70)
    
    # 获取环境变量
    since = os.environ.get('TRENDS_SINCE', 'daily')
    count = int(os.environ.get('TRENDS_COUNT', '50'))
    language = os.environ.get('TRENDS_LANGUAGE', '')
    
    print(f"时间范围: {since}")
    print(f"项目数量: {count}")
    print(f"语言筛选: {language or 'All'}")
    print()
    
    # 获取趋势项目
    projects = get_trending_repositories(language=language or None, since=since, count=count)
    
    if not projects:
        print("❌ 未找到项目")
        return 1
    
    # 保存项目数据
    save_projects(projects, since)
    
    # 生成报告
    report = generate_markdown_report(projects, since)
    
    # 设置 GitHub Actions 输出
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"project_count={len(projects)}\n")
            f.write(f"report_file=latest_github_trends.md\n")
    
    print("\n✅ GitHub Trends 收集完成")
    return 0


if __name__ == '__main__':
    sys.exit(main())
