#!/usr/bin/env python3
"""
GitHub Actions 自动研究收集脚本

环境变量:
    FEISHU_APP_ID - 飞书应用 ID
    FEISHU_APP_SECRET - 飞书应用 Secret
    FEISHU_USER_OPEN_ID - 接收消息的用户的 Open ID
    TOPIC - 研究主题 (默认: AI Agent)
    ARXIV_COUNT - arXiv 论文数量 (默认: 10)
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime
from xml.etree import ElementTree as ET
from typing import List, Dict, Any, Optional

try:
    import lark_oapi as lark
except ImportError:
    print("❌ 未安装 lark-oapi")
    sys.exit(1)


def log(message: str):
    """日志输出"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")


def search_arxiv(query: str, max_results: int = 10) -> List[Dict]:
    """搜索 arXiv 论文"""
    base_url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending"
    }
    
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    
    try:
        log(f"🔍 搜索 arXiv: {query}")
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read()
        
        root = ET.fromstring(data)
        ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}
        papers = []
        
        for entry in root.findall('atom:entry', ns):
            title_elem = entry.find('atom:title', ns)
            paper_title = title_elem.text.strip() if title_elem is not None else ""
            paper_title = ' '.join(paper_title.split())
            
            authors = []
            for author in entry.findall('atom:author', ns):
                name_elem = author.find('atom:name', ns)
                if name_elem is not None:
                    authors.append(name_elem.text)
            
            summary_elem = entry.find('atom:summary', ns)
            summary = summary_elem.text.strip() if summary_elem is not None else ""
            
            links = {}
            for link in entry.findall('atom:link', ns):
                rel = link.get('rel', '')
                href = link.get('href', '')
                if rel == 'alternate':
                    links['abstract'] = href
            
            published_elem = entry.find('atom:published', ns)
            published = published_elem.text[:10] if published_elem is not None else ""
            
            papers.append({
                'title': paper_title,
                'authors': authors[:3],
                'summary': summary[:400] + '...' if len(summary) > 400 else summary,
                'published': published,
                'url': links.get('abstract', '')
            })
        
        log(f"✅ 找到 {len(papers)} 篇论文")
        return papers
    
    except Exception as e:
        log(f"❌ arXiv 搜索失败: {e}")
        return []


def generate_report(topic: str, papers: List[Dict]) -> str:
    """生成研究报告"""
    today = datetime.now().strftime('%Y年%m月%d日')
    
    lines = []
    lines.append(f"# {topic} - 每日研究简报")
    lines.append("")
    lines.append(f"📅 **收集日期**: {today}")
    lines.append(f"📊 **论文数量**: {len(papers)} 篇")
    lines.append("")
    
    # 数据概览
    lines.append("## 📊 数据概览")
    lines.append(f"- arXiv 最新论文: {len(papers)} 篇")
    lines.append("")
    
    # 论文列表
    lines.append("## 📑 最新论文")
    lines.append("")
    
    if papers:
        for i, paper in enumerate(papers[:10], 1):
            lines.append(f"### {i}. {paper.get('title', 'N/A')}")
            
            authors = paper.get('authors', [])
            author_str = ', '.join(authors)
            lines.append(f"**作者**: {author_str}")
            lines.append(f"**发布时间**: {paper.get('published', 'N/A')}")
            
            summary = paper.get('summary', '')
            lines.append(f"**摘要**: {summary}")
            
            url = paper.get('url', '')
            if url:
                lines.append(f"**链接**: [{url}]({url})")
            
            lines.append("")
    else:
        lines.append("*暂无相关论文*")
        lines.append("")
    
    # 页脚
    lines.append("---")
    lines.append("")
    lines.append(f"*本报告由 GitHub Actions 自动生成*")
    lines.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    
    return '\n'.join(lines)


def create_feishu_doc(client: lark.Client, title: str, content: str) -> Optional[str]:
    """创建飞书文档"""
    # 创建空文档
    request = lark.BaseRequest.builder() \
        .http_method(lark.HttpMethod.POST) \
        .uri("/open-apis/docx/v1/documents") \
        .token_types({lark.AccessTokenType.TENANT}) \
        .body({"title": title}) \
        .build()
    
    response = client.request(request)
    
    if not response.success():
        try:
            err_data = json.loads(response.raw.content)
            log(f"❌ 创建文档失败: {err_data}")
        except:
            log(f"❌ 创建文档失败: {response.code}")
        return None
    
    try:
        resp_data = json.loads(response.raw.content)
        doc_id = resp_data.get("data", {}).get("document", {}).get("document_id")
    except:
        log("❌ 解析响应失败")
        return None
    
    log(f"✅ 文档创建成功: {doc_id}")
    
    # 获取页面块 ID
    request = lark.BaseRequest.builder() \
        .http_method(lark.HttpMethod.GET) \
        .uri(f"/open-apis/docx/v1/documents/{doc_id}/blocks?page_size=1") \
        .token_types({lark.AccessTokenType.TENANT}) \
        .build()
    
    response = client.request(request)
    
    if not response.success():
        return doc_id
    
    try:
        resp_data = json.loads(response.raw.content)
        items = resp_data.get("data", {}).get("items", [])
        if not items:
            return doc_id
        page_block_id = items[0].get("block_id")
    except:
        return doc_id
    
    # 转换内容为块
    blocks = []
    for line in content.split('\n'):
        line = line.rstrip()
        if not line:
            continue
        
        if line.startswith('# '):
            blocks.append({
                "block_type": 3,
                "heading1": {"elements": [{"text_run": {"content": line[2:].strip()}}]}
            })
        elif line.startswith('## '):
            blocks.append({
                "block_type": 4,
                "heading2": {"elements": [{"text_run": {"content": line[3:].strip()}}]}
            })
        elif line.startswith('### '):
            blocks.append({
                "block_type": 5,
                "heading3": {"elements": [{"text_run": {"content": line[4:].strip()}}]}
            })
        elif line.startswith('- ') or line.startswith('* '):
            blocks.append({
                "block_type": 12,
                "bullet": {"elements": [{"text_run": {"content": line[2:].strip()}}]}
            })
        elif line.startswith('---'):
            blocks.append({"block_type": 16, "divider": {}})
        else:
            blocks.append({
                "block_type": 2,
                "text": {"elements": [{"text_run": {"content": line}}]}
            })
    
    # 分批添加内容
    batch_size = 50
    for i in range(0, len(blocks), batch_size):
        batch = blocks[i:i + batch_size]
        
        request = lark.BaseRequest.builder() \
            .http_method(lark.HttpMethod.POST) \
            .uri(f"/open-apis/docx/v1/documents/{doc_id}/blocks/{page_block_id}/children") \
            .token_types({lark.AccessTokenType.TENANT}) \
            .body({"index": -1, "children": batch}) \
            .build()
        
        client.request(request)
        
        if i + batch_size < len(blocks):
            time.sleep(0.5)
    
    log(f"✅ 添加了 {len(blocks)} 个内容块")
    return doc_id


def send_notification(client: lark.Client, user_id: str, topic: str, doc_id: str):
    """发送消息通知"""
    doc_url = f"https://www.feishu.cn/docx/{doc_id}"
    
    # 构建卡片消息
    message = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "📚 每日研究简报"},
            "template": "green"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**《{topic} - 每日研究简报》** 已生成"
                }
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"⏰ 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                }
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "📖 查看报告"},
                        "type": "primary",
                        "url": doc_url
                    }
                ]
            }
        ]
    }
    
    request = lark.BaseRequest.builder() \
        .http_method(lark.HttpMethod.POST) \
        .uri("/open-apis/im/v1/messages?receive_id_type=open_id") \
        .token_types({lark.AccessTokenType.TENANT}) \
        .body({
            "receive_id": user_id,
            "msg_type": "interactive",
            "content": json.dumps(message)
        }) \
        .build()
    
    response = client.request(request)
    
    if response.success():
        log("✅ 消息通知已发送")
    else:
        try:
            err_data = json.loads(response.raw.content)
            log(f"⚠️  发送消息失败: {err_data}")
        except:
            log(f"⚠️  发送消息失败: {response.code}")


def main():
    log("=" * 70)
    log("🤖 GitHub Actions - 自动研究收集")
    log("=" * 70)
    
    # 读取环境变量
    app_id = os.environ.get('FEISHU_APP_ID')
    app_secret = os.environ.get('FEISHU_APP_SECRET')
    user_id = os.environ.get('FEISHU_USER_OPEN_ID')
    topic = os.environ.get('TOPIC', 'AI Agent')
    arxiv_count = int(os.environ.get('ARXIV_COUNT', '10'))
    
    log(f"📌 主题: {topic}")
    log(f"📊 数量: {arxiv_count}")
    log("")
    
    # 检查凭证
    if not app_id or not app_secret:
        log("❌ 未找到飞书应用凭证")
        sys.exit(1)
    
    # 创建客户端
    client = lark.Client.builder() \
        .app_id(app_id) \
        .app_secret(app_secret) \
        .log_level(lark.LogLevel.ERROR) \
        .build()
    
    # 1. 搜索 arXiv
    papers = search_arxiv(topic, arxiv_count)
    
    # 2. 生成报告
    log("📝 生成研究报告...")
    today_str = datetime.now().strftime('%Y%m%d')
    report = generate_report(topic, papers)
    doc_title = f"{topic} - 每日研究简报 {today_str}"
    
    # 保存报告到文件（用于 GitHub Actions 上传）
    with open('research_report.md', 'w', encoding='utf-8') as f:
        f.write(report)
    log("✅ 报告已保存到 research_report.md")
    
    # 3. 创建飞书文档
    log("📄 创建飞书文档...")
    doc_id = create_feishu_doc(client, doc_title, report)
    
    if doc_id:
        doc_url = f"https://www.feishu.cn/docx/{doc_id}"
        log(f"✅ 文档创建成功: {doc_url}")
        
        # 保存文档信息
        with open('doc_info.json', 'w') as f:
            json.dump({'doc_id': doc_id, 'doc_url': doc_url, 'title': doc_title}, f)
        
        # 4. 发送通知
        if user_id:
            log("📤 发送消息通知...")
            send_notification(client, user_id, topic, doc_id)
        else:
            log("⚠️  未设置用户 Open ID，跳过消息通知")
    else:
        log("❌ 文档创建失败")
        sys.exit(1)
    
    log("")
    log("=" * 70)
    log("✅ 任务完成")
    log("=" * 70)


if __name__ == '__main__':
    main()
