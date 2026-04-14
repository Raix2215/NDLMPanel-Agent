from pydantic import BaseModel


class DatabaseInstallInfo(BaseModel):
    isInstalled: bool
    version: str | None = None
    databaseType: str


class DatabaseStatus(BaseModel):
    isRunning: bool
    databaseType: str
    currentConnections: int | None = None
    slowQueryCount: int | None = None
