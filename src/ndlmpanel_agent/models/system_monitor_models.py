from pydantic import BaseModel


class CpuInfo(BaseModel):
    modelName: str
    coreCount: int
    usagePercent: float
    load1Min: float
    load5Min: float
    load15Min: float


class MemoryInfo(BaseModel):
    totalBytes: int
    usedBytes: int
    availableBytes: int
    usagePercent: float
    swapTotalBytes: int
    swapUsedBytes: int
    swapUsagePercent: float


class DiskPartitionInfo(BaseModel):
    mountPoint: str
    fileSystem: str
    totalBytes: int
    usedBytes: int
    usagePercent: float
    readBytesPerSec: float
    writeBytesPerSec: float


class GpuInfo(BaseModel):
    modelName: str
    memoryTotalMB: int
    memoryUsedMB: int
    utilizationPercent: float
    temperatureCelsius: float


class NetworkInterfaceInfo(BaseModel):
    interfaceName: str
    ipAddress: str | None
    macAddress: str | None
    recvBytesPerSec: float
    sentBytesPerSec: float
    totalRecvBytes: int
    totalSentBytes: int
    isUp: bool
