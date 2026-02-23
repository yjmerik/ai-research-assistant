"""
飞书 AI 助手 v2.0
支持大模型意图识别和 Skills 系统
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
from skills.stock_skill import StockSkill
from skills.portfolio_skill import PortfolioSkill


# ============ 配置 ============
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
KIMI_API_KEY = os.environ.get("KIMI_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

print(f"🚀 飞书 AI 助手 v2.0 启动")
print(f"   APP_ID: {FEISHU_APP_ID[:20] if FEISHU_APP_ID else 'Not Set'}...")


# ============ 初始化组件 ============
def init_components():
    """初始化所有组件（同步版本）"""
    # 1. 初始化意图识别器
    intent_recognizer = IntentRecognizer(api_key=KIMI_API_KEY)
    
    # 2. 注册所有技能
    registry.register(MarketSkill())
    registry.register(GitHubSkill(config={"github_token": GITHUB_TOKEN}))
    registry.register(PaperSkill())
    registry.register(ChatSkill(config={"llm_api_key": KIMI_API_KEY}))
    registry.register(StockSkill(config={"kimi_api_key": KIMI_API_KEY}))
    registry.register(PortfolioSkill())
    
    print(f"\n✅ 已注册 {len(registry.list_skills())} 个技能:")
    for name in registry.list_skills():
        print(f"   - {name}")
    
    return intent_recognizer


# ============ 消息处理 ============
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
            return
        self.processed_msgs.add(message_id)
        
        # 清理旧消息ID
        if len(self.processed_msgs) > 1000:
            self.processed_msgs.clear()
        
        # 获取或创建用户会话
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {"history": [], "user_id": user_id}
        session = self.user_sessions[user_id]
        
        print(f"📨 [{datetime.now().strftime('%H:%M:%S')}] 用户: {text[:50]}")
        
        try:
            # 更新历史
            session["history"].append({
                "role": "user",
                "content": text,
                "time": datetime.now().isoformat()
            })
            session["history"] = session["history"][-10:]  # 保留最近10条
            
            # 判断是否为快捷命令
            if text.startswith("/"):
                result = await self._handle_command(text, user_id)
            else:
                # 使用大模型识别意图
                result = await self._handle_natural_language(text, session)
            
            # 发送回复
            await self._send_reply(user_id, result)
            
            # 更新历史
            session["history"].append({
                "role": "assistant",
                "content": result.message[:100] if hasattr(result, 'message') else str(result)[:100],
                "time": datetime.now().isoformat()
            })
            
        except Exception as e:
            print(f"❌ 处理失败: {e}")
            await send_text(user_id, f"❌ 处理失败: {str(e)}")
    
    async def _handle_command(self, text: str, user_id: str) -> SkillResult:
        """处理快捷命令"""
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # 命令映射到技能
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
            "/portfolio": ("manage_portfolio", {"action": "query", "user_id": user_id}),
            "/持仓": ("manage_portfolio", {"action": "query", "user_id": user_id}),
        }
        
        if cmd in command_map:
            skill_name, params = command_map[cmd]
            skill = registry.get(skill_name)
            return await skill.execute(**params)
        else:
            return SkillResult(
                success=False,
                message=f"未知命令: {cmd}\n\n可用命令: /market, /github, /paper, /help"
            )
    
    async def _handle_natural_language(self, text: str, session: Dict) -> SkillResult:
        """处理自然语言"""
        
        # 先检查是否是持仓查询
        if any(kw in text for kw in ["持仓", "我的股票", "持仓情况", "查看持仓"]):
            skill = registry.get("manage_portfolio")
            return await skill.execute(action="query", user_id=session.get("user_id", "default"))
        
        # 检查是否是交易记录消息（买入/卖出）
        trade_info = self._parse_trade_message(text)
        if trade_info:
            skill = registry.get("manage_portfolio")
            return await skill.execute(
                action="record",
                user_id=session.get("user_id", "default"),
                stock_name=trade_info["stock_name"],
                trade_action=trade_info["action"],
                price=trade_info["price"],
                shares=trade_info["shares"]
            )
        
        # 使用大模型识别意图
        plan = await self.intent_recognizer.recognize(
            user_input=text,
            skills_schema=registry.get_all_schemas(),
            context=session
        )
        
        skill_name = plan.get("skill", "chat")
        parameters = plan.get("parameters", {})
        confidence = plan.get("confidence", 0)
        reasoning = plan.get("reasoning", "N/A")
        
        print(f"🧠 意图识别: {skill_name} (置信度: {confidence:.2f})")
        print(f"   参数: {parameters}")
        print(f"   推理: {reasoning}")
        
        # 获取技能并执行
        try:
            skill = registry.get(skill_name)
            result = await skill.execute(**parameters)
            return result
        except Exception as e:
            print(f"❌ 技能执行失败: {e}")
            import traceback
            traceback.print_exc()
            # 失败时使用对话技能
            chat_skill = registry.get("chat")
            return await chat_skill.execute(message=text)
    
    def _parse_trade_message(self, text: str) -> Optional[Dict[str, Any]]:
        """
        解析交易消息
        支持格式：
        - 买入茅台 100股 价格1500
        - 卖出腾讯 50股 400元
        - 买入 AAPL 10股 180
        """
        import re
        
        text = text.strip().lower()
        
        # 判断是买入还是卖出
        action = None
        if any(kw in text for kw in ['买入', 'buy', '购买', '买进']):
            action = 'buy'
        elif any(kw in text for kw in ['卖出', 'sell', '抛售', '卖出']):
            action = 'sell'
        
        if not action:
            return None
        
        # 提取股票名称
        stock_name = None
        # 尝试在买入/卖出关键词后面找
        patterns = [
            r'(?:买入|卖出|buy|sell)\s+([\u4e00-\u9fa5a-zA-Z]{1,10})',
            r'(?:买入|卖出|buy|sell)\s+(\S+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                stock_name = match.group(1).strip()
                break
        
        if not stock_name:
            # 尝试找第一个可能的中文或英文股票名
            match = re.search(r'([\u4e00-\u9fa5]{2,}|[a-zA-Z]{1,5})', text)
            if match:
                stock_name = match.group(1).strip()
        
        # 提取数字（股数和价格）
        numbers = re.findall(r'(\d+(?:\.\d+)?)', text)
        if len(numbers) < 2:
            return None
        
        try:
            shares = int(float(numbers[0]))
            price = float(numbers[1])
        except (ValueError, IndexError):
            return None
        
        if stock_name and shares > 0 and price > 0:
            return {
                'action': action,
                'stock_name': stock_name,
                'shares': shares,
                'price': price
            }
        
        return None
    
    async def _send_reply(self, user_id: str, result: SkillResult):
        """发送回复"""
        if result.card_content:
            # 发送卡片消息
            await send_card(user_id, result.card_content)
        else:
            # 发送文本消息
            await send_text(user_id, result.message)


# ============ 飞书 API ============
async def send_text(user_id: str, text: str):
    """发送文本消息"""
    try:
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
        if not response.success():
            print(f"❌ 发送失败: {response.msg}")
    except Exception as e:
        print(f"❌ 发送异常: {e}")


async def send_card(user_id: str, card_content: Dict):
    """发送卡片消息"""
    try:
        client = lark.Client.builder() \
            .app_id(FEISHU_APP_ID) \
            .app_secret(FEISHU_APP_SECRET) \
            .build()
        
        request = CreateMessageRequest.builder() \
            .receive_id_type("open_id") \
            .request_body(CreateMessageRequestBody.builder()
                .receive_id(user_id)
                .msg_type("interactive")
                .content(json.dumps(card_content))
                .build()) \
            .build()
        
        response = client.im.v1.message.create(request)
        if not response.success():
            print(f"❌ 发送卡片失败: {response.msg}")
    except Exception as e:
        print(f"❌ 发送卡片异常: {e}")


# ============ 消息回调 ============
def create_message_handler(processor: MessageProcessor):
    """创建消息处理器"""
    def on_message(data):
        try:
            event = data.event
            message = event.message
            
            user_id = event.sender.sender_id.open_id
            message_id = message.message_id
            msg_type = message.message_type
            
            # 解析文本
            text = ""
            try:
                content = json.loads(message.content)
                text = content.get("text", "").strip()
            except:
                text = ""
            
            if text:
                # 创建新任务处理（不阻塞回调）
                asyncio.create_task(processor.process(user_id, message_id, text, msg_type))
        
        except Exception as e:
            print(f"❌ 消息处理异常: {e}")
    
    return on_message


# ============ 主程序 ============
def main():
    """主程序"""
    # 初始化组件（同步）
    intent_recognizer = init_components()
    
    # 创建消息处理器
    processor = MessageProcessor(intent_recognizer)
    
    # 创建消息回调
    on_message = create_message_handler(processor)
    
    # 创建事件处理器
    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(on_message) \
        .build()
    
    # 创建 WebSocket 客户端
    ws_client = lark.ws.Client(
        FEISHU_APP_ID,
        FEISHU_APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO
    )
    
    print("\n🎯 连接飞书中...")
    print("   支持自然语言理解和 Skills 系统\n")
    
    # 启动（阻塞）
    ws_client.start()


if __name__ == "__main__":
    # 直接运行（不使用 asyncio.run）
    main()
