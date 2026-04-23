import signal

import psutil

from ndlmpanel_agent.exceptions import (
    PermissionDeniedException,
    ResourceNotFoundException,
    ToolExecutionException,
)
from ndlmpanel_agent.models.ops.process.process_models import (
    BatchKillMode,
    BatchKillResult,
    ProcessAutoCleanResult,
    ProcessDetailInfo,
    ProcessInfo,
    ProcessKillResult,
    ProcessPortInfo,
    ProcessSortBy,
)


def _buildPortMap() -> dict[int, list[ProcessPortInfo]]:
    portMap: dict[int, list[ProcessPortInfo]] = {}
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.status != "LISTEN" or conn.pid is None:
                continue
            if not conn.laddr:
                continue
            protocol = "TCP" if conn.type == 1 else "UDP"
            portInfo = ProcessPortInfo(
                listenAddress=conn.laddr.ip,
                protocol=protocol,
                port=conn.laddr.port,
            )
            portMap.setdefault(conn.pid, []).append(portInfo)
    except psutil.AccessDenied:
        pass
    return portMap


def listProcesses(
    sortBy: ProcessSortBy = ProcessSortBy.CPU,
    keyword: str | None = None,
) -> list[ProcessInfo]:
    portMap = _buildPortMap()
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

            if keyword:
                haystack = f"{info['name'] or ''} {command}".lower()
                if keyword.lower() not in haystack:
                    continue

            pid = info["pid"]
            processes.append(
                ProcessInfo(
                    pid=pid,
                    processName=info["name"] or "",
                    userName=info["username"] or "",
                    cpuPercent=info["cpu_percent"] or 0.0,
                    memoryPercent=round(info["memory_percent"] or 0.0, 2),
                    status=info["status"] or "",
                    command=command,
                    ports=portMap.get(pid),
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


def getProcessDetail(pid: int) -> ProcessDetailInfo:
    try:
        proc = psutil.Process(pid)
        info = proc.as_dict(
            attrs=[
                "pid",
                "name",
                "username",
                "cpu_percent",
                "memory_percent",
                "status",
                "cmdline",
                "ppid",
                "create_time",
                "exe",
                "num_threads",
                "num_fds",
                "cwd",
                "memory_info",
            ]
        )

        command = (
            " ".join(info["cmdline"]) if info["cmdline"] else (info["name"] or "")
        )

        memInfo = info.get("memory_info")
        rss = memInfo.rss if memInfo else None
        vms = memInfo.vms if memInfo else None

        portMap = _buildPortMap()

        return ProcessDetailInfo(
            pid=info["pid"],
            processName=info["name"] or "",
            userName=info["username"] or "",
            cpuPercent=info["cpu_percent"] or 0.0,
            memoryPercent=round(info["memory_percent"] or 0.0, 2),
            status=info["status"] or "",
            command=command,
            ports=portMap.get(pid),
            parentPid=info.get("ppid"),
            startTime=info.get("create_time"),
            exePath=info.get("exe"),
            threadCount=info.get("num_threads"),
            fdCount=info.get("num_fds"),
            workDir=info.get("cwd"),
            rss=rss,
            vms=vms,
        )
    except psutil.NoSuchProcess:
        raise ResourceNotFoundException(f"进程不存在: PID={pid}")
    except psutil.AccessDenied:
        raise PermissionDeniedException(f"无权获取进程详情: PID={pid}")


def autoCleanProcesses(
    cpuThreshold: float,
    memoryThreshold: float,
) -> ProcessAutoCleanResult:
    if cpuThreshold <= 0 or cpuThreshold > 100:
        raise ToolExecutionException(
            innerMessage=f"CPU阈值无效: {cpuThreshold}, 应在(0, 100]范围内"
        )
    if memoryThreshold <= 0 or memoryThreshold > 100:
        raise ToolExecutionException(
            innerMessage=f"内存阈值无效: {memoryThreshold}, 应在(0, 100]范围内"
        )

    killedResults: list[ProcessKillResult] = []
    totalScanned = 0

    for proc in psutil.process_iter(
        ["pid", "name", "cpu_percent", "memory_percent"]
    ):
        try:
            info = proc.info
            pid = info["pid"]
            totalScanned += 1

            cpuPercent = info["cpu_percent"] or 0.0
            memoryPercent = info["memory_percent"] or 0.0

            if cpuPercent > cpuThreshold or memoryPercent > memoryThreshold:
                try:
                    proc.send_signal(signal.SIGTERM)
                    killedResults.append(
                        ProcessKillResult(success=True, pid=pid)
                    )
                except psutil.NoSuchProcess:
                    killedResults.append(
                        ProcessKillResult(
                            success=False,
                            pid=pid,
                            errorMessage="进程已不存在",
                        )
                    )
                except psutil.AccessDenied:
                    killedResults.append(
                        ProcessKillResult(
                            success=False,
                            pid=pid,
                            errorMessage="权限不足，无法终止进程",
                        )
                    )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return ProcessAutoCleanResult(
        killedProcesses=killedResults,
        totalScanned=totalScanned,
        totalKilled=sum(1 for r in killedResults if r.success),
    )


def getZombieOrphanProcesses() -> list[ProcessInfo]:
    portMap = _buildPortMap()
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
            "ppid",
        ]
    ):
        try:
            info = proc.info
            ppid = info.get("ppid", 0)
            status = info["status"] or ""

            isZombie = status == psutil.STATUS_ZOMBIE
            isOrphan = ppid == 1 and status != psutil.STATUS_ZOMBIE

            if not isZombie and not isOrphan:
                continue

            command = (
                " ".join(info["cmdline"])
                if info["cmdline"]
                else (info["name"] or "")
            )

            pid = info["pid"]
            processes.append(
                ProcessInfo(
                    pid=pid,
                    processName=info["name"] or "",
                    userName=info["username"] or "",
                    cpuPercent=info["cpu_percent"] or 0.0,
                    memoryPercent=round(info["memory_percent"] or 0.0, 2),
                    status=status,
                    command=command,
                    ports=portMap.get(pid),
                )
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return processes


def batchKillProcesses(
    pids: list[int],
    mode: BatchKillMode = BatchKillMode.SIGTERM,
) -> BatchKillResult:
    sig = signal.SIGTERM if mode == BatchKillMode.SIGTERM else signal.SIGKILL
    results: list[ProcessKillResult] = []

    for pid in pids:
        try:
            proc = psutil.Process(pid)
            proc.send_signal(sig)
            results.append(ProcessKillResult(success=True, pid=pid))
        except psutil.NoSuchProcess:
            results.append(
                ProcessKillResult(
                    success=False, pid=pid, errorMessage="进程不存在"
                )
            )
        except psutil.AccessDenied:
            results.append(
                ProcessKillResult(
                    success=False, pid=pid, errorMessage="权限不足，无法终止进程"
                )
            )
        except Exception as e:
            results.append(
                ProcessKillResult(
                    success=False, pid=pid, errorMessage=str(e)
                )
            )

    totalSuccess = sum(1 for r in results if r.success)
    return BatchKillResult(
        results=results,
        totalRequested=len(pids),
        totalSuccess=totalSuccess,
        totalFailed=len(pids) - totalSuccess,
    )
