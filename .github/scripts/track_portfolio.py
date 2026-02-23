#!/usr/bin/env python3
"""
持仓跟踪定时任务脚本
在交易时间每半小时运行一次，自动分析持仓并推送通知
"""
import os
import sys
import asyncio
import json
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'feishu-assistant'))

from skills.portfolio_tracker_skill import PortfolioTrackerSkill
from skills.portfolio_skill import PortfolioSkill


# 配置
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
FEISHU_USER_OPEN_ID = os.environ.get("FEISHU_USER_OPEN_ID")
KIMI_API_KEY = os.environ.get("KIMI_API_KEY")

# 数据库路径（与主程序一致）
DB_PATH = "/opt/feishu-assistant/data/portfolio.db"
STATE_FILE = "/opt/feishu-assistant/data/portfolio_tracker_state.json"


async def send_feishu_message(message: str):
    """发送飞书消息"""
    try:
        import httpx
        
        # 1. 获取 access_token
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                token_url,
                json={
                    "app_id": FEISHU_APP_ID,
                    "app_secret": FEISHU_APP_SECRET
                }
            )
            data = resp.json()
            token = data.get("tenant_access_token")
            
            if not token:
                print(f"获取 token 失败: {data}")
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
                }
            )
            
            if resp.status_code == 200:
                print(f"✅ 消息发送成功")
                return True
            else:
                print(f"❌ 消息发送失败: {resp.text}")
                return False
                
    except Exception as e:
        print(f"发送消息异常: {e}")
        return False


async def check_trading_hours() -> bool:
    """检查是否在交易时间"""
    now = datetime.now()
    weekday = now.weekday()
    hour = now.hour
    minute = now.minute
    
    # 周末不交易
    if weekday >= 5:  # 5=周六, 6=周日
        print(f"📅 周末不交易: {now.strftime('%Y-%m-%d %H:%M')} 星期{weekday+1}")
        return False
    
    # A股交易时间: 9:30-11:30, 13:00-15:00
    # 港股交易时间: 9:30-12:00, 13:00-16:00
    # 美股交易时间: 21:30-04:00 (次日)
    
    time_val = hour * 60 + minute
    
    # A股上午: 9:30-11:30
    if 570 <= time_val <= 690:
        return True
    # A股下午: 13:00-15:00
    if 780 <= time_val <= 900:
        return True
    # 港股下午延长: 13:00-16:00
    if 780 <= time_val <= 960:
        return True
    
    print(f"⏰ 非交易时间: {now.strftime('%H:%M')}")
    return False


async def main():
    """主函数"""
    print("=" * 60)
    print(f"🚀 持仓跟踪任务启动 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 检查交易时间
    if not await check_trading_hours():
        print("📌 跳过执行（非交易时间）")
        return
    
    # 检查必要配置
    if not all([FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_USER_OPEN_ID]):
        print("❌ 缺少飞书配置")
        return
    
    # 初始化技能
    tracker = PortfolioTrackerSkill({
        "kimi_api_key": KIMI_API_KEY,
        "db_path": DB_PATH,
        "state_file": STATE_FILE
    })
    
    # 执行跟踪
    user_id = FEISHU_USER_OPEN_ID
    result = await tracker.execute(action="track", user_id=user_id)
    
    if not result.success:
        print(f"❌ 跟踪失败: {result.message}")
        return
    
    # 检查是否需要通知
    holdings = result.data.get("holdings", [])
    changes = result.data.get("changes", [])
    
    should_notify = tracker.should_notify(holdings, changes)
    
    if not should_notify:
        print("📌 无显著变化，跳过通知")
        print(f"   持仓数量: {len(holdings)}")
        print(f"   显著变化: {len(changes)}")
        return
    
    # 发送通知
    print(f"📤 发送通知...")
    print(f"   持仓数量: {len(holdings)}")
    print(f"   显著变化: {len(changes)}")
    
    success = await send_feishu_message(result.message)
    
    if success:
        print("✅ 任务完成")
    else:
        print("❌ 发送失败")
    
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
