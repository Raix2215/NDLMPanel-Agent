from ndlmpanel_agent.models.ops.service.service_models import ServiceAction, ServiceOperationResult
from ndlmpanel_agent.tools.ops._command_runner import runCommand


def manageSystemService(
    serviceName: str,
    action: ServiceAction,
) -> ServiceOperationResult:
    if action == ServiceAction.STATUS:
        result = runCommand(
            ["systemctl", "is-active", serviceName],
            checkReturnCode=False,
        )
        return ServiceOperationResult(
            success=True,
            serviceName=serviceName,
            currentStatus=result.stdout.strip(),
        )

    # start/stop/restart/enable/disable 需要 sudo
    runCommand(
        ["systemctl", action.value, serviceName],
        useSudo=True,
    )

    # 查询操作后的状态
    statusResult = runCommand(
        ["systemctl", "is-active", serviceName],
        checkReturnCode=False,
    )

    return ServiceOperationResult(
        success=True,
        serviceName=serviceName,
        currentStatus=statusResult.stdout.strip(),
        message=f"已执行 {action.value} 操作",
    )
