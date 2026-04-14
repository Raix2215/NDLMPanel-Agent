from pydantic import BaseModel


class NginxInstallInfo(BaseModel):
    isInstalled: bool
    version: str | None = None
    configPath: str | None = None


class NginxStatus(BaseModel):
    isRunning: bool
    workerProcessCount: int
    activeConnections: int | None = None
    requestsPerSecond: float | None = None
