"""
系统状态监控工具
CPU / 内存 / 磁盘 / GPU / 网络
注意: getDiskInfo 和 getNetworkInfo 内部有 ~1s 的采样延迟用于计算速率
"""

import socket
import time

import psutil

from ndlmpanel_agent.exceptions import ToolExecutionException
from ndlmpanel_agent.models.ops.monitor.system_monitor_models import (
    CpuInfo,
    DiskPartitionInfo,
    GpuInfo,
    MemoryInfo,
    NetworkInterfaceInfo,
)
from ndlmpanel_agent.tools.ops._command_runner import runCommand


def getCpuInfo() -> CpuInfo:
    # 从 /proc/cpuinfo 读取型号（比 platform.processor() 更可靠）
    modelName = "Unknown"
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    modelName = line.split(":", 1)[1].strip()
                    break
    except (FileNotFoundError, IndexError):
        pass

    load1, load5, load15 = psutil.getloadavg()

    return CpuInfo(
        modelName=modelName,
        coreCount=psutil.cpu_count(logical=True) or 1,
        usagePercent=psutil.cpu_percent(interval=1),
        load1Min=round(load1, 2),
        load5Min=round(load5, 2),
        load15Min=round(load15, 2),
    )


def getMemoryInfo() -> MemoryInfo:
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    return MemoryInfo(
        totalBytes=mem.total,
        usedBytes=mem.used,
        availableBytes=mem.available,
        usagePercent=mem.percent,
        swapTotalBytes=swap.total,
        swapUsedBytes=swap.used,
        swapUsagePercent=swap.percent,
    )


def getDiskInfo() -> list[DiskPartitionInfo]:
    partitions = psutil.disk_partitions(all=False)

    # 采样 1s 计算 IO 速率
    io1 = psutil.disk_io_counters(perdisk=True)
    time.sleep(1)
    io2 = psutil.disk_io_counters(perdisk=True)

    results: list[DiskPartitionInfo] = []
    for part in partitions:
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except PermissionError:
            continue

        # 将分区设备名映射到磁盘设备名（如 sda1 → sda）
        deviceName = part.device.split("/")[-1]
        diskName = deviceName.rstrip("0123456789p")  # 兼容 nvme0n1p1 格式

        readRate = 0.0
        writeRate = 0.0
        for name in (deviceName, diskName):
            if name in io1 and name in io2:
                readRate = float(io2[name].read_bytes - io1[name].read_bytes)
                writeRate = float(io2[name].write_bytes - io1[name].write_bytes)
                break

        results.append(
            DiskPartitionInfo(
                mountPoint=part.mountpoint,
                fileSystem=part.fstype,
                totalBytes=usage.total,
                usedBytes=usage.used,
                usagePercent=usage.percent,
                readBytesPerSec=readRate,
                writeBytesPerSec=writeRate,
            )
        )

    return results


def getGpuInfo() -> list[GpuInfo]:
    """获取 NVIDIA GPU 信息；无 GPU 或无驱动时返回空列表"""
    try:
        result = runCommand(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ]
        )
    except ToolExecutionException:
        return []

    gpus: list[GpuInfo] = []
    for line in result.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue
        try:
            gpus.append(
                GpuInfo(
                    modelName=parts[0],
                    memoryTotalMB=int(float(parts[1])),
                    memoryUsedMB=int(float(parts[2])),
                    utilizationPercent=float(parts[3]),
                    temperatureCelsius=float(parts[4]),
                )
            )
        except (ValueError, IndexError):
            continue

    return gpus


def getNetworkInfo() -> list[NetworkInterfaceInfo]:
    # 采样 1s 计算速率
    io1 = psutil.net_io_counters(pernic=True)
    time.sleep(1)
    io2 = psutil.net_io_counters(pernic=True)

    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()

    results: list[NetworkInterfaceInfo] = []
    for name, counters in io2.items():
        ipAddress = None
        macAddress = None

        if name in addrs:
            for addr in addrs[name]:
                if addr.family == socket.AF_INET:
                    ipAddress = addr.address
                elif addr.family == getattr(socket, "AF_PACKET", -1):
                    macAddress = addr.address
                elif addr.family == getattr(psutil, "AF_LINK", -1):
                    macAddress = addr.address

        prev = io1.get(name)
        recvRate = float(counters.bytes_recv - prev.bytes_recv) if prev else 0.0
        sentRate = float(counters.bytes_sent - prev.bytes_sent) if prev else 0.0

        results.append(
            NetworkInterfaceInfo(
                interfaceName=name,
                ipAddress=ipAddress,
                macAddress=macAddress,
                recvBytesPerSec=recvRate,
                sentBytesPerSec=sentRate,
                totalRecvBytes=counters.bytes_recv,
                totalSentBytes=counters.bytes_sent,
                isUp=stats[name].isup if name in stats else False,
            )
        )

    return results
