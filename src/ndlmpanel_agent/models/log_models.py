from pydantic import BaseModel


class LogQueryResult(BaseModel):
    lines: list[str]
    totalLines: int
    logSource: str
