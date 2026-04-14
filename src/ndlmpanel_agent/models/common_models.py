from pydantic import BaseModel


class OperationResult(BaseModel):
    """多个写操作共用的通用返回"""

    success: bool
    message: str | None = None
