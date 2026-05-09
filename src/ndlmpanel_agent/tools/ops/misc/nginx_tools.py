import os
import re
import tempfile
import urllib.request
from ndlmpanel_agent.exceptions import (
    ServiceUnavailableException,
    ToolExecutionException,
)
from ndlmpanel_agent.models.ops.misc.nginx_models import NginxInstallInfo, NginxStatus,NginxSiteCreateResult
from ndlmpanel_agent.tools.ops._command_runner import runCommand

def checkNginxInstalled() -> NginxInstallInfo:
    try:
        result = runCommand(["nginx", "-v"], checkReturnCode=False)
        output = result.stderr.strip() or result.stdout.strip()

        version = None
        vMatch = re.search(r"nginx/([\d.]+)", output)
        if vMatch:
            version = vMatch.group(1)

        configPath = None
        testResult = runCommand(["nginx", "-t"], checkReturnCode=False)
        cMatch = re.search(r"configuration file (\S+)", testResult.stderr)
        if cMatch:
            configPath = cMatch.group(1)

        return NginxInstallInfo(
            isInstalled=True, version=version, configPath=configPath
        )
    except ToolExecutionException:
        return NginxInstallInfo(isInstalled=False)


def getNginxStatus() -> NginxStatus:
    if not checkNginxInstalled().isInstalled:
        raise ServiceUnavailableException("Nginx 未安装")

    isRunning = False
    workerCount = 0

    try:
        result = runCommand(["systemctl", "is-active", "nginx"], checkReturnCode=False)
        isRunning = result.stdout.strip() == "active"
    except ToolExecutionException:
        pass

    if isRunning:
        try:
            result = runCommand(
                ["pgrep", "-c", "-f", "nginx: worker"], checkReturnCode=False
            )
            workerCount = int(result.stdout.strip())
        except (ToolExecutionException, ValueError):
            pass

    # 尝试读取 stub_status 获取连接数
    activeConnections = None
    try:
        resp = urllib.request.urlopen("http://127.0.0.1/nginx_status", timeout=2)
        content = resp.read().decode()
        connMatch = re.search(r"Active connections:\s*(\d+)", content)
        if connMatch:
            activeConnections = int(connMatch.group(1))
    except Exception:
        pass

    return NginxStatus(
        isRunning=isRunning,
        workerProcessCount=workerCount,
        activeConnections=activeConnections,
        requestsPerSecond=None,
    )

def generateStaticSiteConfig(domain: str, rootPath: str, listenPort: int = 80) -> str:
    return f"""server {{
    listen {listenPort};
    server_name {domain};
    root {rootPath};
    index index.html;
    location / {{
        try_files $uri $uri/ =404;
    }}
}}"""

def generateProxyConfig(domain: str, proxyPass: str, listenPort: int) -> str:
    return f"""server {{
    listen {listenPort};
    server_name {domain};
    location / {{
        proxy_pass {proxyPass};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}"""

def createNginxSite(
        domain: str,
        mode: str,
        listenPort: int,
        rootPath: str | None = None,
        proxyPass: str | None = None
)-> NginxSiteCreateResult:
    mode = mode.strip().lower()
    if mode == "static":
        if not rootPath:
            raise ToolExecutionException("静态站点必须提供 rootPath")
        configContent = generateStaticSiteConfig(domain, rootPath, listenPort)
    elif mode == "reverse_proxy":
        if not proxyPass:
            raise ToolExecutionException("反向代理必须提供 proxyPass")
        configContent = generateProxyConfig(domain, proxyPass, listenPort)
    else:
        raise ToolExecutionException("不支持的模式")
    
    configPath = saveNginxConfig(domain, configContent)
    try:
        testNginxConfig()
    except ToolExecutionException:
        runCommand(["rm", "-f", configPath], useSudo=True, checkReturnCode=False)
        raise

    reloadNginx()

    return NginxSiteCreateResult(
        domain=domain,
        mode=mode,
        listenPort=listenPort,
        configPath=configPath,
        enabledPath=configPath,
        rootPath=rootPath if mode == "static" else None,
        proxyPass=proxyPass if mode == "reverse_proxy" else None,
        isEnabled=True,
        isReloaded=True,
    )   


def createNginxReverseProxySite(
    domain:str,
    proxyPort:str,
    proxyPass:str,
    listenPort:int,
    proxyProtocol:str="http"
)-> NginxSiteCreateResult:
    proxyPass = f"{proxyProtocol}://{proxyPass}:{proxyPort}"
    return createNginxSite(
        domain=domain,
        mode="reverse_proxy",
        listenPort=listenPort,
        proxyPass=proxyPass
)

# 保存 Nginx 配置文件到系统
def saveNginxConfig(configName, configContent):
    siteName = configName.replace("*.", "").replace("/", "_")
    if siteName.endswith(".conf"):
        siteName = siteName[:-5]
    configPath = f"/etc/nginx/sites-enabled/{siteName}.conf"

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        suffix=".conf",
    ) as tmpFile:
        tmpFile.write(configContent)
        tmpPath = tmpFile.name

    try:
        runCommand(["install", "-D", "-m", "644", tmpPath, configPath], useSudo=True)
    finally:
        try:
            os.unlink(tmpPath)
        except OSError:
            pass

    return configPath


# 测试 Nginx 配置是否合法
def testNginxConfig():
    runCommand(["nginx", "-t"], useSudo=True)


# 重载 Nginx 使配置生效
def reloadNginx():
    runCommand(["systemctl", "reload", "nginx"], useSudo=True)


# 重启 Nginx
def restartNginx():
    runCommand(["systemctl", "restart", "nginx"], useSudo=True)


# 获取所有已创建的站点列表
def getNginxSiteList():
    pass
# 删除指定站点配置
def deleteNginxSite(configName):
    pass
# 自动申请 SSL 证书
def applySslCertificate(domain, email):
    pass
# 自动配置 SSL 到 Nginx
def configSslForNginx(domain, certPath, keyPath):
    pass
# 自动续期 SSL 证书
def renewSslCertificate(domain):
    pass
