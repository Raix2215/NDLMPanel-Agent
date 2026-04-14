"""
文件系统操作工具
使用 pathlib/os/shutil，不依赖外部命令
"""

import grp
import os
import pwd
import shutil
import stat
from datetime import datetime
from pathlib import Path

from ndlmpanel_agent.exceptions import (
    PermissionDeniedException,
    ResourceNotFoundException,
    ToolExecutionException,
)
from ndlmpanel_agent.models.filesystem_models import (
    FileInfo,
    FileOperationResult,
    FileType,
    OwnerChangeResult,
    PermissionChangeResult,
)


# ────────────────── 内部辅助 ──────────────────


def _resolveFileType(path: Path) -> FileType:
    if path.is_symlink():
        return FileType.SYMLINK
    if path.is_dir():
        return FileType.DIRECTORY
    if path.is_file():
        return FileType.FILE
    return FileType.OTHER


def _formatPermissions(mode: int) -> str:
    """将 st_mode 中的权限位转为 rwx 字符串，如 'rwxr-xr-x'"""
    octalMode = stat.S_IMODE(mode)
    result = ""
    for shift in (6, 3, 0):
        bits = (octalMode >> shift) & 0o7
        result += "r" if bits & 4 else "-"
        result += "w" if bits & 2 else "-"
        result += "x" if bits & 1 else "-"
    return result


def _requireExists(path: Path, label: str = "路径") -> None:
    if not path.exists():
        raise ResourceNotFoundException(f"{label}不存在: {path}")


# ────────────────── 公开接口 ──────────────────


def listDirectory(targetPath: str) -> list[FileInfo]:
    path = Path(targetPath)
    _requireExists(path, "目录")
    if not path.is_dir():
        raise ToolExecutionException(f"目标不是目录: {targetPath}")

    results: list[FileInfo] = []
    try:
        entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    except PermissionError:
        raise PermissionDeniedException(f"无权访问目录: {targetPath}")

    for entry in entries:
        try:
            st = entry.lstat()
            results.append(
                FileInfo(
                    fileName=entry.name,
                    fileType=_resolveFileType(entry),
                    sizeBytes=st.st_size,
                    permissions=_formatPermissions(st.st_mode),
                    modifiedTime=datetime.fromtimestamp(st.st_mtime),
                    absolutePath=str(entry.resolve())
                    if not entry.is_symlink()
                    else str(entry.absolute()),
                )
            )
        except (PermissionError, OSError):
            continue

    return results


def createFile(targetPath: str) -> FileOperationResult:
    path = Path(targetPath)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=False)
        return FileOperationResult(success=True, absolutePath=str(path.resolve()))
    except FileExistsError:
        raise ToolExecutionException(f"文件已存在: {targetPath}")
    except PermissionError:
        raise PermissionDeniedException(f"无权创建文件: {targetPath}")


def createDirectory(targetPath: str) -> FileOperationResult:
    path = Path(targetPath)
    try:
        path.mkdir(parents=True, exist_ok=True)
        return FileOperationResult(success=True, absolutePath=str(path.resolve()))
    except PermissionError:
        raise PermissionDeniedException(f"无权创建目录: {targetPath}")


def deleteFile(targetPath: str) -> FileOperationResult:
    path = Path(targetPath)
    _requireExists(path, "文件")
    if not path.is_file() and not path.is_symlink():
        raise ToolExecutionException(f"目标不是文件: {targetPath}")
    try:
        path.unlink()
        return FileOperationResult(success=True, absolutePath=targetPath)
    except PermissionError:
        raise PermissionDeniedException(f"无权删除文件: {targetPath}")


def deleteDirectory(targetPath: str, force: bool = False) -> FileOperationResult:
    path = Path(targetPath)
    _requireExists(path, "目录")
    if not path.is_dir():
        raise ToolExecutionException(f"目标不是目录: {targetPath}")

    try:
        if force:
            shutil.rmtree(path)
        else:
            path.rmdir()
        return FileOperationResult(success=True, absolutePath=targetPath)
    except OSError as e:
        if "not empty" in str(e).lower():
            raise ToolExecutionException(
                f"目录非空，请设置 force=True 以强制删除: {targetPath}"
            )
        raise PermissionDeniedException(f"删除目录失败: {e}")


def renameFileOrDirectory(sourcePath: str, destinationPath: str) -> FileOperationResult:
    src = Path(sourcePath)
    _requireExists(src, "源路径")

    dst = Path(destinationPath)
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        return FileOperationResult(success=True, absolutePath=str(dst.resolve()))
    except PermissionError:
        raise PermissionDeniedException(
            f"无权执行重命名/移动: {sourcePath} → {destinationPath}"
        )
    except OSError as e:
        raise ToolExecutionException(f"重命名/移动失败: {e}")


def changePermissions(
    targetPath: str,
    permissionMode: str,
    recursive: bool = False,
) -> PermissionChangeResult:
    path = Path(targetPath)
    _requireExists(path)

    # 解析八进制权限（如 "755"）
    try:
        mode = int(permissionMode, 8)
    except ValueError:
        raise ToolExecutionException(
            f"权限格式错误，请使用八进制格式如 '755': {permissionMode}"
        )

    try:
        if recursive and path.is_dir():
            for root, dirs, files in os.walk(path):
                os.chmod(root, mode)
                for f in files:
                    os.chmod(os.path.join(root, f), mode)
        else:
            os.chmod(path, mode)

        newMode = stat.S_IMODE(path.stat().st_mode)
        return PermissionChangeResult(success=True, newPermissions=oct(newMode)[2:])
    except PermissionError:
        raise PermissionDeniedException(f"无权修改权限: {targetPath}")


def changeOwner(
    targetPath: str,
    owner: str,
    group: str,
    recursive: bool = False,
) -> OwnerChangeResult:
    path = Path(targetPath)
    _requireExists(path)

    try:
        uid = pwd.getpwnam(owner).pw_uid
    except KeyError:
        raise ToolExecutionException(f"用户不存在: {owner}")

    try:
        gid = grp.getgrnam(group).gr_gid
    except KeyError:
        raise ToolExecutionException(f"用户组不存在: {group}")

    try:
        if recursive and path.is_dir():
            for root, dirs, files in os.walk(path):
                os.chown(root, uid, gid)
                for f in files:
                    os.chown(os.path.join(root, f), uid, gid)
        else:
            os.chown(str(path), uid, gid)

        return OwnerChangeResult(success=True, newOwner=owner, newGroup=group)
    except PermissionError:
        raise PermissionDeniedException(f"无权修改所有者(通常需要root): {targetPath}")
