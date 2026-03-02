"""
测试 EvoAgentSkill
"""
import asyncio
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 尝试从 .env 文件加载环境变量
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if value and value != "your_app_id" and value != "your_kimi_api_key" and value != "your_minimax_api_key":
                    os.environ[key] = value
                    print(f"加载环境变量: {key}")

from skills.evo_agent_skill import EvoAgentSkill


async def test_evo_agent():
    """测试 EvoAgentSkill"""

    # 检查 API keys
    kimi_key = os.environ.get("KIMI_API_KEY")
    minimax_key = os.environ.get("MINIMAX_API_KEY")

    print("=" * 50)
    print("EvoAgentSkill 测试")
    print("=" * 50)
    print(f"KIMI_API_KEY: {'已设置' if kimi_key else '未设置'}")
    print(f"MINIMAX_API_KEY: {'已设置' if minimax_key else '未设置'}")
    print()

    if not kimi_key and not minimax_key:
        print("❌ 请设置 KIMI_API_KEY 或 MINIMAX_API_KEY")
        return

    # 创建 EvoAgentSkill 实例
    skill = EvoAgentSkill(config={
        "llm_api_key": kimi_key,
        "minimax_api_key": minimax_key,
        "default_model": "kimi_k2.5"
    })

    # 测试1: 使用 Kimi K2.5 生成设计
    print("\n" + "=" * 50)
    print("测试1: 使用 Kimi K2.5 生成天气查询技能设计")
    print("=" * 50)

    result = await skill.execute(requirement="帮我创建一个查询天气的技能")

    print(f"\n结果: {result.message[:500]}...")

    # 提取 design_id
    if result.data and result.data.get("design_id"):
        design_id = result.data["design_id"]
        print(f"\n设计ID: {design_id}")

        # 测试2: 确认设计
        print("\n" + "=" * 50)
        print("测试2: 确认设计并生成代码")
        print("=" * 50)

        confirm_result = await skill.execute(
            requirement="确认",
            confirm_design=True,
            design_id=design_id
        )

        print(f"\n确认结果: {confirm_result.message[:300]}...")

    # 测试3: 使用 MiniMax M2.5
    if minimax_key:
        print("\n" + "=" * 50)
        print("测试3: 使用 MiniMax M2.5 生成新闻查询技能设计")
        print("=" * 50)

        skill2 = EvoAgentSkill(config={
            "llm_api_key": kimi_key,
            "minimax_api_key": minimax_key,
            "default_model": "minimax_m2.5"
        })

        result2 = await skill2.execute(requirement="用 minimax 创建一个查询新闻的技能")

        print(f"\n结果: {result2.message[:500]}...")

        if result2.data and result2.data.get("design_id"):
            design_id2 = result2.data["design_id"]
            print(f"\n设计ID: {design_id2}")

            # 确认设计
            confirm_result2 = await skill2.execute(
                requirement="确认",
                confirm_design=True,
                design_id=design_id2
            )

            print(f"\n确认结果: {confirm_result2.message[:300]}...")

    print("\n" + "=" * 50)
    print("测试完成!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_evo_agent())
