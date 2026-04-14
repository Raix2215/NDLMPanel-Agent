from ndlmpanel_agent.config import AgentConfiguration
from ndlmpanel_agent.models.chat_models import AgentResponse


class AgentOrchestrator:
    """
    Agent 核心编排器

    职责：接收用户消息 → 调度 LLM → 编排工具调用 → 返回结果
    这是后端唯一需要交互的入口类
    """

    def __init__(self, config: AgentConfiguration):
        self._config = config
        # TODO: 初始化各子模块
        # self._llm_client = ChatCompletionClient(config.llm)
        # self._tool_registry = ToolRegistry()
        # self._safety_guard = SafetyGuard(config.safety)
        # self._trace_logger = TraceLogger(config.audit_log_directory)
        # self._context_manager = ConversationContextManager()

    async def handle_user_message(
        self,
        session_id: str,
        user_message: str,
    ) -> AgentResponse:
        """
        处理一条用户消息，返回 Agent 响应

        这是后端调用的主入口
        """
        # TODO: 实现 ReAct 循环
        raise NotImplementedError

    async def confirm_pending_action(
        self,
        session_id: str,
        confirmed: bool,
    ) -> AgentResponse:
        """
        用户确认/拒绝高危操作后调用
        """
        raise NotImplementedError
