# class GatewayAbstractException(Exception):
#     """所有工具异常的基类，后端可统一捕获此类型做全局异常处理"""

#     def __init__(self, message: str, errorCode: str = "UNKNOWN_ERROR"):
#         self.message = message
#         self.errorCode = errorCode
#         super().__init__(self.message)

class GatewayAbstractException(Exception):
    def __init__(
        self, innerMessage: str = None, userMessage: str = None, cause: Exception = None # type: ignore
    ):
        self.innerMessage = innerMessage
        self.userMessage = userMessage
        self.cause = cause

class ToolExecutionException(GatewayAbstractException):
    """工具执行失败（命令返回非零、解析错误等）"""

    def __init__(self, innerMessage: str = None, cause: Exception = None): # type: ignore
        super().__init__(
            innerMessage=innerMessage,
            userMessage="系统命令执行失败，请稍后重试",
            cause=cause,
        )


class PermissionDeniedException(GatewayAbstractException):
    """权限不足"""

    def __init__(self, innerMessage: str = None, cause: Exception = None): # type: ignore
        super().__init__(
            innerMessage=innerMessage,
            userMessage="权限不足，该操作可能需要管理员权限",
            cause=cause,
        )


class ResourceNotFoundException(GatewayAbstractException):
    """目标资源不存在（文件/进程/服务等）"""

    def __init__(self, innerMessage: str = None, cause: Exception = None): # type: ignore
        super().__init__(
            innerMessage=innerMessage,
            userMessage="目标资源不存在",
            cause=cause,
        )


class ServiceUnavailableException(GatewayAbstractException):
    """依赖的服务未安装或不可用"""

    def __init__(self, innerMessage: str = None, cause: Exception = None): # type: ignore
        super().__init__(
            innerMessage=innerMessage,
            userMessage="所需服务未安装或不可用",
            cause=cause,
        )
