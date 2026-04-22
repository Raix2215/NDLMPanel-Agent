"""
Agent 核心编排器（AgentOrchestrator）

职责：
1. 接收用户自然语言消息
2. 调度 LLM 进行推理
3. 编排工具调用（ReAct Loop）
4. 协调安全校验
5. 返回最终结果

这是后端唯一需要交互的入口类。
后端只需要调用 handleUserMessage() 和 confirmPendingAction()。
"""

from ndlmpanel_agent.agent.conversation_context_manager import (
    ConversationContextManager,
)
from ndlmpanel_agent.config import AgentConfiguration
from ndlmpanel_agent.llm.chat_completion_client import ChatCompletionClient, LLMClientError
from ndlmpanel_agent.models.agent.chat_models import (
    AgentResponse,
    LLMCompletionResult,
)
from ndlmpanel_agent.models.agent.conversation_models import (
    ConversationNodeMeta,
    ToolCallData,
)
from ndlmpanel_agent.models.agent.safety_models import SafetyVerdict
from ndlmpanel_agent.safety.safety_guard import SafetyGuard
from ndlmpanel_agent.tools.tool_registry import ToolRegistry


class AgentOrchestrator:
    """
    Agent 核心编排器。

    生命周期：后端启动时创建一个实例，整个应用复用。
    线程安全：每个 session 有自己的 asyncio.Lock，不同 session 可并发。
    """

    def __init__(
        self,
        config: AgentConfiguration,
        toolFunctions: list | None = None,
    ) -> None:
        self._config = config

        self._llmClient = ChatCompletionClient(config.llm)
        self._contextMgr = ConversationContextManager(config.context)
        self._safetyGuard = SafetyGuard(config.safety)

        # 工具注册：如果外部没传，从 tools 包的 ALL_TOOL_FUNCTIONS 加载
        if toolFunctions is None:
            import ndlmpanel_agent.tools as tools_pkg
            from ndlmpanel_agent.tools import __all__ as tool_names

            toolFunctions = [getattr(tools_pkg, name) for name in tool_names]
        self._toolRegistry = ToolRegistry(toolFunctions)

    # ══════════════════════════════════════════════════════════════════════════
    # 对外接口（后端调用）
    # ══════════════════════════════════════════════════════════════════════════

    async def handleUserMessage(
        self,
        sessionId: str,
        userMessage: str,
    ) -> AgentResponse:
        """
        处理一条用户消息，返回 Agent 响应。

        这是后端调用的主入口。整个 ReAct Loop 在这里完成。

        Args:
            sessionId:   会话 ID（由后端组合生成，如 userId:convId）
            userMessage: 用户的自然语言输入
        """
        session = self._contextMgr.getOrCreate(sessionId)

        async with session.lock:
            # ── Step 1: Prompt Injection 检测 ────────────────────────────
            if self._safetyGuard.checkPromptInjection(userMessage):
                return AgentResponse(
                    reply="检测到潜在的提示词注入攻击，已拒绝处理该消息。",
                    riskLevel="high",
                )

            # ── Step 2: 追加用户消息到上下文 ─────────────────────────────
            self._contextMgr.appendUserMessage(session, userMessage)

            # ── Step 3: ReAct Loop ───────────────────────────────────────
            return await self._reactLoop(session)

    async def confirmPendingAction(
        self,
        sessionId: str,
        confirmed: bool,
    ) -> AgentResponse:
        """
        用户确认/拒绝高危操作后调用。

        当 handleUserMessage 返回 requiresHumanConfirm=True 时，
        前端展示确认对话框，用户操作后调用此方法。

        Args:
            sessionId: 会话 ID
            confirmed: True=用户确认执行，False=用户拒绝
        """
        session = self._contextMgr.get(sessionId)
        if session is None:
            return AgentResponse(reply="会话不存在或已过期。")

        async with session.lock:
            pending = session.pendingAction
            if pending is None:
                return AgentResponse(reply="没有待确认的操作。")

            session.pendingAction = None

            if not confirmed:
                self._contextMgr.appendToolResult(
                    session,
                    toolCallId=pending["toolCallId"],
                    toolName=pending["toolName"],
                    content="[用户拒绝执行] 原因：用户认为该操作不安全或不需要",
                )
                return await self._reactLoop(session)

            # 用户确认：执行工具
            execResult = await self._toolRegistry.execute(
                pending["toolName"],
                pending["argumentsJson"],
            )

            output = execResult.output if execResult.success else (
                f"[执行失败] {execResult.error_message}"
            )
            self._contextMgr.appendToolResult(
                session,
                toolCallId=pending["toolCallId"],
                toolName=pending["toolName"],
                content=output,
            )

            return await self._reactLoop(session)

    # ══════════════════════════════════════════════════════════════════════════
    # ReAct Loop 核心
    # ══════════════════════════════════════════════════════════════════════════

    async def _reactLoop(self, session) -> AgentResponse:
        """
        ReAct 循环：反复调用 LLM，直到得到最终文本回复或达到轮次上限。

        每一轮：
        1. 导出当前上下文 → 发给 LLM
        2. LLM 返回纯文本 → 结束
        3. LLM 返回 tool_calls → 安全校验 → 执行 → 追加结果 → 继续
        """
        maxRounds = self._config.max_tool_call_rounds
        toolsSchema = self._toolRegistry.getToolsSchema()
        toolCallsMade: list[str] = []
        highestRisk = "low"

        for _ in range(maxRounds):
            # ── 导出上下文，调用 LLM ─────────────────────────────────────
            messages = self._contextMgr.toOpenAIMessages(session)
            try:
                llmResult: LLMCompletionResult = await self._llmClient.sendMessages(
                    messages=messages,
                    tools=toolsSchema,
                )
            except LLMClientError as e:
                errReply = f"LLM 服务暂时不可用：{e}"
                self._contextMgr.appendAssistantMessage(session, content=errReply)
                return AgentResponse(reply=errReply, toolCallsMade=toolCallsMade, riskLevel=highestRisk)

            # ── 情况 A: LLM 返回纯文本（无 tool_calls）→ 结束 ──────────
            if not llmResult.toolCalls:
                reply = llmResult.content or ""
                self._contextMgr.appendAssistantMessage(
                    session,
                    content=reply,
                    meta=ConversationNodeMeta(
                        model=llmResult.model,
                        tokenCount=llmResult.totalTokensUsed,
                        reasoningContent=llmResult.reasoningContent,
                    ),
                )
                return AgentResponse(
                    reply=reply,
                    toolCallsMade=toolCallsMade,
                    riskLevel=highestRisk,
                )

            # ── 情况 B: LLM 返回 tool_calls → 处理每个调用 ─────────────
            self._contextMgr.appendAssistantMessage(
                session,
                content=llmResult.content,
                toolCalls=[
                    ToolCallData(
                        id=tc.id,
                        functionName=tc.functionName,
                        arguments=tc.arguments,
                    )
                    for tc in llmResult.toolCalls
                ],
                meta=ConversationNodeMeta(
                    model=llmResult.model,
                    tokenCount=llmResult.totalTokensUsed,
                    reasoningContent=llmResult.reasoningContent,
                ),
            )

            for tc in llmResult.toolCalls:
                toolCallsMade.append(tc.functionName)

                # ── 安全校验 ─────────────────────────────────────────────
                toolDef = self._toolRegistry.getDefinition(tc.functionName)
                if toolDef is None:
                    self._contextMgr.appendToolResult(
                        session,
                        toolCallId=tc.id,
                        toolName=tc.functionName,
                        content=f"[错误] 未知工具: {tc.functionName}",
                    )
                    continue

                safetyResult = self._safetyGuard.checkToolCall(toolDef, tc.arguments)

                if safetyResult.riskLevel == "dangerous":
                    highestRisk = "high"
                elif safetyResult.riskLevel == "write" and highestRisk == "low":
                    highestRisk = "medium"

                # ── 根据校验结果分流 ─────────────────────────────────────
                if safetyResult.verdict == SafetyVerdict.DENY:
                    self._contextMgr.appendToolResult(
                        session,
                        toolCallId=tc.id,
                        toolName=tc.functionName,
                        content=f"[安全拦截] {safetyResult.reason}",
                    )
                    continue

                if safetyResult.verdict == SafetyVerdict.REQUIRE_CONFIRM:
                    session.pendingAction = {
                        "toolCallId": tc.id,
                        "toolName": tc.functionName,
                        "argumentsJson": tc.arguments,
                        "safetyReason": safetyResult.reason,
                    }
                    return AgentResponse(
                        reply=(
                            f"需要您确认以下操作：\n"
                            f"工具: {tc.functionName}\n"
                            f"参数: {tc.arguments}\n"
                            f"原因: {safetyResult.reason}"
                        ),
                        toolCallsMade=toolCallsMade,
                        riskLevel="high",
                        requiresHumanConfirm=True,
                        pendingAction=session.pendingAction,
                    )

                # ── ALLOW: 执行工具 ──────────────────────────────────────
                execResult = await self._toolRegistry.execute(
                    tc.functionName, tc.arguments
                )

                output = execResult.output if execResult.success else (
                    f"[执行失败] {execResult.error_message}"
                )
                self._contextMgr.appendToolResult(
                    session,
                    toolCallId=tc.id,
                    toolName=tc.functionName,
                    content=output,
                )

        # ── 超过最大轮次 ─────────────────────────────────────────────────
        fallbackReply = "抱歉，工具调用轮次已达上限，请尝试简化您的请求。"
        self._contextMgr.appendAssistantMessage(session, content=fallbackReply)
        return AgentResponse(
            reply=fallbackReply,
            toolCallsMade=toolCallsMade,
            riskLevel=highestRisk,
        )
