#!/usr/bin/env python3
"""
调用扣子 Bot 进行论文解读

使用扣子 Chat API v3 与 Bot 对话，获取 AI 通俗解读
文档: https://docs.coze.cn/developer_guides/coze_api_overview
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error

# 扣子 API 配置
COZE_API_BASE = "https://api.coze.cn"


class CozeBotClient:
    """扣子 Bot 客户端"""
    
    def __init__(self, pat, bot_id, user_id="github_actions_user"):
        self.pat = pat
        self.bot_id = bot_id
        self.user_id = user_id
        self.conversation_id = None
        
    def _request(self, method, endpoint, data=None):
        """发送 HTTP 请求"""
        url = f"{COZE_API_BASE}{endpoint}"
        
        headers = {
            'Authorization': f'Bearer {self.pat}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        try:
            if method == 'GET':
                req = urllib.request.Request(url, headers=headers, method='GET')
            else:
                json_data = json.dumps(data, ensure_ascii=False).encode('utf-8') if data else None
                req = urllib.request.Request(url, data=json_data, headers=headers, method=method)
            
            with urllib.request.urlopen(req, timeout=120) as response:
                return json.loads(response.read().decode('utf-8'))
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            print(f"HTTP Error {e.code}: {error_body}")
            try:
                return {'error': json.loads(error_body), 'status': e.code}
            except:
                return {'error': error_body, 'status': e.code}
        except Exception as e:
            return {'error': str(e)}
    
    def chat_with_bot(self, content):
        """
        使用扣子 Chat API v3 与 Bot 对话
        
        API: POST https://api.coze.cn/v3/chat
        """
        print(f"💬 调用扣子 Chat API v3...")
        
        data = {
            "bot_id": self.bot_id,
            "user_id": self.user_id,
            "auto_save_history": True,
            "additional_messages": [
                {
                    "role": "user",
                    "content": content,
                    "content_type": "text"
                }
            ]
        }
        
        result = self._request('POST', '/v3/chat', data)
        
        # 打印调试信息
        print(f"   API 响应 code: {result.get('code', 'N/A')}")
        
        if result.get('error'):
            print(f"❌ API 错误: {result.get('error')}")
            return None
        
        if result.get('code') != 0:
            print(f"❌ 请求失败: {result.get('msg', '未知错误')}")
            return None
        
        # 获取对话 ID 用于查询结果
        data = result.get('data', {})
        self.conversation_id = data.get('conversation_id')
        chat_id = data.get('id')
        
        print(f"✅ 对话创建成功")
        print(f"   Conversation ID: {self.conversation_id[:30]}..." if self.conversation_id else "   Conversation ID: None")
        print(f"   Chat ID: {chat_id[:30]}..." if chat_id else "   Chat ID: None")
        
        # 等待并获取回复
        return self._wait_for_chat_completion(chat_id)
    
    def _wait_for_chat_completion(self, chat_id, timeout=180):
        """等待对话完成并获取结果"""
        print(f"⏳ 等待 Bot 回复...")
        start_time = time.time()
        check_count = 0
        
        while time.time() - start_time < timeout:
            check_count += 1
            # 查询对话状态
            endpoint = f'/v3/chat/retrieve?conversation_id={self.conversation_id}&chat_id={chat_id}'
            result = self._request('GET', endpoint)
            
            if result.get('code') != 0:
                print(f"   查询失败: {result.get('msg', '未知错误')}")
                time.sleep(3)
                continue
            
            data = result.get('data', {})
            status = data.get('status')
            
            # 只打印状态变化
            if check_count == 1 or check_count % 5 == 0:
                print(f"   状态: {status} (检查 #{check_count})")
            
            if status == 'completed':
                # 直接尝试从消息列表获取
                return self._get_chat_messages()
            elif status in ['failed', 'cancelled']:
                print(f"❌ 对话失败: {data.get('last_error', '未知错误')}")
                return None
            
            time.sleep(3)
        
        print("⚠️  等待超时")
        return None
    
    def _get_chat_messages(self):
        """获取对话消息列表"""
        print(f"📥 获取回复内容...")
        
        # 尝试使用 conversation_id 获取消息
        # 注意：v3 API 的消息列表可能使用不同的端点
        endpoint = f'/v1/conversation/message/list?conversation_id={self.conversation_id}'
        result = self._request('GET', endpoint)
        
        # 如果 v1 失败，尝试 v3
        if result.get('code') != 0:
            print(f"   v1 API 失败，尝试 v3...")
            endpoint = f'/v3/chat/message/list?conversation_id={self.conversation_id}'
            result = self._request('GET', endpoint)
        
        if result.get('code') != 0:
            print(f"❌ 获取消息失败: {result.get('msg', '未知错误')}")
            print(f"   响应详情: {json.dumps(result, ensure_ascii=False)[:500]}")
            return None
        
        # v3 API 返回 data 是列表
        messages = result.get('data', [])
        
        if not messages:
            print("❌ 没有收到消息")
            return None
        
        print(f"   收到 {len(messages)} 条消息")
        
        # 找到 assistant 的 answer 类型消息
        for msg in messages:
            msg_type = msg.get('type')
            role = msg.get('role')
            content = msg.get('content', '')
            
            print(f"   消息: type={msg_type}, role={role}, content_len={len(content)}")
            
            if msg_type == 'answer' and role == 'assistant' and content:
                print(f"✅ 找到回复 ({len(content)} 字符)")
                return content
        
        # 如果没有 answer 类型，返回最后一条 assistant 消息
        for msg in reversed(messages):
            if msg.get('role') == 'assistant':
                content = msg.get('content', '')
                if content:
                    print(f"✅ 使用最后一条 assistant 消息 ({len(content)} 字符)")
                    return content
        
        # 最后尝试返回任何有内容的消息
        for msg in reversed(messages):
            content = msg.get('content', '')
            if content:
                print(f"✅ 使用消息内容 ({len(content)} 字符)")
                return content
        
        print("❌ 没有有效的消息内容")
        return None


def load_papers():
    """加载论文数据"""
    try:
        with open('latest_papers.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"❌ 加载论文失败: {e}")
        return None


def format_papers_for_coze(papers_data):
    """格式化论文数据为扣子 Bot 可理解的格式"""
    topic = papers_data.get('topic', 'AI Agent')
    papers = papers_data.get('papers', [])
    
    message = f"请对以下关于「{topic}」的 {len(papers)} 篇论文进行深度解读：\n\n"
    
    for i, paper in enumerate(papers, 1):
        message += f"---\n\n"
        message += f"论文 {i}:\n"
        message += f"标题: {paper.get('title', 'N/A')}\n"
        message += f"作者: {', '.join(paper.get('authors', [])[:3])}\n"
        message += f"发表日期: {paper.get('published', 'N/A')}\n"
        
        # 截断摘要，避免消息太长
        summary = paper.get('summary', 'N/A')
        if len(summary) > 600:
            summary = summary[:600] + "..."
        message += f"摘要: {summary}\n"
        message += f"链接: {paper.get('url', 'N/A')}\n\n"
    
    message += "\n请为每篇论文提供通俗易懂的解读，包括：\n"
    message += "1. 一句话概括核心内容\n"
    message += "2. 核心创新点\n"
    message += "3. 技术原理（用大白话解释）\n"
    message += "4. 实际应用场景\n"
    message += "5. 整体趋势分析\n"
    
    return message


def save_analysis(analysis, topic):
    """保存解读结果"""
    from datetime import datetime
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 保存 Markdown 格式
    md_filename = f"analysis_{timestamp}.md"
    with open(md_filename, 'w', encoding='utf-8') as f:
        f.write(f"# {topic} - AI解读版研究简报\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        f.write(analysis)
    
    print(f"💾 解读已保存: {md_filename}")
    
    # 同时保存为最新文件
    with open('latest_analysis.md', 'w', encoding='utf-8') as f:
        f.write(f"# {topic} - AI解读版研究简报\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        f.write(analysis)
    
    return md_filename


def main():
    print("=" * 70)
    print("🤖 扣子 Bot 论文解读")
    print("=" * 70)
    
    # 获取环境变量
    pat = os.environ.get('COZE_PAT')
    bot_id = os.environ.get('COZE_BOT_ID')
    topic = os.environ.get('TOPIC', 'AI Agent')
    
    # 打印环境变量（隐藏敏感信息）
    print(f"Bot ID: {bot_id[:20]}..." if bot_id else "Bot ID: None")
    print(f"PAT: {'已设置' if pat else '未设置'}")
    print()
    
    if not all([pat, bot_id]):
        print("❌ 缺少必要的环境变量:")
        if not pat:
            print("   - COZE_PAT")
        if not bot_id:
            print("   - COZE_BOT_ID")
        return 1
    
    # 加载论文
    papers_data = load_papers()
    if not papers_data:
        print("❌ 没有找到论文数据")
        return 1
    
    print(f"主题: {papers_data.get('topic', topic)}")
    print(f"论文数量: {papers_data.get('count', 0)}")
    print()
    
    # 格式化消息
    message = format_papers_for_coze(papers_data)
    
    # 创建 Bot 客户端
    client = CozeBotClient(pat, bot_id)
    
    # 发送消息并获取回复
    print(f"📤 发送论文给扣子 Bot 进行解读...")
    print(f"消息长度: {len(message)} 字符")
    print()
    
    reply = client.chat_with_bot(message)
    
    if reply:
        print("\n" + "=" * 70)
        print("📥 解读结果")
        print("=" * 70)
        preview = reply[:800] + "..." if len(reply) > 800 else reply
        print(preview)
        print()
        
        # 保存结果
        filename = save_analysis(reply, papers_data.get('topic', topic))
        
        # 设置 GitHub Actions 输出
        github_output = os.environ.get('GITHUB_OUTPUT')
        if github_output:
            with open(github_output, 'a') as f:
                f.write(f"analysis_file={filename}\n")
                f.write(f"analysis_length={len(reply)}\n")
        
        print("✅ 解读完成")
        return 0
    else:
        print("❌ 未能获取解读结果")
        # 尝试保存原始论文数据作为备选
        with open('analysis_failed.json', 'w', encoding='utf-8') as f:
            json.dump(papers_data, f, ensure_ascii=False, indent=2)
        print("💾 原始论文数据已保存到 analysis_failed.json")
        return 1


if __name__ == '__main__':
    sys.exit(main())
