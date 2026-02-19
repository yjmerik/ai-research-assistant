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

# 历史记录文件
import os
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(SCRIPT_DIR, 'github_trends_history.json')


def load_history():
    """加载已处理的项目历史记录"""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️  加载历史记录失败: {e}")
    return {'processed_projects': [], 'last_update': ''}


def save_history(history):
    """保存已处理的项目历史记录"""
    try:
        history['last_update'] = datetime.now().isoformat()
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        print(f"💾 历史记录已保存 ({len(history['processed_projects'])} 个项目)")
    except Exception as e:
        print(f"⚠️  保存历史记录失败: {e}")


def filter_new_projects(projects, history):
    """过滤掉已处理过的项目"""
    processed = set(history.get('processed_projects', []))
    new_projects = []
    skipped = 0
    
    for project in projects:
        project_id = project.get('full_name', '')
        if project_id and project_id not in processed:
            new_projects.append(project)
        else:
            skipped += 1
    
    print(f"📊 项目统计: 新发现 {len(new_projects)} 个, 已跳过 {skipped} 个已处理项目")
    return new_projects


def add_to_history(projects, history):
    """将新项目添加到历史记录"""
    processed = history.get('processed_projects', [])
    for project in projects:
        project_id = project.get('full_name', '')
        if project_id and project_id not in processed:
            processed.append(project_id)
    
    # 只保留最近 500 个项目的历史记录（避免文件过大）
    if len(processed) > 500:
        processed = processed[-500:]
        print(f"🧹 历史记录已清理，保留最近 500 个项目")
    
    history['processed_projects'] = processed
    return history


def get_trending_repositories(language=None, since='daily', count=50):
    """
    获取与 AI Agent 相关的 GitHub Trending 项目
    
    搜索近期获得 stars 最多的 AI Agent 相关项目（真正的热门项目）
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
    
    # 构建 AI Agent 相关的关键词查询
    # 搜索近期有推送、且 stars 数较多的项目
    # 使用 stars:>10 过滤掉 0 star 的项目
    query = "(agent OR ai-agent OR llm-agent OR autonomous-agent) stars:>10 pushed:>" + date
    
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
    filename = os.path.join(SCRIPT_DIR, f"github_trends_{since}_{timestamp}.json")
    
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
    with open(os.path.join(SCRIPT_DIR, 'latest_github_trends.json'), 'w', encoding='utf-8') as f:
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
    filename = os.path.join(SCRIPT_DIR, f"github_trends_report_{datetime.now().strftime('%Y%m%d')}.md")
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    # 同时保存为最新文件
    with open(os.path.join(SCRIPT_DIR, 'latest_github_trends.md'), 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"💾 报告已保存: {filename}")
    return report


def main():
    print("=" * 70)
    print("🔥 GitHub Trends 收集器 (智能去重版)")
    print("=" * 70)
    
    # 获取环境变量
    since = os.environ.get('TRENDS_SINCE', 'daily')
    count = int(os.environ.get('TRENDS_COUNT', '50'))
    language = os.environ.get('TRENDS_LANGUAGE', '')
    
    print(f"时间范围: {since}")
    print(f"项目数量: {count}")
    print(f"语言筛选: {language or 'All'}")
    print()
    
    # 加载历史记录
    print("📚 加载历史记录...")
    history = load_history()
    print(f"   已处理过 {len(history.get('processed_projects', []))} 个项目")
    print()
    
    # 获取趋势项目（获取更多以便过滤后有足够的项目）
    fetch_count = count * 3  # 获取3倍数量的项目用于过滤
    print(f"🔍 正在获取项目 (目标: {count} 个新项目)...")
    projects = get_trending_repositories(language=language or None, since=since, count=fetch_count)
    
    if not projects:
        print("❌ 未找到项目")
        return 1
    
    # 过滤掉已处理过的项目
    print("\n🔍 过滤已处理的项目...")
    new_projects = filter_new_projects(projects, history)
    
    # 如果新项目不足，给出提示
    if len(new_projects) < count:
        print(f"⚠️  警告: 只有 {len(new_projects)} 个新项目（目标 {count} 个）")
        if len(new_projects) == 0:
            print("💡 建议: 所有项目都已处理过，可以尝试扩大时间范围（weekly/monthly）")
    
    # 取前 count 个项目
    new_projects = new_projects[:count]
    
    print(f"\n✅ 本次将处理 {len(new_projects)} 个新项目")
    
    # 更新历史记录
    history = add_to_history(new_projects, history)
    save_history(history)
    
    # 保存项目数据
    save_projects(new_projects, since)
    
    # 生成报告
    report = generate_markdown_report(new_projects, since)
    
    # 设置 GitHub Actions 输出
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"project_count={len(new_projects)}\n")
            f.write(f"report_file=latest_github_trends.md\n")
    
    print("\n✅ GitHub Trends 收集完成")
    return 0


if __name__ == '__main__':
    sys.exit(main())
