#!/usr/bin/env python3
"""
搜索 arXiv 论文并保存结果
"""

import os
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime


def search_arxiv(topic, count=10):
    """搜索 arXiv 论文"""
    print(f"🔍 搜索 arXiv: {topic} (数量: {count})")
    
    query = urllib.parse.quote(topic)
    url = (
        f"http://export.arxiv.org/api/query?"
        f"search_query=all:{query}&"
        f"start=0&"
        f"max_results={count}&"
        f"sortBy=submittedDate&"
        f"sortOrder=descending"
    )
    
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (GitHub Actions Bot)'
            }
        )
        
        with urllib.request.urlopen(req, timeout=60) as response:
            xml_data = response.read().decode('utf-8')
            
        # 解析 XML
        papers = parse_arxiv_xml(xml_data)
        print(f"✅ 找到 {len(papers)} 篇论文")
        return papers
        
    except Exception as e:
        print(f"❌ 搜索失败: {e}")
        return []


def parse_arxiv_xml(xml_data):
    """解析 arXiv XML"""
    import xml.etree.ElementTree as ET
    
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    
    try:
        root = ET.fromstring(xml_data)
        papers = []
        
        for entry in root.findall('atom:entry', ns):
            # 标题
            title_elem = entry.find('atom:title', ns)
            title = title_elem.text.strip() if title_elem else ''
            title = ' '.join(title.split())
            
            # 作者
            authors = []
            for author in entry.findall('atom:author', ns):
                name_elem = author.find('atom:name', ns)
                if name_elem:
                    authors.append(name_elem.text)
            
            # 摘要
            summary_elem = entry.find('atom:summary', ns)
            summary = summary_elem.text.strip() if summary_elem else ''
            
            # 链接
            url = ''
            for link in entry.findall('atom:link', ns):
                if link.get('rel') == 'alternate':
                    url = link.get('href', '')
                    break
            
            # 发布时间
            published_elem = entry.find('atom:published', ns)
            published = published_elem.text[:10] if published_elem else ''
            
            papers.append({
                'title': title,
                'authors': authors,
                'summary': summary,
                'url': url,
                'published': published
            })
        
        return papers
        
    except Exception as e:
        print(f"❌ 解析失败: {e}")
        return []


def save_papers(papers, topic):
    """保存论文到文件"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"papers_{timestamp}.json"
    
    data = {
        'topic': topic,
        'timestamp': timestamp,
        'count': len(papers),
        'papers': papers
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 论文已保存: {filename}")
    return filename


def main():
    topic = os.environ.get('TOPIC', 'AI Agent')
    count = int(os.environ.get('ARXIV_COUNT', '10'))
    
    print("=" * 70)
    print("📚 arXiv 论文搜索")
    print("=" * 70)
    print(f"主题: {topic}")
    print(f"数量: {count}")
    print()
    
    papers = search_arxiv(topic, count)
    
    if papers:
        filename = save_papers(papers, topic)
        
        # 设置 GitHub Actions 输出
        with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
            f.write(f"papers_file={filename}\n")
            f.write(f"paper_count={len(papers)}\n")
        
        # 同时保存为最新文件
        with open('latest_papers.json', 'w', encoding='utf-8') as f:
            json.dump({
                'topic': topic,
                'timestamp': datetime.now().isoformat(),
                'count': len(papers),
                'papers': papers
            }, f, ensure_ascii=False, indent=2)
        
        print("\n✅ 搜索完成")
        return 0
    else:
        print("\n❌ 未找到论文")
        return 1


if __name__ == '__main__':
    sys.exit(main())
