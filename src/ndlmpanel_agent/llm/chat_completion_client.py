"""
LLM Chat Completion 客户端

封装 openai SDK，提供统一的大模型调用接口。
"""

import json
from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionMessage,
    ChatCompletionToolParam,
)

from ndlmpanel_agent.config import LLMConfiguration


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

    async def send_messages(
        self,
        messages: list[dict],
        tools: list[ChatCompletionToolParam] | None = None,
    ) -> ChatCompletionMessage:
        """
        发送对话消息给 LLM，返回 AI 的回复

        Args:
            messages: OpenAI 格式的消息列表
                      [{"role": "user", "content": "..."}]
            tools:    可用工具的定义列表，可选

        Returns:
            ChatCompletionMessage，包含 content 和/或 tool_calls
        """

        # 构建请求参数
        request_kwargs = {
            "model": self._config.model_name,
            "messages": messages,
            "max_tokens": self._config.max_tokens,
            "temperature": self._config.temperature,
        }

        # 只有提供了工具定义时才传 tools 参数
        # （有些模型在 tools=[] 空列表时会报错）
        if tools:
            request_kwargs["tools"] = tools
            request_kwargs["tool_choice"] = "auto"  # 让 LLM 自己决定是否调用

        response = await self._client.chat.completions.create(**request_kwargs)

        return response.choices[0].message