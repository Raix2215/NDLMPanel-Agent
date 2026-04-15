"""
内部工具：统一的系统命令执行封装
所有需要调用外部命令的工具函数都通过此模块执行
"""

import subprocess

from ndlmpanel_agent.exceptions import (
    PermissionDeniedException,
    ToolExecutionException,
)

_PERMISSION_KEYWORDS = [
    "permission denied",
    "not permitted",
    "operation not permitted",
    "access denied",
    "authentication failure",
]


def runCommand(
    command: list[str],
    timeout: int = 30,
    checkReturnCode: bool = True,
    useSudo: bool = False,
) -> subprocess.CompletedProcess:
    """
    执行系统命令并返回结果

    Args:
        command:          命令和参数列表，如 ["df", "-h"]
        timeout:          超时秒数
        checkReturnCode:  是否检查返回码，非零则抛异常
        useSudo:          是否用 sudo -n（非交互式）提权执行
    """
    if useSudo:
        command = ["sudo", "-n"] + command

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if checkReturnCode and result.returncode != 0:
            stderr = result.stderr.strip()
            if any(kw in stderr.lower() for kw in _PERMISSION_KEYWORDS):
                raise PermissionDeniedException(
                    f"权限不足: {' '.join(command)}\n{stderr}"
                )
            raise ToolExecutionException(
                f"命令执行失败(code={result.returncode}): {' '.join(command)}\n{stderr}"
            )
        return result

    except subprocess.TimeoutExpired as e:
        raise ToolExecutionException(
            innerMessage=f"命令执行超时({timeout}s): {' '.join(command)}",
            cause=e,
        )
    except FileNotFoundError as e:
        raise ToolExecutionException(
            innerMessage=f"命令不存在: {command[0]}",
            cause=e,
    )
