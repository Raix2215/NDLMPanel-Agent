from pydantic import BaseModel
from enum import Enum


class FirewallBackendType(str, Enum):
    FIREWALLD = "firewalld"
    UFW = "ufw"
    IPTABLES = "iptables"
    UNKNOWN = "unknown"


class FirewallStatus(BaseModel):
    isActive: bool
    defaultPolicy: str
    backendType: FirewallBackendType


class FirewallPortRule(BaseModel):
    port: int
    protocol: str
    policy: str
    sourceIp: str | None = None


class FirewallPortOperationResult(BaseModel):
    success: bool
    port: int | None = None
    protocol: str | None = None
    message: str | None = None
