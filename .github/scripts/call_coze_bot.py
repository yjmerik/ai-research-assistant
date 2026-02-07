#!/usr/bin/env python3
"""
调用扣子 Bot 进行论文解读

使用扣子 Chat API 与 Bot 对话，获取 AI 通俗解读
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
    
    def __init__(self, pat, bot_id, workspace_id):
        self.pat = pat
        self.bot_id = bot_id
        self.workspace_id = workspace_id
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
            try:
                return {'error': json.loads(error_body), 'status': e.code}
            except:
                return {'error': error_body, 'status': e.code}
        except Exception as e:
            return {'error': str(e)}
    
    def create_conversation(self):
        """创建对话"""
        print("💬 创建对话...")
        
        data = {
            "bot_id": self.bot_id,
            "workspace_id": self.workspace_id
        }
        
        result = self._request('POST', '/v1/conversation/create', data)
        
        if result.get('code') != 0:
            print(f"❌ 创建对话失败: {result.get('msg')}")
            return None
        
        self.conversation_id = result.get('data', {}).get('conversation_id')
        print(f"✅ 对话创建成功: {self.conversation_id[:20]}...")
        return self.conversation_id
    
    def send_message(self, content):
        """发送消息给 Bot"""
        if not self.conversation_id:
            print("❌ 没有有效的对话 ID")
            return None
        
        print(f"📤 发送消息...")
        
        data = {
            "bot_id": self.bot_id,
            "conversation_id": self.conversation_id,
            "workspace_id": self.workspace_id,
            "content": content,
            "content_type": "text"
        }
        
        result = self._request('POST', '/v1/message/send', data)
        
        if result.get('code') != 0:
            print(f"❌ 发送消息失败: {result.get('msg')}")
            return None
        
        message_id = result.get('data', {}).get('message_id')
        print(f"✅ 消息发送成功: {message_id[:20]}...")
        return message_id
    
    def get_messages(self, limit=10):
        """获取消息列表（包括 Bot 回复）"""
        if not self.conversation_id:
            return None
        
        endpoint = f"/v1/message/list?conversation_id={self.conversation_id}&limit={limit}"
        result = self._request('GET', endpoint)
        
        if result.get('code') != 0:
            print(f"❌ 获取消息失败: {result.get('msg')}")
            return None
        
        return result.get('data', {}).get('messages', [])
    
    def wait_for_reply(self, timeout=120):
        """等待 Bot 回复"""
        print("⏳ 等待 Bot 回复...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            messages = self.get_messages()
            
            if messages:
                # 查找 Bot 的回复（最新的非用户消息）
                for msg in messages:
                    if msg.get('type') == 'answer':
                        print("✅ 收到 Bot 回复")
                        return msg.get('content')
            
            time.sleep(3)
            print("  等待中...")
        
        print("⚠️  等待超时")
        return None
    
    def chat(self, message):
        """发送消息并等待回复"""
        if not self.conversation_id:
            if not self.create_conversation():
                return None
        
        if not self.send_message(message):
            return None
        
        return self.wait_for_reply()


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
        message += f"摘要: {paper.get('summary', 'N/A')[:800]}...\n"
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
    workspace_id = os.environ.get('COZE_WORKSPACE_ID')
    topic = os.environ.get('TOPIC', 'AI Agent')
    
    if not all([pat, bot_id, workspace_id]):
        print("❌ 缺少必要的环境变量:")
        print("   - COZE_PAT")
        print("   - COZE_BOT_ID")
        print("   - COZE_WORKSPACE_ID")
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
    client = CozeBotClient(pat, bot_id, workspace_id)
    
    # 发送消息并获取回复
    print("📤 发送论文给扣子 Bot 进行解读...")
    print(f"消息长度: {len(message)} 字符")
    print()
    
    reply = client.chat(message)
    
    if reply:
        print("\n" + "=" * 70)
        print("📥 解读结果")
        print("=" * 70)
        print(reply[:500] + "..." if len(reply) > 500 else reply)
        print()
        
        # 保存结果
        filename = save_analysis(reply, papers_data.get('topic', topic))
        
        # 设置 GitHub Actions 输出
        with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
            f.write(f"analysis_file={filename}\n")
            f.write(f"analysis_length={len(reply)}\n")
        
        print("✅ 解读完成")
        return 0
    else:
        print("❌ 未能获取解读结果")
        return 1


if __name__ == '__main__':
    sys.exit(main())
