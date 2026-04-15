from ndlmpanel_agent.models.ops.misc.log_models import LogQueryResult
from ndlmpanel_agent.tools.ops._command_runner import runCommand

# 预定义的日志类型 → journalctl 参数映射
_LOG_TYPE_ARGS: dict[str, list[str]] = {
    "syslog": [],
    "auth": ["--facility=auth"],
    "kern": ["-k"],
    "dmesg": ["-k"],
}


def querySystemLogs(
    logType: str = "syslog",
    keyword: str | None = None,
    since: str | None = None,
    until: str | None = None,
    lineLimit: int = 100,
) -> LogQueryResult:
    """
    查询系统日志

    Args:
        logType:    预定义类型 (syslog/auth/kern/dmesg) 或服务名 (nginx/docker/sshd)
        keyword:    过滤关键词
        since:      起始时间，journalctl 格式如 "2024-01-01" 或 "1 hour ago"
        until:      结束时间
        lineLimit:  最大返回行数
    """
    cmd = ["journalctl", "--no-pager", "-n", str(lineLimit)]

    if logType in _LOG_TYPE_ARGS:
        cmd.extend(_LOG_TYPE_ARGS[logType])
    else:
        cmd.extend(["-u", logType])

    if since:
        cmd.extend(["--since", since])
    if until:
        cmd.extend(["--until", until])
    if keyword:
        cmd.extend(["--grep", keyword])

    result = runCommand(cmd, timeout=15, checkReturnCode=False)
    lines = [line for line in result.stdout.strip().splitlines() if line]

    return LogQueryResult(
        lines=lines,
        totalLines=len(lines),
        logSource=f"journalctl({logType})",
    )
