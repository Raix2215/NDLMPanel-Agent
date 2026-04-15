import re

from ndlmpanel_agent.exceptions import ToolExecutionException
from ndlmpanel_agent.models.ops.misc.database_models import DatabaseInstallInfo, DatabaseStatus
from ndlmpanel_agent.tools.ops._command_runner import runCommand

# 数据库类型 → 版本检测命令
_VERSION_COMMANDS: dict[str, list[str]] = {
    "mysql": ["mysql", "--version"],
    "mariadb": ["mysql", "--version"],
    "postgresql": ["psql", "--version"],
    "postgres": ["psql", "--version"],
    "redis": ["redis-server", "--version"],
    "mongodb": ["mongod", "--version"],
}

# 数据库类型 → systemd 服务名候选
_SERVICE_NAMES: dict[str, list[str]] = {
    "mysql": ["mysql", "mysqld", "mariadb"],
    "mariadb": ["mariadb", "mysql", "mysqld"],
    "postgresql": ["postgresql", "postgres"],
    "postgres": ["postgresql", "postgres"],
    "redis": ["redis", "redis-server"],
    "mongodb": ["mongod", "mongodb"],
}


def checkDatabaseInstalled(databaseType: str = "mysql") -> DatabaseInstallInfo:
    dbType = databaseType.lower()
    cmd = _VERSION_COMMANDS.get(dbType)
    if not cmd:
        return DatabaseInstallInfo(isInstalled=False, databaseType=databaseType)

    try:
        result = runCommand(cmd, checkReturnCode=False)
        output = result.stdout.strip() or result.stderr.strip()
        match = re.search(r"(\d+\.\d+\.\d+)", output)
        return DatabaseInstallInfo(
            isInstalled=True,
            version=match.group(1) if match else output[:50],
            databaseType=databaseType,
        )
    except ToolExecutionException:
        return DatabaseInstallInfo(isInstalled=False, databaseType=databaseType)


def getDatabaseStatus(databaseType: str = "mysql") -> DatabaseStatus:
    dbType = databaseType.lower()
    serviceNames = _SERVICE_NAMES.get(dbType, [dbType])

    isRunning = False
    for name in serviceNames:
        try:
            result = runCommand(["systemctl", "is-active", name], checkReturnCode=False)
            if result.stdout.strip() == "active":
                isRunning = True
                break
        except ToolExecutionException:
            continue

    currentConnections = None
    slowQueryCount = None

    if isRunning and dbType in ("mysql", "mariadb"):
        try:
            result = runCommand(
                ["mysqladmin", "status"], checkReturnCode=False, timeout=5
            )
            if result.returncode == 0:
                tMatch = re.search(r"Threads:\s*(\d+)", result.stdout)
                sMatch = re.search(r"Slow queries:\s*(\d+)", result.stdout)
                if tMatch:
                    currentConnections = int(tMatch.group(1))
                if sMatch:
                    slowQueryCount = int(sMatch.group(1))
        except ToolExecutionException:
            pass

    return DatabaseStatus(
        isRunning=isRunning,
        databaseType=databaseType,
        currentConnections=currentConnections,
        slowQueryCount=slowQueryCount,
    )
