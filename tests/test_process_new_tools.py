#!/usr/bin/env python3
"""
新增进程工具函数测试
运行: uv run python tests/test_process_new_tools.py

测试策略:
- 使用当前系统进程进行只读测试（listProcesses, getProcessDetail, getZombieOrphanProcesses）
- 使用临时子进程测试写操作（killProcess, batchKillProcesses, autoCleanProcesses）
- 覆盖正常流程和异常流程
"""

import os
import signal
import subprocess
import sys
import time
import traceback

from ndlmpanel_agent.exceptions import (
    GatewayAbstractException,
    ResourceNotFoundException,
    ToolExecutionException,
)
from ndlmpanel_agent.models.ops.process.process_models import (
    BatchKillMode,
    ProcessDetailInfo,
    ProcessInfo,
    ProcessPortInfo,
)
from ndlmpanel_agent.tools.ops.process.process_tools import (
    autoCleanProcesses,
    batchKillProcesses,
    getProcessDetail,
    getZombieOrphanProcesses,
    killProcess,
    listProcesses,
)

_results: list[tuple[str, str, str]] = []


def _run(module: str, name: str, func):
    try:
        result = func()
        _results.append((module, name, "PASS"))
        return result
    except ResourceNotFoundException as e:
        _results.append((module, name, f"SKIP(资源不存在: {e.innerMessage})"))
    except GatewayAbstractException as e:
        _results.append((module, name, f"FAIL: {e.innerMessage}"))
    except Exception as e:
        _results.append((module, name, f"ERROR: {type(e).__name__}: {e}"))
        traceback.print_exc()
    return None


def _expectFail(module: str, name: str, func, expectedException=ToolExecutionException):
    try:
        func()
        _results.append((module, name, "FAIL: 未抛出预期异常"))
    except expectedException:
        _results.append((module, name, "PASS"))
    except GatewayAbstractException as e:
        _results.append((module, name, f"PASS(抛出其他Gateway异常: {type(e).__name__})"))
    except Exception as e:
        _results.append((module, name, f"ERROR: {type(e).__name__}: {e}"))


def _printReport():
    print("\n" + "=" * 80)
    print("  新增进程工具 - 测试报告")
    print("=" * 80)

    currentModule = ""
    passCount = failCount = skipCount = errorCount = 0

    for module, name, status in _results:
        if module != currentModule:
            currentModule = module
            print(f"\n  [{module}]")

        if status == "PASS" or status.startswith("PASS("):
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

        print(f"    {icon} {name:50s} {status}")

    total = len(_results)
    print(f"\n{'=' * 80}")
    print(
        f"  合计: {total} | ✅ {passCount} | ⏭️  {skipCount} | ❌ {failCount} | 💥 {errorCount}"
    )
    print(f"{'=' * 80}")

    return failCount + errorCount


def _spawnSleepProcess(timeout: int = 60) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", f"import time; time.sleep({timeout})"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def testListProcesses():
    M = "listProcesses"

    result = _run(M, "默认排序(CPU)", lambda: listProcesses())
    if result:
        assert isinstance(result, list), "应返回列表"
        assert len(result) > 0, "应至少有一个进程"
        first = result[0]
        assert isinstance(first, ProcessInfo), "元素应为ProcessInfo"
        print(f"      → 进程数: {len(result)}, 首个: PID={first.pid} {first.processName}")

    result = _run(M, "按内存排序", lambda: listProcesses(sortBy="memory"))
    if result:
        assert len(result) > 0, "应至少有一个进程"

    result = _run(M, "按PID排序", lambda: listProcesses(sortBy="pid"))
    if result:
        assert len(result) > 0
        pids = [p.pid for p in result]
        assert pids == sorted(pids), "PID应升序排列"
        print(f"      → PID升序: {pids[:5]}...")

    result = _run(M, "关键词过滤(python)", lambda: listProcesses(keyword="python"))
    if result:
        print(f"      → 含python的进程数: {len(result)}")

    result = _run(M, "关键词过滤(不存在的进程名)", lambda: listProcesses(keyword="zzz_nonexistent_xyz"))
    if result is not None:
        assert len(result) == 0, "不存在的关键词应返回空列表"


def testListProcessesWithPorts():
    M = "listProcesses(端口信息)"

    result = _run(M, "检查端口字段", lambda: listProcesses())
    if result:
        processesWithPorts = [p for p in result if p.ports is not None and len(p.ports) > 0]
        print(f"      → 有监听端口的进程数: {len(processesWithPorts)}")
        for p in processesWithPorts[:3]:
            portStr = ", ".join(f"{pt.protocol}/{pt.port}({pt.listenAddress})" for pt in p.ports)
            print(f"      → PID={p.pid} {p.processName}: {portStr}")
            for pt in p.ports:
                assert isinstance(pt, ProcessPortInfo), "端口信息应为ProcessPortInfo"
                assert 1 <= pt.port <= 65535, f"端口号应在1-65535范围内: {pt.port}"
                assert pt.protocol in ("TCP", "UDP"), f"协议应为TCP/UDP: {pt.protocol}"


def testGetProcessDetail():
    M = "getProcessDetail"

    currentPid = os.getpid()
    result = _run(M, f"当前进程详情(PID={currentPid})", lambda: getProcessDetail(currentPid))
    if result:
        assert isinstance(result, ProcessDetailInfo), "应返回ProcessDetailInfo"
        assert result.pid == currentPid, f"PID应匹配: {result.pid} != {currentPid}"
        assert result.processName is not None, "进程名不应为空"
        print(f"      → PID={result.pid}, 名称={result.processName}")
        print(f"      → 父PID={result.parentPid}, 线程数={result.threadCount}")
        print(f"      → exePath={result.exePath}")
        print(f"      → workDir={result.workDir}")
        print(f"      → RSS={result.rss}, VMS={result.vms}")
        print(f"      → fdCount={result.fdCount}")
        print(f"      → startTime={result.startTime}")

    result = _run(M, "PID=1(init/systemd)", lambda: getProcessDetail(1))
    if result:
        assert result.pid == 1
        print(f"      → PID=1, 名称={result.processName}, ppid={result.parentPid}")

    _expectFail(M, "不存在的PID", lambda: getProcessDetail(9999999), ResourceNotFoundException)


def testKillProcess():
    M = "killProcess"

    proc = _spawnSleepProcess()
    time.sleep(0.3)
    pid = proc.pid

    result = _run(M, f"SIGTERM终止子进程(PID={pid})", lambda: killProcess(pid))
    if result:
        assert result.success, "应成功终止"
        assert result.pid == pid, "PID应匹配"
        print(f"      → 终止成功: PID={result.pid}")

    proc.wait(timeout=5)

    _expectFail(M, "终止不存在的进程", lambda: killProcess(9999999), ResourceNotFoundException)


def testAutoCleanProcesses():
    M = "autoCleanProcesses"

    result = _run(M, "高阈值(99/99)不应杀进程", lambda: autoCleanProcesses(99, 99))
    if result:
        assert result.totalScanned > 0, "应扫描了进程"
        assert result.totalKilled == 0, "高阈值下不应杀任何进程"
        print(f"      → 扫描: {result.totalScanned}, 终止: {result.totalKilled}")

    _expectFail(M, "CPU阈值=0应报错", lambda: autoCleanProcesses(0, 80))
    _expectFail(M, "CPU阈值=101应报错", lambda: autoCleanProcesses(101, 80))
    _expectFail(M, "内存阈值=-1应报错", lambda: autoCleanProcesses(90, -1))
    _expectFail(M, "内存阈值=200应报错", lambda: autoCleanProcesses(90, 200))


def testGetZombieOrphanProcesses():
    M = "getZombieOrphanProcesses"

    result = _run(M, "获取僵尸/孤儿进程", lambda: getZombieOrphanProcesses())
    if result is not None:
        assert isinstance(result, list), "应返回列表"
        print(f"      → 僵尸/孤儿进程数: {len(result)}")
        for p in result[:5]:
            print(f"      → PID={p.pid}, 名称={p.processName}, 状态={p.status}")
            assert isinstance(p, ProcessInfo), "元素应为ProcessInfo"
            assert p.status in ("zombie", "sleeping", "running", "idle", "stopped"), f"状态: {p.status}"


def testBatchKillProcesses():
    M = "batchKillProcesses"

    proc1 = _spawnSleepProcess()
    proc2 = _spawnSleepProcess()
    proc3 = _spawnSleepProcess()
    time.sleep(0.3)

    pids = [proc1.pid, proc2.pid, proc3.pid]
    print(f"      → 创建子进程: {pids}")

    result = _run(M, "批量SIGTERM终止3个子进程", lambda: batchKillProcesses(pids, BatchKillMode.SIGTERM))
    if result:
        assert result.totalRequested == 3, f"请求数应为3: {result.totalRequested}"
        assert result.totalSuccess == 3, f"成功数应为3: {result.totalSuccess}"
        assert result.totalFailed == 0, f"失败数应为0: {result.totalFailed}"
        print(f"      → 请求: {result.totalRequested}, 成功: {result.totalSuccess}, 失败: {result.totalFailed}")

    for p in [proc1, proc2, proc3]:
        p.wait(timeout=5)

    result = _run(M, "批量终止含不存在PID", lambda: batchKillProcesses([9999998, 9999999], BatchKillMode.SIGTERM))
    if result:
        assert result.totalRequested == 2
        assert result.totalSuccess == 0, "不存在的PID应全部失败"
        assert result.totalFailed == 2
        for r in result.results:
            assert not r.success, "不存在的PID应失败"
            assert r.errorMessage is not None, "失败应有错误信息"
        print(f"      → 不存在PID: 成功={result.totalSuccess}, 失败={result.totalFailed}")

    proc4 = _spawnSleepProcess()
    time.sleep(0.3)
    result = _run(M, "混合存在/不存在PID", lambda: batchKillProcesses([proc4.pid, 9999999], BatchKillMode.SIGTERM))
    if result:
        assert result.totalRequested == 2
        assert result.totalSuccess == 1
        assert result.totalFailed == 1
        print(f"      → 混合: 成功={result.totalSuccess}, 失败={result.totalFailed}")
    proc4.wait(timeout=5)

    result = _run(M, "空PID列表", lambda: batchKillProcesses([], BatchKillMode.SIGTERM))
    if result:
        assert result.totalRequested == 0
        assert result.totalSuccess == 0
        assert result.totalFailed == 0
        print(f"      → 空列表: 请求={result.totalRequested}")


def testBatchKillProcessesSIGKILL():
    M = "batchKillProcesses(SIGKILL)"

    proc = _spawnSleepProcess()
    time.sleep(0.3)

    result = _run(M, f"SIGKILL终止子进程(PID={proc.pid})", lambda: batchKillProcesses([proc.pid], BatchKillMode.SIGKILL))
    if result:
        assert result.totalSuccess == 1, "SIGKILL应成功"
        print(f"      → SIGKILL成功: PID={proc.pid}")

    proc.wait(timeout=5)


def main():
    print(f"当前进程 PID: {os.getpid()}")

    testListProcesses()
    testListProcessesWithPorts()
    testGetProcessDetail()
    testKillProcess()
    testAutoCleanProcesses()
    testGetZombieOrphanProcesses()
    testBatchKillProcesses()
    testBatchKillProcessesSIGKILL()

    errors = _printReport()
    return errors


if __name__ == "__main__":
    exit(main())
