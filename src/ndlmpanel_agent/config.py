from pydantic import BaseModel


class LLMConfiguration(BaseModel):
    """大模型连接配置"""

    api_key: str
    base_url: str
    model_name: str = "glm-4.7"
    max_tokens: int = 65536
    temperature: float = 0.7


class SafetyConfiguration(BaseModel):
    """安全护栏配置"""

    enable_command_filter: bool = True
    enable_prompt_injection_detection: bool = True
    require_human_confirm_for_high_risk: bool = True


class AgentConfiguration(BaseModel):
    """Agent 总配置，后端传入这个即可初始化整个模块"""

    llm: LLMConfiguration
    safety: SafetyConfiguration = SafetyConfiguration()
    max_tool_call_rounds: int = 10  # 单次对话最多调几轮工具
    audit_log_directory: str = "./logs"
