from pydantic import BaseModel
from enum import Enum


class ToolRiskLevel(str, Enum):
    """工具风险等级，三层划分"""

    READ_ONLY = "read_only"  # Layer 1: 只读，自动执行
    WRITE = "write"  # Layer 2: 写操作，需校验
    DANGEROUS = "dangerous"  # Layer 3: 高危，需人工确认


class ToolDefinition(BaseModel):
    """工具的元信息，注册时用"""

    name: str
    description: str
    risk_level: ToolRiskLevel
    parameters_schema: dict  # JSON Schema，给 LLM 看的


class ToolExecutionResult(BaseModel):
    """工具执行的结果"""

    tool_name: str
    success: bool
    output: str
    error_message: str | None = None
