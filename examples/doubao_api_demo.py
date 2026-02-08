"""Doubao (豆包) API demo — 验证 endpoint 的各种调用方式。

测试内容：
1. 普通对话
2. 带 tools 的 function calling
3. 流式输出
4. 流式 + tools
5. 通过 agentica DeepAgent 调用
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(override=True)

API_KEY = os.getenv("ARK_API_KEY", "")
MODEL = os.getenv("AGENTICA_MODEL_NAME", "")
BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

SAMPLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string", "description": "城市名"}},
                "required": ["city"],
            },
        },
    }
]


def test_basic_chat(client):
    """测试1: 普通对话"""
    print("\n[Test 1] 普通对话")
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "你好，说一个字"}],
        max_tokens=10,
    )
    print(f"  OK: {resp.choices[0].message.content}")


def test_with_tools(client):
    """测试2: 带 tools 的 function calling"""
    print("\n[Test 2] Function Calling (tools)")
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "北京天气怎么样"}],
        tools=SAMPLE_TOOLS,
        max_tokens=100,
    )
    msg = resp.choices[0].message
    if msg.tool_calls:
        print(f"  OK: tool_call={msg.tool_calls[0].function.name}({msg.tool_calls[0].function.arguments})")
    else:
        print(f"  OK: content={msg.content}")


def test_stream(client):
    """测试3: 流式输出"""
    print("\n[Test 3] 流式输出")
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "用一句话介绍豆包"}],
        max_tokens=60,
        stream=True,
    )
    print("  ", end="")
    for chunk in resp:
        if chunk.choices and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="")
    print("\n  OK")


def test_stream_with_tools(client):
    """测试4: 流式 + tools"""
    print("\n[Test 4] 流式 + tools")
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "帮我查上海的天气"}],
        tools=SAMPLE_TOOLS,
        max_tokens=100,
        stream=True,
    )
    func_name, func_args = "", ""
    for chunk in resp:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta.content:
            print(f"  content: {delta.content}")
        if delta.tool_calls:
            tc = delta.tool_calls[0]
            if tc.function.name:
                func_name += tc.function.name
            if tc.function.arguments:
                func_args += tc.function.arguments
    if func_name:
        print(f"  OK: tool_call={func_name}({func_args})")
    else:
        print("  OK: no tool call")


async def test_agentica_agent():
    """测试5: 通过 agentica DeepAgent 简单调用"""
    print("\n[Test 5] agentica DeepAgent (简单模式)")
    from agentica import DeepAgent, Doubao

    agent = DeepAgent(
        model=Doubao(id=MODEL),
        description="测试 agent",
        markdown=True,
    )
    result = ""
    async for chunk in agent.arun_stream("说一个笑话，50字以内"):
        if chunk.content:
            result += chunk.content
    print(f"  OK: {result[:80]}")


async def test_agentica_stream_intermediate():
    """测试6: 模拟 agent_service.chat_stream 完整调用（stream_intermediate_steps=True）"""
    print("\n[Test 6] agentica DeepAgent (stream_intermediate_steps=True)")
    from agentica import DeepAgent, Doubao

    agent = DeepAgent(
        model=Doubao(id=MODEL),
        debug_mode=True,
        auto_load_mcp=True,
        add_datetime_to_instructions=True,
        tool_call_limit=40,
    )

    full_content = ""
    async for chunk in agent.arun_stream("你好，说一个字", stream_intermediate_steps=True):
        if chunk is None:
            continue

        event = chunk.event
        print(f"  [event={event}]", end="")

        if event == "ToolCallStarted":
            tool_info = chunk.tools[-1] if chunk.tools else None
            if tool_info:
                name = tool_info.get("tool_name") or tool_info.get("name", "?")
                print(f" tool_call: {name}")
            continue

        if event == "ToolCallCompleted":
            tool_info = chunk.tools[-1] if chunk.tools else None
            if tool_info:
                name = tool_info.get("tool_name") or tool_info.get("name", "?")
                print(f" tool_done: {name}")
            continue

        if event in ("RunStarted", "RunCompleted", "UpdatingMemory",
                     "MultiRoundTurn", "MultiRoundToolCall",
                     "MultiRoundToolResult", "MultiRoundCompleted"):
            print(f" (skipped)")
            continue

        if event == "RunResponse":
            if hasattr(chunk, 'reasoning_content') and chunk.reasoning_content:
                print(f" thinking: {chunk.reasoning_content[:50]}")
            if chunk.content:
                full_content += chunk.content
                print(f" content: {chunk.content}", end="")
            else:
                print()
        else:
            print(f" (unknown event)")

    print(f"\n  Result: {full_content[:80]}")
    print("  OK")


def main():
    print(f"豆包 API Demo")
    print(f"  Model:    {MODEL}")
    print(f"  Base URL: {BASE_URL}")
    print(f"  API Key:  {API_KEY[:8]}...{API_KEY[-4:]}" if len(API_KEY) > 12 else f"  API Key: {API_KEY}")

    from openai import OpenAI

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    # OpenAI 兼容接口测试
    test_basic_chat(client)
    test_with_tools(client)
    test_stream(client)
    test_stream_with_tools(client)

    # agentica DeepAgent 测试
    asyncio.run(test_agentica_agent())

    # 模拟 agent_service.chat_stream 完整链路
    asyncio.run(test_agentica_stream_intermediate())

    print("\n全部测试通过！")


if __name__ == "__main__":
    main()
