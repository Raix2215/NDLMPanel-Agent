from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ProcessSortBy(str, Enum):
    CPU = "cpu"
    MEMORY = "memory"
    PID = "pid"


class ProcessPortInfo(BaseModel):
    listenAddress: str
    protocol: str
    port: int


class ProcessInfo(BaseModel):
    pid: int
    processName: str
    userName: str
    cpuPercent: float
    memoryPercent: float
    status: str
    command: str
    ports: list[ProcessPortInfo] | None = None


class ProcessDetailInfo(ProcessInfo):
    parentPid: int | None 
    startTime: datetime | None
    exePath: str | None
    threadCount: int | None
    fdCount: int | None
    workDir: str | None
    rss: int | None
    vms: int | None


class ProcessKillResult(BaseModel):
    success: bool
    pid: int
    errorMessage: str | None = None


class ProcessAutoCleanResult(BaseModel):
    killedProcesses: list[ProcessKillResult]
    totalScanned: int
    totalKilled: int


class BatchKillMode(str, Enum):
    SIGTERM = "sigterm"
    SIGKILL = "sigkill"


class BatchKillResult(BaseModel):
    results: list[ProcessKillResult]
    totalRequested: int
    totalSuccess: int
    totalFailed: int
