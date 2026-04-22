"""
安全校验数据模型
"""

from enum import Enum

from pydantic import BaseModel


class SafetyVerdict(str, Enum):
    """安全校验结论"""

    ALLOW = "allow"  # 放行
    DENY = "deny"  # 拒绝（如 prompt injection）
    REQUIRE_CONFIRM = "require_confirm"  # 需要人工确认


class SafetyCheckResult(BaseModel):
    """
    SafetyGuard 对单次工具调用的校验结果。

    Orchestrator 根据 verdict 决定：
    - ALLOW → 直接执行
    - DENY → 跳过执行，把 reason 告诉 LLM
    - REQUIRE_CONFIRM → 挂起，等用户确认
    """

    verdict: SafetyVerdict
    reason: str
    toolName: str
    riskLevel: str
