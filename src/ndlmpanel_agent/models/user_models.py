from pydantic import BaseModel


class UserInfo(BaseModel):
    userName: str
    uid: int
    gid: int
    homeDirectory: str
    loginShell: str
    isSudoUser: bool


class LoginRecord(BaseModel):
    userName: str
    loginIp: str | None
    loginTime: str
    loginStatus: str
