"""
防火墙管理工具
自动检测后端类型（firewalld / ufw），适配不同发行版
麒麟/RHEL 使用 firewalld，Ubuntu/Debian 使用 ufw
"""

import re

from ndlmpanel_agent.exceptions import (
    ServiceUnavailableException,
    ToolExecutionException,
)
from ndlmpanel_agent.models.ops.firewall.firewall_models import (
    FirewallBackendType,
    FirewallPortOperationResult,
    FirewallPortRule,
    FirewallStatus,
)
from ndlmpanel_agent.tools.ops._command_runner import runCommand


# ────────────────── 内部辅助 ──────────────────


def _detectBackend() -> FirewallBackendType:
    """检测当前系统使用的防火墙后端"""
    for cmd, backend in [
        (["firewall-cmd", "--version"], FirewallBackendType.FIREWALLD),
        (["ufw", "version"], FirewallBackendType.UFW),
    ]:
        try:
            runCommand(cmd, checkReturnCode=False)
            return backend
        except ToolExecutionException:
            continue
    return FirewallBackendType.UNKNOWN


def _requireBackend() -> FirewallBackendType:
    backend = _detectBackend()
    if backend == FirewallBackendType.UNKNOWN:
        raise ServiceUnavailableException("未检测到受支持的防火墙服务(firewalld/ufw)")
    return backend


# ────────────────── 公开接口 ──────────────────


def getFirewallStatus() -> FirewallStatus:
    backend = _requireBackend()

    if backend == FirewallBackendType.FIREWALLD:
        stateResult = runCommand(["firewall-cmd", "--state"], checkReturnCode=False)
        isActive = "running" in stateResult.stdout.strip().lower()

        defaultPolicy = "unknown"
        if isActive:
            zoneResult = runCommand(["firewall-cmd", "--get-default-zone"])
            defaultPolicy = zoneResult.stdout.strip()

        return FirewallStatus(
            isActive=isActive,
            defaultPolicy=defaultPolicy,
            backendType=backend,
        )

    # ufw
    result = runCommand(["ufw", "status", "verbose"], checkReturnCode=False)
    output = result.stdout
    isActive = "Status: active" in output

    defaultPolicy = "unknown"
    match = re.search(r"Default:\s*(.+)", output)
    if match:
        defaultPolicy = match.group(1).strip()

    return FirewallStatus(
        isActive=isActive,
        defaultPolicy=defaultPolicy,
        backendType=backend,
    )


def listFirewallPorts() -> list[FirewallPortRule]:
    backend = _requireBackend()
    ports: list[FirewallPortRule] = []

    if backend == FirewallBackendType.FIREWALLD:
        # 普通端口
        result = runCommand(["firewall-cmd", "--list-ports"])
        for entry in result.stdout.strip().split():
            if "/" in entry:
                portStr, protocol = entry.split("/", 1)
                ports.append(
                    FirewallPortRule(
                        port=int(portStr),
                        protocol=protocol,
                        policy="accept",
                        sourceIp=None,
                    )
                )

        # 富规则（带来源 IP 的高级规则）
        richResult = runCommand(
            ["firewall-cmd", "--list-rich-rules"], checkReturnCode=False
        )
        for line in richResult.stdout.strip().splitlines():
            portMatch = re.search(r'port port="(\d+)" protocol="(\w+)"', line)
            sourceMatch = re.search(r'source address="([^"]+)"', line)
            actionMatch = re.search(r"(accept|reject|drop)", line)
            if portMatch:
                ports.append(
                    FirewallPortRule(
                        port=int(portMatch.group(1)),
                        protocol=portMatch.group(2),
                        policy=actionMatch.group(1) if actionMatch else "accept",
                        sourceIp=sourceMatch.group(1) if sourceMatch else None,
                    )
                )
        return ports

    # ufw
    result = runCommand(["ufw", "status", "numbered"])
    for line in result.stdout.strip().splitlines():
        match = re.match(r"\[\s*\d+\]\s+(\d+)/(tcp|udp)\s+(\w+)\s+IN\s+(.*)", line)
        if match:
            source = match.group(4).strip()
            ports.append(
                FirewallPortRule(
                    port=int(match.group(1)),
                    protocol=match.group(2),
                    policy=match.group(3).lower(),
                    sourceIp=source if source != "Anywhere" else None,
                )
            )
    return ports


def addFirewallPort(
    port: int,
    protocol: str = "tcp",
    remark: str | None = None,
) -> FirewallPortOperationResult:
    backend = _requireBackend()

    if backend == FirewallBackendType.FIREWALLD:
        runCommand(
            ["firewall-cmd", f"--add-port={port}/{protocol}", "--permanent"],
            useSudo=True,
        )
        runCommand(["firewall-cmd", "--reload"], useSudo=True)
    else:
        runCommand(["ufw", "allow", f"{port}/{protocol}"], useSudo=True)

    return FirewallPortOperationResult(
        success=True,
        port=port,
        protocol=protocol,
        message=f"已放行 {port}/{protocol}",
    )


def removeFirewallPort(
    port: int,
    protocol: str = "tcp",
) -> FirewallPortOperationResult:
    backend = _requireBackend()

    if backend == FirewallBackendType.FIREWALLD:
        runCommand(
            ["firewall-cmd", f"--remove-port={port}/{protocol}", "--permanent"],
            useSudo=True,
        )
        runCommand(["firewall-cmd", "--reload"], useSudo=True)
    else:
        runCommand(["ufw", "delete", "allow", f"{port}/{protocol}"], useSudo=True)

    return FirewallPortOperationResult(
        success=True,
        port=port,
        protocol=protocol,
        message=f"已移除 {port}/{protocol}",
    )
