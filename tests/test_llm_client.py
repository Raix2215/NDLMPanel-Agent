"""
测试 LLM 客户端能否正常调通
运行: uv run python tests/test_llm_client.py
"""

import asyncio
from ndlmpanel_agent.config import LLMConfiguration
from ndlmpanel_agent.llm.chat_completion_client import ChatCompletionClient


async def test_basic_chat():
    """测试基础对话"""
    config = LLMConfiguration(
        api_key="REMOVED_API_KEY", 
        base_url="https://yunwu.ai/v1", 
        model_name="glm-4.7",  
    )

    client = ChatCompletionClient(config)

    messages = [
        {"role": "system", "content": "你是一个Linux运维助手，简洁回答问题。"},
        {"role": "user", "content": "用一句话解释什么是僵尸进程"},
    ]

    response = await client.send_messages(messages)
    print(f"AI 回复: {response.content}")
    print(f"是否有工具调用: {response.tool_calls}")


async def test_tool_calling():
    """测试工具调用"""
    config = LLMConfiguration(
        api_key="REMOVED_API_KEY",
        base_url="https://yunwu.ai/v1",
        model_name="glm-4.7",
    )

    client = ChatCompletionClient(config)

    # 定义一个工具
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_disk_usage",
                "description": "获取系统磁盘使用情况",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "要查询的路径，默认为 /",
                        }
                    },
                    "required": [],
                },
            },
        }
    ]

    messages = [
        {
            "role": "system",
            "content": "你是一个Linux运维助手。需要系统信息时请调用工具。",
        },
        {"role": "user", "content": "帮我看看磁盘还剩多少空间"},
    ]

    response = await client.send_messages(messages, tools=tools)

    if response.tool_calls:
        print("LLM 请求调用工具:")
        for tc in response.tool_calls:
            print(f"  工具名: {tc.function.name}")
            print(f"  参数: {tc.function.arguments}")
            print(f"  调用ID: {tc.id}")
    else:
        print(f"AI 直接回复: {response.content}")


if __name__ == "__main__":
    print("=== 测试基础对话 ===")
    asyncio.run(test_basic_chat())

    print("\n=== 测试工具调用 ===")
    asyncio.run(test_tool_calling())
