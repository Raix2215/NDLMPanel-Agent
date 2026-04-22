"""
LLM Chat Completion 客户端

封装 openai SDK，提供统一的大模型调用接口。
"""

from openai import AsyncOpenAI, APIConnectionError, APIStatusError, RateLimitError

from ndlmpanel_agent.config import LLMConfiguration
from ndlmpanel_agent.models.agent.chat_models import LLMCompletionResult, ToolCallRequest


class LLMClientError(Exception):
    """LLM 调用失败时抛出，携带人类可读的原因"""
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class ChatCompletionClient:
    """
    LLM 调用客户端

    职责：
    1. 管理与大模型 API 的连接
    2. 发送 messages + tools，接收响应
    3. 屏蔽不同模型提供商的差异
    """

    def __init__(self, config: LLMConfiguration):
        self._config = config
        self._client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    async def sendMessages(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMCompletionResult:
        """
        发送对话消息给 LLM，返回 AI 的回复

        Args:
            messages: OpenAI 格式的消息列表
                      [{"role": "user", "content": "..."}]
            tools:    可用工具的定义列表，可选

        Returns:
            LLMCompletionResult，包含 content 和/或 tool_calls
        """
        request_kwargs: dict = {
            "model": self._config.model_name,
            "messages": messages,
            "max_tokens": self._config.max_tokens,
            "temperature": self._config.temperature,
        }

        # 只有提供了工具定义时才传 tools 参数
        # （有些模型在 tools=[] 空列表时会报错）
        if tools:
            request_kwargs["tools"] = tools
            request_kwargs["tool_choice"] = "auto"

        try:
            response = await self._client.chat.completions.create(**request_kwargs)
        except RateLimitError as e:
            raise LLMClientError(f"API 请求频率超限，请稍后重试: {e}", retryable=True) from e
        except APIConnectionError as e:
            raise LLMClientError(f"无法连接到 LLM 服务，请检查网络或 base_url 配置: {e}", retryable=True) from e
        except APIStatusError as e:
            if e.status_code == 401:
                raise LLMClientError("API Key 无效或已过期，请检查配置", retryable=False) from e
            raise LLMClientError(f"LLM API 返回错误 (HTTP {e.status_code}): {e.message}", retryable=False) from e

        return LLMCompletionResult(
            content=response.choices[0].message.content,
            toolCalls=[
                ToolCallRequest(
                    id=call.id,
                    functionName=call.function.name,
                    arguments=call.function.arguments,
                )
                for call in (response.choices[0].message.tool_calls or [])
            ]
            or None,
            finishReason=response.choices[0].finish_reason,
            refusal=response.choices[0].message.refusal,
            totalTokensUsed=response.usage.total_tokens if response.usage else None,
            model=response.model,
            reasoningContent=getattr(response.choices[0].message, "reasoning_content", None),
        )
