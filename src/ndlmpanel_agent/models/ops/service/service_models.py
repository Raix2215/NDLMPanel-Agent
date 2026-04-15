from enum import Enum

from pydantic import BaseModel


class ServiceAction(str, Enum):
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    STATUS = "status"
    ENABLE = "enable"
    DISABLE = "disable"


class ServiceOperationResult(BaseModel):
    success: bool
    serviceName: str
    currentStatus: str
    message: str | None = None
