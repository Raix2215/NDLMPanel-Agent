from enum import Enum

from pydantic import BaseModel


class ProcessSortBy(str, Enum):
    CPU = "cpu"
    MEMORY = "memory"
    PID = "pid"


class ProcessInfo(BaseModel):
    pid: int
    processName: str
    userName: str
    cpuPercent: float
    memoryPercent: float
    status: str
    command: str


class ProcessKillResult(BaseModel):
    success: bool
    pid: int
    errorMessage: str | None = None
