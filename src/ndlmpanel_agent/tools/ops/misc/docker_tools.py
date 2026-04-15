import json
import re

from ndlmpanel_agent.exceptions import (
    ServiceUnavailableException,
    ToolExecutionException,
)
from ndlmpanel_agent.models.ops.misc.docker_models import DockerContainer, DockerInstallInfo
from ndlmpanel_agent.tools.ops._command_runner import runCommand


def checkDockerInstalled() -> DockerInstallInfo:
    try:
        result = runCommand(["docker", "--version"])
        versionStr = result.stdout.strip().split(",")[0].replace("Docker version ", "")
        return DockerInstallInfo(isInstalled=True, version=versionStr)
    except ToolExecutionException:
        return DockerInstallInfo(isInstalled=False)


def _parseMemoryValue(valueStr: str) -> float:
    """解析 '100MiB' / '1.5GiB' / '512KiB' → MB"""
    valueStr = valueStr.strip()
    multipliers = {
        "GiB": 1024,
        "MiB": 1,
        "KiB": 1 / 1024,
        "GB": 1000,
        "MB": 1,
        "KB": 0.001,
    }
    for suffix, factor in multipliers.items():
        if suffix in valueStr:
            try:
                return float(valueStr.replace(suffix, "").strip()) * factor
            except ValueError:
                return 0.0
    return 0.0


def getDockerContainers(
    includeStoppedContainers: bool = False,
) -> list[DockerContainer]:
    if not checkDockerInstalled().isInstalled:
        raise ServiceUnavailableException("Docker 未安装")

    cmd = ["docker", "ps", "--format", "{{json .}}", "--no-trunc"]
    if includeStoppedContainers:
        cmd.insert(2, "-a")

    result = runCommand(cmd)

    containers: list[DockerContainer] = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        container = DockerContainer(
            containerId=data.get("ID", ""),
            imageName=data.get("Image", ""),
            status=data.get("Status", ""),
            ports=data.get("Ports", ""),
        )

        # 对运行中的容器尝试获取资源占用
        if "Up" in container.status:
            try:
                statsResult = runCommand(
                    [
                        "docker",
                        "stats",
                        "--no-stream",
                        "--format",
                        "{{.CPUPerc}},{{.MemUsage}}",
                        container.containerId,
                    ],
                    timeout=10,
                )
                parts = statsResult.stdout.strip().split(",")
                if len(parts) >= 2:
                    container.cpuPercent = float(parts[0].strip().rstrip("%"))
                    memParts = parts[1].strip().split("/")
                    container.memoryUsageMB = _parseMemoryValue(memParts[0])
                    if len(memParts) > 1:
                        container.memoryLimitMB = _parseMemoryValue(memParts[1])
            except (ToolExecutionException, ValueError, IndexError):
                pass

        containers.append(container)

    return containers
