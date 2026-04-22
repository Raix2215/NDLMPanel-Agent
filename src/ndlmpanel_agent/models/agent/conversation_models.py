"""
对话上下文数据模型

核心数据结构：多叉树（N-ary Tree）

为什么用树而不是列表？
- 列表只能表达线性对话，重新生成/编辑历史/切换模型响应时旧数据会丢失
- 树天然支持分支：同一个 user 消息下可以挂多个 assistant 回复（不同模型、重新生成等）
- 导出给 LLM 时，从 root 沿活跃路径走到 leaf，收集一条链即可

存储方式：
- 所有节点存在 dict[nodeId → ConversationNode] 中（扁平存储，O(1) 查找）
- 父子关系通过 parentId / childrenIds 引用
- activeLeafId 标记当前活跃路径的末端
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────────────────
# 消息角色（复用已有定义，但这里独立声明以避免循环导入）
# ──────────────────────────────────────────────────────────────────────────────


class MessageRole(str, Enum):
    """消息角色，对应 OpenAI API 的 role 字段"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


# ──────────────────────────────────────────────────────────────────────────────
# 消息体（对应 OpenAI API 的一条 message）
# ──────────────────────────────────────────────────────────────────────────────


class ToolCallData(BaseModel):
    """
    工具调用信息，嵌在 assistant 消息的 toolCalls 字段里。
    对应 OpenAI API 的 tool_calls[i] 结构。
    """

    id: str  # LLM 生成的调用 ID，tool 消息回传时需要匹配
    functionName: str
    arguments: str  # JSON 字符串，保持原样不解析


class ChatMessagePayload(BaseModel):
    """
    消息体，完整表达 OpenAI API 的一条 message。

    不同 role 使用不同字段：
    - system:    content
    - user:      content
    - assistant: content + toolCalls（可选）
    - tool:      content + toolCallId + name
    """

    role: MessageRole
    content: str | None = None
    toolCalls: list[ToolCallData] | None = None  # assistant 专用
    toolCallId: str | None = None  # tool 专用：关联 assistant 的 tool_call.id
    name: str | None = None  # tool 专用：工具函数名

    def to_openai_dict(self) -> dict:
        """
        序列化为 OpenAI API 期望的 dict 格式。
        ChatCompletionClient.send_messages() 直接接收 list[dict]。
        """
        d: dict = {"role": self.role.value, "content": self.content or ""}

        # assistant 消息带 tool_calls
        if self.role == MessageRole.ASSISTANT and self.toolCalls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.functionName,
                        "arguments": tc.arguments,
                    },
                }
                for tc in self.toolCalls
            ]
            # OpenAI 要求：有 tool_calls 时 content 可以为 null
            if not self.content:
                d["content"] = None

        # tool 消息需要 tool_call_id 和 name
        if self.role == MessageRole.TOOL:
            d["tool_call_id"] = self.toolCallId or ""
            if self.name:
                d["name"] = self.name

        return d


# ──────────────────────────────────────────────────────────────────────────────
# 节点元信息
# ──────────────────────────────────────────────────────────────────────────────


class ConversationNodeMeta(BaseModel):
    """
    节点元信息，记录生成该消息时的上下文。
    主要用于审计日志和多模型对比。
    """

    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model: str | None = None  # 哪个模型生成的（assistant 节点才有值）
    tokenCount: int | None = None  # 该消息消耗的 token 估算
    reasoningContent: str | None = None  # 思维链（DeepSeek/o系列，审计用，不传前端）


# ──────────────────────────────────────────────────────────────────────────────
# 对话节点（树的核心）
# ──────────────────────────────────────────────────────────────────────────────


def _generate_node_id() -> str:
    """生成节点 ID，使用 UUID4 的短格式（前 12 位，碰撞概率极低）"""
    return uuid.uuid4().hex[:12]


class ConversationNode(BaseModel):
    """
    对话树的单个节点。

    每个节点包含一条消息（payload）和树形关系（parent/children）。
    通过 parentId 和 childrenIds 构成多叉树。

    分支产生的时机：
    - 重新生成回复：同一 parent 下新增 assistant 子节点
    - 编辑历史消息：在 parent 下新增修改后的 user 子节点
    - 切换模型响应：同一 user 下挂不同模型的 assistant 子节点
    """

    nodeId: str = Field(default_factory=_generate_node_id)
    parentId: str | None = None  # root 节点为 None
    childrenIds: list[str] = Field(default_factory=list)
    payload: ChatMessagePayload
    meta: ConversationNodeMeta = Field(default_factory=ConversationNodeMeta)


# ──────────────────────────────────────────────────────────────────────────────
# 会话（一棵完整的对话树）
# ──────────────────────────────────────────────────────────────────────────────


class ConversationSession:
    """
    单个对话会话，包含一棵完整的消息树。

    核心数据：
    - nodes: 扁平存储所有节点，O(1) 查找
    - rootNodeId: 树根（system prompt 节点）
    - activeLeafId: 当前活跃路径的末端节点

    导出给 LLM 时：从 root 沿活跃路径走到 activeLeaf，收集有序消息列表。
    """

    def __init__(self, sessionId: str, systemPrompt: str) -> None:
        self.sessionId = sessionId
        self.nodes: dict[str, ConversationNode] = {}
        self.createdAt: float = datetime.now(timezone.utc).timestamp()
        self.lastActiveAt: float = self.createdAt
        self.pendingAction: dict | None = None  # 高危操作挂起
        self.lock = asyncio.Lock()  # 同一 session 串行处理

        # 创建 root 节点（system prompt）
        root = ConversationNode(
            parentId=None,
            payload=ChatMessagePayload(
                role=MessageRole.SYSTEM,
                content=systemPrompt,
            ),
        )
        self.nodes[root.nodeId] = root
        self.rootNodeId: str = root.nodeId
        self.activeLeafId: str = root.nodeId

    def touch(self) -> None:
        """更新最后活跃时间"""
        self.lastActiveAt = datetime.now(timezone.utc).timestamp()

    def is_expired(self, ttlSeconds: int) -> bool:
        """检查 session 是否过期"""
        return (datetime.now(timezone.utc).timestamp() - self.lastActiveAt) > ttlSeconds
