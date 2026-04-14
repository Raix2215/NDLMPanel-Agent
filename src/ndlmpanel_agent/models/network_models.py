from pydantic import BaseModel


class PingResult(BaseModel):
    isReachable: bool
    averageLatencyMs: float | None = None
    packetLossPercent: float | None = None


class PortCheckResult(BaseModel):
    isOpen: bool
    connectionTimeMs: float | None = None
