import re
import socket
import time

from ndlmpanel_agent.exceptions import ToolExecutionException
from ndlmpanel_agent.models.network_models import PingResult, PortCheckResult
from ndlmpanel_agent.tools._command_runner import runCommand


def pingHost(host: str, timeout: int = 5) -> PingResult:
    try:
        result = runCommand(
            ["ping", "-c", "4", "-W", str(timeout), host],
            timeout=timeout * 5,
            checkReturnCode=False,
        )
    except ToolExecutionException:
        return PingResult(isReachable=False, packetLossPercent=100.0)

    lossMatch = re.search(r"([\d.]+)% packet loss", result.stdout)
    latencyMatch = re.search(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)/", result.stdout)

    return PingResult(
        isReachable=(result.returncode == 0),
        averageLatencyMs=float(latencyMatch.group(1)) if latencyMatch else None,
        packetLossPercent=float(lossMatch.group(1)) if lossMatch else None,
    )


def checkPortConnectivity(host: str, port: int, timeout: int = 5) -> PortCheckResult:
    startTime = time.time()
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        elapsed = (time.time() - startTime) * 1000
        sock.close()
        return PortCheckResult(isOpen=True, connectionTimeMs=round(elapsed, 2))
    except (socket.timeout, ConnectionRefusedError, OSError):
        return PortCheckResult(isOpen=False)
