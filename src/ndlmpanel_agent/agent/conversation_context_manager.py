"""
对话上下文管理器（ConversationContextManager）

职责：
1. 管理所有 session 的生命周期（创建、获取、删除、过期清理）
2. 在树形结构上追加消息（正常对话流）
3. 将活跃路径导出为 OpenAI API 格式的 list[dict]
4. 预留分支操作接口（重新生成、编辑历史、切换分支）

设计原则：
- sessionId 由后端组合生成（如 userId:conversationId），本模块不感知"用户"概念
- 所有写操作在 session.lock 保护下执行（由 Orchestrator 负责加锁）
- 树的遍历通过 _traceActivePath 实现：从 activeLeafId 回溯到 root
"""

from ndlmpanel_agent.config import ContextConfiguration
from ndlmpanel_agent.models.agent.conversation_models import (
    ChatMessagePayload,
    ConversationNode,
    ConversationNodeMeta,
    ConversationSession,
    MessageRole,
    ToolCallData,
)


class ConversationContextManager:
    """
    全局对话上下文管理器。

    在 AgentOrchestrator 初始化时创建，整个应用生命周期内复用同一实例。
    按 sessionId 隔离不同会话的对话树。
    """

    def __init__(self, config: ContextConfiguration | None = None) -> None:
        self._config = config or ContextConfiguration()
        self._sessions: dict[str, ConversationSession] = {}

    # ══════════════════════════════════════════════════════════════════════════
    # Session 生命周期
    # ══════════════════════════════════════════════════════════════════════════

    def getOrCreate(
        self,
        sessionId: str,
        systemPrompt: str | None = None,
    ) -> ConversationSession:
        """
        获取已有 session 或创建新的。

        Args:
            sessionId:     会话唯一标识（由后端组合生成）
            systemPrompt:  自定义 system prompt，不传则用配置中的默认值
        """
        if sessionId not in self._sessions:
            prompt = systemPrompt or self._config.default_system_prompt
            self._sessions[sessionId] = ConversationSession(sessionId, prompt)
        session = self._sessions[sessionId]
        session.touch()
        return session

    def get(self, sessionId: str) -> ConversationSession | None:
        """获取已有 session，不存在返回 None"""
        return self._sessions.get(sessionId)

    def delete(self, sessionId: str) -> None:
        """删除 session（用户退出或手动清理时调用）"""
        self._sessions.pop(sessionId, None)

    def listSessions(self) -> list[str]:
        """返回所有活跃的 sessionId 列表"""
        return list(self._sessions.keys())

    def cleanupExpired(self) -> int:
        """
        清理过期 session，返回清理数量。
        可由后端定时任务调用。
        """
        ttl = self._config.session_ttl_seconds
        expired = [
            sid
            for sid, session in self._sessions.items()
            if session.is_expired(ttl)
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)

    # ══════════════════════════════════════════════════════════════════════════
    # Phase 1：基础消息操作（支撑 ReAct Loop）
    # ══════════════════════════════════════════════════════════════════════════

    def appendUserMessage(
        self,
        session: ConversationSession,
        content: str,
    ) -> ConversationNode:
        """
        追加用户消息到当前活跃路径末端。

        树的变化：
          ... → activeLeaf → [新 user 节点]
                               ↑ 成为新的 activeLeaf
        """
        return self._appendNode(
            session,
            ChatMessagePayload(role=MessageRole.USER, content=content),
        )

    def appendAssistantMessage(
        self,
        session: ConversationSession,
        content: str | None,
        toolCalls: list[ToolCallData] | None = None,
        meta: ConversationNodeMeta | None = None,
    ) -> ConversationNode:
        """
        追加 assistant 消息。

        两种情况：
        1. LLM 给出最终文字回复（content 有值，toolCalls 为空）
        2. LLM 要调工具（content 可能为空，toolCalls 有值）

        Args:
            content:    LLM 回复的文字内容
            toolCalls:  LLM 发起的工具调用列表
            meta:       元信息（模型名、token 数、reasoning_content 等）
        """
        return self._appendNode(
            session,
            ChatMessagePayload(
                role=MessageRole.ASSISTANT,
                content=content,
                toolCalls=toolCalls,
            ),
            meta=meta,
        )

    def appendToolResult(
        self,
        session: ConversationSession,
        toolCallId: str,
        toolName: str,
        content: str,
    ) -> ConversationNode:
        """
        追加工具执行结果。

        OpenAI API 要求：
        - role 必须是 "tool"
        - tool_call_id 必须与 assistant 消息中的 tool_calls[i].id 一一对应
        - 如果 assistant 消息有 N 个 tool_calls，后面必须紧跟 N 条 tool 消息
        """
        return self._appendNode(
            session,
            ChatMessagePayload(
                role=MessageRole.TOOL,
                content=content,
                toolCallId=toolCallId,
                name=toolName,
            ),
        )

    # ══════════════════════════════════════════════════════════════════════════
    # 导出给 LLM
    # ══════════════════════════════════════════════════════════════════════════

    def getActivePath(
        self,
        session: ConversationSession,
    ) -> list[ConversationNode]:
        """
        获取当前活跃路径：从 root 到 activeLeaf 的有序节点列表。

        实现方式：从 activeLeafId 往上回溯到 root，收集路径，然后反转。
        时间复杂度 O(d)，d 为树的深度（即对话轮次数）。
        """
        path: list[ConversationNode] = []
        currentId: str | None = session.activeLeafId

        while currentId is not None:
            node = session.nodes.get(currentId)
            if node is None:
                break
            path.append(node)
            currentId = node.parentId

        path.reverse()
        return path

    def toOpenAIMessages(
        self,
        session: ConversationSession,
    ) -> list[dict]:
        """
        将活跃路径导出为 OpenAI API 格式的 list[dict]。
        直接传给 ChatCompletionClient.sendMessages()。
        """
        path = self.getActivePath(session)
        return [node.payload.to_openai_dict() for node in path]

    # ══════════════════════════════════════════════════════════════════════════
    # 上下文管理
    # ══════════════════════════════════════════════════════════════════════════

    def clear(
        self,
        session: ConversationSession,
        keepSystem: bool = True,
    ) -> None:
        """
        清空对话历史。

        Args:
            keepSystem: True 保留 system prompt 节点，False 全部清空
        """
        if keepSystem:
            root = session.nodes.get(session.rootNodeId)
            if root:
                root.childrenIds.clear()
                session.nodes = {session.rootNodeId: root}
                session.activeLeafId = session.rootNodeId
                return

        session.nodes.clear()
        session.activeLeafId = ""
        session.rootNodeId = ""

    def getNode(
        self,
        session: ConversationSession,
        nodeId: str,
    ) -> ConversationNode | None:
        """按 ID 获取节点，供外部模块使用（如审计日志）"""
        return session.nodes.get(nodeId)

    def getMessageCount(self, session: ConversationSession) -> int:
        """返回当前活跃路径上的消息数量"""
        return len(self.getActivePath(session))

    # ══════════════════════════════════════════════════════════════════════════
    # Phase 2：高级编排（预留接口，暂不实现）
    # ══════════════════════════════════════════════════════════════════════════

    def regenerateAt(
        self,
        session: ConversationSession,
        nodeId: str,
    ) -> ConversationNode:
        """在 nodeId 的父节点下创建新的空 assistant 子节点，用于重新生成回复。"""
        raise NotImplementedError("Phase 2: regenerateAt")

    def editNode(
        self,
        session: ConversationSession,
        nodeId: str,
        newContent: str,
    ) -> ConversationNode:
        """编辑指定节点的消息内容，从该点创建新分支。"""
        raise NotImplementedError("Phase 2: editNode")

    def switchToBranch(
        self,
        session: ConversationSession,
        nodeId: str,
    ) -> None:
        """切换 activeLeafId 到指定节点（及其最深活跃后代）。"""
        raise NotImplementedError("Phase 2: switchToBranch")

    def getSiblingBranches(
        self,
        session: ConversationSession,
        nodeId: str,
    ) -> list[ConversationNode]:
        """获取指定节点的所有兄弟节点。"""
        raise NotImplementedError("Phase 2: getSiblingBranches")

    def deleteBranch(
        self,
        session: ConversationSession,
        nodeId: str,
    ) -> None:
        """删除指定节点及其所有后代。"""
        raise NotImplementedError("Phase 2: deleteBranch")

    # ══════════════════════════════════════════════════════════════════════════
    # 内部方法
    # ══════════════════════════════════════════════════════════════════════════

    def _appendNode(
        self,
        session: ConversationSession,
        payload: ChatMessagePayload,
        meta: ConversationNodeMeta | None = None,
    ) -> ConversationNode:
        """
        在当前 activeLeaf 下追加新子节点，并更新 activeLeafId。
        这是所有 append* 方法的底层实现。
        """
        parentId = session.activeLeafId
        node = ConversationNode(
            parentId=parentId,
            payload=payload,
            meta=meta or ConversationNodeMeta(),
        )

        session.nodes[node.nodeId] = node

        parent = session.nodes.get(parentId)
        if parent:
            parent.childrenIds.append(node.nodeId)

        session.activeLeafId = node.nodeId
        session.touch()

        return node
