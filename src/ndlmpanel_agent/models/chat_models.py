from pydantic import BaseModel
from enum import Enum
from datetime import datetime


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ChatMessage(BaseModel):
    """单条对话消息"""

    role: MessageRole
    content: str
    timestamp: datetime
    tool_call_id: str | None = None  # 工具调用结果关联用


class AgentResponse(BaseModel):
    """Agent 返回给后端的完整响应"""

    reply: str  # 最终文本回复
    tool_calls_made: list[str] = []  # 本轮调用了哪些工具
    risk_level: str = "low"  # 本轮风险等级
    requires_human_confirm: bool = False  # 是否需要人工确认
    pending_action: dict | None = None  # 待确认的操作详情

class LLMCompletionResult(BaseModel):
    """
    LLM 单次调用的完整结果
    把 openai SDK 的原始响应转成我们自己的结构
    """

    content: str | None = None  # 文本回复
    tool_calls: list[dict] | None = None  # 工具调用请求
    reasoning_content: str | None = None  # 思维链（如果模型支持）
    finish_reason: str = "stop"  # stop / tool_calls