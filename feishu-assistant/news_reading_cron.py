#!/usr/bin/env python3
"""
新闻精读定时任务 - 每天获取纽约时报和经济学人精选新闻
生成英文原文 + 重点单词 + 句子讲解，保存到飞书文档

用法:
  # 运行一次
  /usr/bin/python3.11 news_reading_cron.py
"""
import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime

# 添加项目路径
SCRIPT_DIR = Path(__file__).parent
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

from skills.news_reading_skill import NewsReadingSkill


async def main():
    """主函数"""
    now = datetime.now()
    print(f"📰 新闻精读任务 - {now.strftime('%Y-%m-%d %H:%M:%S')}")

    # 检查配置
    feishu_app_id = os.environ.get("FEISHU_APP_ID")
    feishu_app_secret = os.environ.get("FEISHU_APP_SECRET")
    kimi_api_key = os.environ.get("KIMI_API_KEY")

    if not all([feishu_app_id, feishu_app_secret, kimi_api_key]):
        print("❌ 缺少配置")
        return 1

    # 初始化技能
    skill = NewsReadingSkill(config={
        "kimi_api_key": kimi_api_key
    })

    # 执行
    print("📥 开始获取新闻...")
    result = await skill.fetch_daily_news()

    if result.success:
        print("✅ 任务完成")
        print(result.message)
    else:
        print("❌ 任务失败")
        print(result.message)

    return 0 if result.success else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
