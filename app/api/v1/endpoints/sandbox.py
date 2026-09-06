"""Execution smoke-test endpoint.

Temporary endpoint for verifying the configured execution provider.
Remove after E2B integration has been verified.
"""

from fastapi import APIRouter, HTTPException

from app.services.execution import (
    ExecutionProviderError,
    ExecutionRequest,
    ExecutionTask,
    get_execution_provider,
)

router = APIRouter(tags=["sandbox"])


@router.post("/sandbox/test", summary="Test execution provider")
async def test_sandbox() -> dict:
    provider = get_execution_provider()

    environment = None

    try:
        environment = await provider.create_environment(
            ExecutionRequest(
                image="base",
                working_directory="/workspace",
            )
        )

        result = await provider.execute(
            environment,
            ExecutionTask(
                command="python",
                args=[
                    "-c",
                    "print('Accord E2B execution works')",
                ],
            ),
        )

        return {
            "provider": provider.name,
            "environment_id": str(environment.id),
            "external_id": environment.external_id,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": result.timed_out,
            "duration_ms": result.duration_ms,
        }

    except ExecutionProviderError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    finally:
        if environment is not None:
            try:
                await provider.destroy_environment(environment)
            except ExecutionProviderError:
                pass