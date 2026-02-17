"""
飞书 AI 助手 v2.0 - 调试版本
"""
import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Set

import lark_oapi as lark
from lark_oapi.api.im.v1 import *

# 导入核心组件
from core.intent_recognizer import IntentRecognizer
from skills.base_skill import SkillResult

# 导入技能
from skills.skill_registry import registry
from skills.market_skill import MarketSkill
from skills.github_skill import GitHubSkill
from skills.paper_skill import PaperSkill
from skills.chat_skill import ChatSkill


# ============ 配置 ============
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
KIMI_API_KEY = os.environ.get("KIMI_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

print(f"🚀 飞书 AI 助手 v2.0 (调试模式) 启动")
print(f"   APP_ID: {FEISHU_APP_ID[:20] if FEISHU_APP_ID else 'Not Set'}...")


def init_components():
    """初始化所有组件"""
    intent_recognizer = IntentRecognizer(api_key=KIMI_API_KEY)
    
    registry.register(MarketSkill())
    registry.register(GitHubSkill(config={"github_token": GITHUB_TOKEN}))
    registry.register(PaperSkill())
    registry.register(ChatSkill(config={"llm_api_key": KIMI_API_KEY}))
    
    print(f"\n✅ 已注册 {len(registry.list_skills())} 个技能:")
    for name in registry.list_skills():
        print(f"   - {name}")
    
    return intent_recognizer


class MessageProcessor:
    """消息处理器"""
    
    def __init__(self, intent_recognizer: IntentRecognizer):
        self.intent_recognizer = intent_recognizer
        self.processed_msgs: Set[str] = set()
        self.user_sessions: Dict[str, Dict] = {}
    
    async def process(self, user_id: str, message_id: str, text: str, 
                     msg_type: str = "text"):
        """处理消息"""
        
        # 去重检查
        if message_id in self.processed_msgs:
            print(f"⚠️ 消息已处理，跳过: {message_id[:20]}")
            return
        self.processed_msgs.add(message_id)
        
        if len(self.processed_msgs) > 1000:
            self.processed_msgs.clear()
        
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {"history": []}
        session = self.user_sessions[user_id]
        
        print(f"\n{'='*50}")
        print(f"📨 [{datetime.now().strftime('%H:%M:%S')}] 收到消息")
        print(f"   用户ID: {user_id[:20]}...")
        print(f"   内容: {text[:100]}")
        print(f"{'='*50}")
        
        try:
            session["history"].append({
                "role": "user",
                "content": text,
                "time": datetime.now().isoformat()
            })
            session["history"] = session["history"][-10:]
            
            if text.startswith("/"):
                print("📝 识别为快捷命令")
                result = await self._handle_command(text, user_id)
            else:
                print("🧠 使用大模型识别意图...")
                result = await self._handle_natural_language(text, session)
            
            print(f"\n📤 准备发送回复:")
            print(f"   成功: {result.success}")
            print(f"   消息长度: {len(result.message)}")
            print(f"   是否有卡片: {result.card_content is not None}")
            
            if result.card_content:
                print(f"   卡片内容预览: {json.dumps(result.card_content, ensure_ascii=False)[:200]}...")
            
            await self._send_reply(user_id, result)
            
            session["history"].append({
                "role": "assistant",
                "content": result.message[:100] if hasattr(result, 'message') else str(result)[:100],
                "time": datetime.now().isoformat()
            })
            
        except Exception as e:
            print(f"❌ 处理失败: {e}")
            import traceback
            traceback.print_exc()
            await send_text(user_id, f"❌ 处理失败: {str(e)}")
    
    async def _handle_command(self, text: str, user_id: str) -> SkillResult:
        """处理快捷命令"""
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        command_map = {
            "/market": ("query_market", {"market": args.upper() if args else "US"}),
            "/m": ("query_market", {"market": args.upper() if args else "US"}),
            "/github": ("search_github", {"keywords": args or "ai-agent"}),
            "/gh": ("search_github", {"keywords": args or "ai-agent"}),
            "/paper": ("search_papers", {"topic": args or "AI"}),
            "/arxiv": ("search_papers", {"topic": args or "AI"}),
            "/chat": ("chat", {"message": args or "你好"}),
            "/help": ("chat", {"message": "帮助"}),
            "/clear": ("chat", {"message": "清除"}),
            "/status": ("chat", {"message": "状态"}),
        }
        
        if cmd in command_map:
            skill_name, params = command_map[cmd]
            print(f"   执行技能: {skill_name}, 参数: {params}")
            skill = registry.get(skill_name)
            result = await skill.execute(**params)
            print(f"   执行结果: success={result.success}")
            return result
        else:
            return SkillResult(
                success=False,
                message=f"未知命令: {cmd}\n\n可用命令: /market, /github, /paper, /help"
            )
    
    async def _handle_natural_language(self, text: str, session: Dict) -> SkillResult:
        """处理自然语言"""
        
        print("\n🤖 调用大模型识别意图...")
        plan = await self.intent_recognizer.recognize(
            user_input=text,
            skills_schema=registry.get_all_schemas(),
            context=session
        )
        
        print(f"🎯 意图识别结果:")
        print(f"   技能: {plan.get('skill')}")
        print(f"   参数: {plan.get('parameters')}")
        print(f"   置信度: {plan.get('confidence')}")
        print(f"   推理: {plan.get('reasoning', 'N/A')}")
        
        skill_name = plan.get("skill", "chat")
        parameters = plan.get("parameters", {})
        
        try:
            skill = registry.get(skill_name)
            print(f"\n⚡ 执行技能: {skill_name}")
            result = await skill.execute(**parameters)
            print(f"✅ 技能执行完成: success={result.success}")
            return result
        except Exception as e:
            print(f"❌ 技能执行失败: {e}")
            import traceback
            traceback.print_exc()
            chat_skill = registry.get("chat")
            return await chat_skill.execute(message=text)
    
    async def _send_reply(self, user_id: str, result: SkillResult):
        """发送回复"""
        print(f"\n📤 发送回复:")
        if result.card_content:
            print("   类型: 卡片消息")
            print(f"   卡片JSON: {json.dumps(result.card_content, ensure_ascii=False)}")
            await send_card(user_id, result.card_content)
        else:
            print("   类型: 文本消息")
            print(f"   内容: {result.message[:100]}...")
            await send_text(user_id, result.message)


async def send_text(user_id: str, text: str):
    """发送文本消息"""
    try:
        print(f"   [send_text] 开始发送...")
        client = lark.Client.builder() \
            .app_id(FEISHU_APP_ID) \
            .app_secret(FEISHU_APP_SECRET) \
            .build()
        
        request = CreateMessageRequest.builder() \
            .receive_id_type("open_id") \
            .request_body(CreateMessageRequestBody.builder()
                .receive_id(user_id)
                .msg_type("text")
                .content(json.dumps({"text": text}))
                .build()) \
            .build()
        
        response = client.im.v1.message.create(request)
        if response.success():
            print(f"   [send_text] ✅ 发送成功")
        else:
            print(f"   [send_text] ❌ 发送失败: {response.code} - {response.msg}")
    except Exception as e:
        print(f"   [send_text] ❌ 异常: {e}")


async def send_card(user_id: str, card_content: Dict):
    """发送卡片消息"""
    try:
        print(f"   [send_card] 开始发送...")
        client = lark.Client.builder() \
            .app_id(FEISHU_APP_ID) \
            .app_secret(FEISHU_APP_SECRET) \
            .build()
        
        content = json.dumps(card_content)
        print(f"   [send_card] 内容长度: {len(content)}")
        
        request = CreateMessageRequest.builder() \
            .receive_id_type("open_id") \
            .request_body(CreateMessageRequestBody.builder()
                .receive_id(user_id)
                .msg_type("interactive")
                .content(content)
                .build()) \
            .build()
        
        response = client.im.v1.message.create(request)
        if response.success():
            print(f"   [send_card] ✅ 发送成功")
        else:
            print(f"   [send_card] ❌ 发送失败: {response.code} - {response.msg}")
    except Exception as e:
        print(f"   [send_card] ❌ 异常: {e}")
        import traceback
        traceback.print_exc()


def create_message_handler(processor: MessageProcessor):
    """创建消息处理器"""
    def on_message(data):
        try:
            event = data.event
            message = event.message
            
            user_id = event.sender.sender_id.open_id
            message_id = message.message_id
            msg_type = message.message_type
            
            text = ""
            try:
                content = json.loads(message.content)
                text = content.get("text", "").strip()
            except:
                text = ""
            
            if text:
                asyncio.create_task(processor.process(user_id, message_id, text, msg_type))
        
        except Exception as e:
            print(f"❌ 消息处理异常: {e}")
    
    return on_message


def main():
    """主程序"""
    intent_recognizer = init_components()
    
    processor = MessageProcessor(intent_recognizer)
    
    on_message = create_message_handler(processor)
    
    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(on_message) \
        .build()
    
    ws_client = lark.ws.Client(
        FEISHU_APP_ID,
        FEISHU_APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO
    )
    
    print("\n" + "="*50)
    print("🎯 调试模式已启动")
    print("   所有消息和意图识别将显示详细日志")
    print("="*50 + "\n")
    
    ws_client.start()


if __name__ == "__main__":
    main()
