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
    createdTime: datetime | None = None
    owner: str | None = None
    group: str | None = None



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


class GrepMatch(BaseModel):
    """Grep匹配结果的单条记录"""
    fileInfo: FileInfo
    lineNumber: int
    lineContent: str


class GrepResult(BaseModel):
    """Grep搜索结果的总体包装类"""
    success: bool
    pattern: str
    targetPath: str
    matches: list[GrepMatch]
    totalMatches: int
    errorMessage: str | None = None
