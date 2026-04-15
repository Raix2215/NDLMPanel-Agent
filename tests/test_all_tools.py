"""
工具函数完整测试
运行: uv run python tests/test_all_tools.py

测试策略:
- 只读操作: 直接执行，验证返回结构
- 写操作: 在 /tmp 下创建临时目录操作，测试完清理
- 需要特定服务的: 捕获 ServiceUnavailableException，标记为 SKIP
- 需要 root 的: 捕获 PermissionDeniedException，标记为 SKIP(NO_PERM)
"""

import os
import signal
import sys
import tempfile
import traceback
from pathlib import Path

# ──────────────────────────────────────────────
#  测试框架（简易版，不依赖 pytest）
# ──────────────────────────────────────────────

_results: list[tuple[str, str, str]] = []  # (模块, 测试名, 状态)


def _run(module: str, name: str, func):
    """执行单个测试，捕获所有异常"""
    from ndlmpanel_agent.exceptions import (
        GatewayAbstractException,
        PermissionDeniedException,
        ServiceUnavailableException,
    )

    try:
        result = func()
        _results.append((module, name, "PASS"))
        return result
    except ServiceUnavailableException as e:
        _results.append((module, name, f"SKIP(服务不可用: {e.innerMessage})"))
    except PermissionDeniedException as e:
        _results.append((module, name, f"SKIP(权限不足: {e.innerMessage})"))
    except GatewayAbstractException as e:
        _results.append((module, name, f"FAIL: {e.innerMessage}"))
    except Exception as e:
        _results.append((module, name, f"ERROR: {type(e).__name__}: {e}"))
        traceback.print_exc()
    return None


def _printReport():
    """打印测试报告"""
    print("\n" + "=" * 80)
    print("  测试报告")
    print("=" * 80)

    currentModule = ""
    passCount = failCount = skipCount = errorCount = 0

    for module, name, status in _results:
        if module != currentModule:
            currentModule = module
            print(f"\n  [{module}]")

        if status == "PASS":
            icon = "✅"
            passCount += 1
        elif status.startswith("SKIP"):
            icon = "⏭️ "
            skipCount += 1
        elif status.startswith("FAIL"):
            icon = "❌"
            failCount += 1
        else:
            icon = "💥"
            errorCount += 1

        print(f"    {icon} {name:40s} {status}")

    total = len(_results)
    print(f"\n{'=' * 80}")
    print(
        f"  合计: {total} | ✅ {passCount} | ⏭️  {skipCount} | ❌ {failCount} | 💥 {errorCount}"
    )
    print(f"{'=' * 80}")

    return failCount + errorCount


# ──────────────────────────────────────────────
#  系统监控测试
# ──────────────────────────────────────────────


def testSystemMonitor():
    from ndlmpanel_agent.tools import (
        getCpuInfo,
        getDiskInfo,
        getGpuInfo,
        getMemoryInfo,
        getNetworkInfo,
    )

    cpu = _run("系统监控", "getCpuInfo", getCpuInfo)
    if cpu:
        print(f"      → {cpu.modelName}, {cpu.coreCount}核, 使用率 {cpu.usagePercent}%")
        assert cpu.coreCount > 0, "核心数应大于0"
        assert 0 <= cpu.usagePercent <= 100, "CPU使用率应在0-100之间"

    mem = _run("系统监控", "getMemoryInfo", getMemoryInfo)
    if mem:
        totalGB = mem.totalBytes / (1024**3)
        usedGB = mem.usedBytes / (1024**3)
        print(f"      → 内存: {usedGB:.1f}G / {totalGB:.1f}G ({mem.usagePercent}%)")
        assert mem.totalBytes > 0, "总内存应大于0"
        assert mem.usedBytes <= mem.totalBytes, "已用内存不应超过总内存"

    disks = _run("系统监控", "getDiskInfo(含IO采样)", getDiskInfo)
    if disks:
        for d in disks[:3]:
            totalGB = d.totalBytes / (1024**3)
            print(
                f"      → {d.mountPoint}: {d.usagePercent}% of {totalGB:.1f}G [{d.fileSystem}]"
            )
            assert d.totalBytes > 0, f"{d.mountPoint} 总容量应大于0"

    gpus = _run("系统监控", "getGpuInfo(无GPU则为空列表)", getGpuInfo)
    if gpus is not None:
        if len(gpus) == 0:
            print("      → 未检测到 NVIDIA GPU（正常，LoongArch 无 N 卡驱动）")
        for g in gpus:
            print(
                f"      → {g.modelName}: {g.memoryUsedMB}MB/{g.memoryTotalMB}MB, {g.temperatureCelsius}°C"
            )

    nics = _run("系统监控", "getNetworkInfo(含速率采样)", getNetworkInfo)
    if nics:
        for n in nics[:3]:
            statusStr = "UP" if n.isUp else "DOWN"
            print(f"      → {n.interfaceName}: {n.ipAddress or 'N/A'} [{statusStr}]")


# ──────────────────────────────────────────────
#  文件系统测试
# ──────────────────────────────────────────────


def testFilesystem():
    from ndlmpanel_agent.tools import (
        changePermissions,
        createDirectory,
        createFile,
        deleteDirectory,
        deleteFile,
        listDirectory,
        renameFileOrDirectory,
    )

    # 在 /tmp 下创建隔离的测试目录
    testRoot = Path(tempfile.mkdtemp(prefix="ndlm_test_"))
    print(f"      → 测试目录: {testRoot}")

    # listDirectory
    _run("文件系统", "listDirectory(/tmp)", lambda: listDirectory("/tmp"))

    # createDirectory
    newDir = str(testRoot / "sub" / "nested")
    result = _run(
        "文件系统", "createDirectory(递归创建)", lambda: createDirectory(newDir)
    )
    if result:
        print(f"      → 创建目录: {result.absolutePath}")
        assert Path(newDir).exists(), "目录应被创建"

    # createFile
    newFile = str(testRoot / "test.txt")
    result = _run("文件系统", "createFile", lambda: createFile(newFile))
    if result:
        assert Path(newFile).exists(), "文件应被创建"

    # createFile 重复创建应抛异常
    from ndlmpanel_agent.exceptions import ToolExecutionException

    try:
        createFile(newFile)
        _results.append(("文件系统", "createFile(重复应报错)", "FAIL: 未抛出异常"))
    except ToolExecutionException:
        _results.append(("文件系统", "createFile(重复应报错)", "PASS"))
    except Exception as e:
        _results.append(("文件系统", "createFile(重复应报错)", f"ERROR: {e}"))

    # listDirectory 查看新建的内容
    items = _run(
        "文件系统", "listDirectory(测试目录)", lambda: listDirectory(str(testRoot))
    )
    if items:
        print(f"      → 目录内容: {[f.fileName for f in items]}")
        assert len(items) >= 2, "应至少有 sub/ 和 test.txt"

    # renameFileOrDirectory
    renamedFile = str(testRoot / "renamed.txt")
    result = _run(
        "文件系统",
        "renameFileOrDirectory",
        lambda: renameFileOrDirectory(newFile, renamedFile),
    )
    if result:
        assert Path(renamedFile).exists(), "重命名后的文件应存在"
        assert not Path(newFile).exists(), "原文件应不存在"

    # changePermissions
    result = _run(
        "文件系统",
        "changePermissions(644)",
        lambda: changePermissions(renamedFile, "644"),
    )
    if result:
        print(f"      → 权限修改后: {result.newPermissions}")

    # deleteFile
    result = _run("文件系统", "deleteFile", lambda: deleteFile(renamedFile))
    if result:
        assert not Path(renamedFile).exists(), "文件应被删除"

    # deleteDirectory 非空未强制应报错
    try:
        deleteDirectory(str(testRoot))
        _results.append(
            ("文件系统", "deleteDirectory(非空不强制应报错)", "FAIL: 未抛出异常")
        )
    except ToolExecutionException:
        _results.append(("文件系统", "deleteDirectory(非空不强制应报错)", "PASS"))
    except Exception as e:
        _results.append(
            ("文件系统", "deleteDirectory(非空不强制应报错)", f"ERROR: {e}")
        )

    # deleteDirectory 强制删除
    result = _run(
        "文件系统",
        "deleteDirectory(force=True)",
        lambda: deleteDirectory(str(testRoot), force=True),
    )
    if result:
        assert not testRoot.exists(), "目录应被删除"

    # 对不存在的路径操作应抛 ResourceNotFoundException
    from ndlmpanel_agent.exceptions import ResourceNotFoundException

    try:
        listDirectory("/nonexistent_path_12345")
        _results.append(("文件系统", "listDirectory(不存在应报错)", "FAIL: 未抛出异常"))
    except ResourceNotFoundException:
        _results.append(("文件系统", "listDirectory(不存在应报错)", "PASS"))
    except Exception as e:
        _results.append(("文件系统", "listDirectory(不存在应报错)", f"ERROR: {e}"))


# ──────────────────────────────────────────────
#  进程管理测试
# ──────────────────────────────────────────────


def testProcess():
    from ndlmpanel_agent.tools import killProcess, listProcesses
    from ndlmpanel_agent.models.ops.process.process_models import ProcessSortBy

    # 按 CPU 排序
    procs = _run(
        "进程管理",
        "listProcesses(按CPU排序)",
        lambda: listProcesses(sortBy=ProcessSortBy.CPU),
    )
    if procs:
        print(f"      → 共 {len(procs)} 个进程")
        if procs:
            top = procs[0]
            print(
                f"      → CPU最高: PID={top.pid} {top.processName} ({top.cpuPercent}%)"
            )

    # 按内存排序
    procs = _run(
        "进程管理",
        "listProcesses(按内存排序)",
        lambda: listProcesses(sortBy=ProcessSortBy.MEMORY),
    )
    if procs and procs:
        top = procs[0]
        print(
            f"      → 内存最高: PID={top.pid} {top.processName} ({top.memoryPercent}%)"
        )

    # 关键词筛选
    procs = _run(
        "进程管理", "listProcesses(筛选python)", lambda: listProcesses(keyword="python")
    )
    if procs is not None:
        print(f"      → 包含 'python' 的进程: {len(procs)} 个")

    # killProcess: 先 fork 一个子进程再杀掉，避免影响系统
    def testKillProcess():
        import subprocess

        # 启动一个无害的 sleep 进程
        child = subprocess.Popen(["sleep", "60"])
        childPid = child.pid
        print(f"      → 启动测试进程 PID={childPid}")
        result = killProcess(childPid, signalNumber=signal.SIGTERM)
        child.wait(timeout=5)
        assert result.success, "kill 应成功"
        print(f"      → 已终止 PID={childPid}")
        return result

    _run("进程管理", "killProcess(安全测试)", testKillProcess)

    # killProcess: 不存在的 PID
    from ndlmpanel_agent.exceptions import ResourceNotFoundException

    try:
        killProcess(999999999)
        _results.append(
            ("进程管理", "killProcess(不存在PID应报错)", "FAIL: 未抛出异常")
        )
    except ResourceNotFoundException:
        _results.append(("进程管理", "killProcess(不存在PID应报错)", "PASS"))
    except Exception as e:
        _results.append(("进程管理", "killProcess(不存在PID应报错)", f"ERROR: {e}"))


# ──────────────────────────────────────────────
#  防火墙测试
# ──────────────────────────────────────────────


def testFirewall():
    from ndlmpanel_agent.tools import (
        addFirewallPort,
        getFirewallStatus,
        listFirewallPorts,
        removeFirewallPort,
    )

    status = _run("防火墙", "getFirewallStatus", getFirewallStatus)
    if status:
        print(
            f"      → 后端: {status.backendType.value}, 活跃: {status.isActive}, 策略: {status.defaultPolicy}"
        )

    ports = _run("防火墙", "listFirewallPorts", listFirewallPorts)
    if ports is not None:
        print(f"      → 已放行端口数: {len(ports)}")
        for p in ports[:5]:
            print(f"        {p.port}/{p.protocol} [{p.policy}] {p.sourceIp or ''}")

    # 添加/删除测试端口（用高位端口避免冲突）
    testPort = 59999
    result = _run(
        "防火墙",
        f"addFirewallPort({testPort}/tcp)",
        lambda: addFirewallPort(testPort, "tcp", "测试端口"),
    )
    if result and result.success:
        print(f"      → 已添加 {testPort}/tcp")

        # 验证是否在列表中
        def verifyPortAdded():
            currentPorts = listFirewallPorts()
            found = any(
                p.port == testPort and p.protocol == "tcp" for p in currentPorts
            )
            assert found, f"端口 {testPort} 应在放行列表中"
            return currentPorts

        _run("防火墙", f"验证端口{testPort}已添加", verifyPortAdded)

        # 清理：删除测试端口
        _run(
            "防火墙",
            f"removeFirewallPort({testPort}/tcp)",
            lambda: removeFirewallPort(testPort, "tcp"),
        )


# ──────────────────────────────────────────────
#  日志查询测试
# ──────────────────────────────────────────────


def testLogs():
    from ndlmpanel_agent.tools import querySystemLogs

    # syslog
    result = _run(
        "日志查询",
        "querySystemLogs(syslog, 20行)",
        lambda: querySystemLogs("syslog", lineLimit=20),
    )
    if result:
        print(f"      → 获取 {result.totalLines} 行, 来源: {result.logSource}")
        if result.lines:
            print(f"      → 最新: {result.lines[-1][:80]}...")

    # auth 日志
    result = _run(
        "日志查询",
        "querySystemLogs(auth)",
        lambda: querySystemLogs("auth", lineLimit=10),
    )
    if result:
        print(f"      → auth 日志: {result.totalLines} 行")

    # 内核日志
    result = _run(
        "日志查询",
        "querySystemLogs(kern)",
        lambda: querySystemLogs("kern", lineLimit=10),
    )
    if result:
        print(f"      → kern 日志: {result.totalLines} 行")

    # 按关键词过滤
    result = _run(
        "日志查询",
        "querySystemLogs(关键词=error)",
        lambda: querySystemLogs("syslog", keyword="error", lineLimit=10),
    )
    if result:
        print(f"      → 包含 'error' 的日志: {result.totalLines} 行")

    # 按服务名查询
    result = _run(
        "日志查询",
        "querySystemLogs(sshd服务)",
        lambda: querySystemLogs("sshd", lineLimit=10),
    )
    if result:
        print(f"      → sshd 日志: {result.totalLines} 行")


# ──────────────────────────────────────────────
#  用户管理测试
# ──────────────────────────────────────────────


def testUsers():
    from ndlmpanel_agent.tools import getLoginHistory, listUsers

    users = _run("用户管理", "listUsers", listUsers)
    if users:
        print(f"      → 用户数: {len(users)}")
        for u in users[:5]:
            sudoTag = "[SUDO]" if u.isSudoUser else ""
            print(f"        {u.userName} (UID={u.uid}) {u.homeDirectory} {sudoTag}")

    history = _run("用户管理", "getLoginHistory", getLoginHistory)
    if history:
        print(f"      → 登录记录数: {len(history)}")
        for h in history[:3]:
            print(
                f"        {h.userName} from {h.loginIp or 'local'} at {h.loginTime} [{h.loginStatus}]"
            )


# ──────────────────────────────────────────────
#  网络诊断测试
# ──────────────────────────────────────────────


def testNetwork():
    from ndlmpanel_agent.tools import checkPortConnectivity, pingHost

    # ping 本地
    result = _run(
        "网络诊断", "pingHost(127.0.0.1)", lambda: pingHost("127.0.0.1", timeout=3)
    )
    if result:
        print(f"      → 可达: {result.isReachable}, 延迟: {result.averageLatencyMs}ms")
        assert result.isReachable, "本地回环应可达"

    # ping 外网
    result = _run(
        "网络诊断",
        "pingHost(223.5.5.5/阿里DNS)",
        lambda: pingHost("223.5.5.5", timeout=5),
    )
    if result:
        print(
            f"      → 可达: {result.isReachable}, 延迟: {result.averageLatencyMs}ms, 丢包: {result.packetLossPercent}%"
        )

    # 端口检测 - 本地 SSH
    result = _run(
        "网络诊断",
        "checkPortConnectivity(localhost:22)",
        lambda: checkPortConnectivity("127.0.0.1", 22, timeout=3),
    )
    if result:
        print(
            f"      → 22端口: {'开放' if result.isOpen else '关闭'}, 耗时: {result.connectionTimeMs}ms"
        )

    # 端口检测 - 不存在的端口
    result = _run(
        "网络诊断",
        "checkPortConnectivity(localhost:59998)",
        lambda: checkPortConnectivity("127.0.0.1", 59998, timeout=2),
    )
    if result:
        print(f"      → 59998端口: {'开放' if result.isOpen else '关闭'}（预期关闭）")


# ──────────────────────────────────────────────
#  系统信息测试
# ──────────────────────────────────────────────


def testSystemInfo():
    from ndlmpanel_agent.tools import (
        getEnvironmentVariables,
        getSystemVersion,
        getUptime,
    )

    ver = _run("系统信息", "getSystemVersion", getSystemVersion)
    if ver:
        print(f"      → 系统: {ver.osName}")
        print(f"      → 内核: {ver.kernelVersion}")
        print(f"      → 主机名: {ver.hostName}")

    uptime = _run("系统信息", "getUptime", getUptime)
    if uptime:
        print(f"      → 运行时间: {uptime.days}天 {uptime.hours}时 {uptime.minutes}分")
        print(f"      → 启动时间: {uptime.bootTime}")

    envVars = _run("系统信息", "getEnvironmentVariables", getEnvironmentVariables)
    if envVars is not None:
        print(f"      → 环境变量数: {len(envVars)}")
        # 验证几个一定存在的变量
        for key in ("HOME", "PATH", "USER"):
            if key in envVars:
                print(
                    f"        {key}={envVars[key][:60]}{'...' if len(envVars.get(key, '')) > 60 else ''}"
                )


# ──────────────────────────────────────────────
#  Docker 测试
# ──────────────────────────────────────────────


def testDocker():
    from ndlmpanel_agent.tools import checkDockerInstalled, getDockerContainers

    info = _run("Docker", "checkDockerInstalled", checkDockerInstalled)
    if info:
        if info.isInstalled:
            print(f"      → Docker 版本: {info.version}")

            containers = _run(
                "Docker",
                "getDockerContainers(all)",
                lambda: getDockerContainers(includeStoppedContainers=True),
            )
            if containers is not None:
                print(f"      → 容器数: {len(containers)}")
                for c in containers[:5]:
                    print(f"        {c.containerId[:12]} {c.imageName} [{c.status}]")
        else:
            print("      → Docker 未安装，跳过容器测试")
            _results.append(("Docker", "getDockerContainers", "SKIP(Docker未安装)"))


# ──────────────────────────────────────────────
#  Nginx 测试
# ──────────────────────────────────────────────


def testNginx():
    from ndlmpanel_agent.tools import checkNginxInstalled, getNginxStatus

    info = _run("Nginx", "checkNginxInstalled", checkNginxInstalled)
    if info:
        if info.isInstalled:
            print(f"      → Nginx 版本: {info.version}, 配置: {info.configPath}")

            status = _run("Nginx", "getNginxStatus", getNginxStatus)
            if status:
                print(
                    f"      → 运行: {status.isRunning}, Worker数: {status.workerProcessCount}"
                )
        else:
            print("      → Nginx 未安装，跳过状态测试")
            _results.append(("Nginx", "getNginxStatus", "SKIP(Nginx未安装)"))


# ──────────────────────────────────────────────
#  数据库测试
# ──────────────────────────────────────────────


def testDatabase():
    from ndlmpanel_agent.tools import checkDatabaseInstalled, getDatabaseStatus

    for dbType in ("mysql", "postgresql", "redis"):
        info = _run(
            "数据库",
            f"checkDatabaseInstalled({dbType})",
            lambda db=dbType: checkDatabaseInstalled(db),
        )
        if info:
            if info.isInstalled:
                print(f"      → {dbType} 版本: {info.version}")

                status = _run(
                    "数据库",
                    f"getDatabaseStatus({dbType})",
                    lambda db=dbType: getDatabaseStatus(db),
                )
                if status:
                    print(
                        f"        运行: {status.isRunning}, 连接数: {status.currentConnections}"
                    )
            else:
                print(f"      → {dbType} 未安装")


# ──────────────────────────────────────────────
#  服务管理测试
# ──────────────────────────────────────────────


def testService():
    from ndlmpanel_agent.models.ops.service.service_models import ServiceAction
    from ndlmpanel_agent.tools import manageSystemService

    # 只测试 status，不做 start/stop 避免影响系统
    for svc in ("sshd", "crond", "firewalld", "NetworkManager"):
        result = _run(
            "服务管理",
            f"manageSystemService({svc}, status)",
            lambda s=svc: manageSystemService(s, ServiceAction.STATUS),
        )
        if result:
            print(f"      → {svc}: {result.currentStatus}")


# ──────────────────────────────────────────────
#  changeOwner 测试（单独列出，需要注意权限）
# ──────────────────────────────────────────────


def testChangeOwner():
    from ndlmpanel_agent.tools import changeOwner, createFile

    testFile = Path(tempfile.mktemp(prefix="ndlm_chown_"))
    createFile(str(testFile))

    # 改为当前用户（一定有权限）
    currentUser = os.environ.get("USER", "nobody")
    import grp

    currentGid = os.getgid()
    try:
        currentGroup = grp.getgrgid(currentGid).gr_name
    except KeyError:
        currentGroup = str(currentGid)

    result = _run(
        "文件系统",
        "changeOwner(当前用户)",
        lambda: changeOwner(str(testFile), currentUser, currentGroup),
    )
    if result:
        print(f"      → 所有者: {result.newOwner}:{result.newGroup}")

    # 清理
    testFile.unlink(missing_ok=True)


# ──────────────────────────────────────────────
#  架构信息（辅助判断 LoongArch 兼容性）
# ──────────────────────────────────────────────


def printArchInfo():
    import platform

    print("=" * 80)
    print("  运行环境")
    print("=" * 80)
    print(f"  架构:    {platform.machine()}")
    print(f"  系统:    {platform.platform()}")
    print(f"  Python:  {platform.python_version()}")
    print(f"  用户:    {os.environ.get('USER', 'unknown')}")
    print(f"  UID:     {os.getuid()}")
    isRoot = os.getuid() == 0
    print(f"  Root:    {'是' if isRoot else '否'}")
    if not isRoot:
        print("  ⚠️  非 root 运行，防火墙写操作和部分权限操作将跳过")
    print()


# ──────────────────────────────────────────────
#  主入口
# ──────────────────────────────────────────────


def main():
    printArchInfo()

    testSystemMonitor()
    testFilesystem()
    testChangeOwner()
    testProcess()
    testFirewall()
    testLogs()
    testUsers()
    testNetwork()
    testSystemInfo()
    testDocker()
    testNginx()
    testDatabase()
    testService()

    failures = _printReport()
    sys.exit(1 if failures > 0 else 0)


if __name__ == "__main__":
    main()
