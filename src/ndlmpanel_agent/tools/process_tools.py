import signal

import psutil

from ndlmpanel_agent.exceptions import (
    PermissionDeniedException,
    ResourceNotFoundException,
)
from ndlmpanel_agent.models.process_models import (
    ProcessInfo,
    ProcessKillResult,
    ProcessSortBy,
)


def listProcesses(
    sortBy: ProcessSortBy = ProcessSortBy.CPU,
    keyword: str | None = None,
) -> list[ProcessInfo]:
    processes: list[ProcessInfo] = []

    for proc in psutil.process_iter(
        [
            "pid",
            "name",
            "username",
            "cpu_percent",
            "memory_percent",
            "status",
            "cmdline",
        ]
    ):
        try:
            info = proc.info
            command = (
                " ".join(info["cmdline"]) if info["cmdline"] else (info["name"] or "")
            )

            # 关键词过滤
            if keyword:
                haystack = f"{info['name'] or ''} {command}".lower()
                if keyword.lower() not in haystack:
                    continue

            processes.append(
                ProcessInfo(
                    pid=info["pid"],
                    processName=info["name"] or "",
                    userName=info["username"] or "",
                    cpuPercent=info["cpu_percent"] or 0.0,
                    memoryPercent=round(info["memory_percent"] or 0.0, 2),
                    status=info["status"] or "",
                    command=command,
                )
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    sortKeyMap = {
        ProcessSortBy.CPU: lambda p: p.cpuPercent,
        ProcessSortBy.MEMORY: lambda p: p.memoryPercent,
        ProcessSortBy.PID: lambda p: p.pid,
    }
    descending = sortBy != ProcessSortBy.PID
    processes.sort(key=sortKeyMap[sortBy], reverse=descending)

    return processes


def killProcess(pid: int, signalNumber: int = signal.SIGTERM) -> ProcessKillResult:
    try:
        proc = psutil.Process(pid)
        proc.send_signal(signalNumber)
        return ProcessKillResult(success=True, pid=pid)
    except psutil.NoSuchProcess:
        raise ResourceNotFoundException(f"进程不存在: PID={pid}")
    except psutil.AccessDenied:
        raise PermissionDeniedException(f"无权终止进程: PID={pid}")
