#!/usr/bin/env python3
"""
创建飞书文档并写入解读内容

使用飞书 Doc API 创建文档并添加内容
参考之前成功的 auto_research.py 实现
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
        
        # 解析响应结构: result.data.document
        data = result.get('data', {})
        doc_data = data.get('document', {}) if isinstance(data, dict) else {}
        
        doc_id = doc_data.get('document_id')
        
        if not doc_id:
            print(f"❌ 无法获取文档 ID")
            return None
        
        # 使用用户的飞书域名
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
    """添加文档内容 - 参考之前成功的实现"""
    print("📝 写入文档内容...")
    print(f"   内容长度: {len(content)} 字符")
    
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{page_block_id}/children"
    
    # 转换内容为块 - 使用正确的块类型编号（参考之前成功的脚本）
    # heading1: 3, heading2: 4, heading3: 5, bullet: 12, text: 2, divider: 16
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
            # 移除 markdown 标记
            text = text.replace('**', '').replace('*', '').replace('`', '')
            blocks.append({
                "block_type": 12,
                "bullet": {"elements": [{"text_run": {"content": text}}]}
            })
        elif line.startswith('---'):
            # 分割线 - block_type 16
            blocks.append({"block_type": 16, "divider": {}})
        else:
            # 普通文本 - block_type 2
            # 移除 markdown 标记
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
    
    # 分批添加内容，每批最多 50 个块
    batch_size = 50
    total_written = 0
    
    for i in range(0, len(blocks), batch_size):
        batch = blocks[i:i + batch_size]
        
        request_body = {
            "index": -1,  # 在末尾添加
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
                print(f"   响应: {json.dumps(result, ensure_ascii=False)[:500]}")
                return False
            
            total_written += len(batch)
            print(f"   已写入批次 {i//batch_size + 1}: {len(batch)} 个块")
            
            # 如果还有更多批次，稍作等待
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


def send_notification(token, user_id, doc_id, topic, paper_count):
    """发送飞书消息通知"""
    print("📤 发送飞书通知...")
    
    if not doc_id:
        print("❌ 文档 ID 为空，无法发送通知")
        return False
    
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
    
    from datetime import datetime
    
    # 构建文档链接
    doc_url = f"https://my.feishu.cn/docx/{doc_id}"
    
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"📚 {topic} - 研究简报已生成"},
            "template": "green"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"✅ **{topic}** 的论文解读已完成！\n📊 共解读 **{paper_count}** 篇论文"
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
                        "text": {"tag": "plain_text", "content": "📖 查看飞书文档"},
                        "type": "primary",
                        "multi_url": {
                            "url": doc_url,
                            "android_url": doc_url,
                            "ios_url": doc_url,
                            "pc_url": doc_url
                        }
                    }
                ]
            }
        ]
    }
    
    data = json.dumps({
        "receive_id": user_id,
        "msg_type": "interactive",
        "content": json.dumps(card, ensure_ascii=False)
    }).encode('utf-8')
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
        
        if result.get('code') != 0:
            print(f"⚠️  通知发送失败: {result.get('msg')}")
            return False
        
        print("✅ 通知发送成功")
        return True
        
    except Exception as e:
        print(f"⚠️  通知发送失败: {e}")
        return False


def load_analysis():
    """加载解读结果"""
    try:
        with open('latest_analysis.md', 'r', encoding='utf-8') as f:
            return f.read()
    except:
        pass
    
    import glob
    files = glob.glob('analysis_*.md')
    if files:
        latest = max(files, key=os.path.getctime)
        with open(latest, 'r', encoding='utf-8') as f:
            return f.read()
    
    return None


def main():
    print("=" * 70)
    print("📄 创建飞书文档")
    print("=" * 70)
    
    # 获取环境变量
    app_id = os.environ.get('FEISHU_APP_ID')
    app_secret = os.environ.get('FEISHU_APP_SECRET')
    user_id = os.environ.get('FEISHU_USER_OPEN_ID')
    topic = os.environ.get('TOPIC', 'AI Agent')
    paper_count = os.environ.get('PAPER_COUNT', '0')
    
    if not all([app_id, app_secret]):
        print("❌ 缺少必要的环境变量:")
        if not app_id:
            print("   - FEISHU_APP_ID")
        if not app_secret:
            print("   - FEISHU_APP_SECRET")
        return 1
    
    # 加载解读结果
    content = load_analysis()
    if not content:
        print("❌ 没有找到解读结果")
        return 1
    
    print(f"主题: {topic}")
    print(f"论文数: {paper_count}")
    print(f"解读长度: {len(content)} 字符")
    print()
    
    # 获取 token
    token = get_feishu_token(app_id, app_secret)
    if not token:
        return 1
    
    from datetime import datetime
    doc_title = f"{topic} - AI解读版研究简报 {datetime.now().strftime('%Y-%m-%d')}"
    
    # 创建文档
    doc_info = create_document(token, doc_title)
    if not doc_info:
        return 1
    
    # 获取页面块 ID
    page_block_id = get_page_block_id(token, doc_info['document_id'])
    if not page_block_id:
        print("⚠️  无法获取页面块 ID，尝试使用文档 ID 作为块 ID...")
        page_block_id = doc_info['document_id']
    
    # 添加内容
    if not add_document_content(token, doc_info['document_id'], page_block_id, content):
        print("⚠️  文档内容写入失败，但文档已创建")
    
    # 发送通知
    if user_id:
        send_notification(token, user_id, doc_info['document_id'], topic, paper_count)
    
    # 设置 GitHub Actions 输出
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"doc_id={doc_info['document_id']}\n")
            f.write(f"doc_url={doc_info['document_url']}\n")
    
    print("\n" + "=" * 70)
    print("✅ 飞书文档创建完成")
    print(f"📖 文档链接: {doc_info['document_url']}")
    print("=" * 70)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
