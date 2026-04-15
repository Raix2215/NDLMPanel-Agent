from datetime import datetime

from pydantic import BaseModel


class SystemVersion(BaseModel):
    osName: str
    kernelVersion: str
    hostName: str


class UptimeInfo(BaseModel):
    days: int
    hours: int
    minutes: int
    bootTime: datetime
