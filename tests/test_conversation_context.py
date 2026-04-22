"""
ConversationContextManager 验证测试
运行方式：uv run python tests/test_conversation_context.py

测试覆盖：
  1. Session 生命周期（创建、获取、删除）
  2. 消息追加（user → assistant → tool → assistant 完整流程）
  3. 树形结构验证（父子关系、活跃路径）
  4. OpenAI 消息格式导出
  5. 清空上下文
  6. 模拟完整 ReAct Loop 场景
"""

import json

from ndlmpanel_agent.agent.conversation_context_manager import (
    ConversationContextManager,
)
from ndlmpanel_agent.config import ContextConfiguration
from ndlmpanel_agent.models.agent.conversation_models import (
    ConversationNodeMeta,
    ToolCallData,
)


def section(title: str) -> None:
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print(f"{'═' * 60}")


def ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def fail(msg: str) -> None:
    print(f"  ❌ {msg}")


def info(msg: str) -> None:
    print(f"  ℹ  {msg}")


# ──────────────────────────────────────────────────────────────────────────────
# 测试 1：Session 生命周期
# ──────────────────────────────────────────────────────────────────────────────


def test_session_lifecycle(mgr: ConversationContextManager) -> None:
    section("测试 1：Session 生命周期")

    s1 = mgr.getOrCreate("user1:conv1")
    s2 = mgr.getOrCreate("user1:conv2")
    s3 = mgr.getOrCreate("user2:conv1")

    if len(mgr.listSessions()) == 3:
        ok(f"创建了 3 个 session: {mgr.listSessions()}")
    else:
        fail(f"session 数量不对: {len(mgr.listSessions())}")

    s1_again = mgr.getOrCreate("user1:conv1")
    if s1 is s1_again:
        ok("重复获取返回同一个 session 对象")
    else:
        fail("重复获取返回了不同对象")

    if mgr.get("nonexistent") is None:
        ok("get 不存在的 session 返回 None")
    else:
        fail("get 不存在的 session 应返回 None")

    mgr.delete("user1:conv2")
    if len(mgr.listSessions()) == 2:
        ok("删除后 session 数量正确")
    else:
        fail(f"删除后 session 数量不对: {len(mgr.listSessions())}")


# ──────────────────────────────────────────────────────────────────────────────
# 测试 2：消息追加 + 树形结构
# ──────────────────────────────────────────────────────────────────────────────


def test_message_append(mgr: ConversationContextManager) -> None:
    section("测试 2：消息追加 + 树形结构")

    session = mgr.getOrCreate("test:append", systemPrompt="你是测试助手")

    # 初始状态：只有 root（system）
    path = mgr.getActivePath(session)
    if len(path) == 1 and path[0].payload.role.value == "system":
        ok(f"初始状态：1 个 root 节点，content='{path[0].payload.content}'")
    else:
        fail(f"初始状态异常: {len(path)} 个节点")

    # 追加 user 消息
    user_node = mgr.appendUserMessage(session, "帮我查一下 CPU 占用")
    path = mgr.getActivePath(session)
    if len(path) == 2 and path[1].payload.content == "帮我查一下 CPU 占用":
        ok("追加 user 消息成功")
    else:
        fail(f"user 消息追加异常: {len(path)} 个节点")

    # 追加 assistant 消息（带 tool_calls）
    tool_calls = [
        ToolCallData(
            id="call_abc123",
            functionName="getCpuInfo",
            arguments="{}",
        )
    ]
    assistant_node = mgr.appendAssistantMessage(
        session,
        content=None,
        toolCalls=tool_calls,
        meta=ConversationNodeMeta(model="deepseek-chat", tokenCount=50),
    )
    path = mgr.getActivePath(session)
    if len(path) == 3 and path[2].payload.toolCalls is not None:
        ok(f"追加 assistant(tool_calls) 成功，模型: {path[2].meta.model}")
    else:
        fail("assistant 消息追加异常")

    # 追加 tool 结果
    tool_node = mgr.appendToolResult(
        session,
        toolCallId="call_abc123",
        toolName="getCpuInfo",
        content='{"modelName": "Intel i7", "usagePercent": 45.2}',
    )
    path = mgr.getActivePath(session)
    if len(path) == 4 and path[3].payload.role.value == "tool":
        ok(f"追加 tool 结果成功，toolCallId={path[3].payload.toolCallId}")
    else:
        fail("tool 结果追加异常")

    # 追加最终 assistant 回复
    final_node = mgr.appendAssistantMessage(
        session,
        content="当前 CPU 占用 45.2%，型号是 Intel i7。",
    )
    path = mgr.getActivePath(session)
    if len(path) == 5:
        ok(f"完整对话路径：{len(path)} 个节点")
    else:
        fail(f"路径长度不对: {len(path)}")

    # 验证父子关系
    info("验证树形父子关系...")
    root = session.nodes[session.rootNodeId]
    if len(root.childrenIds) == 1 and root.childrenIds[0] == user_node.nodeId:
        ok("root → user 父子关系正确")
    else:
        fail(f"root 的 children 不对: {root.childrenIds}")

    if user_node.parentId == root.nodeId:
        ok("user.parentId 指向 root")
    else:
        fail(f"user.parentId 不对: {user_node.parentId}")

    info(f"树中总节点数: {len(session.nodes)}")
    if len(session.nodes) == 5:
        ok("总节点数正确（system + user + assistant + tool + assistant）")
    else:
        fail(f"总节点数不对: {len(session.nodes)}")


# ──────────────────────────────────────────────────────────────────────────────
# 测试 3：OpenAI 消息格式导出
# ──────────────────────────────────────────────────────────────────────────────


def test_openai_export(mgr: ConversationContextManager) -> None:
    section("测试 3：OpenAI 消息格式导出")

    session = mgr.get("test:append")
    if session is None:
        fail("session 不存在，跳过")
        return

    messages = mgr.toOpenAIMessages(session)

    for i, msg in enumerate(messages):
        role = msg["role"]
        content_preview = str(msg.get("content", ""))[:50]
        has_tc = "tool_calls" in msg
        has_tcid = "tool_call_id" in msg
        info(
            f"  [{i}] role={role}, content={content_preview!r}"
            f"{'...' if len(str(msg.get('content', ''))) > 50 else ''}"
            f"{', has tool_calls' if has_tc else ''}"
            f"{', tool_call_id=' + msg['tool_call_id'] if has_tcid else ''}"
        )

    if messages[0]["role"] == "system":
        ok("messages[0] 是 system")
    else:
        fail(f"messages[0] 应该是 system，实际: {messages[0]['role']}")

    if messages[1]["role"] == "user":
        ok("messages[1] 是 user")
    else:
        fail(f"messages[1] 应该是 user，实际: {messages[1]['role']}")

    if "tool_calls" in messages[2]:
        tc = messages[2]["tool_calls"][0]
        if tc["type"] == "function" and tc["function"]["name"] == "getCpuInfo":
            ok("messages[2] assistant 的 tool_calls 格式正确")
        else:
            fail(f"tool_calls 格式不对: {tc}")
    else:
        fail("messages[2] 应该有 tool_calls")

    if messages[3]["role"] == "tool" and messages[3].get("tool_call_id") == "call_abc123":
        ok("messages[3] tool 消息的 tool_call_id 正确")
    else:
        fail(f"messages[3] tool 消息格式不对: {messages[3]}")

    if messages[4]["role"] == "assistant" and "45.2%" in messages[4]["content"]:
        ok("messages[4] 最终 assistant 回复正确")
    else:
        fail(f"messages[4] 不对: {messages[4]}")


# ──────────────────────────────────────────────────────────────────────────────
# 测试 4：清空上下文
# ──────────────────────────────────────────────────────────────────────────────


def test_clear(mgr: ConversationContextManager) -> None:
    section("测试 4：清空上下文")

    session = mgr.getOrCreate("test:clear", systemPrompt="测试清空")
    mgr.appendUserMessage(session, "消息1")
    mgr.appendAssistantMessage(session, "回复1")
    mgr.appendUserMessage(session, "消息2")

    info(f"清空前：{mgr.getMessageCount(session)} 条消息，{len(session.nodes)} 个节点")

    mgr.clear(session, keepSystem=True)
    path = mgr.getActivePath(session)
    if len(path) == 1 and path[0].payload.role.value == "system":
        ok(f"清空后保留 system，节点数: {len(session.nodes)}")
    else:
        fail(f"清空后状态异常: {len(path)} 个节点")

    mgr.appendUserMessage(session, "清空后的新消息")
    if mgr.getMessageCount(session) == 2:
        ok("清空后可以继续追加消息")
    else:
        fail(f"清空后追加异常: {mgr.getMessageCount(session)} 条")


# ──────────────────────────────────────────────────────────────────────────────
# 测试 5：模拟完整 ReAct Loop
# ──────────────────────────────────────────────────────────────────────────────


def test_react_loop_simulation(mgr: ConversationContextManager) -> None:
    section("测试 5：模拟完整 ReAct Loop")

    session = mgr.getOrCreate("test:react", systemPrompt="你是运维助手")

    mgr.appendUserMessage(session, "帮我查一下磁盘占用最高的分区")

    mgr.appendAssistantMessage(
        session,
        content=None,
        toolCalls=[
            ToolCallData(id="call_001", functionName="getDiskInfo", arguments="{}"),
        ],
    )

    mgr.appendToolResult(
        session,
        toolCallId="call_001",
        toolName="getDiskInfo",
        content='[{"mountPoint": "/", "usagePercent": 78.5}, {"mountPoint": "/home", "usagePercent": 92.1}]',
    )

    mgr.appendAssistantMessage(
        session,
        content="发现 /home 分区占用 92.1%，我来查一下具体哪些大文件。",
        toolCalls=[
            ToolCallData(
                id="call_002",
                functionName="listDirectory",
                arguments='{"targetPath": "/home"}',
            ),
        ],
    )

    mgr.appendToolResult(
        session,
        toolCallId="call_002",
        toolName="listDirectory",
        content='[{"fileName": "logs", "sizeBytes": 5368709120}]',
    )

    mgr.appendAssistantMessage(
        session,
        content="/home 分区占用 92.1%，主要是 logs 目录占了 5GB。建议清理旧日志。",
    )

    messages = mgr.toOpenAIMessages(session)
    info(f"完整 ReAct Loop 共 {len(messages)} 条消息")

    roles = [m["role"] for m in messages]
    expected = ["system", "user", "assistant", "tool", "assistant", "tool", "assistant"]
    info(f"角色序列: {roles}")

    if roles == expected:
        ok("消息角色序列完全正确")
    else:
        fail(f"角色序列不匹配，期望: {expected}")

    tc_id_1 = messages[2]["tool_calls"][0]["id"]
    tc_ref_1 = messages[3]["tool_call_id"]
    if tc_id_1 == tc_ref_1 == "call_001":
        ok(f"第 1 轮 tool_call_id 配对正确: {tc_id_1}")
    else:
        fail(f"第 1 轮配对错误: {tc_id_1} vs {tc_ref_1}")

    tc_id_2 = messages[4]["tool_calls"][0]["id"]
    tc_ref_2 = messages[5]["tool_call_id"]
    if tc_id_2 == tc_ref_2 == "call_002":
        ok(f"第 2 轮 tool_call_id 配对正确: {tc_id_2}")
    else:
        fail(f"第 2 轮配对错误: {tc_id_2} vs {tc_ref_2}")

    if "92.1%" in messages[-1]["content"] and "logs" in messages[-1]["content"]:
        ok("最终回复内容正确")
    else:
        fail(f"最终回复不对: {messages[-1]['content']}")

    info(f"树中总节点数: {len(session.nodes)}")


# ──────────────────────────────────────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────────────────────────────────────


def main() -> None:
    print("\n🌳 ConversationContextManager 验证测试")

    config = ContextConfiguration(
        max_context_tokens=32000,
        session_ttl_seconds=1800,
        default_system_prompt="默认系统提示",
    )
    mgr = ConversationContextManager(config)

    test_session_lifecycle(mgr)
    test_message_append(mgr)
    test_openai_export(mgr)
    test_clear(mgr)
    test_react_loop_simulation(mgr)

    section("全部测试完成")


if __name__ == "__main__":
    main()
