"""E2B execution provider.

Concrete E2B implementation of Accord's vendor-neutral execution
provider interface.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID, uuid4

from e2b import AsyncSandbox

from app.config import settings
from app.services.execution.base import (
    ExecutionArtifact,
    ExecutionConfigurationError,
    ExecutionEnvironment,
    ExecutionEnvironmentStatus,
    ExecutionEvent,
    ExecutionEventKind,
    ExecutionFile,
    ExecutionHandle,
    ExecutionProvider,
    ExecutionProviderError,
    ExecutionRequest,
    ExecutionResult,
    ExecutionTask,
)


@dataclass
class _E2BExecution:
    """Internal state for one E2B execution."""

    execution_id: UUID
    environment_id: UUID
    command: Any | None = None
    events: asyncio.Queue[ExecutionEvent | None] = field(
        default_factory=asyncio.Queue
    )
    sequence: int = 0
    result: ExecutionResult | None = None
    started_at: float = field(default_factory=time.monotonic)

    def next_sequence(self) -> int:
        sequence = self.sequence
        self.sequence += 1
        return sequence


class E2BExecutionProvider(ExecutionProvider):
    """Execution provider backed by E2B sandboxes."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        default_timeout_seconds: int | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._default_timeout_seconds = (
            default_timeout_seconds or settings.execution_timeout_seconds
        )

        self._sandboxes: dict[UUID, AsyncSandbox] = {}
        self._executions: dict[UUID, _E2BExecution] = {}

    @property
    def name(self) -> str:
        return "e2b"

    async def create_environment(
        self,
        request: ExecutionRequest,
    ) -> ExecutionEnvironment:
        """Create an E2B sandbox and populate its initial files."""

        template = request.image or "base"

        try:
            create_kwargs: dict[str, Any] = {
                "timeout": request.timeout_seconds,
            }

            if self._api_key is not None:
                create_kwargs["api_key"] = self._api_key

            if self._base_url is not None:
                create_kwargs["domain"] = self._base_url

            if request.environment:
                create_kwargs["envs"] = request.environment

            sandbox = await AsyncSandbox.create(
                template,
                **create_kwargs,
            )
        except Exception as exc:
            raise ExecutionProviderError(
                f"Failed to create E2B environment: {exc}"
            ) from exc

        environment_id = uuid4()

        environment = ExecutionEnvironment(
            id=environment_id,
            provider=self.name,
            external_id=sandbox.sandbox_id,
            status=ExecutionEnvironmentStatus.READY,
            metadata={
                **request.metadata,
                "template": template,
                "working_directory": request.working_directory,
            },
        )

        self._sandboxes[environment_id] = sandbox

        try:
            await self._prepare_environment(sandbox, request)
        except Exception:
            self._sandboxes.pop(environment_id, None)

            try:
                await sandbox.kill()
            except Exception:
                pass

            raise

        return environment

    async def _prepare_environment(
        self,
        sandbox: AsyncSandbox,
        request: ExecutionRequest,
    ) -> None:
        """Create the requested working directory and initial files."""

        if request.working_directory:
            await sandbox.files.make_dir(request.working_directory)

        for file in request.files:
            path = self._resolve_path(
                request.working_directory,
                file.path,
            )

            if file.content is None:
                continue

            await sandbox.files.write(
                path,
                file.content,
            )

    async def start_execution(
        self,
        environment: ExecutionEnvironment,
        task: ExecutionTask,
    ) -> ExecutionHandle:
        """Start an E2B command without waiting for completion."""
    
        sandbox = self._get_sandbox(environment)
    
        execution_id = uuid4()
    
        execution = _E2BExecution(
            execution_id=execution_id,
            environment_id=environment.id,
        )
    
        self._executions[execution_id] = execution
    
        await self._emit(
            execution,
            ExecutionEventKind.STARTED,
            {
                "command": task.command,
                "args": task.args,
            },
        )
    
        command = self._build_command(
            task.command,
            task.args,
        )
    
        timeout = (
            task.timeout_seconds
            or self._default_timeout_seconds
        )
    
        async def on_stdout(data: str) -> None:
            await self._emit(
                execution,
                ExecutionEventKind.STDOUT,
                data,
            )
    
        async def on_stderr(data: str) -> None:
            await self._emit(
                execution,
                ExecutionEventKind.STDERR,
                data,
            )
    
        try:
            execution.command = await sandbox.commands.run(
                command,
                background=True,
                envs=task.environment or None,
                cwd=task.working_directory,
                on_stdout=on_stdout,
                on_stderr=on_stderr,
                timeout=timeout,
            )
        except Exception as exc:
            await self._emit(
                execution,
                ExecutionEventKind.FAILED,
                str(exc),
            )
    
            await execution.events.put(None)
    
            self._executions.pop(
                execution_id,
                None,
            )
    
            raise ExecutionProviderError(
                f"E2B execution failed to start: {exc}"
            ) from exc
    
        return ExecutionHandle(
            execution_id=execution_id,
            environment_id=environment.id,
            metadata={
                "provider": self.name,
                "sandbox_id": environment.external_id,
                "pid": execution.command.pid,
            },
        )

    async def wait_execution(
        self,
        handle: ExecutionHandle,
    ) -> ExecutionResult:
        """Wait for a started E2B execution."""
    
        execution = self._executions.get(
            handle.execution_id
        )
    
        if execution is None:
            raise ExecutionProviderError(
                f"Unknown execution: {handle.execution_id}"
            )
    
        command = execution.command
    
        if command is None:
            raise ExecutionProviderError(
                f"Execution {handle.execution_id} "
                "has no command handle."
            )
    
        try:
            command_result = await command.wait()
    
            duration_ms = int(
                (
                    time.monotonic()
                    - execution.started_at
                )
                * 1000
            )
    
            execution.result = ExecutionResult(
                execution_id=handle.execution_id,
                environment_id=handle.environment_id,
                exit_code=command_result.exit_code,
                stdout=command_result.stdout,
                stderr=command_result.stderr,
                timed_out=False,
                duration_ms=duration_ms,
                metadata={
                    "provider": self.name,
                    **handle.metadata,
                },
            )
    
            await self._emit(
                execution,
                ExecutionEventKind.COMPLETED,
                {
                    "exit_code": command_result.exit_code,
                    "duration_ms": duration_ms,
                },
            )
    
            return execution.result
    
        except Exception as exc:
            duration_ms = int(
                (
                    time.monotonic()
                    - execution.started_at
                )
                * 1000
            )
    
            await self._emit(
                execution,
                ExecutionEventKind.FAILED,
                str(exc),
            )
    
            execution.result = ExecutionResult(
                execution_id=handle.execution_id,
                environment_id=handle.environment_id,
                exit_code=None,
                stdout="",
                stderr=str(exc),
                timed_out=False,
                duration_ms=duration_ms,
                metadata={
                    "provider": self.name,
                    "error": str(exc),
                    **handle.metadata,
                },
            )
    
            return execution.result
    
        finally:
            await execution.events.put(None)
        
    async def stream_events(
        self,
        handle: ExecutionHandle,
    ):
        """Stream events for an execution."""
    
        execution = self._executions.get(
            handle.execution_id
        )
    
        if execution is None:
            raise ExecutionProviderError(
                f"Unknown execution: {handle.execution_id}"
            )
    
        if execution.environment_id != handle.environment_id:
            raise ExecutionProviderError(
                "Execution does not belong to the supplied environment."
            )
    
        while True:
            event = await execution.events.get()
    
            if event is None:
                break
    
            yield event

    async def collect_artifacts(
        self,
        environment: ExecutionEnvironment,
    ) -> list[ExecutionArtifact]:
        """Collect files currently present in the sandbox workspace."""

        sandbox = self._get_sandbox(environment)

        working_directory = str(
            environment.metadata.get(
                "working_directory",
                "/workspace",
            )
        )

        try:
            result = await sandbox.commands.run(
                "find . -type f -print0",
                cwd=working_directory,
                timeout=self._default_timeout_seconds,
            )
        except Exception as exc:
            raise ExecutionProviderError(
                f"Failed to enumerate E2B artifacts: {exc}"
            ) from exc

        if result.exit_code != 0:
            raise ExecutionProviderError(
                "Failed to enumerate E2B artifacts: "
                f"{result.stderr}"
            )

        raw_paths = result.stdout.split("\0")

        artifacts: list[ExecutionArtifact] = []

        for raw_path in raw_paths:
            if not raw_path:
                continue

            relative_path = raw_path.removeprefix("./")
            path = self._resolve_path(
                working_directory,
                relative_path,
            )

            try:
                content = bytes(
                    await sandbox.files.read(
                        path,
                        format="bytes",
                    )
                )
            except Exception as exc:
                raise ExecutionProviderError(
                    f"Failed to read E2B artifact '{path}': {exc}"
                ) from exc

            artifacts.append(
                ExecutionArtifact(
                    environment_id=environment.id,
                    path=path,
                    size_bytes=len(content),
                    content=self._content_or_none(content),
                    metadata={
                        "provider": self.name,
                    },
                )
            )

        return artifacts

    async def destroy_environment(
        self,
        environment: ExecutionEnvironment,
    ) -> None:
        """Terminate an E2B sandbox."""

        sandbox = self._sandboxes.pop(environment.id, None)

        if sandbox is None:
            return

        try:
            await sandbox.kill()
        except Exception as exc:
            raise ExecutionProviderError(
                f"Failed to destroy E2B environment "
                f"{environment.external_id}: {exc}"
            ) from exc
        finally:
            for execution_id, execution in list(
                self._executions.items()
            ):
                if execution.environment_id == environment.id:
                    self._executions.pop(execution_id, None)

    async def close(self) -> None:
        """Release provider resources and terminate owned sandboxes."""

        environment_ids = list(self._sandboxes)

        errors: list[Exception] = []

        for environment_id in environment_ids:
            environment = ExecutionEnvironment(
                id=environment_id,
                provider=self.name,
                external_id=self._sandboxes[
                    environment_id
                ].sandbox_id,
            )

            try:
                await self.destroy_environment(environment)
            except Exception as exc:
                errors.append(exc)

        if errors:
            raise ExecutionProviderError(
                f"Failed to close E2B provider: {errors[0]}"
            )

    async def _emit(
        self,
        execution: _E2BExecution,
        kind: ExecutionEventKind,
        data: str | dict[str, Any],
    ) -> None:
        await execution.events.put(
            ExecutionEvent(
                execution_id=execution.execution_id,
                environment_id=execution.environment_id,
                kind=kind,
                data=data,
                sequence=execution.next_sequence(),
                metadata={
                    "provider": self.name,
                },
            )
        )

    def _get_sandbox(
        self,
        environment: ExecutionEnvironment,
    ) -> AsyncSandbox:
        sandbox = self._sandboxes.get(environment.id)

        if sandbox is None:
            raise ExecutionProviderError(
                f"Unknown execution environment: {environment.id}"
            )

        return sandbox

    @staticmethod
    def _build_command(
        command: str,
        args: list[str],
    ) -> str:
        """Build a shell command without reinterpreting arguments."""

        import shlex

        return " ".join(
            [shlex.quote(command), *map(shlex.quote, args)]
        )

    @staticmethod
    def _resolve_path(
        working_directory: str,
        path: str,
    ) -> str:
        """Resolve a provider-neutral relative path safely."""

        candidate = PurePosixPath(path)

        if candidate.is_absolute():
            return str(candidate)

        return str(
            PurePosixPath(working_directory) / candidate
        )

    @staticmethod
    def _content_or_none(content: bytes) -> bytes | None:
        return content if content else b""