#!/usr/bin/env python3
"""
为 GitHub Trends 创建飞书文档

复用现有逻辑，但读取 GitHub Trends 分析文件
"""

import os
import sys
import json
import urllib.request
import urllib.error
import time


def get_feishu_token(app_id, app_secret):
    """获取飞书 tenant access token"""
    print("🔑 获取飞书 access token...")
    
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = json.dumps({
        "app_id": app_id,
        "app_secret": app_secret
    }).encode('utf-8')
    
    headers = {'Content-Type': 'application/json'}
    
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            
        if result.get('code') != 0:
            print(f"❌ 获取 token 失败: {result.get('msg')}")
            return None
        
        token = result.get('tenant_access_token')
        print("✅ Token 获取成功")
        return token
        
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None


def create_document(token, title):
    """创建飞书文档"""
    print(f"📄 创建飞书文档: {title}...")
    
    url = "https://open.feishu.cn/open-apis/docx/v1/documents"
    
    data = json.dumps({"title": title}).encode('utf-8')
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
        
        if result.get('code') != 0:
            print(f"❌ 创建文档失败: {result.get('msg')}")
            return None
        
        data = result.get('data', {})
        doc_data = data.get('document', {}) if isinstance(data, dict) else {}
        doc_id = doc_data.get('document_id')
        
        if not doc_id:
            print(f"❌ 无法获取文档 ID")
            return None
        
        doc_url = f"https://my.feishu.cn/docx/{doc_id}"
        
        print(f"✅ 文档创建成功: {doc_id}")
        
        return {
            'document_id': doc_id,
            'document_url': doc_url
        }
        
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None


def get_page_block_id(token, doc_id):
    """获取文档的页面块 ID"""
    print("🔍 获取页面块 ID...")
    
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks?page_size=1"
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers, method='GET')
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
        
        if result.get('code') != 0:
            print(f"❌ 获取页面块失败: {result.get('msg')}")
            return None
        
        items = result.get('data', {}).get('items', [])
        if not items:
            print("❌ 没有找到页面块")
            return None
        
        page_block_id = items[0].get('block_id')
        print(f"✅ 页面块 ID: {page_block_id[:20]}...")
        return page_block_id
        
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None


def add_document_content(token, doc_id, page_block_id, content):
    """添加文档内容"""
    print("📝 写入文档内容...")
    print(f"   内容长度: {len(content)} 字符")
    
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{page_block_id}/children"
    
    # 转换内容为块
    blocks = []
    
    for line in content.split('\n'):
        line = line.rstrip()
        if not line:
            continue
        
        if line.startswith('# '):
            # 标题1 - block_type 3
            blocks.append({
                "block_type": 3,
                "heading1": {"elements": [{"text_run": {"content": line[2:].strip()}}]}
            })
        elif line.startswith('## '):
            # 标题2 - block_type 4
            blocks.append({
                "block_type": 4,
                "heading2": {"elements": [{"text_run": {"content": line[3:].strip()}}]}
            })
        elif line.startswith('### '):
            # 标题3 - block_type 5
            blocks.append({
                "block_type": 5,
                "heading3": {"elements": [{"text_run": {"content": line[4:].strip()}}]}
            })
        elif line.startswith('- ') or line.startswith('* '):
            # 无序列表 - block_type 12
            text = line[2:].strip()
            text = text.replace('**', '').replace('*', '').replace('`', '')
            blocks.append({
                "block_type": 12,
                "bullet": {"elements": [{"text_run": {"content": text}}]}
            })
        elif line.startswith('──────────'):
            # 分割线
            blocks.append({
                "block_type": 2,
                "text": {"elements": [{"text_run": {"content": "──────────"}}]}
            })
        else:
            # 普通文本 - block_type 2
            text = line.replace('**', '').replace('*', '').replace('`', '')
            if text:
                blocks.append({
                    "block_type": 2,
                    "text": {"elements": [{"text_run": {"content": text}}]}
                })
    
    if not blocks:
        print("⚠️  没有内容可写入")
        return True
    
    print(f"   准备写入 {len(blocks)} 个块...")
    
    # 分批添加内容
    batch_size = 50
    total_written = 0
    
    for i in range(0, len(blocks), batch_size):
        batch = blocks[i:i + batch_size]
        
        request_body = {
            "index": -1,
            "children": batch
        }
        
        data = json.dumps(request_body, ensure_ascii=False).encode('utf-8')
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))
            
            if result.get('code') != 0:
                print(f"❌ 写入内容失败: {result.get('msg')}")
                return False
            
            total_written += len(batch)
            print(f"   已写入批次 {i//batch_size + 1}: {len(batch)} 个块")
            
            if i + batch_size < len(blocks):
                time.sleep(0.5)
            
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            print(f"❌ HTTP 错误 {e.code}: {error_body[:500]}")
            return False
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            return False
    
    print(f"✅ 文档内容写入完成 (共 {total_written} 个块)")
    return True


def load_analysis():
    """加载 GitHub Trends 分析报告"""
    # 尝试读取 GitHub Trends 分析文件
    try:
        if os.path.exists('latest_github_trends_analysis.md'):
            print("   读取 latest_github_trends_analysis.md...")
            with open('latest_github_trends_analysis.md', 'r', encoding='utf-8') as f:
                content = f.read()
            if content.strip():
                print(f"   ✅ 文件大小: {len(content)} 字符")
                return content
    except Exception as e:
        print(f"   ❌ 读取失败: {e}")
    
    # 查找其他分析文件
    import glob
    files = glob.glob('github_trends_analysis_*.md')
    if files:
        latest = max(files, key=os.path.getctime)
        try:
            print(f"   读取 {latest}...")
            with open(latest, 'r', encoding='utf-8') as f:
                content = f.read()
            if content.strip():
                print(f"   ✅ 文件大小: {len(content)} 字符")
                return content
        except Exception as e:
            print(f"   ❌ 读取失败: {e}")
    
    # 如果没有分析文件，使用原始报告
    try:
        if os.path.exists('latest_github_trends.md'):
            print("   读取 latest_github_trends.md (原始报告)...")
            with open('latest_github_trends.md', 'r', encoding='utf-8') as f:
                content = f.read()
            if content.strip():
                print(f"   ✅ 文件大小: {len(content)} 字符")
                return content
    except Exception as e:
        print(f"   ❌ 读取失败: {e}")
    
    print("   ❌ 没有找到报告文件")
    return None


def main():
    print("=" * 70)
    print("📄 创建 GitHub Trends 飞书文档")
    print("=" * 70)
    
    # 获取环境变量
    app_id = os.environ.get('FEISHU_APP_ID')
    app_secret = os.environ.get('FEISHU_APP_SECRET')
    
    if not all([app_id, app_secret]):
        print("❌ 缺少必要的环境变量:")
        if not app_id:
            print("   - FEISHU_APP_ID")
        if not app_secret:
            print("   - FEISHU_APP_SECRET")
        return 1
    
    # 加载分析报告
    content = load_analysis()
    if not content:
        print("❌ 没有内容可写入")
        return 1
    
    print(f"内容长度: {len(content)} 字符")
    print()
    
    # 获取 token
    token = get_feishu_token(app_id, app_secret)
    if not token:
        return 1
    
    from datetime import datetime
    doc_title = f"🔥 GitHub Trends AI 分析报告 {datetime.now().strftime('%Y-%m-%d')}"
    
    # 创建文档
    doc_info = create_document(token, doc_title)
    if not doc_info:
        return 1
    
    # 获取页面块 ID
    page_block_id = get_page_block_id(token, doc_info['document_id'])
    if not page_block_id:
        print("⚠️  无法获取页面块 ID，尝试使用文档 ID...")
        page_block_id = doc_info['document_id']
    
    # 添加内容
    if not add_document_content(token, doc_info['document_id'], page_block_id, content):
        print("⚠️  文档内容写入失败，但文档已创建")
    
    # 保存文档信息供通知脚本使用
    with open('doc_info.json', 'w') as f:
        json.dump({
            'doc_id': doc_info['document_id'],
            'doc_url': doc_info['document_url'],
            'title': doc_title
        }, f)
    
    print("\n" + "=" * 70)
    print("✅ 飞书文档创建完成")
    print(f"📖 文档链接: {doc_info['document_url']}")
    print("=" * 70)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
