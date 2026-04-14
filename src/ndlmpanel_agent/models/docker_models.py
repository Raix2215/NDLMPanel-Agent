from pydantic import BaseModel


class DockerInstallInfo(BaseModel):
    isInstalled: bool
    version: str | None = None


class DockerContainer(BaseModel):
    containerId: str
    imageName: str
    status: str
    ports: str
    cpuPercent: float | None = None
    memoryUsageMB: float | None = None
    memoryLimitMB: float | None = None
