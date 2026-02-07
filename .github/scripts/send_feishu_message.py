#!/usr/bin/env python3
"""
发送解读结果到飞书

使用飞书 OpenAPI 发送消息到指定用户
"""

import os
import sys
import json
import urllib.request
import urllib.error


def get_feishu_token(app_id, app_secret):
    """获取飞书 tenant access token"""
    print("🔑 获取飞书 access token...")
    
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = json.dumps({
        "app_id": app_id,
        "app_secret": app_secret
    }).encode('utf-8')
    
    headers = {
        'Content-Type': 'application/json'
    }
    
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


def send_message(token, user_id, content, topic, paper_count):
    """发送飞书消息"""
    print(f"📤 发送飞书消息...")
    
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
    
    # 构建卡片消息
    card = build_message_card(topic, paper_count, content)
    
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
            print(f"❌ 发送失败: {result.get('msg')}")
            return False
        
        print("✅ 飞书消息发送成功")
        return True
        
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def build_message_card(topic, paper_count, content):
    """构建飞书卡片消息"""
    from datetime import datetime
    
    # 提取亮点（内容的前 300 字符作为摘要）
    summary = content[:300] + "..." if len(content) > 300 else content
    # 移除 markdown 标记，保留纯文本
    summary = summary.replace('#', '').replace('**', '').replace('*', '').replace('`', '')
    
    card = {
        "config": {
            "wide_screen_mode": True
        },
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"📚 {topic} - AI解读版简报"
            },
            "template": "green"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"🤖 扣子 Bot 已完成 **{paper_count}** 篇论文的深度解读"
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
                "tag": "hr"
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"📝 **解读预览**:\n{summary}"
                }
            },
            {
                "tag": "hr"
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "📖 **解读内容包括**:\n• 每篇论文通俗解读\n• 一句话核心概括\n• 技术原理大白话解释\n• 实际应用场景分析\n• 领域趋势洞察"
                }
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "📎 查看完整解读"
                        },
                        "type": "primary",
                        "multi_url": {
                            "url": "https://github.com/yjmerik/ai-research-assistant/actions",
                            "android_url": "https://github.com/yjmerik/ai-research-assistant/actions",
                            "ios_url": "https://github.com/yjmerik/ai-research-assistant/actions",
                            "pc_url": "https://github.com/yjmerik/ai-research-assistant/actions"
                        }
                    }
                ]
            }
        ]
    }
    
    return card


def load_analysis():
    """加载解读结果"""
    try:
        # 优先读取 latest_analysis.md
        with open('latest_analysis.md', 'r', encoding='utf-8') as f:
            return f.read()
    except:
        pass
    
    # 如果没有，查找最新的 analysis_*.md
    import glob
    files = glob.glob('analysis_*.md')
    if files:
        latest = max(files, key=os.path.getctime)
        with open(latest, 'r', encoding='utf-8') as f:
            return f.read()
    
    return None


def main():
    print("=" * 70)
    print("📤 发送解读结果到飞书")
    print("=" * 70)
    
    # 获取环境变量
    app_id = os.environ.get('FEISHU_APP_ID')
    app_secret = os.environ.get('FEISHU_APP_SECRET')
    user_id = os.environ.get('FEISHU_USER_OPEN_ID')
    topic = os.environ.get('TOPIC', 'AI Agent')
    paper_count = os.environ.get('PAPER_COUNT', '0')
    
    if not all([app_id, app_secret, user_id]):
        print("❌ 缺少必要的环境变量:")
        if not app_id:
            print("   - FEISHU_APP_ID")
        if not app_secret:
            print("   - FEISHU_APP_SECRET")
        if not user_id:
            print("   - FEISHU_USER_OPEN_ID")
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
    
    # 发送消息
    if send_message(token, user_id, content, topic, paper_count):
        print("\n✅ 飞书推送完成")
        return 0
    else:
        print("\n❌ 飞书推送失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
