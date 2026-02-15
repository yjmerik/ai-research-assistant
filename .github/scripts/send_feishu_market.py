#!/usr/bin/env python3
"""
发送市场分析报告到飞书
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime


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


def send_market_card(token, user_id, data):
    """发送市场数据卡片"""
    print("📤 发送飞书市场快报...")
    
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
    
    # 提取关键数据
    us_stocks = data.get('us_stocks', [])
    hk_stocks = data.get('hk_stocks', [])
    fx_rates = data.get('fx_rates', [])
    commodities = data.get('commodities', [])
    
    # 构建市场摘要
    def get_change_emoji(change):
        return "🔴" if change >= 0 else "🟢"  # 美股红色涨，绿色跌
    
    # 主要指数
    market_summary = []
    
    # 美股
    if us_stocks:
        sp500 = next((s for s in us_stocks if s['symbol'] == '^GSPC'), None)
        if sp500:
            market_summary.append(f"🇺🇸 标普500: {sp500['change_pct']:+.2f}%")
    
    # 港股
    if hk_stocks:
        hsi = next((s for s in hk_stocks if s['symbol'] == '^HSI'), None)
        if hsi:
            market_summary.append(f"🇭🇰 恒生指数: {hsi['change_pct']:+.2f}%")
    
    # 汇率
    if fx_rates:
        usdcny = next((r for r in fx_rates if 'CNY' in r.get('name', '')), None)
        if usdcny:
            market_summary.append(f"💱 美元/人民币: {usdcny['price']:.4f}")
    
    summary_text = " | ".join(market_summary) if market_summary else "市场数据加载中..."
    
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"📊 全球市场日报 {datetime.now().strftime('%m/%d')}"},
            "template": "blue"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"📈 **市场摘要**\n{summary_text}"
                }
            },
            {
                "tag": "hr"
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**📋 详细报告内容：**\n• 美股/港股/A股 全面分析\n• 汇率、债市、大宗商品\n• AI 智能市场解读\n• 明日重点关注"
                }
            },
            {
                "tag": "hr"
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"⏰ 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n🤖 由 Kimi AI 智能分析"
                }
            },
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": "⚠️ 本报告仅供参考，不构成投资建议"
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
        
        print("✅ 飞书通知发送成功")
        return True
        
    except Exception as e:
        print(f"⚠️  通知发送失败: {e}")
        return False


def load_market_data():
    """加载市场数据"""
    try:
        with open('latest_market_data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        import glob
        files = glob.glob('market_data_*.json')
        if files:
            latest = max(files, key=os.path.getctime)
            with open(latest, 'r', encoding='utf-8') as f:
                return json.load(f)
    return None


def main():
    print("=" * 70)
    print("📤 发送市场数据到飞书")
    print("=" * 70)
    
    # 获取环境变量
    app_id = os.environ.get('FEISHU_APP_ID')
    app_secret = os.environ.get('FEISHU_APP_SECRET')
    user_id = os.environ.get('FEISHU_USER_OPEN_ID')
    
    if not all([app_id, app_secret, user_id]):
        print("❌ 缺少必要的环境变量")
        return 1
    
    # 加载市场数据
    data = load_market_data()
    if not data:
        print("❌ 没有找到市场数据")
        return 1
    
    # 获取 token
    token = get_feishu_token(app_id, app_secret)
    if not token:
        return 1
    
    # 发送通知
    send_market_card(token, user_id, data)
    
    print("\n✅ 完成")
    return 0


if __name__ == '__main__':
    sys.exit(main())
