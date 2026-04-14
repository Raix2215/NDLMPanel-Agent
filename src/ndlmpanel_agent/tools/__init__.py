from ndlmpanel_agent.tools.database_tools import (
    checkDatabaseInstalled,
    getDatabaseStatus,
)
from ndlmpanel_agent.tools.docker_tools import checkDockerInstalled, getDockerContainers
from ndlmpanel_agent.tools.filesystem_tools import (
    changeOwner,
    changePermissions,
    createDirectory,
    createFile,
    deleteDirectory,
    deleteFile,
    listDirectory,
    renameFileOrDirectory,
)
from ndlmpanel_agent.tools.firewall_tools import (
    addFirewallPort,
    getFirewallStatus,
    listFirewallPorts,
    removeFirewallPort,
)
from ndlmpanel_agent.tools.log_tools import querySystemLogs
from ndlmpanel_agent.tools.network_tools import checkPortConnectivity, pingHost
from ndlmpanel_agent.tools.nginx_tools import checkNginxInstalled, getNginxStatus
from ndlmpanel_agent.tools.process_tools import killProcess, listProcesses
from ndlmpanel_agent.tools.service_tools import manageSystemService
from ndlmpanel_agent.tools.system_info_tools import (
    getEnvironmentVariables,
    getSystemVersion,
    getUptime,
)
from ndlmpanel_agent.tools.system_monitor_tools import (
    getCpuInfo,
    getDiskInfo,
    getGpuInfo,
    getMemoryInfo,
    getNetworkInfo,
)
from ndlmpanel_agent.tools.user_tools import getLoginHistory, listUsers

__all__ = [
    # 防火墙
    "getFirewallStatus",
    "listFirewallPorts",
    "addFirewallPort",
    "removeFirewallPort",
    # 系统监控
    "getCpuInfo",
    "getMemoryInfo",
    "getDiskInfo",
    "getGpuInfo",
    "getNetworkInfo",
    # 文件系统
    "listDirectory",
    "createFile",
    "createDirectory",
    "deleteFile",
    "deleteDirectory",
    "renameFileOrDirectory",
    "changePermissions",
    "changeOwner",
    # 进程
    "listProcesses",
    "killProcess",
    # 日志
    "querySystemLogs",
    # 用户
    "listUsers",
    "getLoginHistory",
    # 网络诊断
    "pingHost",
    "checkPortConnectivity",
    # 系统信息
    "getSystemVersion",
    "getUptime",
    "getEnvironmentVariables",
    # Docker
    "checkDockerInstalled",
    "getDockerContainers",
    # Nginx
    "checkNginxInstalled",
    "getNginxStatus",
    # 数据库
    "checkDatabaseInstalled",
    "getDatabaseStatus",
    # 服务管理
    "manageSystemService",
]
