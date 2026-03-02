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
from skills.portfolio_tracker_skill import PortfolioTrackerSkill
from skills.news_reading_skill import NewsReadingSkill
from skills.evo_agent_skill import EvoAgentSkill


# ============ 配置 ============
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
KIMI_API_KEY = os.environ.get("KIMI_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
QVERIS_API_KEY = os.environ.get("QVERIS_API_KEY")

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
    registry.register(StockSkill(config={"kimi_api_key": KIMI_API_KEY, "qveris_api_key": QVERIS_API_KEY}))
    registry.register(PortfolioSkill(config={"kimi_api_key": KIMI_API_KEY}))
    registry.register(PortfolioTrackerSkill(config={"kimi_api_key": KIMI_API_KEY}))
    registry.register(NewsReadingSkill(config={"kimi_api_key": KIMI_API_KEY}))
    registry.register(EvoAgentSkill(config={"llm_api_key": KIMI_API_KEY}))

    # 3. 加载持久化的自动生成技能
    _load_persisted_skills()

    print(f"\n✅ 已注册 {len(registry.list_skills())} 个技能:")
    for name in registry.list_skills():
        print(f"   - {name}")

    return intent_recognizer


def _load_persisted_skills():
    """加载持久化的自动生成技能"""
    try:
        from skills.evo_agent_skill import EvoAgentSkill

        # 加载已保存的技能
        persisted_skills = EvoAgentSkill.load_persisted_skills()

        if not persisted_skills:
            return

        # 创建 EvoAgentSkill 实例用于创建技能
        evo_skill = EvoAgentSkill(config={"llm_api_key": KIMI_API_KEY})

        for skill_name, data in persisted_skills.items():
            try:
                design = data.get("design", {})
                code = data.get("code", "")

                if not design or not code:
                    continue

                # 创建技能实例
                skill_instance = evo_skill._create_skill_from_code(skill_name, design, code)

                if skill_instance:
                    registry.register(skill_instance)
                    print(f"   ✅ 已加载技能: {skill_name}")
            except Exception as e:
                print(f"   ❌ 加载技能失败 {skill_name}: {e}")

    except Exception as e:
        print(f"[EvoAgent] 加载持久化技能失败: {e}")


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
        """处理快捷命令（支持首字母/前两个字母简写）"""
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # 完整命令映射表
        command_definitions = {
            "/market": {
                "skill": "query_market",
                "params": {"market": args.upper() if args else "US"},
                "shortcuts": ["m", "ma"]
            },
            "/github": {
                "skill": "search_github", 
                "params": {"keywords": args or "ai-agent"},
                "shortcuts": ["g", "gh"]
            },
            "/paper": {
                "skill": "search_papers",
                "params": {"topic": args or "AI"},
                "shortcuts": ["p", "pa"]
            },
            "/chat": {
                "skill": "chat",
                "params": {"message": args or "你好"},
                "shortcuts": ["c", "ch"]
            },
            "/help": {
                "skill": "chat",
                "params": {"message": "帮助"},
                "shortcuts": ["h", "he"]
            },
            "/clear": {
                "skill": "chat",
                "params": {"message": "清除"},
                "shortcuts": ["cl"]
            },
            "/status": {
                "skill": "chat",
                "params": {"message": "状态"},
                "shortcuts": ["s", "st"]
            },
            "/portfolio": {
                "skill": "manage_portfolio",
                "params": {"action": "query", "user_id": user_id},
                "shortcuts": ["po", "pt"]
            },
            "/持仓": {
                "skill": "manage_portfolio",
                "params": {"action": "query", "user_id": user_id},
                "shortcuts": []
            },
            "/reset": {
                "skill": "manage_portfolio",
                "params": {"action": "reset", "user_id": user_id, "confirm": False},
                "shortcuts": ["r", "rs"]
            },
            "/reset confirm": {
                "skill": "manage_portfolio",
                "params": {"action": "reset", "user_id": user_id, "confirm": True},
                "shortcuts": []
            },
            "/track": {
                "skill": "track_portfolio",
                "params": {"action": "track", "user_id": user_id},
                "shortcuts": ["tr", "tk"]
            },
            "/evo": {
                "skill": "evo_agent",
                "params": {"requirement": args or ""},
                "shortcuts": ["e", "ev"]
            },
            "/create": {
                "skill": "evo_agent",
                "params": {"requirement": args or ""},
                "shortcuts": ["cr"]
            },
            "/追踪": {
                "skill": "track_portfolio",
                "params": {"action": "track", "user_id": user_id},
                "shortcuts": []
            },
        }
        
        # 首先尝试精确匹配
        if cmd in command_definitions:
            cmd_def = command_definitions[cmd]
            skill = registry.get(cmd_def["skill"])
            return await skill.execute(**cmd_def["params"])
        
        # 尝试模糊匹配（去除开头的 /）
        cmd_input = cmd[1:] if cmd.startswith('/') else cmd
        
        if cmd_input:
            matches = []
            for full_cmd, definition in command_definitions.items():
                # 检查是否匹配完整命令名（去掉/）
                full_name = full_cmd[1:]  # 去掉 /
                if full_name.startswith(cmd_input):
                    matches.append((full_cmd, definition))
                # 检查是否匹配 shortcuts
                elif cmd_input in definition.get("shortcuts", []):
                    matches.append((full_cmd, definition))
            
            if len(matches) == 1:
                # 唯一匹配
                full_cmd, cmd_def = matches[0]
                skill = registry.get(cmd_def["skill"])
                return await skill.execute(**cmd_def["params"])
            elif len(matches) > 1:
                # 多个匹配，提示用户
                cmd_names = [m[0] for m in matches]
                return SkillResult(
                    success=False,
                    message=f"⚠️ 命令 `{cmd}` 有多个匹配:\n" + 
                            "\n".join([f"• {n}" for n in cmd_names]) +
                            f"\n\n请输入完整命令"
                )
        
        # 没有匹配
        return SkillResult(
            success=False,
            message=f"❓ 未知命令: {cmd}\n\n" +
                    "📋 可用命令:\n" +
                    "• /m /ma → 市场查询\n" +
                    "• /g /gh → GitHub趋势\n" +
                    "• /p /pa → 论文搜索\n" +
                    "• /po /pt → 持仓查询\n" +
                    "• /e /evo → 创建新技能\n" +
                    "• /h → 帮助\n" +
                    "• /s /st → 状态\n" +
                    "• /c /cl → 聊天/清除"
        )
    
    async def _handle_natural_language(self, text: str, session: Dict) -> SkillResult:
        """处理自然语言"""

        # 检查是否是确认设计（格式：确认 {design_id}）
        import re
        confirm_match = re.match(r"确认\s+([a-f0-9]+)", text, re.IGNORECASE)
        if confirm_match:
            design_id = confirm_match.group(1)
            skill = registry.get("evo_agent")
            return await skill.execute(requirement="", confirm_design=True, design_id=design_id)

        # 先检查是否是持仓查询
        if any(kw in text for kw in ["持仓", "我的股票", "持仓情况", "查看持仓"]):
            skill = registry.get("manage_portfolio")
            return await skill.execute(action="query", user_id=session.get("user_id", "default"))
        
        # 检查是否是交易记录消息（买入/卖出）- 使用智能解析
        portfolio_skill = registry.get("manage_portfolio")
        trade_info = await portfolio_skill.smart_parse_trade(text)
        if trade_info:
            return await portfolio_skill.execute(
                action="record",
                user_id=session.get("user_id", "default"),
                stock_name=trade_info["stock_name"],
                trade_action=trade_info["action"],
                price=trade_info["price"],
                shares=trade_info["shares"],
                currency=trade_info.get("currency", "CNY")
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
