"""
安全护栏（SafetyGuard）

职责：
1. 根据工具风险等级决定是否放行
2. 检测高危参数模式（如 rm -rf /、chmod 777）
3. 预留 Prompt Injection 检测接口

设计原则：
- 规则引擎优先，LLM 二次判定作为可选增强（Phase 2）
- 宁可误拦不可漏放（保守策略）
- 所有判定结果都返回 SafetyCheckResult，由 Orchestrator 统一处理
"""

import json
import re

from ndlmpanel_agent.config import SafetyConfiguration
from ndlmpanel_agent.models.agent.safety_models import (
    SafetyCheckResult,
    SafetyVerdict,
)
from ndlmpanel_agent.models.agent.tool_models import ToolDefinition, ToolRiskLevel


# ──────────────────────────────────────────────────────────────────────────────
# 高危参数模式（正则）
# 匹配到这些模式时，即使工具本身是 WRITE 级别，也升级为 REQUIRE_CONFIRM
# ──────────────────────────────────────────────────────────────────────────────

_DANGEROUS_PATTERNS: list[tuple[re.Pattern, str]] = [
    # 危险路径
    (re.compile(r"(^|[/\\])\.\.\s*$"), "路径包含 .. 可能导致目录穿越"),
    (re.compile(r"^/$"), "操作根目录 / 极其危险"),
    (re.compile(r"^/(etc|boot|usr|lib|sbin|bin|proc|sys)\b"), "操作系统关键目录"),
    (re.compile(r"^/home$"), "操作 /home 根目录"),
    # 危险权限
    (re.compile(r"\b777\b"), "chmod 777 权限过于宽松"),
    (re.compile(r"\b000\b"), "chmod 000 会导致文件不可访问"),
    # 危险信号
    (re.compile(r"\b(SIGKILL|9)\b"), "SIGKILL 无法被进程捕获，可能导致数据丢失"),
]


class SafetyGuard:
    """
    安全护栏。

    在 AgentOrchestrator 中，每次 LLM 返回 tool_calls 时，
    逐个调用 check_tool_call() 进行校验。
    """

    def __init__(self, config: SafetyConfiguration | None = None) -> None:
        self._config = config or SafetyConfiguration()

    def checkToolCall(
        self,
        toolDef: ToolDefinition,
        argumentsJson: str,
    ) -> SafetyCheckResult:
        """
        校验单次工具调用是否安全。

        Args:
            toolDef:       工具元信息（含风险等级）
            argumentsJson: LLM 传来的参数 JSON 字符串
        """
        risk = toolDef.risk_level

        # ── Layer 1: READ_ONLY 直接放行 ──────────────────────────────────
        if risk == ToolRiskLevel.READ_ONLY:
            return SafetyCheckResult(
                verdict=SafetyVerdict.ALLOW,
                reason="只读操作，自动放行",
                toolName=toolDef.name,
                riskLevel=risk.value,
            )

        # ── 解析参数，用于后续模式匹配 ───────────────────────────────────
        try:
            args = json.loads(argumentsJson) if argumentsJson.strip() else {}
        except json.JSONDecodeError:
            args = {}

        # ── Layer 2: 检查高危参数模式 ────────────────────────────────────
        if self._config.enable_command_filter:
            patternHit = self._checkDangerousPatterns(args)
            if patternHit:
                return SafetyCheckResult(
                    verdict=SafetyVerdict.REQUIRE_CONFIRM,
                    reason=f"参数触发安全规则: {patternHit}",
                    toolName=toolDef.name,
                    riskLevel=risk.value,
                )

        # ── Layer 3: DANGEROUS 级别需要人工确认 ──────────────────────────
        if risk == ToolRiskLevel.DANGEROUS:
            if self._config.require_human_confirm_for_high_risk:
                return SafetyCheckResult(
                    verdict=SafetyVerdict.REQUIRE_CONFIRM,
                    reason=f"高危操作 [{toolDef.name}] 需要人工确认",
                    toolName=toolDef.name,
                    riskLevel=risk.value,
                )

        # ── WRITE 级别：放行 ─────────────────────────────────────────────
        return SafetyCheckResult(
            verdict=SafetyVerdict.ALLOW,
            reason="写操作，校验通过",
            toolName=toolDef.name,
            riskLevel=risk.value,
        )

    def checkPromptInjection(self, userInput: str) -> bool:
        """
        检测用户输入是否包含 Prompt Injection 攻击。

        Phase 1: 基于关键词的简单检测
        Phase 2: 可接入 LLM 二次判定

        Returns:
            True = 检测到注入风险
        """
        if not self._config.enable_prompt_injection_detection:
            return False

        injection_patterns = [
            r"ignore\s+(all\s+)?previous\s+instructions",
            r"ignore\s+(all\s+)?above",
            r"disregard\s+(all\s+)?previous",
            r"you\s+are\s+now\s+a",
            r"new\s+instructions?\s*:",
            r"system\s*:\s*you\s+are",
            r"忽略(之前|上面|以上)(的|所有)?(指令|规则|提示)",
            r"你现在是一个",
            r"新的指令\s*[：:]",
        ]

        lowerInput = userInput.lower()
        for pattern in injection_patterns:
            if re.search(pattern, lowerInput, re.IGNORECASE):
                return True

        return False

    def _checkDangerousPatterns(self, args: dict) -> str | None:
        """扫描参数值，匹配高危模式。未匹配返回 None。"""
        values_to_check: list[str] = []
        for v in args.values():
            if isinstance(v, str):
                values_to_check.append(v)
            elif isinstance(v, (int, float)):
                values_to_check.append(str(v))

        for value in values_to_check:
            for pattern, reason in _DANGEROUS_PATTERNS:
                if pattern.search(value):
                    return reason

        return None
