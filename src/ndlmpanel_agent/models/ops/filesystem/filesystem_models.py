from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class FileType(str, Enum):
    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    OTHER = "other"


class FileInfo(BaseModel):
    fileName: str
    fileType: FileType
    sizeBytes: int
    permissions: str
    modifiedTime: datetime
    absolutePath: str


class FileOperationResult(BaseModel):
    success: bool
    absolutePath: str | None = None
    errorMessage: str | None = None


class PermissionChangeResult(BaseModel):
    success: bool
    newPermissions: str | None = None
    errorMessage: str | None = None


class OwnerChangeResult(BaseModel):
    success: bool
    newOwner: str | None = None
    newGroup: str | None = None
    errorMessage: str | None = None
