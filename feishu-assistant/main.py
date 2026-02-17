"""
飞书 AI 助手 - 修复版
"""
import os
import json
import asyncio
from datetime import datetime, timedelta

import lark_oapi as lark
from lark_oapi.api.im.v1 import *
import httpx

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

processed_msgs = set()

print(f"🚀 飞书 AI 助手启动")
print(f"   APP_ID: {FEISHU_APP_ID}")

# ========== 命令处理器 ==========
async def handle_help(user_id):
    text = """🤖 **飞书 AI 助手**

**命令：**
• `/market` - 查询市场行情
• `/github` - 搜索 GitHub 趋势
• `/paper` - 搜索 arXiv 论文
• `/clear` - 清除会话
• `/status` - 系统状态
• `/help` - 显示帮助"""
    await send_text(user_id, text)

async def handle_market(user_id):
    await send_text(user_id, "🔄 正在查询市场...")
    try:
        indices = {}
        symbols = {"标普500": "^GSPC", "纳斯达克": "^IXIC", "道琼斯": "^DJI"}
        
        async with httpx.AsyncClient() as client:
            for name, symbol in symbols.items():
                try:
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
                    resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                    data = resp.json()
                    meta = data['chart']['result'][0]['meta']
                    prev, curr = meta.get('previousClose', 0), meta.get('regularMarketPrice', 0)
                    change = ((curr - prev) / prev * 100) if prev else 0
                    emoji = "🟢" if change >= 0 else "🔴"
                    indices[name] = f"{emoji} {name}: {round(curr, 2)} ({change:+.2f}%)"
                except:
                    indices[name] = f"⚪ {name}: -"
        
        msg = f"📊 市场行情 {datetime.now().strftime('%m-%d %H:%M')}\n\n" + "\n".join(indices.values())
        await send_text(user_id, msg)
    except Exception as e:
        await send_text(user_id, f"❌ 查询失败: {str(e)}")

async def handle_github(args, user_id):
    keyword = args if args else "ai-agent"
    await send_text(user_id, f"🔄 搜索 GitHub: {keyword}...")
    
    try:
        date_since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.github.com/search/repositories",
                params={"q": f"{keyword} stars:>10 pushed:>{date_since}", "sort": "stars", "per_page": 5},
                headers={"Authorization": f"token {GITHUB_TOKEN}", "User-Agent": "bot"},
                timeout=30
            )
            repos = resp.json().get("items", [])
        
        msg = f"🚀 GitHub 趋势 - {keyword}\n\n"
        for i, repo in enumerate(repos[:5], 1):
            desc = repo.get("description", "") or "无描述"
            msg += f"{i}. **{repo['full_name']}** ⭐ {repo['stargazers_count']}\n   {desc[:50]}\n\n"
        await send_text(user_id, msg)
    except Exception as e:
        await send_text(user_id, f"❌ 失败: {str(e)}")

async def handle_paper(args, user_id):
    topic = args if args else "AI"
    await send_text(user_id, f"🔄 搜索论文: {topic}...")
    
    try:
        import xml.etree.ElementTree as ET
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "http://export.arxiv.org/api/query",
                params={"search_query": f"all:{topic}", "max_results": 3, "sortBy": "submittedDate"},
                timeout=30
            )
        
        papers = []
        root = ET.fromstring(resp.text)
        for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
            title = entry.find('{http://www.w3.org/2005/Atom}title')
            url = entry.find('{http://www.w3.org/2005/Atom}id')
            if title is not None:
                papers.append({"title": title.text.strip()[:80], "url": url.text if url else ""})
        
        msg = f"📄 arXiv - {topic}\n\n"
        for i, p in enumerate(papers[:3], 1):
            msg += f"{i}. {p['title']}\n   {p['url']}\n\n"
        await send_text(user_id, msg)
    except Exception as e:
        await send_text(user_id, f"❌ 失败: {str(e)}")

# ========== 飞书 API ==========
async def send_text(user_id, text):
    try:
        client = lark.Client.builder().app_id(FEISHU_APP_ID).app_secret(FEISHU_APP_SECRET).build()
        request = CreateMessageRequest.builder() \
            .receive_id_type("open_id") \
            .request_body(CreateMessageRequestBody.builder()
                .receive_id(user_id).msg_type("text").content(json.dumps({"text": text})).build()) \
            .build()
        response = client.im.v1.message.create(request)
        if not response.success():
            print(f"发送失败: {response.msg}")
    except Exception as e:
        print(f"发送异常: {e}")

# ========== 消息处理 ==========
def on_message(data):
    """处理消息"""
    try:
        event = data.event
        message = event.message
        user_id = event.sender.sender_id.open_id
        message_id = message.message_id
        
        content = json.loads(message.content)
        text = content.get("text", "").strip()
        
        print(f"📨 [{datetime.now().strftime('%H:%M:%S')}] {text[:50]}")
        
        # 去重
        if message_id in processed_msgs:
            return
        processed_msgs.add(message_id)
        
        # 命令路由
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd == "/help":
            asyncio.create_task(handle_help(user_id))
        elif cmd == "/market":
            asyncio.create_task(handle_market(user_id))
        elif cmd == "/github":
            asyncio.create_task(handle_github(args, user_id))
        elif cmd == "/paper":
            asyncio.create_task(handle_paper(args, user_id))
        elif cmd == "/status":
            asyncio.create_task(send_text(user_id, "✅ 服务运行正常"))
        elif cmd == "/clear":
            processed_msgs.clear()
            asyncio.create_task(send_text(user_id, "🗑️ 已清除"))
        else:
            asyncio.create_task(send_text(user_id, f"收到: {text[:50]}...\n\n发送 /help 查看命令"))
            
    except Exception as e:
        print(f"处理错误: {e}")

# ========== 启动 ==========
if __name__ == "__main__":
    handler = lark.EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(on_message).build()
    client = lark.ws.Client(FEISHU_APP_ID, FEISHU_APP_SECRET, event_handler=handler, log_level=lark.LogLevel.INFO)
    print("🎯 连接中...")
    client.start()
