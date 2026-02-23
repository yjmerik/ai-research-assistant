#!/usr/bin/env python3
"""
持仓跟踪定时任务 - 服务器本地运行
添加到 crontab: */30 9-11,13-15 * * 1-5 /opt/feishu-assistant/venv/bin/python /opt/feishu-assistant/scripts/portfolio_tracker_cron.py
"""
import os
import sys
import asyncio
import json
from datetime import datetime
from pathlib import Path

# 添加项目路径
SCRIPT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPT_DIR / "app"))

# 加载环境变量
env_file = SCRIPT_DIR / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

from skills.portfolio_tracker_skill import PortfolioTrackerSkill


# 配置
DB_PATH = SCRIPT_DIR / "data" / "portfolio.db"
STATE_FILE = SCRIPT_DIR / "data" / "portfolio_tracker_state.json"

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
FEISHU_USER_OPEN_ID = os.environ.get("FEISHU_USER_OPEN_ID")
KIMI_API_KEY = os.environ.get("KIMI_API_KEY")


async def send_feishu_message(message: str) -> bool:
    """发送飞书消息"""
    try:
        import httpx
        
        # 1. 获取 access_token
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
        async with httpx.AsyncClient() as client:
            resp = await client.post(token_url, json={
                "app_id": FEISHU_APP_ID,
                "app_secret": FEISHU_APP_SECRET
            }, timeout=10)
            data = resp.json()
            token = data.get("tenant_access_token")
            
            if not token:
                print(f"❌ 获取 token 失败: {data}")
                return False
            
            # 2. 发送消息
            msg_url = "https://open.feishu.cn/open-apis/im/v1/messages"
            resp = await client.post(
                msg_url,
                headers={"Authorization": f"Bearer {token}"},
                params={"receive_id_type": "open_id"},
                json={
                    "receive_id": FEISHU_USER_OPEN_ID,
                    "msg_type": "text",
                    "content": json.dumps({"text": message})
                },
                timeout=10
            )
            
            if resp.status_code == 200:
                result = resp.json()
                if result.get("code") == 0:
                    print(f"✅ 消息发送成功")
                    return True
                else:
                    print(f"❌ API 错误: {result}")
                    return False
            else:
                print(f"❌ HTTP 错误: {resp.status_code} - {resp.text}")
                return False
                
    except Exception as e:
        print(f"❌ 发送异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_trading_hours() -> bool:
    """检查是否在交易时间（中国大陆）"""
    now = datetime.now()
    weekday = now.weekday()
    hour = now.hour
    minute = now.minute
    
    print(f"⏰ 当前时间: {now.strftime('%Y-%m-%d %H:%M')} 星期{weekday+1}")
    
    # 周末不交易
    if weekday >= 5:
        print("📅 周末休市")
        return False
    
    time_val = hour * 60 + minute
    
    # A股上午: 9:30-11:30 (570-690)
    if 570 <= time_val <= 690:
        print("📈 A股上午交易时段")
        return True
    
    # A股下午: 13:00-15:00 (780-900)
    if 780 <= time_val <= 900:
        print("📈 A股下午交易时段")
        return True
    
    # 港股下午延长到 16:00 (960)
    if 780 <= time_val <= 960:
        print("📈 港股交易时段")
        return True
    
    print("⏸️ 非交易时间")
    return False


async def main():
    """主函数"""
    print("=" * 60)
    print(f"🚀 持仓跟踪任务 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 检查交易时间
    if not check_trading_hours():
        print("📌 跳过执行（非交易时间）")
        return 0
    
    # 检查必要配置
    if not all([FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_USER_OPEN_ID]):
        print("❌ 缺少飞书配置")
        return 1
    
    # 检查数据库是否存在
    if not DB_PATH.exists():
        print(f"❌ 数据库不存在: {DB_PATH}")
        return 1
    
    # 初始化技能
    tracker = PortfolioTrackerSkill({
        "kimi_api_key": KIMI_API_KEY,
        "db_path": str(DB_PATH),
        "state_file": str(STATE_FILE),
        "feishu_app_id": FEISHU_APP_ID,
        "feishu_app_secret": FEISHU_APP_SECRET
    })
    
    # 执行跟踪
    user_id = FEISHU_USER_OPEN_ID
    result = await tracker.execute(action="track", user_id=user_id)
    
    if not result.success:
        print(f"❌ 跟踪失败: {result.message}")
        # 即使失败也发送通知，让用户知道
        await send_feishu_message(f"⚠️ 持仓跟踪异常\n\n{result.message}")
        return 1
    
    # 检查是否需要通知
    holdings = result.data.get("holdings", [])
    changes = result.data.get("changes", []) if result.data else []
    
    print(f"📊 持仓数量: {len(holdings)}")
    print(f"📊 显著变化: {len(changes)}")
    
    should_notify = tracker.should_notify(holdings, changes)
    
    # 检查是否强制通知（通过命令行参数）
    force_notify = len(sys.argv) > 1 and sys.argv[1] == "--force"
    
    if not should_notify and not force_notify:
        print("📌 无显著变化，跳过通知")
        print("=" * 60)
        return 0
    
    # 发送通知
    print(f"📤 发送通知到飞书...")
    success = await send_feishu_message(result.message)
    
    if success:
        print("✅ 通知发送成功")
    else:
        print("❌ 通知发送失败")
    
    print("=" * 60)
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
