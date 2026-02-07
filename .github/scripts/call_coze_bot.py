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
            print(f"HTTP Error {e.code}: {error_body}")
            try:
                return {'error': json.loads(error_body), 'status': e.code}
            except:
                return {'error': error_body, 'status': e.code}
        except Exception as e:
            return {'error': str(e)}
    
    def chat_with_bot(self, query):
        """
        使用扣子 Chat API 与 Bot 对话
        这是简化版的聊天接口
        """
        print(f"💬 调用扣子 Chat API...")
        
        # 使用 chat 接口直接发送消息
        data = {
            "bot_id": self.bot_id,
            "workspace_id": self.workspace_id,
            "query": query,
            "stream": False
        }
        
        result = self._request('POST', '/v1/chat', data)
        
        # 打印调试信息
        print(f"   API 响应: {json.dumps(result, ensure_ascii=False)[:200]}...")
        
        if result.get('error'):
            print(f"❌ API 错误: {result.get('error')}")
            return None
        
        if result.get('code') != 0:
            print(f"❌ 请求失败: {result.get('msg', '未知错误')}")
            print(f"   完整响应: {result}")
            return None
        
        # 获取回复内容
        data = result.get('data', {})
        
        # 检查不同可能的响应格式
        if isinstance(data, str):
            return data
        
        if isinstance(data, dict):
            # 尝试获取消息内容
            messages = data.get('messages', [])
            if messages:
                for msg in messages:
                    if msg.get('type') == 'answer':
                        return msg.get('content', '')
            
            # 直接返回 data 中的内容字段
            if 'content' in data:
                return data['content']
            if 'answer' in data:
                return data['answer']
            if 'reply' in data:
                return data['reply']
            
            # 返回整个 data 的字符串表示
            return json.dumps(data, ensure_ascii=False)
        
        return str(data)


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
    workspace_id = os.environ.get('COZE_WORKSPACE_ID')
    topic = os.environ.get('TOPIC', 'AI Agent')
    
    # 打印环境变量（隐藏敏感信息）
    print(f"Bot ID: {bot_id[:20]}..." if bot_id else "Bot ID: None")
    print(f"Workspace ID: {workspace_id[:20]}..." if workspace_id else "Workspace ID: None")
    print(f"PAT: {'已设置' if pat else '未设置'}")
    print()
    
    if not all([pat, bot_id, workspace_id]):
        print("❌ 缺少必要的环境变量:")
        if not pat:
            print("   - COZE_PAT")
        if not bot_id:
            print("   - COZE_BOT_ID")
        if not workspace_id:
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
