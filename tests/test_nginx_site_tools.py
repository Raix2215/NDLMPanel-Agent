import subprocess

import pytest

from ndlmpanel_agent.exceptions import ToolExecutionException
from ndlmpanel_agent.models.ops.misc.nginx_models import NginxSiteMode
from ndlmpanel_agent.tools.ops.misc import nginx_tools


def _patchRunCommand(monkeypatch, failNginxTest: bool = False):
    commands = []
    installedFiles = {}

    def fakeRunCommand(command, timeout=30, checkReturnCode=True, useSudo=False):
        commands.append(
            {
                "command": command,
                "timeout": timeout,
                "checkReturnCode": checkReturnCode,
                "useSudo": useSudo,
            }
        )

        if command[:4] == ["install", "-D", "-m", "644"]:
            tmpPath = command[4]
            configPath = command[5]
            with open(tmpPath, encoding="utf-8") as tmpFile:
                installedFiles[configPath] = tmpFile.read()
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        if command == ["nginx", "-t"]:
            if failNginxTest:
                raise ToolExecutionException("nginx 配置测试失败")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        if command[:2] == ["rm", "-f"]:
            installedFiles.pop(command[2], None)
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(nginx_tools, "runCommand", fakeRunCommand)
    return commands, installedFiles


def testCreateNginxStaticSiteWritesConfigAndReloads(monkeypatch):
    commands, installedFiles = _patchRunCommand(monkeypatch)

    result = nginx_tools.createNginxSite(
        domain="example.com",
        mode="static",
        listenPort=80,
        rootPath="/var/www/example.com",
    )

    configPath = "/etc/nginx/sites-enabled/example.com.conf"
    assert result.domain == "example.com"
    assert result.mode == NginxSiteMode.STATIC
    assert result.configPath == configPath
    assert result.enabledPath == configPath
    assert result.rootPath == "/var/www/example.com"
    assert result.proxyPass is None
    assert result.isEnabled is True
    assert result.isReloaded is True

    config = installedFiles[configPath]
    assert "server_name example.com;" in config
    assert "root /var/www/example.com;" in config
    assert "try_files $uri $uri/ =404;" in config

    commandList = [item["command"] for item in commands]
    assert ["nginx", "-t"] in commandList
    assert ["systemctl", "reload", "nginx"] in commandList
    assert all(
        item["useSudo"]
        for item in commands
        if item["command"][0] in {"install", "nginx", "systemctl"}
    )


def testCreateNginxReverseProxySiteWritesProxyConfig(monkeypatch):
    _, installedFiles = _patchRunCommand(monkeypatch)

    result = nginx_tools.createNginxSite(
        domain="api.example.com",
        mode="reverse_proxy",
        listenPort=8080,
        proxyPass="http://127.0.0.1:3000",
    )

    configPath = "/etc/nginx/sites-enabled/api.example.com.conf"
    assert result.mode == NginxSiteMode.REVERSE_PROXY
    assert result.listenPort == 8080
    assert result.proxyPass == "http://127.0.0.1:3000"
    assert result.rootPath is None

    config = installedFiles[configPath]
    assert "listen 8080;" in config
    assert "server_name api.example.com;" in config
    assert "proxy_pass http://127.0.0.1:3000;" in config
    assert "proxy_set_header Host $host;" in config
    assert "proxy_set_header X-Real-IP $remote_addr;" in config
    assert "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;" in config
    assert "proxy_set_header X-Forwarded-Proto $scheme;" in config


def testCreateNginxSiteRollsBackConfigWhenNginxTestFails(monkeypatch):
    commands, installedFiles = _patchRunCommand(monkeypatch, failNginxTest=True)

    with pytest.raises(ToolExecutionException):
        nginx_tools.createNginxSite(
            domain="broken.example.com",
            mode="reverse_proxy",
            listenPort=80,
            proxyPass="http://127.0.0.1:3000",
        )

    configPath = "/etc/nginx/sites-enabled/broken.example.com.conf"
    assert configPath not in installedFiles

    commandList = [item["command"] for item in commands]
    assert ["rm", "-f", configPath] in commandList
    assert ["systemctl", "reload", "nginx"] not in commandList


def testCreateNginxSiteRejectsMissingModeSpecificArguments(monkeypatch):
    _patchRunCommand(monkeypatch)

    with pytest.raises(ToolExecutionException):
        nginx_tools.createNginxSite(
            domain="example.com",
            mode="static",
            listenPort=80,
        )

    with pytest.raises(ToolExecutionException):
        nginx_tools.createNginxSite(
            domain="example.com",
            mode="reverse_proxy",
            listenPort=80,
        )

    with pytest.raises(ToolExecutionException):
        nginx_tools.createNginxSite(
            domain="example.com",
            mode="unknown",
            listenPort=80,
            rootPath="/var/www/example.com",
        )
