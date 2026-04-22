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
    toolCallId: str | None = None


class AgentResponse(BaseModel):
    """Agent 返回给后端的完整响应"""

    reply: str
    toolCallsMade: list[str] = []
    riskLevel: str = "low"
    requiresHumanConfirm: bool = False
    pendingAction: dict | None = None

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
