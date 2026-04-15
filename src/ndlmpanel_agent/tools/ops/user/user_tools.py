import pwd

from ndlmpanel_agent.models.ops.user.user_models import LoginRecord, UserInfo
from ndlmpanel_agent.tools.ops._command_runner import runCommand


def _getSudoUserNames() -> set[str]:
    """收集 sudo/wheel 组中的用户名"""
    sudoUsers: set[str] = set()
    for groupName in ("sudo", "wheel"):
        try:
            result = runCommand(["getent", "group", groupName], checkReturnCode=False)
            if result.returncode == 0:
                parts = result.stdout.strip().split(":")
                if len(parts) >= 4 and parts[3]:
                    sudoUsers.update(parts[3].split(","))
        except Exception:
            continue
    return sudoUsers


def listUsers() -> list[UserInfo]:
    sudoUsers = _getSudoUserNames()
    users: list[UserInfo] = []

    for p in pwd.getpwall():
        # 过滤系统用户（UID < 1000），但保留 root
        if p.pw_uid < 1000 and p.pw_uid != 0:
            continue

        users.append(
            UserInfo(
                userName=p.pw_name,
                uid=p.pw_uid,
                gid=p.pw_gid,
                homeDirectory=p.pw_dir,
                loginShell=p.pw_shell,
                isSudoUser=(p.pw_name in sudoUsers or p.pw_uid == 0),
            )
        )

    return users


def getLoginHistory() -> list[LoginRecord]:
    result = runCommand(["last", "-n", "50", "-i", "-F"], checkReturnCode=False)

    records: list[LoginRecord] = []
    for line in result.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) < 4 or parts[0] in ("reboot", "wtmp", ""):
            continue

        userName = parts[0]
        # 第 3 列如果包含点号则为 IP
        loginIp = parts[2] if len(parts) > 2 and "." in parts[2] else None

        timeStr = " ".join(parts[3:7]) if len(parts) > 6 else " ".join(parts[3:])

        status = "success"
        if "still logged in" in line:
            status = "online"
        elif "gone - no logout" in line:
            status = "abnormal"

        records.append(
            LoginRecord(
                userName=userName,
                loginIp=loginIp,
                loginTime=timeStr,
                loginStatus=status,
            )
        )

    return records
