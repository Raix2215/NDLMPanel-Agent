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

class ToolCallRequest(BaseModel):
    """单个工具调用请求，从 LLM 响应中提取"""
    id: str           # 必须保留，塞回 messages 时用
    functionName: str
    arguments: str    # 保持 JSON 字符串，解析交给 ToolRegistry

class LLMCompletionResult(BaseModel):
    content: str | None = None
    toolCalls: list[ToolCallRequest] | None = None  # 用具名 model 替代裸 dict
    reasoningContent: str | None = None
    finishReason: str = "stop"
    refusal: str | None = None   # 模型拒绝时有值，安全校验可以读
    totalTokensUsed: int | None = None  # 审计日志用
    model: str | None = None  # 审计日志用，记录是哪个模型的响应
