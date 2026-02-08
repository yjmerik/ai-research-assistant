#!/usr/bin/env python3
"""
发送 GitHub Trends 飞书通知
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime


def get_feishu_token(app_id, app_secret):
    """获取飞书 tenant access token"""
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
        
        return result.get('tenant_access_token')
        
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None


def send_notification(token, user_id, doc_id, doc_url):
    """发送飞书消息通知"""
    print("📤 发送飞书通知...")
    
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
    
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "🔥 GitHub Trends 日报"},
            "template": "blue"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"✅ **GitHub Trends** AI 分析报告已生成！\n📊 包含 **Top 50** 热门项目"
                }
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"⏰ 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n🤖 由 Kimi AI 智能分析"
                }
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "📋 **报告内容**: \n• Top 50 热门项目\n• 每个项目的 AI 总结\n• 功能特点分析\n• GitHub 链接"
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


def main():
    print("=" * 70)
    print("📤 发送 GitHub Trends 通知")
    print("=" * 70)
    
    # 获取环境变量
    app_id = os.environ.get('FEISHU_APP_ID')
    app_secret = os.environ.get('FEISHU_APP_SECRET')
    user_id = os.environ.get('FEISHU_USER_OPEN_ID')
    
    if not all([app_id, app_secret, user_id]):
        print("❌ 缺少必要的环境变量")
        return 1
    
    # 读取文档信息
    try:
        with open('doc_info.json', 'r') as f:
            doc_info = json.load(f)
        doc_id = doc_info['doc_id']
        doc_url = doc_info['doc_url']
    except:
        print("❌ 无法读取文档信息")
        return 1
    
    # 获取 token
    token = get_feishu_token(app_id, app_secret)
    if not token:
        return 1
    
    # 发送通知
    send_notification(token, user_id, doc_id, doc_url)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
